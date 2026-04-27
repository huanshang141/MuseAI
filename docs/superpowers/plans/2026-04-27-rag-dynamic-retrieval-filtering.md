# RAG 动态召回数量过滤 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于重排序分数分布的动态文档过滤，解决特定展品查询召回过多无关文档、宽泛主题查询召回不足的问题。

**Architecture:** 在现有 LangGraph RAG 状态机中增加 `filter` 节点，位于 `rerank` 之后、`evaluate` 之前。该节点根据绝对阈值、相对 gap 阈值和 min/max 约束动态决定最终保留的文档数量。同时提升上游 `top_k` 和 `rerank_top_n` 以提供更多候选。

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Pydantic Settings, pytest

---

## 背景与问题分析

当前系统流水线：

```
检索(top_k=5) → 合并(≤5) → 重排序(rerank_top_n=3) → 评估(平均分) → 生成
```

日志揭示的问题：

| 查询类型 | rerank_score 分布 | 问题 |
|---------|------------------|------|
| **连通灶（特定展品）** | 0.41, 0.001, 0.00006 | 只有1个真正相关，但系统硬塞了3个 |
| **半坡陶器（宽泛主题）** | 0.97, 0.97, 0.88 | 3个都高度相关，但可能还有更多优质文档被截断 |

根因：`rerank_top_n=3` 是硬截断，reranker API 只返回前3个，导致：
- 宽泛问题的第4、5个高分文档被丢弃
- 特定问题的低分文档被强制使用，污染上下文

---

## 文件结构变更

| 文件 | 操作 | 职责 |
|-----|------|------|
| `backend/app/application/document_filter.py` | **新建** | 动态文档过滤策略实现（绝对阈值、相对gap、min/max约束） |
| `backend/app/config/settings.py` | 修改 | 新增 `RETRIEVAL_TOP_K`、`RERANK_TOP_N`、`RERANK_ABSOLUTE_THRESHOLD`、`RERANK_RELATIVE_GAP`、`RERANK_MIN_DOCS`、`RERANK_MAX_DOCS` 配置项 |
| `backend/app/infra/langchain/agents.py` | 修改 | RAGAgent 新增 `filter_documents` 节点，插入到 `rerank` → `evaluate` 之间；修改 `evaluate` 使用过滤后文档；新增配置参数 |
| `backend/app/infra/langchain/retrievers.py` | 修改 | `UnifiedRetriever` 的 `top_k` 默认值从 5 改为 15 |
| `backend/app/infra/langchain/__init__.py` | 修改 | `create_rag_agent` 和 `create_retriever` 工厂函数传递新配置参数 |
| `backend/app/application/chat_stream_service.py` | 修改 | `ask_question_stream_with_rag` 使用过滤后的文档生成 sources |
| `backend/tests/unit/test_document_filter.py` | **新建** | 动态过滤核心逻辑单元测试 |
| `backend/tests/unit/test_rag_agent.py` | 修改（如存在）或新建 | RAGAgent filter 节点集成测试 |

---

## Chunk 1: 核心过滤策略实现

### Task 1: 动态文档过滤模块

**Files:**
- Create: `backend/app/application/document_filter.py`
- Test: `backend/tests/unit/test_document_filter.py`

- [ ] **Step 1: 编写过滤策略的单元测试**

