from typing import Any
from collections.abc import AsyncGenerator


class MockEmbeddingProvider:
    def __init__(self, dims: int = 768):
        self.dims = dims

    async def embed(self, text: str) -> list[float]:
        return [0.1] * self.dims

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dims for _ in texts]


class MockLLMProvider:
    async def generate(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "content": "This is a mock response for testing.",
            "model": "mock-model",
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "duration_ms": 100,
        }

    async def generate_stream(self, messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
        for chunk in ["Mock ", "stream ", "response."]:
            yield chunk
