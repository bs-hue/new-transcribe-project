"""Top-level API router.

Authentication is applied here, once, to everything except the routes that must
work without it — so a new router cannot accidentally ship unprotected.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.routes import (
    auth,
    dashboard,
    exports,
    jobs,
    meta,
    search,
    settings,
    transcripts,
    videos,
)

api_router = APIRouter(prefix="/api")

# Public: the health probe (used by Docker) and the login endpoint itself.
api_router.include_router(meta.public_router)
api_router.include_router(auth.router)

# Everything else requires a valid token.
protected = APIRouter(dependencies=[Depends(get_current_user)])
protected.include_router(meta.router)
protected.include_router(dashboard.router)
protected.include_router(settings.router)
protected.include_router(videos.router)
protected.include_router(jobs.router)
protected.include_router(transcripts.router)
protected.include_router(search.router)
protected.include_router(exports.router)

api_router.include_router(protected)
