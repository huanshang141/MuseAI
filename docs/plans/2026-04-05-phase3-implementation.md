# MuseAI Phase 3 Implementation Plan
**Status:** completed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete Phase 3 of MuseAI V2: Query Transform, Redis Cache, Authentication, Integration Tests, and E2E Tests.

**Architecture:** Strict layered architecture (API → Application → Domain → Infrastructure). Each task follows TDD with unit tests first, then implementation.

**Tech Stack:** FastAPI, Redis, JWT (jose), bcrypt, testcontainers, pytest

---

## Phase 3 Setup: Worktree Environment

### Task 0: Environment Setup for Worktree

**Files:**
- Create: `backend/.env.example`
- Create: `backend/.env.test`
- Create: `scripts/setup-worktree-env.sh`
- Create: `backend/tests/fixtures/mock_providers.py`

**Step 1: Create .env.example template**

```bash
# backend/.env.example
**Status:** completed
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

# LLM Provider (OpenAI Compatible)
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.example.com
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4

# Embedding Provider (Ollama)
EMBEDDING_PROVIDER=ollama
EMBEDDING_OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_OLLAMA_MODEL=nomic-embed-text
```

**Step 2: Create .env.test for testing**

```bash
# backend/.env.test
APP_NAME=MuseAI Test
APP_ENV=test
DEBUG=true

DATABASE_URL=sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379/15
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=test_index
EMBEDDING_DIMS=768

JWT_SECRET=test-secret-key-for-testing-only
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

LLM_PROVIDER=mock
LLM_BASE_URL=http://localhost
LLM_API_KEY=test-key
LLM_MODEL=mock-model

EMBEDDING_PROVIDER=mock
EMBEDDING_OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_OLLAMA_MODEL=mock-embedding
```

**Step 3: Create worktree setup script**

```bash
#!/bin/bash
# scripts/setup-worktree-env.sh

set -e

WORKTREE_ROOT=$(git rev-parse --show-toplevel)
MAIN_REPO_ROOT=$(git worktree list | head -1 | awk '{print $1}')
BACKEND_DIR="backend"

echo "Setting up worktree environment..."

if [ -f "$MAIN_REPO_ROOT/$BACKEND_DIR/.env" ]; then
    echo "Creating symlink to main repo .env..."
    
    if [ -f "$WORKTREE_ROOT/$BACKEND_DIR/.env" ]; then
        echo "Backing up existing .env to .env.backup"
        mv "$WORKTREE_ROOT/$BACKEND_DIR/.env" "$WORKTREE_ROOT/$BACKEND_DIR/.env.backup"
    fi
    
    ln -s "$MAIN_REPO_ROOT/$BACKEND_DIR/.env" "$WORKTREE_ROOT/$BACKEND_DIR/.env"
    echo "✓ Symlink created: $WORKTREE_ROOT/$BACKEND_DIR/.env -> $MAIN_REPO_ROOT/$BACKEND_DIR/.env"
else
    echo "⚠ No .env found in main repo. Creating from .env.example..."
    cp "$WORKTREE_ROOT/$BACKEND_DIR/.env.example" "$WORKTREE_ROOT/$BACKEND_DIR/.env"
    echo "✓ Created .env from template. Please fill in your credentials."
fi

if [ -f "$MAIN_REPO_ROOT/$BACKEND_DIR/.env.test" ]; then
    if [ ! -L "$WORKTREE_ROOT/$BACKEND_DIR/.env.test" ]; then
        ln -sf "$MAIN_REPO_ROOT/$BACKEND_DIR/.env.test" "$WORKTREE_ROOT/$BACKEND_DIR/.env.test"
        echo "✓ Symlink created for .env.test"
    fi
fi

echo "Environment setup complete!"
```

**Step 4: Make script executable**

Run: `chmod +x scripts/setup-worktree-env.sh`

**Step 5: Create mock providers for testing**

```python
# backend/tests/fixtures/mock_providers.py
from typing import Any
from collections.abc import AsyncGenerator


class MockEmbeddingProvider:
    def __init__(self, dims: int = 768):
        self.dims = dims
    
    async def embed(self, text: str) -> list[float]:
        return [0.1] * self.dims
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dims for _ in texts]


class MockLLMProvider:
    async def generate(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "content": "This is a mock response for testing.",
            "model": "mock-model",
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "duration_ms": 100,
        }
    
    async def generate_stream(
        self, messages: list[dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        for chunk in ["Mock ", "stream ", "response."]:
            yield chunk
```

