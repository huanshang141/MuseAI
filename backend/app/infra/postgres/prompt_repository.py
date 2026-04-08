# backend/app/infra/postgres/prompt_repository.py
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities import Prompt, PromptVersion
from app.domain.exceptions import EntityNotFoundError, PromptNotFoundError
from app.domain.value_objects import PromptId

from .models import Prompt as PromptORM
from .models import PromptVersion as PromptVersionORM


class PostgresPromptRepository:
    """PostgreSQL implementation of PromptRepository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, orm: PromptORM) -> Prompt:
        """Convert PromptORM to Prompt domain entity."""
        return Prompt(
            id=PromptId(orm.id),
            key=orm.key,
            name=orm.name,
            description=orm.description,
            category=orm.category,
            content=orm.content,
            variables=list(orm.variables) if orm.variables else [],
            is_active=orm.is_active,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            current_version=max(v.version for v in orm.versions) if orm.versions else 1,
        )

    def _version_to_entity(self, orm: PromptVersionORM) -> PromptVersion:
        """Convert PromptVersionORM to PromptVersion domain entity."""
        return PromptVersion(
            id=orm.id,
            prompt_id=PromptId(orm.prompt_id),
            version=orm.version,
            content=orm.content,
            changed_by=orm.changed_by,
            change_reason=orm.change_reason,
            created_at=orm.created_at,
        )

    async def get_by_key(self, key: str) -> Prompt | None:
        """Get a prompt by its unique key."""
        result = await self._session.execute(
            select(PromptORM)
            .options(selectinload(PromptORM.versions))
            .where(PromptORM.key == key)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def get_by_id(self, prompt_id: str) -> Prompt | None:
        """Get a prompt by its ID."""
        result = await self._session.execute(
            select(PromptORM)
            .options(selectinload(PromptORM.versions))
            .where(PromptORM.id == prompt_id)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def list_all(
        self,
        category: str | None = None,
        include_inactive: bool = False,
    ) -> list[Prompt]:
        """List all prompts with optional filtering.

        Args:
            category: Filter by category (optional)
            include_inactive: Include inactive prompts (default: False)

        Returns:
            List of Prompt entities
        """
        query = select(PromptORM).options(selectinload(PromptORM.versions))

        if category is not None:
            query = query.where(PromptORM.category == category)

        if not include_inactive:
            query = query.where(PromptORM.is_active.is_(True))

        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def create(
        self,
        key: str,
        name: str,
        category: str,
        content: str,
        description: str | None = None,
        variables: list[dict[str, str]] | None = None,
    ) -> Prompt:
        """Create a new prompt with initial version.

        Args:
            key: Unique prompt key
            name: Human-readable name
            category: Prompt category
            content: Prompt content/template
            description: Optional description
            variables: Optional list of variable definitions

        Returns:
            Created Prompt entity
        """
        now = datetime.now(UTC)
        prompt_id = str(uuid4())

        # Create prompt
        orm = PromptORM(
            id=prompt_id,
            key=key,
            name=name,
            description=description,
            category=category,
            content=content,
            variables=variables or [],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._session.add(orm)

        # Create initial version
        version_orm = PromptVersionORM(
            id=str(uuid4()),
            prompt_id=prompt_id,
            version=1,
            content=content,
            changed_by=None,
            change_reason="Initial version",
            created_at=now,
        )
        self._session.add(version_orm)

        await self._session.flush()
        return self._to_entity(orm)

    async def update(
        self,
        key: str,
        content: str,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> Prompt:
        """Update a prompt's content and create a new version.

        Args:
            key: Prompt key to update
            content: New content
            changed_by: User who made the change
            change_reason: Reason for the change

        Returns:
            Updated Prompt entity

        Raises:
            PromptNotFoundError: If prompt not found
        """
        result = await self._session.execute(
            select(PromptORM)
            .options(selectinload(PromptORM.versions))
            .where(PromptORM.key == key)
        )
        orm = result.scalar_one_or_none()

        if orm is None:
            raise PromptNotFoundError(f"Prompt not found: {key}")

        # Get current max version
        version_result = await self._session.execute(
            select(func.max(PromptVersionORM.version)).where(
                PromptVersionORM.prompt_id == orm.id
            )
        )
        max_version = version_result.scalar() or 0
        new_version = max_version + 1

        # Update prompt content
        orm.content = content
        orm.updated_at = datetime.now(UTC)

        # Create new version record
        version_orm = PromptVersionORM(
            id=str(uuid4()),
            prompt_id=orm.id,
            version=new_version,
            content=content,
            changed_by=changed_by,
            change_reason=change_reason,
            created_at=datetime.now(UTC),
        )
        self._session.add(version_orm)

        await self._session.flush()
        return self._to_entity(orm)

    async def get_version(self, key: str, version: int) -> PromptVersion | None:
        """Get a specific version of a prompt.

        Args:
            key: Prompt key
            version: Version number

        Returns:
            PromptVersion entity or None if not found
        """
        result = await self._session.execute(
            select(PromptVersionORM)
            .join(PromptORM)
            .where(PromptORM.key == key)
            .where(PromptVersionORM.version == version)
        )
        orm = result.scalar_one_or_none()
        return self._version_to_entity(orm) if orm else None

    async def list_versions(
        self,
        key: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[PromptVersion]:
        """List versions of a prompt.

        Args:
            key: Prompt key
            skip: Number of versions to skip
            limit: Maximum number of versions to return

        Returns:
            List of PromptVersion entities (newest first)
        """
        result = await self._session.execute(
            select(PromptVersionORM)
            .join(PromptORM)
            .where(PromptORM.key == key)
            .order_by(PromptVersionORM.version.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._version_to_entity(orm) for orm in result.scalars().all()]

    async def count_versions(self, key: str) -> int:
        """Count versions of a prompt.

        Args:
            key: Prompt key

        Returns:
            Number of versions
        """
        result = await self._session.execute(
            select(func.count(PromptVersionORM.id))
            .join(PromptORM)
            .where(PromptORM.key == key)
        )
        return result.scalar() or 0

    async def rollback_to_version(
        self,
        key: str,
        version: int,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> Prompt:
        """Rollback a prompt to a specific version.

        This creates a new version with the content from the specified version.

        Args:
            key: Prompt key
            version: Version to rollback to
            changed_by: User who performed the rollback
            change_reason: Reason for the rollback

        Returns:
            Updated Prompt entity

        Raises:
            PromptNotFoundError: If prompt not found
            EntityNotFoundError: If version not found
        """
        prompt_result = await self._session.execute(
            select(PromptORM)
            .options(selectinload(PromptORM.versions))
            .where(PromptORM.key == key)
        )
        prompt_orm = prompt_result.scalar_one_or_none()

        if prompt_orm is None:
            raise PromptNotFoundError(f"Prompt not found: {key}")

        # Get the version to rollback to
        version_result = await self._session.execute(
            select(PromptVersionORM)
            .where(PromptVersionORM.prompt_id == prompt_orm.id)
            .where(PromptVersionORM.version == version)
        )
        version_orm = version_result.scalar_one_or_none()

        if version_orm is None:
            raise EntityNotFoundError(
                f"Version {version} not found for prompt '{key}'"
            )

        # Get current max version
        max_version_result = await self._session.execute(
            select(func.max(PromptVersionORM.version)).where(
                PromptVersionORM.prompt_id == prompt_orm.id
            )
        )
        max_version = max_version_result.scalar() or 0
        new_version = max_version + 1

        # Update prompt content to the old version's content
        prompt_orm.content = version_orm.content
        prompt_orm.updated_at = datetime.now(UTC)

        # Create new version record for the rollback
        new_version_orm = PromptVersionORM(
            id=str(uuid4()),
            prompt_id=prompt_orm.id,
            version=new_version,
            content=version_orm.content,
            changed_by=changed_by,
            change_reason=change_reason or f"Rollback to version {version}",
            created_at=datetime.now(UTC),
        )
        self._session.add(new_version_orm)

        await self._session.flush()
        return self._to_entity(prompt_orm)
