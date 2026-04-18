# B3 SSE Contract Extraction & Tour Stream Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close SYS-3 (SSE event strings duplicated in 18+ literals), CQ-P1-01 (same), and PERFOPS-P1-02 (`tour_chat_service` emits `error` then `done` on exception) in ~1–1.5 person-days. Preserve **both** wire protocols exactly (frontend consumes them already).

**Architecture constraints discovered during planning (important — do not re-litigate):**

1. **Two SSE schemas already exist and are frozen by the frontend:**
   - Chat stream (`chat_stream_service.py` → `useChat.js`) uses `{"type": <name>, ...}` (flat payload). Event names: `thinking`, `chunk`, `done`, `error`, `rag_step`.
   - Tour stream (`tour_chat_service.py` → `useTour.js`) uses `{"event": <name>, "data": {...}}` OR `{"event": <name>, <flat-fields>}` (inconsistent even within tour — `done` is flat, `error`/`chunk` have `data`). Event names: `chunk`, `done`, `error`.
   - **Do NOT unify the two schemas.** Frontend would break. B3 preserves current wire bytes exactly.

2. **The `chat_stream_service` "zero tests" claim from the audit is outdated.** There are 20 existing tests (`test_chat_service_streaming.py` 11 tests, `test_sse_events.py` 5 tests, `test_chat_stream_session_lifecycle.py` 4 tests). They form the regression safety net for Task 2. **B3 does not add new tests for `chat_stream_service` — existing coverage suffices.**

3. **`tour_chat_service.ask_stream_tour` has zero stream-behavior tests** (only `build_system_prompt` is covered in `test_tour_chat_service.py`). Task 3 adds them.

**Tech Stack:** Python 3.11, FastAPI, SSE (text/event-stream), pytest, uv. No frontend changes.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B3.

**Related audit findings:** CQ-P1-01, SYS-3, PERFOPS-P1-02.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/application/sse_events.py` | Create | Tiny module: two format helpers (one per schema) + event-name constants. No I/O, no state. |
| `backend/tests/unit/test_sse_events_builders.py` | Create | Unit tests for the two helpers — byte-exact assertions against hand-written expected strings. |
| `backend/app/application/chat_stream_service.py` | Modify | Replace all 18 `f"data: {json.dumps({'type': ...})}\n\n"` literals with `sse_chat_event(...)` calls. Zero behavior change (existing 20 tests stay green). |
| `backend/app/application/tour_chat_service.py` | Modify | Replace 3 literals with `sse_tour_event(...)`. Fix PERFOPS-P1-02 (do NOT emit `done` after `error`). |
| `backend/tests/unit/test_tour_chat_stream.py` | Create | New file — stream-behavior tests for `ask_stream_tour`, including the error-then-no-done regression test. |
| `backend/tests/contract/test_sse_schema_contract.py` | Create | Schema-pinning contract test — fails if anyone accidentally changes the wire field name (`type` vs `event`) on either service. |

No other files change. In particular, **`useChat.js` and `useTour.js` are not touched**.

---

## Task 1: B3-1 — Create `sse_events.py` builders + unit tests (TDD)

**Scope:** Tiny, pure module. Two functions, one dict of event-name constants, one module-level docstring explaining why two schemas coexist. TDD: write tests first.

**Files:**
- Create: `backend/tests/unit/test_sse_events_builders.py`
- Create: `backend/app/application/sse_events.py`

- [ ] **Step 1: Write the failing test file**

Create `backend/tests/unit/test_sse_events_builders.py` with this content:
```python
"""Byte-exact tests for SSE event builders.

The frontend (useChat.js, useTour.js) parses the exact strings these
builders produce. Any whitespace or key-order change is a wire-protocol
break — hence the strict string equality.
"""
import json


def test_sse_chat_event_basic():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("chunk", stage="generate", content="hello")

    # Must be exactly this wire format:
    expected = f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': 'hello'})}\n\n"
    assert result == expected


def test_sse_chat_event_error():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("error", code="LLM_ERROR", message="boom")
    expected = f"data: {json.dumps({'type': 'error', 'code': 'LLM_ERROR', 'message': 'boom'})}\n\n"
    assert result == expected


def test_sse_chat_event_rag_step():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("rag_step", step="retrieve", status="running", message="...")
    expected = f"data: {json.dumps({'type': 'rag_step', 'step': 'retrieve', 'status': 'running', 'message': '...'})}\n\n"
    assert result == expected


