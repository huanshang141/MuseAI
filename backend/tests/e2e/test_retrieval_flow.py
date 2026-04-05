import uuid

import pytest
from app.application.chunking import ChunkConfig, TextChunker
from app.application.retrieval import rrf_fusion
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.providers.embedding import OllamaEmbeddingProvider


@pytest.mark.asyncio
async def test_dense_search_returns_results(
    es_client: ElasticsearchClient,
    embedding_provider: OllamaEmbeddingProvider,
    sample_document_content: str,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    doc_id = f"doc-dense-{uuid.uuid4()}"
    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content, document_id=doc_id, source="test.txt")

    for chunk in chunks[:3]:
        embedding = await embedding_provider.embed(chunk.content)
        chunk_doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk.document_id,
            "chunk_level": chunk.level,
            "content": chunk.content,
            "content_vector": embedding,
            "source": chunk.source or "",
        }
        await es_client.index_chunk(chunk_doc)

    await es_client.client.indices.refresh(index=index_name)

    query_text = "青铜器"
    query_embedding = await embedding_provider.embed(query_text)
    results = await es_client.search_dense(query_embedding, top_k=5)

    assert len(results) > 0, "Dense search should return results"
    assert all("chunk_id" in r for r in results), "All results should have chunk_id"


@pytest.mark.asyncio
async def test_bm25_search_returns_results(
    es_client: ElasticsearchClient,
    embedding_provider: OllamaEmbeddingProvider,
    sample_document_content: str,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    doc_id = f"doc-bm25-{uuid.uuid4()}"
    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content, document_id=doc_id, source="test.txt")

    for chunk in chunks[:3]:
        embedding = await embedding_provider.embed(chunk.content)
        chunk_doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk.document_id,
            "chunk_level": chunk.level,
            "content": chunk.content,
            "content_vector": embedding,
            "source": chunk.source or "",
        }
        await es_client.index_chunk(chunk_doc)

    await es_client.client.indices.refresh(index=index_name)

    query_text = "瓷器"
    results = await es_client.search_bm25(query_text, top_k=5)

    assert len(results) > 0, "BM25 search should return results"


@pytest.mark.asyncio
async def test_rrf_fusion_combines_results(
    es_client: ElasticsearchClient,
    embedding_provider: OllamaEmbeddingProvider,
    sample_document_content: str,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    doc_id = f"doc-rrf-{uuid.uuid4()}"
    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content, document_id=doc_id, source="test.txt")

    for chunk in chunks[:5]:
        embedding = await embedding_provider.embed(chunk.content)
        chunk_doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk.document_id,
            "chunk_level": chunk.level,
            "content": chunk.content,
            "content_vector": embedding,
            "source": chunk.source or "",
        }
        await es_client.index_chunk(chunk_doc)

    await es_client.client.indices.refresh(index=index_name)

    query_text = "玉器"
    query_embedding = await embedding_provider.embed(query_text)

    dense_results = await es_client.search_dense(query_embedding, top_k=5)
    bm25_results = await es_client.search_bm25(query_text, top_k=5)

    fused_results = rrf_fusion(dense_results, bm25_results, k=60)

    assert len(fused_results) > 0, "RRF fusion should return results"
    assert all("rrf_score" in r for r in fused_results), "All results should have rrf_score"
    assert all("chunk_id" in r for r in fused_results), "All results should have chunk_id"

    scores = [r["rrf_score"] for r in fused_results]
    assert scores == sorted(scores, reverse=True), "Results should be sorted by rrf_score descending"


@pytest.mark.asyncio
async def test_full_retrieval_pipeline(
    es_client: ElasticsearchClient,
    embedding_provider: OllamaEmbeddingProvider,
    sample_document_content: str,
    test_settings,
    clean_es_index,
):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    await es_client.create_index(index_name=index_name, dims=test_settings.EMBEDDING_DIMS)

    doc_id = f"doc-full-{uuid.uuid4()}"
    chunker = TextChunker(ChunkConfig(level=1, window_size=500, overlap=50))
    chunks = chunker.chunk(sample_document_content, document_id=doc_id, source="museum_sample.txt")

    embeddings = await embedding_provider.embed_batch([c.content for c in chunks], max_concurrency=3)

    for chunk, embedding in zip(chunks, embeddings):
        chunk_doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk.document_id,
            "chunk_level": chunk.level,
            "content": chunk.content,
            "content_vector": embedding,
            "source": chunk.source or "",
        }
        await es_client.index_chunk(chunk_doc)

    await es_client.client.indices.refresh(index=index_name)

    query_text = "书画艺术"
    query_embedding = await embedding_provider.embed(query_text)

    dense_results = await es_client.search_dense(query_embedding, top_k=5)
    bm25_results = await es_client.search_bm25(query_text, top_k=5)

    fused_results = rrf_fusion(dense_results, bm25_results, k=60)

    assert len(fused_results) > 0, "Full pipeline should return results"
    assert any("书画" in r.get("content", "") for r in fused_results[:3]), "Top results should be relevant to query"
