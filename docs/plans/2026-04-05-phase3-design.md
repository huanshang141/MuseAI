# MuseAI Phase 3 设计文档

> 创建日期: 2026-04-05
> 状态: 已确认

## 1. 概述

Phase 3 是 MuseAI V2 的最后一个阶段，包含以下任务：

| Task | 名称 | 主要交付物 |
|------|------|------------|
| Task 16 | Query Transform | Step-back / HyDE / Multi-query 策略 |
| Task 17 | Redis Cache Layer | 会话缓存 / Embedding缓存 / 检索缓存 / 限流 |
| Task 18 | Authentication API | 注册 / 登录 / JWT / 登出 |
| Task 19 | Integration Tests | PG / ES / Redis / LLM 集成测试 |
| Task 20 | E2E Tests | 完整用户旅程测试 |

### 1.1 架构原则

采用**严格分层架构**，遵循项目现有规范：

```
API Layer → Application Layer → Domain Layer → Infrastructure Layer
```

---

## 2. Task 16: Query Transform

### 2.1 策略设计

| 策略 | 用途 | 触发条件 | 实现方式 |
|------|------|----------|----------|
| **Step-back** | 问题太具体时抽象化 | 查询包含具体细节（日期、地点、数字） | LLM生成更抽象的问题 |
| **HyDE** | 语义匹配困难时 | 检索分数低于阈值但查询长度适中 | LLM生成假设答案，用答案检索 |
| **Multi-query** | 歧义或宽泛问题 | 查询词模糊或多义词 | LLM生成3个相关查询 |

### 2.2 智能选择算法

```python
class QueryTransformStrategy(Enum):
    NONE = "none"
    STEP_BACK = "step_back"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"

def select_strategy(query: str, retrieval_score: float, attempt: int) -> QueryTransformStrategy:
    if retrieval_score >= 0.7:
        return QueryTransformStrategy.NONE
    
    if attempt == 1:
        if has_specific_details(query):
            return QueryTransformStrategy.STEP_BACK
        elif is_ambiguous(query):
            return QueryTransformStrategy.MULTI_QUERY
        else:
            return QueryTransformStrategy.HYDE
    
    if attempt == 2:
        return QueryTransformStrategy.HYDE
    
    return QueryTransformStrategy.MULTI_QUERY
```

### 2.3 文件结构

```
backend/app/workflows/
├── query_transform.py      # 新建：策略实现
│   ├── QueryTransformStrategy (enum)
│   ├── QueryTransformer (class)
│   │   ├── transform_step_back()
│   │   ├── transform_hyde()
│   │   └── transform_multi_query()
│   └── select_strategy()
├── multi_turn.py           # 修改：集成 transform 逻辑
└── __init__.py
```

### 2.4 与状态机集成

修改 `multi_turn.py` 的 `transform_query()` 方法：

```python
def transform_query(self, query: str, retrieval_score: float) -> list[str]:
    strategy = select_strategy(query, retrieval_score, self.attempts)
    
    if strategy == QueryTransformStrategy.NONE:
        return [query]
    
    transformer = QueryTransformer(self.llm_provider)
    
    if strategy == QueryTransformStrategy.STEP_BACK:
        return [transformer.transform_step_back(query)]
    elif strategy == QueryTransformStrategy.HYDE:
        return [transformer.transform_hyde(query)]
    else:
        return transformer.transform_multi_query(query)
```

### 2.5 测试策略

**Unit Tests:**
- 每种策略的正确生成
- 选择策略的条件判断
- 边界情况处理

**Contract Tests:**
- 策略输出格式验证

---

## 3. Task 17: Redis Cache Layer

### 3.1 缓存策略设计

| 缓存类型 | Key 模式 | TTL | 用途 |
|----------|----------|-----|------|
| **会话上下文** | `session:{id}:context` | 1小时 | 存储最近 N 条消息 |
| **Embedding** | `embed:{hash}` | 24小时 | 避免重复计算 |
| **检索结果** | `retrieve:{query_hash}` | 10分钟 | 相同查询复用 |
| **限流计数** | `rate:{user_id}` | 1分钟 | API 限流 |

### 3.2 文件结构

```
backend/app/infra/redis/
├── __init__.py
├── cache.py              # 新建：缓存客户端
│   ├── RedisCache (class)
│   │   ├── get_session_context()
│   │   ├── set_session_context()
│   │   ├── get_embedding()
│   │   ├── set_embedding()
│   │   ├── get_retrieval()
│   │   ├── set_retrieval()
│   │   └── check_rate_limit()
│   └── create_redis_client()
└── ...
```

### 3.3 核心接口

