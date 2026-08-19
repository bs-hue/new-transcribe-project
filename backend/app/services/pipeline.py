"""The processing pipeline.

    metadata → limits → download → audio → transcribe → store

Each stage is an ``async`` method with the same shape, taking and mutating a
``PipelineContext``. This is the only module that knows the *order* of things —
which is exactly why V2's analysis stage is one entry appended to ``_STAGES``
and nothing else changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.core.errors import AppError, TranscriptionError
from app.core.text import word_count
from app.db.models import Job, JobStage, JobStatus, Transcript, TranscriptSegment, Video
from app.db.session import session_scope
from app.platforms import ParsedURL, parse_url
from app.services.limits import enforce_limits
from app.services.media import MediaBackend, WorkDirectory, get_media_backend, new_work_directory
from app.services.metadata import VideoMetadata, fetch_metadata
from app.services.search import get_search_backend
from app.services.settings_store import effective_settings
from app.services.transcription import (
    TranscriptionProvider,
    TranscriptionResult,
    get_transcription_provider,
    merge_results,
)

logger = logging.getLogger(__name__)

# WAV at 16 kHz, mono, 16-bit. Used to convert a provider's byte cap into a
# chunk duration without probing the file.
_BYTES_PER_AUDIO_SECOND = 16_000 * 2 * 1

# Fraction of overall progress each stage accounts for. Download and
# transcription dominate, so they get the range the user actually watches move.
_STAGE_PROGRESS: dict[JobStage, tuple[float, float]] = {
    JobStage.FETCHING_METADATA: (0.00, 0.05),
    JobStage.CHECKING_LIMITS: (0.05, 0.07),
    JobStage.DOWNLOADING: (0.07, 0.50),
    JobStage.EXTRACTING_AUDIO: (0.50, 0.60),
    JobStage.TRANSCRIBING: (0.60, 0.95),
    JobStage.STORING: (0.95, 1.00),
}


@dataclass(slots=True)
class PipelineContext:
    job_id: str
    video_id: str
    canonical_url: str
    source_url: str
    language: str | None
    work: WorkDirectory
    #: The settings this job runs under: environment defaults with whatever an
    #: administrator has since changed on the Settings screen applied on top.
    #: Read once per job so a change takes effect on the next video rather than
    #: on the next restart — and so one job cannot change under its own feet.
    settings: Settings | None = None
    parsed: ParsedURL | None = None
    metadata: VideoMetadata | None = None
    video_path: Path | None = None
    audio_path: Path | None = None
    result: TranscriptionResult | None = None
    transcript_id: str | None = None
    warnings: list[str] = field(default_factory=list)


class Pipeline:
    """Runs one job from queued to completed."""

    def __init__(
        self,
        settings: Settings | None = None,
        media_backend: MediaBackend | None = None,
        provider: TranscriptionProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._media = media_backend
        self._provider = provider

    @property
    def media(self) -> MediaBackend:
        # Resolved lazily so tests can swap the backend after construction.
        return self._media or get_media_backend(self.settings)

    @property
    def provider(self) -> TranscriptionProvider:
        return self._provider or get_transcription_provider(self.settings)

    def provider_for(self, settings: Settings) -> TranscriptionProvider:
        """The provider built from this job's live settings.

        The model size, the spoken language and the expected vocabulary are all
        changeable from the Settings screen, and all of them are read by the
        provider — so it has to be built from the effective settings, not from
        the ones this process happened to start with.
        """
        return self._provider or get_transcription_provider(settings)

    def media_for(self, settings: Settings) -> MediaBackend:
        """The media backend built from this job's live settings."""
        return self._media or get_media_backend(settings)

    # --- progress ---------------------------------------------------------

    async def _set_stage(self, job_id: str, stage: JobStage, fraction: float = 0.0) -> None:
        """Persist stage + overall progress.

        Deliberately a short, separate transaction: holding one open across a
        multi-minute download would block every other writer on SQLite.
        """
        start, end = _STAGE_PROGRESS.get(stage, (0.0, 0.0))
        progress = start + (end - start) * min(max(fraction, 0.0), 1.0)
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.stage = stage.value
            job.progress = round(progress, 4)
            job.heartbeat_at = datetime.now(UTC)

    # --- stages -----------------------------------------------------------

    async def _stage_metadata(self, ctx: PipelineContext) -> None:
        await self._set_stage(ctx.job_id, JobStage.FETCHING_METADATA)
        ctx.parsed = parse_url(ctx.source_url or ctx.canonical_url)
        ctx.metadata = await fetch_metadata(ctx.parsed, ctx.settings or self.settings)

        async with session_scope() as session:
            video = await session.get(Video, ctx.video_id)
            if video is not None:
                _apply_metadata(video, ctx.metadata)

    async def _stage_limits(self, ctx: PipelineContext) -> None:
        await self._set_stage(ctx.job_id, JobStage.CHECKING_LIMITS)
        assert ctx.metadata is not None
        enforce_limits(ctx.metadata, ctx.settings or self.settings)

    async def _stage_download(self, ctx: PipelineContext) -> None:
        await self._set_stage(ctx.job_id, JobStage.DOWNLOADING)

        last_reported = 0.0

        async def on_progress(fraction: float) -> None:
            nonlocal last_reported
            # One write per whole percent: enough for a smooth bar, far fewer
            # transactions than yt-dlp's per-chunk callback would produce.
            if fraction - last_reported < 0.01 and fraction < 1.0:
                return
            last_reported = fraction
            await self._set_stage(ctx.job_id, JobStage.DOWNLOADING, fraction)

        ctx.video_path = await self.media_for(ctx.settings or self.settings).download_video(
            ctx.canonical_url, ctx.work.path, on_progress
        )

    async def _stage_audio(self, ctx: PipelineContext) -> None:
        await self._set_stage(ctx.job_id, JobStage.EXTRACTING_AUDIO)
        assert ctx.video_path is not None
        ctx.audio_path = await self.media_for(ctx.settings or self.settings).extract_audio(ctx.video_path, ctx.work.path)

    async def _stage_transcribe(self, ctx: PipelineContext) -> None:
        await self._set_stage(ctx.job_id, JobStage.TRANSCRIBING)
        assert ctx.audio_path is not None

        settings = ctx.settings or self.settings
        provider = self.provider_for(settings)
        # A language chosen for this batch wins; otherwise the standing choice
        # from the Settings screen, which is the one people actually maintain.
        language = ctx.language or settings.transcription_language
        cap = provider.max_audio_bytes
        size = ctx.audio_path.stat().st_size

        if cap is None or size <= cap:
            ctx.result = await provider.transcribe(ctx.audio_path, language=language)
            return

        # Too large for the provider: split, transcribe each part, and stitch the
        # timestamps back onto the original timeline.
        # Floor of 10s, not 60: a hosted provider's per-request limit can be
        # shorter than a minute, and a chunk larger than the cap is refused.
        chunk_seconds = max(10, int(cap * 0.9 / _BYTES_PER_AUDIO_SECOND))
        chunks = await self.media_for(settings).split_audio(ctx.audio_path, chunk_seconds)
        logger.info("Audio is %d bytes; transcribing in %d chunks", size, len(chunks))

        results: list[tuple[TranscriptionResult, float]] = []
        for position, (chunk_path, offset) in enumerate(chunks):
            await self._set_stage(
                ctx.job_id, JobStage.TRANSCRIBING, position / max(len(chunks), 1)
            )
            results.append((await provider.transcribe(chunk_path, language=language), offset))

        ctx.result = merge_results(
            results, provider=provider.name, model=provider.model_name
        )

    async def _stage_store(self, ctx: PipelineContext) -> None:
        await self._set_stage(ctx.job_id, JobStage.STORING)
        assert ctx.result is not None

        result = ctx.result
        if not result.text.strip():
            # Music-only Reels are common enough that this needs its own message
            # rather than surfacing as an empty, apparently-successful result.
            raise TranscriptionError(
                "No speech was detected in this video.",
                details={"video_id": ctx.video_id},
            )

        async with session_scope() as session:
            video = await session.get(Video, ctx.video_id)
            transcript = Transcript(
                video_id=ctx.video_id,
                job_id=ctx.job_id,
                text=result.text,
                language=result.language,
                provider=result.provider or self.provider.name,
                model=result.model,
                word_count=word_count(result.text),
                duration_seconds=result.duration_seconds
                or (video.duration_seconds if video else None),
            )
            session.add(transcript)
            await session.flush()

            session.add_all(
                [
                    TranscriptSegment(
                        transcript_id=transcript.id,
                        index=segment.index,
                        start=segment.start,
                        end=segment.end,
                        text=segment.text,
                        speaker=segment.speaker,
                    )
                    for segment in result.segments
                ]
            )

            await get_search_backend(self.settings).index(
                session,
                transcript_id=transcript.id,
                video_id=ctx.video_id,
                title=(video.title if video else "") or "",
                author=(video.author if video else "") or "",
                body=result.text,
            )
            ctx.transcript_id = transcript.id

    _STAGES = (
        _stage_metadata,
        _stage_limits,
        _stage_download,
        _stage_audio,
        _stage_transcribe,
        _stage_store,
    )

    # --- entry point ------------------------------------------------------

    async def run(self, job_id: str) -> None:
        """Execute every stage, then mark the job completed or failed."""
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                logger.warning("Job %s vanished before it could run", job_id)
                return
            video = await session.get(Video, job.video_id)
            if video is None:
                logger.warning("Job %s has no video", job_id)
                return
            ctx_seed = (job.video_id, video.canonical_url, video.source_url, job.language)
            # Once, here, so every stage of this job sees one consistent set of
            # values — including the model, language and vocabulary that decide
            # what the transcript actually says.
            live_settings = await effective_settings(session, self.settings)

        video_id, canonical_url, source_url, language = ctx_seed
        work = new_work_directory(job_id, self.settings)
        ctx = PipelineContext(
            job_id=job_id,
            video_id=video_id,
            canonical_url=canonical_url,
            source_url=source_url,
            language=language,
            work=work,
            settings=live_settings,
        )

        try:
            for stage in self._STAGES:
                await stage(self, ctx)
        except AppError as exc:
            logger.warning("Job %s failed (%s): %s", job_id, exc.code, exc.message)
            await self._finish_failed(job_id, exc)
            raise
        except Exception as exc:  # unexpected: log the trace, keep the message generic
            logger.exception("Job %s crashed", job_id)
            await self._finish_failed(
                job_id, AppError(f"Unexpected error: {exc}")
            )
            raise
        else:
            await self._finish_completed(job_id)
        finally:
            work.cleanup()

    async def _finish_completed(self, job_id: str) -> None:
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.status = JobStatus.COMPLETED.value
            job.stage = JobStage.DONE.value
            job.progress = 1.0
            job.error_code = None
            job.error_message = None
            job.finished_at = datetime.now(UTC)

    async def _finish_failed(self, job_id: str, error: AppError) -> None:
        """Record the failure. The worker decides whether to requeue."""
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.error_code = error.code
            job.error_message = error.message
            retryable = error.retryable and job.attempts < self.settings.job_max_attempts
            if retryable:
                job.status = JobStatus.QUEUED.value
                job.stage = JobStage.PENDING.value
                job.progress = 0.0
            else:
                job.status = JobStatus.FAILED.value
                job.finished_at = datetime.now(UTC)


def _apply_metadata(video: Video, metadata: VideoMetadata) -> None:
    # platform_video_id is intentionally not overwritten: it is the identity we
    # de-duplicate on, parsed from the URL, and the provider's own id can differ
    # (Instagram shortcode vs numeric media id) which would fork the row.
    video.canonical_url = metadata.canonical_url
    video.title = metadata.title
    video.description = metadata.description
    video.author = metadata.author
    video.author_url = metadata.author_url
    video.thumbnail_url = metadata.thumbnail_url
    video.duration_seconds = metadata.duration_seconds
    video.estimated_size_bytes = metadata.estimated_size_bytes
    video.view_count = metadata.view_count
    video.like_count = metadata.like_count
    video.published_at = metadata.published_at
    video.raw_metadata = metadata.raw


async def load_job_with_video(session, job_id: str) -> Job | None:  # noqa: ANN001
    result = await session.execute(
        select(Job).options(selectinload(Job.video)).where(Job.id == job_id)
    )
    return result.scalar_one_or_none()
