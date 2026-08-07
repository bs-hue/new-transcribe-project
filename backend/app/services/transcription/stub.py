"""Deterministic fake provider.

Exists so the whole pipeline, API and UI can be exercised without API keys,
network, or a GPU. Never selected unless explicitly configured.
"""

from __future__ import annotations

from pathlib import Path

from app.services.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegmentData,
)

_SENTENCES = (
    "This is placeholder transcript text produced by the stub provider.",
    "Configure a real TRANSCRIPTION_PROVIDER to generate accurate transcripts.",
    "Each stub segment is five seconds long so timed exports stay valid.",
)


class StubProvider(TranscriptionProvider):
    name = "stub"
    max_audio_bytes = None

    @property
    def model_name(self) -> str | None:
        return "stub-v1"

    async def transcribe(
        self, audio_path: Path, *, language: str | None = None
    ) -> TranscriptionResult:
        segments = [
            TranscriptSegmentData(
                index=index,
                start=float(index * 5),
                end=float((index + 1) * 5),
                text=sentence,
            )
            for index, sentence in enumerate(_SENTENCES)
        ]
        return TranscriptionResult(
            text=" ".join(_SENTENCES),
            segments=segments,
            language=language or "en",
            provider=self.name,
            model="stub-v1",
            duration_seconds=float(len(_SENTENCES) * 5),
        )
