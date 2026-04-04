# Phase 0 E2E Integration Test Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create end-to-end integration tests for Phase 0 (Tasks 1-11) using real PostgreSQL, Elasticsearch, and Ollama services.

**Architecture:** Tests validate the complete document ingestion and retrieval pipeline. Uses real service connections, preset museum test data, and basic verification of results.

**Tech Stack:** pytest, pytest-asyncio, httpx, SQLAlchemy async, Elasticsearch async client, httpx for Ollama

---

## Task 1: Create E2E Test Directory Structure

**Files:**
- Create: `backend/tests/e2e/__init__.py`
- Create: `backend/tests/e2e/test_data/`
- Create: `backend/tests/e2e/test_data/museum_sample.txt`

**Step 1: Create directory structure**

Run:
```bash
mkdir -p backend/tests/e2e/test_data
touch backend/tests/e2e/__init__.py
```

**Step 2: Create sample museum document**

```python
# backend/tests/e2e/test_data/museum_sample.txt
博物馆藏品介绍

青铜器展区
本展区展示了中国古代青铜器的精湛工艺。商代晚期的司母戊鼎重达832.84公斤，是世界上已发现的最大青铜器。鼎身四周饰有龙纹和饕餮纹，工艺精湛，体现了商代青铜铸造的最高水平。展柜中还陈列着各类青铜礼器、兵器和生活用具，包括爵、觚、尊、编钟等珍贵文物。

书画艺术厅
这里收藏了唐宋元明清各代名家真迹。唐代颜真卿的《祭侄文稿》被誉为天下第二行书，笔力雄浑，情感真挚。宋代苏轼的《寒食帖》行笔沉着痛快，展现了文人的风骨气节。元代赵孟頫的山水画意境深远，明代文徵明的小楷工整秀丽，清代郑板桥的竹石图更是传世佳作。

瓷器珍品馆
宋代五大名窑的代表作品尽收于此。汝窑天青釉温润如玉，有雨过天青云破处之美誉。官窑瓷器胎薄釉厚，开片自然形成冰裂纹。哥窑的金丝铁线纹路独特，钧窑的窑变色彩斑斓，定窑的白瓷洁白细腻。明清两代的景德镇御窑瓷器更是精美绝伦，青花、粉彩、珐琅彩各具特色。

玉器陈列室
从新石器时代的玉璧玉琮，到清代乾隆年间的玉山子，中国玉文化源远流长。红山文化的玉龙造型古朴，良渚文化的玉琮刻工精细。汉代的玉衣由数千片玉片用金丝穿缀而成，是帝王贵族的殓服。清代的翠玉白菜栩栩如生，是台北故宫的镇馆之宝。

古代家具展
明式家具以简约著称，线条流畅，榫卯结构精巧。黄花梨木制成的圈椅、官帽椅造型典雅，紫檀木的书案、画案沉稳大气。清代家具则更加华丽繁复，雕工精细，镶嵌工艺精湛。展出的龙椅、屏风、博古架等都是宫廷御用家具的代表作品。
```

**Step 3: Commit**

```bash
git add backend/tests/e2e/
git commit -m "test: add E2E test structure and sample museum data"
```

---

## Task 2: Create E2E Test Fixtures

**Files:**
- Create: `backend/tests/e2e/conftest.py`

**Step 1: Write the fixtures file**

```python
# backend/tests/e2e/conftest.py
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import get_session_maker, get_session, init_database, close_database
from app.infra.postgres.models import Base, User
from app.infra.providers.embedding import OllamaEmbeddingProvider


def get_test_settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return get_test_settings()


@pytest.fixture(scope="session")
async def db_engine(test_settings: Settings):
    await init_database(test_settings.DATABASE_URL)
    yield
    await close_database()


@pytest.fixture
async def db_session(db_engine, test_settings: Settings):
    session_maker = get_session_maker(test_settings.DATABASE_URL)
    async with get_session(session_maker) as session:
        engine = session_maker.kw.get("bind")
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        existing_user = await session.execute(text("SELECT id FROM users WHERE id = 'test-user-e2e'"))
        if not existing_user.scalar_one_or_none():
            test_user = User(id="test-user-e2e", email="e2e@test.com", password_hash="test_hash")
            session.add(test_user)
            await session.commit()

        yield session


@pytest.fixture
async def es_client(test_settings: Settings):
    async with ElasticsearchClient(
        hosts=[test_settings.ELASTICSEARCH_URL],
        index_name=f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test",
    ) as client:
        yield client


@pytest.fixture
async def embedding_provider(test_settings: Settings):
    async with OllamaEmbeddingProvider(
        base_url=test_settings.EMBEDDING_OLLAMA_BASE_URL,
        model=test_settings.EMBEDDING_OLLAMA_MODEL,
        dims=test_settings.EMBEDDING_DIMS,
    ) as provider:
        yield provider


@pytest.fixture
def sample_document_path() -> Path:
    return Path(__file__).parent / "test_data" / "museum_sample.txt"


@pytest.fixture
def sample_document_content(sample_document_path: Path) -> str:
    return sample_document_path.read_text(encoding="utf-8")


@pytest.fixture
async def clean_es_index(es_client: ElasticsearchClient, test_settings: Settings):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    try:
        await es_client.client.indices.delete(index=index_name, ignore_unavailable=True)
    except Exception:
        pass

    yield

    try:
        await es_client.client.indices.delete(index=index_name, ignore_unavailable=True)
    except Exception:
        pass
```

