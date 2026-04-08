# backend/tests/unit/test_unified_indexing_service.py
from unittest.mock import AsyncMock

import pytest
from app.application.chunking import ChunkConfig
from app.application.content_source import ContentMetadata, ContentSource
from app.application.unified_indexing_service import UnifiedIndexingService


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