**Step 6: Commit setup files**

```bash
git add backend/.env.example backend/.env.test scripts/setup-worktree-env.sh backend/tests/fixtures/mock_providers.py
git commit -m "feat: add worktree environment setup and mock providers"
```

---

## Task 16: Query Transform

### Task 16.1: Query Transform Strategy Enum

**Files:**
- Create: `backend/app/workflows/query_transform.py`
- Test: `backend/tests/unit/test_query_transform.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_query_transform.py
import pytest
from app.workflows.query_transform import QueryTransformStrategy, select_strategy


def test_strategy_enum_values():
    assert QueryTransformStrategy.NONE.value == "none"
    assert QueryTransformStrategy.STEP_BACK.value == "step_back"
    assert QueryTransformStrategy.HYDE.value == "hyde"
    assert QueryTransformStrategy.MULTI_QUERY.value == "multi_query"


def test_select_strategy_high_score_returns_none():
    strategy = select_strategy(
        query="test query",
        retrieval_score=0.8,
        attempt=1
    )
    assert strategy == QueryTransformStrategy.NONE


def test_select_strategy_low_score_first_attempt_with_details():
    strategy = select_strategy(
        query="What happened on 2024-01-15?",
        retrieval_score=0.3,
        attempt=1
    )
    assert strategy == QueryTransformStrategy.STEP_BACK


def test_select_strategy_low_score_second_attempt():
    strategy = select_strategy(
        query="test query",
        retrieval_score=0.3,
        attempt=2
    )
    assert strategy == QueryTransformStrategy.HYDE


def test_select_strategy_low_score_third_attempt():
    strategy = select_strategy(
        query="test query",
        retrieval_score=0.3,
        attempt=3
    )
    assert strategy == QueryTransformStrategy.MULTI_QUERY
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_query_transform.py -v`
Expected: FAIL with import errors

**Step 3: Write implementation**

```python
# backend/app/workflows/query_transform.py
import re
from enum import Enum


class QueryTransformStrategy(Enum):
    NONE = "none"
    STEP_BACK = "step_back"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"


def has_specific_details(query: str) -> bool:
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}",
        r"\d{1,2}:\d{2}",
        r"\d+%",
        r"\d+\s*(万|千|百|ten|hundred|thousand|million)",
    ]
    return any(re.search(p, query) for p in patterns)


def is_ambiguous(query: str) -> bool:
    ambiguous_words = ["那个", "这个", "它", "那个东西", "something", "it", "that"]
    query_lower = query.lower()
    return any(word in query_lower for word in ambiguous_words) or len(query) < 10


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

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_query_transform.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/app/workflows/query_transform.py backend/tests/unit/test_query_transform.py
git commit -m "feat: add query transform strategy selection"
```

---

### Task 16.2: Query Transformer Class

**Files:**
- Modify: `backend/app/workflows/query_transform.py`
- Modify: `backend/tests/unit/test_query_transform.py`

**Step 1: Add failing tests for transformer**

```python
# Add to backend/tests/unit/test_query_transform.py
from unittest.mock import AsyncMock, MagicMock
from app.workflows.query_transform import QueryTransformer


@pytest.mark.asyncio
async def test_transform_step_back():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = {
        "content": "这个时期有什么重要的历史事件？",
        "model": "mock",
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "duration_ms": 100,
    }
    
    transformer = QueryTransformer(mock_llm)
    result = await transformer.transform_step_back("2024年1月发生了什么？")
    
    assert result == "这个时期有什么重要的历史事件？"
    mock_llm.generate.assert_called_once()


@pytest.mark.asyncio
async def test_transform_hyde():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = {
        "content": "这是一件青铜器，用于祭祀仪式，年代可追溯到商朝。",
        "model": "mock",
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "duration_ms": 100,
    }
    
    transformer = QueryTransformer(mock_llm)
    result = await transformer.transform_hyde("这件文物是什么？")
    
    assert "青铜器" in result
    mock_llm.generate.assert_called_once()


@pytest.mark.asyncio
async def test_transform_multi_query():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = {
        "content": "1. 这件文物的历史背景是什么？\n2. 这件文物的用途是什么？\n3. 这件文物的制作工艺如何？",
        "model": "mock",
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "duration_ms": 100,
    }
    
    transformer = QueryTransformer(mock_llm)
    result = await transformer.transform_multi_query("这件文物是什么？")
    
    assert len(result) == 3
    assert "历史背景" in result[0]
    assert "用途" in result[1]
    assert "制作工艺" in result[2]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_query_transform.py -v`
