# B6 Performance & Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two performance/observability gaps in ~1.5 person-days: (1) push exhibit listing pagination from Python to SQL so large tables don't cause a full-scan cliff (PERFOPS-P1-01); (2) bridge the request-scope `request_id` (from the HTTP middleware) into the chat-scope `trace_id` so logs across a single SSE request correlate (PERFOPS-P1-03).

**Scope boundary — what this batch does NOT do (intentional):**

1. **PERFOPS-P2-05 (MAX_LIMIT caps on list endpoints) is already closed.** Grep shows every `limit: int = Query(...)` already carries `le=...` (admin/exhibits `le=1000`, admin/prompts `le=100`, public exhibits/chat/documents `le=100–200`). No work needed.
2. **Non-exhibit repositories** (prompt, document, chat sessions) already accept `limit`/`offset` at the Port boundary and push to SQL. PERFOPS-P1-01 specifically flagged `exhibit_service.list_exhibits` — only that dispatcher does in-Python pagination. Other services are clean; do not touch them.
3. **`list_all_active` stays full-load.** It feeds aggregate stats endpoints (`/api/v1/exhibits/stats`, admin stats) that need ALL active rows to count distinct categories/halls/floors. Adding pagination here would break those endpoints. Only the 4 list methods used by the paginated dispatcher (`list_all`, `list_by_category`, `list_by_hall`, `list_with_filters`) gain pagination.
4. **`trace_id` persistence in `chat_messages` row is untouched.** The DB column stays as-is; only logging gets the bridge. Changing the DB schema would require a migration — out of scope.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, loguru, `contextvars.ContextVar`, pytest, uv.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B6.

**Related audit findings:** PERFOPS-P1-01, PERFOPS-P1-03.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/application/ports/repositories.py` | Modify | Add `skip: int = 0, limit: int = 100` kwargs to `list_all`, `list_by_category`, `list_by_hall`, `list_with_filters` |
| `backend/app/infra/postgres/adapters/exhibit.py` | Modify | Push `.offset(skip).limit(limit)` into each of the 4 queries |
| `backend/app/application/exhibit_service.py` | Modify | `list_exhibits` passes `skip`/`limit` through to repo; drop Python slicing |
| `backend/tests/unit/test_exhibit_service.py` | Modify | Flip `test_list_exhibits_applies_python_side_pagination` → SQL version; update the 4 branch tests to assert skip/limit forwarded |
| `backend/app/observability/context.py` | Create | `request_id_var: ContextVar[str \| None]` — tiny module |
| `backend/app/observability/middleware.py` | Modify | Set `request_id_var` on request entry; reset on exit |
| `backend/app/application/chat_stream_service.py` | Modify | Read `request_id_var` at entry; use `logger.bind(trace_id=..., request_id=...)` wherever the service currently logs |
| `backend/tests/unit/test_observability_context.py` | Create | ContextVar behavior: isolation across async tasks, None when unset |
| `backend/tests/contract/test_request_id_bridge.py` | Create | End-to-end: request to `/api/v1/chat/sessions/{id}/ask-stream` carries the X-Request-ID through to the SSE `done` event's log output |

No other files change.

---

## Task 1: B6-1 — Push exhibit listing pagination to SQL (PERFOPS-P1-01)

**Scope:** Four Port methods and the adapter that implements them gain `skip`/`limit` parameters; the service's `list_exhibits` hands them through. The ExhibitService.list_exhibits signature is unchanged from the caller's perspective — it already takes `skip`/`limit` — but internally it now sends those values to the repo instead of Python-slicing.

**Breaking-change risk:** `ExhibitRepositoryPort` is a Protocol. Adding kwargs with defaults is backward compatible for **callers** but any test or implementation that `assert_awaited_once_with(...)` on the old signature will fail. The only existing production caller is `exhibit_service.list_exhibits` (updated in this task). Tests are updated in Step 5.

**Files:**
- Modify: `backend/app/application/ports/repositories.py`
- Modify: `backend/app/infra/postgres/adapters/exhibit.py`
- Modify: `backend/app/application/exhibit_service.py`
- Modify: `backend/tests/unit/test_exhibit_service.py`

- [ ] **Step 1: Capture baseline — all exhibit tests currently green**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_exhibit_service.py backend/tests/unit/test_repositories.py backend/tests/contract/test_exhibits_api.py -v 2>&1 | tail -10
```
Expected: all pass. Record the count.

