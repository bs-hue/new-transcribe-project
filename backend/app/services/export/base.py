"""Export contract.

Exporters render an ``ExportDocument`` — a plain dataclass, not an ORM object —
so a format can be written and tested without a database, and so changing the
schema does not ripple into seven renderers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ExportSegment:
    index: int
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(slots=True)
class ExportDocument:
    """Everything any format needs about one transcript."""

    transcript_id: str
    video_id: str
    title: str
    platform: str
    source_url: str
    text: str
    segments: list[ExportSegment] = field(default_factory=list)
    author: str | None = None
    duration_seconds: float | None = None
    language: str | None = None
    provider: str | None = None
    model: str | None = None
    word_count: int = 0
    published_at: datetime | None = None
    created_at: datetime | None = None

    @property
    def safe_title(self) -> str:
        return self.title or "Untitled"


class Exporter(ABC):
    """Renders an ``ExportDocument`` to bytes."""

    format: str
    extension: str
    content_type: str
    display_name: str
    #: Formats that need timestamps are hidden when a transcript has no segments.
    requires_segments: bool = False
    #: Whether ``render_many`` returns a single file. Advertised so the UI can
    #: offer "one file" only where one exists, instead of hardcoding the list.
    combinable: bool = False

    @abstractmethod
    def render(self, document: ExportDocument) -> bytes: ...

    def render_many(self, documents: list[ExportDocument]) -> bytes | None:
        """Render several transcripts into one file.

        ``None`` means "this format has no sensible combined form", and the
        caller falls back to a ZIP of individual files. Subtitle formats (SRT,
        VTT) keep that default: their timestamps all start from zero, so a
        concatenation would be a file no player could use.
        """
        return None

    def filename(self, document: ExportDocument) -> str:
        from app.core.text import slugify_filename

        return f"{slugify_filename(document.safe_title)}.{self.extension}"
