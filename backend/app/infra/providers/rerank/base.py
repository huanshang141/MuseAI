from abc import ABC, abstractmethod

from pydantic import BaseModel


class RerankRequest(BaseModel):
    model: str
    query: str
    documents: list[str]
    top_n: int = 5


class RerankResult(BaseModel):
    index: int
    relevance_score: float
    document: str


class RerankResponse(BaseModel):
    results: list[RerankResult]
    model: str
    duration_ms: int


class BaseRerankProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