```python
# backend/tests/unit/test_document_filter.py
import pytest
from langchain_core.documents import Document

from app.application.document_filter import DynamicDocumentFilter, FilterConfig


class TestFilterConfig:
    def test_default_config(self):
        config = FilterConfig()
        assert config.absolute_threshold == 0.25
        assert config.relative_gap == 0.25
        assert config.min_docs == 1
        assert config.max_docs == 8

    def test_config_validation(self):
        with pytest.raises(ValueError, match="min_docs must be >= 1"):
            FilterConfig(min_docs=0)
        with pytest.raises(ValueError, match="max_docs must be >= min_docs"):
            FilterConfig(min_docs=5, max_docs=3)
        with pytest.raises(ValueError, match="absolute_threshold must be between 0 and 1"):
            FilterConfig(absolute_threshold=1.5)
        with pytest.raises(ValueError, match="relative_gap must be between 0 and 1"):
            FilterConfig(relative_gap=-0.1)


class TestDynamicDocumentFilter:
    def _make_docs(self, scores: list[float]) -> list[Document]:
        return [
            Document(page_content=f"doc{i}", metadata={"rerank_score": s})
            for i, s in enumerate(scores)
        ]

    def test_specific_exhibit_query(self):
        """连通灶场景: [0.41, 0.001, 0.00006] -> 应只保留1个"""
        docs = self._make_docs([0.41, 0.001, 0.00006])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 1
        assert result[0].metadata["rerank_score"] == pytest.approx(0.41)

    def test_broad_topic_query(self):
        """半坡陶器场景: [0.97, 0.97, 0.88] -> 应保留3个"""
        docs = self._make_docs([0.97, 0.97, 0.88])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 3

    def test_medium_scores_with_tail(self):
        """[0.8, 0.75, 0.72, 0.3, 0.1] -> 应保留前3个"""
        docs = self._make_docs([0.8, 0.75, 0.72, 0.3, 0.1])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 3

    def test_all_high_scores(self):
        """[0.95, 0.94, 0.93, 0.92, 0.91] -> 在max范围内全部保留"""
        docs = self._make_docs([0.95, 0.94, 0.93, 0.92, 0.91])
        filter_obj = DynamicDocumentFilter(FilterConfig(max_docs=5))
        result = filter_obj.filter(docs)
        assert len(result) == 5

    def test_all_low_scores(self):
        """[0.1, 0.05, 0.02] -> 绝对阈值过滤后保留min_docs个"""
        docs = self._make_docs([0.1, 0.05, 0.02])
        filter_obj = DynamicDocumentFilter()
        result = filter_obj.filter(docs)
        assert len(result) == 1  # min_docs=1, 保留最高分

    def test_empty_docs(self):
        result = DynamicDocumentFilter().filter([])
        assert result == []

    def test_single_doc(self):
        docs = self._make_docs([0.5])
        result = DynamicDocumentFilter().filter(docs)
        assert len(result) == 1

    def test_no_rerank_scores_fallback(self):
        """没有 rerank_score 时应使用 rrf_score"""
        docs = [
            Document(page_content="a", metadata={"rrf_score": 0.8}),
            Document(page_content="b", metadata={"rrf_score": 0.3}),
        ]
        result = DynamicDocumentFilter().filter(docs)
        assert len(result) == 1
        assert result[0].metadata["rrf_score"] == pytest.approx(0.8)

    def test_mixed_scores_priority(self):
        """同时有 rerank_score 和 rrf_score 时优先 rerank_score"""
        docs = [
            Document(page_content="a", metadata={"rerank_score": 0.9, "rrf_score": 0.1}),
            Document(page_content="b", metadata={"rerank_score": 0.2, "rrf_score": 0.8}),
        ]
        result = DynamicDocumentFilter().filter(docs)
        assert len(result) == 1
        assert result[0].page_content == "a"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest backend/tests/unit/test_document_filter.py -v`
Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现过滤模块**

