"""Tests for error translation.

The error envelope is a promise to the frontend: every failure, from any cause,
arrives in the same shape. These tests hold us to it — including the one that
matters most, that a genuine bug never leaks internal detail to a client.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import register_exception_handlers
from app.shared.domain.errors import ConflictError, ErrorDetail, NotFoundError


def _app_with_handlers() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    return app


def test_unknown_route_returns_the_standard_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/no-such-endpoint")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["correlation_id"]


def test_domain_error_maps_to_its_status_and_keeps_details() -> None:
    app = _app_with_handlers()

    @app.get("/conflict")
    def raise_conflict() -> None:
        raise ConflictError(
            "Email already registered.",
            details=[ErrorDetail(field="email", issue="already in use")],
        )

    with TestClient(app) as client:
        response = client.get("/conflict")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "Email already registered."
    assert error["details"] == [{"field": "email", "issue": "already in use"}]


def test_not_found_domain_error_maps_to_404() -> None:
    app = _app_with_handlers()

    @app.get("/missing")
    def raise_not_found() -> None:
        raise NotFoundError("Job not found.")

    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_validation_errors_name_the_offending_field() -> None:
    """Field paths follow the API spec: nested and indexed, e.g. ``urls[0]``."""
    app = _app_with_handlers()

    class Payload(BaseModel):
        urls: list[str]

    @app.post("/items")
    def create(payload: Payload) -> None:
        return None

    with TestClient(app) as client:
        response = client.post("/items", json={"urls": [{"not": "a string"}]})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "urls[0]"


def test_unexpected_errors_never_leak_internal_detail() -> None:
    """A real bug must produce a generic message.

    Internal strings — file paths, SQL, connection details — are useful to an
    attacker and useless to a user. The traceback belongs in the logs only.
    """
    app = _app_with_handlers()

    @app.get("/boom")
    def explode() -> None:
        raise RuntimeError("connection string postgres://admin:hunter2@10.0.0.5/db")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text
    assert "postgres://" not in response.text
