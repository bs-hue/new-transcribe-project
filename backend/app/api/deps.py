"""Shared API dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_session_factory

# auto_error=False so a missing header raises our own AuthError shape rather than
# FastAPI's, keeping every error response identical.
_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Request-scoped session.

    Read paths commit nothing; write paths commit explicitly. Rolling back here
    means a handler that raises never leaves a half-applied transaction behind.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    session: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """Resolve the signed-in user from the ``Authorization: Bearer …`` header."""
    if credentials is None or not credentials.credentials:
        raise AuthError("Sign in to use this endpoint.")

    claims = decode_access_token(credentials.credentials, settings)
    user_id = claims.get("sub")
    if not user_id:
        raise AuthError("Invalid authentication token.")

    user = await session.get(User, user_id)
    # A token stays valid until it expires, so re-check the account each request:
    # deleting or deactivating someone takes effect immediately.
    if user is None or not user.is_active:
        raise AuthError("This account is no longer active.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise ForbiddenError("This action requires an administrator account.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
