"""Submit URLs, preview them, and browse the resulting videos."""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.errors import (
    AppError,
    LimitExceededError,
    NotFoundError,
    UnsupportedFileFormatError,
)
from app.db.models import Job, JobStatus, Transcript, Video
from app.schemas import (
    JobSummary,
    PreviewListResponse,
    PreviewResponse,
    SubmissionOutcomeResponse,
    SubmissionResponse,
    TranscriptDetail,
    UploadResponse,
    URLListRequest,
    VideoDetail,
    VideoListResponse,
    VideoSummary,
)
from app.services.ingest import preview_url, submit_urls
from app.services.media import probe_and_thumbnail
from app.services.settings_store import effective_settings

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/debug-proxy")
async def debug_proxy(settings: AppSettings):
    import traceback

    import httpx

    debug_log = []

    # Step 1: Check token
    if not settings.webshare_token:
        debug_log.append("ERROR: WEBSHARE_TOKEN is empty in environment.")
        return {"status": "failed_at_token", "log": debug_log}

    debug_log.append(f"WEBSHARE_TOKEN is set: {settings.webshare_token[:5]}***")

    # Step 2: Fetch proxies
    try:
        debug_log.append("Fetching proxies from Webshare API...")
        headers = {"Authorization": f"Token {settings.webshare_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct", headers=headers
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            debug_log.append(f"SUCCESS: Fetched {len(results)} proxies.")
            if not results:
                return {"status": "no_proxies", "log": debug_log}

            p = results[0]
            proxy_url = f"http://{p['username']}:{p['password']}@{p['proxy_address']}:{p['port']}"
            debug_log.append(f"Selected proxy: {p['proxy_address']}:{p['port']}")
    except Exception as e:
        debug_log.append(f"ERROR fetching proxies: {e}")
        debug_log.append(traceback.format_exc())
        return {"status": "failed_at_webshare_api", "log": debug_log}

    # Step 3: Test proxy against YouTube
    try:
        debug_log.append("Testing proxy connection to YouTube...")
        async with httpx.AsyncClient(proxy=proxy_url, timeout=15) as client:
            r = await client.get("https://www.youtube.com")
            debug_log.append(f"SUCCESS: YouTube returned HTTP {r.status_code}")
            return {"status": "success", "log": debug_log}
    except Exception as e:
        debug_log.append(f"ERROR connecting to YouTube via proxy: {e}")
        debug_log.append(traceback.format_exc())
        return {"status": "failed_at_youtube", "log": debug_log}


#: Preview probes the platform per URL. Fanning out unbounded would get us
#: rate-limited; four at a time keeps a 20-URL paste responsive without that.
_PREVIEW_CONCURRENCY = 4


def _enforce_batch_size(urls: list[str], settings: AppSettings) -> None:
    if len(urls) > settings.max_urls_per_request:
        raise AppError(
            f"Too many URLs: {len(urls)} submitted, limit is {settings.max_urls_per_request}.",
            details={"limit": settings.max_urls_per_request},
        )


@router.post("/preview", response_model=PreviewListResponse)
async def preview(
    payload: URLListRequest, session: DbSession, settings: AppSettings
) -> PreviewListResponse:
    """Validate and probe URLs without downloading anything.

    This is step 3 of the workflow: the user sees title, thumbnail, duration and
    estimated size, plus any limit problems, before committing to a download.
    """
    # Limits are administrator-changeable, so read the effective values rather
    # than the ones captured at startup.
    settings = await effective_settings(session, settings)
    _enforce_batch_size(payload.urls, settings)
    semaphore = asyncio.Semaphore(_PREVIEW_CONCURRENCY)

    async def probe(url: str) -> PreviewResponse:
        async with semaphore:
            result = await preview_url(session, url, settings)
        return PreviewResponse(**asdict(result))

    results = await asyncio.gather(*(probe(url) for url in payload.urls))
    return PreviewListResponse(results=list(results))


@router.post("", response_model=SubmissionResponse, status_code=202)
async def submit(
    payload: URLListRequest,
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
) -> SubmissionResponse:
    """Queue one job per valid URL. Invalid URLs are reported, not fatal."""
    settings = await effective_settings(session, settings)
    _enforce_batch_size(payload.urls, settings)
    result = await submit_urls(
        session,
        payload.urls,
        language=payload.language,
        settings=settings,
        submitted_by=user.id,
    )
    return SubmissionResponse(
        batch_id=result.batch_id,
        accepted_count=result.accepted_count,
        rejected_count=result.rejected_count,
        results=[SubmissionOutcomeResponse(**asdict(outcome)) for outcome in result.outcomes],
    )


@router.get("", response_model=VideoListResponse)
async def list_videos(
    session: DbSession,
    platform: str | None = None,
    author: str | None = None,
    has_transcript: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> VideoListResponse:
    statement = select(Video)
    count_statement = select(func.count(Video.id))

    if platform:
        statement = statement.where(Video.platform == platform)
        count_statement = count_statement.where(Video.platform == platform)
    if author:
        pattern = f"%{author.lower()}%"
        statement = statement.where(func.lower(Video.author).like(pattern))
        count_statement = count_statement.where(func.lower(Video.author).like(pattern))
    if has_transcript is not None:
        exists = select(Transcript.id).where(Transcript.video_id == Video.id).exists()
        condition = exists if has_transcript else ~exists
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)

    total = (await session.execute(count_statement)).scalar_one()
    rows = (
        (
            await session.execute(
                statement.order_by(Video.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )

    return VideoListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[VideoSummary.model_validate(row) for row in rows],
    )


ALLOWED_UPLOAD_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".wmv",
    ".flv",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".wma",
    ".opus",
}


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_video(
    session: DbSession,
    settings: AppSettings,
    user: CurrentUser,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    language: str | None = Form(default=None),
) -> UploadResponse:
    """Accept a video or audio file upload directly, save it, and queue a transcription job."""
    settings = await effective_settings(session, settings)

    raw_filename = file.filename or "uploaded_video.mp4"
    ext = Path(raw_filename).suffix.lower()
    if not ext or ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise UnsupportedFileFormatError(
            f"Unsupported file format '{ext}'. Allowed formats: {allowed}"
        )

    upload_id = uuid.uuid4().hex
    upload_dir = settings.resolved_upload_dir() / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    clean_stem = re.sub(r"[^\w\-.]", "_", Path(raw_filename).stem) or "uploaded"
    safe_filename = f"{clean_stem}{ext}"
    target_path = upload_dir / safe_filename

    max_bytes = settings.max_video_filesize_bytes
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB

    try:
        with open(target_path, "wb") as f_out:
            while chunk := await file.read(chunk_size):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise LimitExceededError(
                        f"File exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB."
                    )
                f_out.write(chunk)
    except Exception:
        if target_path.exists():
            target_path.unlink()
        raise

    thumb_path = upload_dir / "thumbnail.jpg"
    duration, has_thumb = await probe_and_thumbnail(target_path, thumb_path, settings)

    canonical_url = f"upload://{upload_id}/{safe_filename}"
    display_title = (title.strip() if title and title.strip() else Path(raw_filename).stem) or "Uploaded Video"

    video = Video(
        platform="upload",
        platform_video_id=upload_id,
        source_url=canonical_url,
        canonical_url=canonical_url,
        title=display_title,
        author=user.full_name or user.email,
        thumbnail_url=f"/api/videos/uploads/{upload_id}/thumbnail.jpg" if has_thumb else None,
        duration_seconds=duration,
        estimated_size_bytes=total_bytes,
    )
    session.add(video)
    await session.flush()

    batch_id = uuid.uuid4().hex
    job = Job(
        video_id=video.id,
        batch_id=batch_id,
        submitted_by=user.id,
        status=JobStatus.QUEUED.value,
        language=language.strip() if language and language.strip() else None,
    )
    session.add(job)
    await session.commit()

    return UploadResponse(
        job_id=job.id,
        video_id=video.id,
        batch_id=batch_id,
        title=video.title or safe_filename,
        canonical_url=canonical_url,
        status=job.status,
        duration_seconds=video.duration_seconds,
        thumbnail_url=video.thumbnail_url,
    )


@router.get("/uploads/{upload_id}/{filename}")
async def get_uploaded_media(
    upload_id: str,
    filename: str,
    settings: AppSettings,
):
    upload_dir = settings.resolved_upload_dir()
    file_path = (upload_dir / upload_id / filename).resolve()
    # Path traversal protection
    if not str(file_path).startswith(str(upload_dir.resolve())):
        raise NotFoundError("File not found.")
    if not file_path.is_file():
        raise NotFoundError("File not found.")
    return FileResponse(file_path)


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, session: DbSession) -> VideoDetail:
    video = (await session.execute(select(Video).where(Video.id == video_id))).scalar_one_or_none()
    if video is None:
        raise NotFoundError(f"No video with id {video_id}.")

    transcript = (
        await session.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.video_id == video_id)
            .order_by(Transcript.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    transcript_count = (
        await session.execute(
            select(func.count(Transcript.id)).where(Transcript.video_id == video_id)
        )
    ).scalar_one()

    latest_job = (
        await session.execute(
            select(Job).where(Job.video_id == video_id).order_by(Job.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    detail = VideoDetail.model_validate(video)
    detail.transcript_count = int(transcript_count)
    detail.transcript = (
        TranscriptDetail.model_validate(transcript) if transcript is not None else None
    )
    detail.latest_job = JobSummary.model_validate(latest_job) if latest_job else None
    return detail


@router.delete("/{video_id}", status_code=204)
async def delete_video(video_id: str, session: DbSession) -> None:
    """Remove a video and everything derived from it."""
    video = await session.get(Video, video_id)
    if video is None:
        raise NotFoundError(f"No video with id {video_id}.")

    from app.services.search import get_search_backend

    backend = get_search_backend()
    transcript_ids = (
        (await session.execute(select(Transcript.id).where(Transcript.video_id == video_id)))
        .scalars()
        .all()
    )
    for transcript_id in transcript_ids:
        await backend.remove(session, transcript_id)

    await session.delete(video)
    await session.commit()
