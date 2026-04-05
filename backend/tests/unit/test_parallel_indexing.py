import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def test_ingest_method_has_max_concurrency_parameter():
    """The ingest method should have a max_concurrency parameter for controlling parallelism."""
    import inspect
    from app.application.ingestion_service import IngestionService

    sig = inspect.signature(IngestionService.ingest)
    params = list(sig.parameters.keys())

    assert "max_concurrency" in params, "ingest should have max_concurrency parameter"


def test_ingest_uses_gather():
    """The ingest method should use asyncio.gather for parallel indexing."""
    import inspect
    from app.application.ingestion_service import IngestionService

    source = inspect.getsource(IngestionService.ingest)

    assert "asyncio.gather" in source or "gather(" in source, \
        "ingest should use asyncio.gather for parallel indexing"


def test_ingest_uses_semaphore_pattern():
    """The ingest method should use a semaphore to limit concurrent operations."""
    import inspect
    from app.application.ingestion_service import IngestionService

    source = inspect.getsource(IngestionService.ingest)

    assert "Semaphore" in source, "ingest should use asyncio.Semaphore for concurrency control"


@pytest.mark.asyncio
async def test_ingestion_parallel_behavior():
    """Test that ingestion actually performs parallel indexing."""
    from app.application.ingestion_service import IngestionService
    from app.application.chunking import ChunkConfig, TextChunker, Chunk

    # Track timing of each index call
    start_time = asyncio.get_event_loop().time()
    call_times = []

    async def mock_index_chunk(doc):
        call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.05)  # Simulate network delay

    mock_es = MagicMock()
    mock_es.index_chunk = mock_index_chunk
    mock_es.create_index = AsyncMock()

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768] * 10)

    service = IngestionService(es_client=mock_es, embeddings=mock_embeddings)

    # Chunk manually to get multiple chunks
    config = ChunkConfig(level=1, window_size=100, overlap=10)
    chunker = TextChunker(config)

    # Create a long enough text to generate multiple chunks
    content = "This is a test. " * 100
    document_id = "test-doc-123"
    source = "test-source.txt"

    chunks = chunker.chunk(text=content, document_id=document_id, source=source)

    # Should have multiple chunks
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"

    # Run ingestion
    chunk_count = await service.ingest(document_id, content, source, max_concurrency=5)

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
async def test_ingestion_respects_max_concurrency():
    """Test that max_concurrency actually limits concurrent operations."""
    from app.application.ingestion_service import IngestionService
    from app.application.chunking import ChunkConfig, TextChunker

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

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768] * 20)

    service = IngestionService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)]
    )

    # Create content that will produce many chunks
    content = "Test chunk content. " * 100
    document_id = "test-doc-456"
    source = "test.txt"

    # Run with max_concurrency=3
    await service.ingest(document_id, content, source, max_concurrency=3)

    # Max concurrent should not exceed 3
    assert max_concurrent <= 3, \
        f"max_concurrent was {max_concurrent}, expected <= 3"
