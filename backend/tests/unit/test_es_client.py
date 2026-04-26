from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.domain.exceptions import RetrievalError
from app.infra.elasticsearch.client import ElasticsearchClient
from elasticsearch.exceptions import ApiError


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
    def __init__(
        self, hosts: list[str], request_timeout: float = 30.0, max_retries: int = 3, retry_on_timeout: bool = True
    ) -> None:
        self.hosts = hosts
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_on_timeout = retry_on_timeout
        self.indices = MockIndicesClient()
        self.index = AsyncMock(return_value={"result": "created"})
        self.search = AsyncMock(return_value={"hits": {"hits": []}})
        self.delete_by_query = AsyncMock(return_value={"deleted": 5})
        self.ping = AsyncMock(return_value=True)
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
    result = await client.create_index(index_name="museai_chunks_v1", dims=1536)

    assert result == {"status": "created"}
    mock_es_client.indices.exists.assert_called_once()
    mock_es_client.indices.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_index_already_exists(mock_es_client: Any) -> None:
    mock_es_client.indices.exists.return_value = True

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    result = await client.create_index(index_name="museai_chunks_v1", dims=1536)

    assert result == {"status": "already_exists"}
    mock_es_client.indices.exists.assert_called_once()
    mock_es_client.indices.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_index_custom_dims(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    await client.create_index(index_name="museai_chunks_v1", dims=768)

    call_args = mock_es_client.indices.create.call_args
    mapping = call_args.kwargs["body"]
    assert mapping["mappings"]["properties"]["content_vector"]["dims"] == 768


@pytest.mark.asyncio
async def test_create_index_default_dims_is_1536(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    await client.create_index(index_name="museai_chunks_v1")

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
        "content_vector": [0.1] * 1536,
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
    query_vector = [0.1] * 1536
    results = await client.search_dense(query_vector, top_k=5)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    mock_es_client.search.assert_called_once()

    call_args = mock_es_client.search.call_args
    assert call_args.kwargs["index"] == "museai_chunks_v1"
    assert call_args.kwargs["body"]["size"] == 5


@pytest.mark.asyncio
async def test_search_dense_custom_top_k(mock_es_client: Any) -> None:
    mock_es_client.search.return_value = {"hits": {"hits": []}}

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    query_vector = [0.1] * 1536
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

    results = await client.search_dense([0.1] * 1536)
    assert results == []

    results = await client.search_bm25("query")
    assert results == []


@pytest.mark.asyncio
async def test_health_check_success(mock_es_client: Any) -> None:
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    result = await client.health_check()

    assert result is True
    mock_es_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_health_check_failure(mock_es_client: Any) -> None:
    mock_es_client.ping.side_effect = Exception("Connection refused")

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    result = await client.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_create_index_raises_retrieval_error(mock_es_client: Any) -> None:
    mock_es_client.indices.create.side_effect = ApiError("Index creation failed", meta=None, body=None)

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    with pytest.raises(RetrievalError, match="Failed to create index"):
        await client.create_index(index_name="test_index")


@pytest.mark.asyncio
async def test_index_chunk_raises_retrieval_error(mock_es_client: Any) -> None:
    mock_es_client.index.side_effect = ApiError("Indexing failed", meta=None, body=None)

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    with pytest.raises(RetrievalError, match="Failed to index chunk"):
        await client.index_chunk({"chunk_id": "test"})


@pytest.mark.asyncio
async def test_search_dense_raises_retrieval_error(mock_es_client: Any) -> None:
    mock_es_client.search.side_effect = ApiError("Search failed", meta=None, body=None)

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    with pytest.raises(RetrievalError, match="Dense search failed"):
        await client.search_dense([0.1] * 1536)


@pytest.mark.asyncio
async def test_search_bm25_raises_retrieval_error(mock_es_client: Any) -> None:
    mock_es_client.search.side_effect = ApiError("Search failed", meta=None, body=None)

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    with pytest.raises(RetrievalError, match="BM25 search failed"):
        await client.search_bm25("query")


@pytest.mark.asyncio
async def test_delete_by_document_raises_retrieval_error(mock_es_client: Any) -> None:
    mock_es_client.delete_by_query.side_effect = ApiError("Delete failed", meta=None, body=None)

    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    with pytest.raises(RetrievalError, match="Delete by document failed"):
        await client.delete_by_document("doc-123")


@pytest.mark.asyncio
async def test_timeout_and_retry_config() -> None:
    with patch("app.infra.elasticsearch.client.AsyncElasticsearch") as mock_class:
        mock_instance = MockAsyncElasticsearch(["http://localhost:9200"])
        mock_class.return_value = mock_instance

        ElasticsearchClient(
            hosts=["http://localhost:9200"],
            timeout=60.0,
            max_retries=5,
        )

        mock_class.assert_called_once_with(
            ["http://localhost:9200"],
            request_timeout=60.0,
            max_retries=5,
            retry_on_timeout=True,
        )


@pytest.mark.asyncio
async def test_create_index_includes_unified_fields() -> None:
    """Test that index creation includes unified schema fields."""
    mock_es = AsyncMock()
    mock_es.indices = AsyncMock()
    mock_es.indices.exists = AsyncMock(return_value=False)
    mock_es.indices.create = AsyncMock(return_value={"acknowledged": True})

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    await client.create_index("test_index", dims=768)

    call_args = mock_es.indices.create.call_args
    mapping = call_args.kwargs["body"]["mappings"]["properties"]

    # Verify unified fields
    assert "source_id" in mapping
    assert mapping["source_id"]["type"] == "keyword"
    assert "source_type" in mapping
    assert mapping["source_type"]["type"] == "keyword"
    assert "metadata" in mapping
    assert mapping["metadata"]["type"] == "object"


@pytest.mark.asyncio
async def test_search_dense_with_source_types_filter() -> None:
    """Test that dense search supports source_types filtering."""
    mock_es = AsyncMock()
    mock_es.search = AsyncMock(return_value={"hits": {"hits": []}})

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    query_vector = [0.1] * 768
    await client.search_dense(query_vector, top_k=5, source_types=["exhibit", "document"])

    call_args = mock_es.search.call_args
    query = call_args.kwargs["body"]

    # Verify filter clause is present
    assert "filter" in query["knn"]
    assert query["knn"]["filter"]["bool"]["filter"][0] == {"terms": {"source_type": ["exhibit", "document"]}}


@pytest.mark.asyncio
async def test_search_bm25_with_source_types_filter() -> None:
    """Test that BM25 search supports source_types filtering."""
    mock_es = AsyncMock()
    mock_es.search = AsyncMock(return_value={"hits": {"hits": []}})

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    await client.search_bm25("test query", top_k=5, source_types=["exhibit"])

    call_args = mock_es.search.call_args
    query = call_args.kwargs["body"]

    # Verify bool query with must clause is present
    assert "bool" in query["query"]
    assert query["query"]["bool"]["must"][0] == {"match": {"content": "test query"}}
    assert query["query"]["bool"]["must"][1] == {"terms": {"source_type": ["exhibit"]}}


@pytest.mark.asyncio
async def test_get_chunk_by_id_found():
    mock_es = AsyncMock()
    mock_es.get = AsyncMock(return_value={"_source": {"chunk_id": "c1", "content": "test"}})

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    result = await client.get_chunk_by_id("c1")
    assert result is not None
    assert result["chunk_id"] == "c1"
    mock_es.get.assert_called_once_with(index="test_index", id="c1")


@pytest.mark.asyncio
async def test_get_chunk_by_id_not_found():
    mock_es = AsyncMock()
    api_error = ApiError("Not found", meta=MagicMock(status=404), body=None)
    mock_es.get = AsyncMock(side_effect=api_error)

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    result = await client.get_chunk_by_id("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_chunk_by_id_raises_on_error():
    mock_es = AsyncMock()
    api_error = ApiError("Internal error", meta=MagicMock(status=500), body=None)
    mock_es.get = AsyncMock(side_effect=api_error)

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    with pytest.raises(RetrievalError, match="Failed to get chunk"):
        await client.get_chunk_by_id("c1")
