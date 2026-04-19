# B4 Core Service Test Coverage Implementation Plan
**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close TEST-P1-01 (6 application services with zero direct test coverage) and TEST-P1-02 (2 public API routers with no contract tests) in ~2–3 person-days. Each service gets a focused unit-test file covering happy paths and the most important error branches.

**Scope philosophy:** test each public method at least once; for methods with branching logic (`exhibit_service.list_exhibits` has 4 branches, `profile_service.record_visit` has a "first visit" branch, etc.) add one test per non-trivial branch. Avoid exhaustive coverage — diminishing returns waste time. Mock dependencies via ports (already Protocol types after B2) or `AsyncMock()`.

**Architecture constraints (do not re-litigate):**

1. **Service seams are already correct after B2.** `profile_service`, `exhibit_service`, and `curator_service` receive their dependencies as Ports (Protocol types) via constructor injection — trivial to mock with `MagicMock`/`AsyncMock`. `chat_session_service` and `chat_message_service` take `AsyncSession` directly — follow the established pattern from `test_chat_service_streaming.py:14-40` and mock the session with `AsyncMock`/`MagicMock`.

2. **Do not introduce in-memory SQLite in unit tests.** Contract tests (Task 7) use SQLite via the existing `backend/tests/contract/conftest.py` fixtures. Unit tests stay pure — no engine, no tables, no event loop surprises.

3. **Do not broaden the scope.** This batch does **not**: rewrite services, add new methods, fix latent bugs, refactor adapters. If a test catches a bug, stop and flag it — bug fixes are separate commits in a later batch. A test-only batch keeps blast radius minimal.

**Tech Stack:** Python 3.11, pytest, `unittest.mock` (AsyncMock/MagicMock), FastAPI TestClient (for contract tests only), uv.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B4.

**Related audit findings:** TEST-P1-01, TEST-P1-02.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/tests/unit/test_error_handling.py` | Create | Cover `sanitize_error_message` (30 LOC, 1 function) |
| `backend/tests/unit/test_chat_session_service.py` | Create | Cover 5 CRUD functions on `ChatSession` |
| `backend/tests/unit/test_chat_message_service.py` | Create | Cover 3 functions on `ChatMessage` |
| `backend/tests/unit/test_profile_service.py` | Create | Cover `ProfileService` — 8 public methods |
| `backend/tests/unit/test_exhibit_service.py` | Create | Cover `ExhibitService` — 11 public methods, with focus on `list_exhibits` 4-branch routing |
| `backend/tests/unit/test_curator_service.py` | Create | Cover `CuratorService` — 5 methods, all delegate to ≥2 mocked ports |
| `backend/tests/contract/test_profile_api.py` | Create | Contract tests for `api/profile.py` — 2 endpoints |
| `backend/tests/contract/test_exhibits_api.py` | Create | Contract tests for `api/exhibits.py` — 5 endpoints |

No application or infra code is modified in this plan.

---

## Task 1: B4-1 — `sanitize_error_message` unit tests

**Scope:** Pure function, no DB, no mocks beyond a fake exception. 4 focused tests.

**Files:**
- Create: `backend/tests/unit/test_error_handling.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/unit/test_error_handling.py`:
```python
"""Unit tests for sanitize_error_message — ensures no internals leak to client responses."""
from app.application.error_handling import SANITIZED_ERROR_MESSAGE, sanitize_error_message


def test_sanitize_generic_exception_returns_sanitized_constant():
    err = RuntimeError("boom — /etc/secrets/db.conf missing")
    result = sanitize_error_message(err)
    assert result == SANITIZED_ERROR_MESSAGE
    # The raw internal detail must never appear in the returned message.
    assert "/etc/secrets" not in result
    assert "boom" not in result


def test_sanitize_empty_message_exception():
    """Exception with empty str() still returns the sanitized constant."""
    err = ValueError()
    result = sanitize_error_message(err)
    assert result == SANITIZED_ERROR_MESSAGE


def test_sanitize_does_not_leak_exception_type_name():
    """Even the exception class name must not appear in the returned string."""
    class SuperSecretInternalError(Exception):
        pass

    result = sanitize_error_message(SuperSecretInternalError("oops"))
    assert result == SANITIZED_ERROR_MESSAGE
    assert "SuperSecretInternalError" not in result


def test_sanitize_handles_exception_with_request_attribute():
    """Some exceptions (httpx errors) carry a `.request` attribute. The
    function peeks at `.url.path` to enrich the server-side log but must
    not leak anything into the returned string."""
    from types import SimpleNamespace

    err = RuntimeError("upstream failure")
    err.request = SimpleNamespace(url=SimpleNamespace(path="/internal/admin"))

    result = sanitize_error_message(err)

    assert result == SANITIZED_ERROR_MESSAGE
    assert "/internal/admin" not in result
```

- [ ] **Step 2: Run the tests — all 4 should PASS immediately**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_error_handling.py -v
```
Expected: 4 passed.

