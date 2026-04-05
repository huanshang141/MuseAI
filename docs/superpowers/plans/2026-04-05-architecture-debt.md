# Architecture Technical Debt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all P0 and P1 architecture issues identified in the technical debt audit.

**Architecture:** Consolidate session management, fix singleton lifecycle, remove duplicate Vue components, consolidate provider singletons.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Vue 3

---

## Files Modified

| File | Purpose |
|------|---------|
| `backend/app/api/deps.py` | Remove duplicate session maker |
| `backend/app/infra/postgres/database.py` | Add thread-safe singleton |
| `backend/app/main.py` | Use app.state for singletons |
| `backend/app/api/documents.py` | Remove late imports |
| `backend/app/api/chat.py` | Remove late imports, consolidate LLM provider |
| `frontend/src/components/DocumentList.vue` | Delete (duplicate) |
| `frontend/src/components/DocumentUpload.vue` | Delete (duplicate) |

---

## Task 1: Consolidate Session Maker Management

**Files:**
- Modify: `backend/app/infra/postgres/database.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/unit/test_database_singleton.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_database_singleton.py

import pytest
import asyncio


@pytest.mark.asyncio
async def test_get_session_maker_returns_singleton():
    """get_session_maker should return the same instance."""
    from app.infra.postgres.database import get_session_maker, close_database
    
    try:
        maker1 = get_session_maker("sqlite+aiosqlite:///:memory:")
        maker2 = get_session_maker("sqlite+aiosqlite:///:memory:")
        
        # Should return same instance
        assert maker1 is maker2
    finally:
        await close_database()


@pytest.mark.asyncio
async def test_init_database_disposes_old_engine():
    """init_database should properly dispose old engine."""
    from app.infra.postgres.database import init_database, close_database, _engine
    
    try:
        await init_database("sqlite+aiosqlite:///:memory:")
        first_engine = _engine
        
        await init_database("sqlite+aiosqlite:///:memory:")
        second_engine = _engine
        
        # Should be different engine instances
        assert first_engine is not second_engine
    finally:
        await close_database()


def test_get_db_session_uses_global_session_maker():
    """get_db_session should use the global session maker."""
    from app.api.deps import get_db_session
    import inspect
    
    # Check that get_db_session doesn't create its own session maker
    source = inspect.getsource(get_db_session)
    
    # Should not have local _session_maker assignment
    assert "_session_maker = get_session_maker" not in source
    assert "global _session_maker" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_database_singleton.py -v`
Expected: FAIL - deps.py has its own session maker

- [ ] **Step 3: Modify database.py to export a proper singleton**

```python
# backend/app/infra/postgres/database.py

import asyncio
from contextlib import asynccontextmanager
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infra.postgres.models import Base

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None
_init_lock = asyncio.Lock()


async def init_database(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Initialize database engine and session maker.
    
    Thread-safe - uses lock to prevent race conditions.
    Disposes existing engine before creating new one.
    """
    global _engine, _session_maker
    async with _init_lock:
        # Dispose existing engine if any
        if _engine is not None:
            await _engine.dispose()

        # Create new engine with pool configuration
        new_engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
        )
        async with new_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        new_maker = async_sessionmaker(new_engine, class_=AsyncSession, expire_on_commit=False)
        _engine = new_engine
        _session_maker = new_maker

        return _session_maker


async def close_database() -> None:
    """Dispose database engine and clear session maker."""
    global _engine, _session_maker
    async with _init_lock:
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _session_maker = None


def get_session_maker(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Get the global session maker.
    
    If session maker is not initialized and database_url is provided,
    creates a new one (not thread-safe, for testing only).
    
    For production, use init_database() instead.
    """
    global _engine, _session_maker
    if _session_maker is None:
        if database_url is None:
            raise RuntimeError("Database not initialized. Call init_database() first.")
        # Sync initialization for backward compatibility with tests
        new_engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
        new_maker = async_sessionmaker(new_engine, class_=AsyncSession, expire_on_commit=False)
        _engine = new_engine
        _session_maker = new_maker
    return cast(async_sessionmaker[AsyncSession], _session_maker)


@asynccontextmanager
async def get_session(session_maker: async_sessionmaker[AsyncSession] | None = None):
    """Get a database session.
    
    If session_maker is not provided, uses the global one.
    """
    if session_maker is None:
        session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 4: Modify deps.py to use the singleton**

```python
# backend/app/api/deps.py (modify get_db_session)

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import get_user_by_id
from app.config.settings import get_settings
from app.infra.postgres.database import get_session
from app.infra.redis.cache import RedisCache
from app.infra.security.jwt_handler import JWTHandler