```python
class RedisCache:
    def __init__(self, redis_url: str):
        self.client = Redis.from_url(redis_url)
    
    async def get_session_context(self, session_id: str) -> list[dict] | None:
        key = f"session:{session_id}:context"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_session_context(
        self, session_id: str, messages: list[dict], ttl: int = 3600
    ) -> None:
        key = f"session:{session_id}:context"
        await self.client.setex(key, ttl, json.dumps(messages))
    
    async def get_embedding(self, text_hash: str) -> list[float] | None:
        key = f"embed:{text_hash}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def check_rate_limit(self, user_id: str, max_requests: int = 60) -> bool:
        key = f"rate:{user_id}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, 60)
        return count <= max_requests
```

### 3.4 集成点

**与 Embedding Provider 集成：**
```python
async def get_embedding(self, text: str) -> list[float]:
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    cached = await self.cache.get_embedding(text_hash)
    if cached:
        return cached
    
    embedding = await self.ollama_client.embed(text)
    await self.cache.set_embedding(text_hash, embedding)
    return embedding
```

**与 Retrieval 集成：**
```python
async def retrieve(self, query: str) -> list[dict]:
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    
    cached = await self.cache.get_retrieval(query_hash)
    if cached:
        return cached
    
    results = await self.es_client.search(query)
    await self.cache.set_retrieval(query_hash, results)
    return results
```

**与 Chat Service 集成：**
```python
async def ask_question_stream_with_rag(...):
    context = await cache.get_session_context(session_id)
    if not context:
        context = await get_messages_by_session(session, session_id)
        await cache.set_session_context(session_id, context)
```

### 3.5 测试策略

**Unit Tests:**
- 各缓存方法的读写
- TTL 过期行为
- 限流计数逻辑

**Integration Tests:**
- 真实 Redis 连接测试
- 并发访问测试

---

## 4. Task 18: Authentication API

### 4.1 认证流程设计

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Register  │────>│    Login    │────>│  JWT Token  │
│  POST /auth │     │  POST /auth │     │   Bearer    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Protected  │
                    │   Routes    │
                    │  (需要 JWT)  │
                    └─────────────┘
```

### 4.2 文件结构

```
backend/app/
├── api/
│   └── auth.py                    # 新建：认证路由
│       ├── POST /register
│       ├── POST /login
│       └── POST /logout
├── application/
│   └── auth_service.py            # 新建：认证业务逻辑
│       ├── register_user()
│       ├── authenticate_user()
│       ├── create_access_token()
│       └── verify_token()
├── infra/
│   └── security/
│       ├── __init__.py
│       └── jwt_handler.py         # 新建：JWT 处理
│           ├── create_token()
│           ├── verify_token()
│           └── decode_token()
└── api/
    └── deps.py                    # 新建：依赖注入
        └── get_current_user()
```

### 4.3 API 接口设计

**POST /api/v1/auth/register**
```json
// Request
{
  "email": "user@example.com",
  "password": "secure_password"
}

// Response
{
  "id": "user-uuid",
  "email": "user@example.com",
  "created_at": "2026-04-05T10:00:00Z"
}
```

**POST /api/v1/auth/login**
```json
// Request
{
  "email": "user@example.com",
  "password": "secure_password"
}

// Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**POST /api/v1/auth/logout**
```json
// Headers: Authorization: Bearer <token>
// Response: 204 No Content
```

### 4.4 密码安全

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

### 4.5 JWT 处理

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt

class JWTHandler:
    def __init__(self, secret: str, algorithm: str, expire_minutes: int):
        self.secret = secret
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes
    
    def create_token(self, user_id: str) -> str:
        expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        payload = {"sub": user_id, "exp": expire}
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except JWTError:
            return None
```

### 4.6 保护路由

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    token = credentials.credentials
    user_id = jwt_handler.verify_token(token)
    
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user
```

### 4.7 需要保护的端点

以下端点需要 JWT 认证：
- `/chat/sessions` - 所有会话操作
- `/chat/ask` - 问答
- `/documents/*` - 文档管理

以下端点保持公开：
- `/auth/register`
- `/auth/login`
- `/health/*`

### 4.8 测试策略

**Unit Tests:**
- 密码哈希验证
- JWT 创建和验证
- Token 过期处理

**Contract Tests:**
- 注册/登录 API 契约
- 401 响应格式

**Integration Tests:**
- 完整认证流程
- Token 黑名单（可选）

---

## 5. Task 19: Integration Tests

### 5.1 测试范围

