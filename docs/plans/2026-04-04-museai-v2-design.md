# MuseAI V2 设计文档
**Status:** completed

> 创建日期: 2026-04-04
> 状态: 已确认

## 1. 项目概述

### 1.1 背景

MuseAI 面向博物馆导览场景，通过 RAG 和多轮对话将文档知识转化为可交互导览能力。

**核心目标：**
1. 可追溯的知识回答
2. 连贯的多轮对话体验
3. 可中断、低等待感的流式交互

### 1.2 设计约束

| 约束项 | 决策 |
|--------|------|
| 开发范围 | 完整6周计划（Phase 0-3） |
| 团队规模 | 1-2人小团队 |
| 开发流程 | TDD开发 |
| 代码来源 | 全新仓库，无历史代码 |
| 基础设施 | PG/ES/Redis已就绪 |
| 模型服务 | OpenAI兼容服务（gemini-2.5-flash）+ Ollama Embedding（qwen3-embedding:8b） |
| 开发策略 | 垂直切片优先 |

---

## 2. 架构设计

### 2.1 架构原则

1. 先做模块化单体（Modular Monolith），避免早期微服务复杂度
2. 严格分层：API 层不含检索细节，检索层不感知 HTTP
3. 检索与存储单一事实来源：Elasticsearch
4. 关键链路可观测：请求级 trace、阶段耗时、失败分类

### 2.2 分层架构

```
┌─────────────────────────────────────────┐
│           API Layer (FastAPI)           │
│  - 鉴权、请求校验、SSE流式输出             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       Application Layer (用例编排)        │
│  - Ingestion、Retrieval、Conversation     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│          Domain Layer (领域模型)          │
│  - 实体、值对象、领域服务、规则             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     Infrastructure Layer (基础设施)       │
│  - PostgreSQL/Redis/Elasticsearch/LLM    │
└─────────────────────────────────────────┘
```

### 2.3 目录结构

```text
museai-v2/
  backend/
    app/
      api/                  # FastAPI routers
      application/          # 用例编排（摄入、检索、会话）
      domain/               # 领域模型与规则
      infra/
        postgres/
        redis/
        elasticsearch/
        providers/
      workflows/            # RAG 多轮状态机
      observability/        # 日志、指标、trace
      config/
    tests/
      unit/
      integration/
      contract/
      e2e/
      fixtures/
  frontend/
    src/
  docker/
  docs/
```

### 2.4 模块边界

1. **API Service**: 认证、会话、聊天、文档管理入口
2. **Ingestion Service**: 文档分块、Embedding、索引写入
3. **Retrieval Service**: Dense + BM25 + RRF融合 + Rerank
4. **Conversation Service**: 多轮状态机、会话记忆、回答生成
5. **Metadata Service**: 用户、会话、任务、文档元数据管理

---

## 3. 数据存储设计

### 3.1 PostgreSQL 表结构

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    users     │────<│   chat_sessions  │────<│  chat_messages   │
└──────────────┘     └──────────────────┘     └──────────────────┘
                             │
┌──────────────┐     ┌───────▼──────────┐
│   documents  │────<│  ingestion_jobs  │
└──────────────┘     └──────────────────┘
```

**核心表定义：**

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| users | 用户账户 | id, email, password_hash, created_at |
| chat_sessions | 会话 | id, user_id, title, created_at |
| chat_messages | 消息 | id, session_id, role, content, trace_id |
| documents | 文档元信息 | id, user_id, filename, status, created_at |
| ingestion_jobs | 摄入任务 | id, document_id, status, chunk_count, error |

### 3.2 Elasticsearch 索引

索引名: `museai_chunks_v1`（通过 alias 管理读写）

```json
{
  "mappings": {
    "properties": {
      "chunk_id": {"type": "keyword"},
      "document_id": {"type": "keyword"},
      "parent_chunk_id": {"type": "keyword"},
      "root_chunk_id": {"type": "keyword"},
      "chunk_level": {"type": "integer"},
      "content": {"type": "text", "analyzer": "ik_max_word"},
      "content_vector": {
        "type": "dense_vector",
        "dims": 1536,
        "index": true,
        "similarity": "cosine"
      },
      "title": {"type": "keyword"},
      "source": {"type": "keyword"},
      "tags": {"type": "keyword"},
      "user_id": {"type": "keyword"},
      "created_at": {"type": "date"}
    }
  }
}
```

**检索策略：**
- L2作为主检索粒度（平衡语义完整性与召回精度）
- 命中后向上关联L1获取宏观上下文
- 向量维度从配置读取，启动时校验一致性

### 3.3 Redis 缓存策略

| 用途 | Key模式 | TTL |
|------|---------|-----|
| 会话上下文缓存 | `session:{id}:context` | 1小时 |
| Embedding缓存 | `embed:{hash}` | 24小时 |
| 检索结果缓存 | `retrieve:{query_hash}` | 10分钟 |
| 限流计数 | `rate:{user_id}` | 1分钟 |

---

## 4. 核心业务流程

### 4.1 文档摄入流程

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ 上传文档 │───>│ 创建任务 │───>│ 清洗分块 │───>│Embedding│───>│ 写入ES  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                    │                                            │
                    │              ┌─────────┐                   │
                    └──────────────│回写状态 │<──────────────────┘
                                   └─────────┘
```

