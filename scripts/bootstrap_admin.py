#!/usr/bin/env python3
"""Bootstrap script to create an admin user.

Usage:
    python scripts/bootstrap_admin.py --email admin@museai.local --password <password>

Environment variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import argparse
import asyncio
import os
import sys

from sqlalchemy import text
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


async def bootstrap_admin(
    database_url: str,
    email: str,
    password: str,
) -> None:
    _validate_password(password)

    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        result = await session.execute(
            text("SELECT 1 FROM users WHERE email = :email"), {"email": email}
        )
        if result.scalar() is not None:
            print(f"Admin user '{email}' already exists. Skipping.")
            await engine.dispose()
            return

        password_hash = hash_password(password)
        user_id = os.urandom(16).hex()
        user = User(id=user_id, email=email, password_hash=password_hash, role="admin")
        session.add(user)
        await session.commit()
        print(f"Created admin user: id={user_id}, email={email}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap an admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password (min 12 chars)")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is required")
        sys.exit(1)

    try:
        asyncio.run(bootstrap_admin(database_url, args.email, args.password))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