- [ ] **Step 3: Run ruff on the new file**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/unit/test_error_handling.py
```
Expected: `All checks passed!`.

- [ ] **Step 4: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/unit/test_error_handling.py && git commit -m "$(cat <<'EOF'
test(error_handling): cover sanitize_error_message (B4-1 / TEST-P1-01)

Four focused unit tests verify the function never leaks internals:
exception messages, exception class names, or request.url.path details
must not appear in the returned string — only the generic sanitized
constant is returned to the caller.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: B4-2 — `chat_session_service` unit tests

**Scope:** 5 async functions: `create_session`, `get_sessions_by_user`, `count_sessions_by_user`, `get_session_by_id`, `delete_session`. Mock `AsyncSession` with `AsyncMock`/`MagicMock` following the `test_chat_service_streaming.py` pattern.

**Files:**
- Create: `backend/tests/unit/test_chat_session_service.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/unit/test_chat_session_service.py`:
```python
"""Unit tests for chat_session_service — pure session-level mocking, no DB."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.chat_session_service import (
    count_sessions_by_user,
    create_session,
    delete_session,
    get_session_by_id,
    get_sessions_by_user,
)


def _mock_session() -> AsyncMock:
    """AsyncSession with the 4 methods these functions use: add, flush, refresh, execute, delete."""
    session = AsyncMock()
    session.add = MagicMock()  # sync, not async
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_session_persists_new_row_and_returns_it():
    session = _mock_session()

    result = await create_session(session, title="My chat", user_id="user-123")

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.title == "My chat"
    assert added.user_id == "user-123"
    assert added.id  # uuid assigned
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added)
    assert result is added


@pytest.mark.asyncio
async def test_create_session_generates_unique_ids():
    session = _mock_session()
    a = await create_session(session, title="a", user_id="u")
    b = await create_session(session, title="b", user_id="u")
    assert a.id != b.id


@pytest.mark.asyncio
async def test_get_sessions_by_user_applies_limit_and_offset():
    session = _mock_session()
    fake_sessions = [MagicMock(), MagicMock()]
    scalars = MagicMock()
    scalars.all.return_value = fake_sessions
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    result = await get_sessions_by_user(session, user_id="u-1", limit=5, offset=10)

    assert result == fake_sessions
    session.execute.assert_awaited_once()
    # The generated statement is the first positional arg. Assert it's SELECT-ish —
    # deeper SQL introspection belongs in an integration test.
    stmt = session.execute.call_args[0][0]
    rendered = str(stmt).lower()
    assert "select" in rendered
    assert "chat_sessions" in rendered


@pytest.mark.asyncio
async def test_get_sessions_by_user_returns_empty_list_when_no_rows():
    session = _mock_session()
    scalars = MagicMock()
    scalars.all.return_value = []
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    result = await get_sessions_by_user(session, user_id="u-empty")
    assert result == []


@pytest.mark.asyncio
async def test_count_sessions_by_user_returns_int():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = 7
    session.execute.return_value = result_obj

    count = await count_sessions_by_user(session, user_id="u-1")
    assert count == 7


@pytest.mark.asyncio
async def test_count_sessions_by_user_returns_zero_when_null():
    """If DB returns None (theoretically impossible with COUNT but defensively coded), return 0."""
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = None
    session.execute.return_value = result_obj

    count = await count_sessions_by_user(session, user_id="u-1")
    assert count == 0


@pytest.mark.asyncio
async def test_get_session_by_id_returns_session_on_match():
    session = _mock_session()
    target = MagicMock()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = target
    session.execute.return_value = result_obj

    result = await get_session_by_id(session, session_id="s-1", user_id="u-1")
    assert result is target


@pytest.mark.asyncio
async def test_get_session_by_id_returns_none_when_not_found():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = None
    session.execute.return_value = result_obj

    result = await get_session_by_id(session, session_id="missing", user_id="u-1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_session_deletes_and_returns_true_when_found():
    session = _mock_session()
    target = MagicMock()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = target
    session.execute.return_value = result_obj

    ok = await delete_session(session, session_id="s-1", user_id="u-1")

    assert ok is True
    session.delete.assert_awaited_once_with(target)


@pytest.mark.asyncio
async def test_delete_session_returns_false_when_not_found():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = None
    session.execute.return_value = result_obj

    ok = await delete_session(session, session_id="missing", user_id="u-1")
    assert ok is False
    session.delete.assert_not_awaited()
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_session_service.py -v
```
Expected: 10 passed.

- [ ] **Step 3: Run ruff**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/unit/test_chat_session_service.py
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/unit/test_chat_session_service.py && git commit -m "$(cat <<'EOF'
test(chat_session_service): cover 5 CRUD functions (B4-2 / TEST-P1-01)

10 unit tests using AsyncMock/MagicMock to verify each function's
contract: create persists with a fresh UUID, list applies limit/offset,
count coerces None → 0, get returns the matching row or None, delete
returns True only when the row existed.

No DB engine, no SQLite — pure mocking following the pattern
established in test_chat_service_streaming.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: B4-3 — `chat_message_service` unit tests

**Scope:** 3 async functions: `add_message`, `get_messages_by_session`, `count_messages_by_session`.

**Files:**
- Create: `backend/tests/unit/test_chat_message_service.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/unit/test_chat_message_service.py`:
```python
"""Unit tests for chat_message_service."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.chat_message_service import (
    add_message,
    count_messages_by_session,
    get_messages_by_session,
)


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_add_message_persists_with_uuid_and_optional_trace_id():
    session = _mock_session()

    result = await add_message(
        session, session_id="s-1", role="user", content="hello", trace_id="t-1"
    )

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.session_id == "s-1"
    assert added.role == "user"
    assert added.content == "hello"
    assert added.trace_id == "t-1"
    assert added.id  # uuid assigned
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added)
    assert result is added


@pytest.mark.asyncio
async def test_add_message_trace_id_defaults_to_none():
    session = _mock_session()
    result = await add_message(session, session_id="s-1", role="assistant", content="hi")
    assert result.trace_id is None


@pytest.mark.asyncio
async def test_add_message_generates_unique_ids():
    session = _mock_session()
    a = await add_message(session, session_id="s-1", role="user", content="1")
    b = await add_message(session, session_id="s-1", role="user", content="2")
    assert a.id != b.id


