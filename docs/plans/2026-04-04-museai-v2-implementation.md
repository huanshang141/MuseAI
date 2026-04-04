# MuseAI V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a museum AI guide system with RAG-based Q&A, multi-turn conversation, and streaming capabilities.

**Architecture:** Modular monolith with strict layering (API → Application → Domain → Infrastructure). Single FastAPI application with dependency injection for module boundaries.

**Tech Stack:** FastAPI, PostgreSQL (asyncpg), Elasticsearch, Redis, OpenAI-compatible LLM, Ollama Embedding

---

## Phase 0: Scaffold & Baseline (Week 1)

### Task 1: Domain Models

**Files:**
- Create: `backend/app/domain/entities.py`
- Create: `backend/app/domain/value_objects.py`
- Create: `backend/app/domain/exceptions.py`
- Test: `backend/tests/unit/test_domain_entities.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_domain_entities.py
import pytest
from datetime import datetime
from app.domain.entities import User, ChatSession, ChatMessage, Document, IngestionJob
from app.domain.value_objects import SessionId, DocumentId, UserId, JobId


def test_user_creation():
    user = User(
        id=UserId("user-123"),
        email="test@example.com",
        password_hash="hashed_password",
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    assert user.id.value == "user-123"
    assert user.email == "test@example.com"


def test_chat_session_creation():
    session = ChatSession(
        id=SessionId("session-123"),
        user_id=UserId("user-123"),
        title="Test Session",
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    assert session.id.value == "session-123"
    assert session.user_id.value == "user-123"


def test_chat_message_creation():
    message = ChatMessage(
        id="msg-123",
        session_id=SessionId("session-123"),
        role="user",
        content="Hello",
        trace_id="trace-123",
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    assert message.role == "user"
    assert message.content == "Hello"


def test_document_creation():
    doc = Document(
        id=DocumentId("doc-123"),
        user_id=UserId("user-123"),
        filename="test.pdf",
        status="pending",
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    assert doc.filename == "test.pdf"
    assert doc.status == "pending"


def test_ingestion_job_creation():
    job = IngestionJob(
        id=JobId("job-123"),
        document_id=DocumentId("doc-123"),
        status="pending",
        chunk_count=0,
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    assert job.status == "pending"
    assert job.chunk_count == 0


def test_ingestion_job_status_transition():
    job = IngestionJob(
        id=JobId("job-123"),
        document_id=DocumentId("doc-123"),
        status="pending",
        chunk_count=0,
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    job.start()
    assert job.status == "processing"
    job.complete(chunk_count=10)
    assert job.status == "completed"
    assert job.chunk_count == 10


def test_ingestion_job_failure():
    job = IngestionJob(
        id=JobId("job-123"),
        document_id=DocumentId("doc-123"),
        status="pending",
        chunk_count=0,
        created_at=datetime(2026, 1, 1, 12, 0, 0)
    )
    job.start()
    job.fail(error="Something went wrong")
    assert job.status == "failed"
    assert job.error == "Something went wrong"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_domain_entities.py -v`
Expected: FAIL with import errors

**Step 3: Write value objects**

```python
# backend/app/domain/value_objects.py
from dataclasses import dataclass


@dataclass(frozen=True)
class UserId:
    value: str


@dataclass(frozen=True)
class SessionId:
    value: str


@dataclass(frozen=True)
class DocumentId:
    value: str


@dataclass(frozen=True)
class JobId:
    value: str


@dataclass(frozen=True)
class ChunkId:
    value: str


@dataclass(frozen=True)
class TraceId:
    value: str
```

**Step 4: Write domain entities**

