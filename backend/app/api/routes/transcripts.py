"""Browse, read and export stored transcripts."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.core.errors import NotFoundError
from app.db.models import Transcript, Video
from app.schemas import (
    TranscriptDetail,
    TranscriptListResponse,
    TranscriptSummary,
    VideoSummary,
)
from app.services.documents import to_document
from app.services.export import export_one

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


def _content_disposition(filename: str) -> str:
    """RFC 5987 disposition so non-ASCII titles survive the round trip."""
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "transcript"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.get("", response_model=TranscriptListResponse)
async def list_transcripts(
    session: DbSession,
    platform: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TranscriptListResponse:
    statement = select(Transcript)
    count_statement = select(func.count(Transcript.id))

    if platform:
        statement = statement.join(Video, Video.id == Transcript.video_id).where(
            Video.platform == platform
        )
        count_statement = count_statement.join(
            Video, Video.id == Transcript.video_id
        ).where(Video.platform == platform)

    total = (await session.execute(count_statement)).scalar_one()
    rows = (
        (
            await session.execute(
                statement.order_by(Transcript.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )

    return TranscriptListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[TranscriptSummary.model_validate(row) for row in rows],
    )


async def _load(session, transcript_id: str) -> Transcript:  # noqa: ANN001
    transcript = (
        await session.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments), selectinload(Transcript.video))
            .where(Transcript.id == transcript_id)
        )
    ).scalar_one_or_none()
    if transcript is None:
        raise NotFoundError(f"No transcript with id {transcript_id}.")
    return transcript


@router.get("/{transcript_id}", response_model=TranscriptDetail)
async def get_transcript(transcript_id: str, session: DbSession) -> TranscriptDetail:
    transcript = await _load(session, transcript_id)
    detail = TranscriptDetail.model_validate(transcript)
    detail.video = (
        VideoSummary.model_validate(transcript.video) if transcript.video else None
    )
    return detail


@router.get("/{transcript_id}/export")
async def export_transcript(
    transcript_id: str,
    session: DbSession,
    format: str = Query(description="txt | docx | md | xlsx | json | srt | vtt"),
) -> Response:
    """Download one transcript in the requested format."""
    transcript = await _load(session, transcript_id)
    content, filename, content_type = export_one(to_document(transcript), format)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": _content_disposition(filename)},
    )
