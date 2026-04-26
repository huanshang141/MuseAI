# RAG 重复召回问题修复 + 多级分块动态合并 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 RAG 检索结果中同一文档的多个重叠 chunk 被同时召回导致的重复内容问题，并实现自底向上的多级分块动态合并策略，提升检索多样性和答案质量。

**Architecture:** 分两阶段实施。Phase 1 在 RRF 融合阶段增加按 `source_id` 去重，修复 `source` 字段缺失问题。Phase 2 在 RAG Agent 的 LangGraph 状态机中于 `retrieve` → `rerank` 之间插入 `merge` 节点，索引阶段建立 `parent_chunk_id` 层级关联，检索阶段按需拉取父 chunk 进行合并。

**Tech Stack:** Python, FastAPI, Elasticsearch, LangChain/LangGraph, AsyncSQLAlchemy

---

## 问题调查报告

### 问题表现

在一次实际的 LLM 调用中，RAG 返回的 3 个 source 存在严重的重复：

| # | 相似度 | 内容摘要 |
|---|--------|----------|
| 1 | 41.4% | 灶体由两个互通的灶膛组成...（完整段落） |
| 2 | 41.4% | 灶体由两个互通的灶膛组成...（与#1几乎完全相同） |
| 3 | 30.7% | 椭圆形，中间以连通火道相接...（#1的后半段） |

三个结果的内容高度重叠，且 `source` 均显示为"未知来源"。

### 根因分析

#### 根因 1：多级分块策略导致同一文档产生大量重叠 chunk

