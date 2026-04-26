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