- [ ] **Step 2: Update Port signatures in `application/ports/repositories.py`**

Replace the `ExhibitRepositoryPort` block's 4 list methods (lines 58–75 in the current file) with:
```python
    async def list_all(
        self,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]: ...

    async def list_all_active(self) -> list[Exhibit]: ...

    async def list_by_category(
        self,
        category: str,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]: ...

    async def list_by_hall(
        self,
        hall: str,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]: ...

    async def list_with_filters(
        self,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]: ...
```
Leave `list_all_active`, `find_by_interests`, `search_by_name` etc. untouched. `search_by_name` already has skip/limit.

- [ ] **Step 3: Update the adapter in `infra/postgres/adapters/exhibit.py`**

Replace the 4 corresponding methods. Locations are around lines 42–65 currently. Reference implementation pattern — one per method:

```python
    async def list_all(
        self,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_by_category(
        self,
        category: str,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.category == category)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_by_hall(
        self,
        hall: str,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.hall == hall)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_with_filters(
        self,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.is_active.is_(True))
        if category is not None:
            query = query.where(ExhibitORM.category == category)
        if hall is not None:
            query = query.where(ExhibitORM.hall == hall)
        if floor is not None:
            query = query.where(ExhibitORM.floor == floor)
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]
```

**If the existing `list_with_filters` has a different implementation shape** (e.g. its current version doesn't already filter by `is_active`), keep its semantics and only add the `.order_by(...).offset(skip).limit(limit)` chain. Read the current method before writing to confirm.

Rationale for `order_by(created_at desc)`: pagination without explicit ordering is non-deterministic. `created_at desc` matches the implicit "newest first" user expectation and uses the index added in `002_add_created_at_indexes.py` (already live in migrations).

- [ ] **Step 4: Update `exhibit_service.list_exhibits` to forward skip/limit**

Edit `backend/app/application/exhibit_service.py` — the `list_exhibits` method (around lines 80–115). Replace its body with:
```python
    async def list_exhibits(
        self,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
    ) -> list[Exhibit]:
        """Paginated exhibit listing. Pagination is applied in SQL (PERFOPS-P1-01).

        Dispatch matches the 4-branch rule pinned in test_exhibit_service.py:
        - floor present → list_with_filters (handles all 3 filters together)
        - category alone → list_by_category
        - hall alone → list_by_hall
        - no filter → list_all
        """
        if floor is not None:
            return await self._repository.list_with_filters(
                category=category,
                hall=hall,
                floor=floor,
                skip=skip,
                limit=limit,
            )
        if category:
            return await self._repository.list_by_category(category, skip=skip, limit=limit)
        if hall:
            return await self._repository.list_by_hall(hall, skip=skip, limit=limit)
        return await self._repository.list_all(skip=skip, limit=limit)
```

**Important:** the default `limit` changed from 100 (from the original `exhibit_service.py:83`) to 100. Keep whatever default was there originally — if it was 20, keep 20. Match the existing caller's expectation so `GET /api/v1/exhibits?limit=` behavior is unchanged.

- [ ] **Step 5: Update `test_exhibit_service.py` — flip the two Python-slice tests, update branch assertions**

Edit `backend/tests/unit/test_exhibit_service.py`:

(a) The 4 branch tests (`test_list_exhibits_floor_branch_calls_list_with_filters`, `..._category_branch_calls_list_by_category`, `..._hall_branch_calls_list_by_hall`, `..._no_filter_branch_calls_list_all`) previously asserted the repo was called with specific kwargs. Update each assertion to include `skip=0, limit=100` (or whatever default the service uses):

Example for the floor branch test:
```python
@pytest.mark.asyncio
async def test_list_exhibits_floor_branch_calls_list_with_filters():
    repo = _mock_repo()
    repo.list_with_filters.return_value = [_make_exhibit()]

    service = ExhibitService(repo)
    await service.list_exhibits(floor=2, category="bronze", hall="east")

    repo.list_with_filters.assert_awaited_once_with(
        category="bronze", hall="east", floor=2, skip=0, limit=100
    )
    repo.list_by_category.assert_not_awaited()
    repo.list_by_hall.assert_not_awaited()
    repo.list_all.assert_not_awaited()
```
Same pattern for category, hall, and no-filter branches.

(b) Replace the old `test_list_exhibits_applies_python_side_pagination` (currently asserts Python slicing at lines 141–151) with a test that asserts SQL-side pagination:
```python
@pytest.mark.asyncio
async def test_list_exhibits_forwards_skip_and_limit_to_repo():
    """PERFOPS-P1-01: pagination is now applied in SQL, not Python. The
    service must forward skip/limit to the repository — no local slicing."""
    repo = _mock_repo()
    repo.list_all.return_value = [_make_exhibit(id_=f"e-{i}") for i in range(2)]

    service = ExhibitService(repo)
    page = await service.list_exhibits(skip=3, limit=2)

    repo.list_all.assert_awaited_once_with(skip=3, limit=2)
    # The service returns exactly what the repo returned — no extra slicing.
    assert len(page) == 2
```

- [ ] **Step 6: Run the exhibit tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_exhibit_service.py -v 2>&1 | tail -25
```
Expected: all 16 pass. The updated 4 branch tests and the flipped pagination test all green.

- [ ] **Step 7: Run the repository test file + contract tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_repositories.py backend/tests/contract/test_exhibits_api.py -v 2>&1 | tail -20
```
Expected: all pass. If `test_repositories.py` has direct assertions on the old Port signature (e.g. it does `await repo.list_all()` and inspects the result), the tests should still work because kwargs have defaults. If any test explicitly mocks the old 1-arg signature with `assert_awaited_once_with(include_inactive=False)`, update it.

- [ ] **Step 8: Full verification sweep**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3
```
Expected: all green. Same 893 passing count (no new tests added yet — Task 2 adds 10ish).

- [ ] **Step 9: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/application/ports/repositories.py backend/app/infra/postgres/adapters/exhibit.py backend/app/application/exhibit_service.py backend/tests/unit/test_exhibit_service.py && git commit -m "$(cat <<'EOF'
perf(exhibit): push list pagination from Python to SQL (PERFOPS-P1-01)

list_all / list_by_category / list_by_hall / list_with_filters now
accept skip/limit (default 0/100) and apply them in SQL via .offset().limit().
exhibit_service.list_exhibits forwards the caller's pagination through
the Port instead of loading the entire table and slicing the Python list.

Queries now carry an explicit ORDER BY created_at DESC so pagination is
deterministic — leverages the created_at index added in migration 002.

Closes PERFOPS-P1-01. Unchanged: list_all_active (feeds aggregate stats),
find_by_interests (already capped via `limit` kwarg).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: B6-2 — Bridge `trace_id` and `request_id` via ContextVar (PERFOPS-P1-03)

**Scope:** Logs emitted from within a single HTTP request should carry BOTH:
- `request_id` — generated by `RequestLoggingMiddleware` (already exists), maps to the `X-Request-ID` header.
- `trace_id` — generated per chat/SSE invocation inside `chat_stream_service`.

Currently the two are generated in different stack frames and never meet. Bridge them via a request-scoped `ContextVar` set by the middleware and read by the chat stream service.

**Why ContextVar and not FastAPI `Request.state`:** FastAPI's `Request` object isn't easily passed through every async helper; ContextVar propagates automatically through `asyncio.create_task` and async generators (which is exactly what the SSE stream is).

**Files:**
- Create: `backend/app/observability/context.py`
- Modify: `backend/app/observability/middleware.py`
- Modify: `backend/app/application/chat_stream_service.py`
- Create: `backend/tests/unit/test_observability_context.py`
- Create: `backend/tests/contract/test_request_id_bridge.py`

- [ ] **Step 1: Write the unit test for the ContextVar module (TDD red phase)**

Create `backend/tests/unit/test_observability_context.py`:
```python
"""Unit tests for the request_id ContextVar."""
import asyncio

import pytest


def test_request_id_var_default_is_none():
    from app.observability.context import request_id_var
    assert request_id_var.get() is None


def test_request_id_var_set_and_get():
    from app.observability.context import request_id_var

    token = request_id_var.set("req-123")
    try:
        assert request_id_var.get() == "req-123"
    finally:
        request_id_var.reset(token)

    assert request_id_var.get() is None


@pytest.mark.asyncio
async def test_request_id_var_isolated_across_concurrent_tasks():
    """ContextVar must give each asyncio task its own value — otherwise two
    concurrent requests would see each other's request_id."""
    from app.observability.context import request_id_var

    async def set_and_read(expected: str) -> str | None:
        token = request_id_var.set(expected)
        try:
            await asyncio.sleep(0)  # yield to scheduler
            return request_id_var.get()
        finally:
            request_id_var.reset(token)

    results = await asyncio.gather(
        set_and_read("req-A"),
        set_and_read("req-B"),
        set_and_read("req-C"),
    )
    assert results == ["req-A", "req-B", "req-C"]


@pytest.mark.asyncio
async def test_request_id_var_propagates_into_child_task():
    """A child task spawned inside a request must inherit the parent's context."""
    from app.observability.context import request_id_var

    seen: list[str | None] = []

    async def child():
        seen.append(request_id_var.get())

    token = request_id_var.set("req-parent")
    try:
        await asyncio.create_task(child())
    finally:
        request_id_var.reset(token)

    assert seen == ["req-parent"]
```

- [ ] **Step 2: Run the test — 4 failures with ImportError (RED)**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_observability_context.py -v 2>&1 | tail -15
```
Expected: 4 ERROR / FAIL with `ModuleNotFoundError: No module named 'app.observability.context'`.

- [ ] **Step 3: Create the ContextVar module**

Create `backend/app/observability/context.py`:
```python
"""Request-scoped ContextVars for cross-layer log correlation.

RequestLoggingMiddleware sets request_id_var at request entry. Any async
code executing within that request (including async generators used by
SSE streaming) can read it and bind it to log records via
`logger.bind(request_id=request_id_var.get())`.

ContextVar is the right primitive here because:
- values propagate automatically through asyncio.create_task and async
  generators (unlike plain module globals, which would leak between
  concurrent requests).
- reset() on task exit restores the previous value, so nested requests
  (none in our code today, but future-proof) work correctly.
"""
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
```

- [ ] **Step 4: Re-run — all 4 tests PASS (GREEN)**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_observability_context.py -v 2>&1 | tail -15
```
Expected: 4 passed.

- [ ] **Step 5: Wire the ContextVar into `RequestLoggingMiddleware`**

Edit `backend/app/observability/middleware.py`. Add import near the top:
```python
from app.observability.context import request_id_var
```

Modify the `dispatch` method so the request_id is set at entry and reset at exit. The correct shape is to wrap the body in a `try/finally`:

Old (around line 32–107):
```python
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()
        # ... existing body ...
```

New — minimal diff, add ContextVar set/reset:
```python
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        try:
            start_time = time.perf_counter()
            # ... existing body (unchanged) ...
        finally:
            request_id_var.reset(token)
```
The entire existing body — logging, response building, exception handling — stays inside the `try`. Only the `token = ... ; try: ... ; finally: reset` wrapper is added.

- [ ] **Step 6: Wire the bridge into `chat_stream_service`**

Edit `backend/app/application/chat_stream_service.py`. Add import (after the other `from app.application...` imports):
```python
from app.observability.context import request_id_var
```

Find every `logger.debug(...)` / `logger.error(...)` / `logger.warning(...)` / `logger.exception(...)` call in the file (grep for `logger\.`) and wrap each into a `.bind(...)` call that includes both trace_id and request_id. Pattern:

Before:
```python
logger.debug(f"RAG result keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
```

After:
```python
logger.bind(trace_id=trace_id, request_id=request_id_var.get()).debug(
    f"RAG result keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}"
)
```

There are approximately 6–8 such call sites in `chat_stream_service.py`. Each must be bridged. Use a local alias at the top of each function that logs, so the refactor is terse:
```python
async def ask_question_stream_with_rag(...):
    ...
    trace_id = str(uuid.uuid4())
    _log = logger.bind(trace_id=trace_id, request_id=request_id_var.get())
    ...
    _log.debug(f"RAG result keys: ...")
```
This is cleaner than repeating `.bind(...)` on every call.

**Do not change the SSE payloads.** The `trace_id` that appears in the `done` event body must remain exactly as it is — this is a wire-protocol-locked field pinned by B3's contract test. Only logger calls get the bridge.

- [ ] **Step 7: Write the end-to-end contract test**

Create `backend/tests/contract/test_request_id_bridge.py`:
```python
"""PERFOPS-P1-03: logs emitted during a chat SSE request must carry BOTH
request_id (from HTTP middleware) and trace_id (from chat_stream_service).
This test captures loguru output and asserts both IDs appear bound to a
log record emitted from within the chat stream handler."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.main import app
from fastapi.testclient import TestClient
from loguru import logger


@pytest.fixture
def captured_logs():
    """Capture loguru records to an in-memory sink."""
    records: list[dict] = []

    def sink(message):
        records.append(dict(message.record["extra"]))

    handler_id = logger.add(sink, level="DEBUG")
    yield records
    logger.remove(handler_id)


@pytest.fixture
def patch_chat_stream(monkeypatch):
    """Replace the dependencies the chat-stream endpoint needs so we can
    focus on log-field assertions without hitting the real pipeline."""
    from app.api.deps import (
        get_current_user,
        get_db_session,
        get_db_session_maker,
        get_llm_provider,
        get_rag_agent,
    )

    # Fake session + auth
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1"}

    class _FakeSession:
        async def execute(self, *a, **k):
            # Return "session found" for the ownership check.
            from types import SimpleNamespace
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(
                id="s-1", user_id="u-1"
            ))
        async def commit(self):
            return None

    app.dependency_overrides[get_db_session] = lambda: _FakeSession()
    app.dependency_overrides[get_db_session_maker] = lambda: MagicMock()

    # Minimal LLM streaming to end the generator promptly
    mock_llm = MagicMock()
    async def _stream(messages):
        for chunk in ["Hello"]:
            yield chunk
    mock_llm.generate_stream = _stream
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm

    mock_rag = MagicMock()
    mock_rag.run = AsyncMock(return_value={
        "answer": "Hello", "documents": [], "reranked_documents": [],
        "retrieval_score": 0.9, "rewritten_query": "hi", "transformations": [],
    })
    mock_rag.score_threshold = 0.5
    mock_rag.prompt_gateway = None
    app.dependency_overrides[get_rag_agent] = lambda: mock_rag

    yield

    for dep in (get_current_user, get_db_session, get_db_session_maker,
                get_llm_provider, get_rag_agent):
        app.dependency_overrides.pop(dep, None)


def test_request_id_and_trace_id_both_appear_in_logs(patch_chat_stream, captured_logs):
    client = TestClient(app)
    req_id = "bridge-test-req-001"

    with client.stream(
        "POST",
        "/api/v1/chat/sessions/s-1/ask-stream",
        json={"message": "hi"},
        headers={"X-Request-ID": req_id},
    ) as response:
        # Consume the stream
        for _ in response.iter_lines():
            pass
        assert response.status_code == 200

    # Find at least one log record that carries BOTH request_id and trace_id.
    bridged = [
        r for r in captured_logs
        if r.get("request_id") == req_id and r.get("trace_id") is not None
    ]
    assert bridged, (
        f"No log record carries both request_id={req_id!r} and a trace_id. "
        f"Captured extras: {captured_logs[-5:]}"
    )
```

**Note:** this test is the end-to-end proof that the bridge works. If `chat_stream_service` has no `logger.debug/info/...` calls along the happy path (the RAG path has a few at `logger.debug(f"RAG result keys: ...")` etc.), the assertion will fail and guide the implementer to ensure at least one bridged log call is reached per request. The default RAG path logs `"RAG result keys"` and `"documents count"` — those will trigger.

- [ ] **Step 8: Run the bridge contract test**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_request_id_bridge.py -v 2>&1 | tail -15
```
Expected: passes. If it fails with "no bridged log record", inspect `captured_logs` output and confirm `chat_stream_service` is emitting at least one bridged log on the happy path. The RAG path should hit `_log.debug(f"RAG result keys: ...")` line and populate the record.

- [ ] **Step 9: Full verification sweep**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3
```
Expected: 898 passed (was 893; +4 context unit tests + 1 contract test = +5). Lint/type clean.

- [ ] **Step 10: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/observability/context.py backend/app/observability/middleware.py backend/app/application/chat_stream_service.py backend/tests/unit/test_observability_context.py backend/tests/contract/test_request_id_bridge.py && git commit -m "$(cat <<'EOF'
feat(observability): bridge trace_id and request_id via ContextVar (PERFOPS-P1-03)

New module app/observability/context.py exposes request_id_var: a
ContextVar set by RequestLoggingMiddleware on request entry and reset
on exit. chat_stream_service reads it at handler entry and binds both
trace_id and request_id to every log record via logger.bind(), so all
logs emitted during a single SSE request now correlate across layers.

Four ContextVar unit tests pin the isolation behavior (each task sees
its own value, child tasks inherit parent's). One end-to-end contract
test asserts that a request with an X-Request-ID header produces at
least one log record carrying both IDs bound.

Wire protocol unchanged: the trace_id in the SSE 'done' event body is
still generated and emitted exactly as before — the bridge only enriches
server-side log records.

Closes PERFOPS-P1-03.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch B6 Verification

After both tasks commit:

- [ ] **Run the full verification sweep**

```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3
```

Expected:
- pytest: ~898 passed (post-B5 was 893; B6-1 shifts existing tests with no net count change; B6-2 adds 5 new)
- ruff: `All checks passed!`
- mypy: `Success: no issues found in 91 source files` (+1 new file: `observability/context.py`)

- [ ] **Confirm the audit IDs are closed:**
  - PERFOPS-P1-01 (exhibit list_all Python slicing) ✅ by Task 1
  - PERFOPS-P1-03 (trace_id / request_id bridge) ✅ by Task 2

- [ ] **Audit IDs explicitly NOT closed (deferred by design):**
  - PERFOPS-P2-05 (MAX_LIMIT caps) — already in place, no work needed
  - PERFOPS-P2-01 (Alembic CONCURRENTLY) — separate batch if large-table pressure materializes
  - PERFOPS-P2-02 (DB pool sizing) — separate batch when we have ops metrics
  - PERFOPS-P2-03 (tour event fire-and-forget) — accept current tradeoff

---

## Rollback Notes

Task 1 changes the ExhibitRepositoryPort signature; reverting requires re-adding Python slicing to `exhibit_service.list_exhibits`. No data migration involved. Safe.

Task 2 is purely additive — the ContextVar defaults to None when unset, so reverting the middleware change simply leaves chat logs without a `request_id` field. No production-data impact.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: Parent-spec §4 Batch B6 calls for performance fixes. This plan handles the two highest-impact items (PERFOPS-P1-01, P1-03) and documents why P2-05 is already closed. ✓
- **Placeholder scan**: no "TBD" / "TODO". One explicit conditional in Task 1 Step 3 ("if the existing list_with_filters has a different shape, keep its semantics") is bracketed with a clear directive to read before writing. ✓
- **Wire-protocol preservation**: the `trace_id` in SSE `done` event bodies is **not** changed by B6-2 — only log bindings are. Called out explicitly in Step 6 and in the commit message. ✓
- **No new Port callers get pagination pushed down unnecessarily**: the 4 list methods that gain skip/limit are the ones used by the paginated dispatcher. `list_all_active`, `find_by_interests`, and `search_by_name` are untouched. ✓
- **Test updates are tightly scoped**: Task 1 Step 5 updates 5 tests in `test_exhibit_service.py`. No other test files need changes (prompt_cache, repositories integration test use `list_all` with defaults — backward compatible). ✓
