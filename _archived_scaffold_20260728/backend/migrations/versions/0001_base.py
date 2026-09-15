"""base revision

Establishes the migration chain. No tables yet — Phase 1 adds the auth schema
and Phase 2 the transcription schema.

Why an empty migration exists at all: it gives every later revision a common
ancestor and proves the migration machinery runs end to end before any real
schema depends on it. A fresh database and a long-lived one then follow the
exact same numbered path.

Revision ID: 0001_base
Revises: None

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_base"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nothing to do: this revision only marks the start of the chain."""


def downgrade() -> None:
    """Nothing to undo."""