**Step 2: Commit**

```bash
git add backend/tests/e2e/conftest.py
git commit -m "test: add E2E test fixtures for real services"
```

---

## Task 3: Create Document Ingestion Flow Test

**Files:**
- Create: `backend/tests/e2e/test_ingestion_flow.py`

**Step 1: Write the ingestion flow test**

```python
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

    assert len(embedding) == test_settings.EMBEDDING_DIMS, f"Expected {test_settings.EMBEDDING_DIMS} dims, got {len(embedding)}"
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
```

**Step 2: Commit**

```bash
git add backend/tests/e2e/test_ingestion_flow.py
git commit -m "test: add E2E ingestion flow tests"
```

---

## Task 4: Create Retrieval Flow Test

**Files:**
- Create: `backend/tests/e2e/test_retrieval_flow.py`

**Step 1: Write the retrieval flow test**

```python
# backend/tests/e2e/test_retrieval_flow.py
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

    import asyncio
    await asyncio.sleep(1)

    query_text = "青铜器"
    query_embedding = await embedding_provider.embed(query_text)
    results = await es_client.search_dense(query_embedding, top_k=5)

    assert len(results) > 0, "Dense search should return results"
    assert all("chunk_id" in r for r in results), "All results should have chunk_id"


@pytest.mark.asyncio
async def test_bm25_search_returns_results(
    es_client: ElasticsearchClient,
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
        chunk_doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": chunk.document_id,
            "chunk_level": chunk.level,
            "content": chunk.content,
            "content_vector": [0.0] * test_settings.EMBEDDING_DIMS,
            "source": chunk.source or "",
        }
        await es_client.index_chunk(chunk_doc)

    import asyncio
    await asyncio.sleep(1)

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

    import asyncio
    await asyncio.sleep(1)

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

    import asyncio
    await asyncio.sleep(1)

    query_text = "书画艺术"
    query_embedding = await embedding_provider.embed(query_text)

    dense_results = await es_client.search_dense(query_embedding, top_k=5)
    bm25_results = await es_client.search_bm25(query_text, top_k=5)

    fused_results = rrf_fusion(dense_results, bm25_results, k=60)

    assert len(fused_results) > 0, "Full pipeline should return results"
    assert any("书画" in r.get("content", "") for r in fused_results[:3]), "Top results should be relevant to query"
```

**Step 2: Commit**

```bash
git add backend/tests/e2e/test_retrieval_flow.py
git commit -m "test: add E2E retrieval flow tests"
```

---

## Task 5: Create Service Health Check Test

**Files:**
- Create: `backend/tests/e2e/test_service_health.py`

**Step 1: Write the service health test**

```python
# backend/tests/e2e/test_service_health.py
import pytest

from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import get_session_maker, get_session
from app.infra.providers.embedding import OllamaEmbeddingProvider


@pytest.mark.asyncio
async def test_postgres_connection(test_settings):
    session_maker = get_session_maker(test_settings.DATABASE_URL)
    async with get_session(session_maker) as session:
        from sqlalchemy import text
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_elasticsearch_connection(es_client: ElasticsearchClient):
    is_healthy = await es_client.health_check()
    assert is_healthy, "Elasticsearch should be healthy"


@pytest.mark.asyncio
async def test_ollama_embedding_connection(embedding_provider: OllamaEmbeddingProvider):
    embedding = await embedding_provider.embed("test")
    assert len(embedding) > 0, "Ollama embedding should return non-empty vector"
```

**Step 2: Commit**

```bash
git add backend/tests/e2e/test_service_health.py
git commit -m "test: add E2E service health check tests"
```

---

## Task 6: Run All E2E Tests and Verify

**Step 1: Run E2E tests**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/e2e -v --tb=short
```

Expected: All tests pass (may need real services running)

**Step 2: If services not running, provide clear error**

The tests should gracefully skip if services are unavailable, or provide clear error messages about which service failed.

**Step 3: Final commit**

```bash
git add backend/tests/e2e/
git commit -m "test: complete Phase 0 E2E integration tests"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Directory structure and test data | `tests/e2e/__init__.py`, `test_data/museum_sample.txt` |
| 2 | E2E fixtures | `tests/e2e/conftest.py` |
| 3 | Ingestion flow tests | `tests/e2e/test_ingestion_flow.py` |
| 4 | Retrieval flow tests | `tests/e2e/test_retrieval_flow.py` |
| 5 | Service health tests | `tests/e2e/test_service_health.py` |
| 6 | Run and verify | - |

**Total: 6 Tasks**
