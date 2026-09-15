"""Adapter: the real system clock.

The plug for :class:`app.shared.ports.clock.Clock`. Trivial by design — all the
value is in the fact that business rules depend on the *port*, so tests can
substitute a fixed clock instead of sleeping.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.shared.ports.clock import Clock


class SystemClock(Clock):
    """Returns the actual current time, in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)
