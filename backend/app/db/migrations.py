"""Running schema migrations.

Wraps Alembic so a deployment does not have to know Alembic's vocabulary, and
so the awkward case is handled correctly rather than being left to whoever is
deploying at the time.

That awkward case: databases created by ``create_all`` before this project had
migrations. They hold the right tables but no ``alembic_version`` row, so a
plain ``upgrade`` would try to create tables that already exist and fail. Those
are stamped as being at the initial revision first, which records where they
already are without touching a single row of data.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# app/db/migrations.py -> app/db -> app -> backend
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


def _config():  # noqa: ANN202 - alembic's Config, imported lazily
    from alembic.config import Config

    if not _ALEMBIC_INI.exists():
        raise RuntimeError(
            f"Cannot find {_ALEMBIC_INI}. The migration scripts must be "
            "deployed alongside the application."
        )
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return config


def _first_revision(config) -> str:  # noqa: ANN001, ANN202
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    bases = script.get_bases()
    if not bases:
        raise RuntimeError("No migration scripts found.")
    return bases[0]


async def _table_names(database_url: str) -> set[str]:
    # Deliberately the async driver, the same one the app uses. Converting the
    # URL to a synchronous one would demand a second database driver be
    # installed purely for this check — psycopg2 alongside asyncpg.
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return set(
                await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            )
    finally:
        await engine.dispose()


def _state(database_url: str) -> tuple[bool, bool]:
    """Returns (has_alembic_version, has_application_tables)."""
    tables = asyncio.run(_table_names(database_url))
    return "alembic_version" in tables, "users" in tables


def upgrade_to_head(settings: Settings | None = None) -> str:
    """Bring the database to the latest schema. Returns what it did.

    Safe to run on every start: an up-to-date database is a no-op.
    """
    from alembic import command

    settings = settings or get_settings()
    config = _config()
    tracked, populated = _state(settings.database_url)

    action = "upgraded"
    if not tracked and populated:
        # Pre-migration database. Record it at the initial revision so the
        # upgrade below applies only what came after.
        revision = _first_revision(config)
        logger.info("Adopting migrations on an existing database (stamp %s)", revision)
        command.stamp(config, revision)
        action = "adopted and upgraded"

    command.upgrade(config, "head")
    logger.info("Database schema is up to date (%s)", action)
    return action
