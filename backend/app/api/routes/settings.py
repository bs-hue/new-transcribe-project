"""Settings.

Reading is open to any signed-in user, so the app can show the limits it is
enforcing. Changing anything is admin-only.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUser, AppSettings, CurrentUser, DbSession
from app.diagnostics import render, run_diagnostics
from app.schemas import (
    SettingDefinition,
    SettingsResponse,
    SettingsUpdateRequest,
    SystemCheckResponse,
    SystemCheckResult,
)
from app.services.settings_store import DEFINITIONS, current_values, effective_settings
from app.services.settings_store import update_settings as apply_settings

router = APIRouter(prefix="/settings", tags=["settings"])


def _definitions() -> list[SettingDefinition]:
    return [
        SettingDefinition(
            key=d.key,
            label=d.label,
            help=d.help,
            kind=d.kind,
            minimum=d.minimum,
            maximum=d.maximum,
            choices=list(d.choices) if d.choices else None,
            choice_labels=dict(d.choice_labels) if d.choice_labels else None,
            applies_to=d.applies_to,
            unit=d.unit,
        )
        for d in DEFINITIONS
    ]


@router.get("", response_model=SettingsResponse)
async def read_settings(
    session: DbSession, settings: AppSettings, _user: CurrentUser
) -> SettingsResponse:
    effective = await effective_settings(session, settings)
    return SettingsResponse(
        values=await current_values(session),
        definitions=_definitions(),
        transcription_provider=effective.transcription_provider,
        cookies_configured=bool(effective.youtube_cookies_text),
        worker_concurrency=effective.worker_concurrency,
        environment=effective.environment,
    )


@router.patch("", response_model=SettingsResponse)
async def write_settings(
    payload: SettingsUpdateRequest,
    session: DbSession,
    settings: AppSettings,
    admin: AdminUser,
) -> SettingsResponse:
    await apply_settings(session, payload.values, updated_by=admin.id)
    return await read_settings(session, settings, admin)


@router.get("/system-check", response_model=SystemCheckResponse)
async def system_check(
    settings: AppSettings, _admin: AdminUser, deep: bool = False
) -> SystemCheckResponse:
    """The same checks as `python -m app.cli doctor`, in the browser.

    So nobody needs terminal access to find out why transcription is failing.
    `deep` additionally loads the speech model and transcribes a bundled clip;
    it is slow the first time, because that is when the model downloads.
    """
    report = await run_diagnostics(settings, deep=deep)
    return SystemCheckResponse(
        ok=report.ok,
        results=[
            SystemCheckResult(
                name=result.name,
                ok=result.ok,
                warning_only=result.warning_only,
                detail=result.detail,
                fix=result.fix,
            )
            for result in report.results
        ],
        text=render(report),
    )
