# Test Suite Simplification Design

**Date:** 2026-05-01
**Scope:** Backend test suite (`backend/tests/`)
**Approach:** Plan C — Aggressive reduction

## Current State

- 115 test files, ~24,500 lines, 1008 test cases (all passing)
- 6 directories: architecture(3), contract(18), e2e(3), fixtures(1), integration(2), performance(1), unit(88)
- 600-900 lines of duplicated boilerplate (db_session fixtures, auth mocks, mock chat sessions)
- No unit-level `conftest.py` exists
- `fixtures/mock_providers.py` (36 lines) is unused by any test

## Target State

- ~65 test files, ~16,000-18,000 lines, ~950 test cases
- 3 directories: contract, e2e, unit (+ top-level conftest + fixtures)
- Zero duplicated fixtures — centralized in conftest hierarchy
- Shared mock factories replace per-test mock setup

## 1. Directory Structure

### Delete Entire Directories

- `architecture/` (3 files, ~760 lines) — import rule checks, overlaps with unit test guards
- `performance/` (Locust scripts, mock servers) — out of scope for unit/contract tests

### Merge

- `integration/` (2 files) → move into `unit/`

### Result

```
backend/tests/
├── conftest.py              # NEW: global shared fixtures
├── contract/
│   ├── conftest.py          # ENHANCED: extract shared db/auth fixtures
│   └── test_*.py            # 18 files, unchanged
├── e2e/
│   ├── conftest.py          # unchanged
│   └── test_*.py            # 3 files, unchanged
├── fixtures/
│   └── mock_factories.py    # REWRITE: replace unused mock_providers.py
└── unit/
    ├── conftest.py          # NEW: unit-specific fixtures
    └── test_*.py            # ~40 files (from 88)
```

## 2. Delete Entire Files (8 files, ~1,000 lines)

| File | Lines | Reason |
|------|-------|--------|
| `unit/test_pagination.py` | 48 | All tests are signature/constant checks, zero behavior tested |
| `unit/test_debt_marker_scan_script.py` | 12 | Tests shell script content, not production code |
| `unit/test_verify_local_quality_script.py` | 33 | Tests shell script properties, not production code |
| `unit/test_db_session.py` | 10 | Single isinstance check |
| `unit/test_db_models.py` | 130 | All tests are constructor-assignment checks |
| `unit/test_ci_workflow_contract.py` | 107 | Tests CI script content, not production code |
| `architecture/test_ci_guardrails.py` | ~350 | Directory deleted |
| `architecture/test_layer_import_rules.py` | 377 | Directory deleted |
| `architecture/test_no_main_runtime_imports.py` | ~30 | Directory deleted |

## 3. Delete Tests Within Files

| File | Delete | Keep |
|------|--------|------|
| `test_chat_integration.py` | `test_get_rag_agent_function_exists`, `test_chat_service_uses_rag_agent` (existence checks) | `test_ask_question_with_rag_calls_agent` |
| `test_api_state_dependencies.py` | `test_rag_agent_dependency_in_deps`, `test_llm_provider_dependency_in_deps` (hasattr checks) | 2 source-inspection tests |
| `test_auth_service.py` | `test_valid_password_complex` (near-duplicate of `test_valid_password_accepted`); parametrize 4 password validation tests into 1 | All remaining tests |
| `test_redis_singleton.py` | `test_deps_get_redis_cache_uses_singleton` (duplicate of `test_get_redis_cache_returns_singleton`) | All remaining tests |

## 4. File Merging Plan (88 → ~40 unit files)

### TTS (7 → 2)

**`test_tts_core.py`** = `test_tts_provider.py` + `test_tts_service.py` + `test_tts_settings.py` + `test_tts_api.py`

**`test_tts_advanced.py`** = `test_tts_cached.py` + `test_tts_streaming.py` + `test_tts_persona_api.py` + `test_tts_persona_repository.py`

### Tour (6 → 2)

**`test_tour_services.py`** = `test_tour_session_service.py` + `test_tour_event_service.py` + `test_tour_report_service.py` + `test_tour_entities.py`

