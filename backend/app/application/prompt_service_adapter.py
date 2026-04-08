"""PromptServiceAdapter - Adapter that implements PromptGateway using PromptService.

This module provides an implementation of the PromptGateway protocol
that uses the application's PromptService for prompt operations.
"""

from loguru import logger

from app.application.prompt_gateway import PromptGateway
from app.application.prompt_service import PromptService
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.prompt_repository import PostgresPromptRepository


class PromptServiceAdapter(PromptGateway):
    """Adapter that implements PromptGateway using PromptService.

    This adapter provides the connection between the PromptGateway protocol
    (used by deep modules) and the PromptService (application layer).

    It handles the database session management internally, providing a
    simplified interface for prompt operations.
    """

    def __init__(
        self,
        prompt_cache: PromptCache,
    ):
        """Initialize the adapter with required dependencies.

        Args:
            prompt_cache: The prompt cache instance for fast reads
        """
        self._cache = prompt_cache

    async def render(self, key: str, variables: dict[str, str]) -> str | None:
        """Render a prompt with the given variables.

        Args:
            key: Unique prompt key
            variables: Dictionary of variables to substitute

        Returns:
            Rendered prompt content if found, None otherwise
        """
        from app.infra.postgres.database import get_session

        try:
            async with get_session() as session:
                repository = PostgresPromptRepository(session)
                service = PromptService(repository, self._cache)
                return await service.render_prompt(key, variables)
        except RuntimeError as e:
            # Database not initialized (e.g., during tests)
            logger.debug(f"PromptService unavailable for key '{key}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to render prompt '{key}': {e}")
            return None

    async def get(self, key: str) -> str | None:
        """Get raw prompt content without rendering.

        Args:
            key: Unique prompt key

        Returns:
            Raw prompt content if found, None otherwise
        """
        from app.infra.postgres.database import get_session

        try:
            async with get_session() as session:
                repository = PostgresPromptRepository(session)
                service = PromptService(repository, self._cache)
                prompt = await service.get_prompt(key)
                return prompt.content if prompt else None
        except RuntimeError as e:
            # Database not initialized (e.g., during tests)
            logger.debug(f"PromptService unavailable for key '{key}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to get prompt '{key}': {e}")
            return None
