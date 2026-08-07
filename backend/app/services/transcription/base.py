"""Transcription provider contract.

A provider takes an audio file and returns text plus timed segments. That is the
entire interface — everything else (chunking, retries, storage) is the
pipeline's job, so a new provider is genuinely one small file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TranscriptSegmentData:
    index: int
    start: float
    end: float
    text: str
    speaker: str | None = None

    def shifted(self, offset: float, *, index: int) -> TranscriptSegmentData:
        """Move this segment onto the original timeline after chunked decoding."""
        return TranscriptSegmentData(
            index=index,
            start=self.start + offset,
            end=self.end + offset,
            text=self.text,
            speaker=self.speaker,
        )


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    segments: list[TranscriptSegmentData] = field(default_factory=list)
    language: str | None = None
    provider: str = ""
    model: str | None = None
    duration_seconds: float | None = None


class TranscriptionProvider(ABC):
    """Turns an audio file into a transcript."""

    name: str
    #: Largest audio file the provider accepts, in bytes. ``None`` means no cap,
    #: in which case the pipeline never splits the audio.
    max_audio_bytes: int | None = None

    @property
    def model_name(self) -> str | None:
        return None

    @abstractmethod
    async def transcribe(
        self, audio_path: Path, *, language: str | None = None
    ) -> TranscriptionResult:
        """Transcribe one audio file that is already within ``max_audio_bytes``."""

    def validate_configuration(self) -> None:
        """Raise ``ConfigurationError`` if this provider cannot run.

        Called at startup so misconfiguration surfaces immediately in the logs
        and on ``/api/health``, rather than after a user has waited through a
        download.
        """
        return None


def merge_results(
    results: list[tuple[TranscriptionResult, float]],
    *,
    provider: str,
    model: str | None,
) -> TranscriptionResult:
    """Stitch chunk results back into one transcript on the original timeline.

    ``results`` is ``(result, start_offset_seconds)`` in chunk order.
    """
    segments: list[TranscriptSegmentData] = []
    texts: list[str] = []
    language: str | None = None
    end = 0.0

    for result, offset in results:
        language = language or result.language
        for segment in result.segments:
            segments.append(segment.shifted(offset, index=len(segments)))
            end = max(end, segments[-1].end)
        chunk_text = result.text.strip()
        if chunk_text:
            texts.append(chunk_text)

    return TranscriptionResult(
        text=" ".join(texts).strip(),
        segments=segments,
        language=language,
        provider=provider,
        model=model,
        duration_seconds=end or None,
    )