```python
# backend/app/application/document_filter.py
"""动态文档过滤策略。

根据重排序分数分布自适应决定最终保留的文档数量，
解决固定 top_n 导致的召回不足或召回过多的问题。
"""

from dataclasses import dataclass

from langchain_core.documents import Document


@dataclass(frozen=True)
class FilterConfig:
    """文档过滤配置。

    Attributes:
        absolute_threshold: 绝对分数阈值，低于此值的文档将被过滤（默认0.25）
        relative_gap: 相对gap阈值，与最高分差距超过此比例的文档将被过滤（默认0.25）
        min_docs: 最少保留文档数，即使质量不高也至少保留这么多（默认1）
        max_docs: 最多保留文档数，防止高质量文档过多撑爆上下文（默认8）
    """

    absolute_threshold: float = 0.25
    relative_gap: float = 0.25
    min_docs: int = 1
    max_docs: int = 8

    def __post_init__(self):
        if self.min_docs < 1:
            raise ValueError(f"min_docs must be >= 1, got {self.min_docs}")
        if self.max_docs < self.min_docs:
            raise ValueError(
                f"max_docs must be >= min_docs, got max_docs={self.max_docs}, min_docs={self.min_docs}"
            )
        if not 0.0 <= self.absolute_threshold <= 1.0:
            raise ValueError(
                f"absolute_threshold must be between 0 and 1, got {self.absolute_threshold}"
            )
        if not 0.0 <= self.relative_gap <= 1.0:
            raise ValueError(
                f"relative_gap must be between 0 and 1, got {self.relative_gap}"
            )


class DynamicDocumentFilter:
    """动态文档过滤器。

    采用三层过滤策略：
    1. 绝对阈值过滤：剔除明显无关的文档（score < absolute_threshold）
    2. 相对gap过滤：保留与最高分差距在 relative_gap 内的文档
    3. min/max 约束：确保结果在 [min_docs, max_docs] 范围内

    分数优先级：rerank_score > rrf_score > 默认值0.0
    """

    def __init__(self, config: FilterConfig | None = None):
        self.config = config or FilterConfig()

    def _get_score(self, doc: Document) -> float:
        """获取文档的优先级分数。"""
        return doc.metadata.get("rerank_score", doc.metadata.get("rrf_score", 0.0))

    def filter(self, documents: list[Document]) -> list[Document]:
        """对文档列表进行动态过滤。

        Args:
            documents: 输入文档列表，假设已按分数降序排列或需要重新排序

        Returns:
            过滤后的文档列表
        """
        if not documents:
            return []

        # 按分数降序排列
        sorted_docs = sorted(documents, key=self._get_score, reverse=True)
        scores = [self._get_score(d) for d in sorted_docs]
        max_score = scores[0]

        # 策略1: 绝对阈值过滤
        # 但保留至少 min_docs 个，即使它们低于阈值
        absolute_cutoff_index = len(sorted_docs)
        for i, score in enumerate(scores):
            if score < self.config.absolute_threshold and i >= self.config.min_docs:
                absolute_cutoff_index = i
                break

        candidates = sorted_docs[:absolute_cutoff_index]
        candidate_scores = scores[:absolute_cutoff_index]

        if not candidates:
            # 保底：返回最高分文档
            return sorted_docs[: self.config.min_docs]

        # 策略2: 相对gap过滤
        # 保留与最高分差距在 relative_gap 内的文档
        # 例如 max_score=0.8, relative_gap=0.25 -> cutoff = 0.8 * (1-0.25) = 0.6
        relative_cutoff = max_score * (1.0 - self.config.relative_gap)
        gap_cutoff_index = len(candidates)
        for i, score in enumerate(candidate_scores):
            if score < relative_cutoff and i >= self.config.min_docs:
                gap_cutoff_index = i
                break

        result = candidates[:gap_cutoff_index]

        # 策略3: min/max 约束
        if len(result) < self.config.min_docs:
            result = sorted_docs[: self.config.min_docs]
        if len(result) > self.config.max_docs:
            result = result[: self.config.max_docs]

        return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest backend/tests/unit/test_document_filter.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/document_filter.py backend/tests/unit/test_document_filter.py
git commit -m "feat(rag): add dynamic document filter with absolute/relative gap strategies"
```

---

## Chunk 2: 配置层扩展

### Task 2: 扩展 Settings 配置

**Files:**
- Modify: `backend/app/config/settings.py:56-65`

- [ ] **Step 1: 在 settings.py 中添加新的配置项**

```python
# backend/app/config/settings.py
# 在 RERANK_TOP_N 下方添加：

    # 动态文档过滤配置
    RETRIEVAL_TOP_K: int = 15  # ES 粗召回数量，从 5 提升到 15
    RERANK_TOP_N: int = 10  # Reranker 返回数量，从 5 提升到 10
    RERANK_ABSOLUTE_THRESHOLD: float = 0.25  # 绝对分数阈值
    RERANK_RELATIVE_GAP: float = 0.25  # 相对gap阈值
    RERANK_MIN_DOCS: int = 1  # 最少保留文档数
    RERANK_MAX_DOCS: int = 8  # 最多保留文档数
```

