import asyncio
import time
from types import TracebackType
from typing import Any, Self

import httpx
from loguru import logger

from app.config.settings import Settings
from app.domain.exceptions import LLMError
from app.infra.providers.rerank.base import BaseRerankProvider, RerankRequest, RerankResult


class OpenAICompatibleRerankProvider(BaseRerankProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Self | None:
        if not settings.RERANK_BASE_URL:
            return None
        return cls(
            base_url=settings.RERANK_BASE_URL,
            api_key=settings.RERANK_API_KEY,
            model=settings.RERANK_MODEL,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]:
        if not documents:
            return []

        start_time = time.time()
        last_error: Exception | None = None

        request_data = RerankRequest(
            model=self.model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )

        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    "/rerank",
                    json=request_data.model_dump(),
                )
                response.raise_for_status()

                duration_ms = int((time.time() - start_time) * 1000)
                logger.debug(f"Rerank completed in {duration_ms}ms")

                data = response.json()
                results = self._parse_response(data)
                return results[:top_n]

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"Rerank attempt {attempt + 1} failed with HTTP error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Rerank attempt {attempt + 1} failed with request error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
            except Exception as e:
                last_error = e
                logger.warning(f"Rerank attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))

        raise LLMError(f"Rerank failed after {self.max_retries} attempts: {last_error}") from last_error

    def _parse_response(self, data: dict[str, Any]) -> list[RerankResult]:
        results = []

        raw_results = data.get("results", [])
        for item in raw_results:
            if isinstance(item, dict):
                score = item.get("relevance_score", item.get("score", 0.0))
                if score is None:
                    score = 0.0
                result = RerankResult(
                    index=item.get("index", 0),
                    relevance_score=float(score),
                    document=item.get("document", ""),
                )
                results.append(result)

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results
