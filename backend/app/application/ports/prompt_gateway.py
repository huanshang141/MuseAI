from typing import Protocol


class PromptGateway(Protocol):
    async def render(self, key: str, variables: dict[str, str]) -> str | None: ...

    async def get(self, key: str) -> str | None: ...
