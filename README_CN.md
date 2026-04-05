# MuseAI

博物馆智能导览系统 - 基于 RAG（检索增强生成）的智能博物馆内容交互平台。

[English](README.md)

## 功能特性

- **智能问答**：基于 RAG 的问答系统，从博物馆知识库中进行上下文检索
- **混合检索**：使用倒数排名融合（RRF）算法结合稠密向量检索和 BM25 关键词检索
- **多轮对话**：支持查询转换策略（HyDE、后退提问、多查询）的有状态对话
- **文档摄入**：自动文档分块和嵌入，支持层级结构
- **流式响应**：实时 SSE（服务器推送事件）流式输出，提升用户体验
- **用户认证**：基于 JWT 的身份认证，支持速率限制和令牌黑名单
- **健康监控**：内置健康检查端点，提供服务可观测性

## 系统架构

MuseAI 采用严格的分层架构：

```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (Vue 3)                        │
├─────────────────────────────────────────────────────────┤
│                    API 层 (FastAPI)                      │
├─────────────────────────────────────────────────────────┤
│                    应用层                                │
│         (认证、聊天、文档、摄入服务)                      │
├─────────────────────────────────────────────────────────┤
│                    领域层                                │
│              (实体、值对象)                              │
├─────────────────────────────────────────────────────────┤
│                   基础设施层                             │
│      (PostgreSQL, Elasticsearch, Redis, LLM)           │
└─────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端
- **框架**：FastAPI（异步支持）
- **ORM**：SQLAlchemy 2.0（异步）
- **验证**：Pydantic v2
- **AI/ML**：LangChain、LangGraph、OpenAI 兼容 LLM

### 前端
- **框架**：Vue 3 组合式 API
- **UI 库**：Element Plus
- **构建工具**：Vite

### 基础设施
- **数据库**：PostgreSQL 16
- **搜索引擎**：Elasticsearch 8.x + IK 分词器
- **缓存**：Redis 7
- **LLM**：OpenAI 兼容提供商（GPT-4o-mini）
- **嵌入模型**：Ollama（nomic-embed-text）

## 环境要求

- Python 3.11+
- Node.js 18+
- Docker 和 Docker Compose
- uv（Python 包管理器）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/museai.git
cd museai
```

### 2. 启动基础设施服务

```bash
docker-compose up -d
```

这将启动 PostgreSQL、Elasticsearch 和 Redis。

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件进行配置。必要设置：

```env
# LLM 配置（生产环境必需）
LLM_API_KEY=your-openai-api-key

# JWT 密钥（生产环境必须 ≥32 字符）
JWT_SECRET=your-secure-jwt-secret-key-here
```

### 4. 安装后端依赖

```bash
uv sync
```

### 5. 运行后端服务

```bash
uv run uvicorn backend.app.main:app --reload
```

API 将在 `http://localhost:8000` 可用。

### 6. 安装前端依赖

```bash
cd frontend
npm install
```

### 7. 运行前端开发服务器

```bash
npm run dev
```

前端将在 `http://localhost:5173` 可用。

## API 文档

后端运行后，可访问交互式 API 文档：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 主要端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/auth/register` | POST | 注册新用户 |
| `/api/v1/auth/login` | POST | 登录获取 JWT 令牌 |
| `/api/v1/auth/logout` | POST | 登出（黑名单令牌） |
| `/api/v1/documents/upload` | POST | 上传文档进行摄入 |
| `/api/v1/documents` | GET | 获取用户文档列表 |
| `/api/v1/chat/sessions` | GET/POST | 管理聊天会话 |
| `/api/v1/chat/ask` | POST | 提问（非流式） |
| `/api/v1/chat/ask/stream` | POST | 提问（SSE 流式） |
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/ready` | GET | 就绪检查 |

## 配置说明

环境变量（参考 `.env.example`）：

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `APP_ENV` | 环境（development/production） | `development` |
| `DATABASE_URL` | PostgreSQL 连接字符串 | 必需 |
| `REDIS_URL` | Redis 连接字符串 | 必需 |
| `ELASTICSEARCH_URL` | Elasticsearch 端点 | 必需 |
| `JWT_SECRET` | JWT 签名密钥（生产环境 ≥32 字符） | 必需 |
| `JWT_ALGORITHM` | JWT 算法 | `HS256` |
| `JWT_EXPIRE_MINUTES` | 令牌过期时间 | `1440` |
| `LLM_PROVIDER` | LLM 提供商 | `openai` |
| `LLM_BASE_URL` | LLM API 基础 URL | `https://api.openai.com/v1` |
| `LLM_API_KEY` | LLM API 密钥 | 必需 |
| `LLM_MODEL` | 模型名称 | `gpt-4o-mini` |
| `EMBEDDING_PROVIDER` | 嵌入模型提供商 | `ollama` |
| `EMBEDDING_OLLAMA_BASE_URL` | Ollama 基础 URL | `http://localhost:11434` |
| `EMBEDDING_OLLAMA_MODEL` | 嵌入模型 | `nomic-embed-text` |
| `ELASTICSEARCH_INDEX` | ES 索引名称 | `museai_chunks_v1` |
| `EMBEDDING_DIMS` | 嵌入维度 | `1536` |

## 开发指南

### 运行测试

```bash
# 单元测试和契约测试
uv run pytest backend/tests/unit backend/tests/contract -v

# 单个测试文件
uv run pytest backend/tests/unit/test_domain_entities.py -v

# E2E 测试（需要运行基础设施）
uv run pytest backend/tests/e2e -v
```

### 代码质量

```bash
# 代码检查
uv run ruff check backend/

# 类型检查
uv run mypy backend/
```

### 前端开发

```bash
cd frontend

# 开发服务器
npm run dev

# 生产构建
npm run build
```

## 项目结构

```
museai/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI 路由
│   │   │   ├── auth.py         # 认证端点
│   │   │   ├── chat.py         # 聊天端点
│   │   │   ├── documents.py    # 文档管理
│   │   │   └── health.py       # 健康检查
│   │   ├── application/         # 业务逻辑
│   │   │   ├── auth_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── document_service.py
│   │   │   ├── ingestion_service.py
│   │   │   └── retrieval.py    # RRF 融合
│   │   ├── domain/             # 领域实体
│   │   │   ├── entities.py
│   │   │   └── value_objects.py
│   │   ├── infra/              # 基础设施
│   │   │   ├── postgres/
│   │   │   ├── elasticsearch/
│   │   │   ├── redis/
│   │   │   ├── langchain/      # RAG Agent, 检索器
│   │   │   ├── providers/      # LLM, 嵌入提供商
│   │   │   └── security/
│   │   ├── workflows/          # 多轮状态机
│   │   └── main.py
│   └── tests/
│       ├── unit/
│       ├── contract/
│       └── e2e/
├── frontend/
│   ├── src/
│   │   ├── api/               # API 客户端
│   │   ├── components/        # Vue 组件
│   │   ├── composables/       # Vue 组合式函数
│   │   └── main.js
│   └── package.json
├── docker/
├── docs/
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## RAG 管道流程

1. **查询处理**：用户查询通过聊天端点进入
2. **检索**：并行执行稠密向量检索 + BM25 关键词检索
3. **融合**：倒数排名融合（RRF）合并结果
4. **评估**：检查检索质量分数阈值
5. **查询转换**（如需要）：HyDE、后退提问或多查询策略
6. **生成**：LLM 基于检索上下文生成答案
7. **流式输出**：通过 SSE 流式返回响应

## 许可证

MIT License
