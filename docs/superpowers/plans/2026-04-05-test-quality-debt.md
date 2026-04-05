# Test Quality Technical Debt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all P0 and P1 test quality issues identified in the technical debt audit.

**Architecture:** Add frontend test infrastructure, add tests for deps.py, configure coverage thresholds, add service-level tests.

**Tech Stack:** Vitest, Vue Test Utils, pytest-cov, Python 3.13

---

## Files Modified

| File | Purpose |
|------|---------|
| `frontend/package.json` | Add Vitest dependencies |
| `frontend/vitest.config.js` | Configure Vitest |
| `frontend/src/composables/__tests__/` | Add composable tests |
| `backend/tests/unit/test_api_deps.py` | Test deps.py security |
| `backend/pyproject.toml` | Add coverage config |
| `backend/tests/unit/test_document_service.py` | Add service tests |
| `backend/tests/unit/test_chat_service.py` | Add streaming tests |

---

## Task 1: Add Frontend Test Infrastructure

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/composables/__tests__/useAuth.test.js`

- [ ] **Step 1: Add Vitest dependencies to package.json**

```json
// frontend/package.json (add to devDependencies)
{
  "devDependencies": {
    "vitest": "^1.6.0",
    "@vue/test-utils": "^2.4.6",
    "@vitest/ui": "^1.6.0",
    "jsdom": "^24.1.0"
  },
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest --coverage"
  }
}
```

- [ ] **Step 2: Create Vitest configuration**

```javascript
// frontend/vitest.config.js

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{js,ts}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.js', 'src/**/*.vue'],
      exclude: ['src/**/*.test.js', 'src/**/*.spec.js']
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
```

- [ ] **Step 3: Write first test for useAuth composable**

```javascript
// frontend/src/composables/__tests__/useAuth.test.js

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuth } from '../useAuth'

// Mock fetch
global.fetch = vi.fn()

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('starts with no user when no token in localStorage', () => {
    const { user, isAuthenticated } = useAuth()
    expect(user.value).toBeNull()
    expect(isAuthenticated.value).toBe(false)
  })

  it('loads user from token in localStorage', async () => {
    localStorage.setItem('token', 'valid-token')
    
    fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: 'user-1', email: 'test@example.com' })
    })
    
    const { user, isAuthenticated } = useAuth()
    
    // Wait for async fetch
    await new Promise(resolve => setTimeout(resolve, 0))
    
    expect(isAuthenticated.value).toBe(true)
    expect(user.value).toEqual({ id: 'user-1', email: 'test@example.com' })
  })

  it('login stores token and sets user', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ access_token: 'new-token', token_type: 'bearer' })
    })
    
    const { login, isAuthenticated } = useAuth()
    
    await login('test@example.com', 'password')
    
    expect(localStorage.getItem('token')).toBe('new-token')
    expect(isAuthenticated.value).toBe(true)
  })

  it('logout clears token and user', async () => {
    localStorage.setItem('token', 'valid-token')
    
    fetch.mockResolvedValueOnce({ ok: true })
    
    const { logout, isAuthenticated, user } = useAuth()
    
    await logout()
    
    expect(localStorage.getItem('token')).toBeNull()
    expect(isAuthenticated.value).toBe(false)
    expect(user.value).toBeNull()
  })

  it('handles login failure', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'Invalid credentials' })
    })
    
    const { login, error, isAuthenticated } = useAuth()
    
    await login('test@example.com', 'wrong-password')
    
    expect(isAuthenticated.value).toBe(false)
    expect(error.value).toBe('Invalid credentials')
  })
})
```

- [ ] **Step 4: Install dependencies and run test**

Run: `cd /home/singer/MuseAI/frontend && npm install`
Run: `cd /home/singer/MuseAI/frontend && npm test`

Expected: Tests run (may fail initially if useAuth structure differs)

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/vitest.config.js frontend/src/composables/__tests__/
git commit -m "$(cat <<'EOF'
feat(test): add frontend test infrastructure with Vitest

- Add Vitest, Vue Test Utils, jsdom dependencies
- Configure Vitest for Vue 3 testing
- Add initial tests for useAuth composable
- Add test scripts to package.json

P0 test quality fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add Tests for API Dependencies Module

**Files:**
- Create: `backend/tests/unit/test_api_deps.py`

- [ ] **Step 1: Write tests for deps.py security functions**

```python
# backend/tests/unit/test_api_deps.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from redis.exceptions import RedisError