- [ ] **Step 2: 添加配置验证器（可选但推荐）**

在 Settings 类中添加 field_validator：

```python
    @field_validator("RETRIEVAL_TOP_K", "RERANK_TOP_N", "RERANK_MIN_DOCS", "RERANK_MAX_DOCS")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"must be positive, got {v}")
        return v

    @field_validator("RERANK_ABSOLUTE_THRESHOLD", "RERANK_RELATIVE_GAP")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"must be between 0 and 1, got {v}")
        return v
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config/settings.py
git commit -m "feat(config): add dynamic retrieval filtering settings"
```

---

## Chunk 3: RAG Agent 状态机改造

### Task 3: RAGAgent 新增 filter 节点

**Files:**
- Modify: `backend/app/infra/langchain/agents.py`
- Test: `backend/tests/unit/test_rag_agent.py` (新建或修改)

- [ ] **Step 1: 导入过滤模块并扩展 RAGAgent 初始化参数**

在 `agents.py` 顶部添加导入：

```python
from app.application.document_filter import DynamicDocumentFilter, FilterConfig
```

修改 `RAGAgent.__init__` 签名和属性：

```python
    def __init__(
        self,
        llm: BaseChatModel,
        retriever: BaseRetriever,
        rerank_provider: BaseRerankProvider | None = None,
        query_rewriter: ConversationAwareQueryRewriter | None = None,
        prompt_gateway: PromptGateway | None = None,
        llm_provider: Any | None = None,
        score_threshold: float = SCORE_THRESHOLD,
        max_attempts: int = MAX_ATTEMPTS,
        rerank_top_n: int = 5,
        merge_enabled: bool = True,
        merge_max_level: int = 1,
        merge_max_parents: int = 3,
        filter_config: FilterConfig | None = None,  # 新增
    ):
        # ... 现有赋值 ...
        self.document_filter = DynamicDocumentFilter(filter_config)  # 新增
```

- [ ] **Step 2: 在 _build_graph 中插入 filter 节点**

修改 `_build_graph`：

```python
    def _build_graph(self) -> Any:
        """构建LangGraph状态机。"""
        workflow = StateGraph(RAGState)

        # 添加节点
        workflow.add_node("rewrite", self.rewrite_query)
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("merge", self.merge_chunks)
        workflow.add_node("rerank", self.rerank)
        workflow.add_node("filter", self.filter_documents)  # 新增
        workflow.add_node("evaluate", self.evaluate)
        workflow.add_node("transform", self.transform)
        workflow.add_node("generate", self.generate)

        workflow.set_entry_point("rewrite")

        workflow.add_edge("rewrite", "retrieve")
        workflow.add_edge("retrieve", "merge")
        workflow.add_edge("merge", "rerank")
        workflow.add_edge("rerank", "filter")  # 新增
        workflow.add_edge("filter", "evaluate")  # 修改

        # 条件边：评估后决定是转换还是生成
        workflow.add_conditional_edges(
            "evaluate",
            self._should_transform,
            {
                "transform": "transform",
                "generate": "generate",
            },
        )
        # ... 其余不变 ...
```

- [ ] **Step 3: 实现 filter_documents 节点**

在 `rerank` 方法之后、`evaluate` 方法之前插入：

```python
    def filter_documents(self, state: RAGState) -> dict[str, Any]:
        """对重排序后的文档进行动态过滤。"""
        docs = state.get("reranked_documents") or state.get("merged_documents") or state["documents"]

        if not docs:
            logger.debug("filter_documents: no documents to filter")
            return {"filtered_documents": []}

        filtered = self.document_filter.filter(docs)
        logger.info(
            f"filter_documents: {len(docs)} docs -> {len(filtered)} docs "
            f"(config: min={self.document_filter.config.min_docs}, "
            f"max={self.document_filter.config.max_docs}, "
            f"absolute_threshold={self.document_filter.config.absolute_threshold}, "
            f"relative_gap={self.document_filter.config.relative_gap})"
        )
        return {"filtered_documents": filtered}
```

- [ ] **Step 4: 修改 evaluate 节点使用 filtered_documents**

修改 `evaluate` 方法：

