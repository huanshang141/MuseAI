"""PromptService - Application service for prompt management."""

from loguru import logger

from app.domain.entities import Prompt, PromptVersion
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.adapters import PostgresPromptRepository


class PromptService:
    """Application service for managing prompts.

    This service coordinates between the cache and repository layers,
    providing a unified interface for prompt operations.

    The service uses:
    - PromptCache for fast read access to active prompts
    - PostgresPromptRepository for database persistence
    """

    def __init__(
        self,
        repository: PostgresPromptRepository,
        cache: PromptCache,
    ):
        """Initialize the PromptService.

        Args:
            repository: PostgresPromptRepository for database operations
            cache: PromptCache for in-memory caching
        """
        self._repository = repository
        self._cache = cache

    async def get_prompt(self, key: str) -> Prompt | None:
        """Get a prompt by key from cache.

        The cache handles cache misses by loading from the repository.

        Args:
            key: Unique prompt key

        Returns:
            Prompt if found (and active), None otherwise
        """
        return await self._cache.get(key)

    async def render_prompt(self, key: str, variables: dict[str, str]) -> str | None:
        """Get a prompt and render it with the provided variables.

        Args:
            key: Unique prompt key
            variables: Dictionary of variables to substitute in the template

        Returns:
            Rendered prompt content if found, None otherwise

        Raises:
            PromptVariableError: If a required variable is missing
        """
        prompt = await self._cache.get(key)
        if prompt is None:
            return None
        return prompt.render(variables)

    async def list_prompts(
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
        return await self._repository.list_all(
            category=category,
            include_inactive=include_inactive,
        )

    async def update_prompt(
        self,
        key: str,
        content: str,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> Prompt:
        """Update a prompt's content and refresh the cache.

        This creates a new version of the prompt in the database
        and refreshes the cache with the updated prompt.

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
        prompt = await self._repository.update(
            key=key,
            content=content,
            changed_by=changed_by,
            change_reason=change_reason,
        )

        # Refresh the cache with the updated prompt
        self._cache.refresh(prompt)

        logger.info(f"Updated prompt '{key}' by {changed_by}")
        return prompt

    async def get_version(self, key: str, version: int) -> PromptVersion | None:
        """Get a specific version of a prompt.

        Args:
            key: Prompt key
            version: Version number

        Returns:
            PromptVersion entity or None if not found
        """
        return await self._repository.get_version(key, version)

    async def list_versions(
        self,
        key: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PromptVersion], int]:
        """List versions of a prompt with total count.

        Args:
            key: Prompt key
            skip: Number of versions to skip
            limit: Maximum number of versions to return

        Returns:
            Tuple of (list of PromptVersion entities, total count)
        """
        versions = await self._repository.list_versions(key, skip, limit)
        total = await self._repository.count_versions(key)
        return versions, total

    async def rollback_to_version(
        self,
        key: str,
        version: int,
        changed_by: str | None = None,
    ) -> Prompt:
        """Rollback a prompt to a specific version and refresh the cache.

        This creates a new version with the content from the specified version.

        Args:
            key: Prompt key
            version: Version to rollback to
            changed_by: User who performed the rollback

        Returns:
            Updated Prompt entity

        Raises:
            PromptNotFoundError: If prompt not found
            EntityNotFoundError: If version not found
        """
        change_reason = f"Rollback to version {version}"
        prompt = await self._repository.rollback_to_version(
            key=key,
            version=version,
            changed_by=changed_by,
            change_reason=change_reason,
        )

        # Refresh the cache with the rolled-back prompt
        self._cache.refresh(prompt)

        logger.info(f"Rolled back prompt '{key}' to version {version} by {changed_by}")
        return prompt

    async def reload_cache(self, key: str | None = None) -> None:
        """Reload prompt(s) into cache.

        If key is provided, only that prompt is reloaded from the database.
        If key is None, all prompts are reloaded.

        Args:
            key: Optional prompt key to reload (None = reload all)
        """
        if key is not None:
            # Reload single prompt
            prompt = await self._repository.get_by_key(key)
            if prompt is not None:
                self._cache.refresh(prompt)
                logger.info(f"Reloaded prompt '{key}' into cache")
            else:
                # Prompt doesn't exist or is inactive, remove from cache
                self._cache.invalidate(key)
                logger.info(f"Removed prompt '{key}' from cache (not found)")
        else:
            # Reload all prompts
            await self._cache.load_all()
            logger.info("Reloaded all prompts into cache")

    async def create_prompt(
        self,
        key: str,
        name: str,
        category: str,
        content: str,
        description: str | None = None,
        variables: list[dict[str, str]] | None = None,
    ) -> Prompt:
        """Create a new prompt and add it to the cache.

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
        prompt = await self._repository.create(
            key=key,
            name=name,
            category=category,
            content=content,
            description=description,
            variables=variables,
        )

        # Add the new prompt to cache (it's active by default)
        self._cache.refresh(prompt)

        logger.info(f"Created prompt '{key}' in category '{category}'")
        return prompt
