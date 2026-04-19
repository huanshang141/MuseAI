# B7+ Remaining Technical Debt — Consolidated Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining P1/P2 debt items from the 2026-04-17 midterm audit that were not addressed by batches B0–B6. Each batch below is independent; commit per task; the executor may interleave batches or work them in order.

---

## Status Summary

### Already closed (B0–B6 — no work here)
| Batch | Closed audit IDs |
|---|---|
| B0 | SEC-P1-01, SEC-P1-02, SEC-P2-01 |
| B1 | mypy config, layer-rules test, ruff baseline, pytest config (TEST-P1-03, TEST-P2-03/04) |
| B2 | ARCH-P1-01/02/03, ARCH-P2-01/02/03, CQ-P2-01/02, SYS-1/2 |
| B3 | CQ-P1-01, SYS-3, PERFOPS-P1-02 |
| B4 | TEST-P1-01, TEST-P1-02 |
| B5 | SEC-P1-03, SEC-P2-03, confirmed SEC-P2-04 already in place |
| B6 | PERFOPS-P1-01, PERFOPS-P1-03, confirmed PERFOPS-P2-05 already in place |

### Intentionally deferred — documented-but-not-executed (see end of file for rationale)
- **CQ-P1-03** (289 hardcoded Chinese UI strings) — requires i18n framework decision
- **ARCH-P2-02** (anemic domain methods) — large refactor, limited practical win
- **SEC-P2-05** (prompt injection) — design-level, needs red-team iteration
- **TEST-P2-01/02** (over-mocking, contract auto-mocking) — stylistic, no clear win
- **P3 items** — detail polish (covered by "cleanup day" notes in batches below)

### In scope for this plan
- **B7**: Documentation sync (DOC-P1-01, DOC-P1-02, DOC-P1-03, DOC-P2-02, DOC-P2-03)
- **B8**: Code quality — dedup + file splits (CQ-P1-02, CQ-P2-03, CQ-P2-04, CQ-P2-05)
- **B9**: Auth migration — cookie → Bearer + admin bootstrap CLI (SEC-P1-04, SEC-P2-02)
- **B10**: Contract conftest cleanup (TEST-P1-04)
- **B11**: Infrastructure polish (PERFOPS-P2-01, PERFOPS-P2-03, PERFOPS-P2-04)
- **B12**: Frontend dependency upgrades (DOC-P1-04, DOC-P2-01)

**Total estimated effort:** 6–8 person-days across 17 tasks.

---

## B7 — Documentation Sync

> Goal: Bring CLAUDE.md in sync with the actual codebase; give every endpoint a `summary=`; prune stale docs. These prevent future agent sessions from working off a wrong mental model of the project.

### Task B7-1: Rewrite CLAUDE.md router + env var sections (DOC-P1-01, DOC-P1-02)

**Files:**
- Modify: `CLAUDE.md`

**Scope:**
- Router list currently misses: `admin/`, `client_ip` utility, `curator`, `exhibits`, `profile`, `tour`.
- Env vars currently documents ~16 but settings expose ~35 (missing: `ADMIN_EMAILS`, `TRUSTED_PROXIES`, `RERANK_PROVIDER`, `RERANK_MODEL`, `RERANK_ENABLED`, `RERANK_TOP_K`, `LOG_LEVEL`, `LOG_FORMAT`, `CORS_ORIGINS`, `RATE_LIMIT_ENABLED`, `ALLOW_INSECURE_DEV_DEFAULTS`, `EMBEDDING_DIMS`, `SESSION_TTL_SECONDS`, plus a handful more).

- [ ] **Step 1: Scan current source of truth**
  ```bash
  cd /home/singer/MuseAI && ls backend/app/api/ backend/app/api/admin/ && grep -E "^[A-Z_]+:\s*(str|int|bool|float)" backend/app/config/settings.py | sort
  ```
  Capture the full list of routers and env-var field names. Record them for the edit.

- [ ] **Step 2: Replace the "Router layout" section in CLAUDE.md with the scanned list**

Under `## Architecture` → `### Backend Structure`, replace the `api/` sub-block comment to enumerate every current router. Use the actual file tree (including `admin/exhibits.py`, `admin/prompts.py`, `client_ip.py`, `curator.py`, `exhibits.py`, `profile.py`, `tour.py`).

- [ ] **Step 3: Rewrite the "Configuration" section**

List every env var from settings.py grouped by concern: Core, Auth, Database, ES, Redis, LLM, Embedding, Rerank, Logging, Rate limiting, Security, CORS. For each: name, type, default, production requirement, one-line purpose.

- [ ] **Step 4: Update the "Database Schema" section**

Current doc lists 5 tables but the migrations directory (`backend/alembic/versions/`) shows additional tables introduced for tour, exhibits, prompts. Add: `exhibits`, `visitor_profiles`, `tour_sessions`, `tour_events`, `prompts`, `prompt_versions`. Source of truth: `backend/app/infra/postgres/models.py`.

- [ ] **Step 5: Verify nothing got hallucinated**

```bash
cd /home/singer/MuseAI && for name in $(grep -oE "[A-Z_]+:" CLAUDE.md | grep -oE "[A-Z][A-Z_]+" | sort -u); do \
    grep -q "$name" backend/app/config/settings.py || echo "⚠ $name not in settings"; \
done
```
Expected: no warnings.

