"""Typed application configuration, loaded from the environment (12-factor).

Every setting the application has is declared here exactly once, with a type and
a default. Two consequences worth knowing:

1. A malformed value (``MAX_ATTEMPTS=lots``) fails at **startup**, loudly, rather
   than surfacing as a strange bug hours later.
2. Production has guard rails: the app refuses to boot with the development
   secret, insecure cookies, or wildcard CORS. A deployment mistake becomes a
   crash on line one instead of a silent security hole.

Reference: docs/TECHNICAL_ARCHITECTURE.md §9
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
QueueBackend = Literal["background", "arq"]
ProgressBackend = Literal["polling", "sse", "ws"]
StorageBackend = Literal["local", "s3"]
WhisperDevice = Literal["auto", "cpu", "cuda"]
RefreshTransport = Literal["cookie", "body"]

#: The placeholder shipped in ``.env.example``. Rejected in production by the
#: validator at the bottom of this module.
#: noqa justification: the linter flags string literals assigned to secret-looking
#: names. This one is deliberately public — its whole purpose is to be recognised
#: and refused.
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"  # noqa: S105


class Settings(BaseSettings):
    """All application settings. Instances are immutable and cached per process."""

    model_config = SettingsConfigDict(
        # The backend runs from ``backend/`` but ``.env`` lives at the repo root,
        # so both locations are checked. First match wins.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # ── Application ───────────────────────────────────────────────────────
    app_env: AppEnv = "development"
    app_name: str = "Bulk Transcript Agent"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    log_level: LogLevel = "INFO"

    #: Comma-separated list of allowed browser origins. Read via
    #: :attr:`cors_origin_list` rather than parsed here, because environment
    #: variables are plain strings and a comma-separated list is friendlier to
    #: hand-edit than JSON.
    cors_origins: str = "http://localhost:5173"

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/app.db"
    database_echo: bool = False

    # ── Authentication ────────────────────────────────────────────────────
    jwt_secret: SecretStr = SecretStr(DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = Field(default=900, ge=60)
    refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=3600)
    refresh_token_transport: RefreshTransport = "cookie"
    cookie_secure: bool = False
    cookie_domain: str | None = None
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: SecretStr | None = None

    # ── Transcription ─────────────────────────────────────────────────────
    whisper_model: str = "small"
    whisper_device: WhisperDevice = "auto"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = Field(default=0, ge=0)
    whisper_vad_enabled: bool = True
    max_concurrent_transcriptions: int = Field(default=1, ge=1, le=8)
    max_urls_per_batch: int = Field(default=25, ge=1, le=500)
    max_video_duration_seconds: int = Field(default=7200, ge=60)

    # ── Reliability ───────────────────────────────────────────────────────
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_base_seconds: int = Field(default=30, ge=1)
    lease_ttl_seconds: int = Field(default=120, ge=30)
    lease_reap_interval_seconds: int = Field(default=60, ge=10)
    download_timeout_seconds: int = Field(default=900, ge=30)
    extract_timeout_seconds: int = Field(default=300, ge=30)
    transcribe_timeout_seconds: int = Field(default=5400, ge=60)
    summarize_timeout_seconds: int = Field(default=120, ge=10)

    # ── Disk ──────────────────────────────────────────────────────────────
    media_temp_path: str = "./media"
    min_free_disk_mb: int = Field(default=2048, ge=0)

    # ── Queue & progress ──────────────────────────────────────────────────
    queue_backend: QueueBackend = "background"
    progress_backend: ProgressBackend = "polling"
    progress_history_enabled: bool = False

    # ── AI summaries ──────────────────────────────────────────────────────
    llm_enabled: bool = False
    llm_provider: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None

    # ── Storage ───────────────────────────────────────────────────────────
    storage_backend: StorageBackend = "local"
    storage_path: str = "./storage"

    # ── Derived values ────────────────────────────────────────────────────

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def docs_enabled(self) -> bool:
        """Interactive API docs are development-only (API_SPECIFICATION §10)."""
        return self.app_env != "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def summarize_available(self) -> bool:
        """Whether the UI should offer summaries at all (FR-S1/S3)."""
        return self.llm_enabled and self.llm_api_key is not None

    # ── Production guard rails ────────────────────────────────────────────

    @model_validator(mode="after")
    def _reject_insecure_production(self) -> Settings:
        """Refuse to start a production process that is misconfigured.

        These are not style preferences — each one is a live vulnerability if it
        reaches production, and each is easy to leave behind by accident when
        copying a development ``.env``.
        """
        if self.app_env != "production":
            return self

        problems: list[str] = []

        if self.jwt_secret.get_secret_value() == DEV_JWT_SECRET:
            problems.append(
                "JWT_SECRET is still the development placeholder. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true in production (HTTPS-only cookies).")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list explicit origins in production, not '*'.")
        if self.database_url.startswith("sqlite"):
            problems.append(
                "DATABASE_URL points at SQLite. Production requires PostgreSQL "
                "(SQLite's single-writer lock would serialise the API against the worker)."
            )

        if problems:
            raise ValueError(
                "Refusing to start with an insecure production configuration:\n  - "
                + "\n  - ".join(problems)
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, read from the environment once.

    Cached so that configuration is loaded a single time and cannot drift
    mid-process. Tests clear the cache via ``get_settings.cache_clear()``.
    """
    return Settings()
