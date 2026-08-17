"""Application settings.

Every knob is environment-driven so the same image runs in dev and production
with nothing but the environment changed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repo root: backend/app/config.py -> backend/app -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---
    environment: str = "development"
    log_level: str = "INFO"
    app_name: str = "Instagram & YouTube Transcription Agent"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # --- API ---
    # NoDecode stops pydantic-settings treating this as JSON in the environment,
    # so operators can write the obvious `CORS_ORIGINS=a,b` instead of a JSON array.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- Authentication (JWT) ---
    # The default secret is refused outside development: an unchanged signing key
    # means anyone can mint a valid token for themselves.
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720  # 12 hours â€” one working day
    # Creates the first admin at startup when the user table is empty, so a fresh
    # deployment is usable without a shell.
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    # Who may create an account.
    #
    # * ``closed``   â€” nobody. An administrator adds accounts. The default,
    #   because a tool that quietly accepts strangers is worse than one that
    #   makes you turn that on deliberately.
    # * ``approval`` â€” anyone may apply, and waits for an administrator. Sign-up
    #   costs nothing until approved, which is what keeps a public sign-up page
    #   from spending your transcription budget.
    # * ``open``     â€” anyone may sign up and use it immediately. Only sensible
    #   once per-account limits exist, since transcription costs real money.
    registration_mode: Literal["closed", "approval", "open"] = "closed"

    #: The commit this image was built from, stamped in by the build.
    #:
    #: A deployment stays on the commit it last built, so "is my fix live?" is a
    #: question that has cost this project days. Reported by /api/meta and by
    #: `doctor`, so it can be answered from a browser in five seconds rather
    #: than inferred from how the app behaves.
    build_commit: str = "unknown"

    # --- Transcription ---
    # `faster_whisper` transcribes on this machine: free, private, bounded by
    # the hardware. `sarvam` sends the audio to Sarvam AI, which is built for
    # Indian languages and far faster, but is a third party and costs money
    # beyond its free allowance. Local remains the default; choosing otherwise
    # is a deliberate act with a documented trade-off.
    transcription_provider: str = "faster_whisper"
    transcription_language: str | None = None
    # `small` rather than `base`: on English `base` is adequate, but on Hindi and
    # other Indic languages it is close to unusable â€” roughly half the words come
    # back wrong. `small` is the smallest model that produces work anyone would
    # actually use for those languages, and is the honest default for an agency
    # researching Indian content.
    faster_whisper_model: str = "small"
    faster_whisper_device: str = "auto"
    # "default" means float32 on CPU, which is two to four times slower than int8
    # for a barely measurable accuracy difference. Resolved at load time â€” see
    # services/transcription/faster_whisper.py.
    faster_whisper_compute_type: str = "default"
    #: 0 lets the provider divide the machine's cores between the workers.
    faster_whisper_cpu_threads: int = 0
    #: Higher searches more alternatives: slower, slightly more accurate.
    faster_whisper_beam_size: int = 5
    #: Words the model is told to expect â€” brand names, product names, jargon.
    #: Whisper guesses from sound alone, so an unfamiliar word becomes whatever
    #: it sounds nearest to. Naming them in advance fixes exactly that.
    transcription_vocabulary: str | None = None
    #: Discourages the model from repeating itself. 1.0 is off; a little above
    #: stops the "yaa yaa yaa yaa" loops that Whisper falls into on Indic audio.
    faster_whisper_repetition_penalty: float = 1.1
    #: Transcribe several chunks of one video at once instead of one after the
    #: other. Roughly two to four times faster on a CPU for the same output.
    #: 1 disables it and uses the plain sequential path.
    faster_whisper_batch_size: int = 8
    # --- Sarvam AI (only used when transcription_provider = "sarvam") ---
    sarvam_api_key: str | None = None
    sarvam_model: str = "saarika:v2.5"
    #: Longest clip sent in one request. Longer audio is split by the pipeline
    #: and stitched back together, so this is a request limit, not a video one.
    sarvam_max_audio_seconds: int = 30
    sarvam_timeout_seconds: float = 120.0

    #: How many windows of audio automatic detection listens to before deciding.
    #: The library's default is one â€” a single 30-second window â€” so a Reel that
    #: opens on music or an English word gets the whole video's language wrong.
    #: Sampling several and taking the confident answer is far steadier.
    faster_whisper_language_detection_segments: int = 4

    # --- Limits ---
    max_video_duration_seconds: int = 7200
    max_video_filesize_bytes: int = 2 * 1024 * 1024 * 1024
    max_urls_per_request: int = 50

    # --- Media ---
    work_dir: Path = Path("./data/work")
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    keep_media: bool = False
    youtube_proxy: Optional[str] = None
    webshare_token: Optional[str] = None

    # --- Worker ---
    worker_enabled: bool = True
    worker_concurrency: int = 2
    worker_poll_interval_seconds: float = 2.0
    job_max_attempts: int = 3

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept both a comma-separated string and a real list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value



    @field_validator(
        "transcription_language",
        "bootstrap_admin_email",
        "bootstrap_admin_password",
        mode="before",
    )
    @classmethod
    def _empty_str_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("transcription_language", mode="after")
    @classmethod
    def _language_as_a_code(cls, value: str | None) -> str | None:
        """Accept "Hindi" here as well as in the app.

        Whisper needs "hi", and treats anything it does not recognise as no
        language at all â€” falling back to detection without a word of complaint.
        Writing the language's own name into the settings file is the obvious
        thing to do, so it has to work rather than silently do nothing.
        """
        # Imported here: the language table belongs to the transcription
        # package, which imports config, and this avoids the cycle.
        from app.services.transcription.languages import normalise

        try:
            return normalise(value)
        except Exception:  # noqa: BLE001 â€” a bad value must not stop startup
            return None

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolved_work_dir(self) -> Path:
        """Absolute work directory, created on demand."""
        path = self.work_dir
        if not path.is_absolute():
            path = (_REPO_ROOT / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