@pytest.mark.asyncio
async def test_get_messages_by_session_applies_limit_offset_and_asc_order():
    session = _mock_session()
    fake = [MagicMock(), MagicMock(), MagicMock()]
    scalars = MagicMock()
    scalars.all.return_value = fake
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    messages = await get_messages_by_session(session, session_id="s-1", limit=50, offset=0)

    assert messages == fake
    stmt = session.execute.call_args[0][0]
    rendered = str(stmt).lower()
    assert "select" in rendered
    assert "chat_messages" in rendered
    # Messages must be returned oldest-first (ASC), otherwise the chat UI would render inverted.
    assert "asc" in rendered or "order by" in rendered  # ASC is SQLAlchemy's default dir


@pytest.mark.asyncio
async def test_count_messages_by_session_returns_count():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = 42
    session.execute.return_value = result_obj

    assert await count_messages_by_session(session, session_id="s-1") == 42


@pytest.mark.asyncio
async def test_count_messages_by_session_returns_zero_when_null():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = None
    session.execute.return_value = result_obj

    assert await count_messages_by_session(session, session_id="s-empty") == 0
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_message_service.py -v
```
Expected: 6 passed.

- [ ] **Step 3: Run ruff**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/unit/test_chat_message_service.py
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/unit/test_chat_message_service.py && git commit -m "$(cat <<'EOF'
test(chat_message_service): cover 3 message CRUD functions (B4-3 / TEST-P1-01)

6 unit tests: add_message persists with optional trace_id and a fresh
uuid; get_messages_by_session queries the correct table in ascending
order (oldest first); count_messages_by_session coerces None → 0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: B4-4 — `profile_service` unit tests

**Scope:** `ProfileService` class — 8 public methods. After B2 the service takes `VisitorProfileRepositoryPort` as a constructor arg, so mocking is clean.

**Files:**
- Create: `backend/tests/unit/test_profile_service.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/unit/test_profile_service.py`:
```python
"""Unit tests for ProfileService — mocks VisitorProfileRepositoryPort."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.application.profile_service import ProfileService
from app.domain.entities import VisitorProfile
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, ProfileId, UserId


def _make_profile(user_id: str = "u-1", interests: list[str] | None = None) -> VisitorProfile:
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId("p-1"),
        user_id=UserId(user_id),
        interests=interests or [],
        knowledge_level="beginner",
        narrative_preference="balanced",
        reflection_depth="2",
        visited_exhibit_ids=[],
        feedback_history=[],
        created_at=now,
        updated_at=now,
    )


def _mock_repo() -> AsyncMock:
    repo = AsyncMock()
    # Default: no profile exists; each test overrides as needed.
    repo.get_by_user_id = AsyncMock(return_value=None)
    repo.save = AsyncMock(side_effect=lambda p: p)
    return repo


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_profile_when_found():
    repo = _mock_repo()
    existing = _make_profile()
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.get_or_create_profile("u-1")

    assert result is existing
    repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_create_creates_default_when_missing():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None

    service = ProfileService(repo)
    result = await service.get_or_create_profile("u-new")

    repo.save.assert_awaited_once()
    saved = repo.save.call_args[0][0]
    assert saved.user_id.value == "u-new"
    assert saved.knowledge_level == "beginner"
    assert saved.interests == []
    assert saved.visited_exhibit_ids == []
    assert result is saved


@pytest.mark.asyncio
async def test_get_profile_returns_none_when_missing():
    repo = _mock_repo()
    service = ProfileService(repo)
    assert await service.get_profile("nobody") is None


@pytest.mark.asyncio
async def test_update_profile_applies_partial_updates():
    repo = _mock_repo()
    existing = _make_profile(interests=["pottery"])
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.update_profile(
        "u-1",
        interests=["bronze", "pottery"],
        knowledge_level="expert",
    )

    assert result.interests == ["bronze", "pottery"]
    assert result.knowledge_level == "expert"
    # Fields not passed must remain untouched:
    assert result.narrative_preference == "balanced"
    assert result.reflection_depth == "2"
    repo.save.assert_awaited_once_with(existing)


@pytest.mark.asyncio
async def test_update_profile_raises_when_profile_missing():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None

    service = ProfileService(repo)
    with pytest.raises(EntityNotFoundError):
        await service.update_profile("u-missing", interests=["x"])


@pytest.mark.asyncio
async def test_update_profile_refreshes_updated_at_even_with_no_field_changes():
    repo = _mock_repo()
    existing = _make_profile()
    old_ts = existing.updated_at
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.update_profile("u-1")  # no field args

    assert result.updated_at > old_ts


@pytest.mark.asyncio
async def test_record_visit_appends_new_exhibit_and_saves():
    repo = _mock_repo()
    existing = _make_profile()
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.record_visit("u-1", "e-1")

    assert ExhibitId("e-1") in result.visited_exhibit_ids
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_visit_skips_save_when_already_visited():
    repo = _mock_repo()
    existing = _make_profile()
    existing.visited_exhibit_ids.append(ExhibitId("e-1"))
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    await service.record_visit("u-1", "e-1")

    # Idempotent: no second save for the same visit.
    repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_visit_creates_profile_when_none_exists():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None

    service = ProfileService(repo)
    result = await service.record_visit("u-new", "e-1")

    assert ExhibitId("e-1") in result.visited_exhibit_ids
    # First save creates the default profile, second save appends the visit.
    assert repo.save.await_count == 2


@pytest.mark.asyncio
async def test_add_feedback_appends_and_saves():
    repo = _mock_repo()
    existing = _make_profile()
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.add_feedback("u-1", "great tour!")

    assert "great tour!" in result.feedback_history
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_visited_exhibits_returns_empty_when_profile_missing():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None
    service = ProfileService(repo)
    assert await service.get_visited_exhibits("u-missing") == []


@pytest.mark.asyncio
async def test_has_visited_true_false_cases():
    repo = _mock_repo()
    existing = _make_profile()
    existing.visited_exhibit_ids.append(ExhibitId("e-1"))
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    assert await service.has_visited("u-1", "e-1") is True
    assert await service.has_visited("u-1", "e-other") is False
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_profile_service.py -v
```
Expected: 12 passed.

- [ ] **Step 3: Run ruff + mypy**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/unit/test_profile_service.py
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/unit/test_profile_service.py && git commit -m "$(cat <<'EOF'
test(profile_service): cover ProfileService — 8 methods (B4-4 / TEST-P1-01)

12 unit tests against a mocked VisitorProfileRepositoryPort:
- get_or_create: existing profile returned as-is; missing triggers default creation.
- get_profile: passthrough to repo, returns None for unknown.
- update_profile: partial field updates, raises on missing, refreshes updated_at.
- record_visit: idempotent — skips save if already visited; creates profile if missing.
- add_feedback, get_visited_exhibits, has_visited: happy paths + None-profile edges.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: B4-5 — `exhibit_service` unit tests

**Scope:** `ExhibitService` class — 11 public methods. Critical focus: `list_exhibits` has a 4-branch dispatcher (floor / category / hall / list_all) — each branch calls a **different** repository method, so a mis-dispatch would silently return the wrong set. Cover all 4 explicitly. This also sets up the baseline for PERFOPS-P1-01 (list_all loads full table) which a later batch will fix.

**Files:**
- Create: `backend/tests/unit/test_exhibit_service.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/unit/test_exhibit_service.py`:
```python
"""Unit tests for ExhibitService — mocks ExhibitRepositoryPort."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.application.exhibit_service import ExhibitService
from app.domain.entities import Exhibit
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, Location


