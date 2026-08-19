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
        "nocheckcertificate": True,
        "retries": 0,
        "extract_flat": True,
    }

    from app.services.proxy import get_random_proxy
    proxy = get_random_proxy()
    if proxy:
        options["proxy"] = proxy
    return options

def _extract_sync(url: str, settings: Settings) -> dict[str, Any]:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise MetadataError("yt-dlp is not installed on the server.") from exc

    import tempfile
    import os
    
    cookie_path = None
    info = None
    last_exc = None
    
    try:
        options = _ydl_options(settings)
        if settings.youtube_cookies_text:
            fd, cookie_path = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w") as f:
                f.write(settings.youtube_cookies_text)
            options["cookiefile"] = cookie_path

        # YouTube aggressively blocks Datacenter IPs. Since our proxy is rotating,
        # if we hit a bot challenge, we can just retry, which automatically grabs
        # a new IP from the Webshare load balancer until we find a clean one!
        for attempt in range(5):
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=False)
                break  # Success!
            except Exception as exc:
                last_exc = exc
                lowered = str(exc).lower()
                if any(phrase in lowered for phrase in _LOGIN_REQUIRED) and attempt < 4:
                    logger.info(f"Proxy IP blocked by YouTube bot-check. Automatically rotating IP (attempt {attempt + 1}/5)...")
                    # If we need to rotate, we must regenerate options to get a new proxy!
                    options = _ydl_options(settings)
                    if cookie_path:
                        options["cookiefile"] = cookie_path
                    continue  # Retry with a new rotating proxy IP
                
                # If it's a permanent error or we ran out of retries, throw it.
                if attempt == 4:
                    pass # Handled below
                else:
                    _classify_and_raise(url, str(exc))

        if info is None:
            if last_exc:
                message = str(last_exc).lower()
                if any(phrase in message for phrase in _LOGIN_REQUIRED):
                    logger.warning("All proxy attempts blocked by YouTube. Falling back to direct connection (NO PROXY)...")
                    try:
                        fallback_opts = _ydl_options(settings)
                        if "proxy" in fallback_opts:
                            del fallback_opts["proxy"]
                        if cookie_path:
                            fallback_opts["cookiefile"] = cookie_path
                        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                    except Exception as fallback_exc:
                        _classify_and_raise(url, str(fallback_exc))
                else:
                    _classify_and_raise(url, str(last_exc))
            
            if info is None:
                raise MetadataError("The platform returned no metadata for this URL.", details={"url": url})

        # A playlist slipped through despite noplaylist — take the first entry.
        if info.get("_type") == "playlist":
            entries = [e for e in (info.get("entries") or []) if e]
            if not entries:
                raise VideoUnavailableError("That link contains no playable video.")
            info = entries[0]

        return info
    finally:
        if cookie_path and os.path.exists(cookie_path):
            try:
                os.remove(cookie_path)
            except OSError:
                pass


async def fetch_metadata(parsed: ParsedURL, settings: Settings | None = None) -> VideoMetadata:
    """Probe a video without downloading it.

    Runs the (blocking, network-bound) yt-dlp call in a worker thread so the
    event loop keeps serving requests. Wrapped in a timeout so it cannot hang
    indefinitely if the proxy or platform tarpits the connection.
    """
    import asyncio
    settings = settings or get_settings()
    
    try:
        info = await asyncio.wait_for(
            anyio.to_thread.run_sync(_extract_sync, parsed.canonical_url, settings),
            timeout=45.0
        )
    except asyncio.TimeoutError:
        raise MetadataError(
            "Connection timed out while checking the video. The platform or proxy is unresponsive. Please try again.",
            details={"url": parsed.canonical_url}
        )


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
