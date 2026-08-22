"""Platform registry.

Adding a platform is: write an adapter, add it to ``_ADAPTERS``. URL validation,
preview, download, and the UI's platform filter all pick it up from here.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from app.core.errors import InvalidURLError, UnsupportedURLError
from app.platforms.base import ParsedURL, PlatformAdapter
from app.platforms.facebook import FacebookAdapter
from app.platforms.instagram import InstagramAdapter
from app.platforms.youtube import YouTubeAdapter

_ADAPTERS: tuple[PlatformAdapter, ...] = (
    YouTubeAdapter(),
    InstagramAdapter(),
    FacebookAdapter(),
)

_ALLOWED_SCHEMES = {"http", "https"}


def supported_platforms() -> list[dict[str, str]]:
    return [{"name": a.name, "display_name": a.display_name} for a in _ADAPTERS]


def _normalise(raw_url: str) -> str:
    """Trim, add a scheme if the user pasted a bare domain, and validate shape.

    Rejecting anything that is not http(s) here is the first line of SSRF
    defence: ``file://``, ``gopher://`` and friends never reach a fetcher.
    """
    url = (raw_url or "").strip()
    if not url:
        raise InvalidURLError("URL is empty.")

    if "://" not in url:
        url = f"https://{url}"

    try:
        parts = urlparse(url)
    except ValueError as exc:
        raise InvalidURLError(f"Not a valid URL: {raw_url!r}") from exc

    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise InvalidURLError(f"Only http and https URLs are supported (got {parts.scheme!r}).")
    if not parts.netloc:
        raise InvalidURLError(f"Not a valid URL: {raw_url!r}")

    # Strip fragments; they never identify a different video.
    return urlunparse(parts._replace(fragment=""))


def parse_url(raw_url: str) -> ParsedURL:
    """Recognise a URL, or explain precisely why we cannot accept it.

    Raises:
        InvalidURLError: the string is not a usable http(s) URL.
        UnsupportedURLError: it is a URL, but not a video we support.
    """
    url = _normalise(raw_url)

    for adapter in _ADAPTERS:
        parsed = adapter.parse(url)
        if parsed is not None:
            return ParsedURL(
                platform=parsed.platform,
                platform_display_name=parsed.platform_display_name,
                video_id=parsed.video_id,
                canonical_url=parsed.canonical_url,
                original_url=raw_url.strip(),
            )

    # A recognised host with an unrecognised path deserves a better message than
    # a generic rejection — it is almost always a channel or profile link.
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for adapter in _ADAPTERS:
        if adapter.name in host:
            raise UnsupportedURLError(
                f"That looks like a {adapter.display_name} link, but not a single video. "
                "Paste a link to one video or reel.",
                details={"platform": adapter.name},
            )

    names = ", ".join(a.display_name for a in _ADAPTERS)
    raise UnsupportedURLError(
        f"Unsupported URL. Supported platforms: {names}.",
        details={"supported": [a.name for a in _ADAPTERS]},
    )


__all__ = ["ParsedURL", "PlatformAdapter", "parse_url", "supported_platforms"]
