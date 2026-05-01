# Test Suite Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the backend test suite from 115 files/~24,500 lines to ~65 files/~17,000 lines by deleting trivial tests, merging related files, and extracting shared fixtures.

**Architecture:** Create a conftest hierarchy (global → unit/contract) with shared fixtures and mock factories. Delete low-value tests, merge related test files, and refactor remaining tests to use shared infrastructure.

**Tech Stack:** pytest, unittest.mock (AsyncMock, MagicMock), SQLAlchemy async, FastAPI TestClient

---

## File Map

### Files to Create
- `backend/tests/conftest.py` — global shared fixtures (db_session, auth_token, admin_token, mock_redis)
- `backend/tests/unit/conftest.py` — unit-specific fixtures (mock_db_session, mock_rag_agent, mock_auth_stack)
- `backend/tests/fixtures/mock_factories.py` — replace unused mock_providers.py with factory functions

### Files to Modify
- `backend/tests/contract/conftest.py` — enhance with shared fixtures from global
- `backend/tests/unit/test_auth_service.py` — delete duplicate test, parametrize password tests
- `backend/tests/unit/test_chat_integration.py` — delete 2 trivial tests
- `backend/tests/unit/test_api_state_dependencies.py` — delete 2 hasattr tests
- `backend/tests/unit/test_redis_singleton.py` — delete 1 duplicate test

### Files to Delete (entire files)
- `backend/tests/unit/test_pagination.py`
- `backend/tests/unit/test_debt_marker_scan_script.py`
- `backend/tests/unit/test_verify_local_quality_script.py`
- `backend/tests/unit/test_db_session.py`
- `backend/tests/unit/test_db_models.py`
- `backend/tests/unit/test_ci_workflow_contract.py`
- `backend/tests/unit/test_main.py` (source inspection tests only)
- `backend/tests/architecture/` (entire directory)
- `backend/tests/performance/` (entire directory)
- `backend/tests/fixtures/mock_providers.py` (replaced by mock_factories.py)

### Files to Create via Merge
- `backend/tests/unit/test_tts_core.py` (from 4 files)
- `backend/tests/unit/test_tts_advanced.py` (from 4 files)
- `backend/tests/unit/test_tour_services.py` (from 4 files)
- `backend/tests/unit/test_tour_chat.py` (from 3 files)
- `backend/tests/unit/test_chat_services.py` (from 3 files)
- `backend/tests/unit/test_chat_streaming.py` (from 4 files)
- `backend/tests/unit/test_sse.py` (from 2 files)
- `backend/tests/unit/test_retrieval.py` (from 4 files)
- `backend/tests/unit/test_indexing.py` (from 4 files)
- `backend/tests/unit/test_database.py` (from 1 file, simplified)
- `backend/tests/unit/test_deps.py` (from 5 files)
- `backend/tests/unit/test_imports.py` (from 2 files)

---

## Task 1: Create Global conftest.py

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create the global conftest with shared fixtures**