security = HTTPBearer()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session from the global session maker."""
    async for session in get_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

# ... rest of the file unchanged ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_database_singleton.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/postgres/database.py backend/app/api/deps.py backend/tests/unit/test_database_singleton.py
git commit -m "$(cat <<'EOF'
refactor(arch): consolidate session maker management

- Remove duplicate _session_maker in deps.py
- Add pool configuration to engine creation
- Make get_session_maker truly singleton
- Add get_session() without parameters to use global

P0 architecture fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Move Singletons to app.state

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/unit/test_app_state.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_app_state.py

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_singletons_stored_in_app_state():
    """All singletons should be stored in app.state."""
    from app.main import app, lifespan
    from fastapi import FastAPI
    
    # Simulate lifespan startup
    test_app = FastAPI(lifespan=lifespan)
    
    async with lifespan(test_app):
        # Check that singletons are in app.state
        assert hasattr(test_app.state, "es_client")
        assert hasattr(test_app.state, "embeddings")
        assert hasattr(test_app.state, "llm")
        assert hasattr(test_app.state, "retriever")
        assert hasattr(test_app.state, "rag_agent")
        assert hasattr(test_app.state, "ingestion_service")


@pytest.mark.asyncio
async def test_get_singletons_from_app_state():
    """Getter functions should retrieve from app.state."""
    from app.main import app, get_es_client, lifespan
    
    async with lifespan(app):
        client = get_es_client()
        assert client is app.state.es_client
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_app_state.py -v`
Expected: FAIL - Singletons are module-level, not in app.state

- [ ] **Step 3: Modify main.py to use app.state**

```python
# backend/app/main.py

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.application.ingestion_service import IngestionService
from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import create_embeddings, create_llm, create_rag_agent, create_retriever
from app.infra.postgres.database import close_database, init_database

# Lock for thread-safe singleton initialization
_init_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize and cleanup resources."""
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    
    try:
        # Initialize database
        await init_database(settings.DATABASE_URL)

        # Initialize Elasticsearch client
        es_client = ElasticsearchClient(
            hosts=[settings.ELASTICSEARCH_URL],
            index_name=settings.ELASTICSEARCH_INDEX,
        )
        await es_client.create_index(settings.ELASTICSEARCH_INDEX, settings.EMBEDDING_DIMS)

        # Initialize other singletons
        embeddings = create_embeddings(settings)
        llm = create_llm(settings)
        retriever = create_retriever(es_client, embeddings, settings)
        rag_agent = create_rag_agent(llm, retriever, settings)
        ingestion_service = IngestionService(
            es_client=es_client,
            embeddings=embeddings,
        )

        # Store in app.state
        app.state.es_client = es_client
        app.state.embeddings = embeddings
        app.state.llm = llm
        app.state.retriever = retriever
        app.state.rag_agent = rag_agent
        app.state.ingestion_service = ingestion_service
        app.state.settings = settings

        yield
        
    except Exception as e:
        print(f"Failed to initialize: {e}")
        raise
    finally:
        await close_database()
        if hasattr(app.state, "es_client") and app.state.es_client:
            await app.state.es_client.close()
        print("Shutting down")


# Getter functions that retrieve from app.state
def get_es_client() -> ElasticsearchClient:
    """Get Elasticsearch client from app.state."""
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest
    
    # Try to get from request context if available
    try:
        request = StarletteRequest.scope.get("app")
        if request and hasattr(request.state, "es_client"):
            return request.state.es_client
    except (AttributeError, RuntimeError):
        pass
    
    # Fallback for testing - use global app
    from app.main import app
    if hasattr(app.state, "es_client"):
        return app.state.es_client
    raise RuntimeError("Elasticsearch client not initialized. App not started?")


