"""Pagination primitives shared by every list endpoint.

Defined once so that "page 2, size 20" means the same thing everywhere, and so
use cases can express paging without importing anything web-related. The wire
format is in docs/API_SPECIFICATION.md §1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PageRequest:
    """A request for one page of results (1-indexed, as the API exposes it)."""

    page: int = 1
    size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be 1 or greater")
        if not 1 <= self.size <= MAX_PAGE_SIZE:
            raise ValueError(f"size must be between 1 and {MAX_PAGE_SIZE}")

    @property
    def offset(self) -> int:
        """How many rows to skip — the database's view of the same request."""
        return (self.page - 1) * self.size


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of results plus the total count, for rendering page controls."""

    items: Sequence[T]
    total: int
    page: int
    size: int

    @property
    def has_next(self) -> bool:
        return self.page * self.size < self.total
