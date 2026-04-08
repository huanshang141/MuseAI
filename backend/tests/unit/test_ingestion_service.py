from unittest.mock import AsyncMock

import pytest
from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentMetadata, ContentSource
from app.application.unified_indexing_service import UnifiedIndexingService


@pytest.mark.asyncio
async def test_unified_indexing_service_chunks_and_indexes_document():
    """Test indexing a document content source."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    # Create chunker to determine how many chunks will be generated
    config = ChunkConfig(level=1, window_size=100, overlap=10)
    chunker = TextChunker(config)
    content = "This is a test document content for chunking and indexing."
    test_chunks = chunker.chunk(text=content, document_id="test-doc", source="document")

    mock_embeddings = AsyncMock()
    # Return embeddings for each chunk
    mock_embeddings.aembed_documents = AsyncMock(
        return_value=[[0.1] * 768 for _ in range(len(test_chunks))]
    )

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

    count = await service.index_source(source)

    assert count > 0
    assert mock_es.index_chunk.call_count == count


@pytest.mark.asyncio
async def test_unified_indexing_service_chunks_and_indexes_exhibit():
    """Test indexing an exhibit content source."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    # Create chunker to determine how many chunks will be generated
    config = ChunkConfig(level=1, window_size=100, overlap=10)
    chunker = TextChunker(config)
    content = "This is a bronze vessel from the Shang Dynasty."
    test_chunks = chunker.chunk(text=content, document_id="exhibit-001", source="exhibit")

    mock_embeddings = AsyncMock()
    # Return embeddings for each chunk
    mock_embeddings.aembed_documents = AsyncMock(
        return_value=[[0.1] * 768 for _ in range(len(test_chunks))]
    )

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[config],
    )

    source = ContentSource(
        source_id="exhibit-001",
        source_type="exhibit",
        content=content,
        metadata=ContentMetadata(
            name="Shang Bronze Vessel",
            category="Bronze",
            hall="Hall A",
            era="Shang Dynasty",
        ),
    )

    count = await service.index_source(source)

    assert count > 0
    assert mock_es.index_chunk.call_count == count