[chunking.py](file:///home/singer/MuseAI/backend/app/application/chunking.py) 中使用了 3 级分块策略：

```python
ChunkConfig(level=1, window_size=2000, overlap=200)
ChunkConfig(level=2, window_size=500, overlap=50)
ChunkConfig(level=3, window_size=100, overlap=10)
```

同一篇文档被切分为大、中、小三种 chunk，每个 level 的 chunk 之间有 `overlap` 重叠。这些来自**同一文档**的 chunk 在 ES 中都是独立文档，拥有独立的 `chunk_id`，但内容高度相似。

#### 根因 2：RRF 融合基于 `chunk_id` 去重，无法识别同一文档的多级 chunk

[retrieval.py:rrf_fusion()](file:///home/singer/MuseAI/backend/app/domain/services/retrieval.py) 使用 `chunk_id` 作为去重键。由于同一文档的 level-1、level-2、level-3 chunk 拥有**不同的 `chunk_id`**，RRF 会将它们视为不同的文档，全部保留。

#### 根因 3：`UnifiedRetriever` 未按 `document_id` / `source_id` 去重

[retrievers.py:UnifiedRetriever._aget_relevant_documents()](file:///home/singer/MuseAI/backend/app/infra/langchain/retrievers.py) 在 RRF 融合后直接取前 `top_k` 个结果，没有按源文档去重。

#### 根因 4：`source` 字段缺失导致前端显示"未知来源"

[UnifiedRetriever._to_document()](file:///home/singer/MuseAI/backend/app/infra/langchain/retrievers.py) 的 metadata 中没有包含 `source` 字段（只有 `source_id` 和 `source_type`）。而 [chat_stream_service.py](file:///home/singer/MuseAI/backend/app/application/chat_stream_service.py) 读取的是 `doc.metadata.get("source")`，导致来源信息丢失。

---

## Chunk 1: Phase 1 — Source 去重 + Source 字段修复

### Task 1: 为 RRF 融合添加按源文档去重功能

**Files:**
- Modify: `backend/app/domain/services/retrieval.py`
- Test: `backend/tests/unit/test_rag_fusion.py`（补充新测试）

- [ ] **Step 1: 编写失败测试**

在 `backend/tests/unit/test_rag_fusion.py` 中追加测试：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest backend/tests/unit/test_rag_fusion.py::test_rrf_fusion_deduplicates_by_source_id -v
```

Expected: FAIL — `rrf_fusion` 不接受 `deduplicate_by` 和 `top_k` 参数。

- [ ] **Step 3: 实现去重逻辑**

修改 `backend/app/domain/services/retrieval.py` 中的 `rrf_fusion`：

```python
def rrf_fusion(
    dense_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    k: int = 60,
    deduplicate_by: str | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    doc_map: dict[str, dict[str, Any]] = {}
    dense_ranks: dict[str, int] = {}
    bm25_ranks: dict[str, int] = {}

    for rank, doc in enumerate(dense_results, start=1):
        if "chunk_id" not in doc:
            raise ValueError(f"Document at rank {rank} in dense_results missing 'chunk_id' field")
        chunk_id = doc["chunk_id"]
        dense_ranks[chunk_id] = rank
        doc_map[chunk_id] = doc

    for rank, doc in enumerate(bm25_results, start=1):
        if "chunk_id" not in doc:
            raise ValueError(f"Document at rank {rank} in bm25_results missing 'chunk_id' field")
        chunk_id = doc["chunk_id"]
        bm25_ranks[chunk_id] = rank
        if chunk_id not in doc_map:
            doc_map[chunk_id] = doc

    rrf_scores: dict[str, float] = {}
    for chunk_id in doc_map:
        score = 0.0
        if chunk_id in dense_ranks:
            score += 1.0 / (k + dense_ranks[chunk_id])
        if chunk_id in bm25_ranks:
            score += 1.0 / (k + bm25_ranks[chunk_id])
        rrf_scores[chunk_id] = score

    sorted_chunk_ids = sorted(
        rrf_scores.keys(),
        key=lambda x: rrf_scores[x],
        reverse=True,
    )

    result = []
    seen_keys: set[str] = set()

    for chunk_id in sorted_chunk_ids:
        doc = doc_map[chunk_id].copy()
        doc["rrf_score"] = rrf_scores[chunk_id]

        if deduplicate_by:
            key = doc.get(deduplicate_by)
            if key is None:
                key = chunk_id
            if key in seen_keys:
                continue
            seen_keys.add(key)

        result.append(doc)

        if top_k is not None and len(result) >= top_k:
            break

    return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest backend/tests/unit/test_rag_fusion.py -v
```

Expected: 所有测试通过（包括原有 6 个测试和新增 5 个测试）

- [ ] **Step 5: 代码审查**

使用 sub-agent 对 `backend/app/domain/services/retrieval.py` 和 `backend/tests/unit/test_rag_fusion.py` 进行代码审查，处理审查意见。

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/services/retrieval.py backend/tests/unit/test_rag_fusion.py
git commit -m "feat(retrieval): add source-level deduplication to rrf_fusion"
```

---

### Task 2: 在 UnifiedRetriever 中启用去重并修复 source 字段

**Files:**
- Modify: `backend/app/infra/langchain/retrievers.py`
- Test: `backend/tests/unit/test_retriever_parallelism.py`（补充新测试）

- [ ] **Step 1: 修改 UnifiedRetriever 调用 RRF 时传入去重参数**

在 `UnifiedRetriever._aget_relevant_documents()` 中：

```python
fused_results = rrf_fusion(
    dense_results,
    bm25_results,
    k=self.rrf_k,
    deduplicate_by="source_id",
    top_k=self.top_k,
)
```

- [ ] **Step 2: 修复 _to_document 中的 source 字段映射**

```python
def _to_document(self, item: dict[str, Any]) -> Document:
    metadata = {
        "chunk_id": item.get("chunk_id"),
        "source_id": item.get("source_id"),
        "source_type": item.get("source_type"),
        "chunk_level": item.get("chunk_level"),
        "rrf_score": item.get("rrf_score"),
        "parent_chunk_id": item.get("parent_chunk_id"),
    }
    if item.get("source"):
        metadata["source"] = item.get("source")
    elif item.get("metadata", {}).get("filename"):
        metadata["source"] = item["metadata"]["filename"]
    elif item.get("metadata", {}).get("name"):
        metadata["source"] = item["metadata"]["name"]
    elif item.get("source_id"):
        metadata["source"] = item.get("source_id")
    return Document(
        page_content=item.get("content", ""),
        metadata=metadata,
    )
```

- [ ] **Step 3: 编写测试**

在 `backend/tests/unit/test_retriever_parallelism.py` 中追加测试：

```python
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
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest backend/tests/unit/test_retriever_parallelism.py -v
```

Expected: PASS

- [ ] **Step 5: 代码审查**

使用 sub-agent 对 `backend/app/infra/langchain/retrievers.py` 和 `backend/tests/unit/test_retriever_parallelism.py` 进行代码审查。

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/langchain/retrievers.py backend/tests/unit/test_retriever_parallelism.py
git commit -m "feat(retrievers): enable source dedup in UnifiedRetriever and fix source field"
```

---

### Task 3: 检查并修复 RRFRetriever / ExhibitAwareRetriever

**Files:**
- Modify: `backend/app/infra/langchain/retrievers.py`

- [ ] **Step 1: 为 RRFRetriever 添加去重和 source 字段修复**

在 `RRFRetriever._aget_relevant_documents()` 中：
1. 调用 `rrf_fusion(..., deduplicate_by="document_id", top_k=self.top_k)`（因为 RRFRetriever 使用旧 schema 的 `document_id`）
2. 确保构建 Document 时 `source` 字段被正确填充

- [ ] **Step 2: 为 ExhibitAwareRetriever 添加去重**

在 `ExhibitAwareRetriever._aget_relevant_documents()` 中：
1. 调用 `rrf_fusion(..., deduplicate_by="document_id", top_k=self.top_k)`
2. 确保构建 Document 时 `source` 字段被正确填充

- [ ] **Step 3: 运行测试**

```bash
uv run pytest backend/tests/unit -k "retriever" -v
```

- [ ] **Step 4: 代码审查**

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/langchain/retrievers.py
git commit -m "feat(retrievers): apply source dedup to deprecated retrievers"
```

---

### Task 4: 运行全量测试和 lint

- [ ] **Step 1: 运行单元测试和契约测试**

```bash
uv run pytest backend/tests/unit backend/tests/contract -v
```

Expected: 全部通过

- [ ] **Step 2: 运行 lint**

```bash
uv run ruff check backend/
```

Expected: 无错误

- [ ] **Step 3: 运行类型检查**

```bash
uv run mypy backend/
```

Expected: 无新增类型错误

- [ ] **Step 4: Commit（如有修复）**

```bash
git commit -m "test: verify Phase 1 RAG deduplication fix passes all checks"
```

---

### Task 5: Phase 1 端到端验证

**Goal:** 构建真实调用链路进行测试，从前端调用 chat 到后端运行 RAG query。

- [ ] **Step 1: 启动基础设施**

```bash
docker-compose up -d
```

- [ ] **Step 2: 启动后端服务**

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

- [ ] **Step 3: 通过 API 进行端到端测试**

使用 curl 或 httpie 调用 chat API，验证：
1. 返回的 sources 中 `source_id` 唯一（无重复）
2. `source` 字段不再显示"未知来源"
3. 检索结果中无内容高度重叠的 chunk

```bash
# 注册/登录获取 token
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234"}'

# 创建 chat session
curl -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Authorization: Bearer <token>"

# 发送消息（SSE 流式）
curl -N http://localhost:8000/api/v1/chat/sessions/<session_id>/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message":"请介绍一下青铜器"}'
```

- [ ] **Step 4: 验证日志输出**

检查后端日志，确认：
- `Doc xxx: rerank_score=..., rrf_score=..., source=...` 中 `source` 不再为 `None`
- 同一 `source_id` 的 chunk 不再重复出现

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "test: Phase 1 e2e verification complete"
```

---

## Chunk 2: Phase 2 — 多级分块动态合并（Hierarchical Chunk Merge）

> **Design Reference:** [hierarchical-chunk-merge-design.md](file:///home/singer/MuseAI/docs/superpowers/specs/2026-04-26-hierarchical-chunk-merge-design.md)

### Task 6: 索引阶段建立 parent-child 关联

**Files:**
- Modify: `backend/app/application/unified_indexing_service.py`
- Modify: `backend/app/application/ingestion_service.py`
- Test: `backend/tests/unit/test_unified_indexing_service.py`（补充）
- Test: `backend/tests/unit/test_chunking.py`（补充）

- [ ] **Step 1: 编写 parent-child 关联测试**

在 `backend/tests/unit/test_chunking.py` 中追加：

```python
def test_chunk_with_parent_chunk_id():
    chunker = TextChunker(ChunkConfig(level=2, window_size=100, overlap=20))
    text = "Test content for chunking."
    chunks = chunker.chunk(text, document_id="doc-1", parent_chunk_id="parent-abc")
    assert all(c.parent_chunk_id == "parent-abc" for c in chunks)


def test_hierarchical_chunking_parent_ids():
    text = "a" * 3000
    configs = [
        ChunkConfig(level=1, window_size=2000, overlap=200),
        ChunkConfig(level=2, window_size=500, overlap=50),
    ]

    chunker1 = TextChunker(configs[0])
    level1 = chunker1.chunk(text, document_id="doc-1")

    chunker2 = TextChunker(configs[1])
    level2: list[Chunk] = []
    for parent in level1:
        children = chunker2.chunk(parent.content, document_id="doc-1", parent_chunk_id=parent.id)
        level2.extend(children)

    assert all(c.parent_chunk_id is not None for c in level2)
    parent_ids = {c.parent_chunk_id for c in level2}
    assert parent_ids == {c.id for c in level1}
```

- [ ] **Step 2: 运行测试确认通过（chunking 已支持 parent_chunk_id）**

```bash
uv run pytest backend/tests/unit/test_chunking.py -v
```

Expected: PASS（`TextChunker.chunk()` 已支持 `parent_chunk_id` 参数）

- [ ] **Step 3: 修改 UnifiedIndexingService 建立层级关联**

将当前的"单层循环切分"改为"层级递进切分"。同时将默认 `chunk_configs` 从 2 级改为 3 级，与 `IngestionService` 保持一致（设计规格要求 RAG 只主动检索 level-3）。

修改 `backend/app/application/unified_indexing_service.py`：

1. 修改默认 `chunk_configs`：

```python
self.chunk_configs = chunk_configs or [
    ChunkConfig(level=1, window_size=2000, overlap=200),
    ChunkConfig(level=2, window_size=500, overlap=50),
    ChunkConfig(level=3, window_size=100, overlap=10),
]
```

2. 修改 `index_source` 方法为层级递进切分：

```python
async def index_source(
    self,
    source: ContentSource,
    max_concurrency: int = 10,
) -> int:
    total_chunks = 0
    prev_level_chunks: list[Chunk] = []

    for config in self.chunk_configs:
        chunker = TextChunker(config)
        current_level_chunks: list[Chunk] = []

        if not prev_level_chunks:
            chunks = chunker.chunk(
                text=source.content,
                document_id=source.source_id,
                source=source.source_type,
            )
            current_level_chunks.extend(chunks)
        else:
            for parent in prev_level_chunks:
                children = chunker.chunk(
                    text=parent.content,
                    document_id=source.source_id,
                    source=source.source_type,
                    parent_chunk_id=parent.id,
                )
                for child in children:
                    child.start_char += parent.start_char
                    child.end_char += parent.start_char
                current_level_chunks.extend(children)

        if not current_level_chunks:
            continue

        chunk_texts = [c.content for c in current_level_chunks]
        embeddings_list = await self.embeddings.aembed_documents(chunk_texts)

        docs = []
        for chunk, embedding in zip(current_level_chunks, embeddings_list, strict=True):
            doc = {
                "chunk_id": chunk.id,
                "source_id": source.source_id,
                "source_type": source.source_type,
                "content": chunk.content,
                "content_vector": embedding,
                "chunk_level": chunk.level,
                "parent_chunk_id": chunk.parent_chunk_id,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "metadata": source.metadata.to_dict(),
            }
            docs.append(doc)
            total_chunks += 1

        semaphore = asyncio.Semaphore(max_concurrency)

        async def index_with_semaphore(
            doc: dict[str, Any],
            sem: asyncio.Semaphore = semaphore,
        ) -> None:
            async with sem:
                await self.es_client.index_chunk(doc)

        await asyncio.gather(*[index_with_semaphore(doc) for doc in docs])

        prev_level_chunks = current_level_chunks

    logger.info(f"Indexed {total_chunks} chunks for source {source.source_id}")
    return total_chunks
```

- [ ] **Step 4: 同步修改 IngestionService**

修改 `backend/app/application/ingestion_service.py` 中的 `ingest` 方法，采用相同的层级递进切分逻辑：

```python
async def ingest(
    self,
    document_id: str,
    content: str,
    source: str | None = None,
    max_concurrency: int = 10,
) -> int:
    total_chunks = 0
    prev_level_chunks: list[Chunk] = []

    for config in self.chunk_configs:
        chunker = TextChunker(config)
        current_level_chunks: list[Chunk] = []

        if not prev_level_chunks:
            chunks = chunker.chunk(
                text=content,
                document_id=document_id,
                source=source,
            )
            current_level_chunks.extend(chunks)
        else:
            for parent in prev_level_chunks:
                children = chunker.chunk(
                    text=parent.content,
                    document_id=document_id,
                    source=source,
                    parent_chunk_id=parent.id,
                )
                for child in children:
                    child.start_char += parent.start_char
                    child.end_char += parent.start_char
                current_level_chunks.extend(children)

        if not current_level_chunks:
            continue

        chunk_texts = [c.content for c in current_level_chunks]
        embeddings_list = await self.embeddings.aembed_documents(chunk_texts)

        docs = []
        for chunk, embedding in zip(current_level_chunks, embeddings_list, strict=False):
            doc = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_level": chunk.level,
                "content": chunk.content,
                "content_vector": embedding,
                "source": chunk.source,
                "parent_chunk_id": chunk.parent_chunk_id,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            }
            docs.append(doc)
            total_chunks += 1

        semaphore = asyncio.Semaphore(max_concurrency)

        async def index_with_semaphore(doc: dict, _sem=semaphore) -> None:
            async with _sem:
                await self.es_client.index_chunk(doc)

        await asyncio.gather(*[index_with_semaphore(doc) for doc in docs])

        prev_level_chunks = current_level_chunks

    return total_chunks
```

- [ ] **Step 5: 更新 UnifiedIndexingService 测试**

在 `backend/tests/unit/test_unified_indexing_service.py` 中追加：

```python
@pytest.mark.asyncio
async def test_unified_indexing_service_hierarchical_parent_ids():
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.1] * 768 for _ in texts]
    )

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[
            ChunkConfig(level=1, window_size=100, overlap=10),
            ChunkConfig(level=2, window_size=50, overlap=5),
        ],
    )

    source = ContentSource(
        source_id="test-doc-hier",
        source_type="document",
        content="A" * 200,
        metadata=ContentMetadata(filename="test.txt"),
    )

    count = await service.index_source(source)
    assert count > 0

    indexed_docs = [call[0][0] for call in mock_es.index_chunk.call_args_list]
    level2_docs = [d for d in indexed_docs if d["chunk_level"] == 2]
    level1_docs = [d for d in indexed_docs if d["chunk_level"] == 1]

    assert len(level1_docs) > 0
    assert len(level2_docs) > 0
    assert all(d["parent_chunk_id"] is not None for d in level2_docs)

    level1_ids = {d["chunk_id"] for d in level1_docs}
    level2_parent_ids = {d["parent_chunk_id"] for d in level2_docs}
    assert level2_parent_ids.issubset(level1_ids)