**分块策略（L1/L2/L3）：**

| 层级 | 粒度 | 用途 | 配置参数 |
|------|------|------|----------|
| L1 | 文档章节/大段落 | 宏观上下文 | window=2000, overlap=200 |
| L2 | 段落/主题块 | **主检索粒度** | window=500, overlap=50 |
| L3 | 句子/细粒度 | 精确定位 | window=100, overlap=20 |

**状态机：**
```
pending → processing → completed
                  └──→ failed (可重试)
```

### 4.2 查询链路

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 接收Query │───>│Rewrite   │───>│ Dense召回│───>│  RRF融合  │
│          │    │(多轮时)  │    │ BM25召回 │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                     │
     ┌───────────────────────────────────────────────┘
     ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Rerank   │───>│ 层级组装 │───>│ LLM生成  │───>│ 返回答案  │
│ (可选)   │    │ L2+L1    │    │          │    │ +trace   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**RRF融合公式：**
```
score(d) = Σ 1/(k + rank_i(d))  # k=60 (默认)
```

### 4.3 多轮迭代机制

```
┌──────────────────────────────────────────────────────┐
│                  Multi-Turn State Machine            │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────┐   首轮查询   ┌─────────┐               │
│  │  START  │─────────────>│ RETRIEVE│               │
│  └─────────┘              └────┬────┘               │
│                                │                    │
│                     ┌──────────▼──────────┐         │
│                     │   评估召回质量       │         │
│                     │   score >= threshold?│        │
│                     └──────────┬──────────┘         │
│                           YES  │   NO               │
│                    ┌───────────┴───────────┐        │
│                    ▼                       ▼        │
│            ┌─────────────┐        ┌────────────┐   │
│            │  GENERATE   │        │  TRANSFORM │   │
│            └─────────────┘        │ step-back  │   │
│                    │              │ hyde       │   │
│                    │              │ multi-query│   │
│                    │              └─────┬──────┘   │
│                    │                    │          │
│                    │         attempts < max?       │
│                    │              YES │   NO      │
│                    │         ┌────────┴───────┐   │
│                    │         ▼                ▼   │
│                    │    ┌─────────┐    ┌─────────┐ │
│                    │    │ RETRIEVE│    │GENERATE │ │
│                    │    │ (重试)  │    │(低置信) │ │
│                    │    └─────────┘    └─────────┘ │
│                    │                           │   │
│                    └───────────────────────────┘   │
│                                ▼                    │
│                         ┌─────────┐                │
│                         │   END   │                │
│                         └─────────┘                │
└──────────────────────────────────────────────────────┘
```

**Transform策略：**
- **Step-back**: 抽象化问题，获取更广泛上下文
- **HyDE**: 生成假设性答案，用答案检索
- **Multi-query**: 生成多个相关查询，合并结果

### 4.4 流式输出与中断

**SSE事件类型：**
```javascript
// 思考阶段
data: {"type":"thinking","stage":"retrieve","content":"正在检索..."}

// 生成阶段
data: {"type":"chunk","stage":"generate","content":"这件文物"}

// 完成阶段
data: {"type":"done","stage":"generate","trace_id":"xxx","chunks":[...]}

// 错误
data: {"type":"error","code":"RETRIEVE_FAILED","message":"..."}
```

**中断处理：**
```
用户点击停止 → 前端关闭EventSource → 后端收到断开信号
→ 取消LLM生成任务 → 回滚未完成事务 → 记录中断状态
```

---

## 5. API接口设计

### 5.1 接口清单

