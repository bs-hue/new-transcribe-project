"""HTTP surface: submission, browsing, search and export."""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from sqlalchemy import select

from app.db.models import Transcript
from app.services import pipeline as pipeline_module
from app.services.ingest import submit_urls
from app.services.metadata import VideoMetadata
from app.services.pipeline import Pipeline

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SECOND_URL = "https://www.instagram.com/reel/CxYz123abc/"


@pytest.fixture
def patched_metadata(monkeypatch):
    async def fake_fetch(parsed, settings=None):  # noqa: ANN001
        return VideoMetadata(
            platform=parsed.platform,
            platform_video_id=parsed.video_id,
            canonical_url=parsed.canonical_url,
            source_url=parsed.original_url,
            title=f"Video {parsed.video_id}",
            author="Creator Name",
            duration_seconds=60.0,
            estimated_size_bytes=1024 * 1024,
        )

    monkeypatch.setattr(pipeline_module, "fetch_metadata", fake_fetch)


async def _seed_transcript(session, settings, url: str = URL) -> str:
    """Run one URL through the pipeline and return its transcript id."""
    result = await submit_urls(session, [url])
    await Pipeline(settings).run(result.outcomes[0].job_id)
    await session.commit()
    return (
        await session.execute(
            select(Transcript.id).where(Transcript.video_id == result.outcomes[0].video_id)
        )
    ).scalar_one()


# --- meta --------------------------------------------------------------------


async def test_health_reports_ok(client) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] is True


async def test_meta_advertises_platforms_formats_and_limits(client) -> None:
    payload = (await client.get("/api/meta")).json()
    assert {p["name"] for p in payload["platforms"]} == {"youtube", "instagram"}
    assert len(payload["export_formats"]) == 7
    assert payload["limits"]["max_urls_per_request"] == 10
    assert payload["transcription_ready"] is True


# --- submission --------------------------------------------------------------


