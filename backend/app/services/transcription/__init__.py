"""Transcription provider registry."""

from __future__ import annotations

from collections.abc import Callable

from app.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.services.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegmentData,
    merge_results,
)
from app.services.transcription.faster_whisper import FasterWhisperProvider
from app.services.transcription.sarvam import SarvamProvider
from app.services.transcription.stub import StubProvider

#: Providers that never send audio anywhere. The default is one of these, and
#: the system check reports loudly when the configured provider is not.
LOCAL_PROVIDERS = frozenset({FasterWhisperProvider.name, StubProvider.name})

_FACTORIES: dict[str, Callable[[Settings], TranscriptionProvider]] = {
    FasterWhisperProvider.name: FasterWhisperProvider,
    SarvamProvider.name: SarvamProvider,
    StubProvider.name: lambda _settings: StubProvider(),
}

#: Providers a person may choose from the Settings screen. `stub` exists only
#: for tests and would produce nonsense in the app.
SELECTABLE_PROVIDERS = (FasterWhisperProvider.name, SarvamProvider.name)


def available_providers() -> list[str]:
    return sorted(_FACTORIES)


def get_transcription_provider(settings: Settings | None = None) -> TranscriptionProvider:
    """The configured provider, instantiated once per process."""
    settings = settings or get_settings()
    name = settings.transcription_provider.strip().lower()

    factory = _FACTORIES.get(name)
    if factory is None:
        raise ConfigurationError(
            f"Unknown TRANSCRIPTION_PROVIDER {name!r}. "
            f"Available: {', '.join(available_providers())}."
        )

    # Deliberately NOT cached by name. Instances hold the settings they were
    # built with, so a cached one silently ignores every later change — which is
    # how a model chosen on the Settings screen went unused for a whole day.
    # Construction is trivial; the expensive part, loading the speech model, is
    # cached separately and keyed on the values that actually matter.
    return factory(settings)


def reset_provider_cache() -> None:
    """Drop the loaded speech model. Used by tests that change configuration."""
    from app.services.transcription.faster_whisper import _load_model

    _load_model.cache_clear()


__all__ = [
    "LOCAL_PROVIDERS",
    "SELECTABLE_PROVIDERS",
    "TranscriptSegmentData",
    "TranscriptionProvider",
    "TranscriptionResult",
    "available_providers",
    "get_transcription_provider",
    "merge_results",
    "reset_provider_cache",
]
