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
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
    verify_password_func: Callable[[str, str], bool],
) -> User | None:
    user = await get_user_by_email(session, email)

    if user is None:
        return None

    if not verify_password_func(password, user.password_hash):
        return None

    return user


def create_access_token(user_id: str, jwt_handler) -> str:
    return jwt_handler.create_token(user_id)