def test_sse_chat_event_done_with_list_field():
    """done events carry arrays (sources, chunks) — JSON must serialize cleanly."""
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("done", stage="generate", trace_id="t-1", chunks=["a", "b"])
    expected = (
        f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': 't-1', 'chunks': ['a', 'b']})}\n\n"
    )
    assert result == expected


def test_sse_chat_event_preserves_insertion_order():
    """json.dumps preserves dict insertion order. Our helper must too — the
    frontend doesn't care about order, but hand-authored tests for the services
    assert equality against literals, so order stability matters."""
    from app.application.sse_events import sse_chat_event

    # type must always come first; caller's kwarg order decides the rest.
    result = sse_chat_event("thinking", stage="retrieve", content="x")
    assert result.startswith('data: {"type": "thinking"')


def test_sse_tour_event_chunk_with_data_wrapper():
    """Tour schema wraps content under a 'data' key (matches existing wire format)."""
    from app.application.sse_events import sse_tour_event

    result = sse_tour_event("chunk", data={"content": "hello"})
    expected = f"data: {json.dumps({'event': 'chunk', 'data': {'content': 'hello'}})}\n\n"
    assert result == expected


def test_sse_tour_event_done_flat_fields():
    """Tour 'done' events are flat — no data wrapper — to match the current
    wire format consumed by useTour.js."""
    from app.application.sse_events import sse_tour_event

    result = sse_tour_event("done", trace_id="t-1", is_ceramic_question=True)
    expected = f"data: {json.dumps({'event': 'done', 'trace_id': 't-1', 'is_ceramic_question': True})}\n\n"
    assert result == expected


def test_sse_tour_event_error_with_data_wrapper():
    from app.application.sse_events import sse_tour_event

    result = sse_tour_event("error", data={"code": "llm_error", "message": "AI导览暂时不可用，请稍后再试"})
    expected = (
        f"data: {json.dumps({'event': 'error', 'data': {'code': 'llm_error', 'message': 'AI导览暂时不可用，请稍后再试'}}, ensure_ascii=False)}\n\n"
    )
    # NOTE: the existing tour_chat_service uses default json.dumps (ensure_ascii=True),
    # so the wire format is ASCII-escaped. Match that exactly.
    expected_ascii = (
        f"data: {json.dumps({'event': 'error', 'data': {'code': 'llm_error', 'message': 'AI导览暂时不可用，请稍后再试'}})}\n\n"
    )
    assert result == expected_ascii
```

- [ ] **Step 2: Run the new test file — verify all 8 tests FAIL with ImportError**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_sse_events_builders.py -v 2>&1 | tail -20
```
Expected: all 8 tests ERROR with `ModuleNotFoundError: No module named 'app.application.sse_events'`. (This is the RED phase of TDD.)

- [ ] **Step 3: Implement `sse_events.py` to make the tests pass**

Create `backend/app/application/sse_events.py`:
```python
"""SSE (Server-Sent Events) payload builders.

Two schemas coexist and are pinned by frontend consumers:

1. Chat schema — used by `chat_stream_service` and consumed by
   `frontend/src/composables/useChat.js`. Flat payload keyed by "type":
   `{"type": <name>, <extra-fields>}`.

2. Tour schema — used by `tour_chat_service` and consumed by
   `frontend/src/composables/useTour.js`. Keyed by "event":
   `{"event": <name>, "data": {...}}` for most events, or
   `{"event": "done", <flat-fields>}` for the done event (intentional
   inconsistency — matches the current wire format).

Do NOT unify the two schemas here. Changing field names would silently
break the frontend.

The builders accept `**kwargs` so callers can add arbitrary extra fields
without the module needing to know every variant up-front. Kwarg insertion
order is preserved in the JSON output (Python ≥3.7 dict order guarantee).
"""
import json
from typing import Any


def sse_chat_event(type_: str, **fields: Any) -> str:
    """Format a chat-schema SSE event.

    The "type" key is always first in the JSON output, followed by the
    caller-provided fields in kwarg order. Output is terminated with the
    SSE two-newline boundary.
    """
    payload: dict[str, Any] = {"type": type_}
    payload.update(fields)
    return f"data: {json.dumps(payload)}\n\n"


def sse_tour_event(event_: str, **fields: Any) -> str:
    """Format a tour-schema SSE event.

    The "event" key is always first. Callers that need the `{"event": X,
    "data": {...}}` wrapping pass `data={...}` explicitly — this helper
    does not inject the wrapper itself because the tour schema uses flat
    fields for `done` events.
    """
    payload: dict[str, Any] = {"event": event_}
    payload.update(fields)
    return f"data: {json.dumps(payload)}\n\n"
```

