from unittest.mock import AsyncMock

import pytest
from app.infra.langchain.retrievers import RRFRetriever
from langchain_core.documents import Document


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
    from app.infra.langchain.retrievers import UnifiedRetriever

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
    from app.infra.langchain.retrievers import UnifiedRetriever

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
