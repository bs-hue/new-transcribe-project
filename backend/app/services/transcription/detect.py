"""Decide a video's spoken language once, before it is transcribed.

Why this exists: a hosted provider such as Sarvam only accepts short clips, so
the pipeline cuts long audio into ~30-second chunks and each chunk used to be
sent with "detect the language yourself". Saarika leans hard towards Hindi, so
Indian-accented English was regularly heard as ``hi-IN`` and came back as
English words spelled in Devanagari ("व्हाट इज कस्टमर लाइफटाइम वैल्यू"). Worse,
one video could flip between scripts chunk by chunk.

Deciding once, on the whole file, and then telling the provider explicitly
fixes both: English audio is transcribed as English text, Hindi audio as
Devanagari, and every chunk of a video agrees.

Whisper's language identifier is used because it returns a probability for
every language and runs locally in a second or two on a small model. Hindi
and Urdu are the same spoken language (Hindustani) and Whisper splits the
probability between them, so the two are added together and written as Hindi —
the user wants Devanagari, never Urdu script, for Hindi speech.
"""

from __future__ import annotations

import logging
from pathlib import Path

import anyio

from app.config import Settings

logger = logging.getLogger(__name__)

#: Whisper codes that are all "Hindi" for the purposes of choosing a script.
_HINDUSTANI = ("hi", "ur")

# Core Hindi grammatical markers (postpositions, auxiliary verbs, pronouns, conjunctions)
# Real Hindi sentences almost always contain several of these words.
HINDI_GRAMMATICAL_MARKERS = frozenset({
    "है", "हैं", "का", "के", "की", "में", "से", "को", "ने", "था", "थे", "थी",
    "नहीं", "और", "भी", "तो", "कर", "रहा", "रही", "रहे", "हुआ", "हुए", "हुई",
    "होता", "होते", "होती", "हो", "गया", "गई", "गए", "किया", "करना", "करने",
    "लिए", "दिया", "दिए", "दी", "सकता", "सकते", "सकती", "पर", "कि", "या",
    "वाला", "वाले", "वाली", "मुझे", "तुझे", "उसे", "हमें", "उन्हें", "अपना",
    "अपनी", "अपने", "क्या", "क्यों", "कब", "कहाँ", "कैसे", "किस", "किसने",
    "यहाँ", "वहाँ", "अरे", "हूँ",
})

# High-frequency English functional words transliterated into Devanagari
# When English is transcribed by Hindi STT, these words appear in large numbers.
ENGLISH_DEVANAGARI_WORDS = frozenset({
    "इज", "द", "एंड", "ऑफ", "टू", "दिस", "दैट", "यू", "आई", "आर",
    "फॉर", "इट", "कैन", "सो", "इफ", "व्हाट", "विद", "माय", "ऑन", "वी",
    "नॉट", "बट", "ऑल्सो", "एज", "फ्रॉम", "अबाउट", "बी", "एट", "बाय", "ऑल",
    "योर", "दे", "हैव", "हैज", "वाज", "वर", "डू", "डज", "डिड", "देयर",
    "हू", "व्हिच", "व्हेन", "वेयर", "हाउ", "वन", "लाइक", "जस्ट", "नो", "मैन",
    "दीस", "दोज", "देन", "सम", "एनी", "मोर", "मोस्ट", "अवर", "अप", "आउट",
    "इन", "गो", "कम", "टेल", "सेड",
})


