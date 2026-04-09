#!/usr/bin/env python3
"""
Development script to seed a test user in the database.

This script is intended for development/testing purposes only.
Do not use in production environments.

Usage:
    python scripts/seed_dev_user.py

Environment variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.infra.postgres.models import User


DEFAULT_USER_ID = "user-001"
DEFAULT_USER_EMAIL = "test@museai.local"
import bcrypt
DEFAULT_PASSWORD_HASH = bcrypt.hashpw(os.environ.get("DEV_PASSWORD", "dev123").encode(), bcrypt.gensalt()).decode()


async def seed_dev_user(database_url: str, user_id: str | None = None, email: str | None = None) -> None:
    """Create a development test user if it doesn't exist."""
    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        user_id = user_id or DEFAULT_USER_ID
        email = email or DEFAULT_USER_EMAIL

        # Check if user already exists
        result = await session.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})
        if result.scalar() is not None:
            print(f"User '{user_id}' already exists. Skipping.")
            return

        # Create the user
        user = User(id=user_id, email=email, password_hash=DEFAULT_PASSWORD_HASH)
        session.add(user)
        await session.commit()
        print(f"Created dev user: id={user_id}, email={email}")

    await engine.dispose()


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is required")
        sys.exit(1)

    asyncio.run(seed_dev_user(database_url))


if __name__ == "__main__":
    main()
