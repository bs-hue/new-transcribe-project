"""Small text helpers shared by exports and the pipeline."""

from __future__ import annotations

import re
import unicodedata

_UNSAFE_FILENAME_CHARS = re.compile(r"[^\w\s.-]", re.UNICODE)
_WHITESPACE_RUN = re.compile(r"[\s_]+")


def slugify_filename(value: str, *, fallback: str = "transcript", max_length: int = 80) -> str:
    """Turn an arbitrary video title into a safe download filename stem.

    User-controlled text ends up in a ``Content-Disposition`` header and inside
    ZIP archives, so path separators, control characters and traversal sequences
    must not survive this function.
    """
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    cleaned = _UNSAFE_FILENAME_CHARS.sub("", ascii_only)
    cleaned = _WHITESPACE_RUN.sub("_", cleaned).strip("._-")
    cleaned = cleaned[:max_length].strip("._-")
    return cleaned or fallback


def format_timestamp(seconds: float, *, separator: str = ",") -> str:
    """Format seconds as ``HH:MM:SS,mmm`` (SRT) or ``HH:MM:SS.mmm`` (VTT)."""
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def format_duration(seconds: float | None) -> str:
    """Human-readable duration, e.g. ``1:04:09`` or ``0:47``."""
    if seconds is None:
        return "unknown"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def word_count(text: str) -> int:
    return len(text.split())