```python
# backend/app/domain/entities.py
from dataclasses import dataclass, field
from datetime import datetime
from .value_objects import UserId, SessionId, DocumentId, JobId


@dataclass
class User:
    id: UserId
    email: str
    password_hash: str
    created_at: datetime


@dataclass
class ChatSession:
    id: SessionId
    user_id: UserId
    title: str
    created_at: datetime


@dataclass
class ChatMessage:
    id: str
    session_id: SessionId
    role: str
    content: str
    trace_id: str
    created_at: datetime


@dataclass
class Document:
    id: DocumentId
    user_id: UserId
    filename: str
    status: str
    created_at: datetime


@dataclass
class IngestionJob:
    id: JobId
    document_id: DocumentId
    status: str
    chunk_count: int
    created_at: datetime
    error: str | None = None

    def start(self) -> None:
        if self.status != "pending":
            raise ValueError("Can only start pending jobs")
        self.status = "processing"

    def complete(self, chunk_count: int) -> None:
        if self.status != "processing":
            raise ValueError("Can only complete processing jobs")
        self.status = "completed"
        self.chunk_count = chunk_count

    def fail(self, error: str) -> None:
        if self.status != "processing":
            raise ValueError("Can only fail processing jobs")
        self.status = "failed"
        self.error = error
```

**Step 5: Write domain exceptions**

```python
# backend/app/domain/exceptions.py
class DomainError(Exception):
    pass


class EntityNotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class IngestionError(DomainError):
    pass


class RetrievalError(DomainError):
    pass


class LLMError(DomainError):
    pass
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_domain_entities.py -v`
Expected: PASS (8 tests)

**Step 7: Commit**

```bash
git add backend/app/domain/ backend/tests/unit/test_domain_entities.py
git commit -m "feat: add domain entities and value objects"
```

---

### Task 2: Configuration Model

**Files:**
- Modify: `backend/app/config/settings.py`
- Test: `backend/tests/unit/test_config.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_config.py
import pytest
from app.config.settings import Settings


def test_settings_defaults():
    settings = Settings(
        APP_NAME="TestApp",
        APP_ENV="test",
        DEBUG=True,
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        REDIS_URL="redis://localhost/0",
        ELASTICSEARCH_URL="http://localhost:9200",
        JWT_SECRET="test-secret",
        JWT_ALGORITHM="HS256",
        JWT_EXPIRE_MINUTES=60,
        LLM_PROVIDER="openai_compatible",
        LLM_BASE_URL="https://api.example.com",
        LLM_API_KEY="test-key",
        LLM_MODEL="test-model",
        EMBEDDING_PROVIDER="ollama",
        EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
        EMBEDDING_OLLAMA_MODEL="test-embedding",
        ELASTICSEARCH_INDEX="test_index",
        EMBEDDING_DIMS=768
    )
    assert settings.APP_NAME == "TestApp"
    assert settings.EMBEDDING_DIMS == 768


def test_settings_validation_embedding_dims():
    with pytest.raises(ValueError):
        Settings(
            APP_NAME="TestApp",
            APP_ENV="test",
            DEBUG=True,
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            REDIS_URL="redis://localhost/0",
            ELASTICSEARCH_URL="http://localhost:9200",
            JWT_SECRET="test-secret",
            JWT_ALGORITHM="HS256",
            JWT_EXPIRE_MINUTES=60,
            LLM_PROVIDER="openai_compatible",
            LLM_BASE_URL="https://api.example.com",
            LLM_API_KEY="test-key",
            LLM_MODEL="test-model",
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
            EMBEDDING_OLLAMA_MODEL="test-embedding",
            ELASTICSEARCH_INDEX="test_index",
            EMBEDDING_DIMS=0
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_config.py -v`
Expected: FAIL with import errors

**Step 3: Write configuration model**

```python
# backend/app/config/settings.py
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str
    APP_ENV: str
    DEBUG: bool

    DATABASE_URL: str
    REDIS_URL: str
    ELASTICSEARCH_URL: str

    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    LLM_PROVIDER: str
    LLM_BASE_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str

    EMBEDDING_PROVIDER: str
    EMBEDDING_OLLAMA_BASE_URL: str
    EMBEDDING_OLLAMA_MODEL: str

    ELASTICSEARCH_INDEX: str
    EMBEDDING_DIMS: int

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMS must be positive")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_config.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/config/settings.py backend/tests/unit/test_config.py
git commit -m "feat: add configuration model with validation"
```

---

### Task 3: Database Models

