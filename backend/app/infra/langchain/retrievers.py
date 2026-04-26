import asyncio
from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.domain.services.retrieval import rrf_fusion


class RRFRetriever(BaseRetriever):
    """RRF 融合检索器 - DEPRECATED.

    Use UnifiedRetriever instead.
    """

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

        # 并行执行 dense 和 BM25 检索
        dense_results, bm25_results = await asyncio.gather(
            self.es_client.search_dense(query_vector, self.top_k * 2),
            self.es_client.search_bm25(query, self.top_k * 2),
        )

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


class UnifiedRetriever(BaseRetriever):
    """统一检索器，支持搜索所有内容类型（文档、展品等）"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    es_client: Any
    embeddings: Any
    top_k: int = 5
    rrf_k: int = 60
    source_types: list[str] | None = None

    def _get_relevant_documents(self, query: str) -> list[Document]:
        raise NotImplementedError(
            "Sync retrieval not supported in async context. Use _aget_relevant_documents instead."
        )

    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        """异步检索所有内容类型，使用 RRF 融合 dense 和 BM25 结果

        Args:
            query: 查询文本

        Returns:
            包含各种内容类型的 Document 列表，按 RRF 分数排序
        """
        query_vector = await self.embeddings.aembed_query(query)

        # 并行执行 dense 和 BM25 检索以提升性能
        dense_results, bm25_results = await asyncio.gather(
            self.es_client.search_dense(
                query_vector, self.top_k * 2, source_types=self.source_types
            ),
            self.es_client.search_bm25(
                query, self.top_k * 2, source_types=self.source_types
            ),
        )
        fused_results = rrf_fusion(
            dense_results,
            bm25_results,
            k=self.rrf_k,
            deduplicate_by="source_id",
            top_k=self.top_k,
        )

        documents = []
        for item in fused_results:
            doc = self._to_document(item)
            documents.append(doc)

        return documents

    def _to_document(self, item: dict[str, Any]) -> Document:
        """将 ES 结果转换为 LangChain Document

        Args:
            item: ES 搜索结果项

        Returns:
            LangChain Document 对象
        """
        metadata = {
            "chunk_id": item.get("chunk_id"),
            "source_id": item.get("source_id"),
            "source_type": item.get("source_type"),
            "chunk_level": item.get("chunk_level"),
            "rrf_score": item.get("rrf_score"),
            "parent_chunk_id": item.get("parent_chunk_id"),
        }
        if item.get("source"):
            metadata["source"] = item.get("source")
        elif item.get("metadata", {}).get("filename"):
            metadata["source"] = item["metadata"]["filename"]
        elif item.get("metadata", {}).get("name"):
            metadata["source"] = item["metadata"]["name"]
        elif item.get("source_id"):
            metadata["source"] = item.get("source_id")
        else:
            metadata["source"] = None
        return Document(
            page_content=item.get("content", ""),
            metadata=metadata,
        )


class ExhibitAwareRetriever(BaseRetriever):
    """展品感知检索器，支持文档块和展品信息的混合检索 - DEPRECATED.

    Use UnifiedRetriever instead.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    es_client: Any
    embeddings: Any
    top_k: int = 5
    rrf_k: int = 60
    include_exhibits: bool = True
    exhibit_weight: float = 1.0

    def _get_relevant_documents(self, query: str) -> list[Document]:
        raise NotImplementedError(
            "Sync retrieval not supported in async context. Use _aget_relevant_documents instead."
        )

    async def _aget_relevant_documents(
        self, query: str, *, exhibit_filters: dict[str, Any] | None = None
    ) -> list[Document]:
        """异步检索文档块和展品信息

        Args:
            query: 查询文本
            exhibit_filters: 展品过滤条件，可选的 category, hall, floor 过滤

        Returns:
            包含文档块和展品的 Document 列表，按 RRF 分数排序
        """
        query_vector = await self.embeddings.aembed_query(query)

        # 并行执行 dense 和 BM25 检索
        dense_results, bm25_results = await asyncio.gather(
            self.es_client.search_dense(query_vector, self.top_k * 2),
            self.es_client.search_bm25(query, self.top_k * 2),
        )
        fused_chunks = rrf_fusion(dense_results, bm25_results, k=self.rrf_k)

        all_results: list[dict[str, Any]] = []
        for item in fused_chunks:
            item["doc_type"] = "chunk"
            all_results.append(item)

        # 如果启用展品检索，搜索展品
        if self.include_exhibits:
            exhibit_results = await self.es_client.search_exhibits(
                query_vector, top_k=self.top_k, filters=exhibit_filters
            )

            for rank, exhibit in enumerate(exhibit_results, start=1):
                # 为展品计算加权 RRF 分数
                rrf_score = self.exhibit_weight / (self.rrf_k + rank)
                exhibit["rrf_score"] = rrf_score
                exhibit["doc_type"] = "exhibit"
                all_results.append(exhibit)

        # 按分数排序并返回 top_k
        all_results.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)

        documents = []
        for item in all_results[: self.top_k]:
            doc_type = item.get("doc_type", "chunk")

            if doc_type == "exhibit":
                # 构建展品 Document
                name = item.get("name", "")
                description = item.get("description", "")
                category = item.get("category", "")
                hall = item.get("hall", "")
                era = item.get("era", "")
                floor = item.get("floor", "")
                exhibit_id = item.get("exhibit_id", "")

                page_content = f"展品: {name}\n描述: {description}\n类别: {category}\n展厅: {hall}\n年代: {era}"

                doc = Document(
                    page_content=page_content,
                    metadata={
                        "exhibit_id": exhibit_id,
                        "name": name,
                        "category": category,
                        "hall": hall,
                        "floor": floor,
                        "doc_type": "exhibit",
                        "rrf_score": item.get("rrf_score"),
                    },
                )
            else:
                # 构建文档块 Document
                doc = Document(
                    page_content=item.get("content", ""),
                    metadata={
                        "chunk_id": item.get("chunk_id"),
                        "document_id": item.get("document_id"),
                        "chunk_level": item.get("chunk_level"),
                        "source": item.get("source"),
                        "doc_type": "chunk",
                        "rrf_score": item.get("rrf_score"),
                    },
                )
            documents.append(doc)

        return documents