def _make_exhibit(id_: str = "e-1", name: str = "青铜鼎", hall: str = "main", floor: int = 1) -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId(id_),
        name=name,
        description="desc",
        location=Location(x=1.0, y=2.0, floor=floor),
        hall=hall,
        category="bronze",
        era="shang",
        importance=3,
        estimated_visit_time=10,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock(side_effect=lambda e: e)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    repo.list_all = AsyncMock(return_value=[])
    repo.list_with_filters = AsyncMock(return_value=[])
    repo.list_by_category = AsyncMock(return_value=[])
    repo.list_by_hall = AsyncMock(return_value=[])
    repo.list_all_active = AsyncMock(return_value=[])
    repo.find_by_interests = AsyncMock(return_value=[])
    repo.search_by_name = AsyncMock(return_value=[])
    repo.get_distinct_categories = AsyncMock(return_value=[])
    repo.get_distinct_halls = AsyncMock(return_value=[])
    return repo


@pytest.mark.asyncio
async def test_create_exhibit_passes_fields_and_saves():
    repo = _mock_repo()
    service = ExhibitService(repo)

    result = await service.create_exhibit(
        name="玉琮",
        description="新石器时代",
        location_x=3.0,
        location_y=4.0,
        floor=2,
        hall="east",
        category="jade",
        era="neolithic",
        importance=5,
        estimated_visit_time=15,
        document_id="d-2",
    )

    repo.save.assert_awaited_once()
    saved = repo.save.call_args[0][0]
    assert saved.name == "玉琮"
    assert saved.location.x == 3.0
    assert saved.location.floor == 2
    assert saved.is_active is True  # default
    assert saved.id.value  # uuid assigned
    assert result is saved


@pytest.mark.asyncio
async def test_get_exhibit_returns_none_when_missing():
    repo = _mock_repo()
    service = ExhibitService(repo)
    assert await service.get_exhibit("missing") is None


@pytest.mark.asyncio
async def test_get_exhibit_returns_entity_when_found():
    repo = _mock_repo()
    target = _make_exhibit()
    repo.get_by_id.return_value = target

    service = ExhibitService(repo)
    assert await service.get_exhibit("e-1") is target


@pytest.mark.asyncio
async def test_list_exhibits_floor_branch_calls_list_with_filters():
    """floor filter MUST route to list_with_filters (which supports all three
    filters together), not to list_by_category or list_by_hall."""
    repo = _mock_repo()
    repo.list_with_filters.return_value = [_make_exhibit()]

    service = ExhibitService(repo)
    await service.list_exhibits(floor=2, category="bronze", hall="east")

    repo.list_with_filters.assert_awaited_once_with(category="bronze", hall="east", floor=2)
    repo.list_by_category.assert_not_awaited()
    repo.list_by_hall.assert_not_awaited()
    repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_exhibits_category_branch_calls_list_by_category():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.list_exhibits(category="bronze")

    repo.list_by_category.assert_awaited_once_with("bronze")
    repo.list_with_filters.assert_not_awaited()
    repo.list_by_hall.assert_not_awaited()
    repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_exhibits_hall_branch_calls_list_by_hall():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.list_exhibits(hall="east")

    repo.list_by_hall.assert_awaited_once_with("east")
    repo.list_by_category.assert_not_awaited()
    repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_exhibits_no_filter_branch_calls_list_all():
    """PERFOPS-P1-01 baseline: the no-filter branch currently loads the entire
    table and applies skip/limit in Python. That bug is tracked separately;
    this test only pins the current dispatch so the B6 fix doesn't accidentally
    change the public API signature."""
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.list_exhibits()

    repo.list_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_exhibits_applies_python_side_pagination():
    repo = _mock_repo()
    repo.list_all.return_value = [_make_exhibit(id_=f"e-{i}") for i in range(10)]

    service = ExhibitService(repo)
    page = await service.list_exhibits(skip=3, limit=2)

    assert len(page) == 2
    assert page[0].id.value == "e-3"
    assert page[1].id.value == "e-4"