async def test_submit_queues_valid_urls_and_reports_invalid_ones(client) -> None:
    response = await client.post(
        "/api/videos", json={"urls": [URL, "https://vimeo.com/1", SECOND_URL]}
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted_count"] == 2
    assert payload["rejected_count"] == 1
    assert payload["batch_id"]

    rejected = next(r for r in payload["results"] if not r["accepted"])
    assert rejected["error_code"] == "unsupported_url"


async def test_submit_accepts_a_pasted_text_block(client) -> None:
    """The UI sends one textarea value; the API should not care."""
    response = await client.post("/api/videos", json={"urls": f"{URL}\n{SECOND_URL}"})
    assert response.json()["accepted_count"] == 2


async def test_submit_enforces_the_batch_size_limit(client) -> None:
    urls = [f"https://youtu.be/{'a' * 10}{index}" for index in range(11)]
    response = await client.post("/api/videos", json={"urls": urls})
    assert response.status_code == 500
    assert "Too many URLs" in response.json()["message"]


async def test_submit_rejects_an_empty_list(client) -> None:
    assert (await client.post("/api/videos", json={"urls": []})).status_code == 422


async def test_preview_returns_metadata_without_downloading(
    client, monkeypatch, fake_media
) -> None:
    from app.services import ingest as ingest_module

    async def fake_fetch(parsed, settings=None):  # noqa: ANN001
        return VideoMetadata(
            platform=parsed.platform,
            platform_video_id=parsed.video_id,
            canonical_url=parsed.canonical_url,
            source_url=parsed.original_url,
            title="Preview title",
            thumbnail_url="https://img.example/t.jpg",
            duration_seconds=42.0,
            estimated_size_bytes=5 * 1024 * 1024,
        )

    monkeypatch.setattr(ingest_module, "fetch_metadata", fake_fetch)

    payload = (
        await client.post("/api/videos/preview", json={"urls": [URL, "https://vimeo.com/1"]})
    ).json()

    good = payload["results"][0]
    assert good["valid"] is True
    assert good["title"] == "Preview title"
    assert good["thumbnail_url"]
    assert good["duration_seconds"] == 42.0
    assert good["estimated_size_bytes"] == 5 * 1024 * 1024
    assert good["within_limits"] is True

    assert payload["results"][1]["valid"] is False
    assert fake_media.downloaded == []  # nothing was fetched


# --- jobs --------------------------------------------------------------------


async def test_batch_status_aggregates_a_submission(client) -> None:
    batch_id = (await client.post("/api/videos", json={"urls": [URL, SECOND_URL]})).json()[
        "batch_id"
    ]

    payload = (await client.get(f"/api/jobs/batch/{batch_id}")).json()
    assert payload["total"] == 2
    assert payload["queued"] == 2
    assert len(payload["jobs"]) == 2


async def test_unknown_batch_is_a_404(client) -> None:
    assert (await client.get("/api/jobs/batch/nope")).status_code == 404


async def test_cancel_then_retry_moves_a_job_through_states(client) -> None:
    job_id = (await client.post("/api/videos", json={"urls": [URL]})).json()["results"][0][
        "job_id"
    ]

    assert (await client.post(f"/api/jobs/{job_id}/cancel")).json()["status"] == "cancelled"
    assert (await client.post(f"/api/jobs/{job_id}/retry")).json()["status"] == "queued"
    assert (await client.post(f"/api/jobs/{job_id}/retry")).status_code == 404


# --- videos and transcripts --------------------------------------------------


async def test_video_detail_includes_the_latest_transcript(
    client, session, settings, fake_media, patched_metadata
) -> None:
    await _seed_transcript(session, settings)

    videos = (await client.get("/api/videos")).json()
    assert videos["total"] == 1
    video_id = videos["items"][0]["id"]

    detail = (await client.get(f"/api/videos/{video_id}")).json()
    assert detail["title"] == "Video dQw4w9WgXcQ"
    assert detail["transcript"]["word_count"] > 0
    assert len(detail["transcript"]["segments"]) == 3
    assert detail["latest_job"]["status"] == "completed"


async def test_videos_can_be_filtered_by_platform_and_transcript_presence(
    client, session, settings, fake_media, patched_metadata
) -> None:
    await _seed_transcript(session, settings)
    await submit_urls(session, [SECOND_URL])  # queued, never processed

    assert (await client.get("/api/videos?platform=youtube")).json()["total"] == 1
    assert (await client.get("/api/videos?has_transcript=true")).json()["total"] == 1
    assert (await client.get("/api/videos?has_transcript=false")).json()["total"] == 1


async def test_deleting_a_video_removes_its_transcript_and_search_entry(
    client, session, settings, fake_media, patched_metadata
) -> None:
    transcript_id = await _seed_transcript(session, settings)
    video_id = (await client.get("/api/videos")).json()["items"][0]["id"]

    assert (await client.delete(f"/api/videos/{video_id}")).status_code == 204
    assert (await client.get(f"/api/transcripts/{transcript_id}")).status_code == 404
    assert (await client.get("/api/search?q=placeholder")).json()["total"] == 0


async def test_unknown_ids_are_404s(client) -> None:
    assert (await client.get("/api/videos/missing")).status_code == 404
    assert (await client.get("/api/transcripts/missing")).status_code == 404
    assert (await client.get("/api/jobs/missing")).status_code == 404


# --- search ------------------------------------------------------------------


async def test_search_finds_stored_transcripts(
    client, session, settings, fake_media, patched_metadata
) -> None:
    await _seed_transcript(session, settings)

    payload = (await client.get("/api/search?q=placeholder")).json()
    assert payload["total"] == 1
    hit = payload["items"][0]
    assert hit["title"] == "Video dQw4w9WgXcQ"
    assert hit["snippet"]
    assert hit["platform"] == "youtube"


async def test_search_respects_the_platform_filter(
    client, session, settings, fake_media, patched_metadata
) -> None:
    await _seed_transcript(session, settings)
    assert (await client.get("/api/search?q=placeholder&platform=youtube")).json()["total"] == 1
    assert (await client.get("/api/search?q=placeholder&platform=instagram")).json()["total"] == 0


async def test_search_with_no_match_is_empty_not_an_error(
    client, session, settings, fake_media, patched_metadata
) -> None:
    await _seed_transcript(session, settings)
    payload = (await client.get("/api/search?q=zzzznotpresent")).json()
    assert payload["total"] == 0
    assert payload["items"] == []


async def test_search_survives_query_syntax_characters(
    client, session, settings, fake_media, patched_metadata
) -> None:
    """A stray quote or operator must not become a query syntax error."""
    await _seed_transcript(session, settings)
    for query in ['"unbalanced', "AND OR NOT", "placeholder AND", "a*b(c)"]:
        assert (await client.get("/api/search", params={"q": query})).status_code == 200


async def test_search_requires_a_query(client) -> None:
    assert (await client.get("/api/search?q=")).status_code == 422


# --- export ------------------------------------------------------------------


@pytest.mark.parametrize("format_name", ["txt", "docx", "md", "xlsx", "json", "srt", "vtt"])
async def test_single_transcript_export_downloads(
    client, session, settings, fake_media, patched_metadata, format_name: str
) -> None:
    transcript_id = await _seed_transcript(session, settings)

    response = await client.get(
        f"/api/transcripts/{transcript_id}/export", params={"format": format_name}
    )
    assert response.status_code == 200
    assert response.content
    assert "attachment" in response.headers["content-disposition"]


async def test_export_rejects_an_unknown_format(
    client, session, settings, fake_media, patched_metadata
) -> None:
    transcript_id = await _seed_transcript(session, settings)
    response = await client.get(
        f"/api/transcripts/{transcript_id}/export", params={"format": "pdf"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_export_format"


async def test_bulk_export_by_ids_returns_one_combined_file(
    client, session, settings, fake_media, patched_metadata
) -> None:
    first = await _seed_transcript(session, settings)
    second = await _seed_transcript(session, settings, SECOND_URL)

    response = await client.post(
        "/api/exports", json={"format": "txt", "transcript_ids": [first, second]}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "CONTENTS" in response.text


async def test_bulk_export_can_ask_for_separate_files(
    client, session, settings, fake_media, patched_metadata
) -> None:
    first = await _seed_transcript(session, settings)
    second = await _seed_transcript(session, settings, SECOND_URL)

    response = await client.post(
        "/api/exports",
        json={"format": "txt", "transcript_ids": [first, second], "combine": False},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(archive.namelist()) == 2


async def test_bulk_export_by_query_selects_matching_transcripts(
    client, session, settings, fake_media, patched_metadata
) -> None:
    await _seed_transcript(session, settings)
    await _seed_transcript(session, settings, SECOND_URL)

    response = await client.post("/api/exports", json={"format": "json", "query": "placeholder"})
    assert response.status_code == 200
    assert json.loads(response.content)["count"] == 2


async def test_bulk_export_needs_a_selection(client) -> None:
    assert (await client.post("/api/exports", json={"format": "txt"})).status_code == 422


async def test_bulk_export_with_no_matches_is_a_404(client) -> None:
    response = await client.post(
        "/api/exports", json={"format": "txt", "transcript_ids": ["missing"]}
    )
    assert response.status_code == 404


# Authentication has its own suite — see tests/test_auth.py.
