"""Tests for configuration and its production guard rails.

The guard rails exist to stop a development ``.env`` reaching production. A safety
net nobody tests is not a safety net, so each rule is asserted here.

Settings are constructed with explicit keyword arguments rather than unpacked
dictionaries: it keeps every test readable on its own, and it type-checks cleanly
without suppression comments.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import DEV_JWT_SECRET, Settings

_REAL_SECRET = SecretStr("a-real-secret-generated-with-secrets-token-urlsafe")
_PROD_DATABASE = "postgresql+psycopg://user:pass@db:5432/transcripts"


def test_a_correct_production_configuration_is_accepted() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret=_REAL_SECRET,
        cookie_secure=True,
        cors_origins="https://app.example.com",
        database_url=_PROD_DATABASE,
    )

    assert settings.is_production
    assert settings.docs_enabled is False


def test_production_rejects_the_development_secret() -> None:
    with pytest.raises(ValidationError) as raised:
        Settings(
            app_env="production",
            jwt_secret=SecretStr(DEV_JWT_SECRET),
            cookie_secure=True,
            cors_origins="https://app.example.com",
            database_url=_PROD_DATABASE,
        )

    assert "JWT_SECRET" in str(raised.value)


def test_production_rejects_insecure_cookies() -> None:
    with pytest.raises(ValidationError) as raised:
        Settings(
            app_env="production",
            jwt_secret=_REAL_SECRET,
            cookie_secure=False,
            cors_origins="https://app.example.com",
            database_url=_PROD_DATABASE,
        )

    assert "COOKIE_SECURE" in str(raised.value)


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError) as raised:
        Settings(
            app_env="production",
            jwt_secret=_REAL_SECRET,
            cookie_secure=True,
            cors_origins="*",
            database_url=_PROD_DATABASE,
        )

    assert "CORS_ORIGINS" in str(raised.value)


def test_production_rejects_sqlite() -> None:
    """SQLite's single-writer lock would serialise the API against the worker."""
    with pytest.raises(ValidationError) as raised:
        Settings(
            app_env="production",
            jwt_secret=_REAL_SECRET,
            cookie_secure=True,
            cors_origins="https://app.example.com",
            database_url="sqlite:///./data/app.db",
        )

    assert "PostgreSQL" in str(raised.value)


def test_development_defaults_are_permissive() -> None:
    """Development must stay zero-setup: the same values would fail in production."""
    settings = Settings(app_env="development")

    assert settings.docs_enabled is True
    assert settings.is_production is False
    assert settings.database_url.startswith("sqlite")


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins="http://a.test , http://b.test,, ")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_summaries_require_both_a_flag_and_a_key() -> None:
    """Enabling the feature without a key must not advertise it to the UI."""
    without_key = Settings(llm_enabled=True)
    with_key = Settings(llm_enabled=True, llm_api_key=SecretStr("sk-test"))

    assert without_key.summarize_available is False
    assert with_key.summarize_available is True
