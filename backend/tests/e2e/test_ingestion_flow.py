# backend/tests/e2e/test_ingestion_flow.py
import uuid

import pytest

from app.application.chunking import Chunk, ChunkConfig, TextChunker
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.providers.embedding import OllamaEmbeddingProvider


@pytest.mark.asyncio
async def test_chunk_text_produces_valid_chunks(sample_document_content: str):
    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content, document_id="test-doc-1", source="museum_sample.txt")

    assert len(chunks) > 0, "Should produce at least one chunk"
    assert all(len(c.content) <= 500 for c in chunks), "All chunks should respect window size"
    assert all(c.document_id == "test-doc-1" for c in chunks), "All chunks should have correct document_id"
    assert all(c.level == 1 for c in chunks), "All chunks should have correct level"


@pytest.mark.asyncio
async def test_embedding_provider_generates_correct_dimensions(
    embedding_provider: OllamaEmbeddingProvider,
    test_settings,
):
    sample_text = "这是一段测试文本，用于验证嵌入生成功能。"
    embedding = await embedding_provider.embed(sample_text)

    assert len(embedding) == test_settings.EMBEDDING_DIMS, (
        f"Expected {test_settings.EMBEDDING_DIMS} dims, got {len(embedding)}"
    )
    assert all(isinstance(v, float) for v in embedding), "All values should be floats"


@pytest.mark.asyncio
async def test_embedding_batch_processes_multiple_texts(
    embedding_provider: OllamaEmbeddingProvider,
    test_settings,
):
    texts = [
        "第一段测试文本。",
        "第二段测试文本。",
        "第三段测试文本。",
    ]
    embeddings = await embedding_provider.embed_batch(texts, max_concurrency=2)

    assert len(embeddings) == 3, "Should return 3 embeddings"
    assert all(len(e) == test_settings.EMBEDDING_DIMS for e in embeddings), "All embeddings should have correct dims"


@pytest.mark.asyncio
async def test_elasticsearch_index_creation(
    es_client: ElasticsearchClient,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    result = await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    assert result["status"] in ["already_exists", "acknowledged"], "Index should be created or already exist"


@pytest.mark.asyncio
async def test_elasticsearch_index_and_search_chunk(
    es_client: ElasticsearchClient,
    embedding_provider: OllamaEmbeddingProvider,
    sample_document_content: str,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content[:1000], document_id="test-doc-search", source="test.txt")

    test_chunk = chunks[0]
    embedding = await embedding_provider.embed(test_chunk.content)

    chunk_doc = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": test_chunk.document_id,
        "chunk_level": test_chunk.level,
        "content": test_chunk.content,
        "content_vector": embedding,
        "source": test_chunk.source,
    }

    await es_client.index_chunk(chunk_doc)

    results = await es_client.search_dense(embedding, top_k=1)

    assert len(results) > 0, "Should find at least one result"
    assert results[0]["document_id"] == "test-doc-search", "Should find the indexed document"


@pytest.mark.asyncio
async def test_full_ingestion_pipeline(
    es_client: ElasticsearchClient,
    embedding_provider: OllamaEmbeddingProvider,
    sample_document_content: str,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    doc_id = f"doc-{uuid.uuid4()}"

    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content, document_id=doc_id, source="museum_sample.txt")

    assert len(chunks) > 0, "Should produce chunks"

    embeddings = await embedding_provider.embed_batch([c.content for c in chunks[:3]], max_concurrency=2)

    assert len(embeddings) == min(3, len(chunks)), "Should generate embeddings for requested chunks"

    for i, (chunk, embedding) in enumerate(zip(chunks[:3], embeddings)):
        chunk_doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk.document_id,
            "chunk_level": chunk.level,
            "content": chunk.content,
            "content_vector": embedding,
            "source": chunk.source or "",
        }
        await es_client.index_chunk(chunk_doc)

    query_embedding = embeddings[0]
    results = await es_client.search_dense(query_embedding, top_k=3)

    assert len(results) > 0, "Should find results after ingestion"
    assert any(r["document_id"] == doc_id for r in results), "Should find our document in results"
