"""Health and capability discovery.

``/meta`` exists so the frontend never hardcodes the list of platforms, export
formats or limits — add an exporter on the server and the UI dropdown grows.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AppSettings
from app.core.errors import AppError
from app.db.session import healthcheck
from app.platforms import supported_platforms
from app.schemas import HealthResponse, MetaResponse
from app.services.export import available_formats
from app.services.transcription import get_transcription_provider
from app.workers.queue import queue_depth

#: Routes that must work without a token: the container healthcheck cannot log in.
public_router = APIRouter(tags=["meta"])
#: Everything else — mounted behind authentication by app/api/router.py.
router = APIRouter(tags=["meta"])

VERSION = "1.0.0"


@public_router.get("/health", response_model=HealthResponse)
async def health(settings: AppSettings) -> HealthResponse:
    database_ok = await healthcheck()
    depth = await queue_depth() if database_ok else 0
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        database=database_ok,
        worker_enabled=settings.worker_enabled,
        queue_depth=depth,
    )


@router.get("/meta", response_model=MetaResponse)
async def meta(settings: AppSettings) -> MetaResponse:
    """Everything the client needs to render itself correctly."""
    transcription_ready = True
    transcription_error: str | None = None
    try:
        get_transcription_provider(settings).validate_configuration()
    except AppError as exc:
        transcription_ready = False
        transcription_error = exc.message

    return MetaResponse(
        app_name=settings.app_name,
        version=VERSION,
        commit=settings.build_commit,
        platforms=supported_platforms(),
        export_formats=available_formats(),
        limits={
            "max_video_duration_seconds": settings.max_video_duration_seconds,
            "max_video_filesize_bytes": settings.max_video_filesize_bytes,
            "max_urls_per_request": settings.max_urls_per_request,
        },
        transcription_provider=settings.transcription_provider,
        transcription_ready=transcription_ready,
        transcription_error=transcription_error,
        registration_mode=settings.registration_mode,
    )
