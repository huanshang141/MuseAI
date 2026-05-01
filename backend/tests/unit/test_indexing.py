# backend/tests/unit/test_indexing.py
"""Merged indexing tests: unified indexing service, behavior, and embedding provider tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentMetadata, ContentSource
from app.application.unified_indexing_service import UnifiedIndexingService
from app.infra.providers.embedding import OllamaEmbeddingProvider


# ---------------------------------------------------------------------------
# Helper classes (from test_embedding_provider.py)
# ---------------------------------------------------------------------------


class MockResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class MockAsyncClient:
    def __init__(self, response_data=None):
        self._response_data = response_data
        self.post_count = 0

    async def post(self, *args, **kwargs):
        self.post_count += 1
        return MockResponse(self._response_data)

    async def aclose(self):
        pass


# ===========================================================================
# UnifiedIndexingService - basic tests (from test_unified_indexing_service.py)
# ===========================================================================


@pytest.mark.asyncio
async def test_unified_indexing_service_indexes_content_source():
    """Test that UnifiedIndexingService indexes a ContentSource."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    # Return embeddings for each chunk (mock returns one embedding per call,
    # so we make it return a list with matching length)
    mock_embeddings.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.1] * 768 for _ in texts]
    )

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)],
    )

    source = ContentSource(
        source_id="test-doc-123",
        source_type="document",
        content="This is a test document content for chunking and indexing.",
        metadata=ContentMetadata(filename="test.txt"),
    )

    count = await service.index_source(source)

    assert count > 0
    assert mock_es.index_chunk.call_count == count

    # Verify the indexed document has correct fields
    call_args = mock_es.index_chunk.call_args
    indexed_doc = call_args[0][0]
    assert indexed_doc["source_id"] == "test-doc-123"
    assert indexed_doc["source_type"] == "document"
    assert "chunk_id" in indexed_doc
    assert "content_vector" in indexed_doc