@pytest.mark.asyncio
async def test_get_db_session_yields_session():
    """get_db_session should yield a database session."""
    from app.api.deps import get_db_session
    
    sessions = []
    async for session in get_db_session():
        sessions.append(session)
    
    assert len(sessions) == 1
    # Session should be an AsyncSession
    from sqlalchemy.ext.asyncio import AsyncSession
    assert isinstance(sessions[0], AsyncSession)


def test_get_jwt_handler_returns_handler():
    """get_jwt_handler should return a JWTHandler instance."""
    from app.api.deps import get_jwt_handler
    from app.infra.security.jwt_handler import JWTHandler
    
    handler = get_jwt_handler()
    assert isinstance(handler, JWTHandler)


@pytest.mark.asyncio
async def test_get_current_user_raises_for_blacklisted_token():
    """get_current_user should raise 401 for blacklisted token."""
    from app.api.deps import get_current_user
    
    mock_redis = MagicMock()
    mock_redis.is_token_blacklisted = AsyncMock(return_value=True)
    
    mock_jwt = MagicMock()
    mock_jwt.get_jti = MagicMock(return_value="blacklisted-jti")
    
    mock_session = AsyncMock()
    mock_credentials = MagicMock()
    mock_credentials.credentials = "valid-token"
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=mock_credentials,
            jwt_handler=mock_jwt,
            session=mock_session,
            redis=mock_redis,
        )
    
    assert exc_info.value.status_code == 401
    assert "revoked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_raises_for_invalid_token():
    """get_current_user should raise 401 for invalid token."""
    from app.api.deps import get_current_user
    
    mock_redis = MagicMock()
    mock_redis.is_token_blacklisted = AsyncMock(return_value=False)
    
    mock_jwt = MagicMock()
    mock_jwt.get_jti = MagicMock(return_value=None)
    mock_jwt.verify_token = MagicMock(return_value=None)  # Invalid token
    
    mock_session = AsyncMock()
    mock_credentials = MagicMock()
    mock_credentials.credentials = "invalid-token"
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=mock_credentials,
            jwt_handler=mock_jwt,
            session=mock_session,
            redis=mock_redis,
        )
    
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_for_nonexistent_user():
    """get_current_user should raise 401 if user not found."""
    from app.api.deps import get_current_user
    
    mock_redis = MagicMock()
    mock_redis.is_token_blacklisted = AsyncMock(return_value=False)
    
    mock_jwt = MagicMock()
    mock_jwt.get_jti = MagicMock(return_value="valid-jti")
    mock_jwt.verify_token = MagicMock(return_value="user-123")
    
    mock_session = AsyncMock()
    mock_credentials = MagicMock()
    mock_credentials.credentials = "valid-token"
    
    with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )
    
    assert exc_info.value.status_code == 401
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_returns_user_on_success():
    """get_current_user should return user dict on success."""
    from app.api.deps import get_current_user
    
    mock_redis = MagicMock()
    mock_redis.is_token_blacklisted = AsyncMock(return_value=False)
    
    mock_jwt = MagicMock()
    mock_jwt.get_jti = MagicMock(return_value="valid-jti")
    mock_jwt.verify_token = MagicMock(return_value="user-123")
    
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"
    
    mock_session = AsyncMock()
    mock_credentials = MagicMock()
    mock_credentials.credentials = "valid-token"
    
    with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
        result = await get_current_user(
            credentials=mock_credentials,
            jwt_handler=mock_jwt,
            session=mock_session,
            redis=mock_redis,
        )
    
    assert result["id"] == "user-123"
    assert result["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_check_rate_limit_allows_under_limit():
    """check_rate_limit should pass when under limit."""
    from app.api.deps import check_rate_limit
    
    mock_redis = MagicMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)
    
    mock_user = {"id": "user-123"}
    
    # Should not raise
    await check_rate_limit(redis=mock_redis, current_user=mock_user)


@pytest.mark.asyncio
async def test_check_rate_limit_raises_over_limit():
    """check_rate_limit should raise 429 when over limit."""
    from app.api.deps import check_rate_limit
    
    mock_redis = MagicMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=False)
    
    mock_user = {"id": "user-123"}
    
    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit(redis=mock_redis, current_user=mock_user)
    
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_check_rate_limit_passes_on_redis_error():
    """check_rate_limit should pass when Redis is unavailable (fail open)."""
    from app.api.deps import check_rate_limit
    
    mock_redis = MagicMock()
    mock_redis.check_rate_limit = AsyncMock(side_effect=RedisError("Connection refused"))
    
    mock_user = {"id": "user-123"}
    
    # Should not raise - fail open
    await check_rate_limit(redis=mock_redis, current_user=mock_user)
