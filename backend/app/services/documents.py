"""ORM → ``ExportDocument`` mapping.

Lives here rather than in ``services/export`` so exporters stay free of any
database dependency and can be unit-tested with hand-built dataclasses.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Transcript
from app.services.export import ExportDocument, ExportSegment


def to_document(transcript: Transcript) -> ExportDocument:
    video = transcript.video
    return ExportDocument(
        transcript_id=transcript.id,
        video_id=transcript.video_id,
        title=(video.title if video else None) or "Untitled",
        platform=video.platform if video else "unknown",
        source_url=(video.canonical_url if video else "") or "",
        author=video.author if video else None,
        text=transcript.text,
        segments=[
            ExportSegment(
                index=segment.index,
                start=segment.start,
                end=segment.end,
                text=segment.text,
                speaker=segment.speaker,
            )
            for segment in transcript.segments
        ],
        duration_seconds=transcript.duration_seconds
        or (video.duration_seconds if video else None),
        language=transcript.language,
        provider=transcript.provider,
        model=transcript.model,
        word_count=transcript.word_count,
        published_at=video.published_at if video else None,
        created_at=transcript.created_at,
    )


async def load_documents(session: AsyncSession, transcript_ids: list[str]) -> list[ExportDocument]:
    """Load transcripts with segments and video, preserving the requested order."""
    if not transcript_ids:
        return []

    transcripts = (
        (
            await session.execute(
                select(Transcript)
                .options(selectinload(Transcript.segments), selectinload(Transcript.video))
                .where(Transcript.id.in_(transcript_ids))
            )
        )
        .scalars()
        .all()
    )

    by_id = {transcript.id: transcript for transcript in transcripts}
    return [to_document(by_id[tid]) for tid in transcript_ids if tid in by_id]