Expected: FAIL with QueryTransformer not defined

**Step 3: Add QueryTransformer class**

```python
# Add to backend/app/workflows/query_transform.py
from typing import Any


class QueryTransformer:
    STEP_BACK_PROMPT = """你是一个查询优化专家。用户提出了一个过于具体的问题，请生成一个更抽象、更宽泛的问题，帮助获取更多背景信息。

原始问题：{query}

请生成一个更抽象的问题（只输出问题本身，不要解释）："""

    HYDE_PROMPT = """你是一个查询优化专家。请为用户的问题生成一个假设性的答案，用于检索相关文档。

用户问题：{query}

请生成一个假设性的答案（只输出答案，不要解释）："""

    MULTI_QUERY_PROMPT = """你是一个查询优化专家。用户的问题可能有歧义或过于宽泛，请生成3个相关的、更具体的问题，每个问题一行，用数字编号。

用户问题：{query}

请生成3个相关问题："""

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    async def transform_step_back(self, query: str) -> str:
        prompt = self.STEP_BACK_PROMPT.format(query=query)
        response = await self.llm_provider.generate(
            [{"role": "user", "content": prompt}]
        )
        return response["content"].strip()

    async def transform_hyde(self, query: str) -> str:
        prompt = self.HYDE_PROMPT.format(query=query)
        response = await self.llm_provider.generate(
            [{"role": "user", "content": prompt}]
        )
        return response["content"].strip()

    async def transform_multi_query(self, query: str) -> list[str]:
        prompt = self.MULTI_QUERY_PROMPT.format(query=query)
        response = await self.llm_provider.generate(
            [{"role": "user", "content": prompt}]
        )
        
        lines = response["content"].strip().split("\n")
        queries = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                cleaned = line.lstrip("0123456789.-) ")
                if cleaned:
                    queries.append(cleaned)
        
        return queries[:3] if queries else [query]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_query_transform.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add backend/app/workflows/query_transform.py backend/tests/unit/test_query_transform.py
git commit -m "feat: add QueryTransformer with step-back, hyde, and multi-query strategies"
```

---

### Task 16.3: Integrate with Multi-Turn State Machine

**Files:**
- Modify: `backend/app/workflows/multi_turn.py`
- Modify: `backend/tests/unit/test_state_machine.py`

**Step 1: Add test for transform_query integration**

```python
# Add to backend/tests/unit/test_state_machine.py
from unittest.mock import AsyncMock, MagicMock
from app.workflows.multi_turn import MultiTurnStateMachine


@pytest.mark.asyncio
async def test_state_machine_transform_query():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = {
        "content": "更广泛的问题",
        "model": "mock",
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "duration_ms": 50,
    }
    
    sm = MultiTurnStateMachine(score_threshold=0.7, max_attempts=3)
    sm.llm_provider = mock_llm
    
    queries = await sm.transform_query("具体问题", retrieval_score=0.3)
    
    assert len(queries) >= 1
    assert queries[0] != "具体问题"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_state_machine.py::test_state_machine_transform_query -v`
Expected: FAIL

**Step 3: Modify multi_turn.py**

