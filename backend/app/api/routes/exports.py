"""Bulk export.

Select transcripts by id, by video, or by search query, and get one file back:
a combined workbook or JSON document where that makes sense, a ZIP otherwise.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession
from app.core.errors import ExportFormatError, NotFoundError
from app.db.models import Transcript
from app.schemas import BulkExportRequest
from app.services.documents import load_documents
from app.services.export import export_many
from app.services.search import get_search_backend

router = APIRouter(prefix="/exports", tags=["exports"])


async def _resolve_transcript_ids(
    session: DbSession, payload: BulkExportRequest, settings: AppSettings
) -> list[str]:
    """Work out which transcripts the request refers to.

    The three selectors compose: ids, videos, and a query can be combined, and
    the result is de-duplicated while preserving first-seen order.
    """
    ids: list[str] = list(payload.transcript_ids)

    if payload.video_ids:
        # Latest transcript per requested video.
        rows = (
            await session.execute(
                select(Transcript.id, Transcript.video_id)
                .where(Transcript.video_id.in_(payload.video_ids))
                .order_by(Transcript.created_at.desc())
            )
        ).all()
        seen_videos: set[str] = set()
        for transcript_id, video_id in rows:
            if video_id not in seen_videos:
                seen_videos.add(video_id)
                ids.append(transcript_id)

    if payload.query:
        results = await get_search_backend(settings).search(
            session, payload.query, limit=payload.limit, offset=0
        )
        ids.extend(hit.transcript_id for hit in results.hits)

    deduped: list[str] = []
    seen: set[str] = set()
    for transcript_id in ids:
        if transcript_id not in seen:
            seen.add(transcript_id)
            deduped.append(transcript_id)
    return deduped[: payload.limit]


@router.post("")
async def bulk_export(
    payload: BulkExportRequest, session: DbSession, settings: AppSettings
) -> Response:
    if not (payload.transcript_ids or payload.video_ids or payload.query):
        raise ExportFormatError(
            "Specify transcript_ids, video_ids, or a query to export."
        )

    transcript_ids = await _resolve_transcript_ids(session, payload, settings)
    if not transcript_ids:
        raise NotFoundError("No transcripts matched that selection.")

    documents = await load_documents(session, transcript_ids)
    if not documents:
        raise NotFoundError("None of the requested transcripts exist.")

    content, filename, content_type = export_many(
        documents, payload.format, combine=payload.combine
    )

    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "export"
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )
