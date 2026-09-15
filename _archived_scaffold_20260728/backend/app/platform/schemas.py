"""Response shapes for the system endpoints.

These are *wire* models: they describe JSON, and they live at the boundary. They
are intentionally separate from any domain type, so that renaming an internal
field can never silently change the public API.

Contract: docs/API_SPECIFICATION.md §6
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HealthStatus = Literal["ok", "degraded"]
CheckStatus = Literal["ok", "error", "disabled"]


class HealthResponse(BaseModel):
    """Liveness and readiness report."""

    status: HealthStatus = Field(description="Overall health: 'ok' or 'degraded'.")
    version: str = Field(description="Application version.")
    checks: dict[str, CheckStatus] = Field(
        description="Per-dependency status, e.g. {'db': 'ok', 'queue': 'ok'}."
    )


class PublicConfigResponse(BaseModel):
    """Non-sensitive configuration the frontend needs.

    The UI reads its limits from here instead of hardcoding them, so tuning the
    server's configuration never requires a frontend release.
    """

    summarize_available: bool = Field(
        description="Whether AI summaries can be requested (needs an API key server-side)."
    )
    max_urls_per_batch: int
    max_video_duration_seconds: int
    supported_formats: list[str]
    default_model: str
    available_models: list[str]
    manual_retry_enabled: bool
    max_attempts: int
    playlists_supported: bool = Field(
        description="Playlist and channel URLs are rejected in v1; submit individual videos."
    )