```python
    def evaluate(self, state: RAGState) -> dict[str, Any]:
        """评估检索质量。"""
        # 优先使用过滤后的文档
        docs = (
            state.get("filtered_documents")
            or state.get("reranked_documents")
            or state.get("merged_documents")
            or state["documents"]
        )

        if not docs:
            return {"retrieval_score": 0.0}

        scores = []
        for doc in docs:
            score = doc.metadata.get("rerank_score", doc.metadata.get("rrf_score", 0.5))
            scores.append(score)

        # 改进：使用最高分 + 有效文档比例，而非简单平均
        max_score = max(scores) if scores else 0.0
        valid_count = sum(1 for s in scores if s >= 0.3)  # 0.3 作为有效文档的粗略阈值

        # 综合评分：最高分占主导，有效文档数提供加成
        retrieval_score = max_score * (1.0 + 0.05 * min(valid_count, 5))
        retrieval_score = min(retrieval_score, 1.0)  # 封顶 1.0

        logger.debug(
            f"Evaluation score: {retrieval_score:.3f} (max={max_score:.3f}, "
            f"valid_docs={valid_count}, total={len(docs)})"
        )
        return {"retrieval_score": retrieval_score}
```

- [ ] **Step 5: 修改 generate 节点使用 filtered_documents**

修改 `generate` 方法的第一行：

```python
    async def generate(self, state: RAGState) -> dict[str, Any]:
        """生成答案。"""
        docs = (
            state.get("filtered_documents")
            or state.get("reranked_documents")
            or state.get("merged_documents")
            or state["documents"]
        )
        # ... 其余不变 ...
```

- [ ] **Step 6: 更新 RAGState 类型定义（如需要）**

如果 TypedDict 需要显式声明所有键，添加 `filtered_documents`：

```python
class RAGState(TypedDict):
    """RAG状态机的状态定义。"""

    query: str
    rewritten_query: str
    documents: list[Document]
    merged_documents: list[Document]
    reranked_documents: list[Document]
    filtered_documents: list[Document]  # 新增
    retrieval_score: float
    attempts: int
    transformations: list[str]
    answer: str
    conversation_history: list[dict[str, str]]
    system_prompt: str
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/infra/langchain/agents.py
git commit -m "feat(rag): add filter node to RAG agent graph between rerank and evaluate"
```

---

## Chunk 4: 工厂函数和检索器调整

### Task 4: 调整工厂函数和检索器参数

**Files:**
- Modify: `backend/app/infra/langchain/retrievers.py:70`
- Modify: `backend/app/infra/langchain/__init__.py`
- Modify: `backend/app/main.py` (如需要)

- [ ] **Step 1: 修改 UnifiedRetriever 默认 top_k**

```python
# backend/app/infra/langchain/retrievers.py:70
class UnifiedRetriever(BaseRetriever):
    # ...
    top_k: int = 15  # 从 5 改为 15
```

- [ ] **Step 2: 修改 create_retriever 传递 top_k**

```python
# backend/app/infra/langchain/__init__.py
def create_retriever(
    es_client: Any,
    embeddings: CustomOllamaEmbeddings,
    settings: Settings,
) -> UnifiedRetriever:
    return UnifiedRetriever(
        es_client=es_client,
        embeddings=embeddings,
        top_k=settings.RETRIEVAL_TOP_K,  # 从硬编码 5 改为配置驱动
        rrf_k=60,
        chunk_levels=[2, 3],
    )
```

- [ ] **Step 3: 修改 create_rag_agent 传递 filter_config**

