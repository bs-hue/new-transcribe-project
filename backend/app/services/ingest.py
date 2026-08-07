"""Turning pasted URLs into videos and queued jobs.

Submission is deliberately forgiving: one bad URL in a batch of forty should not
reject the batch. Every URL comes back with its own accepted/rejected verdict and
a reason, which is what the UI renders next to each row.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import Job, JobStatus, Transcript, Video
from app.platforms import ParsedURL, parse_url
from app.services.limits import LimitVerdict, check_limits
from app.services.metadata import VideoMetadata, fetch_metadata

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SubmissionOutcome:
    url: str
    accepted: bool
    job_id: str | None = None
    video_id: str | None = None
    platform: str | None = None
    canonical_url: str | None = None
    duplicate_of_existing_video: bool = False
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class SubmissionResult:
    batch_id: str
    outcomes: list[SubmissionOutcome] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.outcomes) - self.accepted_count


@dataclass(slots=True)
class PreviewResult:
    url: str
    valid: bool
    platform: str | None = None
    platform_display_name: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    author: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    estimated_size_bytes: int | None = None
    within_limits: bool = True
    limit_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    already_transcribed: bool = False
    error_code: str | None = None
    error_message: str | None = None


async def _get_or_create_video(session: AsyncSession, parsed: ParsedURL) -> tuple[Video, bool]:
    """Fetch the existing row for this platform video, or create it."""
    existing = (
        await session.execute(
            select(Video).where(
                Video.platform == parsed.platform,
                Video.platform_video_id == parsed.video_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        return existing, True

    video = Video(
        platform=parsed.platform,
        platform_video_id=parsed.video_id,
        source_url=parsed.original_url,
        canonical_url=parsed.canonical_url,
    )
    session.add(video)
    await session.flush()
    return video, False


async def submit_urls(
    session: AsyncSession,
    urls: list[str],
    *,
    language: str | None = None,
    settings: Settings | None = None,
    submitted_by: str | None = None,
) -> SubmissionResult:
    """Validate URLs and queue a job for each accepted one.

    Deliberately does *not* fetch metadata: submission stays fast and the user
    gets job ids immediately. The pipeline probes metadata as its first stage.
    """
    settings = settings or get_settings()
    batch_id = uuid.uuid4().hex
    result = SubmissionResult(batch_id=batch_id)
    seen_in_batch: set[tuple[str, str]] = set()

    for raw_url in urls:
        try:
            parsed = parse_url(raw_url)
        except AppError as exc:
            result.outcomes.append(
                SubmissionOutcome(
                    url=raw_url,
                    accepted=False,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            )
            continue

        key = (parsed.platform, parsed.video_id)
        if key in seen_in_batch:
            result.outcomes.append(
                SubmissionOutcome(
                    url=raw_url,
                    accepted=False,
                    platform=parsed.platform,
                    canonical_url=parsed.canonical_url,
                    error_code="duplicate_in_batch",
                    error_message="This URL appears more than once in the submission.",
                )
            )
            continue
        seen_in_batch.add(key)

        video, existed = await _get_or_create_video(session, parsed)
        job = Job(
            video_id=video.id,
            batch_id=batch_id,
            submitted_by=submitted_by,
            status=JobStatus.QUEUED.value,
            language=language,
        )
        session.add(job)
        await session.flush()

        result.outcomes.append(
            SubmissionOutcome(
                url=raw_url,
                accepted=True,
                job_id=job.id,
                video_id=video.id,
                platform=parsed.platform,
                canonical_url=parsed.canonical_url,
                duplicate_of_existing_video=existed,
            )
        )

    await session.commit()
    logger.info(
        "Batch %s: %d queued, %d rejected",
        batch_id,
        result.accepted_count,
        result.rejected_count,
    )
    return result


async def preview_url(
    session: AsyncSession, raw_url: str, settings: Settings | None = None
) -> PreviewResult:
    """Validate, probe metadata, and check limits — without downloading."""
    settings = settings or get_settings()

    try:
        parsed = parse_url(raw_url)
    except AppError as exc:
        return PreviewResult(
            url=raw_url, valid=False, error_code=exc.code, error_message=exc.message
        )

    try:
        metadata: VideoMetadata = await fetch_metadata(parsed, settings)
    except AppError as exc:
        return PreviewResult(
            url=raw_url,
            valid=False,
            platform=parsed.platform,
            platform_display_name=parsed.platform_display_name,
            canonical_url=parsed.canonical_url,
            error_code=exc.code,
            error_message=exc.message,
        )

    verdict: LimitVerdict = check_limits(metadata, settings)

    already = bool(
        (
            await session.execute(
                select(Transcript.id)
                .join(Video, Video.id == Transcript.video_id)
                .where(
                    Video.platform == parsed.platform,
                    Video.platform_video_id == parsed.video_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    )

    return PreviewResult(
        url=raw_url,
        valid=True,
        platform=parsed.platform,
        platform_display_name=parsed.platform_display_name,
        canonical_url=metadata.canonical_url,
        title=metadata.title,
        author=metadata.author,
        thumbnail_url=metadata.thumbnail_url,
        duration_seconds=metadata.duration_seconds,
        estimated_size_bytes=metadata.estimated_size_bytes,
        within_limits=verdict.allowed,
        limit_reasons=list(verdict.reasons),
        warnings=list(verdict.warnings),
        already_transcribed=already,
    )
