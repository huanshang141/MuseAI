"""In-memory cache for prompts with hot-reload support."""

import asyncio
from collections import OrderedDict

from loguru import logger

from app.domain.entities import Prompt
from app.infra.postgres.adapters import PostgresPromptRepository


class PromptCache:
    """In-memory cache for prompts with automatic refresh support."""

    def __init__(self, max_size: int = 100) -> None:
        self._cache: OrderedDict[str, Prompt] = OrderedDict()
        self._max_size = max_size
        self._repository: PostgresPromptRepository | None = None
        self._lock = asyncio.Lock()

    def set_repository(self, repository: PostgresPromptRepository) -> None:
        """Set the repository for cache misses.

        Args:
            repository: PostgresPromptRepository instance for database access
        """
        self._repository = repository

    async def load_all(self) -> None:
        """Load all active prompts into cache.

        Raises:
            RuntimeError: If repository is not set
        """
        if not self._repository:
            raise RuntimeError("Repository not set")

        prompts = await self._repository.list_all(include_inactive=False)
        async with self._lock:
            self._cache = OrderedDict((p.key, p) for p in prompts)
            self._evict_if_needed()
        logger.info(f"Loaded {len(self._cache)} prompts into cache")

    async def get(self, key: str) -> Prompt | None:
        """Get a prompt from cache, loading from DB on miss.

        Args:
            key: Prompt key to look up

        Returns:
            Prompt if found (and active), None otherwise
        """
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]

        if self._repository:
            prompt = await self._repository.get_by_key(key)
            if prompt and prompt.is_active:
                async with self._lock:
                    self._cache[key] = prompt
                    self._cache.move_to_end(key)
                    self._evict_if_needed()
                return prompt

        return None

    async def refresh(self, prompt: Prompt) -> None:
        """Refresh a single prompt in cache.

        If the prompt is active, it's added/updated in cache.
        If inactive, it's removed from cache if present.

        Args:
            prompt: Prompt entity to cache
        """
        key = prompt.key
        async with self._lock:
            if prompt.is_active:
                self._cache[key] = prompt
                logger.info(f"Refreshed prompt in cache: {key}")
            elif key in self._cache:
                del self._cache[key]
                logger.info(f"Removed inactive prompt from cache: {key}")

    async def invalidate(self, key: str) -> None:
        """Remove a prompt from cache.

        Args:
            key: Prompt key to remove
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.info(f"Invalidated prompt from cache: {key}")

    def _evict_if_needed(self) -> None:
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all prompts from cache."""
        self._cache.clear()
        logger.info("Cleared all prompts from cache")

    def get_all_keys(self) -> list[str]:
        """Get all cached prompt keys.

        Returns:
            List of prompt keys currently in cache
        """
        return list(self._cache.keys())
