"""FastAPI application entry point."""

from __future__ import annotations

import logging
import sys
import asyncio
from collections.abc import AsyncIterator

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.routes.meta import VERSION
from app.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.security import check_secret
from app.db.session import dispose_db, init_db
from app.services.transcription import get_transcription_provider
from app.services.users import bootstrap_admin
from app.workers.runner import WorkerPool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)


    # Refuse to start in production with the shipped JWT signing key â€” an
    # unchanged secret lets anyone mint a token for themselves.
    check_secret(settings)

    await init_db(settings)
    await bootstrap_admin(settings)

    # Surface misconfiguration at startup rather than after a user has waited
    # through a download. Not fatal: the rest of the app (browsing, search,
    # export of existing research) still works without a transcriber.
    try:
        get_transcription_provider(settings).validate_configuration()
        logger.info("Transcription provider: %s", settings.transcription_provider)
    except AppError as exc:
        logger.error("Transcription is not ready: %s", exc.message)

    pool: WorkerPool | None = None
    if settings.worker_enabled:
        pool = WorkerPool(settings)
        await pool.start()
    else:
        logger.info("WORKER_ENABLED=false â€” run workers with: python -m app.workers.runner")

    try:
        yield
    finally:
        if pool is not None:
            await pool.stop()
        await dispose_db()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=VERSION,
        description=(
            "Turn YouTube and Instagram URLs into stored, searchable, exportable "
            "research for the content team."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Exports are fetched with an Authorization header rather than a plain
        # link, so the browser reads the filename from this header â€” and a
        # cross-origin response hides it unless it is explicitly exposed.
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        """Every domain error becomes a consistent, machine-readable body."""
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": VERSION, "docs": "/docs"}

    return app


app = create_app()
