"""Command-line admin tasks.

Usage:
    python -m app.cli doctor --deep          # check this machine can run the hub
    python -m app.cli create-user --email you@agency.com --admin
    python -m app.cli list-users
    python -m app.cli reset-password --email you@agency.com

Deliberately tiny — argparse from the standard library rather than a CLI
framework, because four commands do not justify a dependency.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import UserRole
from app.db.session import dispose_db, init_db, session_scope
from app.services.users import create_user, get_by_email


def _read_password(provided: str | None) -> str:
    """Prompt when no password was passed, so it never lands in shell history."""
    if provided:
        return provided
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise AppError("Passwords do not match.")
    return first


async def _create_user(args: argparse.Namespace) -> None:
    password = _read_password(args.password)
    async with session_scope() as session:
        user = await create_user(
            session,
            email=args.email,
            password=password,
            full_name=args.name,
            role=UserRole.ADMIN.value if args.admin else UserRole.MEMBER.value,
        )
        print(f"Created {user.email} ({user.role}).")


async def _list_users(_args: argparse.Namespace) -> None:
    from sqlalchemy import select

    from app.db.models import User

    async with session_scope() as session:
        users = (
            (await session.execute(select(User).order_by(User.created_at)))
            .scalars()
            .all()
        )

    if not users:
        print("No users yet. Create one with: python -m app.cli create-user --email …")
        return

    print(f"{'EMAIL':<38} {'ROLE':<8} {'ACTIVE':<7} CREATED")
    for user in users:
        active = "yes" if user.is_active else "no"
        print(
            f"{user.email:<38} {user.role:<8} {active:<7} "
            f"{user.created_at:%Y-%m-%d}"
        )


async def _reset_password(args: argparse.Namespace) -> None:
    password = _read_password(args.password)
    async with session_scope() as session:
        user = await get_by_email(session, args.email)
        if user is None:
            raise AppError(f"No account for {args.email}.")
        user.hashed_password = hash_password(password)
        session.add(user)
        print(f"Password updated for {user.email}.")


async def _doctor(args: argparse.Namespace) -> None:
    from app.diagnostics import render, run_diagnostics

    report = await run_diagnostics(deep=args.deep)
    print(render(report))
    if not report.ok:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor", help="Check this machine can run the hub"
    )
    doctor.add_argument(
        "--deep",
        action="store_true",
        help="Also download the speech model and transcribe a test clip "
        "(slow the first time, but proves the whole chain works)",
    )
    doctor.set_defaults(handler=_doctor)

    create = subparsers.add_parser("create-user", help="Add an account")
    create.add_argument("--email", required=True)
    create.add_argument("--password", help="Omit to be prompted (recommended)")
    create.add_argument("--name", help="Full name")
    create.add_argument("--admin", action="store_true", help="Grant admin rights")
    create.set_defaults(handler=_create_user)

    listing = subparsers.add_parser("list-users", help="Show all accounts")
    listing.set_defaults(handler=_list_users)

    migrate = subparsers.add_parser(
        "migrate", help="Bring the database schema up to date (safe to re-run)"
    )
    # Marked so main() runs it outside the async path: Alembic drives its own
    # event loop, which cannot be started inside a running one.
    migrate.set_defaults(handler=None, synchronous=True)

    reset = subparsers.add_parser("reset-password", help="Set a new password")
    reset.add_argument("--email", required=True)
    reset.add_argument("--password", help="Omit to be prompted (recommended)")
    reset.set_defaults(handler=_reset_password)

    return parser


async def _run(args: argparse.Namespace) -> None:
    await init_db(get_settings())
    try:
        await args.handler(args)
    finally:
        await dispose_db()


def main() -> int:
    configure_logging("WARNING")  # keep CLI output to what was asked for
    args = build_parser().parse_args()
    try:
        if getattr(args, "synchronous", False):
            from app.db.migrations import upgrade_to_head

            print(f"Database schema {upgrade_to_head(get_settings())}.")
            return 0
        asyncio.run(_run(args))
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