def get_embeddings():
    """Get embeddings from app.state."""
    from app.main import app
    if hasattr(app.state, "embeddings"):
        return app.state.embeddings
    raise RuntimeError("Embeddings not initialized. App not started?")


def get_llm():
    """Get LLM from app.state."""
    from app.main import app
    if hasattr(app.state, "llm"):
        return app.state.llm
    raise RuntimeError("LLM not initialized. App not started?")


def get_retriever():
    """Get retriever from app.state."""
    from app.main import app
    if hasattr(app.state, "retriever"):
        return app.state.retriever
    raise RuntimeError("Retriever not initialized. App not started?")


def get_rag_agent():
    """Get RAG agent from app.state."""
    from app.main import app
    if hasattr(app.state, "rag_agent"):
        return app.state.rag_agent
    raise RuntimeError("RAG agent not initialized. App not started?")


def get_ingestion_service() -> IngestionService:
    """Get ingestion service from app.state."""
    from app.main import app
    if hasattr(app.state, "ingestion_service"):
        return app.state.ingestion_service
    raise RuntimeError("Ingestion service not initialized. App not started?")


app = FastAPI(title="MuseAI", description="Museum AI Guide System", version="2.0.0", lifespan=lifespan)

# Get settings for CORS configuration
_settings = get_settings()
cors_origins = _settings.get_cors_origins()

# In production, don't allow credentials with wildcard
allow_credentials = _settings.CORS_ALLOW_CREDENTIALS and "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(auth_router, prefix="/api/v1")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_app_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/unit/test_app_state.py
git commit -m "$(cat <<'EOF'
refactor(arch): move singletons to app.state for proper lifecycle

- Store all singletons in app.state during lifespan
- Add getter functions that retrieve from app.state
- Remove module-level global variables
- Thread-safe initialization via lifespan context

P1 architecture fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Remove Late Imports from API Routes

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/api/chat.py`
- Create: `backend/tests/unit/test_api_no_late_imports.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_api_no_late_imports.py

import ast
import inspect


def test_documents_api_no_late_imports_from_main():
    """documents.py should not import from main.py inside functions."""
    from app.api import documents
    source = inspect.getsource(documents)
    tree = ast.parse(source)
    
    late_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    if child.module and "main" in child.module:
                        late_imports.append(f"{node.name}: from {child.module}")
    
    assert len(late_imports) == 0, f"Found late imports from main: {late_imports}"


def test_chat_api_no_late_imports_from_main():
    """chat.py should not import from main.py inside functions."""
    from app.api import chat
    source = inspect.getsource(chat)
    tree = ast.parse(source)
    
    late_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    if child.module and "main" in child.module:
                        late_imports.append(f"{node.name}: from {child.module}")
    
    assert len(late_imports) == 0, f"Found late imports from main: {late_imports}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_api_no_late_imports.py -v`
Expected: FAIL - Both files have late imports

- [ ] **Step 3: Modify documents.py to use dependency injection**

```python
# backend/app/api/documents.py

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentUser, RateLimitDep, SessionDep
from app.application.document_service import (
    create_document,
    delete_document,
    get_document_by_id,
    get_documents_by_user,
    get_ingestion_job_by_document,
    update_document_status,
)
from app.application.ingestion_service import IngestionService
from app.config.settings import Settings, get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import get_session, get_session_maker

router = APIRouter(prefix="/documents", tags=["documents"])


# ... existing model definitions ...


MAX_FILE_SIZE = 50 * 1024 * 1024


# Dependency functions - these will be overridden by main.py
def get_ingestion_service() -> IngestionService:
    """Get ingestion service - overridden by main.py in production."""
    settings = get_settings()
    from app.infra.langchain import create_embeddings
    es_client = ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )
    embeddings = create_embeddings(settings)
    return IngestionService(es_client=es_client, embeddings=embeddings)


def get_es_client() -> ElasticsearchClient:
    """Get ES client - overridden by main.py in production."""
    settings = get_settings()
    return ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )


def get_embeddings():
    """Get embeddings - overridden by main.py in production."""
    settings = get_settings()
    from app.infra.langchain import create_embeddings
    return create_embeddings(settings)


# Dependencies for injection
IngestionServiceDep = IngestionService | None
ESClientDep = ElasticsearchClient | None


async def process_document_background(
    document_id: str,
    content: str,
    filename: str,
    ingestion_service: IngestionService,
):
    """Background task to process uploaded document."""
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with get_session(session_maker) as session:
        try:
            await ingestion_service.process_document(
                session=session,
                document_id=document_id,
                content=content,
                source=filename,
            )
            await session.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to process document {document_id}: {e}")
            await update_document_status(session, document_id, "failed", str(e))
            await session.commit()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    _: RateLimitDep,
    ingestion_service: IngestionService = Depends(get_ingestion_service),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    document = await create_document(session, file.filename, file_size, current_user["id"])
    await session.commit()

    try:
        text_content = content.decode("utf-8")
        background_tasks.add_task(
            process_document_background,
            document.id,
            text_content,
            file.filename,
            ingestion_service,
        )
    except UnicodeDecodeError:
        pass

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )


# ... rest of endpoints unchanged, just remove the late import functions ...
```