```python
"""Global shared fixtures for all tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """SQLite in-memory async session for contract/integration tests."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine(TEST_DATABASE_URL)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def auth_token():
    """Generate a valid JWT token for test user."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.jwt_secret or "test-secret-key-min-32-chars-long!!",
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )
    return jwt_handler.create_token("user-123")


@pytest.fixture
def admin_token():
    """Generate a valid JWT token for admin user."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.jwt_secret or "test-secret-key-min-32-chars-long!!",
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )
    return jwt_handler.create_token("admin-123")


@pytest.fixture
def mock_redis():
    """Unified Redis mock with all common methods."""
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.incr = AsyncMock(return_value=1)
    redis.setex = AsyncMock()
    redis.close = AsyncMock()
    redis.check_rate_limit = AsyncMock(return_value=True)
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    redis.get_guest_session = AsyncMock(return_value=None)
    redis.set_guest_session = AsyncMock()
    return redis
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `uv run pytest backend/tests/unit backend/tests/contract -q --tb=short 2>&1 | tail -5`
Expected: `1008 passed` (or similar, no failures)

---

## Task 2: Create Unit conftest.py

**Files:**
- Create: `backend/tests/unit/conftest.py`

- [ ] **Step 1: Create unit-specific conftest**

```python
"""Unit test fixtures."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db_session():
    """Mock DB session with execute returning a configurable chat_session."""
    session = AsyncMock()
    chat_session = MagicMock()
    chat_session.id = "session-123"
    chat_session.user_id = "user-123"
    result = MagicMock()
    result.scalar_one_or_none.return_value = chat_session
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def mock_rag_agent():
    """Mock RAG agent with LLM and prompt_gateway."""
    agent = MagicMock()
    agent.prompt_gateway = None
    agent.ainvoke = AsyncMock(return_value={"output": "test response"})
    return agent


@pytest.fixture
def mock_auth_stack():
    """Returns (redis, jwt, credentials, request) for auth dependency tests."""
    redis = MagicMock()
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    jwt = MagicMock()
    jwt.get_jti = MagicMock(return_value="jti-123")
    credentials = MagicMock()
    credentials.credentials = "test-token"
    request = MagicMock()
    request.app.state.redis_cache = MagicMock()
    request.app.state.redis_cache.is_token_blacklisted = AsyncMock(return_value=False)
    return redis, jwt, credentials, request
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `uv run pytest backend/tests/unit -q --tb=short 2>&1 | tail -5`
Expected: no failures

---

## Task 3: Create Mock Factories

**Files:**
- Create: `backend/tests/fixtures/mock_factories.py`
- Delete: `backend/tests/fixtures/mock_providers.py`

- [ ] **Step 1: Create mock_factories.py**

```python
"""Shared mock factory functions for tests."""
from unittest.mock import AsyncMock, MagicMock


def make_mock_db_session(chat_session=None):
    """Return a mock DB session with configurable chat_session return value."""
    session = AsyncMock()
    if chat_session is None:
        chat_session = MagicMock()
        chat_session.id = "session-123"
        chat_session.user_id = "user-123"
    result = MagicMock()
    result.scalar_one_or_none.return_value = chat_session
    session.execute = AsyncMock(return_value=result)
    return session


def make_mock_redis(**overrides):
    """Return a configured Redis mock. Override any method via kwargs."""
    redis = MagicMock()
    defaults = {
        "set": AsyncMock(return_value=True),
        "get": AsyncMock(return_value=None),
        "delete": AsyncMock(return_value=True),
        "exists": AsyncMock(return_value=0),
        "incr": AsyncMock(return_value=1),
        "setex": AsyncMock(),
        "close": AsyncMock(),
        "check_rate_limit": AsyncMock(return_value=True),
        "is_token_blacklisted": AsyncMock(return_value=False),
    }
    for attr, mock in defaults.items():
        setattr(redis, attr, overrides.get(attr, mock))
    return redis


def make_mock_rag_agent(**overrides):
    """Return a mock RAG agent. Override any attribute via kwargs."""
    agent = MagicMock()
    agent.prompt_gateway = overrides.get("prompt_gateway", None)
    agent.ainvoke = AsyncMock(return_value=overrides.get("output", {"output": "test response"}))
    return agent


def make_mock_auth_stack(user_id="user-123"):
    """Return (redis, jwt, credentials, request) tuple for auth tests."""
    redis = MagicMock()
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    jwt = MagicMock()
    jwt.get_jti = MagicMock(return_value="jti-123")
    credentials = MagicMock()
    credentials.credentials = "test-token"
    request = MagicMock()
    request.app.state.redis_cache = redis
    return redis, jwt, credentials, request
```

- [ ] **Step 2: Delete mock_providers.py**

```bash
rm backend/tests/fixtures/mock_providers.py
```

- [ ] **Step 3: Verify tests still pass**

Run: `uv run pytest backend/tests/unit backend/tests/contract -q --tb=short 2>&1 | tail -5`
Expected: no failures

---

## Task 4: Delete Trivial Test Files

**Files:**
- Delete: `backend/tests/unit/test_pagination.py`
- Delete: `backend/tests/unit/test_debt_marker_scan_script.py`
- Delete: `backend/tests/unit/test_verify_local_quality_script.py`
- Delete: `backend/tests/unit/test_db_session.py`
- Delete: `backend/tests/unit/test_db_models.py`
- Delete: `backend/tests/unit/test_ci_workflow_contract.py`

- [ ] **Step 1: Delete all trivial test files**

```bash
rm backend/tests/unit/test_pagination.py \
   backend/tests/unit/test_debt_marker_scan_script.py \
   backend/tests/unit/test_verify_local_quality_script.py \
   backend/tests/unit/test_db_session.py \
   backend/tests/unit/test_db_models.py \
   backend/tests/unit/test_ci_workflow_contract.py
```

- [ ] **Step 2: Verify tests still pass**

Run: `uv run pytest backend/tests/unit -q --tb=short 2>&1 | tail -5`
Expected: ~960 passed (reduced from 1008, ~48 tests removed)

---

## Task 5: Delete Architecture and Performance Directories

**Files:**
- Delete: `backend/tests/architecture/` (entire directory)
- Delete: `backend/tests/performance/` (entire directory)

- [ ] **Step 1: Remove both directories**

```bash
rm -rf backend/tests/architecture backend/tests/performance
```

- [ ] **Step 2: Verify tests still pass**

Run: `uv run pytest backend/tests/unit backend/tests/contract -q --tb=short 2>&1 | tail -5`
Expected: same count as Task 4 (architecture/performance weren't in the default test run)

---

## Task 6: Delete Tests Within Files

**Files:**
- Modify: `backend/tests/unit/test_chat_integration.py`
- Modify: `backend/tests/unit/test_api_state_dependencies.py`
- Modify: `backend/tests/unit/test_auth_service.py`
- Modify: `backend/tests/unit/test_redis_singleton.py`

- [ ] **Step 1: Prune test_chat_integration.py — delete 2 trivial tests**

Read `backend/tests/unit/test_chat_integration.py`, then delete the two existence-check tests (`test_get_rag_agent_function_exists` and `test_chat_service_uses_rag_agent`). Keep only `test_ask_question_with_rag_calls_agent`.

- [ ] **Step 2: Prune test_api_state_dependencies.py — delete 2 hasattr tests**

Read `backend/tests/unit/test_api_state_dependencies.py`, then delete `test_rag_agent_dependency_in_deps` and `test_llm_provider_dependency_in_deps`. Keep the two source-inspection tests.

- [ ] **Step 3: Prune test_auth_service.py — delete duplicate, parametrize password tests**

Read `backend/tests/unit/test_auth_service.py`. Delete `test_valid_password_complex` (near-duplicate of `test_valid_password_accepted`). Replace the 4 individual password validation tests (`test_password_too_short`, `test_password_no_uppercase`, `test_password_no_lowercase`, `test_password_no_digit`) with a single parametrized test:

```python
@pytest.mark.parametrize(
    "password,expected_error",
    [
        ("short", "at least 8"),
        ("nouppercase1!", "uppercase"),
        ("NOLOWERCASE1!", "lowercase"),
        ("NoDigits!!", "digit"),
    ],
)
def test_password_validation_rejects_invalid(self, password, expected_error):
    with pytest.raises(ValidationError, match=expected_error):
        RegisterRequest(email="test@example.com", password=password)
```

- [ ] **Step 4: Prune test_redis_singleton.py — delete 1 duplicate test**

Read `backend/tests/unit/test_redis_singleton.py`, then delete `test_deps_get_redis_cache_uses_singleton` (duplicate of `test_get_redis_cache_returns_singleton`).

- [ ] **Step 5: Verify tests still pass**

Run: `uv run pytest backend/tests/unit -q --tb=short 2>&1 | tail -5`
Expected: ~950 passed (reduced from ~960)

---

## Task 7: Merge TTS Files (8 → 2)

**Files:**
- Create: `backend/tests/unit/test_tts_core.py`
- Create: `backend/tests/unit/test_tts_advanced.py`
- Delete: `backend/tests/unit/test_tts_provider.py`
- Delete: `backend/tests/unit/test_tts_service.py`
- Delete: `backend/tests/unit/test_tts_settings.py`
- Delete: `backend/tests/unit/test_tts_api.py`
- Delete: `backend/tests/unit/test_tts_cached.py`
- Delete: `backend/tests/unit/test_tts_streaming.py`
- Delete: `backend/tests/unit/test_tts_persona_api.py`
- Delete: `backend/tests/unit/test_tts_persona_repository.py`

- [ ] **Step 1: Create test_tts_core.py**

Read all 4 source files, then create `backend/tests/unit/test_tts_core.py` combining their contents. Merge imports (deduplicate), keep all test classes and helper functions. Use `from tests.fixtures.mock_factories import make_mock_redis` where applicable to replace inline redis mocks.

The merged file should contain:
- Imports: combined and deduplicated from all 4 files
- Helpers: `_MockAsyncIterator`, `_make_prompt`, `_make_settings`, `_async_iter`
- From test_tts_provider.py: `TestTTSConfig`, `TestBaseTTSProvider`, `TestMockTTSProvider`, `TestXiaomiTTSProvider`, `TestCreateTTSProvider`
- From test_tts_service.py: `TestTTSService` with `_make_service` helper
- From test_tts_settings.py: `TestTTSSettings`
- From test_tts_api.py: `test_synthesize_endpoint`, `test_synthesize_returns_503_when_tts_unavailable` with `mock_tts_service` fixture

- [ ] **Step 2: Create test_tts_advanced.py**

Read all 4 source files, then create `backend/tests/unit/test_tts_advanced.py` combining their contents. The merged file should contain:
- Imports: combined and deduplicated
- Helpers: `FakeProvider`, `_mock_redis`, `_collect`, `_async_iter`, `_make_prompt_orm`
- From test_tts_cached.py: `TestCachedTTSProvider`
- From test_tts_streaming.py: `TestExtractSentences`, `TestTTSStreamManager`
- From test_tts_persona_api.py: `TestListTtsPersonas`, `TestGetTtsPersona`, `TestUpdateTtsPersona`, `TestVoicePreview` with `_create_app` helper
- From test_tts_persona_repository.py: `TestUpdateWithVariables` with `mock_session` and `repo` fixtures

- [ ] **Step 3: Delete original TTS files**

```bash
rm backend/tests/unit/test_tts_provider.py \
   backend/tests/unit/test_tts_service.py \
   backend/tests/unit/test_tts_settings.py \
   backend/tests/unit/test_tts_api.py \
   backend/tests/unit/test_tts_cached.py \
   backend/tests/unit/test_tts_streaming.py \
   backend/tests/unit/test_tts_persona_api.py \
   backend/tests/unit/test_tts_persona_repository.py
```

- [ ] **Step 4: Verify TTS tests pass**

Run: `uv run pytest backend/tests/unit/test_tts_core.py backend/tests/unit/test_tts_advanced.py -v --tb=short 2>&1 | tail -20`
Expected: all ~46 TTS tests pass

- [ ] **Step 5: Verify full suite still passes**

Run: `uv run pytest backend/tests/unit backend/tests/contract -q --tb=short 2>&1 | tail -5`
Expected: ~950 passed

---

## Task 8: Merge Tour Files (6 → 2)

**Files:**
- Create: `backend/tests/unit/test_tour_services.py`
- Create: `backend/tests/unit/test_tour_chat.py`
- Delete: `backend/tests/unit/test_tour_session_service.py`
- Delete: `backend/tests/unit/test_tour_event_service.py`
- Delete: `backend/tests/unit/test_tour_report_service.py`
- Delete: `backend/tests/unit/test_tour_entities.py`
- Delete: `backend/tests/unit/test_tour_chat_service.py`
- Delete: `backend/tests/unit/test_tour_chat_stream.py`
- Delete: `backend/tests/unit/test_tour_stream_tts.py`

- [ ] **Step 1: Create test_tour_services.py**

Read all 4 source files, then create `backend/tests/unit/test_tour_services.py` combining their contents. Merge imports, keep all test classes and helpers.

- [ ] **Step 2: Create test_tour_chat.py**

Read all 3 source files, then create `backend/tests/unit/test_tour_chat.py` combining their contents.

- [ ] **Step 3: Delete original tour files**

```bash
rm backend/tests/unit/test_tour_session_service.py \
   backend/tests/unit/test_tour_event_service.py \
   backend/tests/unit/test_tour_report_service.py \
   backend/tests/unit/test_tour_entities.py \
   backend/tests/unit/test_tour_chat_service.py \
   backend/tests/unit/test_tour_chat_stream.py \
   backend/tests/unit/test_tour_stream_tts.py
```

- [ ] **Step 4: Verify tour tests pass**

Run: `uv run pytest backend/tests/unit/test_tour_services.py backend/tests/unit/test_tour_chat.py -v --tb=short 2>&1 | tail -20`
Expected: all tour tests pass

---

## Task 9: Merge Chat Files (6 → 2)

**Files:**
- Create: `backend/tests/unit/test_chat_services.py`
- Create: `backend/tests/unit/test_chat_streaming.py`
- Delete: `backend/tests/unit/test_chat_session_service.py`
- Delete: `backend/tests/unit/test_chat_message_service.py`
- Delete: `backend/tests/unit/test_chat_integration.py`
- Delete: `backend/tests/unit/test_chat_service_streaming.py`
- Delete: `backend/tests/unit/test_chat_stream_session_lifecycle.py`
- Delete: `backend/tests/unit/test_chat_stream_tts.py`
- Delete: `backend/tests/unit/test_chat_error_sanitization.py`

- [ ] **Step 1: Create test_chat_services.py**

Read `test_chat_session_service.py`, `test_chat_message_service.py`, and the remaining test from `test_chat_integration.py`. Combine into `test_chat_services.py`.

- [ ] **Step 2: Create test_chat_streaming.py**

Read `test_chat_service_streaming.py`, `test_chat_stream_session_lifecycle.py`, `test_chat_stream_tts.py`, and `test_chat_error_sanitization.py`. Combine into `test_chat_streaming.py`.

- [ ] **Step 3: Delete original chat files**

```bash
rm backend/tests/unit/test_chat_session_service.py \
   backend/tests/unit/test_chat_message_service.py \
   backend/tests/unit/test_chat_integration.py \
   backend/tests/unit/test_chat_service_streaming.py \
   backend/tests/unit/test_chat_stream_session_lifecycle.py \
   backend/tests/unit/test_chat_stream_tts.py \
   backend/tests/unit/test_chat_error_sanitization.py
```

- [ ] **Step 4: Verify chat tests pass**

Run: `uv run pytest backend/tests/unit/test_chat_services.py backend/tests/unit/test_chat_streaming.py -v --tb=short 2>&1 | tail -20`
Expected: all chat tests pass

---

## Task 10: Merge SSE Files (2 → 1)

**Files:**
- Create: `backend/tests/unit/test_sse.py`
- Delete: `backend/tests/unit/test_sse_events_builders.py`
- Delete: `backend/tests/unit/test_sse_audio_events.py`

- [ ] **Step 1: Create test_sse.py**

Read both source files and combine into `test_sse.py`. Merge imports, keep all test classes.

- [ ] **Step 2: Delete original SSE files**

```bash
rm backend/tests/unit/test_sse_events_builders.py \
   backend/tests/unit/test_sse_audio_events.py
```

- [ ] **Step 3: Verify SSE tests pass**

Run: `uv run pytest backend/tests/unit/test_sse.py -v --tb=short 2>&1 | tail -10`
Expected: all SSE tests pass

---

## Task 11: Merge Retrieval Files (4 → 1)

**Files:**
- Create: `backend/tests/unit/test_retrieval.py`
- Delete: `backend/tests/unit/test_rag_fusion.py`
- Delete: `backend/tests/unit/test_rrf_retriever.py`
- Delete: `backend/tests/unit/test_retriever_parallelism.py`
- Delete: `backend/tests/unit/test_parallel_indexing.py`

- [ ] **Step 1: Create test_retrieval.py**

Read all 4 source files and combine into `test_retrieval.py`. Merge imports, keep all test classes.

- [ ] **Step 2: Delete original retrieval files**

```bash
rm backend/tests/unit/test_rag_fusion.py \
   backend/tests/unit/test_rrf_retriever.py \
   backend/tests/unit/test_retriever_parallelism.py \
   backend/tests/unit/test_parallel_indexing.py
```

- [ ] **Step 3: Verify retrieval tests pass**

Run: `uv run pytest backend/tests/unit/test_retrieval.py -v --tb=short 2>&1 | tail -10`
Expected: all retrieval tests pass

---

## Task 12: Merge Indexing Files (4 → 1)

**Files:**
- Create: `backend/tests/unit/test_indexing.py`
- Delete: `backend/tests/unit/test_unified_indexing_service.py`
- Delete: `backend/tests/unit/test_unified_indexing_behavior.py`
- Delete: `backend/tests/unit/test_embedding_lifecycle.py`
- Delete: `backend/tests/unit/test_embedding_provider.py`

- [ ] **Step 1: Create test_indexing.py**

Read all 4 source files and combine into `test_indexing.py`. Merge imports, keep all test classes.

- [ ] **Step 2: Delete original indexing files**

```bash
rm backend/tests/unit/test_unified_indexing_service.py \
   backend/tests/unit/test_unified_indexing_behavior.py \
   backend/tests/unit/test_embedding_lifecycle.py \
   backend/tests/unit/test_embedding_provider.py
```

- [ ] **Step 3: Verify indexing tests pass**

Run: `uv run pytest backend/tests/unit/test_indexing.py -v --tb=short 2>&1 | tail -10`
Expected: all indexing tests pass

---

## Task 13: Merge Database Files (1 → 1, simplified)

**Files:**
- Create: `backend/tests/unit/test_database.py`
- Delete: `backend/tests/unit/test_database_singleton.py`

- [ ] **Step 1: Create test_database.py**

Read `test_database_singleton.py` and create `test_database.py` with the same content (this is a rename with minor cleanup since the other files were deleted in Task 4).

- [ ] **Step 2: Delete original file**

```bash
rm backend/tests/unit/test_database_singleton.py
```

- [ ] **Step 3: Verify database tests pass**

Run: `uv run pytest backend/tests/unit/test_database.py -v --tb=short 2>&1 | tail -10`
Expected: all database tests pass

---

## Task 14: Merge Dependencies Files (5 → 1)

**Files:**
- Create: `backend/tests/unit/test_deps.py`
- Delete: `backend/tests/unit/test_api_deps.py`
- Delete: `backend/tests/unit/test_deps_security.py`
- Delete: `backend/tests/unit/test_auth_logout.py`
- Delete: `backend/tests/unit/test_auth_rate_limit.py`
- Delete: `backend/tests/unit/test_guest_rate_limit.py`

- [ ] **Step 1: Create test_deps.py**

Read all 5 source files and combine into `test_deps.py`. Merge imports, keep all test classes. Deduplicate any repeated mock setup patterns using the `mock_auth_stack` fixture from conftest where possible.

- [ ] **Step 2: Delete original deps files**

```bash
rm backend/tests/unit/test_api_deps.py \
   backend/tests/unit/test_deps_security.py \
   backend/tests/unit/test_auth_logout.py \
   backend/tests/unit/test_auth_rate_limit.py \
   backend/tests/unit/test_guest_rate_limit.py
```

- [ ] **Step 3: Verify deps tests pass**

Run: `uv run pytest backend/tests/unit/test_deps.py -v --tb=short 2>&1 | tail -10`
Expected: all deps tests pass

---

## Task 15: Merge Import Files (2 → 1)

**Files:**
- Create: `backend/tests/unit/test_imports.py`
- Delete: `backend/tests/unit/test_api_no_late_imports.py`
- Delete: `backend/tests/unit/test_api_state_dependencies.py`

- [ ] **Step 1: Create test_imports.py**

Read both source files (test_api_state_dependencies.py should already be pruned from Task 6) and combine into `test_imports.py`.

- [ ] **Step 2: Delete original import files**

```bash
rm backend/tests/unit/test_api_no_late_imports.py \
   backend/tests/unit/test_api_state_dependencies.py
```

- [ ] **Step 3: Verify import tests pass**

Run: `uv run pytest backend/tests/unit/test_imports.py -v --tb=short 2>&1 | tail -10`
Expected: all import tests pass

---

## Task 16: Move Integration Tests to Unit

**Files:**
- Move: `backend/tests/integration/test_document_repository_integration.py` → `backend/tests/unit/test_document_repository_integration.py`
- Move: `backend/tests/integration/test_rate_limit_integration.py` → `backend/tests/unit/test_rate_limit_integration.py`
- Delete: `backend/tests/integration/` directory

- [ ] **Step 1: Move integration test files**

```bash
mv backend/tests/integration/test_document_repository_integration.py backend/tests/unit/
mv backend/tests/integration/test_rate_limit_integration.py backend/tests/unit/
rm -rf backend/tests/integration
```

- [ ] **Step 2: Verify moved tests pass**

Run: `uv run pytest backend/tests/unit/test_document_repository_integration.py backend/tests/unit/test_rate_limit_integration.py -v --tb=short 2>&1 | tail -10`
Expected: all integration tests pass

---

## Task 17: Prune test_main.py

**Files:**
- Modify: `backend/tests/unit/test_main.py`

- [ ] **Step 1: Remove source inspection tests from test_main.py**

Read `backend/tests/unit/test_main.py`. Delete `test_get_singletons_from_app_state_structure` and `test_no_module_level_singleton_mutation` (source inspection tests). Keep any remaining behavioral tests.

- [ ] **Step 2: Verify tests pass**

Run: `uv run pytest backend/tests/unit/test_main.py -v --tb=short 2>&1 | tail -10`
Expected: remaining tests pass

---

## Task 18: Final Verification

- [ ] **Step 1: Run full unit + contract test suite**

Run: `uv run pytest backend/tests/unit backend/tests/contract -v --tb=short 2>&1 | tail -30`
Expected: ~950 tests pass, no failures

- [ ] **Step 2: Count final file numbers**

Run: `echo "Unit test files:"; find backend/tests/unit -name "test_*.py" | wc -l; echo "Contract test files:"; find backend/tests/contract -name "test_*.py" | wc -l; echo "Total test files:"; find backend/tests -name "test_*.py" | wc -l`
Expected: unit ~40, contract 18, total ~65

- [ ] **Step 3: Count final line numbers**

Run: `find backend/tests -name "test_*.py" -not -name "__init__.py" | xargs wc -l | tail -1`
Expected: ~16,000-18,000 lines

- [ ] **Step 4: Verify no duplicate fixtures remain**

Run: `grep -rn "TEST_DATABASE_URL" backend/tests/unit/ backend/tests/contract/ 2>/dev/null`
Expected: should return 0 results (all moved to global conftest)

Run: `grep -rn "async def db_session" backend/tests/unit/ backend/tests/contract/ 2>/dev/null`
Expected: should return 0 results (all moved to global conftest)