```

- [ ] **Step 2: Run tests to verify**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_api_deps.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_api_deps.py
git commit -m "$(cat <<'EOF'
test(backend): add tests for API dependencies module

- Test get_db_session yields valid session
- Test get_current_user with valid/invalid/blacklisted tokens
- Test check_rate_limit behavior under various conditions
- Test fail-open behavior for Redis errors

P0 test quality fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Configure Coverage Thresholds

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add coverage configuration to pyproject.toml**

```toml
# backend/pyproject.toml (add at the end)

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["app"]
branch = true
omit = [
    "app/__init__.py",
    "tests/*",
]

[tool.coverage.report]
fail_under = 70
show_missing = true
skip_covered = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]

[tool.coverage.html]
directory = "htmlcov"
```

- [ ] **Step 2: Run tests with coverage**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit --cov=app --cov-report=term-missing`
Expected: Tests run with coverage report

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "$(cat <<'EOF'
test(backend): add coverage configuration with 70% threshold

- Configure pytest with asyncio mode
- Set coverage to fail under 70%
- Configure coverage exclusions and reporting
- Generate HTML coverage reports

P1 test quality fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add Document Service Tests

**Files:**
- Create: `backend/tests/unit/test_document_service.py`

- [ ] **Step 1: Write tests for document_service.py**

```python
# backend/tests/unit/test_document_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.application.document_service import (
    create_document,
    get_documents_by_user,
    get_document_by_id,
    get_ingestion_job_by_document,
    delete_document,
    update_document_status,
)


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_document():
    doc = MagicMock()
    doc.id = "doc-123"
    doc.filename = "test.pdf"
    doc.file_size = 1024
    doc.status = "pending"
    doc.error = None
    doc.created_at = datetime.now(timezone.utc)
    return doc


@pytest.mark.asyncio
async def test_create_document(mock_session, mock_document):
    """create_document should create and return a new document."""
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    
    result = await create_document(
        session=mock_session,
        filename="test.pdf",
        file_size=1024,
        user_id="user-123",
    )
    
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_get_documents_by_user_returns_list(mock_session, mock_document):
    """get_documents_by_user should return list of user's documents."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_document]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await get_documents_by_user(mock_session, "user-123")
    
    assert len(result) == 1
    assert result[0].id == "doc-123"


@pytest.mark.asyncio
async def test_get_documents_by_user_returns_empty_list(mock_session):
    """get_documents_by_user should return empty list when no documents."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await get_documents_by_user(mock_session, "user-123")
    
    assert result == []


@pytest.mark.asyncio
async def test_get_document_by_id_returns_document(mock_session, mock_document):
    """get_document_by_id should return document if owned by user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_document
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await get_document_by_id(mock_session, "doc-123", "user-123")
    
    assert result.id == "doc-123"


@pytest.mark.asyncio
async def test_get_document_by_id_returns_none_if_not_found(mock_session):
    """get_document_by_id should return None if document not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await get_document_by_id(mock_session, "nonexistent", "user-123")
    
    assert result is None


@pytest.mark.asyncio
async def test_get_document_by_id_returns_none_if_not_owner(mock_session):
    """get_document_by_id should return None if not owned by user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Query filters by user_id
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await get_document_by_id(mock_session, "doc-123", "different-user")
    
    assert result is None


@pytest.mark.asyncio
async def test_delete_document_returns_true_on_success(mock_session, mock_document):
    """delete_document should return True when document deleted."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_document
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.delete = AsyncMock()
    
    result = await delete_document(mock_session, "doc-123", "user-123")
    
    assert result is True
    mock_session.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_document_returns_false_if_not_found(mock_session):
    """delete_document should return False if document not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await delete_document(mock_session, "nonexistent", "user-123")
    
    assert result is False


@pytest.mark.asyncio
async def test_update_document_status(mock_session, mock_document):
    """update_document_status should update status and error."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_document
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    await update_document_status(
        mock_session,
        "doc-123",
        "failed",
        "Processing error"
    )
    
    assert mock_document.status == "failed"
    assert mock_document.error == "Processing error"


@pytest.mark.asyncio
async def test_get_ingestion_job_by_document(mock_session):
    """get_ingestion_job_by_document should return job if exists."""
    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.document_id = "doc-123"
    mock_job.status = "completed"
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    result = await get_ingestion_job_by_document(mock_session, "doc-123")
    
    assert result.id == "job-123"
```

