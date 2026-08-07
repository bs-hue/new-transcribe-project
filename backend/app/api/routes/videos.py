"""Submit URLs, preview them, and browse the resulting videos."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.errors import AppError, NotFoundError
from app.db.models import Job, Transcript, Video
from app.schemas import (
    JobSummary,
    PreviewListResponse,
    PreviewResponse,
    SubmissionOutcomeResponse,
    SubmissionResponse,
    TranscriptDetail,
    URLListRequest,
    VideoDetail,
    VideoListResponse,
    VideoSummary,
)
from app.services.ingest import preview_url, submit_urls
from app.services.settings_store import effective_settings

router = APIRouter(prefix="/videos", tags=["videos"])

#: Preview probes the platform per URL. Fanning out unbounded would get us
#: rate-limited; four at a time keeps a 20-URL paste responsive without that.
_PREVIEW_CONCURRENCY = 4


def _enforce_batch_size(urls: list[str], settings: AppSettings) -> None:
    if len(urls) > settings.max_urls_per_request:
        raise AppError(
            f"Too many URLs: {len(urls)} submitted, limit is "
            f"{settings.max_urls_per_request}.",
            details={"limit": settings.max_urls_per_request},
        )


@router.post("/preview", response_model=PreviewListResponse)
async def preview(
    payload: URLListRequest, session: DbSession, settings: AppSettings
) -> PreviewListResponse:
    """Validate and probe URLs without downloading anything.

    This is step 3 of the workflow: the user sees title, thumbnail, duration and
    estimated size, plus any limit problems, before committing to a download.
    """
    # Limits are administrator-changeable, so read the effective values rather
    # than the ones captured at startup.
    settings = await effective_settings(session, settings)
    _enforce_batch_size(payload.urls, settings)
    semaphore = asyncio.Semaphore(_PREVIEW_CONCURRENCY)

    async def probe(url: str) -> PreviewResponse:
        async with semaphore:
            result = await preview_url(session, url, settings)
        return PreviewResponse(**asdict(result))

    results = await asyncio.gather(*(probe(url) for url in payload.urls))
    return PreviewListResponse(results=list(results))


@router.post("", response_model=SubmissionResponse, status_code=202)
async def submit(
    payload: URLListRequest,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
) -> SubmissionResponse:
    """Queue one job per valid URL. Invalid URLs are reported, not fatal."""
    settings = await effective_settings(session, settings)
    _enforce_batch_size(payload.urls, settings)
    result = await submit_urls(
        session,
        payload.urls,
        language=payload.language,
        settings=settings,
        submitted_by=user.id,
    )
    return SubmissionResponse(
        batch_id=result.batch_id,
        accepted_count=result.accepted_count,
        rejected_count=result.rejected_count,
        results=[SubmissionOutcomeResponse(**asdict(outcome)) for outcome in result.outcomes],
    )


@router.get("", response_model=VideoListResponse)
async def list_videos(
    session: DbSession,
    platform: str | None = None,
    author: str | None = None,
    has_transcript: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> VideoListResponse:
    statement = select(Video)
    count_statement = select(func.count(Video.id))

    if platform:
        statement = statement.where(Video.platform == platform)
        count_statement = count_statement.where(Video.platform == platform)
    if author:
        pattern = f"%{author.lower()}%"
        statement = statement.where(func.lower(Video.author).like(pattern))
        count_statement = count_statement.where(func.lower(Video.author).like(pattern))
    if has_transcript is not None:
        exists = select(Transcript.id).where(Transcript.video_id == Video.id).exists()
        condition = exists if has_transcript else ~exists
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)

    total = (await session.execute(count_statement)).scalar_one()
    rows = (
        (
            await session.execute(
                statement.order_by(Video.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )

    return VideoListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[VideoSummary.model_validate(row) for row in rows],
    )


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, session: DbSession) -> VideoDetail:
    video = (
        await session.execute(select(Video).where(Video.id == video_id))
    ).scalar_one_or_none()
    if video is None:
        raise NotFoundError(f"No video with id {video_id}.")

    transcript = (
        await session.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.video_id == video_id)
            .order_by(Transcript.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    transcript_count = (
        await session.execute(
            select(func.count(Transcript.id)).where(Transcript.video_id == video_id)
        )
    ).scalar_one()

    latest_job = (
        await session.execute(
            select(Job).where(Job.video_id == video_id).order_by(Job.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    detail = VideoDetail.model_validate(video)
    detail.transcript_count = int(transcript_count)
    detail.transcript = (
        TranscriptDetail.model_validate(transcript) if transcript is not None else None
    )
    detail.latest_job = JobSummary.model_validate(latest_job) if latest_job else None
    return detail


@router.delete("/{video_id}", status_code=204)
async def delete_video(video_id: str, session: DbSession) -> None:
    """Remove a video and everything derived from it."""
    video = await session.get(Video, video_id)
    if video is None:
        raise NotFoundError(f"No video with id {video_id}.")

    from app.services.search import get_search_backend

    backend = get_search_backend()
    transcript_ids = (
        (
            await session.execute(select(Transcript.id).where(Transcript.video_id == video_id))
        )
        .scalars()
        .all()
    )
    for transcript_id in transcript_ids:
        await backend.remove(session, transcript_id)

    await session.delete(video)
    await session.commit()