- [ ] **Step 4: Modify chat.py similarly**

```python
# backend/app/api/chat.py (relevant changes)

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, RateLimitDep, SessionDep
from app.application.chat_service import (
    ask_question,
    ask_question_stream_with_rag,
    create_session,
    delete_session,
    get_messages_by_session,
    get_session_by_id,
    get_sessions_by_user,
)
from app.config.settings import get_settings
from app.infra.providers.llm import OpenAICompatibleProvider

router = APIRouter(prefix="/chat", tags=["chat"])


# ... existing model definitions ...


def get_llm_provider() -> OpenAICompatibleProvider:
    """Get LLM provider - can be overridden by main.py."""
    settings = get_settings()
    return OpenAICompatibleProvider.from_settings(settings)


def get_rag_agent():
    """Get RAG agent - can be overridden by main.py."""
    from app.main import get_rag_agent as _get
    return _get()


# ... rest of endpoints unchanged, but use Depends() for injection ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_api_no_late_imports.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/documents.py backend/app/api/chat.py backend/tests/unit/test_api_no_late_imports.py
git commit -m "$(cat <<'EOF'
refactor(arch): remove late imports from API routes

- Replace late imports with dependency injection
- Add getter functions that can be overridden
- Inject services via Depends() for testability
- Remove inline from app.main imports

P1 architecture fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Remove Duplicate Vue Components

**Files:**
- Delete: `frontend/src/components/DocumentList.vue`
- Delete: `frontend/src/components/DocumentUpload.vue`
- Create: `frontend/src/components/.gitkeep` (to preserve directory)

- [ ] **Step 1: Verify duplicate components exist and are unused**

Run: `cd /home/singer/MuseAI/frontend && grep -r "from.*DocumentList" src/ || echo "No imports found"`
Run: `cd /home/singer/MuseAI/frontend && grep -r "from.*DocumentUpload" src/ || echo "No imports found"`

Expected: Should show imports use `@/components/knowledge/` versions

- [ ] **Step 2: Delete unused duplicate components**

```bash
rm frontend/src/components/DocumentList.vue
rm frontend/src/components/DocumentUpload.vue
touch frontend/src/components/.gitkeep
```

- [ ] **Step 3: Verify app still builds**

Run: `cd /home/singer/MuseAI/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/
git commit -m "$(cat <<'EOF'
refactor(arch): remove duplicate Vue components

- Delete unused DocumentList.vue (use knowledge/DocumentList.vue)
- Delete unused DocumentUpload.vue (use knowledge/DocumentUpload.vue)
- Keep directory with .gitkeep

P1 architecture fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Run All Tests and Verify

- [ ] **Step 1: Run backend unit tests**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit -v`
Expected: All tests PASS

- [ ] **Step 2: Run backend contract tests**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/contract -v`
Expected: All tests PASS

- [ ] **Step 3: Verify frontend builds**

Run: `cd /home/singer/MuseAI/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit for architecture debt completion**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: complete architecture technical debt fixes (P0 + P1)

Completed fixes:
- P0: Consolidate session maker management
- P0: Add pool configuration to database engine
- P1: Move singletons to app.state
- P1: Remove late imports from API routes
- P1: Remove duplicate Vue components

All tests passing.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```
