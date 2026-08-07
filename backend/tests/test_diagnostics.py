"""System self-checks.

Note the last test: it performs a *real* local transcription and is skipped
automatically when the speech model has not been downloaded. That means it
stays green in CI and on a fresh clone, but genuinely proves the audio → text
chain on any machine that has run `python -m app.cli doctor --deep`.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.diagnostics import (
    SAMPLE_AUDIO,
    SAMPLE_EXPECTED_WORDS,
    check_jwt_secret,
    check_no_paid_api,
    check_python,
    check_work_dir,
    render,
    run_diagnostics,
)


def test_python_version_passes_on_a_supported_interpreter() -> None:
    assert check_python().ok


def test_missing_binary_is_reported_with_a_fix() -> None:
    from app.diagnostics import check_binary

    result = check_binary("definitely-not-a-real-binary", "Fake tool")
    assert not result.ok
    assert result.fix and "ffmpeg" in result.fix


def test_work_dir_check_passes_when_writable(settings) -> None:
    assert check_work_dir(settings).ok


def test_default_secret_is_a_warning_in_development_and_a_failure_otherwise() -> None:
    development = check_jwt_secret(
        Settings(environment="development", jwt_secret="change-me-in-production")
    )
    assert not development.ok
    assert development.warning_only  # does not block local work

    production = check_jwt_secret(
        Settings(environment="production", jwt_secret="change-me-in-production")
    )
    assert not production.ok
    assert not production.warning_only  # must be fixed


def test_a_long_secret_passes() -> None:
    result = check_jwt_secret(
        Settings(environment="production", jwt_secret="x" * 48)
    )
    assert result.ok


def test_the_default_keeps_audio_on_this_machine() -> None:
    """Version 1's promise, stated back to whoever reads the report."""
    result = check_no_paid_api(Settings(transcription_provider="faster_whisper"))
    assert result.ok
    assert not result.warning_only
    assert "faster_whisper" in result.detail
    assert "on this machine" in result.detail


def test_using_a_hosted_service_is_allowed_but_declared() -> None:
    """A hosted provider is a legitimate choice and not a failure. It is also
    audio leaving the building, which the person reading this is entitled to
    know without reading the configuration file."""
    result = check_no_paid_api(Settings(transcription_provider="sarvam"))
    assert result.ok            # not an error
    assert result.warning_only  # but not silent either
    assert "uploaded" in result.detail
    assert "faster_whisper" in (result.fix or "")


def test_the_speech_sample_ships_inside_the_app_package() -> None:
    """Must live in app/assets/, not tests/ — the Docker image excludes tests."""
    assert SAMPLE_AUDIO.exists(), f"missing sample clip: {SAMPLE_AUDIO}"
    assert SAMPLE_AUDIO.stat().st_size > 1000
    assert SAMPLE_AUDIO.parent.name == "assets"
    assert SAMPLE_AUDIO.parent.parent.name == "app"


async def test_full_report_runs_and_renders(settings, database) -> None:
    report = await run_diagnostics(settings, deep=False)
    names = {result.name for result in report.results}
    assert {"Python version", "Database", "Speech-to-text", "Where audio is processed"} <= names

    output = render(report)
    assert "Content Research Hub — system check" in output
    # Every check must appear in the rendered output, or the report lies.
    for result in report.results:
        assert result.name in output


def _model_is_available() -> bool:
    """True when faster-whisper can load its model without a download."""
    try:
        from app.services.transcription import get_transcription_provider

        provider = get_transcription_provider(Settings(transcription_provider="faster_whisper"))
        provider.validate_configuration()
        from app.services.transcription.faster_whisper import _load_model

        _load_model("base", "auto", "default")
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _model_is_available(),
    reason="speech model not downloaded — run: python -m app.cli doctor --deep",
)
async def test_real_local_transcription_produces_the_right_words() -> None:
    """The genuine article: real model, real audio, real words out.

    Skipped where the model is absent, so this never blocks a fresh clone — but
    it is the test that proves free local transcription actually works.
    """
    from app.services.transcription import get_transcription_provider

    provider = get_transcription_provider(Settings(transcription_provider="faster_whisper"))
    result = await provider.transcribe(SAMPLE_AUDIO)

    heard = result.text.lower()
    matched = [word for word in SAMPLE_EXPECTED_WORDS if word in heard]
    assert len(matched) >= 3, f"expected most of {SAMPLE_EXPECTED_WORDS}, heard: {result.text!r}"
    assert result.segments, "timed segments are required for SRT/VTT export"
    assert result.segments[0].end > result.segments[0].start