- [ ] **Step 2: Run tests to verify**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_document_service.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_document_service.py
git commit -m "$(cat <<'EOF'
test(backend): add unit tests for document_service

- Test create_document functionality
- Test get_documents_by_user with various scenarios
- Test get_document_by_id with ownership checks
- Test delete_document with authorization
- Test update_document_status
- Test get_ingestion_job_by_document

P1 test quality fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add Chat Service Streaming Tests

**Files:**
- Create: `backend/tests/unit/test_chat_service_streaming.py`

- [ ] **Step 1: Write tests for streaming functions**

```python
# backend/tests/unit/test_chat_service_streaming.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_rag_agent():
    agent = MagicMock()
    
    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "content": "Hello"}
        yield {"type": "token", "content": " world"}
        yield {"type": "done", "trace_id": "trace-123"}
    
    agent.stream = mock_stream
    return agent


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.mark.asyncio
async def test_ask_question_stream_yields_events(mock_session, mock_rag_agent, mock_llm):
    """ask_question_stream_with_rag should yield SSE events."""
    from app.application.chat_service import ask_question_stream_with_rag
    
    # Mock session.get for session validation
    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = MagicMock(id="session-123", user_id="user-123")
    mock_session.execute = AsyncMock(return_value=mock_session_result)
    
    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="session-123",
        message="Hello",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)
    
    assert len(events) > 0
    # Check SSE format
    assert any("event:" in e for e in events)


@pytest.mark.asyncio
async def test_ask_question_stream_handles_error(mock_session, mock_llm):
    """ask_question_stream_with_rag should handle errors gracefully."""
    from app.application.chat_service import ask_question_stream_with_rag
    
    # Mock session.get for session validation
    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = MagicMock(id="session-123", user_id="user-123")
    mock_session.execute = AsyncMock(return_value=mock_session_result)
    
    # Create a RAG agent that raises an error
    error_agent = MagicMock()
    
    async def error_stream(*args, **kwargs):
        raise Exception("LLM error")
    
    error_agent.stream = error_stream
    
    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="session-123",
        message="Hello",
        rag_agent=error_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)
    
    # Should have error event
    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0


@pytest.mark.asyncio
async def test_ask_question_stream_validates_session(mock_session, mock_rag_agent, mock_llm):
    """ask_question_stream_with_rag should validate session ownership."""
    from app.application.chat_service import ask_question_stream_with_rag
    
    # Mock session.get returns None (not found or not owned)
    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_session_result)
    
    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="nonexistent-session",
        message="Hello",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)
    
    # Should have error event for invalid session
    error_events = [e for e in events if "error" in e.lower() or "not found" in e.lower()]
    assert len(error_events) > 0


@pytest.mark.asyncio
async def test_ask_question_stream_saves_messages(mock_session, mock_rag_agent, mock_llm):
    """ask_question_stream_with_rag should save user and assistant messages."""
    from app.application.chat_service import ask_question_stream_with_rag
    
    # Mock session.get for session validation
    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = MagicMock(id="session-123", user_id="user-123")
    mock_session.execute = AsyncMock(return_value=mock_session_result)
    
    # Track session.add calls
    added_objects = []
    mock_session.add = lambda obj: added_objects.append(obj)
    
    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="session-123",
        message="Hello",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)
    
    # Should have added user message and assistant message
    assert len(added_objects) >= 2  # At least user message and assistant message
```

- [ ] **Step 2: Run tests to verify**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_service_streaming.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_chat_service_streaming.py
git commit -m "$(cat <<'EOF'
test(backend): add streaming tests for chat_service

- Test ask_question_stream_with_rag yields SSE events
- Test error handling during streaming
- Test session validation
- Test message persistence during streaming

P1 test quality fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Run All Tests and Verify

- [ ] **Step 1: Run backend tests with coverage**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit --cov=app --cov-report=term-missing`
Expected: All tests PASS, coverage >= 70%

- [ ] **Step 2: Run frontend tests**

Run: `cd /home/singer/MuseAI/frontend && npm test`
Expected: All tests PASS

- [ ] **Step 3: Final commit for test quality debt completion**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: complete test quality technical debt fixes (P0 + P1)

Completed fixes:
- P0: Add frontend test infrastructure (Vitest)
- P0: Add tests for api/deps.py security module
- P1: Configure coverage thresholds (70%)
- P1: Add document_service tests
- P1: Add chat_service streaming tests

All tests passing.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```