def choose_language(probabilities: dict[str, float]) -> str | None:
    """Pick the language to transcribe in from Whisper's probabilities.

    English vs Hindi is the decision that matters most here. Whisper often
    assigns some probability to Hindi/Urdu when an Indian speaker speaks English,
    because of shared acoustic/accent characteristics.

    Rules:
    - If English is the top detected language, choose "en".
    - If another language (Tamil, Bengali, Marathi, etc.) is the top language
      with higher probability than Hindi and English, choose that language.
    - If Hindi or Urdu is top, but English has strong probability (>= 20% or >= Hindi's
      individual score), choose "en" to prevent the failure mode of English
      words being transliterated into Devanagari script.
    - Only choose "hi" if Hindi is unambiguously dominant (e.g. p_hindi >= 0.35 and
      p_hindi >= 1.5 * p_english).
    """
    if not probabilities:
        return None

    top, p_top = max(probabilities.items(), key=lambda item: item[1])
    p_hindi = sum(probabilities.get(code, 0.0) for code in _HINDUSTANI)
    p_english = probabilities.get("en", 0.0)

    # Clearly a third language (e.g. Tamil, Marathi, Bengali)
    if top not in (*_HINDUSTANI, "en") and p_top > max(p_hindi, p_english):
        return top

    # If English is the single top language, trust it
    if top == "en":
        return "en"

    # If English has significant confidence or beats individual Hindi probability,
    # prefer English to avoid Devanagari transliteration of Indian-accented English
    p_hi_solo = probabilities.get("hi", 0.0)
    if p_english >= 0.20 or p_english >= p_hi_solo:
        return "en"

    # Only pick Hindi if Hindustani is decisively dominant
    if p_hindi >= 0.35 and p_hindi >= 1.5 * p_english:
        return "hi"

    return "en"


def is_devanagari_transliterated_english(text: str) -> bool:
    """Detect if a transcript in Devanagari script is actually transliterated English speech.

    When speech-to-text models (such as Sarvam or Whisper) are told or auto-detect 'hi',
    English speech is phonetically spelled in Devanagari (e.g. 'व्हाट इज कस्टमर लाइफटाइम वैल्यू').
    This function analyzes the density of common English functional words versus Hindi
    grammatical markers to reliably detect this failure mode.
    """
    import re

    tokens = re.findall(r"[\u0900-\u097F]+", text)
    if len(tokens) < 5:
        return False
    h_hits = sum(1 for w in tokens if w in HINDI_GRAMMATICAL_MARKERS)
    e_hits = sum(1 for w in tokens if w in ENGLISH_DEVANAGARI_WORDS)
    return (e_hits >= 3 and e_hits > h_hits) or (e_hits >= 2 and h_hits <= 1)


def _detection_model_name(settings: Settings) -> str:
    # Use a small fast model for language detection.
    # Never load huge models like large-v3-turbo just for language identification.
    return settings.language_detection_model or "tiny"


def _detect_sync(audio_path: Path, settings: Settings) -> str | None:
    from faster_whisper.audio import decode_audio

    from app.services.transcription.faster_whisper import (
        _load_model,
        resolve_compute_type,
        resolve_cpu_threads,
        resolve_device,
    )

    device = resolve_device(settings.faster_whisper_device)
    model = _load_model(
        _detection_model_name(settings),
        device,
        resolve_compute_type(settings.faster_whisper_compute_type, device),
        resolve_cpu_threads(settings.faster_whisper_cpu_threads, settings.worker_concurrency),
    )
    audio = decode_audio(str(audio_path), sampling_rate=16000)
    _, _, all_probs = model.detect_language(
        audio=audio,
        vad_filter=True,
        language_detection_segments=max(1, settings.faster_whisper_language_detection_segments),
    )
    probabilities = {code: float(p) for code, p in all_probs}
    chosen = choose_language(probabilities)
    logger.info(
        "Detected spoken language %r for %s (en=%.0f%%, hi+ur=%.0f%%)",
        chosen,
        audio_path.name,
        100 * probabilities.get("en", 0.0),
        100 * sum(probabilities.get(code, 0.0) for code in _HINDUSTANI),
    )
    return chosen


async def detect_language(audio_path: Path, settings: Settings) -> str | None:
    """The language to transcribe ``audio_path`` in, or ``None`` if unsure.

    Never fails a job: if detection cannot run (model not downloadable, no
    speech found), the provider falls back to detecting on its own as before.
    """
    try:
        return await anyio.to_thread.run_sync(_detect_sync, audio_path, settings)
    except Exception as exc:  # noqa: BLE001 — detection is an improvement, not a requirement
        logger.warning("Language detection failed for %s (%s); provider will detect", audio_path.name, exc)
        return None
