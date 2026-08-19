"""Runtime-changeable settings.

Most configuration is environment-driven and stays that way. A small allowlist
of operational settings — limits, language, model size — can be changed by an
administrator from the Settings screen without editing files or restarting.

Two rules govern what may appear here:

* **Nothing security- or infrastructure-related.** The signing key, the database
  URL and the CORS list are environment-only. A UI that can weaken
  authentication is a UI that will eventually be used to weaken authentication.
* **It must take effect without a restart.** These values are read at the point
  of use, not captured at startup, so a change applies to the next job.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import AppSetting
from app.services.transcription import SELECTABLE_PROVIDERS
from app.services.transcription.languages import COMMON as LANGUAGES
from app.services.transcription.languages import normalise as normalise_language

logger = logging.getLogger(__name__)

Kind = Literal["int", "str"]
#: What a number means. The UI uses this to print "2 hours" beside "7200", so a
#: raw byte count never has to be read as one.
Unit = Literal["seconds", "bytes", "count"]


@dataclass(frozen=True, slots=True)
class Definition:
    key: str
    kind: Kind
    label: str
    help: str
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] | None = None
    #: Human wording for each choice. A dropdown offering "hi" helps nobody;
    #: one offering "Hindi" does. Absent means the choice is already readable.
    choice_labels: dict[str, str] | None = None
    #: Whether changing it affects work already done, or only future jobs.
    applies_to: str = "future jobs"
    unit: Unit | None = None


DEFINITIONS: tuple[Definition, ...] = (
    Definition(
        key="max_video_duration_seconds",
        kind="int",
        label="Longest video accepted",
        help="Videos longer than this are refused before anything is downloaded.",
        minimum=60,
        maximum=86_400,
        applies_to="videos submitted from now on",
        unit="seconds",
    ),
    Definition(
        key="max_video_filesize_bytes",
        kind="int",
        label="Largest download accepted",
        help="Videos estimated larger than this are refused before downloading.",
        minimum=1_000_000,
        maximum=100_000_000_000,
        applies_to="videos submitted from now on",
        unit="bytes",
    ),
    Definition(
        key="max_urls_per_request",
        kind="int",
        label="Links per batch",
        help="How many URLs can be pasted at once.",
        minimum=1,
        maximum=500,
        applies_to="the next submission",
        unit="count",
    ),
    Definition(
        key="transcription_provider",
        kind="str",
        label="Transcription engine",
        help="Where the speech is turned into text. On this machine is free and "
        "private but limited by the hardware. Sarvam AI is built for Indian "
        "languages and much faster — and it uploads the audio to a third "
        "party, so it needs an API key set by whoever installed this.",
        choices=SELECTABLE_PROVIDERS,
        choice_labels={
            "faster_whisper": "On this machine — free, private, slower",
            "sarvam": "Sarvam AI — faster and better Hindi, audio is uploaded",
        },
        applies_to="jobs started from now on",
    ),
    Definition(
        key="transcription_language",
        kind="str",
        label="Spoken language",
        help="Naming the language is the single biggest accuracy win outside "
        "English. Automatic detection listens to a few seconds and often "
        "mistakes Hindi for a neighbouring language, then transcribes the "
        "whole video wrongly. Set it if your videos are usually one language.",
        choices=("", *LANGUAGES),
        choice_labels={"": "Detect automatically", **LANGUAGES},
        applies_to="jobs started from now on",
    ),
    Definition(
        key="transcription_vocabulary",
        kind="str",
        label="Words to expect",
        help="Brand names, product names and jargon your videos use, separated "
        "by commas. The model works from sound alone, so a word it has never "
        "met becomes whatever it sounds nearest to — 'black obsidian' turns "
        "into nonsense. Naming them in advance fixes precisely that.",
        applies_to="jobs started from now on",
    ),
    Definition(
        key="faster_whisper_model",
        kind="str",
        label="Accuracy",
        help="Bigger models are more accurate and slower, and download once on "
        "first use. For Hindi and other Indian languages, anything below "
        "'small' produces text you cannot trust.",
        choices=("tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"),
        choice_labels={
            "tiny": "Tiny — fastest, English only, rough",
            "base": "Base — fast, fine for clear English, weak on Hindi",
            "small": "Small — workable Hindi, quick",
            "medium": "Medium — good Hindi, about 2× slower than small",
            "large-v3-turbo": (
                "Turbo — near-Large quality at roughly Medium speed (recommended)"
            ),
            "large-v3": "Large — best available, and about 5× slower than Turbo",
        },
        applies_to="jobs started from now on",
    ),
    Definition(
        key="youtube_cookies_text",
        kind="str",
        label="YouTube Cookies (Optional)",
        help="Paste the contents of your cookies.txt file here to authenticate with YouTube and bypass the 'Sign in' blocks on Datacenter IPs.",
        applies_to="jobs started from now on",
    ),
)

_BY_KEY = {definition.key: definition for definition in DEFINITIONS}


def _coerce(definition: Definition, raw: str) -> Any:
    if definition.kind == "int":
        return int(raw)

    # Values written before this key was validated are still in the database.
    # Normalising on the way out as well as the way in heals them in place,
    # rather than failing every job until somebody re-saves the screen.
    if definition.key == "transcription_language":
        try:
            return normalise_language(raw)
        except AppError:
            logger.warning(
                "Stored language %r is not one this can transcribe; detecting instead",
                raw,
            )
            return None

    return raw or None


def _validate(definition: Definition, value: Any) -> str:
    """Check a proposed value and return it as the stored string form."""
    if definition.kind == "int":
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise AppError(f"{definition.label} must be a whole number.") from exc
        if definition.minimum is not None and number < definition.minimum:
            raise AppError(f"{definition.label} must be at least {definition.minimum:,}.")
        if definition.maximum is not None and number > definition.maximum:
            raise AppError(f"{definition.label} must be at most {definition.maximum:,}.")
        return str(number)

    text = "" if value is None else str(value).strip()

    # "Hindi" is what a person types, "hi" is what Whisper needs. Translating
    # here means an older screen, an API client or a hand-edited value all end
    # up storing something the transcriber will actually honour.
    if definition.key == "transcription_language":
        return normalise_language(text) or ""

    if definition.choices and text not in definition.choices:
        raise AppError(
            f"{definition.label} must be one of: {', '.join(definition.choices)}."
        )
    return text


async def load_overrides(session: AsyncSession) -> dict[str, Any]:
    """Every stored override, coerced to its proper type."""
    rows = (await session.execute(select(AppSetting))).scalars().all()
    overrides: dict[str, Any] = {}
    for row in rows:
        definition = _BY_KEY.get(row.key)
        if definition is None:
            continue  # a setting that was removed from the allowlist
        try:
            overrides[row.key] = _coerce(definition, row.value)
        except ValueError:
            logger.warning("Ignoring unreadable setting %s=%r", row.key, row.value)
    return overrides


async def effective_settings(
    session: AsyncSession, base: Settings | None = None
) -> Settings:
    """Environment defaults with any stored overrides applied.

    Returns a copy — the cached global settings object is never mutated, so a
    request that changes a limit cannot affect a job already in flight.
    """
    base = base or get_settings()
    overrides = await load_overrides(session)
    return base.model_copy(update=overrides) if overrides else base


async def current_values(session: AsyncSession) -> dict[str, Any]:
    """What each allowlisted setting is right now, override or default."""
    settings = await effective_settings(session)
    return {definition.key: getattr(settings, definition.key) for definition in DEFINITIONS}


async def update_settings(
    session: AsyncSession, changes: dict[str, Any], *, updated_by: str | None = None
) -> dict[str, Any]:
    """Validate and persist changes. Returns the new effective values."""
    unknown = set(changes) - set(_BY_KEY)
    if unknown:
        raise AppError(f"Not a changeable setting: {', '.join(sorted(unknown))}.")

    for key, value in changes.items():
        definition = _BY_KEY[key]
        stored = _validate(definition, value)
        existing = await session.get(AppSetting, key)
        if existing is None:
            session.add(AppSetting(key=key, value=stored, updated_by=updated_by))
        else:
            existing.value = stored
            existing.updated_by = updated_by

    await session.commit()
    logger.info("Settings updated by %s: %s", updated_by or "unknown", sorted(changes))
    return await current_values(session)
