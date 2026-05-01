"""Merged retrieval tests combining:
- test_rag_fusion.py: RRF fusion algorithm unit tests
- test_rrf_retriever.py: RRFRetriever and UnifiedRetriever tests
- test_retriever_parallelism.py: Parallel execution tests for hybrid retrieval
- test_parallel_indexing.py: Behavior-based tests for parallel indexing
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentMetadata, ContentSource
from app.application.unified_indexing_service import UnifiedIndexingService
from app.domain.services.retrieval import rrf_fusion
from app.infra.langchain.retrievers import RRFRetriever, UnifiedRetriever
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# test_rag_fusion.py — RRF fusion algorithm unit tests
# ---------------------------------------------------------------------------


def test_rrf_fusion_basic():
    """基本融合测试"""
    dense_results = [
        {"chunk_id": "A", "content": "doc A"},
        {"chunk_id": "B", "content": "doc B"},
        {"chunk_id": "C", "content": "doc C"},
    ]
    bm25_results = [
        {"chunk_id": "B", "content": "doc B"},
        {"chunk_id": "D", "content": "doc D"},
        {"chunk_id": "A", "content": "doc A"},
    ]

    fused = rrf_fusion(dense_results, bm25_results, k=60)

    assert len(fused) == 4
    assert fused[0]["chunk_id"] == "B"
    assert fused[1]["chunk_id"] == "A"
    assert fused[2]["chunk_id"] == "D"
    assert fused[3]["chunk_id"] == "C"

    assert fused[0]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61, rel=1e-4)
    assert fused[1]["rrf_score"] == pytest.approx(1 / 61 + 1 / 63, rel=1e-4)
    assert fused[2]["rrf_score"] == pytest.approx(1 / 62, rel=1e-4)
    assert fused[3]["rrf_score"] == pytest.approx(1 / 63, rel=1e-4)


def test_rrf_fusion_empty_lists():
    """空列表测试"""
    assert rrf_fusion([], []) == []
    assert rrf_fusion([{"chunk_id": "A"}], []) == [{"chunk_id": "A", "rrf_score": pytest.approx(1 / 61)}]


def test_rrf_fusion_custom_k():
    """自定义 k 参数测试"""
    dense_results = [{"chunk_id": "A"}]
    bm25_results = [{"chunk_id": "A"}]

    fused_k60 = rrf_fusion(dense_results, bm25_results, k=60)
    fused_k1 = rrf_fusion(dense_results, bm25_results, k=1)

    assert fused_k1[0]["rrf_score"] > fused_k60[0]["rrf_score"]


def test_rrf_fusion_preserves_metadata():
    """保留元数据测试"""
    dense_results = [
        {"chunk_id": "A", "content": "doc A", "title": "Title A"},
    ]
    bm25_results = [
        {"chunk_id": "A", "content": "doc A", "title": "Title A"},
    ]

    fused = rrf_fusion(dense_results, bm25_results)

    assert fused[0]["chunk_id"] == "A"
    assert fused[0]["content"] == "doc A"
    assert fused[0]["title"] == "Title A"
    assert "rrf_score" in fused[0]


def test_rrf_fusion_invalid_k():
    """k 参数验证测试"""
    with pytest.raises(ValueError, match="k must be positive"):
        rrf_fusion([{"chunk_id": "A"}], [], k=0)

    with pytest.raises(ValueError, match="k must be positive"):
        rrf_fusion([{"chunk_id": "A"}], [], k=-1)


def test_rrf_fusion_missing_chunk_id():
    """chunk_id 缺失验证测试"""
    with pytest.raises(ValueError, match="missing 'chunk_id' field"):
        rrf_fusion([{"content": "no id"}], [])

    with pytest.raises(ValueError, match="missing 'chunk_id' field"):
        rrf_fusion([], [{"content": "no id"}])


def test_rrf_fusion_deduplicates_by_source_id():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-a", "content": "A2"},
        {"chunk_id": "c3", "source_id": "doc-b", "content": "B1"},
    ]
    bm25 = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c3", "source_id": "doc-b", "content": "B1"},
        {"chunk_id": "c4", "source_id": "doc-c", "content": "C1"},
    ]
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by="source_id", top_k=3)
    source_ids = [r["source_id"] for r in result]
    assert len(source_ids) == len(set(source_ids)), "Results should be deduplicated by source_id"
    assert "doc-a" in source_ids
    assert "doc-b" in source_ids
    assert "doc-c" in source_ids


def test_rrf_fusion_deduplicate_preserves_highest_score():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-a", "content": "A2"},
    ]
    bm25 = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
    ]
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by="source_id")
    assert len(result) == 1
    assert result[0]["chunk_id"] == "c1"


def test_rrf_fusion_deduplicate_fallback_to_chunk_id():
    dense = [
        {"chunk_id": "c1", "content": "A1"},
        {"chunk_id": "c2", "content": "A2"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by="source_id")
    assert len(result) == 2


def test_rrf_fusion_top_k_limits_results():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-b", "content": "B1"},
        {"chunk_id": "c3", "source_id": "doc-c", "content": "C1"},
        {"chunk_id": "c4", "source_id": "doc-d", "content": "D1"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, top_k=2)
    assert len(result) == 2


def test_rrf_fusion_no_dedup_when_none():
    dense = [
        {"chunk_id": "c1", "source_id": "doc-a", "content": "A1"},
        {"chunk_id": "c2", "source_id": "doc-a", "content": "A2"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, deduplicate_by=None)
    assert len(result) == 2


def test_rrf_fusion_top_k_zero_raises():
    with pytest.raises(ValueError, match="top_k must be positive"):
        rrf_fusion([{"chunk_id": "c1"}], [], k=60, top_k=0)


def test_rrf_fusion_top_k_negative_raises():
    with pytest.raises(ValueError, match="top_k must be positive"):
        rrf_fusion([{"chunk_id": "c1"}], [], k=60, top_k=-1)


def test_rrf_fusion_top_k_greater_than_results():
    dense = [
        {"chunk_id": "c1", "content": "A1"},
        {"chunk_id": "c2", "content": "A2"},
    ]
    bm25 = []
    result = rrf_fusion(dense, bm25, k=60, top_k=10)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# test_rrf_retriever.py — RRFRetriever and UnifiedRetriever tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retriever_returns_documents():
    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(
        return_value=[{"chunk_id": "1", "content": "dense result", "document_id": "doc1", "chunk_level": 1}]
    )
    mock_es.search_bm25 = AsyncMock(
        return_value=[{"chunk_id": "2", "content": "bm25 result", "document_id": "doc2", "chunk_level": 1}]
    )

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = RRFRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
    )

    docs = await retriever._aget_relevant_documents("test query")

    assert len(docs) > 0
    assert isinstance(docs[0], Document)
    assert "chunk_id" in docs[0].metadata


@pytest.mark.asyncio
async def test_unified_retriever_searches_all_content_types():
    """Test that UnifiedRetriever searches all content types."""
    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(
        return_value=[
            {"chunk_id": "1", "content": "document chunk", "source_id": "doc1", "source_type": "document"},
            {"chunk_id": "2", "content": "exhibit chunk", "source_id": "ex1", "source_type": "exhibit"},
        ]
    )
    mock_es.search_bm25 = AsyncMock(
        return_value=[
            {"chunk_id": "1", "content": "document chunk", "source_id": "doc1", "source_type": "document"},
        ]
    )

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
    )

    docs = await retriever._aget_relevant_documents("test query")

    assert len(docs) > 0
    # Verify both dense and bm25 were called
    mock_es.search_dense.assert_called_once()
    mock_es.search_bm25.assert_called_once()


@pytest.mark.asyncio
async def test_unified_retriever_filters_by_source_type():
    """Test that UnifiedRetriever can filter by source type."""
    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(return_value=[])
    mock_es.search_bm25 = AsyncMock(return_value=[])

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
        source_types=["exhibit"],
    )

    await retriever._aget_relevant_documents("test query")

    # Verify source_types was passed
    call_args = mock_es.search_dense.call_args
    assert call_args[1]["source_types"] == ["exhibit"]


# ---------------------------------------------------------------------------
# test_retriever_parallelism.py — Parallel execution tests for hybrid retrieval
# ---------------------------------------------------------------------------


class TestUnifiedRetrieverParallelism:
    """Tests for parallel execution of dense and BM25 retrieval."""

    @pytest.mark.asyncio
    async def test_unified_retriever_executes_dense_and_bm25_in_parallel(self):
        """UnifiedRetriever should execute dense and BM25 searches in parallel.

        If both searches take ~100ms each, sequential execution would take ~200ms,
        but parallel execution should complete in ~100ms.
        We assert < 180ms to allow for some overhead while ensuring parallelism.
        """
        # Create mock ES client with simulated delays
        mock_es_client = MagicMock()

        async def slow_dense_search(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return [
                {"chunk_id": "dense-1", "content": "Dense result 1", "rrf_score": 0.9},
                {"chunk_id": "dense-2", "content": "Dense result 2", "rrf_score": 0.8},
            ]

        async def slow_bm25_search(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return [
                {"chunk_id": "bm25-1", "content": "BM25 result 1", "rrf_score": 0.85},
                {"chunk_id": "bm25-2", "content": "BM25 result 2", "rrf_score": 0.75},
            ]

        mock_es_client.search_dense = slow_dense_search
        mock_es_client.search_bm25 = slow_bm25_search

        # Create mock embeddings
        mock_embeddings = MagicMock()
        mock_embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])

        retriever = UnifiedRetriever(
            es_client=mock_es_client,
            embeddings=mock_embeddings,
            top_k=5,
        )

        # Measure execution time
        started = time.perf_counter()
        await retriever._aget_relevant_documents("test query")
        elapsed = time.perf_counter() - started

        # If executed sequentially, would take ~200ms
        # Parallel execution should take ~100ms (plus embedding overhead)
        # Allow 80ms for overhead, so total < 180ms
        assert elapsed < 0.18, (
            f"Retrieval took {elapsed:.3f}s, expected < 0.18s. "
            "Dense and BM25 searches may not be running in parallel."
        )

    @pytest.mark.asyncio
    async def test_unified_retriever_returns_fused_results(self):
        """UnifiedRetriever should return fused results from both dense and BM25."""
        mock_es_client = MagicMock()

        async def mock_dense_search(*args, **kwargs):
            return [
                {"chunk_id": "dense-1", "content": "Dense result 1"},
                {"chunk_id": "dense-2", "content": "Dense result 2"},
            ]

        async def mock_bm25_search(*args, **kwargs):
            return [
                {"chunk_id": "bm25-1", "content": "BM25 result 1"},
                {"chunk_id": "bm25-2", "content": "BM25 result 2"},
            ]

        mock_es_client.search_dense = mock_dense_search
        mock_es_client.search_bm25 = mock_bm25_search

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])

        retriever = UnifiedRetriever(
            es_client=mock_es_client,
            embeddings=mock_embeddings,
            top_k=5,
        )

        documents = await retriever._aget_relevant_documents("test query")

        # Should return documents from fusion
        assert len(documents) > 0
        assert all(hasattr(doc, "page_content") for doc in documents)
        assert all(hasattr(doc, "metadata") for doc in documents)


@pytest.mark.asyncio
async def test_unified_retriever_deduplicates_by_source_id():
    mock_es_client = MagicMock()

    async def mock_dense_search(*args, **kwargs):
        return [
            {"chunk_id": "c1", "source_id": "doc-a", "content": "A1", "chunk_level": 2},
            {"chunk_id": "c2", "source_id": "doc-a", "content": "A2", "chunk_level": 2},
            {"chunk_id": "c3", "source_id": "doc-b", "content": "B1", "chunk_level": 2},
        ]

    async def mock_bm25_search(*args, **kwargs):
        return [
            {"chunk_id": "c1", "source_id": "doc-a", "content": "A1", "chunk_level": 2},
            {"chunk_id": "c3", "source_id": "doc-b", "content": "B1", "chunk_level": 2},
            {"chunk_id": "c4", "source_id": "doc-c", "content": "C1", "chunk_level": 2},
        ]

    mock_es_client.search_dense = mock_dense_search
    mock_es_client.search_bm25 = mock_bm25_search

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es_client,
        embeddings=mock_embeddings,
        top_k=3,
        rrf_k=60,
    )

    docs = await retriever._aget_relevant_documents("query")
    source_ids = [d.metadata["source_id"] for d in docs]
    assert len(source_ids) == len(set(source_ids))
    assert len(docs) == 3
    assert all(d.metadata.get("source") is not None for d in docs)


@pytest.mark.asyncio
async def test_unified_retriever_includes_parent_chunk_id():
    mock_es_client = MagicMock()

    async def mock_dense_search(*args, **kwargs):
        return [
            {"chunk_id": "c1", "source_id": "doc-a", "content": "A1", "chunk_level": 3, "parent_chunk_id": "p1"},
        ]

    async def mock_bm25_search(*args, **kwargs):
        return []

    mock_es_client.search_dense = mock_dense_search
    mock_es_client.search_bm25 = mock_bm25_search

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es_client,
        embeddings=mock_embeddings,
        top_k=5,
    )

    docs = await retriever._aget_relevant_documents("query")
    assert len(docs) == 1
    assert docs[0].metadata.get("parent_chunk_id") == "p1"


@pytest.mark.asyncio
async def test_unified_retriever_source_field_from_metadata_filename():
    mock_es_client = MagicMock()

    async def mock_dense_search(*args, **kwargs):
        return [
            {
                "chunk_id": "c1",
                "source_id": "doc-a",
                "content": "A1",
                "chunk_level": 2,
                "metadata": {"filename": "test.pdf"},
            },
        ]

    async def mock_bm25_search(*args, **kwargs):
        return []

    mock_es_client.search_dense = mock_dense_search
    mock_es_client.search_bm25 = mock_bm25_search

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es_client,
        embeddings=mock_embeddings,
        top_k=5,
    )

    docs = await retriever._aget_relevant_documents("query")
    assert len(docs) == 1
    assert docs[0].metadata.get("source") == "test.pdf"


@pytest.mark.asyncio
async def test_unified_retriever_passes_chunk_levels():
    mock_es_client = MagicMock()

    async def mock_dense_search(*args, **kwargs):
        return [{"chunk_id": "c1", "source_id": "doc-a", "content": "A1", "chunk_level": 2}]

    async def mock_bm25_search(*args, **kwargs):
        return []

    mock_es_client.search_dense = mock_dense_search
    mock_es_client.search_bm25 = mock_bm25_search

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es_client,
        embeddings=mock_embeddings,
        top_k=5,
        chunk_levels=[2, 3],
    )

    docs = await retriever._aget_relevant_documents("query")
    assert len(docs) == 1


# ---------------------------------------------------------------------------
# test_parallel_indexing.py — Behavior-based tests for parallel indexing
# ---------------------------------------------------------------------------


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

        chunker1 = TextChunker(configs[0])
        level1 = chunker1.chunk(text=content, document_id="test-doc", source="document")

        chunker2 = TextChunker(configs[1])
        level2 = []
        for parent in level1:
            children = chunker2.chunk(text=parent.content, document_id="test-doc", source="document")
            level2.extend(children)

        total_expected = len(level1) + len(level2)

        mock_embeddings = MagicMock()
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

            async def mock_index_chunk(doc, _lock: asyncio.Lock = lock):
                nonlocal concurrent_count, max_observed
                async with _lock:
                    concurrent_count += 1
                    max_observed = max(max_observed, concurrent_count)

                await asyncio.sleep(0.01)

                async with _lock:
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
