"""Database plumbing: engine, sessions, and the Unit of Work adapter.

This is infrastructure. Business code never imports it — it receives a
:class:`~app.shared.ports.unit_of_work.UnitOfWork` and works through that.

One subtlety worth reading, because it prevents a whole class of
"works in dev, breaks in production" bug: **SQLite ignores foreign keys unless
told otherwise.** Our schema leans on cascading deletes (deleting a job should
delete its items, transcripts, and segments). Without the pragma below, those
cascades silently do nothing on a developer's machine, and the missing behaviour
only shows up on production Postgres, which does enforce them. So we switch
foreign keys on for every SQLite connection and keep the two engines honest.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Self

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.shared.ports.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base that every SQLAlchemy model inherits from.

    Alembic reads ``Base.metadata`` to work out what the schema should look like,
    which is why new model modules must be imported in ``migrations/env.py`` —
    a model Alembic cannot see is a table Alembic will not create.
    """


def create_database_engine(settings: Settings) -> Engine:
    """Build the SQLAlchemy engine for the configured database.

    The engine is the connection pool for the whole process; it is created once
    in the composition root, not per request.
    """
    url = make_url(settings.database_url)
    is_sqlite = url.get_backend_name() == "sqlite"

    connect_args: dict[str, Any] = {}
    if is_sqlite:
        _ensure_sqlite_parent_directory(url.database)
        # Background work runs on a different thread from the request that
        # started it, and SQLite objects are thread-bound by default.
        connect_args["check_same_thread"] = False

    engine = create_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,  # detect connections dropped by the server or a restart
        connect_args=connect_args,
    )

    if is_sqlite:
        _enable_sqlite_foreign_keys(engine)

    logger.info("database_engine_created", backend=url.get_backend_name())
    return engine


def _ensure_sqlite_parent_directory(database: str | None) -> None:
    """Create the folder for a file-backed SQLite database if it is missing.

    Saves a confusing "unable to open database file" on a fresh checkout, where
    the configured ``data/`` directory does not exist yet (it is git-ignored).
    """
    if not database or database == ":memory:":
        return
    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Turn on foreign-key enforcement for every SQLite connection."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the session factory used by the Unit of Work.

    ``expire_on_commit=False`` so that objects remain readable after commit —
    otherwise returning an entity from a use case triggers a surprise reload
    (or fails, if the session has already closed).
    """
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ping(engine: Engine) -> bool:
    """Return whether the database answers a trivial query.

    Used by the readiness check: a process that cannot reach its database is
    running but not *ready*, and should not receive traffic.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database_ping_failed")
        return False
    return True


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of the transaction boundary.

    Usage::

        with unit_of_work as uow:
            ...                 # make changes
            uow.commit()        # explicit, always

    Without an explicit ``commit()`` the block rolls back. That default is
    deliberate: a use case that raises halfway through leaves nothing behind,
    so partial writes are impossible by construction rather than by vigilance.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False

    @property
    def session(self) -> Session:
        """The active session. Raises if used outside a ``with`` block."""
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.session accessed outside a 'with' block; "
                "enter the unit of work first."
            )
        return self._session

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if not self._committed:
                self.rollback()
        finally:
            if self._session is not None:
                self._session.close()
                self._session = None

    def commit(self) -> None:
        self.session.commit()
        self._committed = True

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
