"""Sign-in and account management."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, AppSettings, CurrentUser, DbSession
from app.core.errors import ForbiddenError, NotFoundError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserRole
from app.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.users import approve, authenticate, create_user, register

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: DbSession, settings: AppSettings
) -> TokenResponse:
    user = await authenticate(session, payload.email, payload.password)
    token, expires_in = create_access_token(user.id, role=user.role, settings=settings)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.get("/registration")
async def registration_mode(settings: AppSettings) -> dict[str, str]:
    """Whether sign-up is offered, for the sign-in page.

    Public by necessity: the page that needs it is the one you see before you
    have a token. It reveals only what a "Create an account" link would.
    """
    return {"mode": settings.registration_mode}


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_account(
    payload: RegisterRequest, session: DbSession, settings: AppSettings
) -> UserResponse:
    """Public sign-up. Refused outright unless REGISTRATION_MODE allows it.

    Returns the account rather than a token even when approval is not required,
    so there is one sign-in path rather than two. The client posts to /login
    next, and gets the same treatment as everybody else.
    """
    user = await register(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        settings=settings,
    )
    await session.commit()
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/me/password", response_model=UserResponse)
async def change_password(
    payload: PasswordChangeRequest, user: CurrentUser, session: DbSession
) -> UserResponse:
    """Change your own password. Requires the current one."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise ForbiddenError("Your current password is incorrect.")

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    await session.commit()
    return UserResponse.model_validate(user)


# --- admin only --------------------------------------------------------------


@router.get("/users", response_model=list[UserResponse])
async def list_users(session: DbSession, _admin: AdminUser) -> list[UserResponse]:
    users = (
        (await session.execute(select(User).order_by(User.created_at))).scalars().all()
    )
    return [UserResponse.model_validate(user) for user in users]


@router.post("/users", response_model=UserResponse, status_code=201)
async def add_user(
    payload: UserCreateRequest, session: DbSession, _admin: AdminUser
) -> UserResponse:
    user = await create_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
    )
    await session.commit()
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, payload: UserUpdateRequest, session: DbSession, admin: AdminUser
) -> UserResponse:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"No user with id {user_id}.")

    # Guard against an admin locking themselves out of their own account.
    if user.id == admin.id:
        if payload.is_active is False:
            raise ForbiddenError("You cannot deactivate your own account.")
        if payload.role is not None and payload.role != UserRole.ADMIN.value:
            raise ForbiddenError("You cannot remove your own admin role.")

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)

    session.add(user)
    await session.commit()
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: str, session: DbSession, _admin: AdminUser
) -> UserResponse:
    """Let a waiting account in. Idempotent, so a double-click is harmless."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"No user with id {user_id}.")

    await approve(session, user)
    await session.commit()
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, session: DbSession, admin: AdminUser) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"No user with id {user_id}.")
    if user.id == admin.id:
        raise ForbiddenError("You cannot delete your own account.")

    await session.delete(user)
    await session.commit()
