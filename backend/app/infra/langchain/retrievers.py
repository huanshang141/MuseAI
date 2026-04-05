from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.application.retrieval import rrf_fusion


class RRFRetriever(BaseRetriever):
    """RRF 融合检索器"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    es_client: Any
    embeddings: Any
    top_k: int = 5
    rrf_k: int = 60

    def _get_relevant_documents(self, query: str) -> list[Document]:
        raise NotImplementedError(
            "Sync retrieval not supported in async context. Use _aget_relevant_documents instead."
        )

    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        query_vector = await self.embeddings.aembed_query(query)

        dense_results = await self.es_client.search_dense(query_vector, self.top_k * 2)
        bm25_results = await self.es_client.search_bm25(query, self.top_k * 2)

        fused = rrf_fusion(dense_results, bm25_results, k=self.rrf_k)

        documents = []
        for item in fused[: self.top_k]:
            doc = Document(
                page_content=item.get("content", ""),
                metadata={
                    "chunk_id": item.get("chunk_id"),
                    "document_id": item.get("document_id"),
                    "chunk_level": item.get("chunk_level"),
                    "source": item.get("source"),
                    "rrf_score": item.get("rrf_score"),
                },
            )
            documents.append(doc)

        return documents
