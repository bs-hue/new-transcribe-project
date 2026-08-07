"""Password hashing and JWT issuing.

Two free, permissively licensed libraries do the cryptography, because writing
either of these by hand is how people get breached:

* ``bcrypt`` (Apache-2.0) — deliberately slow password hashing with a per-password
  salt, so a stolen database cannot be reversed with a rainbow table.
* ``PyJWT`` (MIT) — signed tokens, so the server can trust a request without
  storing a session.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import Settings, get_settings
from app.core.errors import AuthError, ConfigurationError

logger = logging.getLogger(__name__)

INSECURE_DEFAULT_SECRET = "change-me-in-production"

# bcrypt truncates silently at 72 bytes. Rejecting longer input is better than
# accepting a password whose tail never mattered.
_MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    _validate_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # A malformed hash in the database must read as "wrong password", never
        # as a server error that leaks which accounts exist.
        return False


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if len(password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise AuthError("Password is too long (maximum 72 bytes).")


def check_secret(settings: Settings | None = None) -> None:
    """Refuse to run in production with the shipped signing key."""
    settings = settings or get_settings()
    if settings.environment == "development":
        return
    if settings.jwt_secret == INSECURE_DEFAULT_SECRET or len(settings.jwt_secret) < 32:
        raise ConfigurationError(
            "JWT_SECRET must be set to a unique random value of at least 32 "
            "characters outside development. Generate one with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )


def create_access_token(
    user_id: str, *, role: str, settings: Settings | None = None
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``."""
    settings = settings or get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)

    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Verify a token and return its claims, or raise ``AuthError``."""
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Your session has expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token.") from exc