```
/api/v1
├── /auth
│   ├── POST /register          # 用户注册
│   └── POST /login             # 用户登录
│
├── /chat
│   ├── POST /sessions          # 创建会话
│   ├── GET  /sessions          # 会话列表
│   ├── GET  /sessions/{id}     # 会话详情
│   ├── DELETE /sessions/{id}   # 删除会话
│   ├── GET  /sessions/{id}/messages  # 历史消息
│   ├── POST /ask               # 单轮问答（非流式）
│   └── POST /ask/stream        # 单轮问答（流式）
│
├── /multi-turn-chat
│   ├── POST /ask               # 多轮问答（非流式）
│   └── POST /ask/stream        # 多轮问答（流式）
│
├── /documents
│   ├── GET  /                  # 文档列表
│   ├── POST /upload            # 上传文档
│   ├── GET  /{id}              # 文档详情
│   ├── DELETE /{id}            # 删除文档
│   └── GET  /{id}/status       # 摄入状态
│
└── /health
    ├── GET /health             # 健康检查
    └── GET /ready              # 就绪检查
```

### 5.2 核心接口契约

**POST /api/v1/chat/ask/stream**
```json
// Request
{
  "session_id": "uuid",
  "message": "这件青铜器是做什么用的？"
}

// Response (SSE)
data: {"type":"thinking","stage":"rewrite","content":"正在理解问题"}
data: {"type":"thinking","stage":"retrieve","content":"检索到3个相关段落"}
data: {"type":"chunk","stage":"generate","content":"这件青铜器"}
data: {"type":"chunk","stage":"generate","content":"是祭祀用品"}
data: {"type":"done","trace_id":"xxx","sources":[...]}
```

**POST /api/v1/documents/upload**
```json
// Request (multipart/form-data)
file: document.pdf

// Response
{
  "id": "uuid",
  "filename": "document.pdf",
  "status": "pending",
  "created_at": "2026-04-04T10:00:00Z"
}
```

### 5.3 Trace Schema (v2)

每次请求返回完整trace，便于调试：

```json
{
  "trace_id": "uuid",
  "trace_version": "v2",
  "stages": [
    {
      "name": "rewrite",
      "duration_ms": 120,
      "input": "原始query",
      "output": "改写后query"
    },
    {
      "name": "retrieve",
      "duration_ms": 350,
      "dense_count": 5,
      "bm25_count": 8,
      "fused_count": 6,
      "reranked": false
    },
    {
      "name": "generate",
      "duration_ms": 1200,
      "model": "gemini-2.5-flash",
      "prompt_tokens": 500,
      "completion_tokens": 150
    }
  ],
  "total_duration_ms": 1670,
  "attempts": 1,
  "confidence": 0.85
}
```

### 5.4 错误码规范

| 错误码 | HTTP状态 | 说明 |
|--------|----------|------|
| AUTH_FAILED | 401 | 认证失败 |
| SESSION_NOT_FOUND | 404 | 会话不存在 |
| DOCUMENT_NOT_FOUND | 404 | 文档不存在 |
| INGESTION_FAILED | 500 | 文档摄入失败 |
| RETRIEVE_FAILED | 500 | 检索失败 |
| LLM_ERROR | 503 | LLM服务异常 |
| RATE_LIMITED | 429 | 请求过于频繁 |

---

## 6. 测试策略

### 6.1 测试金字塔

```
            ┌─────────┐
            │   E2E   │  ← 端到端：完整业务链路
            │  (5%)   │
        ┌───┴─────────┴───┐
        │  Integration    │  ← 集成测试：外部依赖交互
        │     (25%)       │
    ┌───┴─────────────────┴───┐
    │       Contract          │  ← 契约测试：API/Trace Schema
    │         (20%)           │
┌───┴─────────────────────────┴───┐
│            Unit                 │  ← 单元测试：纯逻辑
│            (50%)                │
└─────────────────────────────────┘
```

### 6.2 各层测试范围

**Unit Tests (50%)**
```
backend/tests/unit/
├── test_chunking.py         # 分块逻辑（L1/L2/L3边界）
├── test_rag_fusion.py       # RRF融合算法
├── test_rerank.py           # 重排逻辑
├── test_state_machine.py    # 多轮状态机转换
├── test_query_transform.py  # 查询变换
└── test_utils.py            # 工具函数
```

**Contract Tests (20%)**
```
backend/tests/contract/
├── test_api_schema.py       # OpenAPI契约验证
├── test_sse_events.py       # SSE事件格式
├── test_trace_schema.py     # Trace v2结构
└── test_error_responses.py  # 错误响应格式
```

