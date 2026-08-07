"""Job status, batch progress, retry and cancel.

The frontend polls ``/jobs/batch/{batch_id}`` while a submission is processing;
one request covers a whole paste, however many URLs it contained.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.core.errors import NotFoundError
from app.db.models import Job, JobStatus, Transcript, User
from app.schemas import BatchStatusResponse, JobDetail, JobListResponse, VideoSummary
from app.workers.queue import cancel_job, retry_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _to_detail(session, job: Job) -> JobDetail:  # noqa: ANN001
    detail = JobDetail.model_validate(job)
    detail.video = VideoSummary.model_validate(job.video) if job.video else None
    detail.transcript_id = (
        await session.execute(
            select(Transcript.id)
            .where(Transcript.job_id == job.id)
            .order_by(Transcript.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Resolved for display. Null when the account has since been removed —
    # deleting a colleague must not delete the research they collected.
    if job.submitted_by:
        submitter = await session.get(User, job.submitted_by)
        if submitter is not None:
            detail.submitted_by_name = submitter.full_name or submitter.email
    return detail


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session: DbSession,
    status: str | None = None,
    batch_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    statement = select(Job).options(selectinload(Job.video))
    count_statement = select(func.count(Job.id))

    if status:
        statement = statement.where(Job.status == status)
        count_statement = count_statement.where(Job.status == status)
    if batch_id:
        statement = statement.where(Job.batch_id == batch_id)
        count_statement = count_statement.where(Job.batch_id == batch_id)

    total = (await session.execute(count_statement)).scalar_one()
    jobs = (
        (
            await session.execute(
                statement.order_by(Job.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .unique()
        .scalars()
        .all()
    )

    return JobListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[await _to_detail(session, job) for job in jobs],
    )


@router.get("/batch/{batch_id}", response_model=BatchStatusResponse)
async def batch_status(batch_id: str, session: DbSession) -> BatchStatusResponse:
    """Aggregate progress for one submission."""
    jobs = (
        (
            await session.execute(
                select(Job)
                .options(selectinload(Job.video))
                .where(Job.batch_id == batch_id)
                .order_by(Job.created_at)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    if not jobs:
        raise NotFoundError(f"No batch with id {batch_id}.")

    counts = {status.value: 0 for status in JobStatus}
    for job in jobs:
        counts[job.status] = counts.get(job.status, 0) + 1

    return BatchStatusResponse(
        batch_id=batch_id,
        total=len(jobs),
        queued=counts[JobStatus.QUEUED.value],
        running=counts[JobStatus.RUNNING.value],
        completed=counts[JobStatus.COMPLETED.value],
        failed=counts[JobStatus.FAILED.value],
        cancelled=counts[JobStatus.CANCELLED.value],
        jobs=[await _to_detail(session, job) for job in jobs],
    )


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, session: DbSession) -> JobDetail:
    job = (
        await session.execute(
            select(Job).options(selectinload(Job.video)).where(Job.id == job_id)
        )
    ).unique().scalar_one_or_none()
    if job is None:
        raise NotFoundError(f"No job with id {job_id}.")
    return await _to_detail(session, job)


@router.post("/{job_id}/retry", response_model=JobDetail)
async def retry(job_id: str, session: DbSession) -> JobDetail:
    if not await retry_job(job_id):
        raise NotFoundError("Only failed or cancelled jobs can be retried.")
    return await get_job(job_id, session)


@router.post("/{job_id}/cancel", response_model=JobDetail)
async def cancel(job_id: str, session: DbSession) -> JobDetail:
    if not await cancel_job(job_id):
        raise NotFoundError("Only jobs that have not started yet can be cancelled.")
    return await get_job(job_id, session)
