"""Spoken languages, by the name a person would use.

Whisper wants a two-letter code. People type "Hindi". Somebody has to translate
between the two, and it should not be the person — typing the language's own
name into a box labelled "Spoken language" is not a mistake, and the system
accepting it and then silently ignoring it is.
"""

from __future__ import annotations

from app.core.errors import AppError

#: Offered in the UI, in the order they appear. Every language Whisper supports
#: still works if its code is typed directly; these are the ones an Indian
#: agency actually needs at hand.
COMMON: dict[str, str] = {
    "hi": "Hindi",
    "en": "English",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
}

#: Names people reasonably type that are not the canonical spelling above.
ALIASES: dict[str, str] = {
    "hinglish": "hi",  # Hindi with English mixed in — still Hindi to Whisper
    "hindustani": "hi",
    "bangla": "bn",
    "panjabi": "pa",
    "punjabi": "pa",
    "tamizh": "ta",
    "marathi": "mr",
}


def _supported_codes() -> set[str]:
    """Every code the installed Whisper build accepts.

    Read from the library rather than duplicated here, so upgrading it does not
    silently leave this list behind.
    """
    try:
        from faster_whisper.tokenizer import _LANGUAGE_CODES

        return set(_LANGUAGE_CODES)
    except Exception:  # noqa: BLE001 — provider not installed, e.g. in tests
        return set(COMMON)


def normalise(value: str | None) -> str | None:
    """Turn whatever was typed into a code Whisper understands.

    ``None`` means "detect it", which is a legitimate answer rather than a
    missing one. Anything unrecognised raises instead of being passed through:
    Whisper treats an unknown language as no language and quietly falls back to
    detection, which is how a box reading "Hindi" produced English-looking
    nonsense for a week.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in ALIASES:
        return ALIASES[lowered]

    by_name = {name.lower(): code for code, name in COMMON.items()}
    if lowered in by_name:
        return by_name[lowered]

    if lowered in _supported_codes():
        return lowered

    known = ", ".join(sorted(COMMON.values()))
    raise AppError(
        f"{text!r} is not a language this can transcribe. Use one of: {known} — "
        "or leave it blank to detect it automatically."
    )


def display_name(code: str | None) -> str:
    """How to show a stored code back to a person."""
    if not code:
        return "Detect automatically"
    return COMMON.get(code, code)