| 组件 | 测试场景 | 依赖 |
|------|----------|------|
| **PostgreSQL** | CRUD 操作、事务、级联删除 | Docker Testcontainers |
| **Elasticsearch** | 索引创建、向量检索、BM25 检索 | Docker Testcontainers |
| **Redis** | 缓存读写、TTL、限流 | Docker Testcontainers |
| **LLM Provider** | 响应生成、流式输出、错误处理 | Mock 或真实服务 |
| **完整流程** | 摄入 → 检索 → 问答 | 所有容器 |

### 5.2 文件结构

```
backend/tests/integration/
├── __init__.py
├── conftest.py                    # 新建：共享 fixtures
│   ├── postgres_container
│   ├── elasticsearch_container
│   ├── redis_container
│   └── mock_llm
├── test_postgres.py               # 新建：PG 集成测试
├── test_elasticsearch.py          # 新建：ES 集成测试
├── test_redis.py                  # 新建：Redis 集成测试
├── test_llm_provider.py           # 新建：LLM 集成测试
├── test_ingestion_flow.py         # 已存在，可能需要更新
└── test_retrieval_flow.py         # 已存在，可能需要更新
```

### 5.3 Testcontainers 配置

```python
# backend/tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.elasticsearch import ElasticSearchContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def elasticsearch_container():
    with ElasticSearchContainer("elasticsearch:8.10.0") as es:
        yield es

@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as redis:
        yield redis

@pytest.fixture
async def db_session(postgres_container):
    from app.infra.postgres.database import get_session_maker
    
    maker = get_session_maker(postgres_container.get_connection_url())
    async with get_session(maker) as session:
        yield session

@pytest.fixture
def es_client(elasticsearch_container):
    from elasticsearch import AsyncElasticsearch
    return AsyncElasticsearch(elasticsearch_container.get_connection_url())

@pytest.fixture
def redis_client(redis_container):
    from redis.asyncio import Redis
    return Redis.from_url(redis_container.get_connection_url())
```

### 5.4 测试用例设计

**test_postgres.py:**
- test_create_user
- test_cascade_delete_session
- test_transaction_rollback

**test_elasticsearch.py:**
- test_create_index
- test_vector_search
- test_bm25_search

**test_redis.py:**
- test_cache_set_get
- test_ttl_expiry
- test_rate_limit_counter

**test_ingestion_flow.py:**
- test_full_ingestion_pipeline

**test_retrieval_flow.py:**
- test_rrf_fusion_retrieval
- test_cache_hit

### 5.5 Mock LLM 策略

```python
@pytest.fixture
def mock_llm_provider():
    class MockLLMProvider:
        async def generate(self, messages):
            return LLMResponse(
                content="Mock response",
                model="mock-model",
                prompt_tokens=10,
                completion_tokens=5,
                duration_ms=100,
            )
        
        async def generate_stream(self, messages):
            for chunk in ["Mock ", "stream ", "response"]:
                yield chunk
    
    return MockLLMProvider()
```

### 5.6 依赖添加

```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    # ... existing deps ...
    "testcontainers>=4.0.0",
    "docker>=7.0.0",
]
```

---

## 6. Task 20: E2E Tests

### 6.1 完整用户旅程

```
1. 用户注册        POST /auth/register
2. 用户登录        POST /auth/login → 获取 JWT Token
3. 创建会话        POST /chat/sessions
4. 上传文档        POST /documents/upload
5. 等待摄入完成     GET /documents/{id}/status (轮询)
6. 多轮问答        POST /chat/ask/stream (SSE)
7. 会话管理        GET /chat/sessions, DELETE /chat/sessions/{id}
8. 清理           DELETE /documents/{id}
```

### 6.2 文件结构

```
backend/tests/e2e/
├── __init__.py
├── conftest.py                    # 更新
│   ├── e2e_client
│   ├── test_user
│   └── auth_headers
├── test_full_journey.py           # 新建
│   ├── test_user_registration()
│   ├── test_user_login()
│   ├── test_document_upload_and_ingestion()
│   ├── test_multi_turn_qa()
│   ├── test_session_management()
│   └── test_full_journey()
├── test_ingestion_flow.py         # 已存在
├── test_retrieval_flow.py         # 已存在
└── test_service_health.py         # 已存在
```

### 6.3 E2E 测试配置

