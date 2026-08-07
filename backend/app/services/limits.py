"""System limit checks.

Pure functions: metadata + settings in, a verdict out. No I/O, so this is
trivially testable and can be called from the preview endpoint (to warn) and
from the pipeline (to reject) with identical results.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.core.errors import LimitExceededError
from app.core.text import format_duration
from app.services.metadata import VideoMetadata


@dataclass(frozen=True, slots=True)
class LimitVerdict:
    allowed: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def reason(self) -> str | None:
        return " ".join(self.reasons) if self.reasons else None


def _human_bytes(size: float | None) -> str:
    if not size:
        return "unknown size"
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"  # pragma: no cover


def check_limits(metadata: VideoMetadata, settings: Settings | None = None) -> LimitVerdict:
    """Decide whether a video may be processed.

    Size is treated as a *warning* rather than a hard block when the platform
    only gave us an estimate — refusing a video because of an approximation we
    computed from a bitrate would be worse than trying and failing honestly.
    Duration, which platforms report exactly, is a hard limit.
    """
    settings = settings or get_settings()
    reasons: list[str] = []
    warnings: list[str] = []

    if metadata.is_live:
        reasons.append("Live streams cannot be transcribed. Wait until the stream has ended.")

    duration = metadata.duration_seconds
    max_duration = settings.max_video_duration_seconds
    if duration is not None and duration > max_duration:
        reasons.append(
            f"Video is {format_duration(duration)}, which exceeds the "
            f"{format_duration(max_duration)} limit."
        )
    elif duration is None:
        warnings.append("Duration is unknown; this video may exceed system limits.")

    size = metadata.estimated_size_bytes
    max_size = settings.max_video_filesize_bytes
    if size is not None and size > max_size:
        reasons.append(
            f"Estimated download is {_human_bytes(size)}, which exceeds the "
            f"{_human_bytes(max_size)} limit."
        )
    elif size is not None and size > max_size * 0.8:
        warnings.append(f"Estimated download is {_human_bytes(size)} — close to the limit.")
    elif size is None:
        warnings.append("Download size could not be estimated before downloading.")

    return LimitVerdict(allowed=not reasons, reasons=tuple(reasons), warnings=tuple(warnings))


def enforce_limits(metadata: VideoMetadata, settings: Settings | None = None) -> None:
    """Raise if the video may not be processed."""
    verdict = check_limits(metadata, settings)
    if not verdict.allowed:
        raise LimitExceededError(
            verdict.reason or "Video exceeds system limits.",
            details={"reasons": list(verdict.reasons)},
        )