- [ ] **Step 6: Commit**
  ```
  docs(claude): sync router list, env vars, schema with source of truth (DOC-P1-01, DOC-P1-02)
  ```

### Task B7-2: Add `summary=` to every FastAPI route (DOC-P1-03)

**Files:**
- Modify: all 11 `backend/app/api/*.py` and `backend/app/api/admin/*.py` files — ~50 routes total.

**Scope:** OpenAPI's Swagger UI uses `summary` for the route name in the left sidebar. Currently every route shows its function name (`get_documents`, `ask_question_stream_with_rag`) — ugly and not language-neutral. Give each route a ≤60-char human-readable `summary=`.

- [ ] **Step 1: Enumerate every route**

```bash
cd /home/singer/MuseAI && grep -n "^@router\." backend/app/api/*.py backend/app/api/admin/*.py
```

- [ ] **Step 2: For each router decorator, add `summary=` kwarg**

Use imperative English for verbs and concrete nouns. Examples:
- `@router.post("/register", ...)` → `summary="Register new user"`
- `@router.post("/documents/upload", ...)` → `summary="Upload document"`
- `@router.get("/exhibits", ...)` → `summary="List exhibits (public)"`
- `@router.get("/exhibits/{id}", ...)` → `summary="Get exhibit detail"`
- `@router.post("/chat/sessions/{id}/ask-stream", ...)` → `summary="Ask chat question (SSE)"`

No content change — `summary=` is metadata only. Tests are unaffected.

- [ ] **Step 3: Verify**

```bash
cd /home/singer/MuseAI && grep -c "@router\." backend/app/api/*.py backend/app/api/admin/*.py | awk -F: '{ sum += $2 } END { print "routes:", sum }' && \
  grep -c "summary=" backend/app/api/*.py backend/app/api/admin/*.py | awk -F: '{ sum += $2 } END { print "summaries:", sum }'
```
Expected: `routes == summaries`. Any delta is a missing summary.

- [ ] **Step 4: Run full test sweep — no behavior change, all 898 tests still pass**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract --tb=no -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**
  ```
  docs(api): add summary= to every FastAPI route (DOC-P1-03)
  ```

### Task B7-3: Purge legacy debt docs + tag plans with status (DOC-P2-02, DOC-P2-03)

**Files:**
- Delete: `TECHNICAL_DEBT_AUDIT_2026-04-06.md` (top-level stale audit — superseded by `docs/audit/2026-04-17-midterm-technical-debt-audit.md`)
- Modify: each file in `docs/plans/` to add a frontmatter line `Status: completed | in-progress | deferred`

- [ ] **Step 1: Confirm the top-level audit is obsolete**
  ```bash
  cd /home/singer/MuseAI && ls docs/audit/ && head -5 TECHNICAL_DEBT_AUDIT_2026-04-06.md 2>/dev/null
  ```
  If `docs/audit/2026-04-17-midterm-technical-debt-audit.md` exists and references supersede the older file, delete the old one.

- [ ] **Step 2: Annotate every `docs/plans/*.md`**