```

- [ ] **Step 6: 运行测试**

```bash
uv run pytest backend/tests/unit/test_chunking.py backend/tests/unit/test_unified_indexing_service.py backend/tests/unit/test_ingestion_service.py -v
```

- [ ] **Step 7: 代码审查**

使用 sub-agent 审查 `unified_indexing_service.py`、`ingestion_service.py` 及相关测试。

- [ ] **Step 8: Commit**

```bash
git add backend/app/application/unified_indexing_service.py backend/app/application/ingestion_service.py backend/tests/unit/test_chunking.py backend/tests/unit/test_unified_indexing_service.py
git commit -m "feat(chunking): establish parent-child relationships across chunk levels"
```

---

### Task 7: ES 新增按 chunk_id 精确查询方法

**Files:**
- Modify: `backend/app/infra/elasticsearch/client.py`
- Test: `backend/tests/unit/test_es_client.py`（补充）

- [ ] **Step 1: 新增 get_chunk_by_id 方法**

在 `ElasticsearchClient` 中添加：

```python
async def get_chunk_by_id(self, chunk_id: str) -> dict[str, Any] | None:
    try:
        result = await self.client.get(index=self.index_name, id=chunk_id)
        return cast(dict[str, Any], result["_source"])
    except ApiError as e:
        if e.meta and e.meta.status == 404:
            return None
        raise RetrievalError(f"Failed to get chunk {chunk_id}") from e
    except TransportError as e:
        raise RetrievalError(f"Failed to get chunk {chunk_id}") from e
