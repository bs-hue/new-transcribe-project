"""API request and response models.

Kept in one module because they are the contract, and reading a contract in one
place is easier than chasing it across eight files.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- shared ------------------------------------------------------------------


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None


class Page(BaseModel):
    total: int
    limit: int
    offset: int


# --- auth --------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    #: None means the account has signed up and is waiting to be let in.
    approved_at: datetime | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserCreateRequest(BaseModel):
    email: str
    password: Annotated[str, Field(min_length=8, max_length=72)]
    full_name: str | None = None
    role: Literal["admin", "member"] = "member"


class RegisterRequest(BaseModel):
    """Public sign-up.

    Note the absence of a role field. This endpoint is unauthenticated, so
    accepting one would let anybody make themselves an administrator.
    """

    email: str
    password: Annotated[str, Field(min_length=8, max_length=72)]
    full_name: str | None = None


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None
    password: Annotated[str, Field(min_length=8, max_length=72)] | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: Annotated[str, Field(min_length=8, max_length=72)]


# --- submission --------------------------------------------------------------


class URLListRequest(BaseModel):
    """A pasted block of URLs.

    Accepts a JSON array or a single newline/comma-separated string, because the
    UI's textarea and API clients naturally produce different shapes and neither
    should have to care.
    """

    urls: list[str] = Field(min_length=1)
    language: str | None = Field(
        default=None,
        max_length=16,
        description="ISO-639-1 hint, e.g. 'en'. Omit to auto-detect.",
    )

    @field_validator("urls", mode="before")
    @classmethod
    def _accept_text_block(cls, value: object) -> object:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        expanded: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            expanded.extend(part.strip() for part in item.replace(",", "\n").splitlines())
        return [item for item in expanded if item]


class SubmissionOutcomeResponse(BaseModel):
    url: str
    accepted: bool
    job_id: str | None = None
    video_id: str | None = None
    platform: str | None = None
    canonical_url: str | None = None
    duplicate_of_existing_video: bool = False
    error_code: str | None = None
    error_message: str | None = None


class SubmissionResponse(BaseModel):
    batch_id: str
    accepted_count: int
    rejected_count: int
    results: list[SubmissionOutcomeResponse]


class PreviewResponse(BaseModel):
    url: str
    valid: bool
    platform: str | None = None
    platform_display_name: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    author: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    estimated_size_bytes: int | None = None
    within_limits: bool = True
    limit_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    already_transcribed: bool = False
    error_code: str | None = None
    error_message: str | None = None


class PreviewListResponse(BaseModel):
    results: list[PreviewResponse]


# --- videos, jobs, transcripts ----------------------------------------------


class VideoSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: str
    title: str | None = None
    author: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    canonical_url: str
    source_url: str
    published_at: datetime | None = None
    created_at: datetime


class VideoDetail(VideoSummary):
    description: str | None = None
    author_url: str | None = None
    estimated_size_bytes: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    transcript: TranscriptDetail | None = None
    transcript_count: int = 0
    latest_job: JobSummary | None = None


class VideoListResponse(Page):
    items: list[VideoSummary]


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    batch_id: str | None = None
    submitted_by: str | None = None
    status: str
    stage: str
    progress: float
    attempts: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobDetail(JobSummary):
    video: VideoSummary | None = None
    transcript_id: str | None = None
    submitted_by_name: str | None = None


class JobListResponse(Page):
    items: list[JobDetail]


class BatchStatusResponse(BaseModel):
    batch_id: str
    total: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    jobs: list[JobDetail]

    @property
    def is_finished(self) -> bool:
        return self.queued == 0 and self.running == 0


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    start: float
    end: float
    text: str
    speaker: str | None = None


class TranscriptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    language: str | None = None
    provider: str
    model: str | None = None
    word_count: int
    duration_seconds: float | None = None
    created_at: datetime


class TranscriptDetail(TranscriptSummary):
    text: str
    segments: list[SegmentResponse] = Field(default_factory=list)
    video: VideoSummary | None = None


class TranscriptListResponse(Page):
    items: list[TranscriptSummary]


class RecentTranscript(TranscriptSummary):
    video: VideoSummary | None = None


# --- dashboard ---------------------------------------------------------------


class DashboardResponse(BaseModel):
    """Everything the landing page shows, in one request."""

    in_progress: int
    finished_today: int
    needs_attention: int
    total_research: int
    active_jobs: list[JobDetail]
    recent_transcripts: list[RecentTranscript]


# --- settings ----------------------------------------------------------------


class SettingDefinition(BaseModel):
    """Describes a changeable setting, so the UI renders it without hardcoding."""

    key: str
    label: str
    help: str
    kind: Literal["int", "str"]
    minimum: int | None = None
    maximum: int | None = None
    choices: list[str] | None = None
    choice_labels: dict[str, str] | None = None
    applies_to: str
    #: What the number means, so the UI can show "2 hours" beside "7200".
    unit: Literal["seconds", "bytes", "count"] | None = None


class SettingsResponse(BaseModel):
    values: dict[str, object]
    definitions: list[SettingDefinition]
    transcription_provider: str
    cookies_configured: bool
    worker_concurrency: int
    environment: str


class SettingsUpdateRequest(BaseModel):
    values: dict[str, object] = Field(min_length=1)


class SystemCheckResult(BaseModel):
    name: str
    ok: bool
    warning_only: bool
    detail: str
    fix: str | None = None


class SystemCheckResponse(BaseModel):
    ok: bool
    results: list[SystemCheckResult]
    #: The same report the command line prints, for copying into a support message.
    text: str


# --- search ------------------------------------------------------------------


class SearchResultItem(BaseModel):
    transcript_id: str
    video_id: str
    snippet: str
    rank: float
    title: str | None = None
    author: str | None = None
    platform: str | None = None
    thumbnail_url: str | None = None
    canonical_url: str | None = None
    duration_seconds: float | None = None
    word_count: int = 0
    created_at: datetime | None = None


class SearchResponse(Page):
    query: str
    items: list[SearchResultItem]


# --- export ------------------------------------------------------------------


class BulkExportRequest(BaseModel):
    format: str
    transcript_ids: list[str] = Field(default_factory=list)
    video_ids: list[str] = Field(default_factory=list)
    #: Export everything matching a search query instead of listing ids.
    query: str | None = None
    limit: Annotated[int, Field(ge=1, le=500)] = 200
    #: One file holding every transcript, rather than a ZIP of separate files.
    #: Subtitle formats ignore this — see ``Exporter.render_many``.
    combine: bool = True


# --- meta --------------------------------------------------------------------


class PlatformInfo(BaseModel):
    name: str
    display_name: str


class ExportFormatInfo(BaseModel):
    format: str
    display_name: str
    extension: str
    content_type: str
    requires_segments: bool
    combinable: bool = False


class LimitsInfo(BaseModel):
    max_video_duration_seconds: int
    max_video_filesize_bytes: int
    max_urls_per_request: int


class MetaResponse(BaseModel):
    app_name: str
    version: str
    #: Which commit is actually running. "unknown" outside a built image.
    commit: str = "unknown"
    platforms: list[PlatformInfo]
    export_formats: list[ExportFormatInfo]
    limits: LimitsInfo
    transcription_provider: str
    transcription_ready: bool
    transcription_error: str | None = None
    #: closed | approval | open — lets the sign-in page decide whether to offer
    #: a "create an account" link rather than hardcoding it.
    registration_mode: str = "closed"


class HealthResponse(BaseModel):
    status: str
    database: bool
    worker_enabled: bool
    queue_depth: int


# Resolve the forward references used above.
VideoDetail.model_rebuild()
JobDetail.model_rebuild()
