from typing import Protocol

from app.domain.entities import Prompt


class PromptGateway(Protocol):
    async def render(self, key: str, variables: dict[str, str]) -> str | None: ...

    async def get(self, key: str) -> str | None: ...

    async def get_entity(self, key: str) -> Prompt | None: ...