```python
# Modify backend/app/workflows/multi_turn.py
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.workflows.query_transform import (
    QueryTransformStrategy,
    QueryTransformer,
    select_strategy,
)


class State(Enum):
    START = "start"
    RETRIEVE = "retrieve"
    EVALUATE = "evaluate"
    TRANSFORM = "transform"
    GENERATE = "generate"
    END = "end"


@dataclass
class MultiTurnResult:
    state: State
    query: str
    answer: str
    retrieval_score: float
    attempts: int
    transformations: list[str]


class MultiTurnStateMachine:
    def __init__(
        self,
        score_threshold: float = 0.7,
        max_attempts: int = 3,
        llm_provider: Any = None,
    ):
        self.score_threshold = score_threshold
        self.max_attempts = max_attempts
        self.llm_provider = llm_provider
        self.current_state = State.START
        self.attempts = 0
        self._query: str | None = None
        self._retrieval_score: float | None = None
        self._transformations: list[str] = []

    def process(self, query: str) -> None:
        self._query = query
        self.current_state = State.RETRIEVE

    def set_retrieval_score(self, score: float) -> None:
        self._retrieval_score = score
        self.current_state = State.EVALUATE

    def evaluate(self) -> None:
        if self._retrieval_score is None:
            raise ValueError("No retrieval score set")

        if self._retrieval_score >= self.score_threshold:
            self.current_state = State.GENERATE
        elif self.attempts < self.max_attempts:
            self.current_state = State.TRANSFORM
            self.attempts += 1
        else:
            self.current_state = State.GENERATE

    async def transform_query(self, query: str, retrieval_score: float) -> list[str]:
        strategy = select_strategy(query, retrieval_score, self.attempts)
        
        if strategy == QueryTransformStrategy.NONE:
            return [query]
        
        if self.llm_provider is None:
            return [query]
        
        transformer = QueryTransformer(self.llm_provider)
        
        if strategy == QueryTransformStrategy.STEP_BACK:
            transformed = await transformer.transform_step_back(query)
            self._transformations.append(f"step_back: {transformed}")
            return [transformed]
        elif strategy == QueryTransformStrategy.HYDE:
            transformed = await transformer.transform_hyde(query)
            self._transformations.append(f"hyde: {transformed}")
            return [transformed]
        else:
            transformed = await transformer.transform_multi_query(query)
            self._transformations.append(f"multi_query: {transformed}")
            return transformed

    def apply_transform(self) -> None:
        self.current_state = State.RETRIEVE

    def run(
        self,
        query: str,
        retrieval_score: float,
        generated_answer: str,
    ) -> MultiTurnResult:
        self.current_state = State.START
        self.attempts = 0
        self._transformations = []

        self.process(query)

        while self.current_state != State.GENERATE:
            self.set_retrieval_score(retrieval_score)
            self.evaluate()

            if self.current_state == State.TRANSFORM:
                self.apply_transform()

        self.current_state = State.END

        return MultiTurnResult(
            state=self.current_state,
            query=query,
            answer=generated_answer,
            retrieval_score=retrieval_score,
            attempts=self.attempts,
            transformations=self._transformations,
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_state_machine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/workflows/multi_turn.py backend/tests/unit/test_state_machine.py
git commit -m "feat: integrate query transform with multi-turn state machine"
```

---

## Task 17: Redis Cache Layer

### Task 17.1: Redis Cache Client

**Files:**
- Create: `backend/app/infra/redis/cache.py`
- Create: `backend/tests/unit/test_redis_cache.py`

**Step 1: Add redis dependency**

Run: `uv add redis`

**Step 2: Write the failing test**

```python
# backend/tests/unit/test_redis_cache.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infra.redis.cache import RedisCache


@pytest.mark.asyncio
async def test_get_session_context_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_session_context("session-123")
    
    assert result is None
    mock_redis.get.assert_called_once_with("session:session-123:context")


@pytest.mark.asyncio
async def test_get_session_context_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b'[{"role": "user", "content": "hello"}]'
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_session_context("session-123")
    
    assert result == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_set_session_context():
    mock_redis = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    await cache.set_session_context(
        "session-123",
        [{"role": "user", "content": "hello"}],
        ttl=3600
    )
    
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "session:session-123:context"
    assert call_args[0][1] == 3600


@pytest.mark.asyncio
async def test_get_embedding_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_embedding("hash123")
    
    assert result is None


@pytest.mark.asyncio
async def test_get_embedding_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = b'[0.1, 0.2, 0.3]'
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_embedding("hash123")
    
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_set_embedding():
    mock_redis = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    await cache.set_embedding("hash123", [0.1, 0.2, 0.3], ttl=86400)
    
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_get_retrieval_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.get_retrieval("query123")
    
    assert result is None


@pytest.mark.asyncio
async def test_set_retrieval():
    mock_redis = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    await cache.set_retrieval("query123", [{"chunk_id": "c1"}], ttl=600)
    
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_check_rate_limit_within_limit():
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 5
    mock_redis.expire = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.check_rate_limit("user-123", max_requests=60)
    
    assert result is True


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded():
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 61
    mock_redis.expire = AsyncMock()
    
    cache = RedisCache.__new__(RedisCache)
    cache.client = mock_redis
    
    result = await cache.check_rate_limit("user-123", max_requests=60)
    
    assert result is False
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_redis_cache.py -v`
Expected: FAIL with import errors

