"""System endpoints: ``GET /health`` and ``GET /config/public``.

Both are public — a monitoring probe cannot log in, and the frontend needs its
limits before a user exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.database import ping
from app.core.dependencies import EngineDep, SettingsDep
from app.platform.schemas import CheckStatus, HealthResponse, PublicConfigResponse

router = APIRouter(tags=["platform"])

#: Whisper model sizes we expose. Larger is more accurate and slower; on a
#: CPU-only box anything above `small` is usually impractical, so `large` is
#: deliberately absent until benchmarking says otherwise.
AVAILABLE_MODELS = ["tiny", "base", "small", "medium"]

#: Export formats derived on demand from a stored transcript (FR-T1..T3).
SUPPORTED_FORMATS = ["txt", "srt", "vtt", "json"]


# Defined with `def`, not `async def`, on purpose: the database ping is blocking
# I/O. FastAPI runs sync endpoints in a worker thread, so the event loop stays
# free. An `async def` here would block every other request while it waited.
@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and readiness",
    responses={503: {"description": "A required dependency is unavailable."}},
)
def health(response: Response, engine: EngineDep, settings: SettingsDep) -> HealthResponse:
    """Report whether this process is running *and* able to serve traffic.

    Returns **503** when a required dependency is down. That distinction matters
    to whatever is watching: a process that is alive but cannot reach its
    database should be restarted or taken out of rotation, not counted healthy.
    """
    database_ok = ping(engine)

    checks: dict[str, CheckStatus] = {
        "db": "ok" if database_ok else "error",
        # v1 executes jobs in this same process, so a live process means a live
        # queue. This becomes a real check when the ARQ worker is introduced.
        "queue": "ok",
    }

    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", version=settings.app_version, checks=checks)

    return HealthResponse(status="ok", version=settings.app_version, checks=checks)


@router.get(
    "/config/public",
    response_model=PublicConfigResponse,
    summary="Client configuration",
)
def public_config(settings: SettingsDep) -> PublicConfigResponse:
    """Expose the non-sensitive settings the UI needs to render correctly.

    Nothing secret may be added here — the response is readable by anyone.
    """
    return PublicConfigResponse(
        summarize_available=settings.summarize_available,
        max_urls_per_batch=settings.max_urls_per_batch,
        max_video_duration_seconds=settings.max_video_duration_seconds,
        supported_formats=SUPPORTED_FORMATS,
        default_model=settings.whisper_model,
        available_models=AVAILABLE_MODELS,
        manual_retry_enabled=True,
        max_attempts=settings.max_attempts,
        playlists_supported=False,
    )
