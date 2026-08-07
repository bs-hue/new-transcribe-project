"""Worker loop.

Runs inside the API process by default (``WORKER_ENABLED=true``), which keeps V1
to a single container. Set ``WORKER_ENABLED=false`` on the API and run
``python -m app.workers.runner`` separately the moment you want to scale
transcription independently of request serving — no code change required.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.config import Settings, get_settings
from app.services.pipeline import Pipeline
from app.workers.queue import claim_next_job, requeue_stale_jobs

logger = logging.getLogger(__name__)


class WorkerPool:
    """N concurrent workers polling the job table."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._tasks: list[asyncio.Task] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._tasks:
            return
        await requeue_stale_jobs()
        self._stopping.clear()
        self._tasks = [
            asyncio.create_task(self._loop(index), name=f"worker-{index}")
            for index in range(max(1, self.settings.worker_concurrency))
        ]
        logger.info("Started %d worker(s)", len(self._tasks))

    async def stop(self) -> None:
        if not self._tasks:
            return
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []
        logger.info("Workers stopped")

    async def _sleep_or_stop(self, seconds: float) -> None:
        """Idle for `seconds`, but wake immediately on shutdown."""
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)

    async def _loop(self, index: int) -> None:
        pipeline = Pipeline(self.settings)
        idle_backoff = self.settings.worker_poll_interval_seconds

        while not self._stopping.is_set():
            try:
                job_id = await claim_next_job()
            except Exception:
                logger.exception("worker-%d could not read the queue", index)
                await self._sleep_or_stop(idle_backoff * 5)
                continue

            if job_id is None:
                await self._sleep_or_stop(idle_backoff)
                continue

            logger.info("worker-%d picked up job %s", index, job_id)
            try:
                await pipeline.run(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                # The pipeline already recorded the failure against the job; the
                # worker's only job here is to stay alive for the next one.
                logger.debug("worker-%d finished job %s with an error", index, job_id)


async def run_forever() -> None:  # pragma: no cover - process entry point
    from app.core.logging import configure_logging
    from app.db.session import dispose_db, init_db

    settings = get_settings()
    configure_logging(settings.log_level)
    await init_db(settings)

    pool = WorkerPool(settings)
    await pool.start()
    try:
        await asyncio.Event().wait()  # until SIGINT/SIGTERM
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await pool.stop()
        await dispose_db()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_forever())