@pytest.mark.asyncio
async def test_unified_indexing_service_indexes_exhibit():
    """Test that UnifiedIndexingService indexes an exhibit ContentSource."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    # Return embeddings for each chunk
    mock_embeddings.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.1] * 768 for _ in texts]
    )

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=200, overlap=20)],
    )

    source = ContentSource(
        source_id="exhibit-456",
        source_type="exhibit",
        content="Ming Dynasty Blue and White Porcelain Vase. This exquisite piece dates back to the 15th century.",
        metadata=ContentMetadata(
            name="Blue and White Vase",
            category="Ceramics",
            hall="Hall A",
            floor=2,
            era="Ming Dynasty",
            importance=5,
        ),
    )

    count = await service.index_source(source)

    assert count > 0

    # Verify metadata is preserved
    call_args = mock_es.index_chunk.call_args
    indexed_doc = call_args[0][0]
    assert indexed_doc["source_type"] == "exhibit"
    assert indexed_doc["metadata"]["name"] == "Blue and White Vase"
    assert indexed_doc["metadata"]["category"] == "Ceramics"


@pytest.mark.asyncio
async def test_unified_indexing_service_delete_source():
    """Test that UnifiedIndexingService can delete a source."""
    mock_es = AsyncMock()
    mock_es.delete_by_query = AsyncMock(return_value={"deleted": 5})

    mock_embeddings = AsyncMock()

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
    )

    await service.delete_source("test-doc-123")

    mock_es.delete_by_query.assert_called_once()
    call_args = mock_es.delete_by_query.call_args
    query = call_args[1]["body"]
    assert query["query"]["term"]["source_id"] == "test-doc-123"


@pytest.mark.asyncio
async def test_unified_indexing_service_delete_source_with_type():
    """Test that UnifiedIndexingService can delete a source with type filter."""
    mock_es = AsyncMock()
    mock_es.delete_by_query = AsyncMock(return_value={"deleted": 3})
    mock_embeddings = AsyncMock()

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
    )

    await service.delete_source("test-doc-123", source_type="document")

    mock_es.delete_by_query.assert_called_once()
    call_args = mock_es.delete_by_query.call_args
    query = call_args[1]["body"]
    # Verify compound query
    assert query["query"]["bool"]["must"][0]["term"]["source_id"] == "test-doc-123"
    assert query["query"]["bool"]["must"][1]["term"]["source_type"] == "document"


@pytest.mark.asyncio
async def test_unified_indexing_service_empty_content():
    """Test that UnifiedIndexingService handles empty content."""
    mock_es = AsyncMock()
    mock_embeddings = AsyncMock()

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
    )

    source = ContentSource(
        source_id="empty-doc",
        source_type="document",
        content="",  # Empty content
        metadata=ContentMetadata(filename="empty.txt"),
    )

    count = await service.index_source(source)
    assert count == 0
    mock_es.index_chunk.assert_not_called()


@pytest.mark.asyncio
async def test_unified_indexing_service_hierarchical_parent_ids():
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.1] * 768 for _ in texts]
    )

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[
            ChunkConfig(level=1, window_size=100, overlap=10),
            ChunkConfig(level=2, window_size=50, overlap=5),
        ],
    )

    source = ContentSource(
        source_id="test-doc-hier",
        source_type="document",
        content="A" * 200,
        metadata=ContentMetadata(filename="test.txt"),
    )

    count = await service.index_source(source)
    assert count > 0

    indexed_docs = [call[0][0] for call in mock_es.index_chunk.call_args_list]
    level2_docs = [d for d in indexed_docs if d["chunk_level"] == 2]
    level1_docs = [d for d in indexed_docs if d["chunk_level"] == 1]

    assert len(level1_docs) > 0
    assert len(level2_docs) > 0
    assert all(d["parent_chunk_id"] is not None for d in level2_docs)

    level1_ids = {d["chunk_id"] for d in level1_docs}
    level2_parent_ids = {d["parent_chunk_id"] for d in level2_docs}
    assert level2_parent_ids.issubset(level1_ids)


@pytest.mark.asyncio
async def test_unified_indexing_service_hierarchical_offset_calculation():
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.1] * 768 for _ in texts]
    )

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[
            ChunkConfig(level=1, window_size=50, overlap=0),
            ChunkConfig(level=2, window_size=20, overlap=0),
        ],
    )

    content = "A" * 50 + "B" * 50
    source = ContentSource(
        source_id="offset-test",
        source_type="document",
        content=content,
        metadata=ContentMetadata(filename="test.txt"),
    )

    await service.index_source(source)

    indexed_docs = [call[0][0] for call in mock_es.index_chunk.call_args_list]
    level2_docs = [d for d in indexed_docs if d["chunk_level"] == 2]

    for doc in level2_docs:
        assert doc["start_char"] >= 0
        assert doc["end_char"] <= len(content)
        assert content[doc["start_char"]:doc["end_char"]] == doc["content"]


# ===========================================================================
# UnifiedIndexingService - behavior tests (from test_unified_indexing_behavior.py)
# ===========================================================================


class TestUnifiedIndexingServiceBehavior:
    """Tests for UnifiedIndexingService behavior."""

    @pytest.mark.asyncio
    async def test_index_source_creates_valid_chunk_documents(self):
        """Test that indexed documents contain all required fields."""
        indexed_docs = []

        async def mock_index_chunk(doc):
            indexed_docs.append(doc)

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=100, overlap=10)
        content = "Test content for validation. " * 20

        chunker = TextChunker(config)
        test_chunks = chunker.chunk(text=content, document_id="test-doc", source="document")

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(
            return_value=[[0.1] * 768 for _ in range(len(test_chunks))]
        )

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[config],
        )

        source = ContentSource(
            source_id="test-doc-123",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="test.txt"),
        )

        await service.index_source(source, max_concurrency=5)

        # Verify each indexed document has required fields
        for doc in indexed_docs:
            assert "chunk_id" in doc
            assert "source_id" in doc
            assert "source_type" in doc
            assert "content" in doc
            assert "content_vector" in doc
            assert "chunk_level" in doc
            assert "metadata" in doc

            # Verify field values
            assert doc["source_id"] == "test-doc-123"
            assert doc["source_type"] == "document"
            assert len(doc["content_vector"]) == 768
            assert doc["chunk_level"] == 1

    @pytest.mark.asyncio
    async def test_index_source_uses_embeddings_for_chunks(self):
        """Test that embeddings are generated for each chunk text."""
        embed_calls = []

        async def mock_aembed_documents(texts):
            embed_calls.append(texts)
            return [[0.1] * 768 for _ in range(len(texts))]

        mock_es = MagicMock()
        mock_es.index_chunk = AsyncMock()
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=100, overlap=10)
        content = "Embedding test content. " * 30

        chunker = TextChunker(config)
        chunker.chunk(text=content, document_id="test-doc", source="document")

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = mock_aembed_documents

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[config],
        )

        source = ContentSource(
            source_id="test-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="test.txt"),
        )

        await service.index_source(source, max_concurrency=5)

        # Verify embeddings were called for chunk texts
        assert len(embed_calls) >= 1
        # The texts passed should match the chunk contents
        for call in embed_calls:
            assert isinstance(call, list)
            assert all(isinstance(t, str) for t in call)

    @pytest.mark.asyncio
    async def test_index_source_propagates_metadata(self):
        """Test that source metadata is propagated to indexed documents."""
        indexed_docs = []

        async def mock_index_chunk(doc):
            indexed_docs.append(doc)

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=200, overlap=20)
        content = "Metadata test. " * 20

        chunker = TextChunker(config)
        test_chunks = chunker.chunk(text=content, document_id="test-doc", source="exhibit")

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(
            return_value=[[0.1] * 768 for _ in range(len(test_chunks))]
        )

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[config],
        )

        source = ContentSource(
            source_id="exhibit-456",
            source_type="exhibit",
            content=content,
            metadata=ContentMetadata(filename="exhibit_info.txt"),
        )

        await service.index_source(source, max_concurrency=5)

        # Verify metadata is included in all documents
        for doc in indexed_docs:
            assert "metadata" in doc
            assert isinstance(doc["metadata"], dict)

    @pytest.mark.asyncio
    async def test_index_source_handles_large_content(self):
        """Test that index_source handles large content efficiently."""
        indexed_count = 0

        async def mock_index_chunk(doc):
            nonlocal indexed_count
            indexed_count += 1

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=1000, overlap=100)
        # Create large content
        content = "Large content test. " * 1000

        chunker = TextChunker(config)
        test_chunks = chunker.chunk(text=content, document_id="test-doc", source="document")

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(
            return_value=[[0.1] * 768 for _ in range(len(test_chunks))]
        )

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[config],
        )

        source = ContentSource(
            source_id="large-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="large.txt"),
        )

        count = await service.index_source(source, max_concurrency=20)

        assert count == indexed_count
        assert count > 0


class TestUnifiedIndexingServiceDelete:
    """Tests for UnifiedIndexingService delete operations."""

    @pytest.mark.asyncio
    async def test_delete_source_calls_es_delete_by_query(self):
        """Test that delete_source calls Elasticsearch delete_by_query."""
        delete_calls = []

        async def mock_delete_by_query(index, body):
            delete_calls.append({"index": index, "body": body})
            return {"deleted": 5}

        mock_es = MagicMock()
        mock_es.delete_by_query = mock_delete_by_query
        mock_es.index_name = "test_index"

        mock_embeddings = MagicMock()

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[],
        )

        await service.delete_source("doc-123")

        # Verify delete was called
        assert len(delete_calls) == 1
        assert delete_calls[0]["index"] == "test_index"
        assert "query" in delete_calls[0]["body"]

    @pytest.mark.asyncio
    async def test_delete_source_with_type_filter(self):
        """Test that delete_source applies source type filter when provided."""
        delete_calls = []

        async def mock_delete_by_query(index, body):
            delete_calls.append({"index": index, "body": body})
            return {"deleted": 3}

        mock_es = MagicMock()
        mock_es.delete_by_query = mock_delete_by_query
        mock_es.index_name = "test_index"

        mock_embeddings = MagicMock()

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[],
        )

        await service.delete_source("exhibit-456", source_type="exhibit")

        # Verify both filters were applied
        query = delete_calls[0]["body"]["query"]
        assert "bool" in query
        assert "must" in query["bool"]

        filters = query["bool"]["must"]
        source_id_filter = {"term": {"source_id": "exhibit-456"}}
        source_type_filter = {"term": {"source_type": "exhibit"}}

        assert source_id_filter in filters
        assert source_type_filter in filters


class TestUnifiedIndexingServiceChunkLevels:
    """Tests for multi-level chunking behavior."""

    @pytest.mark.asyncio
    async def test_index_source_creates_chunks_at_multiple_levels(self):
        """Test that multiple chunk configs create chunks at different levels."""
        indexed_docs = []

        async def mock_index_chunk(doc):
            indexed_docs.append(doc)

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        # Two chunk configs at different levels
        configs = [
            ChunkConfig(level=1, window_size=500, overlap=50),
            ChunkConfig(level=2, window_size=100, overlap=10),
        ]

        content = "Multi-level content test. " * 50

        # Mock embeddings to return correct number per call
        embed_call_count = [0]

        async def mock_aembed_documents(texts):
            embed_call_count[0] += 1
            return [[0.1] * 768 for _ in range(len(texts))]

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = mock_aembed_documents

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=configs,
        )

        source = ContentSource(
            source_id="multi-level-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="multi.txt"),
        )

        count = await service.index_source(source, max_concurrency=10)

        # Verify chunks were created at different levels
        chunk_levels = set(doc["chunk_level"] for doc in indexed_docs)

        assert count == len(indexed_docs)
        assert 1 in chunk_levels  # Level 1 chunks should exist
        assert 2 in chunk_levels  # Level 2 chunks should exist

    @pytest.mark.asyncio
    async def test_index_source_default_configs(self):
        """Test that default chunk configs are used when none provided."""
        mock_es = MagicMock()
        mock_es.index_chunk = AsyncMock()
        mock_es.create_index = AsyncMock()

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])

        # Create service without explicit chunk_configs
        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
        )

        # Verify default configs are set
        assert len(service.chunk_configs) == 3
        assert service.chunk_configs[0].level == 1
        assert service.chunk_configs[1].level == 2
        assert service.chunk_configs[2].level == 3


# ===========================================================================
# Embedding lifecycle tests (from test_embedding_lifecycle.py)
# ===========================================================================


def test_ollama_provider_supports_external_client():
    """OllamaEmbeddingProvider should accept external httpx client."""
    import httpx
    from app.infra.providers.embedding import OllamaEmbeddingProvider

    external_client = httpx.AsyncClient()
    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dims=768,
        client=external_client,  # Should accept external client
    )

    assert provider.client is external_client


def test_custom_embeddings_reuses_provider():
    """CustomOllamaEmbeddings should not create new provider each call."""
    from app.infra.langchain.embeddings import CustomOllamaEmbeddings

    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dims=768,
    )

    # Get provider twice
    provider1 = embeddings._get_provider()
    provider2 = embeddings._get_provider()

    # Should be same instance
    assert provider1 is provider2


@pytest.mark.asyncio
async def test_embeddings_close_provider():
    """CustomOllamaEmbeddings should close provider on demand."""
    from app.infra.langchain.embeddings import CustomOllamaEmbeddings

    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dims=768,
    )

    provider = embeddings._get_provider()
    provider.close = AsyncMock()

    await embeddings.close()

    provider.close.assert_called_once()


# ===========================================================================
# Embedding provider tests (from test_embedding_provider.py)
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_single_text():
    response_data = {"embedding": [0.1] * 768}
    mock_client = MockAsyncClient(response_data)

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        embedding = await provider.embed("test text")

        assert len(embedding) == 768
        assert all(v == 0.1 for v in embedding)
        assert mock_client.post_count == 1


@pytest.mark.asyncio
async def test_embed_batch_concurrent():
    response_data = {"embeddings": [[0.1] * 768, [0.1] * 768, [0.1] * 768]}
    mock_client = MockAsyncClient(response_data)

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        texts = ["text 1", "text 2", "text 3"]
        embeddings = await provider.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 768 for e in embeddings)
        assert mock_client.post_count == 1


@pytest.mark.asyncio
async def test_embed_dimension_validation():
    response_data = {"embedding": [0.1] * 512}
    mock_client = MockAsyncClient(response_data)

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)

        with pytest.raises(ValueError, match="Embedding dimension mismatch: expected 768, got 512"):
            await provider.embed("test text")


@pytest.mark.asyncio
async def test_timeout_parameter():
    mock_client = MockAsyncClient({"embedding": [0.1] * 768})

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(
            base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768, timeout=30.0
        )

        assert provider.timeout == 30.0
        mock_client_class.assert_called_once_with(timeout=30.0)


@pytest.mark.asyncio
async def test_close_method():
    mock_client = MagicMock()
    mock_client.aclose = MagicMock(return_value=None)
    mock_client.aclose.return_value = None

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        await provider.close()


@pytest.mark.asyncio
async def test_context_manager():
    response_data = {"embedding": [0.1] * 768}
    mock_client = MockAsyncClient(response_data)
    close_called = False

    async def mock_aclose():
        nonlocal close_called
        close_called = True

    mock_client.aclose = mock_aclose

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        async with OllamaEmbeddingProvider(
            base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768
        ) as provider:
            embedding = await provider.embed("test text")
            assert len(embedding) == 768

        assert close_called


@pytest.mark.asyncio
async def test_embed_batch_partial_failure():
    async def post_with_failure(*args, **kwargs):
        raise Exception("Simulated failure")

    mock_client = MagicMock()
    mock_client.post = post_with_failure

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        texts = ["text 1", "text 2", "text 3"]

        with pytest.raises(RuntimeError, match="Failed to embed batch"):
            await provider.embed_batch(texts)
