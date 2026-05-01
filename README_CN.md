# MuseAI

博物馆智能导览系统 - 基于 RAG（检索增强生成）的智能博物馆内容交互平台。

[English](README.md)

## 功能特性

- **智能问答**：基于 RAG 的问答系统，从博物馆知识库中进行上下文检索
- **混合检索**：使用倒数排名融合（RRF）算法结合稠密向量检索和 BM25 关键词检索，支持来源去重
- **多轮对话**：支持查询转换策略（HyDE、后退提问、多查询）和动态召回过滤的有状态对话
- **文档摄入**：自动层级文档分块（父子关系）和嵌入，支持 Elasticsearch 索引
- **流式响应**：实时 SSE（服务器推送事件）流式输出，支持可选的 TTS 音频事件
- **用户认证**：基于 JWT 的身份认证，支持速率限制和令牌黑名单
- **导览系统**：博物馆导览会话管理，展厅追踪，事件记录和参观报告
- **策展人 AI 智能体**：基于 LangGraph 的 AI 导览规划、展品叙事生成和反思提示
- **语音合成**：基于句子级别的 TTS 流式输出，支持人设管理、Redis 缓存和多提供商（小米、Mock）
- **访客画像**：个性化访客画像，包含兴趣、知识水平和叙事偏好
- **管理后台**：完整的管理界面，涵盖展品、展厅、文档、提示词、TTS 人设和 LLM 调用追踪审计
- **设计系统**：基于 Element Plus 的博物馆主题设计令牌和组件
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
- **数据库迁移**：Alembic

### 前端
- **框架**：Vue 3 组合式 API
- **UI 库**：Element Plus（博物馆设计系统）
- **构建工具**：Vite
- **路由**：Vue Router
- **组合式函数**：可复用的认证、聊天、导览、TTS、展品等 hooks

### 基础设施
- **数据库**：PostgreSQL 16
- **搜索引擎**：Elasticsearch 8.x + IK 分词器
- **缓存**：Redis 7
- **LLM**：OpenAI 兼容提供商（GPT-4o-mini）
- **嵌入模型**：Ollama（nomic-embed-text）
- **重排序**：OpenAI 兼容或 SiliconFlow 重排序提供商
- **语音合成**：小米 TTS 提供商（Redis 缓存）

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

### 5. 初始化数据库

```bash
# 运行数据库迁移（创建表结构）
python scripts/init_db.py

# 创建管理员用户
python scripts/init_db.py --admin-email admin@museai.local --admin-password YourPassword123
```