**Step 4: Write implementation**

```python
# backend/app/infra/redis/cache.py
import json
from typing import Any

from redis.asyncio import Redis


class RedisCache:
    def __init__(self, redis_url: str):
        self.client = Redis.from_url(redis_url)
    
    @classmethod
    def from_url(cls, redis_url: str) -> "RedisCache":
        return cls(redis_url)
    
    async def close(self) -> None:
        await self.client.close()
    
    async def get_session_context(self, session_id: str) -> list[dict] | None:
        key = f"session:{session_id}:context"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_session_context(
        self, session_id: str, messages: list[dict], ttl: int = 3600
    ) -> None:
        key = f"session:{session_id}:context"
        await self.client.setex(key, ttl, json.dumps(messages))
    
    async def delete_session_context(self, session_id: str) -> None:
        key = f"session:{session_id}:context"
        await self.client.delete(key)
    
    async def get_embedding(self, text_hash: str) -> list[float] | None:
        key = f"embed:{text_hash}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_embedding(
        self, text_hash: str, embedding: list[float], ttl: int = 86400
    ) -> None:
        key = f"embed:{text_hash}"
        await self.client.setex(key, ttl, json.dumps(embedding))
    
    async def get_retrieval(self, query_hash: str) -> list[dict] | None:
        key = f"retrieve:{query_hash}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def set_retrieval(
        self, query_hash: str, results: list[dict], ttl: int = 600
    ) -> None:
        key = f"retrieve:{query_hash}"
        await self.client.setex(key, ttl, json.dumps(results))
    
    async def check_rate_limit(self, user_id: str, max_requests: int = 60) -> bool:
        key = f"rate:{user_id}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, 60)
        return count <= max_requests
    
    async def get_rate_limit_count(self, user_id: str) -> int:
        key = f"rate:{user_id}"
        count = await self.client.get(key)
        return int(count) if count else 0


def create_redis_client(redis_url: str) -> RedisCache:
    return RedisCache(redis_url)
```

**Step 5: Update __init__.py**

```python
# backend/app/infra/redis/__init__.py
from app.infra.redis.cache import RedisCache, create_redis_client

__all__ = ["RedisCache", "create_redis_client"]
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_redis_cache.py -v`
Expected: PASS (10 tests)

**Step 7: Commit**

```bash
git add backend/app/infra/redis/cache.py backend/app/infra/redis/__init__.py backend/tests/unit/test_redis_cache.py
git commit -m "feat: add Redis cache layer with session, embedding, retrieval, and rate limit"
```

---

## Task 18: Authentication API

### Task 18.1: JWT Handler

**Files:**
- Create: `backend/app/infra/security/__init__.py`
- Create: `backend/app/infra/security/jwt_handler.py`
- Create: `backend/tests/unit/test_jwt_handler.py`

**Step 1: Add dependencies**

Run: `uv add python-jose[cryptography] passlib[bcrypt]`

**Step 2: Write the failing test**