- [ ] **Step 4: Re-run the test file — verify all 8 pass (GREEN phase)**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_sse_events_builders.py -v 2>&1 | tail -15
```
Expected: 8 passed.

- [ ] **Step 5: Run ruff + mypy on the two new files**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/application/sse_events.py backend/tests/unit/test_sse_events_builders.py && uv run mypy backend/app/application/sse_events.py
```
Expected: `All checks passed!` + `Success: no issues found in 1 source file`.

- [ ] **Step 6: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/app/application/sse_events.py backend/tests/unit/test_sse_events_builders.py && git commit -m "$(cat <<'EOF'
feat(sse): add sse_events.py builders for chat + tour schemas (B3-1)

Two pure helpers (sse_chat_event, sse_tour_event) produce the byte-exact
SSE payloads currently duplicated in ~20 string literals across the
streaming services. The two schemas (type-keyed for chat, event-keyed
for tour) are preserved intentionally — the frontend pins both.

8 unit tests in test_sse_events_builders.py assert byte-exact equality
against hand-written literals so any future field renaming breaks the
test suite loudly instead of silently breaking the wire.

Partial fix for SYS-3 / CQ-P1-01. Tasks 2 and 3 convert the call sites.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: B3-2 — Refactor `chat_stream_service.py` to use `sse_chat_event`

**Scope:** Byte-for-byte-preserving replacement of 18 inline SSE literals with `sse_chat_event(...)` calls. **Zero behavior change.** The existing 20 tests (`test_chat_service_streaming.py`, `test_sse_events.py`, `test_chat_stream_session_lifecycle.py`) are the regression net.

**Key rule:** every replacement must produce the identical output string. If a test fails after this task, the refactor is wrong — **do not edit the tests to match the new output**; fix the refactor.

**Files:**
- Modify: `backend/app/application/chat_stream_service.py` (18 call-site replacements)

- [ ] **Step 1: Capture baseline — run the full stream test suite before touching the file**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_service_streaming.py backend/tests/contract/test_sse_events.py backend/tests/unit/test_chat_stream_session_lifecycle.py -v 2>&1 | tail -30
```
Expected: 20 passed (11 + 5 + 4). Record the exact counts — this is the baseline.

- [ ] **Step 2: Add the import**

In `backend/app/application/chat_stream_service.py`, insert a new import line after the existing `from app.application.error_handling import sanitize_error_message` (around line 11):
```python
from app.application.sse_events import sse_chat_event
```
Remove the now-unused `import json` at line 1. (Rationale: after Task 2, no `json.dumps` call remains in this file. `json` is not used elsewhere in the module — verified by grep during planning.)

**Before committing, verify:**
```bash
cd /home/singer/MuseAI && grep -n "json" backend/app/application/chat_stream_service.py
```
Expected output: no matches. If `json` is still referenced anywhere, keep the import.

- [ ] **Step 3: Replace each of the 18 literals**

Use these exact substitutions. Apply in order; each replacement is a standalone `Edit` call (pick a larger context window if the line isn't unique).

| Line # | Old (exact) | New |
|---|---|---|
| 83 | `yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"` | `yield sse_chat_event("error", code="SESSION_NOT_FOUND", message="Session not found")` |
| 88 | `yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"` | `yield sse_chat_event("thinking", stage="retrieve", content="正在检索...")` |
| 89 | `yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '检索完成'})}\n\n"` | `yield sse_chat_event("thinking", stage="retrieve", content="检索完成")` |
| 97 | `yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"` | `yield sse_chat_event("chunk", stage="generate", content=chunk)` |
| 104 | `yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'chunks': chunks})}\n\n"` | `yield sse_chat_event("done", stage="generate", trace_id=trace_id, chunks=chunks)` |
| 107 | `yield f"data: {json.dumps({'type': 'error', 'code': 'LLM_ERROR', 'message': sanitized})}\n\n"` | `yield sse_chat_event("error", code="LLM_ERROR", message=sanitized)` |
| 110 | `yield f"data: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': sanitized})}\n\n"` | `yield sse_chat_event("error", code="INTERNAL_ERROR", message=sanitized)` |
| 124 | `yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"` | `yield sse_chat_event("error", code="SESSION_NOT_FOUND", message="Session not found")` |
| 129-130 | (local `_rag_event` helper — delete it entirely) | Replace every call below with `sse_chat_event("rag_step", step=..., status=..., message=...)` inline |
| 196 | `yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"` | `yield sse_chat_event("chunk", stage="generate", content=chunk)` |
| 248 | `yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'sources': sources})}\n\n"` | `yield sse_chat_event("done", stage="generate", trace_id=trace_id, sources=sources)` |
| 251 | `yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"` | `yield sse_chat_event("error", code="RAG_ERROR", message=sanitized)` |
| 277 | `yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"` | `yield sse_chat_event("thinking", stage="retrieve", content="正在检索...")` |
| 286 | `yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': retrieve_msg})}\n\n"` | `yield sse_chat_event("thinking", stage="retrieve", content=retrieve_msg)` |
| 289 | `yield f"data: {json.dumps({'type': 'thinking', 'stage': 'evaluate', 'content': eval_msg})}\n\n"` | `yield sse_chat_event("thinking", stage="evaluate", content=eval_msg)` |
| 317 | `yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"` | `yield sse_chat_event("chunk", stage="generate", content=chunk)` |
| 358 | `yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'sources': sources})}\n\n"` | `yield sse_chat_event("done", stage="generate", trace_id=trace_id, sources=sources)` |
| 361 | `yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"` | `yield sse_chat_event("error", code="RAG_ERROR", message=sanitized)` |