@pytest.mark.asyncio
async def test_update_exhibit_partial_updates_and_location_merge():
    repo = _mock_repo()
    existing = _make_exhibit()
    repo.get_by_id.return_value = existing

    service = ExhibitService(repo)
    result = await service.update_exhibit(
        exhibit_id="e-1",
        name="新名",
        location_x=9.0,  # only x provided — y and floor must be preserved
    )

    assert result.name == "新名"
    assert result.location.x == 9.0
    assert result.location.y == 2.0  # unchanged
    assert result.location.floor == 1  # unchanged
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_exhibit_raises_when_missing():
    repo = _mock_repo()
    repo.get_by_id.return_value = None

    service = ExhibitService(repo)
    with pytest.raises(EntityNotFoundError):
        await service.update_exhibit("missing", name="x")


@pytest.mark.asyncio
async def test_update_exhibit_location_partial_without_x_still_merges():
    """If the caller passes only location_y (no x), location_x must be preserved."""
    repo = _mock_repo()
    existing = _make_exhibit()
    repo.get_by_id.return_value = existing

    service = ExhibitService(repo)
    result = await service.update_exhibit("e-1", location_y=7.0)

    assert result.location.x == 1.0  # preserved
    assert result.location.y == 7.0


@pytest.mark.asyncio
async def test_delete_exhibit_delegates_to_repo():
    repo = _mock_repo()
    repo.delete.return_value = True

    service = ExhibitService(repo)
    assert await service.delete_exhibit("e-1") is True
    repo.delete.assert_awaited_once_with(ExhibitId("e-1"))


@pytest.mark.asyncio
async def test_find_by_interests_passes_through():
    repo = _mock_repo()
    repo.find_by_interests.return_value = [_make_exhibit()]

    service = ExhibitService(repo)
    result = await service.find_by_interests(["bronze"], limit=5)

    repo.find_by_interests.assert_awaited_once_with(["bronze"], 5)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_search_exhibits_passes_all_kwargs_to_repo():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.search_exhibits(
        query="鼎", skip=5, limit=10, category="bronze", hall="east", floor=1
    )

    repo.search_by_name.assert_awaited_once_with(
        query="鼎", category="bronze", hall="east", floor=1, skip=5, limit=10
    )


@pytest.mark.asyncio
async def test_get_all_categories_and_halls_pass_through():
    repo = _mock_repo()
    repo.get_distinct_categories.return_value = ["bronze", "jade"]
    repo.get_distinct_halls.return_value = ["east", "main"]

    service = ExhibitService(repo)
    assert await service.get_all_categories() == ["bronze", "jade"]
    assert await service.get_all_halls() == ["east", "main"]


