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
                        f"Embedding dimension mismatch: "
                        f"expected {self.dims}, got {len(embedding)}"
                    )

                return embedding
            except httpx.HTTPStatusError as e:
                last_error = e
                if self._should_retry(e) and attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Embedding attempt {attempt + 1} failed "
                        f"with HTTP {e.response.status_code}, retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Embedding service returned error: "
                        f"{e.response.status_code}"
                    ) from e
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Embedding attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Embedding service at {self.base_url} "
                        f"timed out after {self.max_retries} attempts"
                    ) from e
            except httpx.ConnectTimeout as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Embedding attempt {attempt + 1} "
                        f"connection timed out, retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Failed to connect to embedding service "
                        f"at {self.base_url} after {self.max_retries} attempts"
                    ) from e

        raise RuntimeError(
            f"Embedding failed after {self.max_retries} attempts: "
            f"{last_error}"
        ) from last_error

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 20,
        max_concurrency: int = 5,
    ) -> list[list[float]]:
        if not texts:
            return []

        semaphore = asyncio.Semaphore(max_concurrency)

        async def embed_batch_chunk(
            chunk: list[str],
        ) -> list[list[float]]:
            async with semaphore:
                last_error: Exception | None = None
                for attempt in range(self.max_retries):
                    try:
                        response = await self.client.post(
                            f"{self.base_url}/api/embed",
                            json={"model": self.model, "input": chunk},
                        )
                        response.raise_for_status()
                        data = response.json()
                        embeddings = data.get("embeddings", [])
                        if len(embeddings) != len(chunk):
                            raise ValueError(
                                f"Batch count mismatch: "
                                f"expected {len(chunk)}, got {len(embeddings)}"
                            )
                        for i, emb in enumerate(embeddings):
                            if len(emb) != self.dims:
                                raise ValueError(
                                    f"Dimension mismatch at {i}: "
                                    f"expected {self.dims}, got {len(emb)}"
                                )
                        return embeddings
                    except (
                        httpx.TimeoutException,
                        httpx.HTTPStatusError,
                    ) as e:
                        last_error = e
                        if self._should_retry(e) and attempt < self.max_retries - 1:
                            delay = self.retry_delay * (2**attempt)
                            logger.warning(
                                f"Batch attempt {attempt + 1} failed, "
                                f"retrying in {delay}s"
                            )
                            await asyncio.sleep(delay)
                        else:
                            raise RuntimeError(
                                f"Batch embedding failed: {last_error}"
                            ) from e
                raise RuntimeError(
                    f"Batch failed after {self.max_retries} attempts: "
                    f"{last_error}"
                ) from last_error

        batches = [
            texts[i : i + batch_size]
            for i in range(0, len(texts), batch_size)
        ]

        results = await asyncio.gather(
            *[embed_batch_chunk(b) for b in batches],
            return_exceptions=True,
        )

        all_embeddings = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise RuntimeError(
                    f"Failed to embed batch at index {i}: {result}"
                ) from result
            all_embeddings.extend(result)

        return all_embeddings
