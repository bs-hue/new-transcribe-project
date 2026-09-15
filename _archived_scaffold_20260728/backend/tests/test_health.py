"""Tests for the system endpoints.

These are the Phase 0 definition of done: the application boots, reaches its
database, reports honestly, and tells the frontend its limits.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.middleware import CORRELATION_HEADER


def test_health_reports_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"] == "ok"
    assert body["version"]


def test_health_response_carries_a_correlation_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers[CORRELATION_HEADER]


def test_incoming_correlation_id_is_preserved(client: TestClient) -> None:
    """An ID supplied by the caller is reused, so a chain of calls shares a trace."""
    response = client.get("/api/v1/health", headers={CORRELATION_HEADER: "trace-abc-123"})

    assert response.headers[CORRELATION_HEADER] == "trace-abc-123"


def test_public_config_exposes_limits_the_ui_needs(client: TestClient) -> None:
    body = client.get("/api/v1/config/public").json()

    assert body["max_urls_per_batch"] == 25
    assert body["max_video_duration_seconds"] == 7200
    assert body["default_model"] == "small"
    assert set(body["supported_formats"]) == {"txt", "srt", "vtt", "json"}
    assert body["playlists_supported"] is False


def test_summaries_are_unavailable_without_an_api_key(client: TestClient) -> None:
    """Summaries are opt-in and require a key; the UI must hide them otherwise."""
    body = client.get("/api/v1/config/public").json()

    assert body["summarize_available"] is False


def test_interactive_docs_are_served_in_development(client: TestClient) -> None:
    assert client.get("/api/v1/docs").status_code == 200
    assert client.get("/api/v1/openapi.json").status_code == 200
