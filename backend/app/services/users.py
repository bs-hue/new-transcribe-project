"""User lookup and creation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import AppError, AuthError
from app.core.security import hash_password, verify_password
from app.db.models import User, UserRole
from app.db.session import session_scope

logger = logging.getLogger(__name__)


class EmailTakenError(AppError):
    code = "email_taken"
    status_code = 409


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(User.email == normalise_email(email)))
    ).scalar_one_or_none()


async def count_users(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count(User.id)))).scalar_one())


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    role: str = UserRole.MEMBER.value,
    approved: bool = True,
) -> User:
    """Create an account.

    ``approved`` defaults to true because this path is an administrator adding
    somebody deliberately — asking them to then approve their own invitation
    would be pure ceremony. Self-service sign-up goes through ``register``.
    """
    email = normalise_email(email)
    if not email or "@" not in email:
        raise AppError("A valid email address is required.")
    if await get_by_email(session, email) is not None:
        raise EmailTakenError(f"An account already exists for {email}.")
    if role not in {UserRole.ADMIN.value, UserRole.MEMBER.value}:
        raise AppError(f"Unknown role {role!r}. Use 'admin' or 'member'.")

    user = User(
        email=email,
        full_name=(full_name or "").strip() or None,
        hashed_password=hash_password(password),
        role=role,
        approved_at=datetime.now(UTC) if approved else None,
    )
    session.add(user)
    await session.flush()
    return user


class RegistrationClosedError(AppError):
    code = "registration_closed"
    status_code = 403


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    settings: Settings | None = None,
) -> User:
    """Create an account from the public sign-up form.

    Always a member, never an admin — the endpoint is unauthenticated, so
    honouring a role from the request would be a privilege-escalation hole.
    """
    settings = settings or get_settings()
    mode = settings.registration_mode
    if mode == "closed":
        raise RegistrationClosedError(
            "This service is invitation-only. Ask an administrator for an account."
        )

    return await create_user(
        session,
        email=email,
        password=password,
        full_name=full_name,
        role=UserRole.MEMBER.value,
        approved=(mode == "open"),
    )


async def approve(session: AsyncSession, user: User) -> User:
    """Let a waiting account in. Re-approving an approved account is a no-op."""
    if user.approved_at is None:
        user.approved_at = datetime.now(UTC)
        session.add(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, or raise a deliberately vague ``AuthError``.

    The same message is returned for an unknown email and a wrong password so the
    endpoint cannot be used to discover which addresses have accounts.
    """
    user = await get_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Incorrect email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated.")
    # Told apart from deactivation on purpose. "Waiting for approval" is a
    # state the person can do nothing about but should understand; "deactivated"
    # means somebody decided. Conflating them makes both confusing.
    if user.approved_at is None:
        raise AuthError(
            "This account is waiting for an administrator to approve it."
        )

    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return user


async def bootstrap_admin(settings: Settings | None = None) -> None:
    """Create the first admin from the environment, if there are no users yet.

    Makes a fresh deployment usable without shell access. Deliberately a no-op
    once any account exists, so it cannot be used to re-add an admin later.
    """
    settings = settings or get_settings()
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if not email or not password:
        return

    async with session_scope() as session:
        if await count_users(session) > 0:
            return
        await create_user(
            session,
            email=email,
            password=password,
            full_name="Administrator",
            role=UserRole.ADMIN.value,
        )

    logger.warning(
        "Created the first admin account (%s) from BOOTSTRAP_ADMIN_*. "
        "Sign in and change this password.",
        normalise_email(email),
    )
