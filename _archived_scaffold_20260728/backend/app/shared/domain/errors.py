"""Domain error vocabulary.

Business code raises these. Note what is absent: any mention of HTTP status
codes. A use case that discovers a missing job raises :class:`NotFoundError`
because *the job is missing* — deciding that this means "404" is the web layer's
job, and lives in ``core/errors.py``.

That separation is why the same use cases could be driven by a CLI, a scheduled
task, or a queue worker without change.

Each ``code`` matches the API contract in docs/API_SPECIFICATION.md §1.1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """One specific problem within a larger error.

    Attributes:
        field: Where the problem is, e.g. ``"urls[0]"``.
        issue: What is wrong, e.g. ``"not a valid URL"``.
    """

    field: str
    issue: str


class DomainError(Exception):
    """Base class for every expected, business-meaningful failure.

    "Expected" is the key word. A missing job or a duplicate email is a normal
    outcome we describe precisely. Anything *not* derived from this class is an
    unexpected bug, and is reported as a generic 500 without leaking internals.
    """

    code: ClassVar[str] = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: Sequence[ErrorDetail] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: tuple[ErrorDetail, ...] = tuple(details or ())


class ValidationFailedError(DomainError):
    """Input violated a business rule that validation at the edge cannot express."""

    code: ClassVar[str] = "VALIDATION_ERROR"


class UnauthenticatedError(DomainError):
    """No valid credentials were presented."""

    code: ClassVar[str] = "UNAUTHENTICATED"


class TokenExpiredError(DomainError):
    """The access token has expired; the client should refresh rather than re-login."""

    code: ClassVar[str] = "TOKEN_EXPIRED"


class ForbiddenError(DomainError):
    """Authenticated, but lacking the required role or ownership."""

    code: ClassVar[str] = "FORBIDDEN"


class NotFoundError(DomainError):
    """The resource does not exist, or is not visible to this caller.

    Deliberately conflated: telling a user that a resource exists but is
    someone else's leaks information. Both cases return 404.
    """

    code: ClassVar[str] = "NOT_FOUND"


class ConflictError(DomainError):
    """The request conflicts with existing state, e.g. a duplicate email."""

    code: ClassVar[str] = "CONFLICT"


class RateLimitedError(DomainError):
    """The caller has exceeded an allowed rate."""

    code: ClassVar[str] = "RATE_LIMITED"


class PayloadTooLargeError(DomainError):
    """A size or count limit was exceeded, e.g. too many URLs in one batch."""

    code: ClassVar[str] = "PAYLOAD_TOO_LARGE"


class UnprocessableSourceError(DomainError):
    """A submitted URL cannot be processed (unsupported, private, or unreachable)."""

    code: ClassVar[str] = "UNPROCESSABLE_SOURCE"
