# backend/app/application/auth_service.py
"""Authentication service with dependency on repository port.

This service implements authentication business logic without depending
on infrastructure layer modules. It uses repository ports (protocols)
that are implemented by adapters in the infrastructure layer.
"""

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infra.postgres.models import User


async def register_user(
    user_repo: "UserRepositoryPort",
    email: str,
    password: str,
    hash_password_func: Callable[[str], str],
    admin_emails: list[str] | None = None,
) -> "User":
    """Register a new user with the given email and password.

    Args:
        user_repo: Repository implementing UserRepositoryPort for database operations.
        email: The user's email address.
        password: The user's plain text password.
        hash_password_func: Function to hash the password.
        admin_emails: List of admin email addresses. If the user's email
            is in this list, they will be assigned the "admin" role.

    Returns:
        The newly created User instance.
    """
    # Import User model locally to avoid module-level infra dependency
    from app.infra.postgres.models import User

    user_id = str(uuid.uuid4())
    password_hash = hash_password_func(password)

    # Determine role based on admin_emails list
    role = "user"
    if admin_emails and email in admin_emails:
        role = "admin"

    user = User(
        id=user_id,
        email=email,
        password_hash=password_hash,
        role=role,
    )
    await user_repo.add(user)
    return user


async def get_user_by_email(user_repo: "UserRepositoryPort", email: str) -> "User | None":
    """Retrieve a user by their email address.

    Args:
        user_repo: Repository implementing UserRepositoryPort for database operations.
        email: The email address to search for.

    Returns:
        The User instance if found, None otherwise.
    """
    return await user_repo.get_by_email(email)


async def get_user_by_id(user_repo: "UserRepositoryPort", user_id: str) -> "User | None":
    """Retrieve a user by their unique identifier.

    Args:
        user_repo: Repository implementing UserRepositoryPort for database operations.
        user_id: The unique identifier of the user.

    Returns:
        The User instance if found, None otherwise.
    """
    return await user_repo.get_by_id(user_id)


async def authenticate_user(
    user_repo: "UserRepositoryPort",
    email: str,
    password: str,
    verify_password_func: Callable[[str, str], bool],
) -> "User | None":
    """Authenticate a user by verifying their email and password.

    Args:
        user_repo: Repository implementing UserRepositoryPort for database operations.
        email: The user's email address.
        password: The user's plain text password.
        verify_password_func: Function to verify the password against a hash.

    Returns:
        The User instance if authentication succeeds, None otherwise.
    """
    user = await user_repo.get_by_email(email)

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


# Import the protocol for type hints
from app.application.ports.repositories import UserRepositoryPort  # noqa: E402

__all__ = [
    "register_user",
    "get_user_by_email",
    "get_user_by_id",
    "authenticate_user",
    "create_access_token",
    "verify_token",
    "UserRepositoryPort",
]
