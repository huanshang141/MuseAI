# Technical Debt Phase 2+ Design Document

**Date**: 2026-04-06
**Status**: Approved
**Scope**: P2/P3 technical debt remediation and linter warning cleanup

---

## Executive Summary

This document outlines the implementation plan for remaining technical debt after P0/P1 issues have been resolved. The approach follows a phased strategy to minimize risk and allow flexible integration into sprint planning.

### Current Status

| Category | P0/P1 | P2/P3 | New Issues |
|----------|-------|-------|------------|
| Security | ✅ Fixed | 5 issues | 0 |
| Architecture | ✅ Fixed | 6 issues | 0 |
| Performance | ✅ Fixed | 5 issues | 0 |
| Test Quality | ✅ Fixed | 6 issues | 0 |
| Linter | - | - | 20+ warnings |

### Test Coverage: 79.54% (exceeds 70% threshold)

---

## Phase 1: Linter Warning Cleanup

**Goal**: Achieve clean `ruff check` output with zero warnings.

**Duration**: ~30 minutes

### Issues to Fix

#### B904: Exception Chain Missing (6 occurrences)

**Location**: `backend/app/infra/elasticsearch/client.py`

**Problem**: `raise` in except clause without `from` keyword loses stack trace.

**Fix Pattern**:
```python
# Before
except (ApiError, TransportError) as e:
    logger.error(f"Failed to create index: {repr(e)}")
    raise RetrievalError("Failed to create index")

# After
except (ApiError, TransportError) as e:
    logger.error(f"Failed to create index: {repr(e)}")
    raise RetrievalError("Failed to create index") from e
```

**Files to Modify**:
- `backend/app/infra/elasticsearch/client.py`: Lines 72, 81, 100, 111, 121

#### B023: Closure Variable Not Bound (1 occurrence)

**Location**: `backend/app/application/ingestion_service.py:87`

**Problem**: `semaphore` variable in nested function is not bound at definition time.

**Fix**:
```python
# Before
async def index_with_semaphore(doc: dict) -> None:
    async with semaphore:
        await self.es_client.index_chunk(doc)

# After
async def index_with_semaphore(doc: dict, sem: asyncio.Semaphore = semaphore) -> None:
    async with sem:
        await self.es_client.index_chunk(doc)
```

Or capture via functools.partial.

#### B905: zip() Without strict (1 occurrence)

**Location**: `backend/app/application/ingestion_service.py:68`

**Fix**:
```python
# Before
for chunk, embedding in zip(chunks, embeddings_list):

# After
for chunk, embedding in zip(chunks, embeddings_list, strict=True):
```

#### Import Issues (multiple files)

- I001: Import block unsorted
- F401: Unused imports
- F811: Redundant imports

**Fix**: Run `ruff --fix` for auto-fixable issues, manually fix remaining.

### Success Criteria

- `uv run ruff check backend/` returns exit code 0
- All tests still pass

---

## Phase 2: P2 Security Debt

**Goal**: Address medium-priority security concerns.

**Duration**: ~2 hours

### 2.1: Input Validation for Chat Fields

**Problem**: No length limits on `title` and `message` fields.

**Impact**: Storage abuse, log injection, DoS through large payloads.

**Solution**:

```python
# backend/app/api/chat.py

from pydantic import Field

class CreateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)

class AskRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=10000)
```

**Tests**: Add validation tests in `test_chat_api.py`.

### 2.2: Password Special Character Requirement

**Problem**: Password validation doesn't require special characters.

**Solution**:

```python
# backend/app/api/auth.py

import re

SPECIAL_CHAR_PATTERN = re.compile(r'[!@#$%^&*(),.?":{}|<>]')

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)

    @field_validator('password')
    def validate_password_strength(cls, v):
        if not SPECIAL_CHAR_PATTERN.search(v):
            raise ValueError('Password must contain at least one special character')
        return v
```

### 2.3: Health Endpoint Security

**Problem**: `/ready` exposes infrastructure details to unauthenticated users.

**Solution**:

Option A: Require authentication
```python
@router.get("/ready")
async def readiness_check(current_user: CurrentUser, session: SessionDep):
    # ... existing checks
```

Option B: Simple status only (recommended for public health checks)
```python
@router.get("/ready")
async def readiness_check():
    return {"status": "ok"}

@router.get("/ready/detail")
async def detailed_readiness(current_user: CurrentUser, session: SessionDep):
    # ... existing detailed checks
```

---

## Phase 3: P2 Architecture Debt

**Goal**: Improve code maintainability and testability.

**Duration**: ~4 hours

### 3.1: Settings Singleton Caching

**Problem**: `get_settings()` creates new instance on every call.

**Solution**:

