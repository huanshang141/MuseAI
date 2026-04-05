import asyncio
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        dims: int,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dims = dims
        self.timeout = timeout
        # Use provided client or create one
        self._owns_client = client is None
        self.client: httpx.AsyncClient = client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "OllamaEmbeddingProvider":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self.client.aclose()

    async def embed(self, text: str) -> list[float]:
        response = await self.client.post(f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text})
        response.raise_for_status()
        data = response.json()
        embedding = data["embedding"]

        if len(embedding) != self.dims:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dims}, got {len(embedding)}")

        return embedding

    async def embed_batch(self, texts: list[str], max_concurrency: int = 5) -> list[list[float]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def embed_with_semaphore(text: str) -> list[float]:
            async with semaphore:
                return await self.embed(text)

        results = await asyncio.gather(*[embed_with_semaphore(text) for text in texts], return_exceptions=True)

        embeddings = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise RuntimeError(f"Failed to embed text at index {i}: {result}")
            embeddings.append(result)

        return embeddings
