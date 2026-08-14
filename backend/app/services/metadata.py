"""Metadata probing — everything we can learn *before* downloading a byte.

This is what powers the preview step: the user sees title, thumbnail, duration
and estimated size, plus whether the video passes system limits, and can drop
items from a batch before any transfer starts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import anyio

from app.config import Settings, get_settings
from app.core.errors import MetadataError, VideoUnavailableError
from app.platforms import ParsedURL

logger = logging.getLogger(__name__)

# Phrases yt-dlp emits for content that will never become available. Retrying
# these wastes a worker slot and confuses the user with three identical errors.
_PERMANENT_FAILURES = (
    "video unavailable",
    "private video",
    "this video is private",
    "removed by the uploader",
    "account associated with this video has been terminated",
    "does not exist",
    "not found",
    "page not found",
    "sign in to confirm your age",
    "requested content is not available",
)

_LOGIN_REQUIRED = (
    "login required",
    "requires authentication",
    "rate-limit reached",
    "sign in to confirm",
    "use --cookies",
)


@dataclass(slots=True)
class VideoMetadata:
    """Normalised metadata, plus the untouched provider payload."""

    platform: str
    platform_video_id: str
    canonical_url: str
    source_url: str
    title: str | None = None
    description: str | None = None
    author: str | None = None
    author_url: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    estimated_size_bytes: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    published_at: datetime | None = None
    is_live: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


def _ydl_options(settings: Settings) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 30,
        "retries": 2,
        "extract_flat": True,
        "source_address": "0.0.0.0",
        "extractor_args": {"youtube": ["client=android,ios"]},
    }
    if settings.cookies_file:
        options["cookiefile"] = str(settings.cookies_file)
    return options


def _classify_and_raise(url: str, message: str) -> None:
    lowered = message.lower()
    if any(phrase in lowered for phrase in _PERMANENT_FAILURES):
        raise VideoUnavailableError(
            "This video is unavailable — it may be private, deleted, or region-locked.",
            details={"url": url, "provider_message": message},
        )
    if any(phrase in lowered for phrase in _LOGIN_REQUIRED):
        raise VideoUnavailableError(
            "This video requires an authenticated session. Configure COOKIES_FILE "
            "with a logged-in cookie export and try again.",
            details={"url": url, "provider_message": message},
        )
    raise MetadataError(
        f"Could not read video metadata: {message}",
        details={"url": url},
    )


def _estimate_size(info: dict[str, Any]) -> int | None:
    """Best available size estimate, in bytes.

    yt-dlp reports size in three descending qualities: an exact ``filesize``, an
    ``filesize_approx``, or nothing at all — in which case bitrate × duration is
    a good enough estimate to decide whether something busts a limit.
    """
    for key in ("filesize", "filesize_approx"):
        value = info.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)

    # Sum the selected video + audio streams when only per-format sizes exist.
    requested = info.get("requested_formats") or []
    if requested:
        total = 0
        for fmt in requested:
            size = fmt.get("filesize") or fmt.get("filesize_approx")
            if not size:
                total = 0
                break
            total += int(size)
        if total:
            return total

    duration = info.get("duration")
    total_bitrate = info.get("tbr")  # kbit/s
    if duration and total_bitrate:
        return int(float(duration) * float(total_bitrate) * 1000 / 8)

    # Largest per-format estimate is better than claiming we know nothing.
    sizes = [
        int(f["filesize"] or f.get("filesize_approx") or 0)
        for f in (info.get("formats") or [])
        if f.get("filesize") or f.get("filesize_approx")
    ]
    return max(sizes) if sizes else None


def _parse_upload_date(info: dict[str, Any]) -> datetime | None:
    timestamp = info.get("timestamp")
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=UTC)
    raw_date = info.get("upload_date")  # "YYYYMMDD"
    if isinstance(raw_date, str) and len(raw_date) == 8 and raw_date.isdigit():
        try:
            return datetime.strptime(raw_date, "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _best_thumbnail(info: dict[str, Any]) -> str | None:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbnails = info.get("thumbnails") or []
    if not thumbnails:
        return None
    # yt-dlp orders thumbnails worst-to-best; the last with a URL is the best.
    for thumb in reversed(thumbnails):
        if thumb.get("url"):
            return thumb["url"]
    return None


def _slim_raw(info: dict[str, Any]) -> dict[str, Any]:
    """Keep the fields worth persisting.

    The full yt-dlp payload includes every format variant and can be hundreds of
    kilobytes per video — too much to store per row. These are the fields V2/V3
    will plausibly mine (hashtags, engagement, categories).
    """
    keys = (
        "id", "title", "description", "duration", "view_count", "like_count",
        "comment_count", "repost_count", "channel", "channel_id", "channel_url",
        "channel_follower_count", "uploader", "uploader_id", "uploader_url",
        "upload_date", "timestamp", "categories", "tags", "webpage_url",
        "extractor_key", "language", "age_limit", "availability", "live_status",
        "width", "height", "fps", "resolution", "aspect_ratio",
    )
    return {key: info[key] for key in keys if key in info and info[key] is not None}


def _extract_sync(url: str, settings: Settings) -> dict[str, Any]:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise MetadataError("yt-dlp is not installed on the server.") from exc

    try:
        with yt_dlp.YoutubeDL(_ydl_options(settings)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        _classify_and_raise(url, str(exc))
        raise  # unreachable; keeps type checkers happy

    if info is None:
        raise MetadataError("The platform returned no metadata for this URL.", details={"url": url})

    # A playlist slipped through despite noplaylist — take the first entry.
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise VideoUnavailableError("That link contains no playable video.")
        info = entries[0]

    return info


async def fetch_metadata(parsed: ParsedURL, settings: Settings | None = None) -> VideoMetadata:
    """Probe a video without downloading it.

    Runs the (blocking, network-bound) yt-dlp call in a worker thread so the
    event loop keeps serving requests.
    """
    settings = settings or get_settings()
    info = await anyio.to_thread.run_sync(_extract_sync, parsed.canonical_url, settings)

    return VideoMetadata(
        platform=parsed.platform,
        platform_video_id=str(info.get("id") or parsed.video_id),
        canonical_url=info.get("webpage_url") or parsed.canonical_url,
        source_url=parsed.original_url,
        title=info.get("title") or info.get("fulltitle"),
        description=info.get("description"),
        author=info.get("uploader") or info.get("channel"),
        author_url=info.get("uploader_url") or info.get("channel_url"),
        thumbnail_url=_best_thumbnail(info),
        duration_seconds=float(info["duration"]) if info.get("duration") else None,
        estimated_size_bytes=_estimate_size(info),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        published_at=_parse_upload_date(info),
        is_live=bool(info.get("is_live")),
        raw=_slim_raw(info),
    )