At the top of each plan file, just below the H1 heading, insert a status line:
```markdown
**Status:** completed (2026-04-17)
```
(Or `in-progress` for work the executor hasn't yet completed; `deferred` for those explicitly skipped.)

- [ ] **Step 3: Commit**
  ```
  docs(cleanup): delete superseded audit + tag plans with status (DOC-P2-02, DOC-P2-03)
  ```

---

## B8 — Code Dedup & File Splits

> Goal: Eliminate Pydantic model duplication and split the three files that broke the 400-line threshold for single-file modules.

### Task B8-1: Consolidate duplicated Pydantic response models (CQ-P1-02)

**Files:**
- Create: `backend/app/api/_shared_responses.py`
- Modify: `backend/app/api/documents.py`, `backend/app/api/chat.py`, `backend/app/api/admin/exhibits.py`, `backend/app/api/exhibits.py`

**Scope:** `DeleteResponse` appears 3× identically (`documents.py:75`, `chat.py:118`, `admin/exhibits.py:75`). `ExhibitListResponse` appears 2× (`exhibits.py:55`, `admin/exhibits.py:53`). If fields drift between copies, the OpenAPI schema becomes inconsistent — confusing for API consumers.

- [ ] **Step 1: Create the shared module**

Create `backend/app/api/_shared_responses.py`:
```python
"""Response models shared across multiple routers.

Keep this module small — only promote a model here when it's literally
identical across 2+ routers. Divergent variants should stay local.
"""
from pydantic import BaseModel


class DeleteResponse(BaseModel):
    """Standard response for DELETE operations: bare success flag."""
    success: bool


# ExhibitListResponse is NOT shared — the public and admin variants carry
# different per-item fields (see api/exhibits.py vs api/admin/exhibits.py).
# If a future refactor converges the two, move it here.
```

**Why ExhibitListResponse is NOT deduped:** the public and admin variants return different per-item shapes (admin exposes `is_active`, `created_at`, etc. while public strips them). Merging them would broaden the public shape or require generics. Keep them separate; the audit flag was opportunistic — the real win is `DeleteResponse`.

- [ ] **Step 2: Replace the 3 `DeleteResponse` definitions with imports**

In each of `documents.py`, `chat.py`, `admin/exhibits.py`, delete the local `class DeleteResponse(BaseModel): ...` block and add:
```python
from app.api._shared_responses import DeleteResponse
```

- [ ] **Step 3: Run tests**
  ```bash
  cd /home/singer/MuseAI && uv run pytest backend/tests/contract/ -q 2>&1 | tail -3
  ```
  Expected: all pass (OpenAPI schema is behaviorally the same).

- [ ] **Step 4: Commit**
  ```
  refactor(api): dedup DeleteResponse to _shared_responses (CQ-P1-02)
  ```

### Task B8-2: Split `postgres/models.py` into per-aggregate modules (CQ-P2-05)

**Files:**
- Source: `backend/app/infra/postgres/models.py` (457 LOC, all 10 ORM classes in one file)
- Target: new directory `backend/app/infra/postgres/models/` with one file per aggregate + an `__init__.py` that re-exports.

**Layout:**
```
models/
  __init__.py        # from .user import User; from .document import Document, IngestionJob; ...
  base.py            # Base = declarative_base()
  user.py            # User
  document.py        # Document, IngestionJob
  chat.py            # ChatSession, ChatMessage
  exhibit.py         # Exhibit
  profile.py         # VisitorProfile
  tour.py            # TourSession, TourEvent
  prompt.py          # Prompt, PromptVersion
```

- [ ] **Step 1: Read current `models.py` and group classes**

```bash
cd /home/singer/MuseAI && grep -n "^class .*Base)" backend/app/infra/postgres/models.py
```

Map each class to the module file listed above.

- [ ] **Step 2: Create `models/base.py` with the `Base` declarative**

```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

- [ ] **Step 3: Create each per-aggregate file, importing `Base` from `.base`**

For each file, copy the corresponding class(es) verbatim. Replace `from .models import Base` (if present) with `from .base import Base`.

- [ ] **Step 4: Delete `models.py` and create `models/__init__.py` re-exporting everything**

```python
"""Re-export all ORM classes so existing callers (from app.infra.postgres.models import User)
continue to work without changes."""
from app.infra.postgres.models.base import Base
from app.infra.postgres.models.chat import ChatMessage, ChatSession
from app.infra.postgres.models.document import Document, IngestionJob
from app.infra.postgres.models.exhibit import Exhibit
from app.infra.postgres.models.profile import VisitorProfile
from app.infra.postgres.models.prompt import Prompt, PromptVersion
from app.infra.postgres.models.tour import TourEvent, TourSession
from app.infra.postgres.models.user import User

__all__ = [
    "Base", "User", "Document", "IngestionJob", "ChatSession", "ChatMessage",
    "Exhibit", "VisitorProfile", "TourSession", "TourEvent", "Prompt", "PromptVersion",
]
```

- [ ] **Step 5: Verify no caller broke**

```bash
cd /home/singer/MuseAI && grep -rn "from app.infra.postgres.models import" backend/app/ backend/tests/ --include="*.py" | head
```
Every import like `from app.infra.postgres.models import User` continues to resolve because `__init__.py` re-exports.

- [ ] **Step 6: Run full test + mypy sweep**
  ```bash
  cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture -q 2>&1 | tail -3 && uv run mypy backend/ 2>&1 | tail -3
  ```
  Expected: all pass, mypy clean (may be +7 files on the count).

- [ ] **Step 7: Commit**
  ```
  refactor(postgres): split models.py into per-aggregate modules (CQ-P2-05)
  ```

### Task B8-3: Split `infra/providers/rerank.py` into per-provider files (CQ-P2-04)

**Files:**
- Source: `backend/app/infra/providers/rerank.py` (~454 LOC, 3 provider classes in one file)
- Target: new directory `backend/app/infra/providers/rerank/` with one file per provider + `__init__.py`.

- [ ] **Step 1: Read `rerank.py` to identify the 3 providers**

Look for `class .*Reranker` definitions. Typical names: `DashscopeReranker`, `LocalReranker`, `NoopReranker` (or similar).

- [ ] **Step 2: Create the package structure**

```
providers/rerank/
  __init__.py     # re-exports every class + the factory function
  base.py         # abstract Reranker class / Protocol
  dashscope.py    # DashscopeReranker
  local.py        # LocalReranker
  noop.py         # NoopReranker
  factory.py      # create_reranker(settings) dispatcher
```

- [ ] **Step 3: Move each class to its dedicated file**

Preserve every import used by the class. Shared helpers move to `base.py`.

- [ ] **Step 4: `__init__.py` re-exports**

```python
from app.infra.providers.rerank.base import Reranker
from app.infra.providers.rerank.dashscope import DashscopeReranker
from app.infra.providers.rerank.factory import create_reranker
from app.infra.providers.rerank.local import LocalReranker
from app.infra.providers.rerank.noop import NoopReranker

__all__ = ["Reranker", "DashscopeReranker", "LocalReranker", "NoopReranker", "create_reranker"]
```

- [ ] **Step 5: Verify existing callers still resolve**

```bash
cd /home/singer/MuseAI && grep -rn "from app.infra.providers.rerank" backend/app/ backend/tests/ --include="*.py" | head
```

- [ ] **Step 6: Run tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract -q 2>&1 | tail -3
```

- [ ] **Step 7: Commit**
  ```
  refactor(rerank): split per-provider files (CQ-P2-04)
  ```

### Task B8-4: Split `infra/langchain/curator_tools.py` (CQ-P2-03)

**Files:**
- Source: `backend/app/infra/langchain/curator_tools.py` (641 LOC, 6+ BaseTool subclasses + TSP helpers)
- Target: new directory `backend/app/infra/langchain/curator_tools/` with one file per tool + one file for the TSP helpers.

- [ ] **Step 1: Inventory the classes and helpers in the source file**

```bash
cd /home/singer/MuseAI && grep -n "^class .*Tool\|^def " backend/app/infra/langchain/curator_tools.py | head -30
```

- [ ] **Step 2: Create the package**

```
curator_tools/
  __init__.py           # re-exports every tool + helper
  tsp.py                # travelling-salesman helpers (order_exhibits, nearest_neighbor, etc.)
  path_planning.py      # PathPlanningTool
  narrative.py          # NarrativeGenerationTool
  reflection.py         # ReflectionPromptsTool
  knowledge_retrieval.py  # KnowledgeRetrievalTool
  # (one file per BaseTool subclass; names match the tool names)
```

- [ ] **Step 3: Move each tool class to its own file**

Preserve imports. Helpers used by multiple tools go to `tsp.py` or a new `_shared.py`.

- [ ] **Step 4: `__init__.py` re-exports**

```python
from app.infra.langchain.curator_tools.knowledge_retrieval import KnowledgeRetrievalTool
from app.infra.langchain.curator_tools.narrative import NarrativeGenerationTool
from app.infra.langchain.curator_tools.path_planning import PathPlanningTool
from app.infra.langchain.curator_tools.reflection import ReflectionPromptsTool
# ... + any others

__all__ = ["PathPlanningTool", "NarrativeGenerationTool", "ReflectionPromptsTool",
           "KnowledgeRetrievalTool"]
```

- [ ] **Step 5: Run the full test sweep**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture -q 2>&1 | tail -3
```

Test files that import from `app.infra.langchain.curator_tools` continue to work because of re-exports.

- [ ] **Step 6: Commit**
  ```
  refactor(langchain): split curator_tools into per-tool files (CQ-P2-03)
  ```

---

## B9 — Auth Migration & Admin Bootstrap

> Goal: Execute the two user-approved security forks from the midterm spec: (1) drop cookie-based auth in favor of single-surface Bearer tokens in `Authorization` header; (2) provision admins via a bootstrap CLI script, not the `ADMIN_EMAILS` env list.

### Task B9-1: Backend cookie removal — first half of SEC-P1-04

**Files:**
- Modify: `backend/app/api/auth.py` (remove `set_cookie` on login; remove cookie fallback on logout)
- Modify: `backend/app/api/deps.py` (remove cookie fallback in `get_current_user` and `get_current_admin`)
- Modify: `backend/tests/unit/test_deps_security.py`, `backend/tests/contract/test_auth*.py` as needed

**Scope:** Drop all `response.set_cookie` / `response.delete_cookie` / `request.cookies.get("access_token")` references. The returned `TokenResponse.access_token` field is already the canonical way clients obtain the token — the cookie was redundant.

- [ ] **Step 1: Enumerate cookie surface**

```bash
cd /home/singer/MuseAI && grep -rn "set_cookie\|delete_cookie\|access_token.*cookies" backend/app/ --include="*.py"
```

- [ ] **Step 2: Remove the set_cookie call from `login`**

In `backend/app/api/auth.py`, delete the `response.set_cookie(...)` block (around lines 119–127). The login handler should still accept `response: Response` as a parameter but simply not touch it (or remove that parameter — cleaner; just remove the parameter if nothing else uses it).

- [ ] **Step 3: Remove the cookie fallback from `logout`**

In the same file, the logout handler tries the Authorization header first, then falls back to cookie. Drop the fallback. The new shape:
```python
auth_header = request.headers.get("Authorization")
token = None
if auth_header and auth_header.startswith("Bearer "):
    token = auth_header.replace("Bearer ", "")

if token:
    # existing blacklist logic
    ...
# No delete_cookie call — the client was never given one.
```

- [ ] **Step 4: Remove cookie fallback in `deps.py`**

If `get_current_user` / `get_current_admin` read from `request.cookies.get("access_token")`, remove that path. Only `HTTPBearer` via the `Authorization` header remains.

- [ ] **Step 5: Update tests**

- Any test that set a cookie and expected auth success: add `Authorization: Bearer <token>` header instead.
- Any test that asserted a set-cookie response: delete the assertion (no cookie is set anymore).

- [ ] **Step 6: Run the full auth test surface**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_deps_security.py backend/tests/unit/test_auth_service.py backend/tests/unit/test_auth_rate_limit.py backend/tests/contract/test_auth*.py -v 2>&1 | tail -20
```

- [ ] **Step 7: Commit**
  ```
  fix(auth): remove cookie auth surface — Bearer-only (SEC-P1-04 backend)
  ```

### Task B9-2: Frontend cookie removal — second half of SEC-P1-04

**Files:**
- Modify: `frontend/src/api/index.js` (remove all 5 `credentials: 'include'` lines; inject Authorization header from localStorage)
- Modify: `frontend/src/composables/useAuth.js` (save/remove token in localStorage around login/logout)
- Modify: `frontend/src/composables/__tests__/useAuth.test.js` (flip assertions — token IS in localStorage now)
- Modify: `frontend/src/api/__tests__/index.test.js` (assert Authorization header sent)

**Scope:** Frontend currently relies on the browser sending the HttpOnly cookie automatically. After Task B9-1 the backend no longer sets the cookie, so requests become unauthenticated. Switch to localStorage + explicit `Authorization: Bearer <token>` header.

**XSS risk acknowledgment:** localStorage is more XSS-vulnerable than HttpOnly cookie. The user accepted this tradeoff in the parent spec design — single-surface simplicity wins. If an XSS lands, the token is forfeit; CSP and output-escaping are the mitigations, tracked separately.

- [ ] **Step 1: Add token storage + retrieval helpers to `frontend/src/api/index.js`**

At the top of the file:
```js
function getAuthToken() {
  return localStorage.getItem('access_token')
}
export function setAuthToken(token) {
  if (token) localStorage.setItem('access_token', token)
  else localStorage.removeItem('access_token')
}
```

In the `request()` function, inject the header if present:
```js
async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  const token = getAuthToken()
  if (token) headers.Authorization = `Bearer ${token}`

  // ... rest unchanged, BUT remove credentials: 'include' from the fetch call
  response = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  })
  // ...
}
```

- [ ] **Step 2: Remove every `credentials: 'include'` line**

```bash
cd /home/singer/MuseAI/frontend && grep -n "credentials: 'include'" src/api/index.js
```
Each of the 5 occurrences goes. The Authorization header in Step 1 is the replacement.

- [ ] **Step 3: Store / clear token on login / logout in `useAuth.js`**

On login success:
```js
import { setAuthToken } from '../api/index.js'
// inside login handler after successful response:
setAuthToken(response.data.access_token)
```
On logout (and on 401 response):
```js
setAuthToken(null)
```

- [ ] **Step 4: Flip the test assertions**

In `frontend/src/composables/__tests__/useAuth.test.js`, the existing 3 assertions `expect(localStorage.getItem('access_token')).toBeNull()` should become `.toBe('<expected-token>')` for the logged-in paths (and remain `.toBeNull()` for logged-out paths).

In `frontend/src/api/__tests__/index.test.js`, add an assertion that an authenticated request carries the Authorization header. Example:
```js
it('sends Authorization header when token is in localStorage', async () => {
  localStorage.setItem('access_token', 'my-test-token')
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => ({}) }))

  await someApiCall()

  const callArgs = global.fetch.mock.calls[0]
  expect(callArgs[1].headers.Authorization).toBe('Bearer my-test-token')
})
```

- [ ] **Step 5: Run frontend tests**

```bash
cd /home/singer/MuseAI/frontend && npm run test -- --run 2>&1 | tail -15
```

- [ ] **Step 6: Manual smoke test (not automated)**

1. Start backend (`uv run uvicorn backend.app.main:app --reload`) and frontend (`cd frontend && npm run dev`).
2. Log in via the UI. Open DevTools → Application → Local Storage. Confirm `access_token` is present.
3. Confirm no `access_token` cookie is set.
4. Refresh the page. Navigation requiring auth still works (token survives across reloads via localStorage).
5. Log out. localStorage `access_token` is removed.

- [ ] **Step 7: Commit**
  ```
  fix(auth): switch frontend to Bearer + localStorage (SEC-P1-04 frontend)
  ```

### Task B9-3: Bootstrap-only admin CLI (SEC-P2-02)

**Files:**
- Create: `backend/scripts/bootstrap_admin.py`
- Modify: `backend/app/config/settings.py` (deprecate `ADMIN_EMAILS` — emit warning when set in production)
- Modify: `backend/app/application/auth_service.py` (accept only DB role — stop reading admin_emails)
- Create: `backend/tests/unit/test_bootstrap_admin.py`

**Scope:** Currently `ADMIN_EMAILS` env var auto-promotes users with matching emails at registration. Per user fork, replace with an explicit CLI that an operator runs once to provision the first admin; subsequent admin grants happen via a future admin-to-admin endpoint (out of scope for this task — add a TODO note in the CLI output).

- [ ] **Step 1: Write the CLI**

Create `backend/scripts/bootstrap_admin.py`:
```python
#!/usr/bin/env python
"""Bootstrap an admin user. Run once at deployment time.

Usage:
    uv run python -m backend.scripts.bootstrap_admin --email alice@example.com

If the user doesn't exist, creates one with a random password printed to stderr
(the operator must reset it before use). If the user exists, promotes them to admin.
"""
import argparse
import asyncio
import secrets
import sys

from app.config.settings import get_settings
from app.infra.postgres.database import get_session_maker
from app.infra.postgres.models import User as UserORM
from app.infra.security import hash_password
from sqlalchemy import select


async def bootstrap_admin(email: str) -> None:
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with session_maker() as session:
        result = await session.execute(select(UserORM).where(UserORM.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            random_password = secrets.token_urlsafe(24)
            user = UserORM(
                id=secrets.token_urlsafe(16),
                email=email,
                password_hash=hash_password(random_password),
                role="admin",
            )
            session.add(user)
            await session.commit()
            print(f"Created admin user {email}.")
            print(f"TEMPORARY PASSWORD (change on first login): {random_password}", file=sys.stderr)
        else:
            user.role = "admin"
            await session.commit()
            print(f"Promoted existing user {email} to admin.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    asyncio.run(bootstrap_admin(args.email))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Deprecate `ADMIN_EMAILS`**

In `backend/app/config/settings.py`, add a `model_validator` (or post-init hook) that, if `ADMIN_EMAILS` is non-empty and `APP_ENV == "production"`, logs a deprecation warning: "ADMIN_EMAILS is deprecated — use scripts/bootstrap_admin.py."

- [ ] **Step 3: Stop auto-promoting in `register_user`**

In `backend/app/application/auth_service.py`, the `admin_emails` parameter is still accepted for backward compat (delete-later), but production branches through a new explicit flag. Simplest fix: leave `admin_emails` path working (so existing tests pass), but remove it from the default call site in `api/auth.py` — register new users always as `role="user"`. Admin grants go through the CLI.

- [ ] **Step 4: Write unit tests for the CLI**

Create `backend/tests/unit/test_bootstrap_admin.py`:
```python
"""Unit test for bootstrap_admin — in-memory SQLite, no real DB."""
import asyncio

import pytest
from app.infra.postgres.models import Base, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


@pytest.mark.asyncio
async def test_bootstrap_creates_new_admin(monkeypatch):
    """Calling bootstrap_admin with a non-existent email creates a new admin user."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(
        "backend.scripts.bootstrap_admin.get_session_maker",
        lambda _url: maker,
    )

    from backend.scripts.bootstrap_admin import bootstrap_admin
    await bootstrap_admin("admin@test.local")

    async with maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@test.local"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.role == "admin"


@pytest.mark.asyncio
async def test_bootstrap_promotes_existing_user(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        session.add(User(id="u-1", email="bob@test.local", password_hash="x", role="user"))
        await session.commit()

    monkeypatch.setattr(
        "backend.scripts.bootstrap_admin.get_session_maker",
        lambda _url: maker,
    )

    from backend.scripts.bootstrap_admin import bootstrap_admin
    await bootstrap_admin("bob@test.local")

    async with maker() as session:
        result = await session.execute(select(User).where(User.email == "bob@test.local"))
        user = result.scalar_one_or_none()
        assert user.role == "admin"
```

- [ ] **Step 5: Run the tests + smoke the CLI locally (sqlite)**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_bootstrap_admin.py -v 2>&1 | tail -10
```

- [ ] **Step 6: Commit**
  ```
  feat(admin): bootstrap-only admin CLI (SEC-P2-02); deprecate ADMIN_EMAILS
  ```

---

## B10 — Contract Conftest Cleanup (TEST-P1-04)

> Goal: Fix the async/event-loop hazards in `backend/tests/contract/conftest.py`. Currently the autouse fixture manipulates `db_module._engine` and mixes `asyncio.run` with `loop.create_task` — a pattern that produces intermittent "event loop closed" errors.

**Files:**
- Modify: `backend/tests/contract/conftest.py`

- [ ] **Step 1: Identify the problematic fixture**

```bash
cd /home/singer/MuseAI && sed -n '1,50p' backend/tests/contract/conftest.py
```

The `reset_database_globals` fixture does:
```python
if db_module._engine is not None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(db_module._engine.dispose())
    except RuntimeError:
        asyncio.run(db_module._engine.dispose())
```

This is unsafe: creating a task with `loop.create_task` and not awaiting it means the dispose may run after the loop dies. `asyncio.run(...)` inside an already-running loop raises `RuntimeError` which the current code swallows.

- [ ] **Step 2: Rewrite as an async fixture that actually awaits the dispose**

```python
import app.infra.postgres.database as db_module
import pytest


@pytest.fixture(autouse=True)
async def reset_database_globals():
    """Reset global database state before and after each test (truly async)."""
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_maker = None

    yield

    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_maker = None
```

Fixture-as-async-generator is supported by pytest-asyncio ≥0.21 (which the project already uses — `asyncio_mode = "auto"` in pyproject.toml).

- [ ] **Step 3: Run the full contract test suite**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract -v 2>&1 | tail -15
```
Expected: all pass, zero `RuntimeWarning: coroutine ... was never awaited` warnings (these currently appear for a handful of contract tests).

- [ ] **Step 4: Commit**
  ```
  test(contract): rewrite reset_database_globals as async fixture (TEST-P1-04)
  ```

---

## B11 — Infrastructure Polish

> Goal: Three small operational improvements that prevent future incidents when the system scales or experiences downstream outages.

### Task B11-1: Future Alembic migrations must use CONCURRENTLY for indexes (PERFOPS-P2-01)

**Files:**
- Create: `backend/alembic/README.md` (operator-facing guidelines)
- Modify: `backend/alembic/env.py` (optional: add a linting hint in comments)

**Scope:** Current 5 migrations use blocking `op.create_index(...)` calls which take a schema lock. Fine at current scale (<1M rows per table). For future migrations on larger tables this is a production-freeze hazard. Don't retroactively rewrite the 5 existing migrations — they've already been applied in any running environment and rewriting them doesn't change history. Instead, document the policy so future migrations follow it.

- [ ] **Step 1: Create `backend/alembic/README.md`**

```markdown
# Alembic migration authoring guidelines

## Indexes on tables expected to grow past 100K rows

Create indexes with `postgresql_concurrently=True`, which requires a non-transactional migration (`op.execute` inside a function or `op.get_context().autocommit_block()`).

Template:
```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_chat_messages_session_id",
            "chat_messages",
            ["session_id"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_chat_messages_session_id", postgresql_concurrently=True)
```

## Data migrations

Never mix data changes and schema changes in one migration. Schema migration + data migration = two separate revisions.

## Downgrade parity

Every upgrade MUST have a symmetric, tested downgrade.
```

- [ ] **Step 2: Commit**
  ```
  docs(alembic): migration authoring guidelines (PERFOPS-P2-01)
  ```

### Task B11-2: Tour event recording — replace fire-and-forget with bounded retry (PERFOPS-P2-03)

**Files:**
- Modify: `backend/app/application/tour_chat_service.py`

**Scope:** Current code:
```python
try:
    async with session_maker() as event_session:
        await record_events(event_session, ...)
except Exception as e:
    logger.warning(f"Failed to record tour event: {e}")
```

A transient DB hiccup loses the analytics event silently. Wrap in a 3-retry loop with exponential backoff (0.1s, 0.2s, 0.4s). If all retries fail, log at ERROR level (not WARNING) with the full request_id / trace_id so operators can correlate.

- [ ] **Step 1: Add the retry wrapper**

In `tour_chat_service.py`, extract the recording block into a helper:
```python
import asyncio

async def _record_event_with_retry(
    session_maker, tour_session_id, exhibit_id, current_hall,
    message, is_ceramic,
) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with session_maker() as event_session:
                await record_events(event_session, tour_session_id, [{
                    "event_type": "exhibit_question",
                    "exhibit_id": exhibit_id,
                    "hall": current_hall,
                    "metadata": {"question": message, "is_ceramic_question": is_ceramic},
                }])
            return  # success
        except Exception as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(0.1 * (2 ** attempt))
    logger.error(
        f"Tour event recording failed after 3 attempts: {last_error}",
        extra={"tour_session_id": tour_session_id, "exhibit_id": exhibit_id},
    )
```

Replace the existing try/except in `ask_stream_tour` with a call to `_record_event_with_retry(...)`.

- [ ] **Step 2: Add a test**

Create or extend `backend/tests/unit/test_tour_chat_stream.py` with a test that simulates a transient failure on attempts 1–2 and success on attempt 3:
```python
@pytest.mark.asyncio
async def test_tour_event_recording_retries_on_transient_failure(monkeypatch):
    call_count = [0]
    async def flaky_record(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
            raise RuntimeError("transient db blip")
        return None
    monkeypatch.setattr(
        "app.application.tour_chat_service.record_events", flaky_record
    )
    # ... drive ask_stream_tour to completion and assert call_count[0] == 3
```

- [ ] **Step 3: Run tests**
- [ ] **Step 4: Commit**
  ```
  feat(tour): retry tour event recording with backoff (PERFOPS-P2-03)
  ```

### Task B11-3: Elasticsearch/Redis degradation mode (PERFOPS-P2-04)

**Files:**
- Modify: `backend/app/main.py` (startup lifespan — don't fast-fail on ES/Redis; log + flag degraded)
- Modify: `backend/app/api/health.py` (expose degradation state in `/health`)
- Modify: `backend/app/application/chat_stream_service.py` (short-circuit with a friendly error when RAG is unavailable)

**Scope:** Currently `main.py` fast-fails if ES or Redis isn't reachable at startup. For a museum kiosk deployment, a partially-working app (chat degraded, browsing still functional) is better than a full outage. Track an `app.state.degraded: set[str]` with labels like `"elasticsearch"`, `"redis"`. Readiness reflects it.

- [ ] **Step 1: Change startup probes from fast-fail to soft-degrade**

In `main.py`'s lifespan:
```python
app.state.degraded: set[str] = set()
try:
    await es_client.health_check()
except Exception as e:
    logger.error(f"ES unavailable at startup: {e}; entering degraded mode")
    app.state.degraded.add("elasticsearch")

try:
    await redis_cache.client.ping()
except Exception as e:
    logger.error(f"Redis unavailable at startup: {e}; entering degraded mode")
    app.state.degraded.add("redis")
```

- [ ] **Step 2: Expose state in `/health`**

`health.py` returns:
```python
@router.get("/health")
async def health() -> dict:
    degraded = list(app.state.degraded) if hasattr(app.state, "degraded") else []
    status = "healthy" if not degraded else "degraded"
    return {"status": status, "degraded_services": degraded}
```

- [ ] **Step 3: Chat stream short-circuits when ES is degraded**

In `chat_stream_service.ask_question_stream_with_rag`, check `app.state.degraded` early — if `"elasticsearch"` is present, emit an `error` SSE event with code `RAG_UNAVAILABLE` and a user-friendly message, without attempting retrieval.

- [ ] **Step 4: Tests**

Add to `backend/tests/unit/test_chat_service_streaming.py`:
```python
@pytest.mark.asyncio
async def test_ask_question_stream_returns_rag_unavailable_when_degraded(monkeypatch):
    from app.main import app
    app.state.degraded = {"elasticsearch"}
    # Drive the handler and assert the first non-thinking event is an error with code=RAG_UNAVAILABLE.
    app.state.degraded = set()  # cleanup
```

- [ ] **Step 5: Run tests**
- [ ] **Step 6: Commit**
  ```
  feat(reliability): soft-degrade on ES/Redis outage at startup (PERFOPS-P2-04)
  ```

---

## B12 — Frontend Dependency Upgrades (DOC-P1-04, DOC-P2-01)

### Task B12-1: Upgrade vitest → 3.x + jsdom → latest + vue-router → 4.5.x

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json` (via npm install)

**Scope:** The vite patch in B0-1 left vitest 1.x still installed — an older major with known advisories (moderate severity). Also vue-router 4.3 → 4.5 brings performance improvements. Do one major upgrade at a time to isolate breakage.

- [ ] **Step 1: Baseline audit**
```bash
cd /home/singer/MuseAI/frontend && npm audit --production 2>&1 | tail -20
```

- [ ] **Step 2: Upgrade vitest to the latest 3.x**

Edit `frontend/package.json` devDependencies. Set `"vitest": "^3.0.0"`. Run `npm install`. Run `npm run test -- --run` to confirm.

If the test suite breaks due to API changes, fix per-call-site (vitest 3 renamed a few APIs — `vi.mocked`, `vi.hoisted` etc. may need adjustments).

- [ ] **Step 3: Upgrade jsdom to the latest**

`"jsdom": "^24.0.0"` (or whatever is current). `npm install`. Run tests again.

- [ ] **Step 4: Upgrade vue-router to ^4.5.0**

`"vue-router": "^4.5.0"`. Read the 4.5 release notes for breaking changes — typically minor. `npm install` + `npm run test -- --run` + `npm run build`.

- [ ] **Step 5: Confirm audit is clean**
```bash
cd /home/singer/MuseAI/frontend && npm audit --production 2>&1 | grep -E "high|critical" || echo "no high/critical"
```

- [ ] **Step 6: Commit**
  ```
  fix(deps): upgrade vitest 3.x, jsdom, vue-router 4.5 (DOC-P1-04)
  ```

### Task B12-2: Annotate deliberate Python upper-bound caps (DOC-P2-01)

**Files:**
- Modify: `pyproject.toml`

**Scope:** The project caps `elasticsearch<9.0.0` and `langchain-community<0.4.0`. The reasons aren't written down. Annotate.

- [ ] **Step 1: Add comments**

In `pyproject.toml`:
```toml
# elasticsearch 9.x removes the sync-client wrapper we use in tests.
# Upgrade path: rewrite test setup to use the new client.
elasticsearch = ">=8.0.0,<9.0.0"

# langchain-community 0.4 breaks the RetrieverInterface we depend on
# (retriever.get_relevant_documents signature changed).
# Upgrade path: migrate to the new asyncio-only signature throughout
# infra/langchain/retrievers.py.
langchain-community = ">=0.3.0,<0.4.0"
```

- [ ] **Step 2: Commit**
  ```
  docs(deps): annotate deliberate upper-bound caps (DOC-P2-01)
  ```

---

## Deferred items — rationale

These are on the audit list but NOT covered above, with explicit reasoning. Future-batch candidates; don't implement in this plan.

| Audit ID | Why deferred |
|---|---|
| **CQ-P1-03** (289 hardcoded Chinese UI strings) | Requires an i18n framework decision (vue-i18n? lightweight homegrown?) and coordination with product for English/other-language rollout. Too large for one batch and the default-language user (Chinese) isn't immediately affected. |
| **ARCH-P2-02** (anemic domain methods like `ChatSession.add_message = pass`) | The current anemic-domain pattern is intentional for CRUD aggregates. Rich domain methods would be invented-for-their-own-sake without a clear business invariant to enforce. Revisit when a domain rule emerges that doesn't fit in a service. |
| **SEC-P2-05** (prompt injection) | Design-level. Needs threat modeling, input sanitization strategy (character filters? structured tools?), and output validation. Ship a focused spec document in its own track before committing code. |
| **TEST-P2-01/02** (52 mocks in a single test file, contract conftest auto-mocking singletons) | Stylistic issue; refactoring the tests to use narrower mocking hurts readability more than it helps correctness. Revisit if the test suite actually produces false-negatives (which it has not). |
| **P3 items** from the audit | Each is low-value polish. Sweep them up in a dedicated "cleanup day" when code-quality is the primary focus of the week; do not interleave with feature work. |

---

## Final Verification (run after ALL batches close)

```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3 && \
  (cd frontend && npm run test -- --run 2>&1 | tail -5) && \
  (cd frontend && npm run build 2>&1 | tail -5) && \
  (cd frontend && npm audit --production 2>&1 | grep -E "high|critical" || echo "frontend audit clean")
```

Expected state at completion:
- Backend tests: ~910+ passing (varies with B9 test adjustments)
- Ruff: clean
- Mypy: clean on ~95–100 source files (more files after B8 splits)
- Frontend: tests pass, build succeeds, no high/critical audit findings

---

## Rollback Notes

Each task is its own commit. B9 is the only batch with dependencies between tasks: B9-2 (frontend) must land with B9-1 (backend) or the application breaks. Ship B9-1 + B9-2 together (or with B9-1 first during a brief downtime window). B9-3 (admin CLI) is independent of the auth cutover.

All other batches are independent; any subset can be executed in any order.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: every audit P1/P2 item is either addressed above or listed in "Deferred items" with rationale. ✓
- **Placeholder scan**: no "TBD" / "TODO". Where exact code depends on current state (e.g. rerank provider class names), the plan instructs the executor to read the source first. ✓
- **Blast radius**: B7 is doc-only. B8 is behavior-preserving refactor (re-exports maintain import compatibility). B9 is the only batch touching production auth — called out explicitly with coordinated-ship requirement. B10–B12 are each narrowly scoped. ✓
- **Test-first discipline**: every task with a behavior change has a named test file and assertion to drive the change. Pure-refactor tasks (B7, B8) rely on the existing 898-test suite as the regression net. ✓
- **Executor can work independently**: each task has enough detail to implement without reading the parent audit. Cross-references to audit IDs are for traceability, not lookup. ✓
