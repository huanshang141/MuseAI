import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_index_source_method_has_max_concurrency_parameter():
    """The index_source method should have a max_concurrency parameter for controlling parallelism."""
    import inspect

    from app.application.unified_indexing_service import UnifiedIndexingService

    sig = inspect.signature(UnifiedIndexingService.index_source)
    params = list(sig.parameters.keys())

    assert "max_concurrency" in params, "index_source should have max_concurrency parameter"


def test_index_source_uses_gather():
    """The index_source method should use asyncio.gather for parallel indexing."""
    import inspect

    from app.application.unified_indexing_service import UnifiedIndexingService

    source = inspect.getsource(UnifiedIndexingService.index_source)

    assert "asyncio.gather" in source or "gather(" in source, \
        "index_source should use asyncio.gather for parallel indexing"


def test_index_source_uses_semaphore_pattern():
    """The index_source method should use a semaphore to limit concurrent operations."""
    import inspect

    from app.application.unified_indexing_service import UnifiedIndexingService

    source = inspect.getsource(UnifiedIndexingService.index_source)

    assert "Semaphore" in source, "index_source should use asyncio.Semaphore for concurrency control"


@pytest.mark.asyncio
async def test_unified_indexing_parallel_behavior():
    """Test that unified indexing actually performs parallel indexing."""
    from app.application.chunking import ChunkConfig, TextChunker
    from app.application.content_source import ContentMetadata, ContentSource
    from app.application.unified_indexing_service import UnifiedIndexingService

    # Track timing of each index call
    call_times = []

    async def mock_index_chunk(doc):
        call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.05)  # Simulate network delay

    mock_es = MagicMock()
    mock_es.index_chunk = mock_index_chunk
    mock_es.create_index = AsyncMock()

    config = ChunkConfig(level=1, window_size=100, overlap=10)
    content = "This is a test. " * 100

    # Pre-calculate chunk count to return correct number of embeddings
    chunker = TextChunker(config)
    test_chunks = chunker.chunk(text=content, document_id="test-doc-123", source="document")

    mock_embeddings = MagicMock()
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
        source_id="test-doc-123",
        source_type="document",
        content=content,
        metadata=ContentMetadata(filename="test-source.txt"),
    )

    # Should have multiple chunks
    assert len(test_chunks) > 1, f"Expected multiple chunks, got {len(test_chunks)}"

    # Run ingestion
    await service.index_source(source, max_concurrency=5)

    # If parallel, all calls should start roughly at the same time
    # If sequential, each call would start 0.05s after the previous
    if len(call_times) > 1:
        # Calculate the time span of all calls starting
        first_call = min(call_times)
        last_call = max(call_times)

        # With parallel execution and semaphore, all should start within ~0.1s of each other
        # With sequential execution, would take len(chunks) * 0.05 seconds
        time_span = last_call - first_call

        # If parallel with max_concurrency=5, even with 10 chunks,
        # all should start within 0.2s (batching by 5)
        # Sequential would be 10 * 0.05 = 0.5s
        assert time_span < 0.3, \
            f"Indexing appears sequential, time span was {time_span}s for {len(call_times)} chunks"


@pytest.mark.asyncio
async def test_unified_indexing_respects_max_concurrency():
    """Test that max_concurrency actually limits concurrent operations."""
    from app.application.chunking import ChunkConfig, TextChunker
    from app.application.content_source import ContentMetadata, ContentSource
    from app.application.unified_indexing_service import UnifiedIndexingService

    concurrent_count = 0
    max_concurrent = 0
    lock = asyncio.Lock()

    async def mock_index_chunk(doc):
        nonlocal concurrent_count, max_concurrent
        async with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

        await asyncio.sleep(0.02)  # Simulate work

        async with lock:
            concurrent_count -= 1

    mock_es = MagicMock()
    mock_es.index_chunk = mock_index_chunk
    mock_es.create_index = AsyncMock()

    config = ChunkConfig(level=1, window_size=100, overlap=10)
    content = "Test chunk content. " * 100

    # Pre-calculate chunk count to return correct number of embeddings
    chunker = TextChunker(config)
    test_chunks = chunker.chunk(text=content, document_id="test-doc-456", source="document")

    mock_embeddings = MagicMock()
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
        source_id="test-doc-456",
        source_type="document",
        content=content,
        metadata=ContentMetadata(filename="test.txt"),
    )

    # Run with max_concurrency=3
    await service.index_source(source, max_concurrency=3)

    # Max concurrent should not exceed 3
    assert max_concurrent <= 3, \
        f"max_concurrent was {max_concurrent}, expected <= 3"
