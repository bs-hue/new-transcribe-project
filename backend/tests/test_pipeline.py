"""End-to-end pipeline: submit → metadata → limits → download → audio →
transcribe → store, with the network and ffmpeg faked out."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.errors import LimitExceededError, VideoUnavailableError
from app.db.models import Job, JobStage, JobStatus, Transcript, TranscriptSegment, Video
from app.services import pipeline as pipeline_module
from app.services.ingest import submit_urls
from app.services.metadata import VideoMetadata
from app.services.pipeline import Pipeline
from app.workers.queue import cancel_job, claim_next_job, requeue_stale_jobs, retry_job

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _fake_metadata(**overrides) -> VideoMetadata:
    base = {
        "platform": "youtube",
        "platform_video_id": "dQw4w9WgXcQ",
        "canonical_url": URL,
        "source_url": URL,
        "title": "How to write a hook",
        "author": "Creator Name",
        "thumbnail_url": "https://img.example/thumb.jpg",
        "duration_seconds": 95.0,
        "estimated_size_bytes": 8 * 1024 * 1024,
        "raw": {"tags": ["marketing", "hooks"]},
    }
    return VideoMetadata(**{**base, **overrides})


@pytest.fixture
def patched_metadata(monkeypatch):
    """Replace the yt-dlp probe. Returns a mutable holder the test can adjust."""
    holder = {"metadata": _fake_metadata(), "error": None}

    async def fake_fetch(parsed, settings=None):  # noqa: ANN001
        if holder["error"]:
            raise holder["error"]
        return holder["metadata"]

    monkeypatch.setattr(pipeline_module, "fetch_metadata", fake_fetch)
    return holder


async def _submit(session, url: str = URL) -> str:
    result = await submit_urls(session, [url])
    assert result.accepted_count == 1
    return result.outcomes[0].job_id


async def test_happy_path_produces_a_stored_transcript(
    session, fake_media, patched_metadata, settings
) -> None:
    job_id = await _submit(session)

    await Pipeline(settings).run(job_id)

    await session.commit()  # see the worker's committed writes
    job = (await session.execute(select(Job).where(Job.id == job_id))).unique().scalar_one()
    assert job.status == JobStatus.COMPLETED.value
    assert job.stage == JobStage.DONE.value
    assert job.progress == 1.0
    assert job.error_message is None

    video = (await session.execute(select(Video))).scalar_one()
    assert video.title == "How to write a hook"
    assert video.author == "Creator Name"
    assert video.duration_seconds == 95.0
    assert video.raw_metadata["tags"] == ["marketing", "hooks"]

    transcript = (await session.execute(select(Transcript))).scalar_one()
    assert transcript.provider == "stub"
    assert transcript.word_count > 0
    assert transcript.job_id == job_id

    segments = (await session.execute(select(TranscriptSegment))).scalars().all()
    assert len(segments) == 3
    assert segments[0].start == 0.0
    assert [segment.index for segment in segments] == [0, 1, 2]

    assert fake_media.downloaded == [URL]


async def test_video_over_the_duration_limit_never_downloads(
    session, fake_media, patched_metadata, settings
) -> None:
    patched_metadata["metadata"] = _fake_metadata(duration_seconds=999_999.0)
    job_id = await _submit(session)

    with pytest.raises(LimitExceededError):
        await Pipeline(settings).run(job_id)

    await session.commit()
    job = (await session.execute(select(Job).where(Job.id == job_id))).unique().scalar_one()
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "limit_exceeded"
    # The point of checking limits before downloading.
    assert fake_media.downloaded == []


async def test_unavailable_video_fails_without_retrying(
    session, fake_media, patched_metadata, settings
) -> None:
    patched_metadata["error"] = VideoUnavailableError("This video is private.")
    job_id = await _submit(session)

    with pytest.raises(VideoUnavailableError):
        await Pipeline(settings).run(job_id)

    await session.commit()
    job = (await session.execute(select(Job).where(Job.id == job_id))).unique().scalar_one()
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "video_unavailable"


async def test_large_audio_is_chunked_and_stitched(
    session, fake_media, patched_metadata, settings, monkeypatch
) -> None:
    """Audio above a provider's cap is split, then merged back onto one timeline."""
    from app.services.transcription import get_transcription_provider

    provider = get_transcription_provider(settings)
    monkeypatch.setattr(type(provider), "max_audio_bytes", 512, raising=False)
    fake_media.audio_size = 4096  # comfortably over the cap

    job_id = await _submit(session)
    await Pipeline(settings, provider=provider).run(job_id)

    await session.commit()
    transcript = (await session.execute(select(Transcript))).scalar_one()
    segments = (
        (
            await session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.index)
            )
        )
        .scalars()
        .all()
    )
    # Two chunks x three stub segments, re-indexed and offset onto one timeline.
    assert len(segments) == 6
    assert [segment.index for segment in segments] == [0, 1, 2, 3, 4, 5]
    # The point of stitching: one rising timeline, not two restarting at zero.
    starts = [segment.start for segment in segments]
    assert starts == sorted(starts)
    assert segments[-1].start > segments[0].start


