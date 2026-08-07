"""Transcription via Sarvam AI's Saarika models.

Whisper is trained overwhelmingly on English; Hindi is a small fraction of its
data and code-switched Hinglish smaller still, which is why it needs the largest
model to produce a usable Indian-language transcript and why that model is too
slow on a machine without a GPU. Saarika is built for Indian languages, so the
work happens on someone else's hardware and finishes in seconds.

**This provider sends audio off the network.** That reverses Version 1's
promise that no research leaves the building, so it is opt-in: nothing happens
unless ``TRANSCRIPTION_PROVIDER=sarvam`` and a key are set. The local engine
stays installed and one setting switches back to it.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.errors import ConfigurationError, TranscriptionError
from app.services.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegmentData,
)

logger = logging.getLogger(__name__)

API_URL = "https://api.sarvam.ai/speech-to-text"

#: Sarvam names languages as locales; the rest of the app uses ISO codes.
#: Anything absent here is a language Saarika does not transcribe.
LANGUAGE_CODES: dict[str, str] = {
    "hi": "hi-IN",
    "en": "en-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "or": "od-IN",
    "pa": "pa-IN",
    "ta": "ta-IN",
    "te": "te-IN",
}

#: What to send when nobody has chosen a language, so Saarika detects it.
AUTO = "unknown"

#: The extracted audio is 16 kHz mono 16-bit PCM, so seconds convert to bytes
#: exactly. Used to turn a duration limit into the byte cap the pipeline splits
#: on — the pipeline knows nothing about audio formats and should not.
BYTES_PER_SECOND = 16_000 * 2


class SarvamProvider(TranscriptionProvider):
    name = "sarvam"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def model_name(self) -> str | None:
        return self.settings.sarvam_model

    @property
    def max_audio_bytes(self) -> int:
        """Long audio is split by the pipeline before it reaches here.

        Expressed as a duration in settings because that is how the limit is
        documented and how a person thinks about it; converted to bytes because
        that is what the pipeline measures.
        """
        return self.settings.sarvam_max_audio_seconds * BYTES_PER_SECOND

    def validate_configuration(self) -> None:
        if not self.settings.sarvam_api_key:
            raise ConfigurationError(
                "SARVAM_API_KEY is not set. Create a free key at sarvam.ai, put "
                "it in .env, and restart — or set TRANSCRIPTION_PROVIDER="
                "faster_whisper to keep transcribing on this machine instead."
            )

    def _language_for(self, language: str | None) -> str:
        if not language:
            return AUTO
        code = LANGUAGE_CODES.get(language.lower())
        if code is None:
            # Better to let Saarika detect than to fail: an unsupported choice
            # is usually a language it can still hear, just not one we mapped.
            logger.warning(
                "Sarvam does not take %r as a language; detecting instead", language
            )
            return AUTO
        return code

    @staticmethod
    def _segments(payload: dict[str, Any], text: str) -> list[TranscriptSegmentData]:
        """Timed segments if the response carries them, one block if not.

        Saarika returns word or segment timings depending on the model and the
        request. A transcript without timings is still worth having — the
        exports that need them simply have one long segment — so a missing
        field is not an error.
        """
        timestamps = payload.get("timestamps") or {}
        starts = timestamps.get("start_time_seconds") or []
        ends = timestamps.get("end_time_seconds") or []
        words = timestamps.get("words") or []

        if words and len(words) == len(starts) == len(ends):
            return [
                TranscriptSegmentData(
                    index=index, start=float(start), end=float(end), text=str(word)
                )
                for index, (word, start, end) in enumerate(zip(words, starts, ends, strict=True))
            ]

        if not text:
            return []
        return [TranscriptSegmentData(index=0, start=0.0, end=0.0, text=text)]

    async def transcribe(
        self, audio_path: Path, *, language: str | None = None
    ) -> TranscriptionResult:
        self.validate_configuration()

        started = time.monotonic()
        data = {
            "model": self.settings.sarvam_model,
            "language_code": self._language_for(language),
        }

        try:
            with audio_path.open("rb") as handle:
                async with httpx.AsyncClient(
                    timeout=self.settings.sarvam_timeout_seconds
                ) as client:
                    response = await client.post(
                        API_URL,
                        headers={"api-subscription-key": self.settings.sarvam_api_key},
                        data=data,
                        files={"file": (audio_path.name, handle, "audio/wav")},
                    )
        except httpx.HTTPError as exc:
            raise TranscriptionError(
                "Could not reach Sarvam. Check the internet connection, or switch "
                "TRANSCRIPTION_PROVIDER to faster_whisper to transcribe locally."
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise ConfigurationError(
                "Sarvam rejected the API key. Check SARVAM_API_KEY in .env."
            )
        if response.status_code == 429:
            raise TranscriptionError(
                "Sarvam's rate limit was reached. This job will be retried; if it "
                "keeps happening, slow the batch down or switch to local "
                "transcription."
            )
        if response.status_code >= 400:
            raise TranscriptionError(
                f"Sarvam refused the audio ({response.status_code}): "
                f"{response.text[:200]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise TranscriptionError("Sarvam returned something that is not JSON.") from exc

        text = (payload.get("transcript") or "").strip()
        detected = payload.get("language_code") or ""
        # Back to the two-letter code the rest of the app stores.
        iso = detected.split("-")[0] or None

        elapsed = time.monotonic() - started
        logger.info(
            "Sarvam transcribed %s in %.1fs (%d characters, language=%s, model=%s)",
            audio_path.name,
            elapsed,
            len(text),
            iso or "unknown",
            self.settings.sarvam_model,
        )

        return TranscriptionResult(
            text=text,
            segments=self._segments(payload, text),
            language=iso,
            provider=self.name,
            model=self.settings.sarvam_model,
        )