**Special handling for the local `_rag_event` helper** (currently lines 129-130):
```python
def _rag_event(step: str, status: str, message: str) -> str:
    return f"data: {json.dumps({'type': 'rag_step', 'step': step, 'status': status, 'message': message})}\n\n"
```
Delete this function entirely. Replace every `yield _rag_event('rewrite', 'running', '正在分析查询意图...')` with:
```python
yield sse_chat_event("rag_step", step="rewrite", status="running", message="正在分析查询意图...")
```
Repeat for every `_rag_event(...)` call site (there are ~10 calls between lines 132 and 166).

- [ ] **Step 4: Grep-check — no json.dumps / no _rag_event references remain**

Run:
```bash
cd /home/singer/MuseAI && grep -n "json.dumps\|_rag_event\|^import json" backend/app/application/chat_stream_service.py
```
Expected: no output. If any match appears, the refactor is incomplete.

- [ ] **Step 5: Run the 20 regression tests — all must pass unchanged**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_service_streaming.py backend/tests/contract/test_sse_events.py backend/tests/unit/test_chat_stream_session_lifecycle.py -v 2>&1 | tail -30
```
Expected: 20 passed, identical to the baseline from Step 1. If ANY test fails with a string-mismatch assertion, the refactor is not byte-exact — **fix the refactor, do not edit the test**. The most likely cause is a reordered kwarg (e.g. `content=x, stage=y` vs `stage=y, content=x`) — Python dict preserves kwarg order, which flows through to `json.dumps`.

- [ ] **Step 6: Run ruff + mypy on the edited file**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/application/chat_stream_service.py && uv run mypy backend/app/application/chat_stream_service.py
```
Expected: clean on both.

- [ ] **Step 7: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/app/application/chat_stream_service.py && git commit -m "$(cat <<'EOF'
refactor(sse): chat_stream_service uses sse_chat_event() builder (B3-2)

Replaces 18 duplicated f-string SSE literals with calls to
sse_chat_event(). Byte-exact preservation — all 20 existing streaming
tests pass unchanged. Local _rag_event helper removed in favor of the
shared builder.

Part of SYS-3 / CQ-P1-01 remediation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: B3-3 — Refactor `tour_chat_service.py` + fix PERFOPS-P1-02 (error-then-done bug) with TDD

**Scope:** Two changes in one commit because they share the same file and review:
1. Replace 3 SSE literals in `ask_stream_tour` with `sse_tour_event(...)` calls.
2. Fix the contract bug where `ask_stream_tour` emits a `done` event AFTER an `error` event on the RAG-failure branch (lines 91-107 of current file).

**Why one commit:** the bug fix requires restructuring the same code region as the builder substitution. Two commits would step on each other. The commit message documents both changes.

