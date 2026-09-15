"""Port: a transaction boundary.

A "unit of work" is a group of changes that must succeed or fail together.
Creating a batch job writes one job row and N item rows; if the process dies
between them, we must not be left with a job that has no items.

Use cases therefore express intent — *these changes belong together* — and never
touch a database session. Two things follow:

  * business logic can be tested with an in-memory fake that records calls
  * the persistence technology can change without touching a single use case

Adapter: :class:`app.core.database.SqlAlchemyUnitOfWork`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class UnitOfWork(ABC):
    """A transaction, used as a context manager.

    Commit is always explicit. Leaving the block without committing rolls back,
    so a use case that raises partway through cannot leave half its changes
    behind — the safe outcome is the default one.
    """

    @abstractmethod
    def __enter__(self) -> Self:
        """Begin the unit of work."""

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back unless :meth:`commit` was called, then release resources."""

    @abstractmethod
    def commit(self) -> None:
        """Persist every change made in this unit of work."""

    @abstractmethod
    def rollback(self) -> None:
        """Discard every change made in this unit of work."""