**Integration Tests (25%)**
```
backend/tests/integration/
├── test_elasticsearch.py    # ES检索、索引操作
├── test_postgres.py         # PG事务、会话持久化
├── test_redis.py            # 缓存读写、限流
├── test_llm_provider.py     # LLM/Embedding调用
├── test_ingestion_flow.py   # 完整摄入流程
└── test_sse_interrupt.py    # 流式中断处理
```

**E2E Tests (5%)**
```
backend/tests/e2e/
└── test_full_journey.py     # 完整用户旅程
```

### 6.3 TDD开发流程

```
┌──────────────────────────────────────────────────────┐
│                    TDD Red-Green Cycle               │
├──────────────────────────────────────────────────────┤
│                                                      │
│  1. Red:   写失败测试                                 │
│     - 定义接口契约（Contract Test）                   │
│     - 定义业务逻辑（Unit Test）                       │
│                                                      │
│  2. Green: 写最小实现使测试通过                       │
│     - 实现核心逻辑                                    │
│     - 不追求完美，先通过测试                          │
│                                                      │
│  3. Refactor: 重构优化                               │
│     - 消除重复代码                                    │
│     - 优化结构                                        │
│     - 测试保证行为不变                                │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 6.4 关键测试用例

**必测场景：**

| 模块 | 测试用例 | 验证点 |
|------|----------|--------|
| 分块 | L2层级边界正确性 | 字符数、overlap计算 |
| RRF融合 | 多路召回合并 | 分数计算、排序正确 |
| 状态机 | 多轮迭代逻辑 | attempt计数、transform触发 |
| ES检索 | 向量+BM25混合 | 召回数量、分数范围 |
| SSE中断 | 用户中断响应 | 1秒内停止、状态回滚 |
| Trace | 完整性验证 | 阶段覆盖、耗时记录 |

### 6.5 测试数据管理

```
backend/tests/fixtures/
├── sample_documents/    # 测试文档
│   ├── simple.pdf
│   └── complex.pdf
├── mock_embeddings.json # Mock Embedding数据
└── test_queries.json    # 测试查询集
```

**测试隔离策略：**
- Unit Tests: 纯函数，无外部依赖
- Contract Tests: Mock外部服务
- Integration Tests: 使用Docker Testcontainers（ES/PG/Redis）
- E2E Tests: 完整环境，测试后清理数据

### 6.6 CI门禁

```yaml
# PR触发
**Status:** completed
- ruff lint          # 代码风格
- mypy               # 类型检查
- pytest unit        # 单元测试
- pytest contract    # 契约测试

# Merge到main触发
- pytest integration # 集成测试
- pytest e2e         # 端到端测试
- pytest --cov       # 覆盖率报告（目标80%）
```

---

## 7. 非功能需求

### 7.1 性能目标

| 指标 | 目标值 |
|------|--------|
| /chat/ask p95延迟 | < 5秒（无外部rerank） |
| /chat/ask/stream 首token | < 1.5秒 |
| 中断请求响应时间 | < 1秒终止上游生成 |
| 检索链路错误率 | < 1%（日维度） |
| 摄入任务幂等性 | 支持重试，不产生重复chunk |

### 7.2 可观测性

- **日志**: 结构化JSON日志，包含trace_id
- **指标**: Prometheus格式，记录延迟、召回数、错误率
- **追踪**: 每请求trace_id贯穿全链路

---

## 8. 实施计划框架

| Phase | 周次 | 目标 | 交付物 |
|-------|------|------|--------|
| Phase 0 | 第1周 | 脚手架与基线 | 项目结构、CI、配置模型、健康检查 |
| Phase 1 | 第2-3周 | 摄入与检索内核 | 文档上传、分块、ES入库、混合检索、RRF融合 |
| Phase 2 | 第4-5周 | 多轮与流式 | 会话管理、多轮状态机、SSE流式、中断处理 |
| Phase 3 | 第6周 | 联调与切换 | 前后端联调、E2E测试、性能压测、灰度上线 |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Embedding维度不一致 | 启动失败 | 配置校验 + 启动时检查 |
| LLM服务不稳定 | 生成失败 | 重试机制 + 降级策略 |
| ES索引mapping变更 | 检索失败 | Alias管理 + 版本化索引 |
| 多轮状态丢失 | 体验中断 | Redis持久化 + PG备份 |

---

## 10. 参考文档

- [背景.md](../reference/背景.md)
- [prd.md](../reference/prd.md)