**The bug (current behavior, PERFOPS-P1-02):**
```python
try:
    async for event in _stream_rag(rag_agent, message, system_prompt):
        yield event
except Exception as e:
    logger.error(f"Tour chat RAG error: {e}")
    error_data = json.dumps({...})
    yield f"data: {error_data}\n\n"     # emits "error"
# <-- falls through here after error OR success
done_data = {...}
yield f"data: {json.dumps(done_data)}\n\n"   # ALWAYS emits "done" — even after error
```
Frontend (`useTour.js:152,159`) dispatches on `event.event`. Getting `error` followed by `done` is ambiguous: the success callback may run even though the stream failed. Fix: return early after yielding the error event.

**Files:**
- Modify: `backend/app/application/tour_chat_service.py`
- Create: `backend/tests/unit/test_tour_chat_stream.py`

- [ ] **Step 1: Write the failing regression test for the bug (RED phase)**

Create `backend/tests/unit/test_tour_chat_stream.py`:
```python
"""Stream-behavior tests for ask_stream_tour.

Existing tests (test_tour_chat_service.py) only cover build_system_prompt.
This file adds coverage for the async generator itself, including the
regression test for PERFOPS-P1-02 (error-then-done dual emission bug).
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.tour_chat_service import ask_stream_tour


def _collect_event_types(events: list[str]) -> list[str]:
    """Parse 'data: {...}\n\n' lines and return the 'event' field of each."""
    parsed = []
    for raw in events:
        assert raw.startswith("data: ")
        assert raw.endswith("\n\n")
        payload = json.loads(raw[len("data: ") : -2])
        parsed.append(payload.get("event"))
    return parsed


@pytest.fixture
def fake_tour_session():
    """A minimal tour_session object with the attributes ask_stream_tour reads."""
    return SimpleNamespace(
        visited_exhibit_ids=[],
        persona="A",
        assumption="A",
        current_hall="relic-hall",
    )


@pytest.fixture
def fake_session_maker():
    """session_maker() must be usable as an async context manager."""
    session_ctx = AsyncMock()
    session_ctx.__aenter__.return_value = AsyncMock()
    session_ctx.__aexit__.return_value = None
    maker = MagicMock(return_value=session_ctx)
    return maker


@pytest.mark.asyncio
async def test_stream_emits_chunk_then_done_on_success(
    monkeypatch, fake_tour_session, fake_session_maker
):
    async def fake_get_session(db, sid):
        return fake_tour_session
    monkeypatch.setattr(
        "app.application.tour_chat_service.get_session", fake_get_session
    )
    async def fake_record_events(*args, **kwargs):
        return None
    monkeypatch.setattr(
        "app.application.tour_chat_service.record_events", fake_record_events
    )

    rag_agent = MagicMock()
    rag_agent.run = AsyncMock(return_value={"answer": "hello"})

    events = []
    async for event in ask_stream_tour(
        db_session=MagicMock(),
        session_maker=fake_session_maker,
        tour_session_id="tour-1",
        message="q?",
        rag_agent=rag_agent,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert types == ["chunk", "done"]


@pytest.mark.asyncio
async def test_stream_emits_error_and_NOT_done_when_rag_fails(
    monkeypatch, fake_tour_session, fake_session_maker
):
    """PERFOPS-P1-02 regression: after an error event, done MUST NOT follow."""
    async def fake_get_session(db, sid):
        return fake_tour_session
    monkeypatch.setattr(
        "app.application.tour_chat_service.get_session", fake_get_session
    )
    async def fake_record_events(*args, **kwargs):
        return None
    monkeypatch.setattr(
        "app.application.tour_chat_service.record_events", fake_record_events
    )

    rag_agent = MagicMock()
    rag_agent.run = AsyncMock(side_effect=RuntimeError("boom"))

    events = []
    async for event in ask_stream_tour(
        db_session=MagicMock(),
        session_maker=fake_session_maker,
        tour_session_id="tour-1",
        message="q?",
        rag_agent=rag_agent,
    ):
        events.append(event)

    types = _collect_event_types(events)
    assert "error" in types, f"expected error event, got {types}"
    assert "done" not in types, (
        f"PERFOPS-P1-02 regression: 'done' must not follow 'error', got {types}"
    )
```

