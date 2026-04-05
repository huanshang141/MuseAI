
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, PrivateAttr

from app.infra.providers.embedding import OllamaEmbeddingProvider


class CustomOllamaEmbeddings(BaseModel, Embeddings):
    """包装 OllamaEmbeddingProvider 到 LangChain Embeddings 接口"""

    base_url: str
    model: str
    dims: int
    timeout: float = 60.0

    _provider: OllamaEmbeddingProvider | None = PrivateAttr(default=None)

    def _get_provider(self) -> OllamaEmbeddingProvider:
        if self._provider is None:
            self._provider = OllamaEmbeddingProvider(
                base_url=self.base_url,
                model=self.model,
                dims=self.dims,
                timeout=self.timeout,
            )
        return self._provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        return asyncio.run(self.aembed_documents(texts))

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        provider = self._get_provider()
        return await provider.embed_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        import asyncio

        return asyncio.run(self.aembed_query(text))

    async def aembed_query(self, text: str) -> list[float]:
        provider = self._get_provider()
        return await provider.embed(text)

    async def close(self) -> None:
        """Close the underlying provider."""
        if self._provider is not None:
            await self._provider.close()
            self._provider = None