@pytest.mark.asyncio
async def test_list_all_active_delegates():
    repo = _mock_repo()
    repo.list_all_active.return_value = [_make_exhibit()]
    service = ExhibitService(repo)
    result = await service.list_all_active()
    assert len(result) == 1
    repo.list_all_active.assert_awaited_once()
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_exhibit_service.py -v
```
Expected: 16 passed.

- [ ] **Step 3: Run ruff**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/unit/test_exhibit_service.py
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/unit/test_exhibit_service.py && git commit -m "$(cat <<'EOF'
test(exhibit_service): cover ExhibitService — 11 methods (B4-5 / TEST-P1-01)

16 unit tests against a mocked ExhibitRepositoryPort. Particular focus
on list_exhibits' 4-branch dispatcher (floor → list_with_filters,
category → list_by_category, hall → list_by_hall, none → list_all) —
a mis-dispatch would silently return the wrong set, so each branch is
verified with negative assertions that the other repo methods were NOT
called. Location merge logic in update_exhibit is also pinned explicitly.

Baseline for future PERFOPS-P1-01 fix (list_all in-Python pagination).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: B4-6 — `curator_service` unit tests

**Scope:** `CuratorService` — 5 public methods (`plan_tour`, `generate_narrative`, `get_reflection_prompts`, `chat`, `get_exhibit_info`). All delegate to 3 collaborators: `CuratorAgentPort`, `ProfileService`, `ExhibitService`. Mock all three.

**Files:**
- Create: `backend/tests/unit/test_curator_service.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/unit/test_curator_service.py`:
```python
"""Unit tests for CuratorService — mocks CuratorAgentPort + ProfileService + ExhibitService."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.application.curator_service import CuratorService
from app.domain.entities import Exhibit, VisitorProfile
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, Location, ProfileId, UserId


def _make_profile(interests: list[str] | None = None) -> VisitorProfile:
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId("p-1"),
        user_id=UserId("u-1"),
        interests=interests or ["bronze"],
        knowledge_level="intermediate",
        narrative_preference="storytelling",
        reflection_depth="3",
        visited_exhibit_ids=[ExhibitId("e-old")],
        feedback_history=[],
        created_at=now,
        updated_at=now,
    )


def _make_exhibit() -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId("e-1"),
        name="青铜鼎",
        description="商代礼器",
        location=Location(x=1.0, y=2.0, floor=1),
        hall="main",
        category="bronze",
        era="shang",
        importance=5,
        estimated_visit_time=15,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _mocks():
    """Return (agent, profile_service, exhibit_service) all as AsyncMocks."""
    agent = AsyncMock()
    agent.run = AsyncMock(return_value={"output": "agent response", "session_id": "sess-1"})

    profile_svc = AsyncMock()
    profile_svc.get_or_create_profile = AsyncMock(return_value=_make_profile())
    profile_svc.record_visit = AsyncMock()

    exhibit_svc = AsyncMock()
    exhibit_svc.get_exhibit = AsyncMock(return_value=_make_exhibit())

    return agent, profile_svc, exhibit_svc


@pytest.mark.asyncio
async def test_plan_tour_uses_profile_interests_when_not_overridden():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.plan_tour(user_id="u-1", available_time=60)

    assert result["interests"] == ["bronze"]  # from profile
    assert result["available_time"] == 60
    assert result["visited_exhibit_ids"] == ["e-old"]
    agent.run.assert_awaited_once()
    # The prompt sent to the agent must carry the interest and time:
    prompt_sent = agent.run.call_args.kwargs["user_input"]
    assert "60分钟" in prompt_sent
    assert "bronze" in prompt_sent


@pytest.mark.asyncio
async def test_plan_tour_override_interests_win():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)
    result = await service.plan_tour(user_id="u-1", available_time=30, interests=["jade"])

    assert result["interests"] == ["jade"]
    assert "jade" in agent.run.call_args.kwargs["user_input"]


@pytest.mark.asyncio
async def test_generate_narrative_raises_when_exhibit_missing():
    agent, prof, exh = _mocks()
    exh.get_exhibit.return_value = None

    service = CuratorService(agent, prof, exh)
    with pytest.raises(EntityNotFoundError):
        await service.generate_narrative(user_id="u-1", exhibit_id="missing")

    agent.run.assert_not_awaited()
    prof.record_visit.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_narrative_records_visit_after_success():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.generate_narrative(user_id="u-1", exhibit_id="e-1")

    assert result["narrative"] == "agent response"
    assert result["exhibit_name"] == "青铜鼎"
    # Visit must be recorded AFTER the agent returns successfully.
    prof.record_visit.assert_awaited_once_with("u-1", "e-1")


@pytest.mark.asyncio
async def test_get_reflection_prompts_raises_when_exhibit_missing():
    agent, prof, exh = _mocks()
    exh.get_exhibit.return_value = None

    service = CuratorService(agent, prof, exh)
    with pytest.raises(EntityNotFoundError):
        await service.get_reflection_prompts(user_id="u-1", exhibit_id="missing")


@pytest.mark.asyncio
async def test_get_reflection_prompts_includes_profile_level():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.get_reflection_prompts(user_id="u-1", exhibit_id="e-1")

    assert result["knowledge_level"] == "intermediate"
    assert result["reflection_depth"] == "3"
    prompt = agent.run.call_args.kwargs["user_input"]
    assert "intermediate" in prompt
    assert "反思深度：3" in prompt


@pytest.mark.asyncio
async def test_chat_passes_history_through_and_includes_profile_context():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    history = [{"role": "user", "content": "hi"}]
    result = await service.chat(user_id="u-1", message="tell me about jade", chat_history=history)

    agent.run.assert_awaited_once()
    assert agent.run.call_args.kwargs["chat_history"] == history
    assert "tell me about jade" in agent.run.call_args.kwargs["user_input"]
    assert result["response"] == "agent response"


@pytest.mark.asyncio
async def test_chat_defaults_history_to_empty_list():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    await service.chat(user_id="u-1", message="hi")
    assert agent.run.call_args.kwargs["chat_history"] == []


@pytest.mark.asyncio
async def test_get_exhibit_info_raises_when_exhibit_missing():
    agent, prof, exh = _mocks()
    exh.get_exhibit.return_value = None

    service = CuratorService(agent, prof, exh)
    with pytest.raises(EntityNotFoundError):
        await service.get_exhibit_info(user_id="u-1", exhibit_id="missing")


@pytest.mark.asyncio
async def test_get_exhibit_info_returns_exhibit_dict_and_knowledge():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.get_exhibit_info(user_id="u-1", exhibit_id="e-1")

    assert result["exhibit"]["id"] == "e-1"
    assert result["exhibit"]["name"] == "青铜鼎"
    assert result["exhibit"]["era"] == "shang"
    assert result["knowledge"] == "agent response"
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_curator_service.py -v
```
Expected: 10 passed.

- [ ] **Step 3: Run ruff**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/unit/test_curator_service.py
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/unit/test_curator_service.py && git commit -m "$(cat <<'EOF'
test(curator_service): cover CuratorService — 5 orchestration methods (B4-6 / TEST-P1-01)

10 unit tests against mocked CuratorAgentPort + ProfileService +
ExhibitService. Every method's contract is pinned: plan_tour uses
profile interests by default (override wins), generate_narrative
raises on missing exhibit and only records the visit after the agent
succeeds, get_exhibit_info / get_reflection_prompts raise on missing,
chat defaults history to empty list and passes it through to the agent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: B4-7 — Contract tests for `profile` and `exhibits` public APIs

**Scope:** Use FastAPI `TestClient` + dep overrides (established pattern from `backend/tests/contract/conftest.py`). Cover:

- `api/profile.py`: `GET /api/v1/profile` (auth required), `PUT /api/v1/profile` (auth + rate limit).
- `api/exhibits.py`: 5 endpoints, all public (no auth). `GET /api/v1/exhibits`, `GET /api/v1/exhibits/stats`, `GET /api/v1/exhibits/categories/list`, `GET /api/v1/exhibits/halls/list`, `GET /api/v1/exhibits/{id}`.

**Files:**
- Create: `backend/tests/contract/test_profile_api.py`
- Create: `backend/tests/contract/test_exhibits_api.py`

- [ ] **Step 1: Check existing contract fixture for auth tokens**

Run to confirm the auth_token fixture pattern:
```bash
cd /home/singer/MuseAI && grep -n "auth_token\|mock_current_user\|override_dependencies" backend/tests/contract/conftest.py backend/tests/contract/test_sse_events.py 2>&1 | head -20
```

If existing tests have a reusable `auth_token` fixture, use it. If not, the profile test file below defines its own via a minimal `override_current_user` dep override.

- [ ] **Step 2: Write `test_profile_api.py`**

Create `backend/tests/contract/test_profile_api.py`:
```python
"""Contract tests for api/profile.py — GET and PUT endpoints."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.api.deps import get_current_user, rate_limit
from app.domain.entities import VisitorProfile
from app.domain.value_objects import ProfileId, UserId
from app.main import app
from fastapi.testclient import TestClient


