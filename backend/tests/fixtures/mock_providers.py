from collections.abc import AsyncGenerator
from typing import Any, Self

from app.infra.providers.llm import LLMResponse


class MockEmbeddingProvider:
    def __init__(self, dims: int = 768):
        self.dims = dims

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def embed(self, text: str) -> list[float]:
        return [0.1] * self.dims

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dims for _ in texts]


class MockLLMProvider:
    async def generate(self, messages: list[dict[str, Any]]) -> LLMResponse:
        return LLMResponse(
            content="This is a mock response for testing.",
            model="mock-model",
            prompt_tokens=10,
            completion_tokens=10,
            duration_ms=100,
        )

    async def generate_stream(self, messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
        for chunk in ["Mock ", "stream ", "response."]:
            yield chunk
