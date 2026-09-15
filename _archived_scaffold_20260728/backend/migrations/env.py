"""Alembic environment.

Bridges Alembic to our application configuration so that migrations always run
against the same database the app uses, with no duplicated connection string.

Two settings below matter more than they look:

* ``render_as_batch=True`` — SQLite cannot ``ALTER TABLE`` the way Postgres can.
  Batch mode rewrites such changes as create-copy-swap, so one migration script
  runs on both engines. Without it, any future column change would fail in dev.
* ``compare_type=True`` — autogenerate notices column *type* changes, not only
  added and removed columns.
"""

from __future__ import annotations

from alembic import context

from app.core.config import get_settings
from app.core.database import Base, create_database_engine

# ─────────────────────────────────────────────────────────────────────────────
# Import every module that defines SQLAlchemy models here.
#
# Alembic compares the live database against ``Base.metadata``. A model class
# that has not been imported is invisible to it, and autogenerate will cheerfully
# report "no changes detected" — or worse, try to drop the table.
#
# Phase 1 adds:  from app.modules.auth.infrastructure import models  # noqa: F401
# ─────────────────────────────────────────────────────────────────────────────

target_metadata = Base.metadata
settings = get_settings()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (``alembic upgrade head --sql``).

    Useful when a production database change has to be reviewed or applied by
    someone other than the deploy process.
    """
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