**Files:**
- Create: `backend/app/infra/postgres/models.py`
- Test: `backend/tests/unit/test_db_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_db_models.py
from app.infra.postgres.models import User, ChatSession, ChatMessage, Document, IngestionJob


def test_user_model():
    user = User(
        id="user-123",
        email="test@example.com",
        password_hash="hashed"
    )
    assert user.id == "user-123"
    assert user.email == "test@example.com"


def test_chat_session_model():
    session = ChatSession(
        id="session-123",
        user_id="user-123",
        title="Test Session"
    )
    assert session.user_id == "user-123"
    assert session.title == "Test Session"


def test_chat_message_model():
    msg = ChatMessage(
        id="msg-123",
        session_id="session-123",
        role="user",
        content="Hello",
        trace_id="trace-123"
    )
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_document_model():
    doc = Document(
        id="doc-123",
        user_id="user-123",
        filename="test.pdf",
        status="pending"
    )
    assert doc.filename == "test.pdf"
    assert doc.status == "pending"


def test_ingestion_job_model():
    job = IngestionJob(
        id="job-123",
        document_id="doc-123",
        status="pending",
        chunk_count=0
    )
    assert job.document_id == "doc-123"
    assert job.status == "pending"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_db_models.py -v`
Expected: FAIL with import errors

**Step 3: Write database models**

```python
# backend/app/infra/postgres/models.py
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="ingestion_jobs")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_db_models.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/app/infra/postgres/models.py backend/tests/unit/test_db_models.py
git commit -m "feat: add SQLAlchemy database models"
```

---

### Task 4: Database Session Management

**Files:**
- Create: `backend/app/infra/postgres/database.py`
- Test: `backend/tests/unit/test_db_session.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_db_session.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.postgres.database import get_session_maker, get_session


@pytest.mark.asyncio
async def test_get_session():
    maker = get_session_maker("sqlite+aiosqlite:///:memory:")
    async for session in get_session(maker):
        assert isinstance(session, AsyncSession)
        break
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_db_session.py -v`
Expected: FAIL with import errors

**Step 3: Write database session**

```python
# backend/app/infra/postgres/database.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


def get_session_maker(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_session(session_maker: async_sessionmaker[AsyncSession]):
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Step 4: Add aiosqlite to dev dependencies**

Modify `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "httpx>=0.28.0",
    "aiosqlite>=0.20.0",
]
```

Run: `uv sync --extra dev`

**Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_db_session.py -v`
Expected: PASS (1 test)

**Step 6: Commit**

```bash
git add backend/app/infra/postgres/database.py backend/tests/unit/test_db_session.py pyproject.toml uv.lock
git commit -m "feat: add async database session management"
```

---

### Task 5: Health Check Endpoint

**Files:**
- Create: `backend/app/api/health.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/contract/test_health_api.py`

**Step 1: Write the failing test**

```python
# backend/tests/contract/test_health_api.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert "elasticsearch" in data
    assert "redis" in data
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/contract/test_health_api.py -v`
Expected: FAIL with import errors

**Step 3: Write health router**

```python
# backend/app/api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from elasticsearch import AsyncElasticsearch

from app.infra.postgres.database import get_session
from app.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    settings = get_settings()
    
    checks = {
        "database": "unknown",
        "elasticsearch": "unknown",
        "redis": "unknown"
    }
    
    return checks
```

**Step 4: Update main.py**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    yield
    print("Shutting down")