```python
# backend/tests/unit/test_jwt_handler.py
import pytest
from datetime import timedelta
from app.infra.security.jwt_handler import JWTHandler


def test_create_token():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    token = handler.create_token("user-123")
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_token_valid():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    token = handler.create_token("user-123")
    
    user_id = handler.verify_token(token)
    
    assert user_id == "user-123"


def test_verify_token_invalid():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    
    user_id = handler.verify_token("invalid-token")
    
    assert user_id is None


def test_verify_token_wrong_secret():
    handler1 = JWTHandler(
        secret="secret1",
        algorithm="HS256",
        expire_minutes=60
    )
    handler2 = JWTHandler(
        secret="secret2",
        algorithm="HS256",
        expire_minutes=60
    )
    
    token = handler1.create_token("user-123")
    user_id = handler2.verify_token(token)
    
    assert user_id is None


def test_decode_token():
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    token = handler.create_token("user-123")
    
    payload = handler.decode_token(token)
    
    assert payload is not None
    assert payload.get("sub") == "user-123"
    assert "exp" in payload
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_jwt_handler.py -v`
Expected: FAIL with import errors

**Step 4: Write implementation**

```python
# backend/app/infra/security/__init__.py
from app.infra.security.jwt_handler import JWTHandler

__all__ = ["JWTHandler"]
```

```python
# backend/app/infra/security/jwt_handler.py
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt


class JWTHandler:
    def __init__(self, secret: str, algorithm: str, expire_minutes: int):
        self.secret = secret
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes
    
    def create_token(self, user_id: str, extra_data: dict[str, Any] | None = None) -> str:
        expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        payload = {"sub": user_id, "exp": expire}
        
        if extra_data:
            payload.update(extra_data)
        
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except JWTError:
            return None
    
    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_jwt_handler.py -v`
Expected: PASS (5 tests)

**Step 6: Commit**

```bash
git add backend/app/infra/security/ backend/tests/unit/test_jwt_handler.py
git commit -m "feat: add JWT handler for authentication"
```

---

### Task 18.2: Password Hashing

**Files:**
- Create: `backend/app/infra/security/password.py`
- Create: `backend/tests/unit/test_password.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_password.py
from app.infra.security.password import hash_password, verify_password


def test_hash_password():
    password = "secure_password_123"
    hashed = hash_password(password)
    
    assert hashed != password
    assert len(hashed) > 0
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    password = "secure_password_123"
    hashed = hash_password(password)
    
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    password = "secure_password_123"
    wrong_password = "wrong_password"
    hashed = hash_password(password)
    
    assert verify_password(wrong_password, hashed) is False


def test_hash_password_different_each_time():
    password = "secure_password_123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    
    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_password.py -v`
Expected: FAIL with import errors

**Step 3: Write implementation**

```python
# backend/app/infra/security/password.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

**Step 4: Update __init__.py**

```python
# backend/app/infra/security/__init__.py
from app.infra.security.jwt_handler import JWTHandler
from app.infra.security.password import hash_password, verify_password

__all__ = ["JWTHandler", "hash_password", "verify_password"]
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_password.py -v`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add backend/app/infra/security/ backend/tests/unit/test_password.py
git commit -m "feat: add password hashing with bcrypt"
```

---

### Task 18.3: Auth Service

**Files:**
- Create: `backend/app/application/auth_service.py`
- Create: `backend/tests/unit/test_auth_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_auth_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
)


@pytest.mark.asyncio
async def test_register_user():
    mock_session = AsyncMock()
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    
    from app.infra.security import hash_password
    
    user = await register_user(
        session=mock_session,
        email="test@example.com",
        password="password123",
        hash_password_func=hash_password,
    )
    
    assert user is not None
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_success():
    from app.infra.security import hash_password
    
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"
    mock_user.password_hash = hash_password("password123")
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result
    
    user = await authenticate_user(
        session=mock_session,
        email="test@example.com",
        password="password123",
        verify_password_func=lambda p, h: p == "password123" and h == mock_user.password_hash,
    )
    
    assert user is not None
    assert user.id == "user-123"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    from app.infra.security import hash_password
    
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.password_hash = hash_password("password123")
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result
    
    user = await authenticate_user(
        session=mock_session,
        email="test@example.com",
        password="wrong_password",
        verify_password_func=lambda p, h: False,
    )
    
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    user = await authenticate_user(
        session=mock_session,
        email="notfound@example.com",
        password="password123",
        verify_password_func=lambda p, h: True,
    )
    
    assert user is None


def test_create_access_token():
    from app.infra.security.jwt_handler import JWTHandler
    
    handler = JWTHandler(
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=60
    )
    
    token = create_access_token(user_id="user-123", jwt_handler=handler)
    
    assert token is not None
    assert isinstance(token, str)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_auth_service.py -v`
