"""Port: the current time.

Asking for the time looks too trivial to abstract — until you try to test it.
Several rules in this system are time-based:

  * a worker's lease expires after N seconds (crash recovery)
  * an access token expires after 15 minutes
  * a failed item retries after an exponential backoff

Tested against the real clock, those require either sleeping for minutes or
accepting flaky tests. With a clock behind a port, a test can hand the code a
fixed or fast-forwarded time and assert the rule directly.

Adapter: :class:`app.core.clock.SystemClock`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Supplies the current time as a timezone-aware UTC datetime."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time in UTC.

        Always timezone-aware. Naive datetimes are a recurring source of
        off-by-hours bugs, so they are not permitted anywhere in this codebase.
        """
