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
                        # Unified schema fields
                        "chunk_id": {"type": "keyword"},
                        "source_id": {"type": "keyword"},
                        "source_type": {"type": "keyword"},
                        "chunk_level": {"type": "integer"},
                        "parent_chunk_id": {"type": "keyword"},
                        "root_chunk_id": {"type": "keyword"},
                        "start_char": {"type": "integer"},
                        "end_char": {"type": "integer"},
                        "content": {"type": "text", "analyzer": "ik_max_word"},
                        "content_vector": {"type": "dense_vector", "dims": dims, "index": True, "similarity": "cosine"},
                        # Metadata as nested object
                        "metadata": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "keyword"},
                                "filename": {"type": "keyword"},
                                "category": {"type": "keyword"},
                                "hall": {"type": "keyword"},
                                "floor": {"type": "integer"},
                                "era": {"type": "keyword"},
                                "importance": {"type": "integer"},
                                "location_x": {"type": "float"},
                                "location_y": {"type": "float"},
                            },
                        },
                        # Legacy fields for backward compatibility
                        "document_id": {"type": "keyword"},
                        "title": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        # Legacy exhibit fields
                        "doc_type": {"type": "keyword"},
                        "exhibit_id": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "hall": {"type": "keyword"},
                        "floor": {"type": "keyword"},
                    }
                }
            }

            await self.client.indices.create(index=index_name, body=mapping)
            logger.info(f"Created ES index: {index_name}")
            return {"status": "created"}
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to create index {index_name}: {repr(e)}")
            raise RetrievalError(f"Failed to create index: {type(e).__name__}") from e

    async def index_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        try:
            chunk_id = chunk["chunk_id"]
            result = await self.client.index(index=self.index_name, id=chunk_id, document=chunk)
            return cast(dict[str, Any], result)
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to index chunk: {type(e).__name__}")
            raise RetrievalError("Failed to index chunk") from e

    async def search_dense(
        self,
        query_vector: list[float],
        top_k: int = 5,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Dense vector search with optional source type filter."""
        try:
            query: dict[str, Any] = {
                "knn": {
                    "field": "content_vector",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 10,
                },
                "size": top_k,
            }

            if source_types:
                query["knn"]["filter"] = {"bool": {"filter": [{"terms": {"source_type": source_types}}]}}

            response = await self.client.search(index=self.index_name, body=query)

            return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
        except (ApiError, TransportError) as e:
            logger.error(f"Dense search failed: {type(e).__name__}")
            raise RetrievalError("Dense search failed") from e

    async def search_bm25(
        self,
        query_text: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """BM25 text search with optional source type filter."""
        try:
            if source_types:
                query: dict[str, Any] = {
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"content": query_text}},
                                {"terms": {"source_type": source_types}},
                            ]
                        }
                    },
                    "size": top_k,
                }
            else:
                query = {"query": {"match": {"content": query_text}}, "size": top_k}

            response = await self.client.search(index=self.index_name, body=query)

            return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
        except (ApiError, TransportError) as e:
            logger.error(f"BM25 search failed: {type(e).__name__}")
            raise RetrievalError("BM25 search failed") from e

    async def delete_by_document(self, document_id: str) -> dict[str, Any]:
        try:
            query = {"query": {"term": {"document_id": document_id}}}

            result = await self.client.delete_by_query(index=self.index_name, body=query)
            return cast(dict[str, Any], result)
        except (ApiError, TransportError) as e:
            logger.error(f"Delete by document failed: {type(e).__name__}")
            raise RetrievalError("Delete by document failed") from e

    async def delete_by_query(
        self,
        index: str | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Delete documents matching a query.

        Args:
            index: Index name (defaults to self.index_name).
            body: Query body with 'query' key.

        Returns:
            Result from Elasticsearch delete_by_query operation.
        """
        try:
            target_index = index or self.index_name
            result = await self.client.delete_by_query(index=target_index, body=body)
            return cast(dict[str, Any], result)
        except (ApiError, TransportError) as e:
            logger.error(f"Delete by query failed: {type(e).__name__}")
            raise RetrievalError("Delete by query failed") from e

    async def close(self) -> None:
        try:
            await self.client.close()
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to close ES client: {type(e).__name__}")

    async def index_exhibit(self, exhibit_doc: dict[str, Any]) -> dict[str, Any]:
        """Index an exhibit document."""
        try:
            exhibit_id = exhibit_doc["exhibit_id"]
            doc_id = f"exhibit_{exhibit_id}"
            result = await self.client.index(index=self.index_name, id=doc_id, document=exhibit_doc)
            logger.info(f"Successfully indexed exhibit: {exhibit_id}")
            return cast(dict[str, Any], result)
        except (ApiError, TransportError) as e:
            logger.error(f"Failed to index exhibit: {type(e).__name__}")
            raise RetrievalError("Failed to index exhibit") from e

    async def delete_exhibit(self, exhibit_id: str) -> dict[str, Any]:
        """Delete an exhibit document by ID."""
        try:
            doc_id = f"exhibit_{exhibit_id}"
            result = await self.client.delete(index=self.index_name, id=doc_id)
            logger.info(f"Successfully deleted exhibit: {exhibit_id}")
            return cast(dict[str, Any], result)
        except ApiError as e:
            if e.meta and e.meta.status == 404:
                logger.warning(f"Exhibit not found: {exhibit_id}")
                return {"status": "not_found"}
            logger.error(f"Failed to delete exhibit: {type(e).__name__}")
            raise RetrievalError("Failed to delete exhibit") from e
        except TransportError as e:
            logger.error(f"Failed to delete exhibit: {type(e).__name__}")
            raise RetrievalError("Failed to delete exhibit") from e

    async def search_exhibits(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Vector similarity search for exhibits."""
        try:
            filter_clauses: list[dict[str, Any]] = [{"term": {"doc_type": "exhibit"}}]

            if filters:
                if "category" in filters:
                    filter_clauses.append({"term": {"category": filters["category"]}})
                if "hall" in filters:
                    filter_clauses.append({"term": {"hall": filters["hall"]}})
                if "floor" in filters:
                    filter_clauses.append({"term": {"floor": filters["floor"]}})

            query = {
                "knn": {
                    "field": "content_vector",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": top_k * 10,
                    "filter": {"bool": {"filter": filter_clauses}},
                },
                "size": top_k,
            }

            response = await self.client.search(index=self.index_name, body=query)
            logger.info(f"Exhibit search returned {len(response['hits']['hits'])} results")
            return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
        except (ApiError, TransportError) as e:
            logger.error(f"Exhibit search failed: {type(e).__name__}")
            raise RetrievalError("Exhibit search failed") from e
