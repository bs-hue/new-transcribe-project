"""Domain errors.

Every error carries a stable machine-readable ``code`` so the UI can react to a
specific failure without string-matching a message, and a ``retryable`` flag the
worker uses to decide whether a second attempt could possibly help.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all expected, user-explainable failures."""

    code: str = "internal_error"
    status_code: int = 500
    retryable: bool = False

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        payload: dict = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class UnsupportedURLError(AppError):
    """The URL is not a recognised video on a supported platform."""

    code = "unsupported_url"
    status_code = 422


class InvalidURLError(AppError):
    """The string is not a usable URL at all."""

    code = "invalid_url"
    status_code = 422


class MetadataError(AppError):
    """The platform metadata could not be read."""

    code = "metadata_failed"
    status_code = 502
    retryable = True


class VideoUnavailableError(AppError):
    """The video is private, removed, or region-locked. Retrying will not help."""

    code = "video_unavailable"
    status_code = 404
    retryable = False


class LimitExceededError(AppError):
    """The video is outside configured system limits."""

    code = "limit_exceeded"
    status_code = 413
    retryable = False


class DownloadError(AppError):
    code = "download_failed"
    status_code = 502
    retryable = True


class AudioExtractionError(AppError):
    code = "audio_extraction_failed"
    status_code = 500
    retryable = False


class TranscriptionError(AppError):
    code = "transcription_failed"
    status_code = 502
    retryable = True


class ConfigurationError(AppError):
    """The server is misconfigured — an operator has to fix it, not a retry."""

    code = "configuration_error"
    status_code = 500
    retryable = False


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ExportFormatError(AppError):
    code = "unsupported_export_format"
    status_code = 422


class AuthError(AppError):
    """Not signed in, or the credentials are wrong."""

    code = "unauthorized"
    status_code = 401


class ForbiddenError(AppError):
    """Signed in, but not allowed to do this."""

    code = "forbidden"
    status_code = 403
