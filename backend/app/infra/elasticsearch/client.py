from typing import Any, cast

from elasticsearch import AsyncElasticsearch


class ElasticsearchClient:
    def __init__(self, hosts: list[str], index_name: str = "museai_chunks_v1"):
        self.client = AsyncElasticsearch(hosts)
        self.index_name = index_name

    async def __aenter__(self) -> "ElasticsearchClient":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        await self.close()

    async def create_index(self, dims: int = 768) -> dict[str, Any]:
        if await self.client.indices.exists(index=self.index_name):
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

        result = await self.client.indices.create(index=self.index_name, body=mapping)
        return cast(dict[str, Any], result)

    async def index_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        chunk_id = chunk["chunk_id"]
        result = await self.client.index(index=self.index_name, id=chunk_id, document=chunk)
        return cast(dict[str, Any], result)

    async def search_dense(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        query = {
            "knn": {"field": "content_vector", "query_vector": query_vector, "k": top_k, "num_candidates": top_k * 10}
        }

        response = await self.client.search(index=self.index_name, body=query, size=top_k)

        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]

    async def search_bm25(self, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
        query = {"query": {"match": {"content": query_text}}}

        response = await self.client.search(index=self.index_name, body=query, size=top_k)

        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]

    async def delete_by_document(self, document_id: str) -> dict[str, Any]:
        query = {"query": {"term": {"document_id": document_id}}}

        result = await self.client.delete_by_query(index=self.index_name, body=query)
        return cast(dict[str, Any], result)

    async def close(self) -> None:
        await self.client.close()