async def test_transcript_is_searchable_immediately(
    session, fake_media, patched_metadata, settings
) -> None:
    from app.services.search import get_search_backend

    job_id = await _submit(session)
    await Pipeline(settings).run(job_id)
    await session.commit()

    results = await get_search_backend(settings).search(session, "placeholder transcript")
    assert results.total == 1
    assert results.hits[0].snippet


async def test_duplicate_urls_reuse_one_video_row(session) -> None:
    first = await submit_urls(session, [URL])
    second = await submit_urls(session, ["https://youtu.be/dQw4w9WgXcQ"])

    assert second.outcomes[0].duplicate_of_existing_video is True
    assert second.outcomes[0].video_id == first.outcomes[0].video_id
    videos = (await session.execute(select(Video))).scalars().all()
    assert len(videos) == 1


async def test_mixed_batch_reports_per_url_verdicts(session) -> None:
    result = await submit_urls(
        session,
        [
            URL,
            "https://vimeo.com/12345",
            "https://www.instagram.com/reel/CxYz123abc/",
            "not-a-url",
            "https://youtu.be/dQw4w9WgXcQ",  # duplicate of the first
        ],
    )
    assert result.accepted_count == 2
    assert result.rejected_count == 3
    by_url = {outcome.url: outcome for outcome in result.outcomes}
    assert by_url["https://vimeo.com/12345"].error_code == "unsupported_url"
    assert by_url["https://youtu.be/dQw4w9WgXcQ"].error_code == "duplicate_in_batch"


async def test_queue_claim_is_exclusive(session) -> None:
    await _submit(session)

    first = await claim_next_job()
    second = await claim_next_job()

    assert first is not None
    assert second is None  # the only job was already claimed


async def test_stale_running_jobs_are_requeued(session) -> None:
    job_id = await _submit(session)
    await claim_next_job()

    # A worker that crashed leaves the row RUNNING with a stale heartbeat.
    async with pipeline_module.session_scope() as scoped:
        job = await scoped.get(Job, job_id)
        job.heartbeat_at = None

    assert await requeue_stale_jobs() == 1
    assert await claim_next_job() == job_id


async def test_cancel_applies_only_before_a_job_starts(session) -> None:
    job_id = await _submit(session)

    assert await cancel_job(job_id) is True
    assert await claim_next_job() is None
    assert await cancel_job(job_id) is False  # already cancelled


async def test_retry_puts_a_failed_job_back_on_the_queue(
    session, fake_media, patched_metadata, settings
) -> None:
    patched_metadata["error"] = VideoUnavailableError("gone")
    job_id = await _submit(session)
    with pytest.raises(VideoUnavailableError):
        await Pipeline(settings).run(job_id)

    assert await retry_job(job_id) is True
    assert await claim_next_job() == job_id
