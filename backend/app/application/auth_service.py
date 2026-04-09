import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.application.ports.repositories import UserRepositoryPort
from app.domain.entities import User as UserEntity


async def register_user(
    user_repo: UserRepositoryPort,
    email: str,
    password: str,
    hash_password_func: Callable[[str], str],
    admin_emails: list[str] | None = None,
) -> UserEntity:
    user_id = str(uuid.uuid4())
    password_hash = hash_password_func(password)

    role = "user"
    if admin_emails and email in admin_emails:
        role = "admin"

    now = datetime.now(UTC)
    user = UserEntity(
        id=user_id,
        email=email,
        password_hash=password_hash,
        role=role,
        created_at=now,
    )
    await user_repo.add(user)
    return user


async def get_user_by_email(user_repo: UserRepositoryPort, email: str) -> UserEntity | None:
    return await user_repo.get_by_email(email)


async def get_user_by_id(user_repo: UserRepositoryPort, user_id: str) -> UserEntity | None:
    return await user_repo.get_by_id(user_id)


async def authenticate_user(
    user_repo: UserRepositoryPort,
    email: str,
    password: str,
    verify_password_func: Callable[[str, str], bool],
) -> UserEntity | None:
    user = await user_repo.get_by_email(email)

    if user is None:
        return None

    if not verify_password_func(password, user.password_hash):
        return None

    return user


def create_access_token(user_id: str, jwt_handler) -> str:
    return jwt_handler.create_token(user_id)


def verify_token(token: str, jwt_handler) -> str | None:
    return jwt_handler.verify_token(token)


__all__ = [
    "register_user",
    "get_user_by_email",
    "get_user_by_id",
    "authenticate_user",
    "create_access_token",
    "verify_token",
    "UserRepositoryPort",
]
