# backend/app/infra/postgres/adapters/auth_repository.py
"""PostgreSQL adapter for user repository.

This adapter implements the UserRepositoryPort protocol using SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import User


class PostgresUserRepository:
    """PostgreSQL implementation of UserRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """Initialize with async session.

        Args:
            session: SQLAlchemy async session for database operations.
        """
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address.

        Args:
            email: The email address to search for.

        Returns:
            The User ORM instance if found, None otherwise.
        """
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        """Retrieve a user by their unique identifier.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            The User ORM instance if found, None otherwise.
        """
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, user: User) -> None:
        """Add a new user to the repository.

        Args:
            user: The User ORM instance to add.
        """
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