- [ ] **Step 2: Run the new test file — second test must FAIL, first must PASS**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_tour_chat_stream.py -v 2>&1 | tail -20
```
Expected:
- `test_stream_emits_chunk_then_done_on_success` → PASS (baseline)
- `test_stream_emits_error_and_NOT_done_when_rag_fails` → FAIL with `AssertionError: PERFOPS-P1-02 regression: 'done' must not follow 'error', got ['error', 'done']`

This confirms the bug is real and the test catches it.

- [ ] **Step 3: Refactor `tour_chat_service.py` — builder substitution + early return on error**

Edit `backend/app/application/tour_chat_service.py`:

(a) **Remove** the top-level `import json` (line 1) — it will be unused after substitution. Keep every other import.

(b) **Add** after the existing `from app.application.tour_session_service import get_session` (line 11):
```python
from app.application.sse_events import sse_tour_event
```

(c) **Replace** the body of `ask_stream_tour` (lines ~88-120) with the following (note the early `return` after the error event — this is the bug fix):
```python
    trace_id = str(uuid.uuid4())
    is_ceramic = detect_ceramic_question(message)

    try:
        async for event in _stream_rag(rag_agent, message, system_prompt):
            yield event
    except Exception as e:
        logger.error(f"Tour chat RAG error: {e}")
        yield sse_tour_event(
            "error",
            data={"code": "llm_error", "message": "AI导览暂时不可用，请稍后再试"},
        )
        return  # PERFOPS-P1-02: do NOT emit 'done' after 'error'

    yield sse_tour_event(
        "done",
        trace_id=trace_id,
        is_ceramic_question=is_ceramic,
    )

    try:
        async with session_maker() as event_session:
            await record_events(event_session, tour_session_id, [
                {
                    "event_type": "exhibit_question",
                    "exhibit_id": exhibit_id,
                    "hall": tour_session.current_hall,
                    "metadata": {"question": message, "is_ceramic_question": is_ceramic},
                }
            ])
    except Exception as e:
        logger.warning(f"Failed to record tour event: {e}")
```

(d) **Replace** the `_stream_rag` helper (currently at lines 123-128) with:
```python
async def _stream_rag(rag_agent: Any, message: str, system_prompt: str) -> AsyncGenerator[str, None]:
    result = await rag_agent.run(message, system_prompt=system_prompt)
    answer = result.get("answer", "")

    yield sse_tour_event("chunk", data={"content": answer})
```

**Note on error-event recording:** after the fix, if RAG fails, we bail out BEFORE recording the tour event. This is intentional — recording an `exhibit_question` event for a failed answer would be misleading analytics. If the product wants to track failures, do it in a follow-up batch with a separate `event_type="failed_question"`.

- [ ] **Step 4: Grep-check — no json.dumps / no f-string SSE literals remain**

Run:
```bash
cd /home/singer/MuseAI && grep -n "json\.dumps\|^import json\|data: {json" backend/app/application/tour_chat_service.py
```
Expected: no output.

- [ ] **Step 5: Re-run the new test file — both tests must PASS (GREEN phase)**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_tour_chat_stream.py -v 2>&1 | tail -15
```
Expected: 2 passed.

- [ ] **Step 6: Run the contract test that touches tour streaming to catch any regression**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_tour_api.py::test_tour_chat_stream backend/tests/contract/test_tour_api.py::test_tour_chat_stream_no_auth backend/tests/unit/test_tour_chat_service.py -v 2>&1 | tail -20
```
Expected: all pass. (`test_tour_chat_service.py` covers `build_system_prompt` only — unaffected. The two `test_tour_api` tests hit `ask_stream_tour` via HTTP.)

- [ ] **Step 7: Run ruff + mypy on the edited file**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/application/tour_chat_service.py backend/tests/unit/test_tour_chat_stream.py && uv run mypy backend/app/application/tour_chat_service.py
```
Expected: clean on both.

- [ ] **Step 8: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/app/application/tour_chat_service.py backend/tests/unit/test_tour_chat_stream.py && git commit -m "$(cat <<'EOF'
fix(tour): do not emit 'done' after 'error' (PERFOPS-P1-02) + builder refactor (B3-3)

Two changes in one commit:

1. ask_stream_tour previously yielded a 'done' event after yielding
   'error' on RAG failure, so useTour.js would run its success callback
   even when the stream had errored. Fix: early return after the error
   event. Regression test in test_tour_chat_stream.py pins this.

