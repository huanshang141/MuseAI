from typing import Any, cast

from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import ApiError, TransportError
from loguru import logger

from app.domain.exceptions import RetrievalError


class ElasticsearchClient:
    def __init__(
        self,
        hosts: list[str],
        index_name: str = "museai_chunks_v1",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.index_name = index_name
        self.client = AsyncElasticsearch(
            hosts,
            request_timeout=timeout,
            max_retries=max_retries,
            retry_on_timeout=True,
        )

    async def __aenter__(self) -> "ElasticsearchClient":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        await self.close()

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception as e:
            logger.error(f"ES health check failed: {type(e).__name__}")
            return False

    async def create_index(self, index_name: str, dims: int = 1536) -> dict[str, Any]:
        try:
            if await self.client.indices.exists(index=index_name):
                return {"status": "already_exists"}

            mapping = {
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "document_id": {"type": "keyword"},
                        "parent_chunk_id": {"type": "keyword"},
                        "root_chunk_id": {"type": "keyword"},
                        "chunk_level": {"type": "integer"},
                        "content": {"type": "text", "analyzer": "ik_max_word"},
                        "content_vector": {"type": "dense_vector", "dims": dims, "index": True, "similarity": "cosine"},
                        "title": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "created_at": {"type": "date"},
                    }
                }
            }

            await self.client.indices.create(index=index_name, body=mapping)
            logger.info(f"Created ES index: {index_name}")
            return {"status": "created"}
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to create index {index_name}: {repr(e)}")
            raise RetrievalError(f"Failed to create index: {type(e).__name__}")

    async def index_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        try:
            chunk_id = chunk["chunk_id"]
            result = await self.client.index(index=self.index_name, id=chunk_id, document=chunk)
            return cast(dict[str, Any], result)
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to index chunk: {type(e).__name__}")
            raise RetrievalError("Failed to index chunk")

    async def search_dense(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        try:
            query = {
                "knn": {
                    "field": "content_vector",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 10,
                },
                "size": top_k,
            }

            response = await self.client.search(index=self.index_name, body=query)

            return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
        except (ApiError, TransportError) as e:
            logger.error(f"Dense search failed: {type(e).__name__}")
            raise RetrievalError("Dense search failed")

    async def search_bm25(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        try:
            query = {"query": {"match": {"content": query_text}}, "size": top_k}

            response = await self.client.search(index=self.index_name, body=query)

            return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
        except (ApiError, TransportError) as e:
            logger.error(f"BM25 search failed: {type(e).__name__}")
            raise RetrievalError("BM25 search failed")

    async def delete_by_document(self, document_id: str) -> dict[str, Any]:
        try:
            query = {"query": {"term": {"document_id": document_id}}}

            result = await self.client.delete_by_query(index=self.index_name, body=query)
            return cast(dict[str, Any], result)
        except (ApiError, TransportError) as e:
            logger.error(f"Delete by document failed: {type(e).__name__}")
            raise RetrievalError("Delete by document failed")

    async def close(self) -> None:
        try:
            await self.client.close()
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to close ES client: {type(e).__name__}")