```python
# backend/app/infra/langchain/__init__.py
def create_rag_agent(
    llm: Any,
    retriever: Any,
    settings: Settings,
    rerank_provider: Any | None = None,
    query_rewriter: ConversationAwareQueryRewriter | None = None,
    prompt_gateway: PromptGateway | None = None,
    llm_provider: Any | None = None,
) -> RAGAgent:
    from app.application.document_filter import FilterConfig

    filter_config = FilterConfig(
        absolute_threshold=settings.RERANK_ABSOLUTE_THRESHOLD,
        relative_gap=settings.RERANK_RELATIVE_GAP,
        min_docs=settings.RERANK_MIN_DOCS,
        max_docs=settings.RERANK_MAX_DOCS,
    )

    return RAGAgent(
        llm=llm,
        retriever=retriever,
        rerank_provider=rerank_provider,
        query_rewriter=query_rewriter,
        prompt_gateway=prompt_gateway,
        llm_provider=llm_provider,
        score_threshold=0.7,
        max_attempts=3,
        rerank_top_n=settings.RERANK_TOP_N,  # 从 settings.RERANK_TOP_N 驱动
        merge_enabled=settings.CHUNK_MERGE_ENABLED,
        merge_max_level=settings.CHUNK_MERGE_MAX_LEVEL,
        merge_max_parents=settings.CHUNK_MERGE_MAX_PARENTS,
        filter_config=filter_config,  # 新增
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/infra/langchain/retrievers.py backend/app/infra/langchain/__init__.py
git commit -m "feat(rag): wire up dynamic filter config and increase default top_k to 15"
```

---

## Chunk 5: Chat Stream Service 适配

### Task 5: 使用过滤后的文档生成 sources

**Files:**
- Modify: `backend/app/application/chat_stream_service.py:176-253`

- [ ] **Step 1: 修改 ask_question_stream_with_rag 中的文档使用逻辑**

当前代码在 `result` 返回后，多处使用 `reranked_documents` 或 `documents`。需要统一优先使用 `filtered_documents`。

找到这两处并修改：

**第1处（约 line 176）：生成 prompt 的 context**

```python
# 修改前
docs = result.get("reranked_documents") or result.get("documents", [])
context = "\n\n".join(doc.page_content for doc in docs)

# 修改后
docs = (
    result.get("filtered_documents")
    or result.get("reranked_documents")
    or result.get("documents", [])
)
context = "\n\n".join(doc.page_content for doc in docs)
```

**第2处（约 line 215）：生成 sources 用于前端展示**

```python
# 修改前
docs = result.get("reranked_documents") or result.get("documents", [])
_log.debug(f"Using docs count: {len(docs)}")

# 修改后
docs = (
    result.get("filtered_documents")
    or result.get("reranked_documents")
    or result.get("documents", [])
)
_log.debug(f"Using docs count: {len(docs)} (filtered from {len(result.get('reranked_documents', []))})")
```

- [ ] **Step 2: 在 SSE 事件中增加过滤信息（可选但推荐）**

在 `rag_step` 事件中增加 filter 步骤的反馈：

```python
# 在 rerank 完成后、evaluate 开始前添加
yield sse_chat_event("rag_step", step="filter", status="running", message="正在筛选高质量参考文档...")

filtered_count = len(result.get("filtered_documents", []))
original_count = len(result.get("reranked_documents", []))
f_msg = f'从 {original_count} 篇文档中筛选出 {filtered_count} 篇高质量参考'
yield sse_chat_event("rag_step", step="filter", status="completed", message=f_msg)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/application/chat_stream_service.py
git commit -m "feat(chat): use filtered_documents for context and sources display"
```

---

## Chunk 6: 集成测试与验证

### Task 6: RAG Agent 集成测试

**Files:**
- Create/Modify: `backend/tests/unit/test_rag_agent.py`

- [ ] **Step 1: 编写 RAGAgent filter 节点集成测试**