Expected: FAIL with import errors

**Step 3: Write implementation**

```python
# backend/app/application/auth_service.py
import uuid
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import User


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    hash_password_func: Callable[[str], str],
) -> User:
    user_id = str(uuid.uuid4())
    password_hash = hash_password_func(password)
    
    user = User(
        id=user_id,
        email=email,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
    verify_password_func: Callable[[str, str], bool],
) -> User | None:
    user = await get_user_by_email(session, email)
    
    if user is None:
        return None
    
    if not verify_password_func(password, user.password_hash):
        return None
    
    return user


def create_access_token(user_id: str, jwt_handler) -> str:
    return jwt_handler.create_token(user_id)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_auth_service.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/app/application/auth_service.py backend/tests/unit/test_auth_service.py
git commit -m "feat: add auth service with register and authenticate"
```

---

### Task 18.4: Auth API Endpoints

**Files:**
- Create: `backend/app/api/auth.py`
- Create: `backend/app/api/deps.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/contract/test_auth_api.py`

**Step 1: Write the failing test**

```python
# backend/tests/contract/test_auth_api.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_register_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
            },
        )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_login_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "password123",
            },
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "password123",
            },
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong@example.com",
                "password": "password123",
            },
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong@example.com",
                "password": "wrongpassword",
            },
        )
    
    assert response.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/contract/test_auth_api.py -v`
Expected: FAIL with import errors

**Step 3: Create deps.py**

```python
# backend/app/api/deps.py
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.security.jwt_handler import JWTHandler
from app.application.auth_service import get_user_by_id

security = HTTPBearer()

_session_maker = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    global _session_maker
    if _session_maker is None:
        settings = get_settings()
        _session_maker = get_session_maker(settings.DATABASE_URL)
    async with get_session(_session_maker) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_jwt_handler() -> JWTHandler:
    settings = get_settings()
    return JWTHandler(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )


JWTHandlerDep = Annotated[JWTHandler, Depends(get_jwt_handler)]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    jwt_handler: JWTHandler = get_jwt_handler,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    token = credentials.credentials
    user_id = jwt_handler.verify_token(token)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"id": user.id, "email": user.email}


CurrentUser = Annotated[dict, Depends(get_current_user)]
```

**Step 4: Create auth.py**

```python
# backend/app/api/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, JWTHandlerDep, get_jwt_handler
from app.application.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    get_user_by_email,
)
from app.infra.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: SessionDep,
):
    existing_user = await get_user_by_email(session, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = await register_user(
        session=session,
        email=request.email,
        password=request.password,
        hash_password_func=hash_password,
    )
    await session.commit()
    
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at.isoformat(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: SessionDep,
    jwt_handler: JWTHandlerDep,
):
    user = await authenticate_user(
        session=session,
        email=request.email,
        password=request.password,
        verify_password_func=verify_password,
    )
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = create_access_token(user.id, jwt_handler)
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=jwt_handler.expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    return None
```

**Step 5: Modify main.py to include auth router**

```python
# Add to backend/app/main.py imports
from app.api.auth import router as auth_router

# Add router before or after health router
app.include_router(auth_router, prefix="/api/v1")
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest backend/tests/contract/test_auth_api.py -v`
Expected: PASS (3 tests)

**Step 7: Commit**

```bash
git add backend/app/api/auth.py backend/app/api/deps.py backend/app/main.py backend/tests/contract/test_auth_api.py
git commit -m "feat: add authentication API endpoints (register, login, logout)"
```

---

