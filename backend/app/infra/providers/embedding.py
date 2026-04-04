import httpx
from typing import Protocol


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    def __init__(self, base_url: str, model: str, dims: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dims = dims

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text}, timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings
