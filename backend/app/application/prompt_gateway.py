"""PromptGateway - Protocol for prompt rendering in deep modules.

This module defines the PromptGateway protocol that allows deep modules
(workflows, infra) to access prompts without directly importing from app.main.
"""

from typing import Protocol


class PromptGateway(Protocol):
    """Protocol for rendering prompts with variable substitution.

    This gateway provides a clean interface for deep modules to access
    prompts without coupling to app.main or specific implementations.

    Implementations should handle:
    - Prompt lookup by key
    - Variable substitution
    - Fallback behavior when prompts are not found
    """

    async def render(self, key: str, variables: dict[str, str]) -> str | None:
        """Render a prompt with the given variables.

        Args:
            key: Unique prompt key
            variables: Dictionary of variables to substitute in the template

        Returns:
            Rendered prompt content if found, None otherwise
        """
        ...

    async def get(self, key: str) -> str | None:
        """Get raw prompt content without rendering.

        Args:
            key: Unique prompt key

        Returns:
            Raw prompt content if found, None otherwise
        """
        ...
