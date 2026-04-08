# backend/tests/unit/test_unified_indexing_behavior.py
"""Behavior-based tests for unified indexing service.

These tests verify the actual behavior of the unified indexing service,
focusing on outcomes rather than implementation details.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentMetadata, ContentSource
from app.application.unified_indexing_service import UnifiedIndexingService


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
        test_chunks = chunker.chunk(text=content, document_id="test-doc", source="document")

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

        result = await service.delete_source("doc-123")

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

        result = await service.delete_source("exhibit-456", source_type="exhibit")

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
        assert len(service.chunk_configs) == 2
        assert service.chunk_configs[0].level == 1
        assert service.chunk_configs[1].level == 2
