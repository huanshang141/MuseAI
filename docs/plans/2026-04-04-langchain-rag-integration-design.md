# LangChain RAG Integration Design

**Date:** 2026-04-04  
**Status:** Approved

---

## Overview

将现有 MuseAI 项目集成 LangChain 生态，实现完整的 RAG 流程，修复断裂的 Ingestion Pipeline 和 Chat 数据链路。

---

## Goals

1. 集成 LangChain 1.x 生态系统
2. 修复文档摄取流程（上传 → 分块 → 向量化 → 存储）
3. 实现 RAG 检索（Dense + BM25 + RRF 融合）
4. 使用 LangGraph 构建 Multi-turn RAG Agent
5. 保持现有自定义组件（多层级分块、自定义 ES 索引映射）

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                      │
├─────────────────────────────────────────────────────────────────┤
│  /upload  →  IngestionService  →  TextChunker (多层级)          │
│                    ↓                                             │
│              CustomOllamaEmbeddings                              │
│                    ↓                                             │
│              ElasticsearchClient (自定义索引)                    │
├─────────────────────────────────────────────────────────────────┤
│  /ask/stream  →  RAGAgent (LangGraph)                           │
│                       ↓                                          │
│                 RRFRetriever (BaseRetriever)                     │
│                    ↓         ↓                                   │
│              search_dense  search_bm25                           │
│                    ↓         ↓                                   │
│                    rrf_fusion                                    │
│                       ↓                                          │
│               ChatOpenAI (生成回答)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. LangChain Infrastructure

**CustomOllamaEmbeddings**
- 包装现有 `OllamaEmbeddingProvider`
- 实现 `langchain_core.embeddings.Embeddings` 接口
- 支持异步嵌入生成

**依赖版本：**
```
langchain>=1.2.14,<2.0.0
langchain-core>=1.2.22,<2.0.0
langchain-community>=0.3.0,<0.4.0
langchain-openai>=1.1.12,<2.0.0
langchain-elasticsearch>=0.2.0,<0.3.0
langgraph>=1.1.3,<2.0.0
```

### 2. RRF Retriever

**RRFRetriever**
- 继承 `langchain_core.retrievers.BaseRetriever`
- 内部调用 `ElasticsearchClient` 执行 BM25 + Dense 查询
- 应用层 RRF 融合算法
- 返回 LangChain `Document` 对象

### 3. Ingestion Pipeline

**IngestionService**
- 保留多层级 `TextChunker`
- 使用 `CustomOllamaEmbeddings` 生成向量
- 使用 `ElasticsearchClient.index_chunk()` 写入（保留自定义索引映射）
- 更新 `IngestionJob` 状态

### 4. RAG Agent (LangGraph)

**RAGAgent**
- 状态图节点：retrieve → evaluate → transform/generate
- 集成 `RRFRetriever` 作为检索工具
- Multi-turn 逻辑：检索质量评估 + 查询变换重试
- 使用 `ChatOpenAI` 生成回答

---

## File Structure

```
backend/app/
├── infra/
│   ├── langchain/              # 新增
│   │   ├── __init__.py         # 工厂函数
│   │   ├── embeddings.py       # CustomOllamaEmbeddings
│   │   ├── retrievers.py       # RRFRetriever
│   │   └── agents.py           # RAGAgent (LangGraph)
│   ├── elasticsearch/          # 保留
│   │   └── client.py           # 自定义索引创建 + 多层级写入
│   └── providers/
│       ├── llm.py              # 保留（fallback）
│       └── embedding.py        # 保留（被 LangChain 封装）
├── application/
│   ├── ingestion_service.py    # 新增
│   ├── chat_service.py         # 重构：使用 RAGAgent
│   ├── chunking.py             # 保留
│   └── retrieval.py            # 保留（RRF 算法）
└── main.py                     # 修改：依赖注入
```

---

## Data Flow

### Ingestion Flow

```
POST /upload
    ↓
IngestionService.ingest()
    ↓
TextChunker.chunk() [level 1, 2, 3]
    ↓
CustomOllamaEmbeddings.aembed_documents()
    ↓
ElasticsearchClient.index_chunk() [自定义索引映射]
    ↓
IngestionJob.status = "completed"
```

### Query Flow

```
POST /ask/stream
    ↓
RAGAgent.run()
    ↓
[retrieve] RRFRetriever._aget_relevant_documents()
    ↓         ├── search_dense(query_vector)
    ↓         ├── search_bm25(query)
    ↓         └── rrf_fusion()
    ↓
[evaluate] 检索质量评估
    ↓
[transform/generate] ChatOpenAI 流式生成
    ↓
保存 ChatMessage
    ↓
SSE 流式返回
```

---

## Migration Strategy

| 阶段 | 内容 | 工作量 |
|-----|------|-------|
| Phase 1 | LangChain 基础设施 + CustomOllamaEmbeddings | ~2h |
| Phase 2 | RRFRetriever 实现 | ~3h |
| Phase 3 | Ingestion Pipeline 修复 | ~3h |
| Phase 4 | RAG Agent (LangGraph) + chat_service 重构 | ~4h |

**总计:** ~12h

---

## Testing Strategy

1. **Unit Tests**: 每个新组件独立测试
2. **Integration Tests**: 
   - 上传文档 → 验证 ES 中有 chunks
   - 发送问题 → 验证 RAG 检索正常
3. **E2E Tests**: 
   - 上传文档 → 聊天提问 → 验证回答包含文档内容

---

## Risks

1. **LangChain 版本兼容性**: 使用版本约束锁定大版本
2. **多层级分块复杂性**: 保留现有实现，仅集成接口
3. **ES 索引迁移**: 使用自定义客户端，无需迁移现有数据

---

## Success Criteria

- [ ] 文档上传后 `chunk_count > 0`
- [ ] 聊天能检索到上传文档的相关内容
- [ ] Multi-turn Agent 能根据检索质量决定是否重试
- [ ] 所有现有测试通过
- [ ] 新增组件测试覆盖率 > 80%