```python
# backend/app/config/settings.py

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

Or use `@lru_cache`:
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

### 3.2: RRF Implementation Consolidation

**Problem**: RRF algorithm exists in both `application/retrieval.py` and `infra/langchain/retrievers.py`.

**Solution**: Move RRF to domain service, inject into retriever.

```python
# backend/app/domain/services/retrieval.py

def rrf_fusion(results: list[list], k: int = 60) -> list:
    """Reciprocal Rank Fusion algorithm."""
    # ... implementation

# backend/app/infra/langchain/retrievers.py imports from domain
from app.domain.services.retrieval import rrf_fusion
```

### 3.3: Protocol Interfaces for External Dependencies

**Problem**: `LLMProvider` protocol exists but not used consistently.

**Solution**: Define protocols for all external dependencies:

```python
# backend/app/domain/protocols.py

from typing import Protocol

class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> str: ...
    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]: ...

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

class VectorStore(Protocol):
    async def search(self, query: str, top_k: int) -> list[dict]: ...
    async def index(self, documents: list[dict]) -> None: ...
```

---

## Phase 4: P2 Test Quality Debt

**Goal**: Improve test reliability and coverage of edge cases.

**Duration**: ~4 hours

### 4.1: Service-Level Tests with Real Database

**Problem**: Tests use MagicMock for database, not verifying actual SQL.

**Solution**: Use SQLite in-memory for service tests:

```python
# backend/tests/conftest.py

@pytest.fixture
async def real_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    async with async_session() as session:
        yield session
    await engine.dispose()
```

### 4.2: Concurrent Access Tests

**Problem**: No tests for behavior under concurrent access.

**Solution**:

```python
# backend/tests/unit/test_concurrent_access.py

@pytest.mark.asyncio
async def test_concurrent_document_creation():
    """Test that concurrent document creation doesn't cause race conditions."""
    tasks = [
        create_document(session, f"doc{i}.txt", 100, "user-123")
        for i in range(10)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Verify all succeeded and no duplicates
```

### 4.3: E2E Test Mock Strategy

**Problem**: E2E tests require live ES, Ollama, PostgreSQL.

**Solution**: Add mock mode for CI:

```python
# backend/tests/e2e/conftest.py

@pytest.fixture
def mock_external_services(monkeypatch):
    if os.getenv("CI") == "true":
        # Use mocks in CI
        monkeypatch.setattr("app.infra.elasticsearch.client.ElasticsearchClient", MockESClient)
        monkeypatch.setattr("app.infra.langchain.embeddings.CustomOllamaEmbeddings", MockEmbeddings)
```

---

## Implementation Order

```
Phase 1 (Immediate)
    ↓
Linter Cleanup (~30 min)
    ↓
Phase 2 (Next Sprint)
    ↓
P2 Security (~2 hrs)
    ↓
Phase 3 (Following Sprint)
    ↓
P2 Architecture (~4 hrs)
    ↓
Phase 4 (When Test Coverage Drops)
    ↓
P2 Test Quality (~4 hrs)
```

---

## P3 Backlog (Low Priority)

These items are documented but not scheduled:

1. **Debug Mode Default** - Already fixed (default is False)
2. **Email Case Sensitivity** - Normalize to lowercase
3. **Content Security Policy** - Add CSP headers
4. **Large File chat_service.py** - Consider splitting
5. **Frontend State via Module Refs** - Consider Pinia migration
6. **Rate Limiting Algorithm** - Implement sliding window

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Ruff warnings | 20+ | 0 |
| Test coverage | 79.54% | ≥ 75% |
| P0 issues | 0 | 0 |
| P1 issues | 0 | 0 |
| P2 issues | 22 | 0 (after phases) |

---

## Appendices

### A. Files Modified Summary

**Phase 1:**
- `backend/app/infra/elasticsearch/client.py`
- `backend/app/application/ingestion_service.py`
- Various test files (import cleanup)

**Phase 2:**
- `backend/app/api/chat.py`
- `backend/app/api/auth.py`
- `backend/app/api/health.py`

**Phase 3:**
- `backend/app/config/settings.py`
- `backend/app/domain/services/retrieval.py` (new)
- `backend/app/infra/langchain/retrievers.py`
- `backend/app/domain/protocols.py` (new)

**Phase 4:**
- `backend/tests/conftest.py`
- `backend/tests/unit/test_concurrent_access.py` (new)
- `backend/tests/e2e/conftest.py`

### B. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Run full test suite after each change |
| Performance regression | Benchmark before/after for Phase 3 changes |
| Import cycles (Phase 3) | Use late imports or dependency injection |

---

**Document Version**: 1.0
**Last Updated**: 2026-04-06
**Author**: Claude Opus 4.6
