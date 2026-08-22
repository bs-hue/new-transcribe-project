"""Facebook and Meta Ads Library URL recognition.

Supports:
- Meta Ads Library links: https://www.facebook.com/ads/library/?id=...
- Meta Ads Archive links: https://www.facebook.com/ads/archive/render_ad/?id=...
- Facebook Videos: https://www.facebook.com/watch/?v=...
- Facebook Reels: https://www.facebook.com/reel/...
- Facebook Share links: https://www.facebook.com/share/v/...
- Shortlinks: https://fb.watch/...
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from app.platforms.base import ParsedURL, PlatformAdapter


class FacebookAdapter(PlatformAdapter):
    name = "facebook"
    display_name = "Meta / Facebook"

    patterns = (
        # Ads Library ID in query parameter: ?id=123456 or &id=123456
        re.compile(r"facebook\.com/ads/(?:library|archive/render_ad)/?.*?[?&]id=(?P<id>\d+)", re.IGNORECASE),
        # Watch / Reels / Videos / Shares
        re.compile(r"facebook\.com/(?:watch/?\?v=|reel/|share/v/|(?:[^/]+/videos/))(?P<id>[0-9A-Za-z_-]+)", re.IGNORECASE),
        re.compile(r"fb\.watch/(?P<id>[0-9A-Za-z_-]+)", re.IGNORECASE),
    )

    def extract_id(self, url: str) -> str | None:
        # First check query params directly for ads library
        if "ads/library" in url or "ads/archive" in url:
            try:
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                if "id" in qs and qs["id"]:
                    return qs["id"][0]
            except Exception:
                pass

        return super().extract_id(url)

    def canonical_url(self, video_id: str) -> str:
        # If it's a numeric ID typical of Ad Library or video post
        return f"https://www.facebook.com/ads/library/?id={video_id}"

    def parse(self, url: str) -> ParsedURL | None:
        video_id = self.extract_id(url)
        if not video_id:
            return None

        # Determine canonical URL format
        if "reel" in url:
            canonical = f"https://www.facebook.com/reel/{video_id}/"
        elif "watch" in url or "share" in url:
            canonical = f"https://www.facebook.com/watch/?v={video_id}"
        else:
            canonical = f"https://www.facebook.com/ads/library/?id={video_id}"

        return ParsedURL(
            platform=self.name,
            platform_display_name=self.display_name,
            video_id=video_id,
            canonical_url=canonical,
            original_url=url,
        )
