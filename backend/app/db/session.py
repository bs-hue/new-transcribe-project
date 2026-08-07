"""Async engine, session factory, and schema bootstrap."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings
from app.db.models import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _prepare_sqlite_path(database_url: str) -> None:
    """Make sure the directory holding the SQLite file exists."""
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return
    file_part = database_url[len(prefix) :]
    if file_part in ("", ":memory:") or file_part.startswith(":memory:"):
        return
    Path(file_part).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _apply_sqlite_pragmas(engine: AsyncEngine) -> None:
    """WAL + foreign keys.

    WAL lets the worker write while the API reads, which is the whole reason
    SQLite is viable for this workload. Foreign keys are off by default in
    SQLite, so cascades would silently not happen without this.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _prepare_sqlite_path(settings.database_url)
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            future=True,
        )
        if settings.is_sqlite:
            _apply_sqlite_pragmas(_engine)
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(settings),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional session for background work (outside the request cycle)."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(settings: Settings | None = None) -> None:
    """Create tables and the search index if they do not exist.

    V1 deliberately uses ``create_all`` rather than a migration tool: there is
    one schema version and no production data to migrate. The moment the schema
    changes under a live deployment, add Alembic — the models are already
    structured for it.
    """
    settings = settings or get_settings()
    engine = get_engine(settings)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.services.search import get_search_backend

    await get_search_backend(settings).initialise(engine)
    logger.info("Database ready (%s)", "sqlite" if settings.is_sqlite else "external")


async def dispose_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def healthcheck() -> bool:
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - only on a broken database
        logger.exception("Database healthcheck failed")
        return False
