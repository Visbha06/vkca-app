"""Create the initial Head Coach account for a new VKCA installation."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole  # noqa: E402
from src.models.user import User  # noqa: E402
from src.services.password_service import PasswordService  # noqa: E402

DEFAULT_EMAIL = "headcoach@vkca.test"
DEFAULT_PASSWORD = "SuperSecur3!P@ss"
DEFAULT_FIRST_NAME = "Head"
DEFAULT_LAST_NAME = "Coach"


async def seed_head_coach(
    session: AsyncSession,
    *,
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    first_name: str = DEFAULT_FIRST_NAME,
    last_name: str = DEFAULT_LAST_NAME,
) -> tuple[User, bool]:
    """Create the initial Head Coach, returning the account and creation status."""

    normalized_email = email.strip().lower()
    existing_user = await session.scalar(
        select(User).where(User.email == normalized_email)
    )
    if existing_user is not None:
        return existing_user, False

    PasswordService.validate_password_policy(password)
    user = User(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=normalized_email,
        hashed_password=PasswordService.hash_password(password),
        role=UserRole.HEAD_COACH,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--email", default=os.getenv("HEAD_COACH_EMAIL", DEFAULT_EMAIL)
    )
    parser.add_argument(
        "--password",
        default=os.getenv("HEAD_COACH_PASSWORD", DEFAULT_PASSWORD),
        help="Initial password; prefer the HEAD_COACH_PASSWORD environment variable.",
    )
    parser.add_argument(
        "--first-name",
        default=os.getenv("HEAD_COACH_FIRST_NAME", DEFAULT_FIRST_NAME),
    )
    parser.add_argument(
        "--last-name",
        default=os.getenv("HEAD_COACH_LAST_NAME", DEFAULT_LAST_NAME),
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    from src.database import AsyncSessionFactory, engine

    try:
        async with AsyncSessionFactory() as session:
            user, created = await seed_head_coach(
                session,
                email=args.email,
                password=args.password,
                first_name=args.first_name,
                last_name=args.last_name,
            )
        action = "Created" if created else "Already exists"
        print(f"{action}: {user.email} ({user.role})")
    finally:
        await engine.dispose()


def main() -> None:
    """Run the seed operation from the command line."""

    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
