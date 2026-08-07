"""Public sign-up, approval, and the login gate that depends on both."""

from __future__ import annotations

import pytest

from app.config import get_settings

NEW_ACCOUNT = {
    "email": "applicant@example.test",
    "password": "a-good-enough-password",
    "full_name": "Ada Applicant",
}


@pytest.fixture
def registration(monkeypatch):
    """Set REGISTRATION_MODE for one test.

    Settings are resolved per request, so clearing the cache after changing the
    environment is enough — no need to rebuild the app.
    """

    def apply(mode: str) -> None:
        monkeypatch.setenv("REGISTRATION_MODE", mode)
        get_settings.cache_clear()

    yield apply
    get_settings.cache_clear()


async def test_sign_up_is_refused_unless_it_is_turned_on(
    anonymous_client, registration
) -> None:
    """The default must be closed: a tool that quietly accepts strangers is
    worse than one that makes you enable it deliberately."""
    registration("closed")
    response = await anonymous_client.post("/api/auth/register", json=NEW_ACCOUNT)
    assert response.status_code == 403
    assert response.json()["code"] == "registration_closed"


async def test_the_mode_is_readable_without_signing_in(
    anonymous_client, registration
) -> None:
    """The sign-in page needs this before anybody has a token."""
    registration("approval")
    response = await anonymous_client.get("/api/auth/registration")
    assert response.status_code == 200
    assert response.json() == {"mode": "approval"}


async def test_approval_mode_creates_an_account_that_cannot_sign_in_yet(
    anonymous_client, registration
) -> None:
    registration("approval")

    created = await anonymous_client.post("/api/auth/register", json=NEW_ACCOUNT)
    assert created.status_code == 201
    body = created.json()
    assert body["approved_at"] is None
    assert body["role"] == "member"

    denied = await anonymous_client.post(
        "/api/auth/login",
        json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]},
    )
    assert denied.status_code == 401
    # Distinct from "deactivated": nobody has decided anything yet, and the
    # applicant should be told which of the two it is.
    assert "approve" in denied.json()["message"].lower()


async def test_an_admin_can_approve_and_then_they_can_sign_in(
    anonymous_client, admin_client, registration
) -> None:
    registration("approval")

    created = await anonymous_client.post("/api/auth/register", json=NEW_ACCOUNT)
    user_id = created.json()["id"]

    approved = await admin_client.post(f"/api/auth/users/{user_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["approved_at"] is not None

    allowed = await anonymous_client.post(
        "/api/auth/login",
        json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]},
    )
    assert allowed.status_code == 200
    assert allowed.json()["access_token"]


async def test_approving_twice_is_harmless(
    anonymous_client, admin_client, registration
) -> None:
    """A double-click must not move the approval date or fail."""
    registration("approval")
    user_id = (
        await anonymous_client.post("/api/auth/register", json=NEW_ACCOUNT)
    ).json()["id"]

    first = await admin_client.post(f"/api/auth/users/{user_id}/approve")
    second = await admin_client.post(f"/api/auth/users/{user_id}/approve")
    assert second.status_code == 200

    # Compared as instants, not as strings. SQLite does not store timezones, so
    # a value just written reads back as "…Z" and the same value re-read comes
    # back naive — identical moments, different spelling. PostgreSQL keeps the
    # offset, so this only bites in tests.
    def instant(response) -> str:  # noqa: ANN001
        return response.json()["approved_at"].rstrip("Z")

    assert instant(second) == instant(first)


async def test_open_mode_lets_them_in_immediately(
    anonymous_client, registration
) -> None:
    registration("open")

    created = await anonymous_client.post("/api/auth/register", json=NEW_ACCOUNT)
    assert created.status_code == 201
    assert created.json()["approved_at"] is not None

    allowed = await anonymous_client.post(
        "/api/auth/login",
        json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]},
    )
    assert allowed.status_code == 200


async def test_signing_up_cannot_make_you_an_admin(
    anonymous_client, registration
) -> None:
    """The endpoint is unauthenticated, so an accepted role would be a
    privilege-escalation hole rather than a convenience."""
    registration("open")
    response = await anonymous_client.post(
        "/api/auth/register", json={**NEW_ACCOUNT, "role": "admin"}
    )
    assert response.status_code == 201
    assert response.json()["role"] == "member"


async def test_an_existing_email_is_refused(
    anonymous_client, registration, member_credentials
) -> None:
    registration("open")
    email, _ = member_credentials
    response = await anonymous_client.post(
        "/api/auth/register", json={**NEW_ACCOUNT, "email": email}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


async def test_a_short_password_is_refused(anonymous_client, registration) -> None:
    registration("open")
    response = await anonymous_client.post(
        "/api/auth/register", json={**NEW_ACCOUNT, "password": "short"}
    )
    assert response.status_code == 422


async def test_accounts_an_admin_creates_are_approved_on_creation(
    admin_client,
) -> None:
    """Approving your own invitation would be pure ceremony."""
    response = await admin_client.post(
        "/api/auth/users",
        json={"email": "invited@example.test", "password": "invited-password"},
    )
    assert response.status_code == 201
    assert response.json()["approved_at"] is not None


async def test_only_an_admin_may_approve(
    anonymous_client, client, registration
) -> None:
    registration("approval")
    user_id = (
        await anonymous_client.post("/api/auth/register", json=NEW_ACCOUNT)
    ).json()["id"]

    response = await client.post(f"/api/auth/users/{user_id}/approve")
    assert response.status_code == 403
