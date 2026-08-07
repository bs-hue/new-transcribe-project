"""The job queue — a table, not a broker.

Jobs are claimed with a conditional ``UPDATE ... WHERE status = 'queued'``, which
is atomic on both SQLite and Postgres. That keeps V1 to two processes and one
database. The interface here is narrow on purpose: when volume justifies Redis or
SQS, this file is what gets replaced, and nothing else.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.models import Job, JobStage, JobStatus
from app.db.session import session_scope

logger = logging.getLogger(__name__)

#: A running job whose heartbeat is older than this is presumed dead (the worker
#: crashed or the container was reclaimed mid-download) and is requeued.
STALE_AFTER = timedelta(minutes=30)


async def claim_next_job() -> str | None:
    """Atomically take the oldest queued job. Returns its id, or ``None``."""
    async with session_scope() as session:
        candidate = (
            await session.execute(
                select(Job.id)
                .where(Job.status == JobStatus.QUEUED.value)
                .order_by(Job.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()

        if candidate is None:
            return None

        now = datetime.now(UTC)
        # The status predicate is the lock: if another worker claimed this row
        # between the SELECT and here, rowcount is 0 and we simply try again.
        claimed = await session.execute(
            update(Job)
            .where(Job.id == candidate, Job.status == JobStatus.QUEUED.value)
            .values(
                status=JobStatus.RUNNING.value,
                stage=JobStage.PENDING.value,
                started_at=now,
                heartbeat_at=now,
                attempts=Job.attempts + 1,
                error_code=None,
                error_message=None,
            )
        )
        return candidate if claimed.rowcount else None


async def requeue_stale_jobs() -> int:
    """Recover jobs abandoned by a crashed worker. Called once at startup."""
    cutoff = datetime.now(UTC) - STALE_AFTER
    async with session_scope() as session:
        result = await session.execute(
            update(Job)
            .where(
                Job.status == JobStatus.RUNNING.value,
                (Job.heartbeat_at.is_(None)) | (Job.heartbeat_at < cutoff),
            )
            .values(
                status=JobStatus.QUEUED.value,
                stage=JobStage.PENDING.value,
                progress=0.0,
                error_code="worker_restarted",
                error_message="A worker stopped mid-job; this job was requeued.",
            )
        )
        count = result.rowcount or 0

    if count:
        logger.warning("Requeued %d stale job(s)", count)
    return count


async def cancel_job(job_id: str) -> bool:
    """Cancel a job that has not started. Returns whether anything changed.

    Running jobs are not interrupted: killing a download mid-flight leaves
    partial files and buys nothing, so cancellation applies to the queue only.
    """
    async with session_scope() as session:
        result = await session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.QUEUED.value)
            .values(
                status=JobStatus.CANCELLED.value,
                finished_at=datetime.now(UTC),
            )
        )
        return bool(result.rowcount)


async def retry_job(job_id: str) -> bool:
    """Put a failed or cancelled job back on the queue."""
    async with session_scope() as session:
        result = await session.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status.in_([JobStatus.FAILED.value, JobStatus.CANCELLED.value]),
            )
            .values(
                status=JobStatus.QUEUED.value,
                stage=JobStage.PENDING.value,
                progress=0.0,
                attempts=0,
                error_code=None,
                error_message=None,
                started_at=None,
                finished_at=None,
            )
        )
        return bool(result.rowcount)


async def queue_depth() -> int:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Job.id).where(Job.status == JobStatus.QUEUED.value)
            )
        ).all()
        return len(rows)
