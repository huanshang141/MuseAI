"""Tests for retriever parallelism in hybrid retrieval."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infra.langchain.retrievers import UnifiedRetriever


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