```

- [ ] **Step 2: 编写测试**

在 `backend/tests/unit/test_es_client.py` 中追加：

```python
@pytest.mark.asyncio
async def test_get_chunk_by_id_found():
    mock_es = AsyncMock()
    mock_es.get = AsyncMock(return_value={"_source": {"chunk_id": "c1", "content": "test"}})

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    result = await client.get_chunk_by_id("c1")
    assert result is not None
    assert result["chunk_id"] == "c1"
    mock_es.get.assert_called_once_with(index="test_index", id="c1")


@pytest.mark.asyncio
async def test_get_chunk_by_id_not_found():
    mock_es = AsyncMock()
    api_error = ApiError("Not found", meta=MagicMock(status=404), body=None)
    mock_es.get = AsyncMock(side_effect=api_error)

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    result = await client.get_chunk_by_id("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_chunk_by_id_raises_on_error():
    mock_es = AsyncMock()
    api_error = ApiError("Internal error", meta=MagicMock(status=500), body=None)
    mock_es.get = AsyncMock(side_effect=api_error)

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    with pytest.raises(RetrievalError, match="Failed to get chunk"):
        await client.get_chunk_by_id("c1")
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest backend/tests/unit/test_es_client.py -k "get_chunk" -v
```

- [ ] **Step 4: 代码审查**

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/elasticsearch/client.py backend/tests/unit/test_es_client.py
git commit -m "feat(es): add get_chunk_by_id for parent chunk retrieval"
```

---

### Task 8: 新增合并相关配置到 Settings

**Files:**
- Modify: `backend/app/config/settings.py`

- [ ] **Step 1: 添加合并配置项**

在 `Settings` 类中添加：

```python
RAG_MERGE_ENABLED: bool = True
RAG_MERGE_THRESHOLD: int = 2
RAG_MERGE_BOOST: float = 1.05
RAG_RETRIEVE_LEVEL: int = 3
```

- [ ] **Step 2: 运行配置测试**

```bash
uv run pytest backend/tests/unit/test_config.py -v
```

- [ ] **Step 3: 代码审查**

- [ ] **Step 4: Commit**

```bash
git add backend/app/config/settings.py
git commit -m "feat(config): add RAG merge settings"
```

---

### Task 9: 修改 UnifiedRetriever 支持按 chunk_level 过滤检索

> **重要**：此任务必须在 merge 节点之前实现，因为 merge 节点假设输入是 level-3 chunk。如果不先实现 chunk_level 过滤，merge 节点可能接收到混合 level 的 chunk，导致合并逻辑不正确。

**Files:**
- Modify: `backend/app/infra/elasticsearch/client.py`
- Modify: `backend/app/infra/langchain/retrievers.py`
- Modify: `backend/app/infra/langchain/__init__.py`

- [ ] **Step 1: 为 ES 搜索方法添加 chunk_level 过滤**

在 `search_dense` 和 `search_bm25` 中添加 `chunk_level` 参数：

```python
async def search_dense(
    self,
    query_vector: list[float],
    top_k: int = 5,
    source_types: list[str] | None = None,
    chunk_level: int | None = None,
) -> list[dict[str, Any]]:
    try:
        filter_clauses: list[dict[str, Any]] = []
        if source_types:
            filter_clauses.append({"terms": {"source_type": source_types}})
        if chunk_level is not None:
            filter_clauses.append({"term": {"chunk_level": chunk_level}})

        query: dict[str, Any] = {
            "knn": {
                "field": "content_vector",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": top_k * 10,
            },
            "size": top_k,
        }

        if filter_clauses:
            query["knn"]["filter"] = {"bool": {"filter": filter_clauses}}

        response = await self.client.search(index=self.index_name, body=query)
        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
    except (ApiError, TransportError) as e:
        logger.error(f"Dense search failed: {type(e).__name__}")
        raise RetrievalError("Dense search failed") from e


async def search_bm25(
    self,
    query_text: str,
    top_k: int = 5,
    source_types: list[str] | None = None,
    chunk_level: int | None = None,
) -> list[dict[str, Any]]:
    try:
        must_clauses: list[dict[str, Any]] = [{"match": {"content": query_text}}]
        filter_clauses: list[dict[str, Any]] = []
        if source_types:
            filter_clauses.append({"terms": {"source_type": source_types}})
        if chunk_level is not None:
            filter_clauses.append({"term": {"chunk_level": chunk_level}})

        if filter_clauses:
            query: dict[str, Any] = {
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "filter": filter_clauses,
                    }
                },
                "size": top_k,
            }
        else:
            query = {"query": {"match": {"content": query_text}}, "size": top_k}

        response = await self.client.search(index=self.index_name, body=query)
        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
    except (ApiError, TransportError) as e:
        logger.error(f"BM25 search failed: {type(e).__name__}")
        raise RetrievalError("BM25 search failed") from e
```

- [ ] **Step 2: 修改 UnifiedRetriever 支持 chunk_level 过滤**

在 `UnifiedRetriever` 中添加 `chunk_level` 属性，并在搜索时传入：

```python
class UnifiedRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    es_client: Any
    embeddings: Any
    top_k: int = 5
    rrf_k: int = 60
    source_types: list[str] | None = None
    chunk_level: int | None = None

    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        query_vector = await self.embeddings.aembed_query(query)

        dense_results, bm25_results = await asyncio.gather(
            self.es_client.search_dense(
                query_vector, self.top_k * 2, source_types=self.source_types, chunk_level=self.chunk_level
            ),
            self.es_client.search_bm25(
                query, self.top_k * 2, source_types=self.source_types, chunk_level=self.chunk_level
            ),
        )
        fused_results = rrf_fusion(
            dense_results,
            bm25_results,
            k=self.rrf_k,
            deduplicate_by="source_id",
            top_k=self.top_k,
        )

        documents = []
        for item in fused_results[: self.top_k]:
            doc = self._to_document(item)
            documents.append(doc)

        return documents
```

- [ ] **Step 3: 修改 create_retriever 传入 chunk_level**

在 `backend/app/infra/langchain/__init__.py` 中：

```python
def create_retriever(
    es_client: Any,
    embeddings: CustomOllamaEmbeddings,
    settings: Settings,
) -> UnifiedRetriever:
    return UnifiedRetriever(
        es_client=es_client,
        embeddings=embeddings,
        top_k=5,
        rrf_k=60,
        chunk_level=settings.RAG_RETRIEVE_LEVEL,
    )
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest backend/tests/unit/test_es_client.py backend/tests/unit/test_retriever_parallelism.py -v
```

- [ ] **Step 5: 代码审查**

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/elasticsearch/client.py backend/app/infra/langchain/retrievers.py backend/app/infra/langchain/__init__.py
git commit -m "feat(retrieval): add chunk_level filter to ES search and UnifiedRetriever"
```

---

### Task 10: RAG Agent 新增 merge 节点

**Files:**
- Modify: `backend/app/infra/langchain/agents.py`
- Test: `backend/tests/unit/test_rag_agent.py`（补充）
- Test: `backend/tests/unit/test_merge_node.py`（创建）

- [ ] **Step 1: 修改 RAGAgent.__init__ 接收 merge 配置**

在 `RAGAgent.__init__` 中添加参数：

```python
def __init__(
    self,
    llm: BaseChatModel,
    retriever: BaseRetriever,
    rerank_provider: BaseRerankProvider | None = None,
    query_rewriter: ConversationAwareQueryRewriter | None = None,
    prompt_gateway: PromptGateway | None = None,
    score_threshold: float = SCORE_THRESHOLD,
    max_attempts: int = MAX_ATTEMPTS,
    rerank_top_n: int = 5,
    merge_enabled: bool = True,
    merge_threshold: int = 2,
    merge_boost: float = 1.05,
):
    ...
    self.merge_enabled = merge_enabled
    self.merge_threshold = merge_threshold
    self.merge_boost = merge_boost
    self._graph = self._build_graph()
```

- [ ] **Step 2: 在 RAGAgent 中实现 merge 方法**

```python
async def merge(self, state: RAGState) -> dict[str, Any]:
    documents = state["documents"]

    if not self.merge_enabled or not documents:
        return {"documents": documents}

    from collections import defaultdict

    parent_hits: dict[str, list[Document]] = defaultdict(list)
    standalone: list[Document] = []

    for doc in documents:
        pid = doc.metadata.get("parent_chunk_id")
        if pid:
            parent_hits[pid].append(doc)
        else:
            standalone.append(doc)

    merged: list[Document] = []
    for pid, children in parent_hits.items():
        if len(children) >= self.merge_threshold:
            parent_data = await self._fetch_parent_chunk(pid)
            if parent_data:
                best_score = max(d.metadata.get("rrf_score", 0) for d in children)
                parent_doc = Document(
                    page_content=parent_data.get("content", ""),
                    metadata={
                        "chunk_id": parent_data.get("chunk_id"),
                        "source_id": parent_data.get("source_id"),
                        "source_type": parent_data.get("source_type"),
                        "chunk_level": parent_data.get("chunk_level"),
                        "rrf_score": best_score * self.merge_boost,
                        "merged_from": [d.metadata["chunk_id"] for d in children],
                        "is_merged": True,
                        "parent_chunk_id": parent_data.get("parent_chunk_id"),
                        "source": parent_data.get("source") or parent_data.get("metadata", {}).get("filename") or parent_data.get("metadata", {}).get("name") or parent_data.get("source_id"),
                    },
                )
                merged.append(parent_doc)
                continue
        best = max(children, key=lambda d: d.metadata.get("rrf_score", 0))
        merged.append(best)

    final = standalone + merged
    final.sort(key=lambda d: d.metadata.get("rrf_score", 0), reverse=True)
    return {"documents": final[: self.rerank_top_n * 2]}


async def _fetch_parent_chunk(self, parent_chunk_id: str) -> dict[str, Any] | None:
    try:
        if hasattr(self.retriever, "es_client"):
            return await self.retriever.es_client.get_chunk_by_id(parent_chunk_id)
    except Exception as e:
        logger.warning(f"Failed to fetch parent chunk {parent_chunk_id}: {e}")
    return None
```

> **TODO（后续优化）**：设计规格 2.2.2 提到可选的语义相关性验证——如果 parent chunk 与查询完全不相关，应返回 None 以保留孩子。当前实现未包含此验证，可在后续迭代中通过轻量级 BM25 过滤添加。

> **TODO（后续优化）**：设计规格 7 提到合并后 level-2 chunk 可能过长超出 LLM context 的风险。当前实现未包含 context 长度检查，可在 `merge` 节点输出时检查合并后文档的总字符数，超长时截断或回退到 level-3。

- [ ] **Step 3: 修改 _build_graph 插入 merge 节点**

```python
def _build_graph(self) -> Any:
    workflow = StateGraph(RAGState)

    workflow.add_node("rewrite", self.rewrite_query)
    workflow.add_node("retrieve", self.retrieve)
    workflow.add_node("merge", self.merge)
    workflow.add_node("rerank", self.rerank)
    workflow.add_node("evaluate", self.evaluate)
    workflow.add_node("transform", self.transform)
    workflow.add_node("generate", self.generate)

    workflow.set_entry_point("rewrite")
    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("retrieve", "merge")
    workflow.add_edge("merge", "rerank")
    workflow.add_edge("rerank", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        self._should_transform,
        {
            "transform": "transform",
            "generate": "generate",
        },
    )

    workflow.add_conditional_edges(
        "transform",
        self._should_retry,
        {
            "retry": "rewrite",
            "generate": "generate",
        },
    )

    workflow.add_edge("generate", END)

    return workflow.compile()
```

- [ ] **Step 4: 创建 merge 节点单元测试**

创建 `backend/tests/unit/test_merge_node.py`：

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document
from app.infra.langchain.agents import RAGAgent


@pytest.mark.asyncio
async def test_merge_node_replaces_children_with_parent():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()
    mock_retriever.es_client.get_chunk_by_id = AsyncMock(return_value={
        "chunk_id": "p1",
        "content": "parent content",
        "chunk_level": 2,
        "source_id": "doc-a",
        "source_type": "document",
    })

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_threshold=2,
        merge_boost=1.05,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
        Document(page_content="c3", metadata={"chunk_id": "c3", "parent_chunk_id": "p2", "rrf_score": 0.3}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    merged = result["documents"]
    assert len(merged) == 2
    assert any(d.metadata.get("is_merged") for d in merged)
    assert all(d.metadata.get("chunk_id") != "c2" for d in merged)


@pytest.mark.asyncio
async def test_merge_node_below_threshold_keeps_children():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_threshold=3,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    merged = result["documents"]
    assert len(merged) == 1
    assert not any(d.metadata.get("is_merged") for d in merged)


@pytest.mark.asyncio
async def test_merge_node_disabled_passes_through():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=False,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    assert result["documents"] == docs


@pytest.mark.asyncio
async def test_merge_node_fetch_parent_fallback():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()
    mock_retriever.es_client.get_chunk_by_id = AsyncMock(return_value=None)

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_threshold=2,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    merged = result["documents"]
    assert len(merged) == 1
    assert merged[0].metadata["chunk_id"] == "c1"
    assert not any(d.metadata.get("is_merged") for d in merged)


@pytest.mark.asyncio
async def test_merge_node_empty_documents():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        rerank_top_n=5,
    )

    result = await agent.merge({"documents": [], "query": "test", "rewritten_query": "test"})
    assert result["documents"] == []


@pytest.mark.asyncio
async def test_merge_node_boost_applied():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()
    mock_retriever.es_client.get_chunk_by_id = AsyncMock(return_value={
        "chunk_id": "p1",
        "content": "parent content",
        "chunk_level": 2,
        "source_id": "doc-a",
        "source_type": "document",
    })

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_threshold=2,
        merge_boost=1.1,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    merged = result["documents"]
    assert len(merged) == 1
    assert merged[0].metadata["rrf_score"] == pytest.approx(0.5 * 1.1)
    assert merged[0].metadata["is_merged"] is True
    assert merged[0].metadata["merged_from"] == ["c1", "c2"]


@pytest.mark.asyncio
async def test_merge_node_multiple_parents():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()

    async def mock_get_chunk(chunk_id):
        data = {
            "p1": {"chunk_id": "p1", "content": "parent 1", "chunk_level": 2, "source_id": "doc-a", "source_type": "document"},
            "p2": {"chunk_id": "p2", "content": "parent 2", "chunk_level": 2, "source_id": "doc-b", "source_type": "document"},
        }
        return data.get(chunk_id)

    mock_retriever.es_client.get_chunk_by_id = AsyncMock(side_effect=mock_get_chunk)

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_threshold=2,
        merge_boost=1.05,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
        Document(page_content="c3", metadata={"chunk_id": "c3", "parent_chunk_id": "p2", "rrf_score": 0.3}),
        Document(page_content="c4", metadata={"chunk_id": "c4", "parent_chunk_id": "p2", "rrf_score": 0.2}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    merged = result["documents"]
    assert len(merged) == 2
    assert all(d.metadata.get("is_merged") for d in merged)
    assert merged[0].metadata["chunk_id"] == "p1"
    assert merged[1].metadata["chunk_id"] == "p2"


@pytest.mark.asyncio
async def test_merge_node_source_field_preserved():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()
    mock_retriever.es_client.get_chunk_by_id = AsyncMock(return_value={
        "chunk_id": "p1",
        "content": "parent content",
        "chunk_level": 2,
        "source_id": "doc-a",
        "source_type": "document",
        "metadata": {"filename": "test.pdf"},
    })

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_threshold=2,
        merge_boost=1.05,
        rerank_top_n=5,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "parent_chunk_id": "p1", "rrf_score": 0.5}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "parent_chunk_id": "p1", "rrf_score": 0.4}),
    ]
    result = await agent.merge({"documents": docs, "query": "test", "rewritten_query": "test"})

    merged = result["documents"]
    assert len(merged) == 1
    assert merged[0].metadata.get("source") is not None
    assert merged[0].metadata["source"] != "未知来源"
```

- [ ] **Step 5: 运行测试**

```bash
uv run pytest backend/tests/unit/test_merge_node.py -v
uv run pytest backend/tests/unit/test_rag_agent.py -v
```

- [ ] **Step 6: 代码审查**

使用 sub-agent 审查 `agents.py` 和 `test_merge_node.py`。

- [ ] **Step 7: Commit**

```bash
git add backend/app/infra/langchain/agents.py backend/tests/unit/test_merge_node.py
git commit -m "feat(rag): add hierarchical chunk merge node to RAG agent"
```

---

### Task 11: 修改 create_rag_agent 工厂函数传入 merge 配置

**Files:**
- Modify: `backend/app/infra/langchain/__init__.py`

- [ ] **Step 1: 从 settings 读取 merge 配置并传入 RAGAgent**

修改 `create_rag_agent`：

```python
def create_rag_agent(
    llm: Any,
    retriever: Any,
    settings: Settings,
    rerank_provider: Any | None = None,
    query_rewriter: ConversationAwareQueryRewriter | None = None,
    prompt_gateway: PromptGateway | None = None,
) -> RAGAgent:
    return RAGAgent(
        llm=llm,
        retriever=retriever,
        rerank_provider=rerank_provider,
        query_rewriter=query_rewriter,
        prompt_gateway=prompt_gateway,
        score_threshold=0.7,
        max_attempts=3,
        rerank_top_n=settings.RERANK_TOP_N,
        merge_enabled=settings.RAG_MERGE_ENABLED,
        merge_threshold=settings.RAG_MERGE_THRESHOLD,
        merge_boost=settings.RAG_MERGE_BOOST,
    )
```

- [ ] **Step 2: 更新工厂函数测试**

检查 `backend/tests/unit/test_factory_functions.py` 是否需要更新，确保新参数被正确传递。

```bash
uv run pytest backend/tests/unit/test_factory_functions.py -v
```

- [ ] **Step 3: 代码审查**

- [ ] **Step 4: Commit**

```bash
git add backend/app/infra/langchain/__init__.py
git commit -m "feat(factory): wire merge config into RAGAgent via create_rag_agent"
```

---

### Task 12: 运行全量测试和 lint

- [ ] **Step 1: 运行单元测试和契约测试**

```bash
uv run pytest backend/tests/unit backend/tests/contract -v
```

Expected: 全部通过

- [ ] **Step 2: 运行 lint 和类型检查**

```bash
uv run ruff check backend/
uv run mypy backend/
```

Expected: 无错误

- [ ] **Step 3: 修复任何问题并 Commit**

```bash
git commit -m "test: verify hierarchical merge integration passes all checks"
```

---

### Task 14: Phase 2 端到端验证

**Goal:** 构建真实调用链路进行测试，验证多级分块动态合并功能。

- [ ] **Step 1: 清空 ES 索引并重新索引**

```bash
# 删除旧索引
curl -X DELETE "http://localhost:9200/museai_chunks_v1"

# 重启后端以重建索引
uv run uvicorn backend.app.main:app --reload --port 8000
```

- [ ] **Step 2: 上传一篇文档并验证 parent-child 关联**

```bash
# 上传文档
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@test_document.txt"

# 验证 ES 中的 parent_chunk_id
curl "http://localhost:9200/museai_chunks_v1/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{"query":{"exists":{"field":"parent_chunk_id"}},"size":5}'
```

- [ ] **Step 3: 通过 Chat API 验证 merge 功能**

```bash
# 发送一个覆盖多个 level-3 chunk 的查询
curl -N http://localhost:8000/api/v1/chat/sessions/<session_id>/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message":"请详细介绍这件文物的历史背景"}'
```

验证：
1. 返回的 sources 中无内容高度重叠的 chunk
2. 如果同一父节点的多个 level-3 chunk 被检索到，应被合并为 level-2 chunk
3. 合并后的 chunk 在 metadata 中包含 `is_merged: true` 和 `merged_from` 字段

- [ ] **Step 4: 验证降级处理**

临时将 `RAG_MERGE_ENABLED=false`，验证 merge 节点被跳过，系统仍正常工作。

- [ ] **Step 5: Commit**

```bash
git commit --allow-empty -m "test: Phase 2 e2e verification complete"
```

---

## 验证清单

### Phase 1（Source 去重 + Source 字段修复）
- [ ] 同一 `source_id` 的多个 chunk 在 RRF 后只保留一个（分数最高的）
- [ ] `UnifiedRetriever` 返回的 `top_k` 结果中，所有 `source_id` 唯一
- [ ] 前端不再显示"未知来源"，而是显示正确的 `source_id`
- [ ] 原有 RRF 测试全部通过（向后兼容）
- [ ] Ruff 和 Mypy 检查通过

### Phase 2（多级分块动态合并）
- [ ] 索引后的 chunk 具有正确的 `parent_chunk_id` 层级关系（level-3 → level-2 → level-1）
- [ ] `UnifiedIndexingService` 默认使用 3 级 chunk 配置
- [ ] RAG Agent 的 `merge` 节点能将同一父节点的多个 level-3 替换为 level-2
- [ ] 未达到阈值的父节点保留原 level-3 chunk
- [ ] ES 不可用时 merge 节点降级透传
- [ ] 合并后的评分包含 `merge_boost` 奖励
- [ ] 合并后的 `parent_doc` 包含 `source` 字段（不再显示"未知来源"）
- [ ] `UnifiedRetriever` 支持按 `chunk_level` 过滤检索（默认只检索 level-3）
- [ ] 所有单元测试、契约测试通过，lint 无错误
