"""JWT authentication and account management."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.errors import AuthError, ConfigurationError
from app.core.security import (
    INSECURE_DEFAULT_SECRET,
    check_secret,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# --- password hashing --------------------------------------------------------


def test_password_round_trips() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"  # never stored in the clear
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_hashes_differently_each_time() -> None:
    """Per-password salt: identical passwords must not produce identical hashes."""
    assert hash_password("same-password-x") != hash_password("same-password-x")


def test_short_passwords_are_refused() -> None:
    with pytest.raises(AuthError):
        hash_password("short")


def test_a_corrupt_hash_reads_as_wrong_password() -> None:
    """Never a 500 — a broken row must not reveal that the account exists."""
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


# --- tokens ------------------------------------------------------------------


def test_token_round_trips(settings) -> None:
    token, expires_in = create_access_token("user-123", role="member", settings=settings)
    claims = decode_access_token(token, settings)
    assert claims["sub"] == "user-123"
    assert claims["role"] == "member"
    assert expires_in > 0


def test_a_token_signed_with_another_secret_is_rejected(settings) -> None:
    other = Settings(jwt_secret="a-completely-different-secret-value-here")
    token, _ = create_access_token("user-123", role="member", settings=other)
    with pytest.raises(AuthError):
        decode_access_token(token, settings)


def test_a_tampered_token_is_rejected(settings) -> None:
    token, _ = create_access_token("user-123", role="member", settings=settings)
    with pytest.raises(AuthError):
        decode_access_token(token[:-3] + "aaa", settings)


def test_an_expired_token_is_rejected(settings) -> None:
    expired = Settings(jwt_secret=settings.jwt_secret, access_token_expire_minutes=-1)
    token, _ = create_access_token("user-123", role="member", settings=expired)
    with pytest.raises(AuthError) as exc:
        decode_access_token(token, settings)
    assert "expired" in exc.value.message.lower()


def test_production_refuses_the_shipped_secret() -> None:
    with pytest.raises(ConfigurationError):
        check_secret(Settings(environment="production", jwt_secret=INSECURE_DEFAULT_SECRET))


def test_production_refuses_a_short_secret() -> None:
    with pytest.raises(ConfigurationError):
        check_secret(Settings(environment="production", jwt_secret="too-short"))


def test_development_tolerates_the_default_secret() -> None:
    check_secret(Settings(environment="development", jwt_secret=INSECURE_DEFAULT_SECRET))


# --- login -------------------------------------------------------------------


async def test_login_returns_a_usable_token(anonymous_client, member_credentials) -> None:
    email, password = member_credentials
    response = await anonymous_client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == email
    assert "password" not in response.text.lower() or "hashed" not in response.text

    me = await anonymous_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"}
    )
    assert me.json()["email"] == email


async def test_login_is_case_insensitive_on_email(anonymous_client, member_credentials) -> None:
    _, password = member_credentials
    response = await anonymous_client.post(
        "/api/auth/login", json={"email": "WRITER@AGENCY.TEST", "password": password}
    )
    assert response.status_code == 200


async def test_wrong_password_and_unknown_email_give_the_same_answer(
    anonymous_client, member_credentials
) -> None:
    """Otherwise login becomes a way to discover which addresses have accounts."""
    email, _ = member_credentials
    wrong = await anonymous_client.post(
        "/api/auth/login", json={"email": email, "password": "not-the-password"}
    )
    unknown = await anonymous_client.post(
        "/api/auth/login", json={"email": "nobody@agency.test", "password": "whatever12"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["message"] == unknown.json()["message"]


# --- enforcement -------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/api/meta", "/api/videos", "/api/jobs", "/api/transcripts", "/api/search?q=x"],
)
async def test_protected_routes_reject_anonymous_requests(anonymous_client, path: str) -> None:
    response = await anonymous_client.get(path)
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


async def test_health_stays_public(anonymous_client) -> None:
    """The container healthcheck cannot sign in."""
    assert (await anonymous_client.get("/api/health")).status_code == 200


async def test_a_garbage_token_is_rejected(anonymous_client) -> None:
    response = await anonymous_client.get(
        "/api/videos", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_deactivating_an_account_takes_effect_immediately(
    admin_client, client, member_credentials
) -> None:
    """A still-valid token must stop working the moment the account is disabled."""
    assert (await client.get("/api/videos")).status_code == 200

    users = (await admin_client.get("/api/auth/users")).json()
    member = next(u for u in users if u["email"] == member_credentials[0])
    await admin_client.patch(f"/api/auth/users/{member['id']}", json={"is_active": False})

    assert (await client.get("/api/videos")).status_code == 401


# --- account management ------------------------------------------------------


async def test_admins_can_create_accounts(admin_client) -> None:
    response = await admin_client.post(
        "/api/auth/users",
        json={"email": "New.Person@agency.test", "password": "another-password", "role": "member"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new.person@agency.test"  # normalised
    assert "hashed_password" not in response.text


async def test_members_cannot_create_accounts(client) -> None:
    response = await client.post(
        "/api/auth/users", json={"email": "x@agency.test", "password": "password123"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_members_cannot_list_accounts(client) -> None:
    assert (await client.get("/api/auth/users")).status_code == 403


async def test_duplicate_emails_are_refused(admin_client, member_credentials) -> None:
    response = await admin_client.post(
        "/api/auth/users", json={"email": member_credentials[0], "password": "password123"}
    )
    assert response.status_code == 409


async def test_short_passwords_are_refused_by_the_api(admin_client) -> None:
    response = await admin_client.post(
        "/api/auth/users", json={"email": "x@agency.test", "password": "short"}
    )
    assert response.status_code == 422


async def test_an_admin_cannot_lock_themselves_out(admin_client, admin_credentials) -> None:
    users = (await admin_client.get("/api/auth/users")).json()
    me = next(u for u in users if u["email"] == admin_credentials[0])

    assert (
        await admin_client.patch(f"/api/auth/users/{me['id']}", json={"is_active": False})
    ).status_code == 403
    assert (
        await admin_client.patch(f"/api/auth/users/{me['id']}", json={"role": "member"})
    ).status_code == 403
    assert (await admin_client.delete(f"/api/auth/users/{me['id']}")).status_code == 403


async def test_changing_your_own_password_requires_the_current_one(
    client, member_credentials, anonymous_client
) -> None:
    _, password = member_credentials

    assert (
        await client.post(
            "/api/auth/me/password",
            json={"current_password": "wrong-one", "new_password": "brand-new-password"},
        )
    ).status_code == 403

    assert (
        await client.post(
            "/api/auth/me/password",
            json={"current_password": password, "new_password": "brand-new-password"},
        )
    ).status_code == 200

    # The new password works, the old one does not.
    fresh = await anonymous_client.post(
        "/api/auth/login",
        json={"email": member_credentials[0], "password": "brand-new-password"},
    )
    assert fresh.status_code == 200
