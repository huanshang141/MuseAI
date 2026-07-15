from collections.abc import Callable

from app.application.ports.repositories import UserRepositoryPort
from app.domain.entities import User as UserEntity


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
    "get_user_by_id",
    "authenticate_user",
    "create_access_token",
    "verify_token",
    "UserRepositoryPort",
]
