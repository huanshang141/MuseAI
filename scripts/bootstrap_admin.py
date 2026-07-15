#!/usr/bin/env python3
"""Bootstrap script to create an admin user.

Usage:
    $env:MUSEAI_ADMIN_PASSWORD = "<password>"
    python scripts/bootstrap_admin.py --email admin@museai.local

Environment variables:
    DATABASE_URL: PostgreSQL connection string (required)
    MUSEAI_ADMIN_PASSWORD: Preferred non-interactive password source (optional)
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.infra.postgres.models import User
from app.infra.security.password import hash_password

MIN_PASSWORD_LENGTH = 12


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters, got {len(password)}"
        )
    requirements = {
        "an uppercase letter": any(char.isupper() for char in password),
        "a lowercase letter": any(char.islower() for char in password),
        "a digit": any(char.isdigit() for char in password),
        "a special character": any(not char.isalnum() and not char.isspace() for char in password),
    }
    missing = [label for label, satisfied in requirements.items() if not satisfied]
    if missing:
        raise ValueError("Password must contain " + ", ".join(missing))


def _resolve_password(cli_password: str | None) -> str:
    password = cli_password or os.environ.get("MUSEAI_ADMIN_PASSWORD")
    if password is None:
        password = getpass.getpass("Admin password: ")
    if not password:
        raise ValueError("Password cannot be empty")
    return password


async def bootstrap_admin(
    database_url: str,
    email: str,
    password: str,
) -> None:
    _validate_password(password)

    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_maker() as session:
            admin_result = await session.execute(
                select(User).where(User.role == "admin").limit(1)
            )
            existing_admin = admin_result.scalar_one_or_none()
            if existing_admin is not None:
                if existing_admin.email == email:
                    print(f"User '{email}' is already the configured admin. Nothing to do.")
                    return
                raise ValueError(
                    "An administrator account already exists. "
                    "Refusing to create a second administrator."
                )

            user_result = await session.execute(select(User).where(User.email == email))
            existing_user = user_result.scalar_one_or_none()

            if existing_user is not None:
                existing_user.role = "admin"
                existing_user.password_hash = hash_password(password)
                await session.commit()
                print(f"Promoted existing user '{email}' to admin and refreshed its password.")
                return

            password_hash = hash_password(password)
            user_id = os.urandom(16).hex()
            user = User(id=user_id, email=email, password_hash=password_hash, role="admin")
            session.add(user)
            await session.commit()
            print(f"Created admin user: id={user_id}, email={email}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap an admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument(
        "--password",
        help="Admin password (discouraged: visible in process history); prefer MUSEAI_ADMIN_PASSWORD",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is required")
        sys.exit(1)

    try:
        password = _resolve_password(args.password)
        asyncio.run(bootstrap_admin(database_url, args.email, password))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
