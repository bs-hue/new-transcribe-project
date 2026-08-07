"""Copy an existing SQLite library into PostgreSQL (or Supabase).

Moving the database leaves the old transcripts behind: the app looks at the new
one and the library appears empty. Nothing is lost — it is simply in the other
file — and this brings it across.

    python scripts/copy_sqlite_to_postgres.py \
        --source sqlite+aiosqlite:////data/app.db \
        --target "postgresql+asyncpg://...?ssl=require"

Copies videos, transcripts and their segments — the research itself. It
deliberately does not copy:

* **users**, because the target already has accounts and matching them by email
  would either collide or silently create duplicates. Sign in with the account
  the new database already knows.
* **jobs**, because a job is a record of work that has already finished. Keeping
  them would mean rewriting every ``submitted_by`` to point at a user that was
  not copied.
* **app_settings**, because those are deliberately per-deployment.

Safe to run twice: rows that already exist are skipped rather than duplicated.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base, Transcript, TranscriptSegment, Video

# Parents before children: a transcript cannot be inserted before its video.
ORDER: tuple[type[Base], ...] = (Video, Transcript, TranscriptSegment)


async def _copy_table(source_engine, target_engine, table: Table) -> tuple[int, int]:
    """Returns (rows found, rows inserted)."""
    async with source_engine.connect() as source:
        rows = [dict(row._mapping) for row in await source.execute(select(table))]

    if not rows:
        return 0, 0

    async with target_engine.begin() as target:
        before = (await target.execute(select(table))).rowcount
        # ON CONFLICT DO NOTHING makes this re-runnable: a partial copy can be
        # finished by running it again rather than cleaned up first.
        await target.execute(pg_insert(table).on_conflict_do_nothing(), rows)
        after = len(
            (await target.execute(select(table.c[list(table.primary_key.columns)[0].name]))).all()
        )

    return len(rows), after - max(before, 0)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="SQLite URL to read from")
    parser.add_argument("--target", required=True, help="PostgreSQL URL to write to")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be copied without writing anything",
    )
    args = parser.parse_args()

    source_engine = create_async_engine(args.source)
    target_engine = create_async_engine(args.target)

    try:
        total = 0
        for model in ORDER:
            table = model.__table__
            async with source_engine.connect() as source:
                found = len((await source.execute(select(table.c.id))).all())

            if args.dry_run:
                print(f"  {table.name}: {found} rows would be copied")
                continue

            found, inserted = await _copy_table(source_engine, target_engine, table)
            skipped = found - inserted
            note = f" ({skipped} already there)" if skipped > 0 else ""
            print(f"  {table.name}: {inserted} copied{note}")
            total += inserted

        if not args.dry_run:
            print(f"\nDone — {total} rows copied.")
    finally:
        await source_engine.dispose()
        await target_engine.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
