"""Instagram URL recognition — Reels, video posts, and IGTV.

Note for operators: Instagram increasingly requires an authenticated session for
public content. Set ``COOKIES_FILE`` to a Netscape-format cookie export from a
logged-in browser profile (see ``docs/COOKIES.md``). Without it, downloads fail
with a login-required error, which the pipeline surfaces verbatim.
"""

from __future__ import annotations

import re

from app.platforms.base import PlatformAdapter

# Instagram shortcodes are base64url-ish, historically 11 chars but not
# guaranteed, so accept a sane range rather than a fixed width.
_ID = r"(?P<id>[A-Za-z0-9_-]{5,32})"


class InstagramAdapter(PlatformAdapter):
    name = "instagram"
    display_name = "Instagram"
    patterns = (
        # /reel/CODE, /reels/CODE, /p/CODE, /tv/CODE — with or without a
        # leading /username/ segment.
        re.compile(rf"instagram\.com/(?:[A-Za-z0-9_.]+/)?reels?/{_ID}"),
        re.compile(rf"instagram\.com/(?:[A-Za-z0-9_.]+/)?p/{_ID}"),
        re.compile(rf"instagram\.com/(?:[A-Za-z0-9_.]+/)?tv/{_ID}"),
    )

    def canonical_url(self, video_id: str) -> str:
        # /reel/ resolves for every video post type, including /p/ and /tv/.
        return f"https://www.instagram.com/reel/{video_id}/"
