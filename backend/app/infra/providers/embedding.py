import asyncio
from typing import Protocol

import httpx
from loguru import logger


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
        max_retries: int = 3,
        retry_delay: float = 1.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dims = dims
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._owns_client = client is None
        self.client: httpx.AsyncClient = client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "OllamaEmbeddingProvider":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _should_retry(self, error: Exception) -> bool:
        if isinstance(error, httpx.TimeoutException):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code >= 500
        return False

    async def embed(self, text: str) -> list[float]:
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["embedding"]

                if len(embedding) != self.dims:
                    raise ValueError(
                        f"Embedding dimension mismatch: expected {self.dims}, got {len(embedding)}"
                    )

                return embedding
            except httpx.HTTPStatusError as e:
                last_error = e
                if self._should_retry(e) and attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Embedding attempt {attempt + 1}/{self.max_retries} failed "
                        f"with HTTP {e.response.status_code}, retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Embedding service returned error: {e.response.status_code}"
                    ) from e
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Embedding attempt {attempt + 1}/{self.max_retries} timed out, "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Embedding service at {self.base_url} timed out after {self.max_retries} attempts"
                    ) from e
            except httpx.ConnectTimeout as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Embedding attempt {attempt + 1}/{self.max_retries} connection timed out, "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Failed to connect to embedding service at {self.base_url} after {self.max_retries} attempts"
                    ) from e

        raise RuntimeError(f"Embedding failed after {self.max_retries} attempts: {last_error}") from last_error

    async def embed_batch(self, texts: list[str], max_concurrency: int = 5) -> list[list[float]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def embed_with_semaphore(text: str) -> list[float]:
            async with semaphore:
                return await self.embed(text)

        results = await asyncio.gather(
            *[embed_with_semaphore(text) for text in texts], return_exceptions=True
        )

        embeddings = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise RuntimeError(f"Failed to embed text at index {i}: {result}")
            embeddings.append(result)

        return embeddings
