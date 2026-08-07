"""Transcript search.

One interface, two implementations. SQLite gets real ranked full-text search via
FTS5; anything else gets a portable ``LIKE`` backend. Callers never learn which
one they got, which is what lets V3 swap in Postgres ``tsvector`` or a vector
store without touching a single call site.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[\w'-]+", re.UNICODE)
_SNIPPET_RADIUS = 120


@dataclass(frozen=True, slots=True)
class SearchFilters:
    platform: str | None = None
    author: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    transcript_id: str
    video_id: str
    snippet: str
    rank: float


@dataclass(frozen=True, slots=True)
class SearchResults:
    hits: list[SearchHit]
    total: int


def _tokenise(query: str) -> list[str]:
    """Extract plain word tokens.

    User input never reaches the FTS parser as syntax — every token is re-quoted
    as a literal phrase. That keeps a stray ``"`` or ``AND`` from producing a
    query syntax error instead of results.
    """
    return _WORD.findall(query or "")


def _build_snippet(body: str, tokens: list[str]) -> str:
    """A readable excerpt centred on the first matching term."""
    if not body:
        return ""
    lowered = body.lower()
    position = -1
    for token in tokens:
        position = lowered.find(token.lower())
        if position != -1:
            break
    if position == -1:
        head = body[: _SNIPPET_RADIUS * 2].strip()
        return head + ("…" if len(body) > _SNIPPET_RADIUS * 2 else "")

    start = max(0, position - _SNIPPET_RADIUS)
    end = min(len(body), position + _SNIPPET_RADIUS)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{body[start:end].strip()}{suffix}"


def _filter_clause(filters: SearchFilters, params: dict) -> str:
    clauses = []
    if filters.platform:
        clauses.append("v.platform = :platform")
        params["platform"] = filters.platform
    if filters.author:
        clauses.append("LOWER(v.author) LIKE :author")
        params["author"] = f"%{filters.author.lower()}%"
    if filters.created_after:
        clauses.append("t.created_at >= :created_after")
        params["created_after"] = filters.created_after
    if filters.created_before:
        clauses.append("t.created_at <= :created_before")
        params["created_before"] = filters.created_before
    return (" AND " + " AND ".join(clauses)) if clauses else ""


class SearchBackend(ABC):
    """Keeps a searchable view of transcripts and answers queries over it."""

    name: str

    async def initialise(self, engine: AsyncEngine) -> None:
        """Create any backing structures. Must be idempotent."""
        return None

    async def index(
        self,
        session: AsyncSession,
        *,
        transcript_id: str,
        video_id: str,
        title: str,
        author: str,
        body: str,
    ) -> None:
        return None

    async def remove(self, session: AsyncSession, transcript_id: str) -> None:
        return None

    @abstractmethod
    async def search(
        self,
        session: AsyncSession,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResults: ...


class SqliteFtsBackend(SearchBackend):
    """FTS5 virtual table, kept in sync on write."""

    name = "sqlite_fts5"

    _CREATE = """
        CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
            transcript_id UNINDEXED,
            video_id UNINDEXED,
            title,
            author,
            body,
            tokenize = 'porter unicode61'
        )
    """

    def __init__(self) -> None:
        self._available = True

    async def initialise(self, engine: AsyncEngine) -> None:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(self._CREATE))
            logger.info("Search backend: SQLite FTS5")
        except Exception:
            # FTS5 is compiled into virtually every SQLite build, but if this one
            # lacks it, degrade to LIKE rather than refusing to start.
            logger.warning("FTS5 unavailable; falling back to LIKE search", exc_info=True)
            self._available = False

    async def index(
        self,
        session: AsyncSession,
        *,
        transcript_id: str,
        video_id: str,
        title: str,
        author: str,
        body: str,
    ) -> None:
        if not self._available:
            return
        await self.remove(session, transcript_id)
        await session.execute(
            text(
                "INSERT INTO transcript_fts (transcript_id, video_id, title, author, body) "
                "VALUES (:transcript_id, :video_id, :title, :author, :body)"
            ),
            {
                "transcript_id": transcript_id,
                "video_id": video_id,
                "title": title,
                "author": author,
                "body": body,
            },
        )

    async def remove(self, session: AsyncSession, transcript_id: str) -> None:
        if not self._available:
            return
        await session.execute(
            text("DELETE FROM transcript_fts WHERE transcript_id = :transcript_id"),
            {"transcript_id": transcript_id},
        )

    async def search(
        self,
        session: AsyncSession,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResults:
        if not self._available:
            return await _LIKE_BACKEND.search(
                session, query, filters=filters, limit=limit, offset=offset
            )

        tokens = _tokenise(query)
        if not tokens:
            return SearchResults(hits=[], total=0)

        filters = filters or SearchFilters()
        params: dict = {
            # Each token quoted as a literal phrase; implicit AND between them.
            "match": " ".join(f'"{token}"' for token in tokens),
            "limit": limit,
            "offset": offset,
        }
        where = _filter_clause(filters, params)

        base = f"""
            FROM transcript_fts f
            JOIN transcripts t ON t.id = f.transcript_id
            JOIN videos v ON v.id = t.video_id
            WHERE transcript_fts MATCH :match{where}
        """

        total = (
            await session.execute(text(f"SELECT COUNT(*) {base}"), params)
        ).scalar_one()

        rows = (
            await session.execute(
                text(
                    "SELECT f.transcript_id, f.video_id, "
                    "snippet(transcript_fts, 4, '', '', '…', 24) AS snippet, "
                    f"bm25(transcript_fts) AS rank {base} "
                    "ORDER BY rank LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).mappings().all()

        return SearchResults(
            hits=[
                SearchHit(
                    transcript_id=row["transcript_id"],
                    video_id=row["video_id"],
                    snippet=(row["snippet"] or "").strip(),
                    # bm25 returns "lower is better"; invert so callers can treat
                    # rank as a relevance score everywhere.
                    rank=-float(row["rank"] or 0.0),
                )
                for row in rows
            ],
            total=int(total),
        )


class LikeSearchBackend(SearchBackend):
    """Portable substring search. Correct everywhere, fast enough to five figures."""

    name = "like"

    async def search(
        self,
        session: AsyncSession,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResults:
        tokens = _tokenise(query)
        if not tokens:
            return SearchResults(hits=[], total=0)

        filters = filters or SearchFilters()
        params: dict = {"limit": limit, "offset": offset}
        token_clauses = []
        for position, token in enumerate(tokens):
            key = f"token_{position}"
            params[key] = f"%{token.lower()}%"
            token_clauses.append(
                f"(LOWER(t.text) LIKE :{key} OR LOWER(v.title) LIKE :{key} "
                f"OR LOWER(v.author) LIKE :{key})"
            )

        where = " AND ".join(token_clauses) + _filter_clause(filters, params)
        base = f"FROM transcripts t JOIN videos v ON v.id = t.video_id WHERE {where}"

        total = (await session.execute(text(f"SELECT COUNT(*) {base}"), params)).scalar_one()
        rows = (
            await session.execute(
                text(
                    f"SELECT t.id AS transcript_id, t.video_id, t.text {base} "
                    "ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).mappings().all()

        return SearchResults(
            hits=[
                SearchHit(
                    transcript_id=row["transcript_id"],
                    video_id=row["video_id"],
                    snippet=_build_snippet(row["text"] or "", tokens),
                    rank=0.0,
                )
                for row in rows
            ],
            total=int(total),
        )


_LIKE_BACKEND = LikeSearchBackend()
_backend: SearchBackend | None = None


def get_search_backend(settings: Settings | None = None) -> SearchBackend:
    global _backend
    if _backend is None:
        settings = settings or get_settings()
        _backend = SqliteFtsBackend() if settings.is_sqlite else _LIKE_BACKEND
    return _backend


def reset_search_backend() -> None:
    """Drop the cached backend. Used by tests that rebuild the database."""
    global _backend
    _backend = None
