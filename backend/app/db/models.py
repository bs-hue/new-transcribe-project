"""Database models.

Deliberately small. The shape that matters for later versions:

    Video ──1:N── Job
      └──1:N── Transcript ──1:N── TranscriptSegment

``Video.raw_metadata`` keeps the untouched provider payload so V2/V3 can mine
fields V1 never modelled (view counts, hashtags, upload date) without
re-downloading anything. ``Transcript`` is versioned rather than overwritten so a
better model can be run later without destroying prior research.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Declarative base. JSON is portable across SQLite and Postgres."""

    type_annotation_map = {dict: JSON}


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}


class JobStage(enum.StrEnum):
    """Where in the pipeline a job is. Ordered as the pipeline runs them."""

    PENDING = "pending"
    FETCHING_METADATA = "fetching_metadata"
    CHECKING_LIMITS = "checking_limits"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    STORING = "storing"
    DONE = "done"


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class User(Base):
    """A person who can sign in.

    Small on purpose: an internal agency tool needs "who are you" and "may you
    manage other accounts", not a permissions matrix. Roles can grow into one
    later without moving any data.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), default=None)
    # bcrypt hash. The plaintext password is never stored or logged.
    hashed_password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.MEMBER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: When an administrator let this account in. ``None`` means "signed up and
    #: waiting". Deliberately separate from ``is_active``: that is the ban
    #: switch, and an admin needs to tell a new applicant apart from someone
    #: they have suspended. Accounts an admin creates are approved on creation.
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value


class AppSetting(Base):
    """A runtime-changeable setting, overriding the environment default.

    Only the handful of settings an administrator should be able to change from
    the Settings screen live here — limits, language, model size. Anything
    security- or infrastructure-related (the signing key, the database URL)
    stays environment-only and is deliberately not reachable from the UI.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: Stored as text and coerced on read, so one table serves every type.
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    updated_by: Mapped[str | None] = mapped_column(String(32), default=None)


class Video(Base):
    """A piece of source content. One row per unique platform video."""

    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("platform", "platform_video_id", name="uq_video_platform_id"),
        Index("ix_videos_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)

    platform: Mapped[str] = mapped_column(String(32), index=True)
    platform_video_id: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)

    # Populated by the metadata stage, before anything is downloaded.
    title: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    author: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    author_url: Mapped[str | None] = mapped_column(Text, default=None)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    estimated_size_bytes: Mapped[int | None] = mapped_column(Integer, default=None)
    view_count: Mapped[int | None] = mapped_column(Integer, default=None)
    like_count: Mapped[int | None] = mapped_column(Integer, default=None)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    jobs: Mapped[list[Job]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="Job.created_at"
    )
    transcripts: Mapped[list[Transcript]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="Transcript.created_at.desc()",
    )

    @property
    def latest_transcript(self) -> Transcript | None:
        return self.transcripts[0] if self.transcripts else None


class Job(Base):
    """One run of the pipeline for one video. Also the queue row."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_batch_id", "batch_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)

    # Groups the jobs created by a single multi-URL submission, so the UI can
    # show "batch 7 of 12 complete" without the client tracking ids itself.
    batch_id: Mapped[str | None] = mapped_column(String(32), default=None)

    # Who submitted it. SET NULL rather than CASCADE: removing someone from the
    # team must not delete the research they collected.
    submitted_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )

    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED.value, index=True)
    stage: Mapped[str] = mapped_column(String(32), default=JobStage.PENDING.value)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 – 1.0

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    # Per-job override; falls back to the configured default when null.
    language: Mapped[str | None] = mapped_column(String(16), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    video: Mapped[Video] = relationship(back_populates="jobs", lazy="joined")


class Transcript(Base):
    """A stored transcript. Versioned per video, newest first."""

    __tablename__ = "transcripts"
    __table_args__ = (Index("ix_transcripts_video_created", "video_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str | None] = mapped_column(String(32), default=None)

    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16), default=None)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64), default=None)

    word_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    video: Mapped[Video] = relationship(back_populates="transcripts")
    segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.index",
    )


class TranscriptSegment(Base):
    """A timed chunk of a transcript.

    Segments are what make SRT/VTT export real rather than approximated, and what
    a future "jump to this quote in the video" feature needs.
    """

    __tablename__ = "transcript_segments"
    __table_args__ = (Index("ix_segments_transcript_index", "transcript_id", "index"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    transcript_id: Mapped[str] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )

    index: Mapped[int] = mapped_column(Integer)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    speaker: Mapped[str | None] = mapped_column(String(64), default=None)

    transcript: Mapped[Transcript] = relationship(back_populates="segments")