2. The three inline json.dumps SSE literals are replaced with
   sse_tour_event() builder calls. Wire format preserved byte-exactly.

Partial fix for SYS-3 / CQ-P1-01 and full fix for PERFOPS-P1-02.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: B3-4 — Schema-pinning contract test to prevent future drift

**Scope:** One small contract test file that scans `chat_stream_service.py` and `tour_chat_service.py` for any lingering raw `json.dumps(...{"type"` or `json.dumps(...{"event"` literals, and verifies that the frontend wire field (`type` for chat, `event` for tour) has not accidentally been swapped. This turns "discovered during review" drift into "fails at CI".

**Why a test and not just a grep:** ruff rules can't enforce semantic wire-protocol constraints, and a pure grep is a docs file. A test fails loudly in the standard test run and gets the same attention as any other red bar.

**Files:**
- Create: `backend/tests/contract/test_sse_schema_contract.py`

- [ ] **Step 1: Write the contract test**

Create `backend/tests/contract/test_sse_schema_contract.py`:
```python
"""Pins the SSE wire protocols used by chat_stream_service and tour_chat_service.

Frontend consumers (useChat.js, useTour.js) parse events by exact field name.
If anyone accidentally renames "type" → "event" (or vice versa) in a refactor,
this test fails loudly instead of silently breaking the frontend.

Also guards against the return of inline json.dumps(...) SSE literals now
that sse_events.py exists — the only approved way to produce SSE payloads
from these services is via the builders.
"""
import re
from pathlib import Path

CHAT_SERVICE = Path(__file__).resolve().parents[2] / "app" / "application" / "chat_stream_service.py"
TOUR_SERVICE = Path(__file__).resolve().parents[2] / "app" / "application" / "tour_chat_service.py"


def test_chat_stream_service_has_no_raw_json_dumps_sse_literals():
    """After B3-2, chat_stream_service must route all SSE events through
    sse_chat_event. A re-introduced f-string json.dumps literal is a
    contract regression."""
    source = CHAT_SERVICE.read_text(encoding="utf-8")
    assert "json.dumps" not in source, (
        "chat_stream_service.py must not construct SSE payloads via json.dumps. "
        "Use sse_chat_event() from app.application.sse_events."
    )


def test_tour_chat_service_has_no_raw_json_dumps_sse_literals():
    """Same guarantee for tour_chat_service after B3-3."""
    source = TOUR_SERVICE.read_text(encoding="utf-8")
    assert "json.dumps" not in source, (
        "tour_chat_service.py must not construct SSE payloads via json.dumps. "
        "Use sse_tour_event() from app.application.sse_events."
    )


def test_chat_service_uses_type_keyed_events_only():
    """Chat wire protocol is keyed on 'type' (consumed by useChat.js).
    A switch to 'event' would silently break the frontend."""
    source = CHAT_SERVICE.read_text(encoding="utf-8")
    # The only SSE construction call in this file should be sse_chat_event.
    assert "sse_chat_event" in source
    # No sse_tour_event calls — those belong in tour_chat_service.
    assert "sse_tour_event" not in source, (
        "chat_stream_service uses the 'type'-keyed schema — sse_tour_event belongs in tour_chat_service."
    )


def test_tour_service_uses_event_keyed_events_only():
    """Tour wire protocol is keyed on 'event' (consumed by useTour.js)."""
    source = TOUR_SERVICE.read_text(encoding="utf-8")
    assert "sse_tour_event" in source
    assert "sse_chat_event" not in source, (
        "tour_chat_service uses the 'event'-keyed schema — sse_chat_event belongs in chat_stream_service."
    )


def test_sse_events_builders_produce_expected_key_names():
    """Lock the two schemas at the builder level. If anyone flips the
    'type' and 'event' keys in sse_events.py, both useChat.js and
    useTour.js break silently. This test catches that."""
    from app.application.sse_events import sse_chat_event, sse_tour_event

    chat_output = sse_chat_event("chunk", stage="generate", content="x")
    assert re.match(r'^data: \{"type": "chunk"', chat_output), (
        f"sse_chat_event must emit 'type'-keyed payload, got: {chat_output!r}"
    )

    tour_output = sse_tour_event("chunk", data={"content": "x"})
    assert re.match(r'^data: \{"event": "chunk"', tour_output), (
        f"sse_tour_event must emit 'event'-keyed payload, got: {tour_output!r}"
    )
```