> 详细说明请参见下方 [数据库初始化](#数据库初始化) 章节。

### 6. 运行后端服务

```bash
uv run uvicorn backend.app.main:app --reload
```

API 将在 `http://localhost:8000` 可用。

### 7. 安装前端依赖

```bash
cd frontend
npm install
```

### 8. 运行前端开发服务器

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
| `/api/v1/chat/guest/message` | POST | 访客消息（SSE 流式） |
| `/api/v1/exhibits` | GET | 浏览展品（公开） |
| `/api/v1/exhibits/{id}` | GET | 获取展品详情 |
| `/api/v1/profile` | GET/PUT | 获取/更新访客画像 |
| `/api/v1/tour/sessions` | POST | 创建导览会话 |
| `/api/v1/tour/sessions/{id}/chat/stream` | POST | 导览聊天流式输出（SSE） |
| `/api/v1/tour/sessions/{id}/report` | GET/POST | 生成/获取导览报告 |
| `/api/v1/curator/plan-tour` | POST | 规划博物馆导览（AI） |
| `/api/v1/curator/narrative` | POST | 生成展品叙事（AI） |
| `/api/v1/tts/synthesize` | POST | 文本转语音合成 |
| `/api/v1/admin/exhibits` | GET/POST | 管理展品 |
| `/api/v1/admin/halls` | GET/POST | 管理展厅 |
| `/api/v1/admin/prompts` | GET | 管理提示词模板 |
| `/api/v1/admin/documents` | GET/POST | 管理文档 |
| `/api/v1/admin/llm-traces` | GET | 查看 LLM 调用追踪 |
| `/api/v1/admin/tts/personas` | GET/PUT | 管理 TTS 人设 |
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
| `RERANK_PROVIDER` | 重排序提供商（openai, cohere, custom） | `openai` |
| `RERANK_MODEL` | 重排序模型标识 | `rerank-v1` |
| `RERANK_TOP_N` | 重排序结果数量 | `10` |
| `TTS_ENABLED` | 启用语音合成 | `false` |
| `TTS_PROVIDER` | TTS 提供商（xiaomi, mock） | `xiaomi` |
| `TTS_DEFAULT_VOICE` | 默认 TTS 语音/人设 | `冰糖` |

## 数据库初始化

项目使用 Alembic 管理数据库 schema 迁移。应用启动时也会自动创建缺失的表，但推荐使用迁移脚本来保证 schema 版本正确。

### 初始化脚本

`scripts/init_db.py` 是统一的服务初始化入口，覆盖 PostgreSQL 迁移、Elasticsearch 索引创建和服务连通性检查：

```bash
# 运行迁移 + ES 索引创建 + 服务连通性检查
python scripts/init_db.py

# 运行迁移 + 创建管理员
python scripts/init_db.py --admin-email admin@museai.local --admin-password YourPassword123

# 完整初始化：迁移 + ES 索引 + 管理员 + 开发测试数据
python scripts/init_db.py --admin-email admin@museai.local --admin-password YourPassword123 --seed-dev

# 仅运行 PostgreSQL 迁移
python scripts/init_db.py --schema-only

# 仅创建 ES 索引（幂等，已存在则跳过）
python scripts/init_db.py --init-es
```

### 生产环境部署流程

```bash
# 1. 启动基础设施
docker-compose up -d

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 JWT_SECRET、LLM_API_KEY 等

# 3. 安装依赖
uv sync

# 4. 初始化所有服务（数据库迁移 + ES 索引 + 管理员）
python scripts/init_db.py --init-es --admin-email admin@museum.cn --admin-password 'YourStr0ngPass!'

# 5. 启动服务
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 本地开发流程

```bash
# 1. 启动基础设施
docker-compose up -d

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，确保 DATABASE_URL 指向本地 PostgreSQL

# 3. 安装依赖
uv sync

# 4. 完整初始化：数据库迁移 + ES 索引 + 管理员 + 测试数据
python scripts/init_db.py --admin-email admin@museai.local --admin-password dev12345678 --seed-dev

# 5. 启动后端
uv run uvicorn backend.app.main:app --reload

# 6. 启动前端
cd frontend && npm install && npm run dev
```

### 手动操作 Alembic

如需手动管理迁移：

```bash
# 查看当前迁移状态
uv run alembic current

# 升级到最新版本
uv run alembic upgrade head

# 回滚一个版本
uv run alembic downgrade -1

# 查看迁移历史
uv run alembic history
```

### 种子数据脚本

项目提供以下独立的种子数据脚本（`scripts/` 目录）：

| 脚本 | 用途 | 依赖服务 |
|------|------|----------|
| `seed_dev_user.py` | 创建开发测试用户 | PostgreSQL |
| `bootstrap_admin.py` | 创建/提升管理员用户 | PostgreSQL |
| `init_exhibits.py` | 导入 70+ 展品数据（青铜器、陶瓷、书画等） | PostgreSQL, Elasticsearch, Ollama |
| `init_test_data.py` | 综合测试数据（用户、文档、聊天记录） | PostgreSQL, Elasticsearch, Ollama |
| `import_real_exhibits_via_api.py` | 通过 REST API 导入展品数据 | 完整后端服务 |
| `cleanup_llm_traces.py` | 清理过期 LLM 调用追踪记录 | PostgreSQL |

## 开发指南

### 一键本地验证

```bash
bash scripts/verify_local_quality.sh
```

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
│   │   │   ├── curator.py      # 策展人 AI 端点
│   │   │   ├── documents.py    # 文档管理
│   │   │   ├── exhibits.py     # 展品浏览
│   │   │   ├── health.py       # 健康检查
│   │   │   ├── profile.py      # 访客画像
│   │   │   ├── tour.py         # 导览会话管理
│   │   │   ├── tts.py          # 语音合成
│   │   │   └── admin/          # 管理路由
│   │   │       ├── documents.py
│   │   │       ├── exhibits.py
│   │   │       ├── halls.py
│   │   │       ├── llm_traces.py
│   │   │       ├── prompts.py
│   │   │       └── tts_persona.py
│   │   ├── application/         # 业务逻辑
│   │   │   ├── auth_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── curator_service.py
│   │   │   ├── document_service.py
│   │   │   ├── ingestion_service.py
│   │   │   ├── tour_*_service.py
│   │   │   ├── tts_service.py
│   │   │   ├── llm_trace/      # LLM 调用追踪
│   │   │   └── workflows/      # 多轮状态机
│   │   ├── domain/              # 领域实体
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   └── services/       # RRF 融合
│   │   ├── infra/              # 基础设施
│   │   │   ├── postgres/
│   │   │   ├── elasticsearch/
│   │   │   ├── redis/
│   │   │   ├── cache/          # 提示词缓存
│   │   │   ├── langchain/      # RAG Agent, 检索器, 策展人智能体
│   │   │   ├── providers/      # LLM, 嵌入, 重排序, TTS 提供商
│   │   │   └── security/
│   │   └── main.py
│   └── tests/
│       ├── unit/
│       ├── contract/
│       └── e2e/
├── frontend/
│   ├── src/
│   │   ├── api/               # API 客户端
│   │   ├── components/        # Vue 组件（聊天、导览、展品、管理等）
│   │   ├── composables/       # Vue 组合式函数（useAuth, useChat, useTour, useTTSPlayer 等）
│   │   ├── design-system/     # 博物馆设计令牌和组件
│   │   ├── views/             # 页面视图（首页、导览、策展人、展品、管理等）
│   │   ├── router/            # Vue Router 配置
│   │   ├── styles/            # 全局样式
│   │   └── main.js
│   └── package.json
├── scripts/                   # 工具脚本（种子数据、初始化、清理）
├── docker/
├── docs/
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## RAG 管道流程

1. **查询处理**：用户查询通过聊天端点进入
2. **检索**：并行执行稠密向量检索 + BM25 关键词检索
3. **融合**：倒数排名融合（RRF）合并结果，支持来源去重
4. **重排序**：重排序提供商对结果进行评分和过滤
5. **动态过滤**：绝对/相对差距策略过滤低质量结果
6. **分块合并**：检索到子分块时自动提升父分块（层级结构）
7. **评估**：检查检索质量分数阈值
8. **查询转换**（如需要）：HyDE、后退提问或多查询策略
9. **生成**：LLM 基于检索上下文生成答案
10. **流式输出**：通过 SSE 流式返回响应（支持可选的 TTS 音频事件）

## 许可证

MIT License
