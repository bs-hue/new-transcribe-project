"""Local transcription via faster-whisper — the Version 1 default.

Free, open source (MIT), and entirely local: no API key, no per-minute cost, and
no client research leaving the building. No size cap either, since it streams
from disk rather than uploading.

The trade-off is hardware: transcription speed depends on the machine, and the
model is downloaded once on first use (~150 MB for ``base``).
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import anyio

from app.config import Settings, get_settings
from app.core.errors import ConfigurationError, TranscriptionError
from app.services.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegmentData,
)

logger = logging.getLogger(__name__)


def resolve_device(requested: str) -> str:
    """Turn ``auto`` into the device actually present."""
    if requested != "auto":
        return requested
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:  # noqa: BLE001 — any failure here just means "no GPU"
        pass
    return "cpu"


def resolve_compute_type(requested: str, device: str) -> str:
    """Turn ``default`` into the fastest type that device handles well.

    faster-whisper's own ``default`` is float32 on CPU. That is the slowest
    option available and buys accuracy nobody can hear: int8 runs two to four
    times faster on the same machine. On a GPU, float16 is the equivalent
    choice. An explicit setting is always respected.
    """
    if requested != "default":
        return requested
    return "float16" if device == "cuda" else "int8"


def resolve_cpu_threads(requested: int, concurrency: int) -> int:
    """How many CPU cores one transcription may use.

    Whisper will happily take every core. With two workers running, both take
    every core, and they spend their time fighting each other rather than
    transcribing — total throughput goes *down*. Splitting the machine between
    them is slower per video and faster per batch, which is what bulk work
    needs.
    """
    if requested > 0:
        return requested
    cores = os.cpu_count() or 4
    return max(1, cores // max(1, concurrency))


@lru_cache(maxsize=2)
def _load_model(model_size: str, device: str, compute_type: str, cpu_threads: int) -> Any:
    """Load and cache the model.

    Model load is seconds-to-minutes and hundreds of MB of RAM; doing it per job
    would dominate runtime, so it is cached for the process lifetime and shared
    by every worker in it.
    """
    from faster_whisper import WhisperModel

    logger.info(
        "Loading faster-whisper model %s on %s (%s, %d thread(s))",
        model_size,
        device,
        compute_type,
        cpu_threads,
    )
    return WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads if device == "cpu" else 0,
    )


@lru_cache(maxsize=2)
def _batched(model: Any) -> Any:
    """Wrap a model so chunks of one video transcribe together.

    Sequentially, each 30-second window waits for the one before it. Batched,
    several are in flight at once and the CPU stops idling between them — two
    to four times faster for identical output. Cached alongside the model
    because building it is not free either.
    """
    from faster_whisper import BatchedInferencePipeline

    return BatchedInferencePipeline(model=model)


class FasterWhisperProvider(TranscriptionProvider):
    name = "faster_whisper"
    max_audio_bytes = None  # reads from disk; no upload limit to respect

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def model_name(self) -> str | None:
        return self.settings.faster_whisper_model

    def validate_configuration(self) -> None:
        try:
            import faster_whisper  # noqa: F401
        except ImportError as exc:
            raise ConfigurationError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            ) from exc

    def _transcribe_sync(self, audio_path: Path, language: str | None) -> TranscriptionResult:
        device = resolve_device(self.settings.faster_whisper_device)
        model = _load_model(
            self.settings.faster_whisper_model,
            device,
            resolve_compute_type(self.settings.faster_whisper_compute_type, device),
            resolve_cpu_threads(
                self.settings.faster_whisper_cpu_threads, self.settings.worker_concurrency
            ),
        )
        started = time.monotonic()

        batch_size = max(1, self.settings.faster_whisper_batch_size)
        # Batching is a pure speed change, so it degrades to the sequential path
        # rather than failing a job if the installed library cannot do it.
        engine: Any = model
        extra: dict[str, Any] = {}
        if batch_size > 1:
            try:
                engine = _batched(model)
                extra["batch_size"] = batch_size
            except Exception as exc:  # noqa: BLE001
                logger.warning("Batched transcription unavailable (%s); running one at a time", exc)

        segment_iter, info = engine.transcribe(
            str(audio_path),
            language=language,
            # VAD trims silence, which measurably improves accuracy on Reels
            # where the first second is often a musical sting.
            vad_filter=True,
            beam_size=self.settings.faster_whisper_beam_size,
            # Whisper normally feeds each segment its own previous output as
            # context. When it mishears once — far more likely outside English —
            # that error becomes the context for the next segment, and it can
            # lock into repeating the same phrase for minutes. Turning this off
            # costs a little coherence and removes the failure mode entirely.
            condition_on_previous_text=False,
            # A second, independent guard against the same loop.
            repetition_penalty=self.settings.faster_whisper_repetition_penalty,
            # Words the model would otherwise have to guess from sound alone.
            hotwords=(self.settings.transcription_vocabulary or None),
            # Only consulted when `language` is None. Listening to more of the
            # video before deciding is the difference between "this is Hindi"
            # and "the first thing I heard was a music sting, so, Indonesian".
            language_detection_segments=(
                self.settings.faster_whisper_language_detection_segments
            ),
            **extra,
        )

        segments: list[TranscriptSegmentData] = []
        for raw in segment_iter:
            text = (raw.text or "").strip()
            if not text:
                continue
            segments.append(
                TranscriptSegmentData(
                    index=len(segments),
                    start=float(raw.start),
                    end=float(raw.end),
                    text=text,
                )
            )

        # Logged so "is it fast enough?" has an answer from the machine itself
        # rather than from a stopwatch. Above 1x means faster than real time.
        audio_seconds = getattr(info, "duration", None)
        elapsed = time.monotonic() - started
        detected = getattr(info, "language", None)
        if language is None and detected:
            # Printed because a wrong guess here ruins the entire transcript,
            # and this line is the only place it is visible.
            logger.info(
                "Language was not set; detected %r with %.0f%% confidence",
                detected,
                100 * (getattr(info, "language_probability", 0.0) or 0.0),
            )
        if audio_seconds and elapsed > 0:
            logger.info(
                "Transcribed %.0fs of audio in %.0fs "
                "(%.1fx real time, model=%s, %s, batch=%d)",
                audio_seconds,
                elapsed,
                audio_seconds / elapsed,
                self.settings.faster_whisper_model,
                device,
                batch_size,
            )

        return TranscriptionResult(
            text=" ".join(segment.text for segment in segments).strip(),
            segments=segments,
            language=getattr(info, "language", None) or language,
            provider=self.name,
            model=self.settings.faster_whisper_model,
            duration_seconds=getattr(info, "duration", None),
        )

    async def transcribe(
        self, audio_path: Path, *, language: str | None = None
    ) -> TranscriptionResult:
        self.validate_configuration()
        try:
            return await anyio.to_thread.run_sync(self._transcribe_sync, audio_path, language)
        except ConfigurationError:
            raise
        except Exception as exc:
            raise TranscriptionError(f"Local transcription failed: {exc}") from exc