- [ ] **Step 2: Run the new contract test — all 5 tests should pass immediately**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_sse_schema_contract.py -v 2>&1 | tail -15
```
Expected: 5 passed. (All rules are about the post-B3-2/B3-3 state of the code, which now holds.)

- [ ] **Step 3: Run ruff + mypy on the new file**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/tests/contract/test_sse_schema_contract.py
```
Expected: clean. (mypy is not strictly needed for this test — it's pure string/regex; but won't fail either.)

- [ ] **Step 4: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/tests/contract/test_sse_schema_contract.py && git commit -m "$(cat <<'EOF'
test(sse): add schema-pinning contract test for chat + tour SSE wires (B3-4)

Five assertions locking the two SSE wire protocols:
- No inline json.dumps(...) SSE literals may return to the stream services.
- chat_stream_service must only use sse_chat_event (type-keyed).
- tour_chat_service must only use sse_tour_event (event-keyed).
- The builders themselves must not swap the key names.

Turns "discovered during review" wire-protocol drift into a loud CI failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch B3 Verification

After all four tasks commit:

- [ ] **Run the full verification sweep**

Run:
```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3
```

Expected:
- pytest: 780 passed (was 765 after B2; +8 builder tests in B3-1, +2 tour stream tests in B3-3, +5 schema contract tests in B3-4 = 780)
- ruff: `All checks passed!`
- mypy: `Success: no issues found in 90 source files` (+1 new file: sse_events.py)

- [ ] **Confirm the audit IDs are closed** — no further code changes required:
  - CQ-P1-01 (SSE strings duplicated 18×) ✅ by Tasks 2 + 3
  - SYS-3 (SSE contract scattered — cross-dimensional debt) ✅ by Tasks 1–4 combined
  - PERFOPS-P1-02 (tour error+done dual emission) ✅ by Task 3

- [ ] **Sanity-check the frontend still works (manual smoke test, not automated)**

Not part of this plan's CI gate — B3 is backend-only and every byte-exact test passes — but worth a human eyeball after merge:
1. Start backend (`uv run uvicorn backend.app.main:app --reload`) and frontend (`cd frontend && npm run dev`).
2. Open chat, ask a question, verify chunks stream and answer renders.
3. Start a tour session, ask a question, verify the tour response streams.
4. (Optional, hard to reproduce locally) Kill the LLM mid-stream on a tour and verify the frontend shows the error toast without running the success handler.

---

## Rollback Notes

Each task is its own commit on `feature/tour-visitor-flow`. Rollback order if needed:
- Revert Task 4 (contract test) — independent, safe anytime.
- Revert Task 3 (tour fix) — independent of Tasks 1–2; the bug returns.
- Revert Task 2 (chat refactor) — requires also reverting Task 1 (it depends on `sse_events.py`).
- Revert Task 1 (builder module) — ok to keep if Tasks 2–3 were reverted; the module is unused but harmless.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: parent-spec §4 Batch B3 calls for "extract SSE contract + add chat_stream_service tests." Tests for chat_stream_service already exist (20 of them), so this plan reallocates that time to fixing PERFOPS-P1-02 and adding schema-pinning. The parent-spec intent (contract extraction) is fully satisfied. ✓
- **Placeholder scan**: no "TBD" / "TODO" / "add appropriate …" patterns. Every code block is complete. ✓
- **Wire-protocol preservation**: every `sse_chat_event(...)` and `sse_tour_event(...)` kwarg order matches the existing literal's dict key order exactly. Python's kwarg ordering + `dict.update` insertion-order preservation means the JSON output is byte-identical. Verified by the 8 builder tests in Task 1 and the 20 existing tests in Task 2. ✓
- **Task ordering**: Task 2 depends on Task 1 (builder must exist). Task 3 depends on Task 1 (same). Task 4 depends on Tasks 2 and 3 (asserts their post-state). Ordering is enforced by the task numbering; no parallel execution within the batch. ✓
- **PERFOPS-P1-02 fix scope**: `return` after the error yield is the minimal correct fix. Alternatives (try/finally, explicit `done=False` flag) would be more invasive. The TDD regression test locks the behavior. ✓
- **Frontend not touched**: verified by grep — `useChat.js` reads `event.type`, `useTour.js` reads `event.event`; both fields remain exactly as they were. ✓