app = FastAPI(
    title="MuseAI",
    description="Museum AI Guide System",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/contract/test_health_api.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add backend/app/api/health.py backend/app/main.py backend/tests/contract/test_health_api.py
git commit -m "feat: add health check endpoints"
```

---

### Task 6: CI Configuration

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      
      - name: Set up Python
        run: uv python install 3.11
      
      - name: Install dependencies
        run: uv sync --extra dev
      
      - name: Run ruff
        run: uv run ruff check backend/
      
      - name: Run mypy
        run: uv run mypy backend/

  test-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      
      - name: Set up Python
        run: uv python install 3.11
      
      - name: Install dependencies
        run: uv sync --extra dev
      
      - name: Run unit tests
        run: uv run pytest backend/tests/unit -v

  test-contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      
      - name: Set up Python
        run: uv python install 3.11
      
      - name: Install dependencies
        run: uv sync --extra dev
      
      - name: Run contract tests
        run: uv run pytest backend/tests/contract -v
```

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions CI workflow"
```

---

## Phase 1: Ingestion & Retrieval Core (Week 2-3)

### Task 7: Text Chunking Service

**Files:**
- Create: `backend/app/application/chunking.py`
- Test: `backend/tests/unit/test_chunking.py`

See design document for full implementation details.

---

### Task 8: Embedding Provider

**Files:**
- Create: `backend/app/infra/providers/embedding.py`
- Test: `backend/tests/unit/test_embedding_provider.py`

See design document for full implementation details.

---

### Task 9: Elasticsearch Client

**Files:**
- Create: `backend/app/infra/elasticsearch/client.py`
- Test: `backend/tests/unit/test_es_client.py`

See design document for full implementation details.

---

### Task 10: RRF Fusion Algorithm

**Files:**
- Create: `backend/app/application/retrieval.py`
- Test: `backend/tests/unit/test_rag_fusion.py`

See design document for full implementation details.

---

### Task 11: Document Upload API

**Files:**
- Create: `backend/app/api/documents.py`
- Create: `backend/app/application/document_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/contract/test_documents_api.py`

See design document for full implementation details.

---

## Phase 2: Multi-turn & Streaming (Week 4-5)

### Task 12: LLM Provider

**Files:**
- Create: `backend/app/infra/providers/llm.py`
- Test: `backend/tests/unit/test_llm_provider.py`

See design document for full implementation details.

---

### Task 13: Chat Session API

**Files:**
- Create: `backend/app/api/chat.py`
- Create: `backend/app/application/chat_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/contract/test_chat_api.py`

See design document for full implementation details.

---

### Task 14: SSE Streaming Endpoint

**Files:**
- Modify: `backend/app/api/chat.py`
- Test: `backend/tests/contract/test_sse_events.py`

See design document for full implementation details.

---

### Task 15: Multi-turn State Machine

**Files:**
- Create: `backend/app/workflows/multi_turn.py`
- Test: `backend/tests/unit/test_state_machine.py`

See design document for full implementation details.

---

## Phase 3: Integration & Deployment (Week 6)

### Task 16: Query Transform Strategies

**Files:**
- Create: `backend/app/workflows/query_transform.py`
- Test: `backend/tests/unit/test_query_transform.py`

See design document for full implementation details.

---

### Task 17: Redis Cache Layer

**Files:**
- Create: `backend/app/infra/redis/cache.py`
- Test: `backend/tests/unit/test_redis_cache.py`

See design document for full implementation details.

---

### Task 18: Authentication API

**Files:**
- Create: `backend/app/api/auth.py`
- Create: `backend/app/application/auth_service.py`
- Test: `backend/tests/contract/test_auth_api.py`

See design document for full implementation details.

---

### Task 19: Integration Tests

**Files:**
- Create: `backend/tests/integration/test_ingestion_flow.py`
- Create: `backend/tests/integration/test_retrieval_flow.py`

See design document for full implementation details.

---

### Task 20: E2E Tests

**Files:**
- Create: `backend/tests/e2e/test_full_journey.py`

See design document for full implementation details.

---

## Summary

| Phase | Tasks | Duration | Key Deliverables |
|-------|-------|----------|------------------|
| Phase 0 | 1-6 | Week 1 | Project scaffold, domain models, health endpoints, CI |
| Phase 1 | 7-11 | Week 2-3 | Chunking, embedding, ES client, RRF fusion, document API |
| Phase 2 | 12-15 | Week 4-5 | LLM provider, chat API, SSE streaming, state machine |
| Phase 3 | 16-20 | Week 6 | Query transform, cache, auth, integration tests, E2E |

**Total: 20 Tasks across 6 Weeks**
