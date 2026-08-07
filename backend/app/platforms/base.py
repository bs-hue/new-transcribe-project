"""Platform adapter contract.

An adapter's only job is turning a pasted URL into a canonical, identified video
reference. Downloading is `yt-dlp`'s problem; adapters exist so that *validation*
is explicit — we accept URLs we recognise rather than handing arbitrary user
input to a downloader.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedURL:
    """A URL that has been recognised as a specific video on a platform."""

    platform: str
    platform_display_name: str
    video_id: str
    canonical_url: str
    original_url: str


class PlatformAdapter(ABC):
    """Recognises and canonicalises URLs for one platform."""

    name: str
    display_name: str
    #: Patterns whose first capture group is the platform video id.
    patterns: tuple[re.Pattern[str], ...] = ()

    def matches(self, url: str) -> bool:
        return any(pattern.search(url) for pattern in self.patterns)

    def extract_id(self, url: str) -> str | None:
        for pattern in self.patterns:
            match = pattern.search(url)
            if match:
                return match.group("id")
        return None

    @abstractmethod
    def canonical_url(self, video_id: str) -> str:
        """The single URL form we store and de-duplicate on."""

    def parse(self, url: str) -> ParsedURL | None:
        video_id = self.extract_id(url)
        if not video_id:
            return None
        return ParsedURL(
            platform=self.name,
            platform_display_name=self.display_name,
            video_id=video_id,
            canonical_url=self.canonical_url(video_id),
            original_url=url,
        )