### Task 18.5: Protect Routes with JWT

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/api/documents.py`
- Create: `backend/tests/contract/test_protected_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/contract/test_protected_routes.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_protected_route_without_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sessions")
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/chat/sessions",
            headers={"Authorization": "Bearer invalid-token"},
        )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "protected@example.com", "password": "password123"},
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "protected@example.com", "password": "password123"},
        )
        token = login_response.json()["access_token"]
        
        response = await client.get(
            "/api/v1/chat/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
    
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/contract/test_protected_routes.py -v`
Expected: FAIL (returns 200 without auth)

**Step 3: Modify chat.py to require authentication**

Add `CurrentUser` dependency to protected endpoints. See design doc for full implementation.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/contract/test_protected_routes.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/app/api/documents.py backend/tests/contract/test_protected_routes.py
git commit -m "feat: protect chat and document routes with JWT authentication"
```

---

## Task 19: Integration Tests

### Task 19.1: Setup Testcontainers

**Files:**
- Modify: `pyproject.toml`
- Create: `backend/tests/integration/conftest.py`

**Step 1: Add dependencies**

Run: `uv add --dev testcontainers docker`

**Step 2: Create integration conftest**

```python
# backend/tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15", driver="asyncpg") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as redis:
        yield redis


@pytest.fixture
async def db_session(postgres_container):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    engine = create_async_engine(
        postgres_container.get_connection_url(),
        echo=False
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def redis_client(redis_container):
    from redis.asyncio import Redis
    
    client = Redis.from_url(redis_container.get_connection_url())
    yield client
    await client.close()
```

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock backend/tests/integration/conftest.py
git commit -m "feat: add testcontainers setup for integration tests"
```

---

### Task 19.2: PostgreSQL Integration Tests

**Files:**
- Create: `backend/tests/integration/test_postgres.py`

**Step 1: Write tests**

See design doc for full test implementation covering:
- User CRUD
- Session management
- Cascade deletes
- Transactions

**Step 2: Run tests**

Run: `uv run pytest backend/tests/integration/test_postgres.py -v`

**Step 3: Commit**

```bash
git add backend/tests/integration/test_postgres.py
git commit -m "test: add PostgreSQL integration tests"
```

---

### Task 19.3: Redis Integration Tests

**Files:**
- Create: `backend/tests/integration/test_redis.py`

**Step 1: Write tests**

See design doc for full test implementation covering:
- Cache set/get
- TTL expiry
- Rate limiting

**Step 2: Run tests**

Run: `uv run pytest backend/tests/integration/test_redis.py -v`

**Step 3: Commit**

```bash
git add backend/tests/integration/test_redis.py
git commit -m "test: add Redis integration tests"
```

---

## Task 20: E2E Tests

### Task 20.1: E2E Test Configuration

**Files:**
- Modify: `backend/tests/e2e/conftest.py`
- Create: `backend/tests/fixtures/sample_document.pdf`

**Step 1: Update e2e conftest**

```python
# backend/tests/e2e/conftest.py
import uuid
import pytest
import httpx

E2E_BASE_URL = "http://localhost:8000/api/v1"


@pytest.fixture(scope="session")
async def e2e_client():
    async with httpx.AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def registered_user(e2e_client):
    email = f"e2e_{uuid.uuid4()}@example.com"
    response = await e2e_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test_password_123"},
    )
    return response.json()


@pytest.fixture
async def auth_token(e2e_client, registered_user):
    response = await e2e_client.post(
        "/api/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": "test_password_123",
        },
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
```

**Step 2: Create sample test document**

Place a small PDF file in `backend/tests/fixtures/sample_document.pdf`

**Step 3: Commit**

```bash
git add backend/tests/e2e/conftest.py backend/tests/fixtures/
git commit -m "test: add E2E test configuration and fixtures"
```

---

### Task 20.2: Full Journey E2E Test

**Files:**
- Create: `backend/tests/e2e/test_full_journey.py`

**Step 1: Write full journey test**

See design doc for complete implementation.

**Step 2: Mark tests with e2e marker**

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = ["e2e: end-to-end tests"]
```

**Step 3: Commit**

```bash
git add backend/tests/e2e/test_full_journey.py pyproject.toml
git commit -m "test: add full journey E2E test"
```

---

## Summary

| Task | Files Created | Files Modified | Key Tests |
|------|---------------|----------------|-----------|
| Task 0 | 4 | 0 | - |
| Task 16 | 1 | 2 | 10+ |
| Task 17 | 2 | 1 | 10+ |
| Task 18 | 5 | 3 | 15+ |
| Task 19 | 4 | 1 | 10+ |
| Task 20 | 2 | 2 | 5+ |

**Total: ~50 tests across Phase 3**
