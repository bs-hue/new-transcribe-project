"""System limit checks — step 4 of the workflow."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.errors import LimitExceededError
from app.services.limits import check_limits, enforce_limits
from app.services.metadata import VideoMetadata


def _metadata(**overrides) -> VideoMetadata:
    base = {
        "platform": "youtube",
        "platform_video_id": "abc",
        "canonical_url": "https://www.youtube.com/watch?v=abc",
        "source_url": "https://youtu.be/abc",
        "duration_seconds": 120.0,
        "estimated_size_bytes": 10 * 1024 * 1024,
    }
    return VideoMetadata(**{**base, **overrides})


@pytest.fixture
def limits() -> Settings:
    return Settings(
        max_video_duration_seconds=600,
        max_video_filesize_bytes=100 * 1024 * 1024,
    )


def test_normal_video_is_allowed(limits: Settings) -> None:
    verdict = check_limits(_metadata(), limits)
    assert verdict.allowed
    assert not verdict.reasons


def test_long_video_is_rejected(limits: Settings) -> None:
    verdict = check_limits(_metadata(duration_seconds=1200.0), limits)
    assert not verdict.allowed
    assert "exceeds" in verdict.reason


def test_oversized_video_is_rejected(limits: Settings) -> None:
    verdict = check_limits(_metadata(estimated_size_bytes=500 * 1024 * 1024), limits)
    assert not verdict.allowed
    assert "MB" in verdict.reason or "GB" in verdict.reason


def test_live_stream_is_rejected(limits: Settings) -> None:
    verdict = check_limits(_metadata(is_live=True), limits)
    assert not verdict.allowed
    assert "Live streams" in verdict.reason


def test_near_limit_size_warns_but_allows(limits: Settings) -> None:
    verdict = check_limits(_metadata(estimated_size_bytes=95 * 1024 * 1024), limits)
    assert verdict.allowed
    assert verdict.warnings


def test_unknown_duration_warns_but_allows(limits: Settings) -> None:
    verdict = check_limits(_metadata(duration_seconds=None), limits)
    assert verdict.allowed
    assert any("Duration is unknown" in warning for warning in verdict.warnings)


def test_enforce_raises_with_all_reasons(limits: Settings) -> None:
    metadata = _metadata(duration_seconds=9999.0, estimated_size_bytes=999 * 1024 * 1024)
    with pytest.raises(LimitExceededError) as exc:
        enforce_limits(metadata, limits)
    assert len(exc.value.details["reasons"]) == 2
    assert exc.value.retryable is False