```python
# backend/tests/e2e/conftest.py
import pytest
import httpx

E2E_BASE_URL = "http://localhost:8000/api/v1"

@pytest.fixture(scope="session")
async def e2e_client():
    async with httpx.AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        yield client

@pytest.fixture
async def test_user(e2e_client):
    response = await e2e_client.post(
        "/auth/register",
        json={
            "email": f"e2e_test_{uuid.uuid4()}@example.com",
            "password": "test_password_123",
        },
    )
    return response.json()

@pytest.fixture
async def auth_headers(e2e_client, test_user):
    response = await e2e_client.post(
        "/auth/login",
        json={
            "email": test_user["email"],
            "password": "test_password_123",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### 6.4 测试数据准备

```
backend/tests/fixtures/
├── sample_document.pdf            # 测试文档
├── sample_queries.json            # 测试查询集
└── expected_responses.json        # 预期响应（可选）
```

### 6.5 E2E 运行配置

```yaml
# .github/workflows/ci.yml
test-e2e:
  services:
    postgres: postgres:15
    elasticsearch: elasticsearch:8.10.0
    redis: redis:7
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = ["e2e: end-to-end tests"]
```

---

## 7. Worktree 环境配置

### 7.1 问题

Git worktree 创建时不会拷贝 `.env` 文件（gitignored），但开发/测试需要这些配置。

### 7.2 解决方案

采用**多层保障策略**：

| 层级 | 方案 | 用途 |
|------|------|------|
| 1 | `.env.example` | 模板参考 |
| 2 | 符号链接脚本 | 自动共享主 worktree 的 .env |
| 3 | 测试默认配置 | 无 .env 时的 fallback |

### 7.3 文件结构

```
backend/
├── .env                    # 实际环境配置（gitignored）
├── .env.example            # 新建：环境变量模板
├── .env.test               # 新建：测试环境配置
└── scripts/
    └── setup-worktree-env.sh   # 新建：worktree 环境配置脚本
```

### 7.4 .env.example 模板

```bash
# 应用配置
APP_NAME=MuseAI
APP_ENV=development
DEBUG=true

# 数据库
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/museai

# Redis
REDIS_URL=redis://localhost:6379/0

# Elasticsearch
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=museai_chunks_v1
EMBEDDING_DIMS=1536

# JWT
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# LLM Provider
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.example.com
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4

# Embedding Provider
EMBEDDING_PROVIDER=ollama
EMBEDDING_OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_OLLAMA_MODEL=nomic-embed-text
```

### 7.5 Worktree 环境配置脚本

```bash
#!/bin/bash
# scripts/setup-worktree-env.sh

set -e

WORKTREE_ROOT=$(git rev-parse --show-toplevel)
MAIN_REPO_ROOT=$(git worktree list | head -1 | awk '{print $1}')
BACKEND_DIR="backend"

if [ -f "$MAIN_REPO_ROOT/$BACKEND_DIR/.env" ]; then
    echo "Creating symlink to main repo .env..."
    
    if [ -f "$WORKTREE_ROOT/$BACKEND_DIR/.env" ]; then
        mv "$WORKTREE_ROOT/$BACKEND_DIR/.env" "$WORKTREE_ROOT/$BACKEND_DIR/.env.backup"
    fi
    
    ln -s "$MAIN_REPO_ROOT/$BACKEND_DIR/.env" "$WORKTREE_ROOT/$BACKEND_DIR/.env"
    echo "✓ Symlink created"
else
    echo "⚠ No .env in main repo. Creating from .env.example..."
    cp "$WORKTREE_ROOT/$BACKEND_DIR/.env.example" "$WORKTREE_ROOT/$BACKEND_DIR/.env"
fi
```

### 7.6 测试环境默认配置

```python
# backend/tests/conftest.py
@lru_cache
def get_test_settings():
    """获取测试配置，支持无 .env 时的 fallback"""
    from app.config.settings import Settings
    
    env_vars = {
        "APP_NAME": os.getenv("APP_NAME", "MuseAI Test"),
        "APP_ENV": os.getenv("APP_ENV", "test"),
        "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:"),
        # ... 其他默认值
    }
    
    return Settings(**env_vars)
```

### 7.7 Mock Provider for Testing

```python
# backend/tests/fixtures/mock_providers.py

class MockEmbeddingProvider:
    def __init__(self, dims: int = 768):
        self.dims = dims
    
    async def embed(self, text: str) -> list[float]:
        return [0.1] * self.dims


class MockLLMProvider:
    async def generate(self, messages: list[dict]) -> dict:
        return {
            "content": "This is a mock response.",
            "model": "mock-model",
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "duration_ms": 100,
        }
    
    async def generate_stream(self, messages: list[dict]):
        for chunk in ["Mock ", "stream ", "response."]:
            yield chunk
```

---

## 8. 实施顺序

按计划顺序执行：Task 16 → Task 17 → Task 18 → Task 19 → Task 20

每个任务遵循 TDD 流程：
1. 写失败测试
2. 写最小实现
3. 重构优化
4. 提交代码
