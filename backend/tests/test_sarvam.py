"""Sarvam AI provider.

The network is mocked: these prove the request we send and how we read the
reply, which is what breaks. Whether Saarika transcribes Hindi well is Sarvam's
problem, not something a test here can or should assert.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.core.errors import ConfigurationError, TranscriptionError
from app.services.transcription import LOCAL_PROVIDERS, available_providers
from app.services.transcription.sarvam import BYTES_PER_SECOND, SarvamProvider


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    path = tmp_path / "clip.wav"
    path.write_bytes(b"RIFF" + b"\0" * 64)
    return path


def _settings(**overrides) -> Settings:
    return Settings(
        transcription_provider="sarvam", sarvam_api_key="test-key", **overrides
    )


def _mock(monkeypatch, handler) -> dict:
    """Route every request through `handler`, and record what was sent."""
    captured: dict = {}

    class FakeClient:
        def __init__(self, *_, **__) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_) -> None:
            return None

        async def post(self, url, headers=None, data=None, files=None):  # noqa: ANN001
            captured.update(url=url, headers=headers, data=data, files=files)
            return handler()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    return captured


def _response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.sarvam.ai/speech-to-text"),
    )


# --- the request -------------------------------------------------------------


async def test_hindi_is_sent_as_the_locale_sarvam_expects(monkeypatch, audio) -> None:
    """The app stores "hi"; Sarvam wants "hi-IN". Sending the wrong one is how
    a language setting silently does nothing — the lesson from Whisper."""
    captured = _mock(monkeypatch, lambda: _response({"transcript": "नमस्ते"}))

    await SarvamProvider(_settings()).transcribe(audio, language="hi")

    assert captured["data"]["language_code"] == "hi-IN"
    assert captured["headers"]["api-subscription-key"] == "test-key"


async def test_no_language_asks_sarvam_to_detect(monkeypatch, audio) -> None:
    captured = _mock(monkeypatch, lambda: _response({"transcript": "ok"}))

    await SarvamProvider(_settings()).transcribe(audio, language=None)

    assert captured["data"]["language_code"] == "unknown"


async def test_a_language_sarvam_cannot_do_falls_back_to_detection(
    monkeypatch, audio
) -> None:
    """Saarika has no Urdu. Detecting is a worse answer than Urdu and a much
    better one than failing the job."""
    captured = _mock(monkeypatch, lambda: _response({"transcript": "ok"}))

    await SarvamProvider(_settings()).transcribe(audio, language="ur")

    assert captured["data"]["language_code"] == "unknown"


# --- the reply ---------------------------------------------------------------


async def test_word_timings_become_segments(monkeypatch, audio) -> None:
    _mock(
        monkeypatch,
        lambda: _response(
            {
                "transcript": "ये ब्रेसलेट है",
                "language_code": "hi-IN",
                "timestamps": {
                    "words": ["ये", "ब्रेसलेट", "है"],
                    "start_time_seconds": [0.0, 0.5, 1.2],
                    "end_time_seconds": [0.5, 1.2, 1.6],
                },
            }
        ),
    )

    result = await SarvamProvider(_settings()).transcribe(audio, language="hi")

    assert result.text == "ये ब्रेसलेट है"
    assert result.language == "hi"  # stored as the code the rest of the app uses
    assert [segment.text for segment in result.segments] == ["ये", "ब्रेसलेट", "है"]
    assert result.segments[1].start == 0.5


async def test_a_transcript_without_timings_is_still_a_transcript(
    monkeypatch, audio
) -> None:
    """SRT and VTT need timings, but text, Word and Excel do not. Losing the
    whole transcript because the timings are missing would be the wrong trade."""
    _mock(monkeypatch, lambda: _response({"transcript": "hello", "language_code": "en-IN"}))

    result = await SarvamProvider(_settings()).transcribe(audio)

    assert result.text == "hello"
    assert len(result.segments) == 1


# --- when it goes wrong ------------------------------------------------------


async def test_a_missing_key_is_caught_before_any_upload(audio) -> None:
    provider = SarvamProvider(Settings(transcription_provider="sarvam", sarvam_api_key=None))
    with pytest.raises(ConfigurationError) as caught:
        await provider.transcribe(audio)
    # The message has to name the way out, not just the problem.
    assert "faster_whisper" in str(caught.value)


async def test_a_rejected_key_says_so_plainly(monkeypatch, audio) -> None:
    _mock(monkeypatch, lambda: _response({"error": "unauthorized"}, status=401))

    with pytest.raises(ConfigurationError) as caught:
        await SarvamProvider(_settings()).transcribe(audio)
    assert "SARVAM_API_KEY" in str(caught.value)


async def test_a_rate_limit_is_retryable_not_fatal(monkeypatch, audio) -> None:
    """Free tiers run out mid-batch. That must be a job the queue retries, not
    a configuration error that stops everything."""
    _mock(monkeypatch, lambda: _response({"error": "too many"}, status=429))

    with pytest.raises(TranscriptionError) as caught:
        await SarvamProvider(_settings()).transcribe(audio)
    assert "rate limit" in str(caught.value).lower()


async def test_no_internet_points_back_at_the_local_engine(monkeypatch, audio) -> None:
    def explode():
        raise httpx.ConnectError("no route to host")

    _mock(monkeypatch, explode)

    with pytest.raises(TranscriptionError) as caught:
        await SarvamProvider(_settings()).transcribe(audio)
    assert "faster_whisper" in str(caught.value)


# --- how it fits the rest ----------------------------------------------------


def test_long_audio_is_split_into_requests_sarvam_will_accept() -> None:
    """Sarvam takes short clips. The pipeline already splits and stitches, and
    only needs the limit expressed in the bytes it measures."""
    provider = SarvamProvider(_settings(sarvam_max_audio_seconds=30))
    assert provider.max_audio_bytes == 30 * BYTES_PER_SECOND


def test_sarvam_is_available_but_is_not_a_local_provider() -> None:
    """It is a real choice, and it is not one that keeps audio in the building.
    The system check reads this to tell an administrator which they are on."""
    assert "sarvam" in available_providers()
    assert "sarvam" not in LOCAL_PROVIDERS
    assert Settings().transcription_provider in LOCAL_PROVIDERS
