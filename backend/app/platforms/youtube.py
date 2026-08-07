"""YouTube URL recognition — watch pages, short links, Shorts, embeds, live."""

from __future__ import annotations

import re

from app.platforms.base import PlatformAdapter

_ID = r"(?P<id>[A-Za-z0-9_-]{11})"


class YouTubeAdapter(PlatformAdapter):
    name = "youtube"
    display_name = "YouTube"
    patterns = (
        # https://www.youtube.com/watch?v=ID  (also &t=, /watch?foo=bar&v=ID)
        re.compile(rf"(?:youtube\.com|youtube-nocookie\.com)/watch\?(?:[^&\s]*&)*v={_ID}"),
        # https://youtu.be/ID
        re.compile(rf"youtu\.be/{_ID}"),
        # https://www.youtube.com/shorts/ID
        re.compile(rf"youtube\.com/shorts/{_ID}"),
        # https://www.youtube.com/embed/ID  and  /v/ID
        re.compile(rf"(?:youtube\.com|youtube-nocookie\.com)/(?:embed|v)/{_ID}"),
        # https://www.youtube.com/live/ID
        re.compile(rf"youtube\.com/live/{_ID}"),
    )

    def canonical_url(self, video_id: str) -> str:
        return f"https://www.youtube.com/watch?v={video_id}"
