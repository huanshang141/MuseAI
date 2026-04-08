# backend/tests/unit/test_parallel_indexing.py
"""Behavior-based tests for parallel indexing functionality.

These tests verify the actual behavior of parallel indexing operations,
replacing brittle source-inspection tests with tests that validate
the expected outcomes and side effects.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentMetadata, ContentSource
from app.application.unified_indexing_service import UnifiedIndexingService


class TestIndexSourceBehavior:
    """Tests for index_source method behavior."""

    @pytest.mark.asyncio
    async def test_index_source_indexes_all_chunks(self):
        """Test that index_source indexes all generated chunks."""
        indexed_chunks = []

        async def mock_index_chunk(doc):
            indexed_chunks.append(doc)

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=100, overlap=10)
        content = "This is a test sentence. " * 50  # Enough for multiple chunks

        # Pre-calculate chunk count
        chunker = TextChunker(config)
        test_chunks = chunker.chunk(text=content, document_id="test-doc", source="document")
        expected_chunk_count = len(test_chunks)

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(
            return_value=[[0.1] * 768 for _ in range(expected_chunk_count)]
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

        # Run indexing
        count = await service.index_source(source, max_concurrency=5)

        # Verify all chunks were indexed
        assert count == expected_chunk_count
        assert len(indexed_chunks) == expected_chunk_count

    @pytest.mark.asyncio
    async def test_index_source_respects_concurrency_limit(self):
        """Test that index_source respects the max_concurrency limit.

        This test verifies that even with many chunks, the concurrent
        operations never exceed the specified limit.
        """
        concurrent_count = 0
        max_observed_concurrency = 0
        lock = asyncio.Lock()

        async def mock_index_chunk(doc):
            nonlocal concurrent_count, max_observed_concurrency
            async with lock:
                concurrent_count += 1
                max_observed_concurrency = max(max_observed_concurrency, concurrent_count)

            await asyncio.sleep(0.02)  # Simulate work

            async with lock:
                concurrent_count -= 1

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=100, overlap=10)
        content = "Test chunk content. " * 100  # Generate many chunks

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
            source_id="test-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="test.txt"),
        )

        # Run with specific concurrency limit
        max_concurrency = 3
        await service.index_source(source, max_concurrency=max_concurrency)

        # Verify concurrency was never exceeded
        assert max_observed_concurrency <= max_concurrency, \
            f"Max observed concurrency {max_observed_concurrency} exceeded limit {max_concurrency}"

    @pytest.mark.asyncio
    async def test_index_source_returns_correct_count(self):
        """Test that index_source returns the total number of chunks indexed."""
        mock_es = MagicMock()
        mock_es.index_chunk = AsyncMock()
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=200, overlap=20)
        content = "Sample content for testing. " * 30

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
            source_id="test-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="test.txt"),
        )

        count = await service.index_source(source, max_concurrency=10)

        assert count == len(test_chunks)
        assert count > 0

    @pytest.mark.asyncio
    async def test_index_source_processes_multiple_chunk_configs(self):
        """Test that index_source processes all chunk configurations."""
        indexed_chunks = []

        async def mock_index_chunk(doc):
            indexed_chunks.append(doc)

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        # Multiple chunk configs at different levels
        configs = [
            ChunkConfig(level=1, window_size=500, overlap=50),
            ChunkConfig(level=2, window_size=200, overlap=20),
        ]

        content = "This is test content. " * 100

        # Calculate total expected chunks across all configs
        total_expected = 0
        chunk_counts = []
        for config in configs:
            chunker = TextChunker(config)
            chunks = chunker.chunk(text=content, document_id="test-doc", source="document")
            chunk_counts.append(len(chunks))
            total_expected += len(chunks)

        mock_embeddings = MagicMock()
        # Return embeddings for total expected chunks
        mock_embeddings.aembed_documents = AsyncMock(
            return_value=[[0.1] * 768 for _ in range(total_expected)]
        )

        # We need to mock aembed_documents to return correct number per call
        call_count = [0]

        def get_embeddings(texts):
            call_count[0] += 1
            return AsyncMock(return_value=[[0.1] * 768 for _ in range(len(texts))])()

        mock_embeddings.aembed_documents = get_embeddings

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=configs,
        )

        source = ContentSource(
            source_id="test-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="test.txt"),
        )

        count = await service.index_source(source, max_concurrency=10)

        # Verify all chunks from all configs were processed
        assert count == total_expected
        assert len(indexed_chunks) == total_expected

    @pytest.mark.asyncio
    async def test_index_source_handles_empty_content(self):
        """Test that index_source handles empty content gracefully."""
        mock_es = MagicMock()
        mock_es.index_chunk = AsyncMock()
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=100, overlap=10)

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[])

        service = UnifiedIndexingService(
            es_client=mock_es,
            embeddings=mock_embeddings,
            chunk_configs=[config],
        )

        source = ContentSource(
            source_id="test-doc",
            source_type="document",
            content="",  # Empty content
            metadata=ContentMetadata(filename="empty.txt"),
        )

        count = await service.index_source(source, max_concurrency=10)

        # Should return 0 for empty content
        assert count == 0


class TestParallelIndexingTiming:
    """Tests for parallel indexing timing behavior."""

    @pytest.mark.asyncio
    async def test_parallel_indexing_is_faster_than_sequential(self):
        """Test that parallel indexing completes faster than sequential would.

        This verifies that concurrent operations actually run in parallel,
        not sequentially.
        """
        call_times = []

        async def mock_index_chunk(doc):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)  # Simulate network delay

        mock_es = MagicMock()
        mock_es.index_chunk = mock_index_chunk
        mock_es.create_index = AsyncMock()

        config = ChunkConfig(level=1, window_size=100, overlap=10)
        content = "Parallel test content. " * 100  # Multiple chunks

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
            source_id="test-doc",
            source_type="document",
            content=content,
            metadata=ContentMetadata(filename="test.txt"),
        )

        # Run with high concurrency
        await service.index_source(source, max_concurrency=10)

        if len(call_times) > 1:
            # Calculate time span of all calls
            time_span = max(call_times) - min(call_times)

            # If sequential, time would be num_chunks * 0.05
            # If parallel with semaphore, time should be much less
            sequential_time = len(call_times) * 0.05

            # Parallel execution should complete in less than half the sequential time
            assert time_span < sequential_time * 0.5, \
                f"Parallel execution took {time_span}s, expected less than {sequential_time * 0.5}s"

    @pytest.mark.asyncio
    async def test_index_source_with_different_concurrency_limits(self):
        """Test that different concurrency limits affect execution behavior."""
        results = {}

        for max_concurrency in [1, 5, 10]:
            concurrent_count = 0
            max_observed = 0
            lock = asyncio.Lock()

            async def mock_index_chunk(doc):
                nonlocal concurrent_count, max_observed
                async with lock:
                    concurrent_count += 1
                    max_observed = max(max_observed, concurrent_count)

                await asyncio.sleep(0.01)

                async with lock:
                    concurrent_count -= 1

            mock_es = MagicMock()
            mock_es.index_chunk = mock_index_chunk
            mock_es.create_index = AsyncMock()

            config = ChunkConfig(level=1, window_size=50, overlap=5)
            content = "Conc test. " * 50

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
                source_id=f"test-doc-{max_concurrency}",
                source_type="document",
                content=content,
                metadata=ContentMetadata(filename="test.txt"),
            )

            await service.index_source(source, max_concurrency=max_concurrency)
            results[max_concurrency] = max_observed

        # With concurrency=1, max should be 1 (sequential)
        assert results[1] == 1

        # With higher concurrency, max observed should still respect limits
        assert results[5] <= 5
        assert results[10] <= 10
