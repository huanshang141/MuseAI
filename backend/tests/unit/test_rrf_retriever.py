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
