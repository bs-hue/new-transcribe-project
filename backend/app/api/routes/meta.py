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


@public_router.get("/debug-proxy")
async def debug_proxy(settings: AppSettings):
    import httpx
    import traceback
    
    debug_log = []
    
    # Step 1: Check token
    if not settings.webshare_token:
        debug_log.append("ERROR: WEBSHARE_TOKEN is empty in environment.")
        return {"status": "failed_at_token", "log": debug_log}
    
    debug_log.append(f"WEBSHARE_TOKEN is set: {settings.webshare_token[:5]}***")
    
    # Step 2: Fetch proxies
    try:
        debug_log.append("Fetching proxies from Webshare API...")
        headers = {"Authorization": f"Token {settings.webshare_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://proxy.webshare.io/api/v2/proxy/list/?mode=direct", headers=headers)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            debug_log.append(f"SUCCESS: Fetched {len(results)} proxies.")
            if not results:
                return {"status": "no_proxies", "log": debug_log}
            
            p = results[0]
            proxy_url = f"http://{p['username']}:{p['password']}@{p['proxy_address']}:{p['port']}"
            debug_log.append(f"Selected proxy: {p['proxy_address']}:{p['port']}")
    except Exception as e:
        debug_log.append(f"ERROR fetching proxies: {e}")
        debug_log.append(traceback.format_exc())
        return {"status": "failed_at_webshare_api", "log": debug_log}
        
    # Step 3: Test proxy against YouTube
    try:
        debug_log.append("Testing proxy connection to YouTube...")
        async with httpx.AsyncClient(proxy=proxy_url, timeout=15) as client:
            r = await client.get("https://www.youtube.com")
            debug_log.append(f"SUCCESS: YouTube returned HTTP {r.status_code}")
            return {"status": "success", "log": debug_log}
    except Exception as e:
        debug_log.append(f"ERROR connecting to YouTube via proxy: {e}")
        debug_log.append(traceback.format_exc())
        return {"status": "failed_at_youtube", "log": debug_log}


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
