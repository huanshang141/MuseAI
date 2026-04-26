# 多级分块动态合并设计（方案 A：检索后合并）

**Goal:** 在 RAG 检索阶段实现自底向上的动态合并策略：只检索 level-3 chunk，当同一 level-2 父节点的孩子命中数达到阈值时，自动用 level-2 chunk 替换这些孩子，从而提升召回质量、消除重复内容。

**Architecture:** 在现有 LangGraph RAG Agent 的 `retrieve` → `rerank` 之间插入一个 `merge` 节点。该节点分析检索结果的 `parent_chunk_id` 分布，对高密度命中区域进行向上合并。索引阶段保持全部 level 的 chunk 不变，仅通过 ES 的 `parent_chunk_id` 字段建立树状关联。

**Tech Stack:** Python, FastAPI, Elasticsearch, LangChain/LangGraph

---

## 1. 当前问题分析

### 1.1 多级分块现状

[`chunking.py`](file:///home/singer/MuseAI/backend/app/application/chunking.py) 中 `TextChunker` 使用滑动窗口切分：

```python
ChunkConfig(level=1, window_size=2000, overlap=200)
ChunkConfig(level=2, window_size=500, overlap=50)
ChunkConfig(level=3, window_size=100, overlap=10)
```

- 同一文档被切成 3 个 level 的 chunk，每个 level 独立索引到 ES。
- `Chunk` 已包含 `parent_chunk_id` 字段，但当前**未建立真正的父子关系**（所有 chunk 的 `parent_chunk_id` 均为 `None`）。
- [`UnifiedIndexingService.index_source()`](file:///home/singer/MuseAI/backend/app/application/unified_indexing_service.py) 遍历 `chunk_configs` 时，没有将 level-3 的 `parent_chunk_id` 指向 level-2 的对应 chunk。

### 1.2 检索重复根因

[`UnifiedRetriever._aget_relevant_documents()`](file:///home/singer/MuseAI/backend/app/infra/langchain/retrievers.py) 调用 `rrf_fusion()` 后直接取 `top_k`，同一文档的 level-2/3 chunk 可能同时出现，内容高度重叠。

### 1.3 设计约束

- **索引不动**：不删除或修改已索引的 level-1/2 chunk，保持向后兼容。
- **检索优先**：RAG 只主动检索 level-3（最细粒度），合并时按需拉取 level-2。
- **阈值可配**：合并阈值、最大合并数等参数通过 `Settings` 注入。

---

## 2. 核心设计

### 2.1 索引阶段：建立 parent-child 关联

修改 [`UnifiedIndexingService.index_source()`](file:///home/singer/MuseAI/backend/app/application/unified_indexing_service.py)，在多层切分时记录父子关系：

```
Level 1 (2000字) ──► Level 2 (500字) ──► Level 3 (100字)
     chunk_1a           chunk_2a,b,c,d      chunk_3a,b,c,...
                            ▲                   ▲
                            └──── parent ───────┘
```

具体做法：
1. 先对文档做 level-1 切分。
2. 对每个 level-1 chunk 做 level-2 切分，记录 `parent_chunk_id = level_1_chunk.id`。
3. 对每个 level-2 chunk 做 level-3 切分，记录 `parent_chunk_id = level_2_chunk.id`。
4. 所有 chunk 仍全部索引到 ES，但 `parent_chunk_id` 字段不再是空值。

> 注：`IngestionService`（旧版）同样需要做此修改，或迁移到 `UnifiedIndexingService`。

### 2.2 检索阶段：自底向上动态合并

在 RAG Agent 的状态机中，于 `retrieve` 和 `rerank` 之间插入 `merge` 节点：

```
rewrite ──► retrieve(level-3 only) ──► merge ──► rerank ──► evaluate ──► generate
```

#### 2.2.1 merge 节点算法

输入：`list[Document]`（level-3 chunk 检索结果）
输出：`list[Document]`（合并后的结果，可能包含 level-2 chunk）

```python
async def merge(self, state: RAGState) -> dict[str, Any]:
    documents = state["documents"]
    query = state.get("rewritten_query") or state["query"]

    # Step 1: 按 parent_chunk_id 分组统计
    parent_hits: dict[str, list[Document]] = defaultdict(list)
    standalone_docs: list[Document] = []

    for doc in documents:
        parent_id = doc.metadata.get("parent_chunk_id")
        if parent_id:
            parent_hits[parent_id].append(doc)
        else:
            standalone_docs.append(doc)

    # Step 2: 判断是否触发合并
    merged_docs: list[Document] = []
    threshold = self.merge_threshold  # e.g., 2

    for parent_id, children in parent_hits.items():
        if len(children) >= threshold:
            # 拉取 level-2 chunk 替换孩子
            level2_doc = await self._fetch_parent_chunk(parent_id, query)
            if level2_doc:
                # 评分 = 孩子最高 RRF 分 + 合并奖励
                best_child_score = max(
                    c.metadata.get("rrf_score", 0) for c in children
                )
                level2_doc.metadata["rrf_score"] = best_child_score * 1.05
                level2_doc.metadata["merged_from"] = [c.metadata["chunk_id"] for c in children]
                merged_docs.append(level2_doc)
            else:
                # fallback: 保留孩子中分数最高的一个
                best = max(children, key=lambda d: d.metadata.get("rrf_score", 0))
                merged_docs.append(best)
        else:
            # 未达阈值，保留所有孩子
            merged_docs.extend(children)

    # Step 3: 合并 standalone 和 merged，按分数排序
    final_docs = standalone_docs + merged_docs
    final_docs.sort(key=lambda d: d.metadata.get("rrf_score", 0), reverse=True)

    return {"documents": final_docs[: self.top_k]}
```

#### 2.2.2 拉取父 chunk 的实现

`_fetch_parent_chunk()` 通过 ES 的 `term` 查询按 `chunk_id`（即父节点 ID）精确获取：

```python
async def _fetch_parent_chunk(self, parent_chunk_id: str, query: str) -> Document | None:
    """从 ES 拉取 level-2 parent chunk，并验证其相关性。"""
    result = await self.es_client.search_by_chunk_id(parent_chunk_id)
    if not result:
        return None

    doc_data = result[0]
    # 可选：用轻量级语义过滤验证 parent chunk 是否与查询相关
    # 如果 parent 与查询完全不相关，返回 None 以保留孩子
    return Document(
        page_content=doc_data["content"],
        metadata={
            "chunk_id": doc_data["chunk_id"],
            "source_id": doc_data.get("source_id"),
            "chunk_level": doc_data.get("chunk_level"),
            "rrf_score": doc_data.get("rrf_score", 0),
            "is_merged": True,
        },
    )
```

> ES 需要新增 `search_by_chunk_id()` 方法，或复用现有 `client.get(index, id)` API。

### 2.3 评分调整策略

合并后的 level-2 chunk 评分需要反映"合并价值"：

```
merged_score = max(child_rrf_scores) * merge_boost
```

- `merge_boost` 默认 1.05（轻微奖励），可配置。
- 如果 level-2 的 BM25/向量分数已单独计算，也可直接采用其原始分数。
- 被合并的 level-3 chunk 的 `chunk_id` 记录到 `merged_from` metadata，便于溯源和调试。

### 2.4 RAG Agent 状态机修改

[`agents.py`](file:///home/singer/MuseAI/backend/app/infra/langchain/agents.py) 的 `_build_graph()` 需要新增 `merge` 节点：

```python
def _build_graph(self) -> Any:
    workflow = StateGraph(RAGState)

    workflow.add_node("rewrite", self.rewrite_query)
    workflow.add_node("retrieve", self.retrieve)
    workflow.add_node("merge", self.merge)           # NEW
    workflow.add_node("rerank", self.rerank)
    workflow.add_node("evaluate", self.evaluate)
    workflow.add_node("transform", self.transform)
    workflow.add_node("generate", self.generate)

    workflow.set_entry_point("rewrite")
    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("retrieve", "merge")           # NEW
    workflow.add_edge("merge", "rerank")             # NEW
    workflow.add_edge("rerank", "evaluate")
    # ... 其余不变
```

`RAGState` 不需要新增字段，`documents` 在 `merge` 节点中被替换即可。

---

## 3. 数据流与边界

### 3.1 输入输出

| 阶段 | 输入 | 输出 | 说明 |
|------|------|------|------|
| retrieve | query | `list[Document]` (level-3) | 只检索 `chunk_level=3` 的 chunk |
| merge | `list[Document]` (level-3) | `list[Document]` (mixed) | 部分被替换为 level-2 |
| rerank | `list[Document]` (mixed) | `list[Document]` (reranked) | 对合并后的结果重排序 |

### 3.2 降级处理

- 如果 `merge` 节点拉取父 chunk 失败（ES 不可用），直接透传原 level-3 结果。
- 如果父 chunk 与查询语义不相关（可通过轻量级 BM25 过滤），保留原 level-3 结果。

### 3.3 与现有去重策略的关系

本设计与前文 `rrf_fusion` 的 `deduplicate_by="source_id"` **互补**：
- `deduplicate_by` 解决"同一文档的不同 chunk 同时出现"。
- `merge` 解决"同一父节点的多个孩子同时出现，且内容重叠"。

两者可以共存：先 `deduplicate_by` 去重，再 `merge` 向上合并。

---

## 4. 配置参数

新增到 [`Settings`](file:///home/singer/MuseAI/backend/app/config/settings.py)：

```python
# RAG 动态合并配置
RAG_MERGE_ENABLED: bool = True          # 是否启用动态合并
RAG_MERGE_THRESHOLD: int = 2            # 同一父节点下命中几个孩子才触发合并
RAG_MERGE_BOOST: float = 1.05           # 合并后评分奖励系数
RAG_RETRIEVE_LEVEL: int = 3             # 主动检索的 chunk level（默认 3）
```

---

## 5. 测试策略

### 5.1 单元测试

- `test_merge_node.py`：模拟 4 个 level-3 chunk，其中 3 个共享同一 parent，验证合并后输出 1 个 level-2 + 1 个独立 level-3。
- `test_merge_threshold.py`：验证阈值边界（如 threshold=2，只有 1 个孩子时不合并）。
- `test_fetch_parent_fallback.py`：模拟 ES 返回空，验证 fallback 到保留最佳孩子。

### 5.2 集成测试

- 端到端测试：上传一篇文档，查询一个覆盖多个 level-3 chunk 的问题，验证返回结果中无重复且包含 level-2 内容。

### 5.3 性能测试

- 测量 `merge` 节点引入的额外 ES 查询延迟（预期 < 50ms，因为按 `chunk_id` 精确查询）。

---

## 6. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/application/chunking.py` | 修改 | `TextChunker.chunk()` 支持传入 `parent_chunk_id` |
| `backend/app/application/unified_indexing_service.py` | 修改 | 多层切分时建立 parent-child 关联 |
| `backend/app/application/ingestion_service.py` | 修改 | 同上（或标记为废弃，迁移到 UnifiedIndexingService） |
| `backend/app/infra/elasticsearch/client.py` | 修改 | 新增 `get_chunk_by_id()` 方法 |
| `backend/app/infra/langchain/agents.py` | 修改 | 新增 `merge` 节点，修改 `_build_graph()` |
| `backend/app/config/settings.py` | 修改 | 新增合并相关配置项 |
| `backend/tests/unit/test_merge_node.py` | 创建 | merge 节点单元测试 |
| `backend/tests/unit/test_chunking_parent.py` | 创建 | parent-child 关联测试 |

---

## 7. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| parent-child 关联建立错误导致合并到无关 chunk | 在 `chunking.py` 中通过 `start_char`/`end_char` 精确计算父子关系，增加断言验证 |
| merge 引入额外 ES 查询导致延迟增加 | 使用 `asyncio.gather` 并行拉取多个 parent chunk；增加缓存 |
| 合并后 level-2 chunk 过长超出 LLM context | 在 `generate` 节点增加总长度检查，超长时截断或回退到 level-3 |
| 阈值设置不当导致过度合并或从不合并 | 默认保守阈值（2），通过线上 A/B 测试调优 |

---

## 8. 后续扩展

- **自适应阈值**：根据查询长度、文档类型动态调整 `merge_threshold`。
- **多级合并**：如果 level-2 的命中也密集，可继续向上合并到 level-1（需要更复杂的树遍历）。
- **合并热度统计**：记录哪些 parent chunk 经常被合并，用于指导索引策略优化。