**`test_tour_chat.py`** = `test_tour_chat_service.py` + `test_tour_chat_stream.py` + `test_tour_stream_tts.py`

### Chat (6 → 2)

**`test_chat_services.py`** = `test_chat_session_service.py` + `test_chat_message_service.py` + remaining test from `test_chat_integration.py`

**`test_chat_streaming.py`** = `test_chat_service_streaming.py` + `test_chat_stream_session_lifecycle.py` + `test_chat_stream_tts.py` + `test_chat_error_sanitization.py`

### SSE (2 → 1)

**`test_sse.py`** = `test_sse_events_builders.py` + `test_sse_audio_events.py`

### Retrieval (4 → 1)

**`test_retrieval.py`** = `test_rag_fusion.py` + `test_rrf_retriever.py` + `test_retriever_parallelism.py` + `test_parallel_indexing.py`

### Indexing (4 → 1)

**`test_indexing.py`** = `test_unified_indexing_service.py` + `test_unified_indexing_behavior.py` + `test_embedding_lifecycle.py` + `test_embedding_provider.py`

### Database (2 → 1)

**`test_database.py`** = `test_database_singleton.py` (db_session and db_models deleted)

### Dependencies (5 → 1)

**`test_deps.py`** = `test_api_deps.py` + `test_deps_security.py` + `test_auth_logout.py` + `test_auth_rate_limit.py` + `test_guest_rate_limit.py`

### Imports (2 → 1)

**`test_imports.py`** = `test_api_no_late_imports.py` + `test_api_state_dependencies.py` (pruned)

### Files Kept As-Is (~25)

```
test_auth_service.py, test_bootstrap_admin.py, test_chunking.py,
test_client_ip.py, test_config.py, test_content_source.py,
test_context_manager.py, test_conversation_query_rewrite.py,
test_custom_embeddings.py, test_document_filter.py,
test_document_service.py, test_documents_integration.py,
test_domain_entities.py, test_error_handling.py, test_es_client.py,
test_exhibit_service.py, test_factory_functions.py,
test_ingestion_service.py, test_jwt_handler.py, test_llm_provider.py,
test_llm_trace_masking.py, test_llm_trace_recorder.py, test_main.py,
test_museum_tools.py, test_observability_context.py,
test_prompt_cache.py, test_prompt_service.py, test_query_transform.py,
test_rag_agent.py, test_repositories.py, test_rerank_provider.py,
test_state_machine.py, test_profile_service.py,
test_reflection_prompts.py, test_redis_cache.py,
test_redis_singleton.py, test_curator_agent.py,
test_curator_service.py, test_curator_tools.py,
test_voice_description_helpers.py
```

## 5. Fixture Hierarchy

### `tests/conftest.py` (NEW — global)

```python
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

### `tests/unit/conftest.py` (NEW)

```python
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

### `tests/contract/conftest.py` (ENHANCED)

Add `db_session`, `auth_token`, `admin_token` fixtures (imported from global conftest via pytest's conftest hierarchy). Remove duplicated definitions from individual contract test files.

## 6. Mock Factories (`tests/fixtures/mock_factories.py`)

Replace unused `mock_providers.py`:

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

## 7. Execution Order

1. **Create conftest hierarchy** — `tests/conftest.py`, `tests/unit/conftest.py`, enhance `tests/contract/conftest.py`
2. **Create mock factories** — rewrite `tests/fixtures/mock_factories.py`, delete `mock_providers.py`
3. **Delete entire files** — 5 unit files + architecture directory + performance directory
4. **Delete tests within files** — prune specific low-value tests
5. **Merge files** — combine related test files per merging plan
6. **Refactor to use shared fixtures** — replace inline mock setups with conftest fixtures and factory imports
7. **Verify** — `uv run pytest backend/tests/unit backend/tests/contract -v` must pass with ~950 tests

## 8. Expected Results

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Test files (unit) | 88 | ~40 | -55% |
| Test files (total) | 115 | ~65 | -43% |
| Lines of test code | ~24,500 | ~16,000-18,000 | -30% |
| Duplicated fixture definitions | 13+ | 0 | -100% |
| Test cases | 1008 | ~950 | -5% |
| Directories | 6 | 3 | -50% |
