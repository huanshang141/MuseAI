from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from app.infra.elasticsearch.client import ElasticsearchClient


class MockIndicesClient:
    def __init__(self) -> None:
        self.exists = AsyncMock(return_value=False)
        self.create = AsyncMock(return_value={"acknowledged": True})


class MockSearchResponse:
    def __init__(self, hits: list[dict[str, Any]]) -> None:
        self._data = {"hits": {"hits": [{"_source": hit} for hit in hits]}}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


class MockAsyncElasticsearch:
    def __init__(self, hosts: list[str]) -> None:
        self.hosts = hosts
        self.indices = MockIndicesClient()
        self.index = AsyncMock(return_value={"result": "created"})
        self.search = AsyncMock(return_value={"hits": {"hits": []}})
        self.delete_by_query = AsyncMock(return_value={"deleted": 5})
        self.close = AsyncMock()


@pytest.fixture
def mock_es_client() -> Any:
    with patch("app.infra.elasticsearch.client.AsyncElasticsearch") as mock_class:
        mock_instance = MockAsyncElasticsearch(["http://localhost:9200"])
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_create_index_new(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    result = await client.create_index(dims=768)

    assert result == {"acknowledged": True}
    mock_es_client.indices.exists.assert_called_once()
    mock_es_client.indices.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_index_already_exists(mock_es_client: Any) -> None:
    mock_es_client.indices.exists.return_value = True

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    result = await client.create_index(dims=768)

    assert result == {"status": "already_exists"}
    mock_es_client.indices.exists.assert_called_once()
    mock_es_client.indices.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_index_custom_dims(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    await client.create_index(dims=1536)

    call_args = mock_es_client.indices.create.call_args
    mapping = call_args.kwargs["body"]
    assert mapping["mappings"]["properties"]["content_vector"]["dims"] == 1536


@pytest.mark.asyncio
async def test_index_chunk(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    chunk = {
        "chunk_id": "chunk-123",
        "document_id": "doc-456",
        "content": "Test content",
        "content_vector": [0.1] * 768,
    }

    result = await client.index_chunk(chunk)

    assert result == {"result": "created"}
    mock_es_client.index.assert_called_once_with(index="museai_chunks_v1", id="chunk-123", document=chunk)


@pytest.mark.asyncio
async def test_search_dense(mock_es_client: Any) -> None:
    mock_es_client.search.return_value = {
        "hits": {"hits": [{"_source": {"chunk_id": "chunk-1", "content": "result 1"}}]}
    }

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    query_vector = [0.1] * 768
    results = await client.search_dense(query_vector, top_k=5)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    mock_es_client.search.assert_called_once()

    call_args = mock_es_client.search.call_args
    assert call_args.kwargs["index"] == "museai_chunks_v1"
    assert call_args.kwargs["size"] == 5


@pytest.mark.asyncio
async def test_search_dense_custom_top_k(mock_es_client: Any) -> None:
    mock_es_client.search.return_value = {"hits": {"hits": []}}

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    query_vector = [0.1] * 768
    await client.search_dense(query_vector, top_k=20)

    call_args = mock_es_client.search.call_args
    query = call_args.kwargs["body"]
    assert query["knn"]["k"] == 20
    assert query["knn"]["num_candidates"] == 200


@pytest.mark.asyncio
async def test_search_bm25(mock_es_client: Any) -> None:
    mock_es_client.search.return_value = {
        "hits": {"hits": [{"_source": {"chunk_id": "chunk-2", "content": "result 2"}}]}
    }

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    results = await client.search_bm25("test query", top_k=10)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-2"

    call_args = mock_es_client.search.call_args
    query = call_args.kwargs["body"]
    assert query["query"]["match"]["content"] == "test query"


@pytest.mark.asyncio
async def test_delete_by_document(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    result = await client.delete_by_document("doc-123")

    assert result == {"deleted": 5}

    call_args = mock_es_client.delete_by_query.call_args
    assert call_args.kwargs["index"] == "museai_chunks_v1"
    query = call_args.kwargs["body"]
    assert query["query"]["term"]["document_id"] == "doc-123"


@pytest.mark.asyncio
async def test_close(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    await client.close()

    mock_es_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager() -> None:
    with patch("app.infra.elasticsearch.client.AsyncElasticsearch") as mock_class:
        mock_instance = MockAsyncElasticsearch(["http://localhost:9200"])
        mock_class.return_value = mock_instance

        async with ElasticsearchClient(hosts=["http://localhost:9200"]):
            pass

        mock_instance.close.assert_called_once()


@pytest.mark.asyncio
async def test_custom_index_name(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"], index_name="custom_index")

    assert client.index_name == "custom_index"

    chunk = {"chunk_id": "test-id"}
    await client.index_chunk(chunk)

    call_args = mock_es_client.index.call_args
    assert call_args.kwargs["index"] == "custom_index"


@pytest.mark.asyncio
async def test_search_returns_empty_list(mock_es_client: Any) -> None:
    mock_es_client.search.return_value = {"hits": {"hits": []}}

    client = ElasticsearchClient(hosts=["http://localhost:9200"])

    results = await client.search_dense([0.1] * 768)
    assert results == []

    results = await client.search_bm25("query")
    assert results == []