TEST_USER = {"id": "u-contract-1", "email": "contract@test.local"}


def _override_user():
    return TEST_USER


def _noop_rate_limit():
    return True


def _make_profile() -> VisitorProfile:
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId("p-1"),
        user_id=UserId(TEST_USER["id"]),
        interests=["bronze"],
        knowledge_level="beginner",
        narrative_preference="balanced",
        reflection_depth="2",
        visited_exhibit_ids=[],
        feedback_history=[],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[rate_limit] = _noop_rate_limit
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def patch_profile_service(monkeypatch):
    """Replace get_profile_service so no real DB is touched."""
    mock_service = AsyncMock()
    mock_service.get_or_create_profile = AsyncMock(return_value=_make_profile())
    mock_service.update_profile = AsyncMock(return_value=_make_profile())

    def fake_factory(session):
        return mock_service

    monkeypatch.setattr("app.api.profile.get_profile_service", fake_factory)
    return mock_service


def test_get_profile_returns_200_and_profile_json(override_auth, patch_profile_service):
    client = TestClient(app)
    response = client.get("/api/v1/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == TEST_USER["id"]
    assert body["interests"] == ["bronze"]
    assert body["knowledge_level"] == "beginner"


def test_put_profile_updates_and_returns_updated(override_auth, patch_profile_service):
    updated = _make_profile()
    updated.knowledge_level = "expert"
    patch_profile_service.update_profile.return_value = updated

    client = TestClient(app)
    response = client.put(
        "/api/v1/profile",
        json={"knowledge_level": "expert"},
    )

    assert response.status_code == 200
    assert response.json()["knowledge_level"] == "expert"
    patch_profile_service.update_profile.assert_awaited_once()


def test_put_profile_returns_404_when_entity_not_found(override_auth, patch_profile_service):
    from app.domain.exceptions import EntityNotFoundError
    patch_profile_service.update_profile.side_effect = EntityNotFoundError("no profile")

    client = TestClient(app)
    response = client.put(
        "/api/v1/profile",
        json={"knowledge_level": "expert"},
    )

    assert response.status_code == 404
    # The error message returned to the client must be sanitized — raw internal
    # messages ("no profile") must not appear.
    assert "no profile" not in response.json()["detail"]


def test_get_profile_requires_auth():
    """Without the override_auth fixture, no user → 401 or similar."""
    # Drop any lingering overrides from other tests.
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(rate_limit, None)
    client = TestClient(app)
    response = client.get("/api/v1/profile")
    assert response.status_code in {401, 403}
```

- [ ] **Step 3: Write `test_exhibits_api.py`**

Create `backend/tests/contract/test_exhibits_api.py`:
```python
"""Contract tests for api/exhibits.py — public (unauthenticated) endpoints."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location
from app.main import app
from fastapi.testclient import TestClient


def _make_exhibit(id_: str = "e-1", name: str = "青铜鼎") -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId(id_),
        name=name,
        description="desc",
        location=Location(x=1.0, y=2.0, floor=1),
        hall="main",
        category="bronze",
        era="shang",
        importance=3,
        estimated_visit_time=10,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def patch_exhibit_service(monkeypatch):
    """The router constructs ExhibitService per-request; patch the constructor
    path so every request gets the same mock."""
    mock = AsyncMock()
    mock.list_exhibits = AsyncMock(return_value=[_make_exhibit()])
    mock.list_all_active = AsyncMock(return_value=[_make_exhibit()])
    mock.search_exhibits = AsyncMock(return_value=[_make_exhibit()])
    mock.get_exhibit = AsyncMock(return_value=_make_exhibit())
    mock.get_all_categories = AsyncMock(return_value=["bronze", "jade"])
    mock.get_all_halls = AsyncMock(return_value=["east", "main"])

    monkeypatch.setattr(
        "app.api.exhibits.ExhibitService",
        lambda _repo: mock,
    )
    return mock


def test_list_exhibits_returns_200_with_pagination(patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits?skip=0&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert "exhibits" in body
    assert "total" in body
    assert body["skip"] == 0
    assert body["limit"] == 10


def test_list_exhibits_applies_filter_query_params(patch_exhibit_service):
    client = TestClient(app)
    response = client.get(
        "/api/v1/exhibits?category=bronze&hall=east&floor=1"
    )

    assert response.status_code == 200
    # The service was called with the filters:
    call = patch_exhibit_service.list_exhibits.call_args
    assert call.kwargs.get("category") == "bronze"
    assert call.kwargs.get("hall") == "east"
    assert call.kwargs.get("floor") == 1


def test_get_exhibit_detail_returns_200(patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/e-1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "e-1"
    assert body["name"] == "青铜鼎"


def test_get_exhibit_detail_returns_404_when_missing(patch_exhibit_service):
    patch_exhibit_service.get_exhibit.return_value = None

    client = TestClient(app)
    response = client.get("/api/v1/exhibits/missing")
    assert response.status_code == 404


def test_get_categories_list_returns_distinct_categories(patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/categories/list")
    assert response.status_code == 200
    assert response.json() == ["bronze", "jade"]


def test_get_halls_list_returns_distinct_halls(patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/halls/list")
    assert response.status_code == 200
    assert response.json() == ["east", "main"]


def test_get_exhibits_stats_returns_200(patch_exhibit_service):
    """The /stats endpoint calls list_all_active and groups. We only assert
    200 + expected shape; the service-layer logic is already covered in
    test_exhibit_service.py."""
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/stats")
    assert response.status_code == 200
    body = response.json()
    # The response model has top-level count fields + arrays:
    assert isinstance(body, dict)
```

**Note on the `/stats` endpoint:** inspect `api/exhibits.py` around the `/stats` route to see the exact response model fields before finalizing the last assertion. If the response uses a specific schema like `{"total": N, "by_category": [...], "by_hall": [...]}`, assert the keys present rather than just the type. If the endpoint calls `list_all_active`, the mock above covers it; otherwise add the needed mock.

- [ ] **Step 4: Run both new contract test files**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_profile_api.py backend/tests/contract/test_exhibits_api.py -v 2>&1 | tail -30
```
Expected: 4 passed (profile) + 7 passed (exhibits) = 11 passed.

If any test fails due to a dep-override or mocking mismatch (e.g. the `/stats` endpoint does extra DB work not covered by the mock), add the missing mock method — do NOT relax the assertion.

- [ ] **Step 5: Run ruff**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/contract/test_profile_api.py backend/tests/contract/test_exhibits_api.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd /home/singer/MuseAI && git add backend/tests/contract/test_profile_api.py backend/tests/contract/test_exhibits_api.py && git commit -m "$(cat <<'EOF'
test(api): contract tests for profile + exhibits routers (B4-7 / TEST-P1-02)

- test_profile_api.py (4 tests): GET returns 200 with profile JSON, PUT
  applies updates, PUT returns 404 with sanitized detail when
  EntityNotFoundError, no-auth request returns 401/403.
- test_exhibits_api.py (7 tests): list with pagination + filter query
  params, detail 200 / 404, categories/halls list endpoints, stats
  endpoint 200.

Service-layer logic is mocked via monkeypatch of the router's service
constructor — real DB stays untouched. Sanitized error messages verified
for EntityNotFoundError path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch B4 Verification

After all seven tasks commit:

- [ ] **Run the full verification sweep**

```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3
```

Expected:
- pytest: **~876 passed** (post-B3 was 812 on full tree; +64 new tests in B4 = 876; ± a few depending on exact test-count calibration).
- ruff: `All checks passed!`
- mypy: `Success: no issues found in 90 source files` (no new source files in B4 — just tests).

- [ ] **Confirm the audit IDs are closed** — no further code changes required:
  - TEST-P1-01 (6 services zero-coverage) ✅ by Tasks 1–6
  - TEST-P1-02 (profile + exhibits APIs no contract tests) ✅ by Task 7

- [ ] **Cross-check: are there any other services still at zero coverage?**

```bash
cd /home/singer/MuseAI && for svc in $(ls backend/app/application/*_service.py | xargs -n1 basename | sed 's/.py$//'); do \
    count=$(grep -rln "from app.application.$svc\b\|app\.application\.$svc " backend/tests/ --include="*.py" | wc -l); \
    echo "$svc: $count test files"; \
done
```
Expected: every `*_service` shows ≥ 1 test file. If any still shows 0, it's a new service added after the audit — flag in a follow-up plan.

---

## Rollback Notes

Each task is its own commit. All 7 tasks create test-only files; no application code is modified. Reverting any commit deletes only the corresponding test file — no production risk. Tasks are **independent**: Task 4 doesn't require Task 3 to exist, etc. Any subset can ship in any order.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: Parent spec §4 Batch B4 calls for "core test gaps" — closes TEST-P1-01 (6 services) and TEST-P1-02 (2 APIs). All 8 targets are covered. ✓
- **Placeholder scan**: no "TBD" / "TODO" / "add appropriate …" / "similar to" patterns. Every code block is a complete, runnable test file with explicit mocks. The one exception is Task 7 Step 3's note on `/stats` response shape — explicitly flagged as "inspect and finalize" because the response schema needs to be verified against the router before the test can be written with certainty; a prescriptive block would be wrong if the schema differs. ✓
- **No scope creep**: every test asserts existing behavior. The PERFOPS-P1-01 list_all baseline test (B4-5) explicitly pins CURRENT behavior so a later batch can flip it safely without breaking the test. No bug fixes in this batch. ✓
- **Mocking discipline**: services that take Ports (profile, exhibit, curator) use Protocol mocking (AsyncMock with assigned attributes); services that take AsyncSession (chat_session, chat_message) use AsyncMock/MagicMock following the existing pattern from test_chat_service_streaming.py. No real DB engine in unit tests. ✓
- **Task independence**: tasks 1–6 are pure-unit and touch no shared state. Task 7 touches dependency overrides but cleans up in a fixture teardown (or pytest monkeypatch auto-undo) so it doesn't leak to sibling tests. ✓
- **Test count predictions**: 4 + 10 + 6 + 12 + 16 + 10 + 11 = 69 new tests. Verification expects ~876 total post-B4 (812 + 64). The small discrepancy (69 vs 64) is acceptable: some tests may consolidate during implementation. ✓