```python
# backend/tests/unit/test_rag_agent.py
import pytest
from langchain_core.documents import Document
from unittest.mock import AsyncMock, MagicMock

from app.infra.langchain.agents import RAGAgent, RAGState
from app.application.document_filter import FilterConfig


class TestRAGAgentFilterNode:
    @pytest.fixture
    def mock_rag_agent(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        agent = RAGAgent(
            llm=mock_llm,
            retriever=mock_retriever,
            rerank_provider=None,
            filter_config=FilterConfig(
                absolute_threshold=0.25,
                relative_gap=0.25,
                min_docs=1,
                max_docs=8,
            ),
        )
        return agent

    def test_filter_node_with_specific_exhibit(self, mock_rag_agent):
        """模拟连通灶场景"""
        state: RAGState = {
            "query": "介绍一下连通灶",
            "rewritten_query": "介绍一下连通灶",
            "documents": [],
            "merged_documents": [],
            "reranked_documents": [
                Document(page_content="连通灶是大型公共灶...", metadata={"rerank_score": 0.41}),
                Document(page_content="青铜馆A厅介绍...", metadata={"rerank_score": 0.001}),
                Document(page_content="半坡人生活方式...", metadata={"rerank_score": 0.00006}),
            ],
            "filtered_documents": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": [],
            "system_prompt": "",
        }
        result = mock_rag_agent.filter_documents(state)
        filtered = result["filtered_documents"]
        assert len(filtered) == 1
        assert filtered[0].metadata["rerank_score"] == pytest.approx(0.41)

    def test_filter_node_with_broad_topic(self, mock_rag_agent):
        """模拟半坡陶器场景"""
        state: RAGState = {
            "query": "介绍一下半坡的陶器",
            "rewritten_query": "介绍一下半坡的陶器",
            "documents": [],
            "merged_documents": [],
            "reranked_documents": [
                Document(page_content="陶器的造型与纹饰...", metadata={"rerank_score": 0.97}),
                Document(page_content="雕塑艺术...", metadata={"rerank_score": 0.97}),
                Document(page_content="彩陶图案集萃...", metadata={"rerank_score": 0.88}),
            ],
            "filtered_documents": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": [],
            "system_prompt": "",
        }
        result = mock_rag_agent.filter_documents(state)
        filtered = result["filtered_documents"]
        assert len(filtered) == 3

    def test_evaluate_uses_filtered_documents(self, mock_rag_agent):
        """评估节点应优先使用 filtered_documents"""
        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "documents": [],
            "merged_documents": [],
            "reranked_documents": [
                Document(page_content="a", metadata={"rerank_score": 0.9}),
                Document(page_content="b", metadata={"rerank_score": 0.1}),
            ],
            "filtered_documents": [
                Document(page_content="a", metadata={"rerank_score": 0.9}),
            ],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": [],
            "system_prompt": "",
        }
        result = mock_rag_agent.evaluate(state)
        # 只有1个文档且分数0.9，max_score=0.9, valid_count=1
        # retrieval_score = 0.9 * (1 + 0.05*1) = 0.945
        assert result["retrieval_score"] == pytest.approx(0.945)
```

- [ ] **Step 2: 运行测试**

Run: `uv run pytest backend/tests/unit/test_rag_agent.py -v`
Expected: PASS

- [ ] **Step 3: 运行全部单元测试确保无回归**

Run: `uv run pytest backend/tests/unit -v`
Expected: 全部通过（或已知失败不变）

- [ ] **Step 4: Lint 和 Type Check**

Run: `uv run ruff check backend/`
Expected: 无新增错误

Run: `uv run mypy backend/`
Expected: 无新增类型错误

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_rag_agent.py
git commit -m "test(rag): add integration tests for filter node and evaluate scoring"
```

---

## 配置参考

部署时可通过环境变量调整：

```bash
# 粗召回数量（ES 返回给 reranker 的候选数）
RETRIEVAL_TOP_K=15

# Reranker 返回数量
RERANK_TOP_N=10

# 动态过滤参数
RERANK_ABSOLUTE_THRESHOLD=0.25
RERANK_RELATIVE_GAP=0.25
RERANK_MIN_DOCS=1
RERANK_MAX_DOCS=8
```

调参指南：
- `absolute_threshold` 降低 → 保留更多文档（适合宽泛问题多的场景）
- `relative_gap` 降低 → 对分数差距更敏感，更容易截断尾部
- `max_docs` 根据 LLM context window 调整（当前 8 个文档约 4k-8k tokens）

---

## 回滚计划

若线上出现问题，可通过环境变量快速回滚到旧行为：

```bash
# 回滚到固定 top_n=3 的行为
RETRIEVAL_TOP_K=5
RERANK_TOP_N=3
RERANK_ABSOLUTE_THRESHOLD=0.0
RERANK_RELATIVE_GAP=1.0
RERANK_MIN_DOCS=3
RERANK_MAX_DOCS=3
```

这会让过滤策略保留固定3个文档，等效于旧行为。
