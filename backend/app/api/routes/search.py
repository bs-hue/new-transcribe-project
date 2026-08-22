"""Search across every stored transcript."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession
from app.db.models import Transcript, Video
from app.schemas import SearchResponse, SearchResultItem
from app.services.search import SearchFilters, get_search_backend

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    session: DbSession,
    settings: AppSettings,
    q: str = Query(default="", min_length=0, description="Words to look for across all transcripts"),
    platform: str | None = None,
    author: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    backend = get_search_backend(settings)
    results = await backend.search(
        session,
        q,
        filters=SearchFilters(
            platform=platform,
            author=author,
            created_after=created_after,
            created_before=created_before,
        ),
        limit=limit,
        offset=offset,
    )

    if not results.hits:
        return SearchResponse(query=q, total=results.total, limit=limit, offset=offset, items=[])

    # One extra query hydrates every hit; the search backend deliberately returns
    # only ids so it never has to know what a response looks like.
    rows = (
        await session.execute(
            select(Transcript, Video)
            .join(Video, Video.id == Transcript.video_id)
            .where(Transcript.id.in_([hit.transcript_id for hit in results.hits]))
        )
    ).all()
    by_id = {transcript.id: (transcript, video) for transcript, video in rows}

    items = []
    for hit in results.hits:
        record = by_id.get(hit.transcript_id)
        if record is None:  # index entry outlived its transcript
            continue
        transcript, video = record
        items.append(
            SearchResultItem(
                transcript_id=transcript.id,
                video_id=video.id,
                snippet=hit.snippet,
                rank=hit.rank,
                title=video.title,
                author=video.author,
                platform=video.platform,
                thumbnail_url=video.thumbnail_url,
                canonical_url=video.canonical_url,
                duration_seconds=transcript.duration_seconds or video.duration_seconds,
                word_count=transcript.word_count,
                created_at=transcript.created_at,
            )
        )

    return SearchResponse(
        query=q, total=results.total, limit=limit, offset=offset, items=items
    )
