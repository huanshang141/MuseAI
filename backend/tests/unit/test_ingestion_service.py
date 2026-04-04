import pytest
from unittest.mock import AsyncMock
from app.application.ingestion_service import IngestionService
from app.application.chunking import ChunkConfig


@pytest.mark.asyncio
async def test_ingestion_service_chunks_and_indexes():
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})
    
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])
    
    service = IngestionService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)],
    )
    
    count = await service.ingest(
        document_id="test-doc",
        content="This is a test document content for chunking and indexing.",
        source="test.txt",
    )
    
    assert count > 0
    assert mock_es.index_chunk.call_count == count
