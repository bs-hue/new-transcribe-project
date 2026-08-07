"""Cross-origin behaviour the frontend depends on."""

from __future__ import annotations


async def test_export_filename_header_is_exposed_to_the_browser(
    client, session, settings, fake_media, monkeypatch
) -> None:
    """Downloads are fetched with an Authorization header rather than a plain
    link, so the browser can only name the file if this header is exposed."""
    from app.services import pipeline as pipeline_module
    from app.services.ingest import submit_urls
    from app.services.metadata import VideoMetadata
    from app.services.pipeline import Pipeline

    async def fake_fetch(parsed, settings=None):  # noqa: ANN001
        return VideoMetadata(
            platform=parsed.platform,
            platform_video_id=parsed.video_id,
            canonical_url=parsed.canonical_url,
            source_url=parsed.original_url,
            title="How to write a hook",
            duration_seconds=60.0,
        )

    monkeypatch.setattr(pipeline_module, "fetch_metadata", fake_fetch)

    result = await submit_urls(session, ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    await Pipeline(settings).run(result.outcomes[0].job_id)
    await session.commit()

    detail = (await client.get(f"/api/videos/{result.outcomes[0].video_id}")).json()
    response = await client.get(
        f"/api/transcripts/{detail['transcript']['id']}/export",
        params={"format": "txt"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "")
    assert "Content-Disposition" in exposed
    assert "How_to_write_a_hook" in response.headers["content-disposition"]
