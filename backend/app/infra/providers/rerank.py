"""Rerank服务提供者模块。

支持OpenAI兼容格式的Rerank API。
"""

import asyncio
import time
from types import TracebackType
from typing import Any, Protocol, Self

import httpx
from loguru import logger
from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from app.config.settings import Settings
from app.domain.exceptions import LLMError


class RerankRequest(BaseModel):
    """Rerank请求模型。"""

    query: str
    documents: list[str]
    top_n: int = 5


class RerankResult(BaseModel):
    """Rerank结果模型。"""

    index: int
    relevance_score: float
    document: str


class RerankResponse(BaseModel):
    """Rerank响应模型。"""

    results: list[RerankResult]
    model: str
    duration_ms: int


class RerankProvider(Protocol):
    """Rerank服务协议。"""

    async def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]:
        """对文档进行重排序。"""
        ...


class OpenAICompatibleRerankProvider:
    """OpenAI兼容格式的Rerank服务提供者。"""

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
        """从配置创建Rerank提供者实例。"""
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
        """关闭客户端连接。"""
        await self._client.aclose()

    async def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]:
        """对文档进行重排序。

        Args:
            query: 查询文本
            documents: 待排序的文档列表
            top_n: 返回前N个结果

        Returns:
            按相关性排序的结果列表

        Raises:
            LLMError: 当API调用失败时抛出
        """
        if not documents:
            return []

        start_time = time.time()
        last_error: Exception | None = None

        # 构建请求数据
        request_data = RerankRequest(
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )

        for attempt in range(self.max_retries):
            try:
                # 调用Rerank API
                response = await self._client.post(
                    "/rerank",
                    json=request_data.model_dump(),
                )
                response.raise_for_status()

                duration_ms = int((time.time() - start_time) * 1000)
                logger.debug(f"Rerank completed in {duration_ms}ms")

                # 解析响应
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
        """解析API响应。

        支持多种响应格式：
        1. Jina格式: {"results": [{"index": 0, "relevance_score": 0.9, "document": "..."}]}
        2. Cohere格式: {"results": [{"index": 0, "relevance_score": 0.9}]}
        3. 自定义格式: 同Jina格式
        """
        results = []

        # 处理results数组
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

        # 按相关性分数降序排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results


class MockRerankProvider:
    """用于测试的Mock Rerank提供者。"""

    async def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]:
        """返回基于简单字符串匹配的模拟结果。"""
        if not documents:
            return []

        results = []
        query_lower = query.lower()

        for idx, doc in enumerate(documents):
            # 简单的相似度计算：查询词在文档中出现的比例
            doc_lower = doc.lower()
            score = sum(1 for word in query_lower.split() if word in doc_lower) / max(len(query_lower.split()), 1)

            results.append(
                RerankResult(
                    index=idx,
                    relevance_score=score,
                    document=doc,
                )
            )

        # 排序并返回top_n
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_n]
