"""Dashboard summary.

One request rather than five, because the dashboard polls while work is running
and five round trips every two seconds is wasteful for numbers this cheap to
compute.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.db.models import Job, JobStatus, Transcript, Video
from app.schemas import DashboardResponse, JobDetail, RecentTranscript, VideoSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

#: How many active jobs and recent transcripts the dashboard shows.
ACTIVE_LIMIT = 8
RECENT_LIMIT = 6
#: How many extra transcript rows to read so that de-duplicating by video still
#: leaves a full row of cards when videos have been transcribed more than once.
RECENT_OVERFETCH = 4


@router.get("", response_model=DashboardResponse)
async def dashboard(session: DbSession, _user: CurrentUser) -> DashboardResponse:
    active_states = [JobStatus.QUEUED.value, JobStatus.RUNNING.value]

    in_progress = (
        await session.execute(
            select(func.count(Job.id)).where(Job.status.in_(active_states))
        )
    ).scalar_one()

    # "Today" is deliberately UTC rather than the viewer's timezone: the server
    # has no reliable way to know theirs, and a wrong local midnight is worse
    # than a consistent one.
    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    finished_today = (
        await session.execute(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.COMPLETED.value, Job.finished_at >= midnight
            )
        )
    ).scalar_one()

    needs_attention = (
        await session.execute(
            select(func.count(Job.id)).where(Job.status == JobStatus.FAILED.value)
        )
    ).scalar_one()

    # Distinct videos, not transcripts. The tile links to History, which lists
    # videos — a video transcribed twice must not make the two counts disagree.
    total_research = (
        await session.execute(select(func.count(func.distinct(Transcript.video_id))))
    ).scalar_one()

    active_jobs = (
        (
            await session.execute(
                select(Job)
                .options(selectinload(Job.video))
                .where(Job.status.in_(active_states))
                .order_by(Job.created_at)
                .limit(ACTIVE_LIMIT)
            )
        )
        .unique()
        .scalars()
        .all()
    )

    # Newest first, then one card per video. Re-transcribing something must not
    # fill "Recent research" with the same video twice. Over-fetching and
    # de-duplicating in Python keeps this identical on SQLite and PostgreSQL.
    recent = (
        await session.execute(
            select(Transcript, Video)
            .join(Video, Video.id == Transcript.video_id)
            .order_by(Transcript.created_at.desc())
            .limit(RECENT_LIMIT * RECENT_OVERFETCH)
        )
    ).all()

    jobs: list[JobDetail] = []
    for job in active_jobs:
        detail = JobDetail.model_validate(job)
        detail.video = VideoSummary.model_validate(job.video) if job.video else None
        jobs.append(detail)

    transcripts: list[RecentTranscript] = []
    seen: set[str] = set()
    for transcript, video in recent:
        if transcript.video_id in seen:
            continue
        seen.add(transcript.video_id)
        item = RecentTranscript.model_validate(transcript)
        item.video = VideoSummary.model_validate(video)
        transcripts.append(item)
        if len(transcripts) == RECENT_LIMIT:
            break

    return DashboardResponse(
        in_progress=int(in_progress),
        finished_today=int(finished_today),
        needs_attention=int(needs_attention),
        total_research=int(total_research),
        active_jobs=jobs,
        recent_transcripts=transcripts,
    )
