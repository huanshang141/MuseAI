# backend/app/application/auth_service.py
import uuid
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import User


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    hash_password_func: Callable[[str], str],
) -> User:
    """Register a new user with the given email and password.

    Args:
        session: AsyncSession for database operations.
        email: The user's email address.
        password: The user's plain text password.
        hash_password_func: Function to hash the password.

    Returns:
        The newly created User instance.
    """
    user_id = str(uuid.uuid4())
    password_hash = hash_password_func(password)

    user = User(
        id=user_id,
        email=email,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Retrieve a user by their email address.

    Args:
        session: AsyncSession for database operations.
        email: The email address to search for.

    Returns:
        The User instance if found, None otherwise.
    """
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    """Retrieve a user by their unique identifier.

    Args:
        session: AsyncSession for database operations.
        user_id: The unique identifier of the user.

    Returns:
        The User instance if found, None otherwise.
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
    verify_password_func: Callable[[str, str], bool],
) -> User | None:
    """Authenticate a user by verifying their email and password.

    Args:
        session: AsyncSession for database operations.
        email: The user's email address.
        password: The user's plain text password.
        verify_password_func: Function to verify the password against a hash.

    Returns:
        The User instance if authentication succeeds, None otherwise.
    """
    user = await get_user_by_email(session, email)

    if user is None:
        return None

    if not verify_password_func(password, user.password_hash):
        return None

    return user


def create_access_token(user_id: str, jwt_handler) -> str:
    """Create a JWT access token for a user.

    Args:
        user_id: The unique identifier of the user.
        jwt_handler: JWT handler instance with a create_token method.

    Returns:
        A JWT token string.
    """
    return jwt_handler.create_token(user_id)


def verify_token(token: str, jwt_handler) -> str | None:
    """Verify a JWT token and return the user_id if valid.

    Args:
        token: The JWT token string to verify.
        jwt_handler: JWT handler instance with a verify_token method.

    Returns:
        The user_id string if the token is valid, None otherwise.
    """
    return jwt_handler.verify_token(token)
