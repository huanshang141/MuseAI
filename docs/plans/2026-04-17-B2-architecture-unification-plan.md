# B2 Architecture Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six-site `infra/langchain/* → app.application.*` reverse-dependency (SYS-1) and collapse the dual-Port surface (SYS-2) into a single `application/ports/` convention. Along the way: relocate `rrf_fusion` to `domain/services/`, consolidate repository adapters into `infra/postgres/adapters/`, kill the circular-import workaround in `document_service.py`, and absorb `workflows/` into `application/workflows/` with explicit dependency injection (no more module-level mutable `set_prompt_gateway`). By the end of this batch, `KNOWN_VIOLATIONS` in `test_layer_import_rules.py` is empty, `test_known_violations_still_exist` guards against regression, and the dependency direction of the entire backend is machine-enforced.

**Architecture:** Seven tasks, each independently revertable. Tasks 1-4 perform the port moves that remove each KNOWN_VIOLATIONS entry. Task 5 consolidates adapters (pure file move + import updates; no behavior change). Task 6 removes the `noqa: E402` in `document_service.py` now that its cause (circular via the pre-move layout) is resolved. Task 7 absorbs `workflows/` into `application/workflows/` with constructor injection replacing the module-level setter. Task 8 confirms `KNOWN_VIOLATIONS` is empty and does final verification.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x async, LangChain/LangGraph, ruff, mypy, pytest. No runtime framework changes; only import paths, file locations, and a couple of small class refactors.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B2.

**Related audit findings:** ARCH-P1-01 (infra reverse-deps), ARCH-P1-02 (dual ports), ARCH-P1-03 (workflows layer), ARCH-P2-01 (adapter file layout), ARCH-P2-03 (module-level mutable), ARCH-P2-04 (circular import noqa), CQ-P2-01, CQ-P2-02.

**Depends on:** B1 complete (strict layer rules + KNOWN_VIOLATIONS allowlist enforcement). Without B1-2, the layer test won't fail on regressions introduced during this refactor.

---

## Current State Baseline

Established during planning (2026-04-17/18):

### KNOWN_VIOLATIONS (in `backend/tests/architecture/test_layer_import_rules.py`)
```python
{
    ("infra/langchain/agents.py",         "app.application.prompt_gateway"),       # → B2-2
    ("infra/langchain/__init__.py",       "app.application.prompt_gateway"),       # → B2-2
    ("infra/langchain/curator_agent.py",  "app.application.prompt_gateway"),       # → B2-2
    ("infra/langchain/curator_tools.py",  "app.application.prompt_gateway"),       # → B2-2
    ("infra/langchain/tools.py",          "app.application.context_manager"),      # → B2-2
    ("infra/langchain/retrievers.py",     "app.application.retrieval"),            # → B2-3
}
```
All 6 entries must be removed over Tasks 2-4. The `test_known_violations_still_exist` hygiene test will fail if any removal is incomplete — this is the acceptance gate.

### Dual Port map
- `domain/repositories.py`: `ExhibitRepository`, `TourPathRepository`, `VisitorProfileRepository` (3 Protocols) — to delete
- `application/ports/repositories.py`: `UserRepositoryPort`, `DocumentRepositoryPort`, `ExhibitRepositoryPort`, `VisitorProfileRepositoryPort`, `ChatSessionRepositoryPort`, `ChatMessageRepositoryPort`, `LLMProviderPort`, `CachePort`, `CuratorAgentPort` — to keep + extend
- `TourPathRepository` is **defined but never used** (grep confirmed): do NOT add `TourPathRepositoryPort` — YAGNI.

### Domain-repository callers (2 total)
- `backend/app/application/exhibit_service.py:6` — `from app.domain.repositories import ExhibitRepository`
- `backend/app/application/profile_service.py:6` — `from app.domain.repositories import VisitorProfileRepository`

### Infra reverse-dep callers (6 total)
See KNOWN_VIOLATIONS table above.

### Postgres adapter layout
| Current | After B2-4 |
|---|---|
| `infra/postgres/adapters/auth_repository.py` — `PostgresUserRepository` | unchanged |
| `infra/postgres/adapters/document_repository.py` — `PostgresDocumentRepository` | unchanged |
| `infra/postgres/repositories.py` — `PostgresExhibitRepository` + `PostgresVisitorProfileRepository` | split into `adapters/exhibit_repository.py` + `adapters/visitor_profile_repository.py`; delete `repositories.py` |
| `infra/postgres/prompt_repository.py` — `PostgresPromptRepository` | move to `adapters/prompt_repository.py` |

### Workflows layout
- `backend/app/workflows/reflection_prompts.py` — has module-level mutable `_prompt_gateway` + `set_prompt_gateway()` (ARCH-P2-03)
- `backend/app/workflows/query_transform.py` — constructor-injects `prompt_gateway` ✓
- `backend/app/workflows/multi_turn.py` — imports `from app.infra.providers.llm import LLMProvider` (concrete, not a Port)
- `main.py:38,84` — `from app.workflows.reflection_prompts import set_prompt_gateway` + `set_prompt_gateway(prompt_gateway)` call

---

## File Structure — B2 end state

```
backend/app/
├── domain/
│   ├── services/                              NEW (Task 4)
│   │   ├── __init__.py
│   │   └── retrieval.py                       rrf_fusion (moved from application/retrieval.py)
│   └── repositories.py                        DELETED (Task 1)
├── application/
│   ├── ports/
│   │   ├── repositories.py                    unchanged — still the 9 *Port classes
│   │   ├── prompt_gateway.py                  NEW (Task 2) — PromptGateway Protocol
│   │   └── context_manager.py                 NEW (Task 3) — ConversationContextManagerPort Protocol
│   ├── workflows/                             NEW (Task 7)
│   │   ├── __init__.py
│   │   ├── reflection_prompts.py              moved + class refactor (no more globals)
│   │   ├── query_transform.py                 moved (imports updated)
│   │   └── multi_turn.py                      moved + LLMProvider → LLMProviderPort
│   ├── context_manager.py                     KEEP concrete class; now declares it implements the Port
│   ├── prompt_service_adapter.py              import PromptGateway from ports
│   ├── document_service.py                    import moved to TOP (noqa removed) — Task 6
│   ├── prompt_gateway.py                      DELETED (Task 2)
│   └── retrieval.py                           DELETED (Task 4)
├── infra/
│   ├── postgres/
│   │   ├── adapters/                          EXPANDED (Task 5)
│   │   │   ├── auth_repository.py             unchanged
│   │   │   ├── document_repository.py         unchanged
│   │   │   ├── exhibit_repository.py          NEW (split from repositories.py)
│   │   │   ├── visitor_profile_repository.py  NEW (split from repositories.py)
│   │   │   └── prompt_repository.py           moved from ../prompt_repository.py
│   │   ├── repositories.py                    DELETED
│   │   └── prompt_repository.py               DELETED
│   └── langchain/
│       ├── __init__.py                        import PromptGateway from ports
│       ├── agents.py                          import PromptGateway from ports
│       ├── curator_agent.py                   import PromptGateway from ports
│       ├── curator_tools.py                   import PromptGateway from ports
│       ├── retrievers.py                      import rrf_fusion from domain/services
│       └── tools.py                           import ConversationContextManagerPort from ports
└── workflows/                                 DELETED after Task 7 absorbs into application/workflows/
```

---

## Task 1: B2-1 — Port unification (delete `domain/repositories.py`)

**Scope:** 2 caller updates, 1 file deletion. `ExhibitRepository` and `VisitorProfileRepository` already have equivalents in `application/ports/repositories.py` (`ExhibitRepositoryPort`, `VisitorProfileRepositoryPort`) — this task changes the two callers to the canonical Port and deletes the old file. `TourPathRepository` is never used, so it is simply dropped.

**Files:**
- Modify: `backend/app/application/exhibit_service.py:6`
- Modify: `backend/app/application/profile_service.py:6`
- Delete: `backend/app/domain/repositories.py`

- [ ] **Step 1: Verify the current-state claims (no late surprises)**

Run:
```bash
cd /home/singer/MuseAI && rg -n "from app\.domain\.repositories|from app\.domain import repositories|TourPathRepository\b" backend/ 2>&1
```
Expected: exactly these 3 matches (and no others):
```
backend/app/application/exhibit_service.py:6:from app.domain.repositories import ExhibitRepository
backend/app/application/profile_service.py:6:from app.domain.repositories import VisitorProfileRepository
backend/app/domain/repositories.py:46:class TourPathRepository(Protocol):
```
If any other caller appears, STOP and amend this plan: an extra caller must be updated before the file can be deleted.

- [ ] **Step 2: Compare signatures to confirm swap is safe**

Open both protocol definitions side by side in your head:
- `domain/repositories.py:7-43` — `ExhibitRepository` — 13 methods
- `application/ports/repositories.py:55-97` — `ExhibitRepositoryPort` — same 13 methods, same signatures

Likewise for `VisitorProfileRepository` (4 methods) ↔ `VisitorProfileRepositoryPort` (4 methods).

Run a quick check:
```bash
cd /home/singer/MuseAI && python -c "
from app.domain.repositories import ExhibitRepository, VisitorProfileRepository
from app.application.ports.repositories import ExhibitRepositoryPort, VisitorProfileRepositoryPort
for dom, port in [(ExhibitRepository, ExhibitRepositoryPort), (VisitorProfileRepository, VisitorProfileRepositoryPort)]:
    dom_methods = {m for m in vars(dom) if not m.startswith('_')}
    port_methods = {m for m in vars(port) if not m.startswith('_')}
    missing = dom_methods - port_methods
    extra = port_methods - dom_methods
    print(f'{dom.__name__} vs {port.__name__}: missing in port={missing}, extra in port={extra}')
"
```
Expected: `missing in port=set(), extra in port=set()` for both pairs. If `missing` is non-empty, STOP and add the missing methods to the Port before proceeding.

- [ ] **Step 3: Swap imports in `exhibit_service.py`**

Edit `backend/app/application/exhibit_service.py:6`. Replace:
```python
from app.domain.repositories import ExhibitRepository
```
with:
```python
from app.application.ports.repositories import ExhibitRepositoryPort
```

Also replace every in-file use of the class name. Grep:
```bash
cd /home/singer/MuseAI && rg -n "ExhibitRepository\b" backend/app/application/exhibit_service.py
```
For each match, change `ExhibitRepository` → `ExhibitRepositoryPort`. Typical site: the constructor `def __init__(self, exhibit_repository: ExhibitRepository):` becomes `def __init__(self, exhibit_repository: ExhibitRepositoryPort):`.

- [ ] **Step 4: Swap imports in `profile_service.py`**

Mirror Step 3 for `backend/app/application/profile_service.py`:
```python
# old
from app.domain.repositories import VisitorProfileRepository
# new
from app.application.ports.repositories import VisitorProfileRepositoryPort
```
And rename all in-file `VisitorProfileRepository` references to `VisitorProfileRepositoryPort`.

- [ ] **Step 5: Delete `domain/repositories.py`**

Run:
```bash
cd /home/singer/MuseAI && rm backend/app/domain/repositories.py
```

- [ ] **Step 6: Confirm no stale references**

Run:
```bash
cd /home/singer/MuseAI && rg -n "from app\.domain\.repositories|from app\.domain import repositories|\bExhibitRepository\b|\bVisitorProfileRepository\b|\bTourPathRepository\b" backend/
```
Expected: empty (or only matches in the rewritten `*Port` form, which won't match the regex since it has a trailing `Port`).

- [ ] **Step 7: Run the full suite**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6 && uv run mypy backend/ 2>&1 | tail -3 && uv run ruff check backend/ 2>&1 | tail -3
```
Expected: 756 passed (same count as end of B1), mypy Success, ruff clean.

- [ ] **Step 8: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/application/exhibit_service.py backend/app/application/profile_service.py backend/app/domain/repositories.py && git commit -m "$(cat <<'EOF'
refactor(arch): delete domain/repositories.py — single Port surface (ARCH-P1-02)

ExhibitRepository and VisitorProfileRepository were Protocol duplicates of
ExhibitRepositoryPort/VisitorProfileRepositoryPort that already lived in
application/ports/repositories.py. Two callers (exhibit_service,
profile_service) moved to the canonical Port. TourPathRepository was
defined in domain/ but never used — dropped per YAGNI.

One Port surface now: application/ports/repositories.py. domain/ reverts
to pure entities + value objects.

Closes ARCH-P1-02 (port B2-1) and CQ-P2-02 from 2026-04-17 audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: B2-2a — Move `PromptGateway` Protocol into `application/ports/`

**Scope:** Create `application/ports/prompt_gateway.py` holding the `PromptGateway` Protocol; delete `application/prompt_gateway.py`; update 7 callers (incl. 4 KNOWN_VIOLATIONS entries); remove those 4 entries from the allowlist.

**Files:**
- Create: `backend/app/application/ports/prompt_gateway.py`
- Delete: `backend/app/application/prompt_gateway.py`
- Modify: 7 callers
- Modify: `backend/tests/architecture/test_layer_import_rules.py` (remove 4 entries from KNOWN_VIOLATIONS)

- [ ] **Step 1: Create the new port file**

Create `backend/app/application/ports/prompt_gateway.py` with contents:
```python
"""PromptGateway port — Protocol for prompt rendering.

Defines the interface that deep modules (infra/langchain, application/workflows)
use to render prompts without coupling to a specific implementation.
"""

from typing import Protocol


class PromptGateway(Protocol):
    """Protocol for rendering prompts with variable substitution."""

    async def render(self, key: str, variables: dict[str, str]) -> str | None:
        """Render a prompt with the given variables.

        Args:
            key: Unique prompt key
            variables: Dictionary of variables to substitute in the template

        Returns:
            Rendered prompt content if found, None otherwise
        """
        ...

    async def get(self, key: str) -> str | None:
        """Get raw prompt content without rendering.

        Args:
            key: Unique prompt key

        Returns:
            Raw prompt content if found, None otherwise
        """
        ...
```

(Content is byte-for-byte equivalent to the existing `application/prompt_gateway.py` class definition, minus the module-level docstring context.)

- [ ] **Step 2: Update every caller's import path**

Run:
```bash
cd /home/singer/MuseAI && rg -l "from app\.application\.prompt_gateway import PromptGateway" backend/
```
Expected output, 7 files:
- `backend/app/application/prompt_service_adapter.py`
- `backend/app/infra/langchain/agents.py`
- `backend/app/infra/langchain/__init__.py`
- `backend/app/infra/langchain/curator_agent.py`
- `backend/app/infra/langchain/curator_tools.py`
- `backend/app/workflows/reflection_prompts.py`
- `backend/app/workflows/query_transform.py`

For each file, replace:
```python
from app.application.prompt_gateway import PromptGateway
```
with:
```python
from app.application.ports.prompt_gateway import PromptGateway
```

(Use `sed -i 's|from app.application.prompt_gateway import PromptGateway|from app.application.ports.prompt_gateway import PromptGateway|' <file>` for each, OR make the edits individually.)

- [ ] **Step 3: Delete the old file**

Run:
```bash
cd /home/singer/MuseAI && rm backend/app/application/prompt_gateway.py
```

Verify no stragglers:
```bash
cd /home/singer/MuseAI && rg -n "from app\.application\.prompt_gateway|app\.application\.prompt_gateway" backend/
```
Expected: only `backend/tests/architecture/test_layer_import_rules.py` lines showing KNOWN_VIOLATIONS entries — those get deleted in Step 4.

- [ ] **Step 4: Remove the 4 prompt_gateway entries from KNOWN_VIOLATIONS**

Edit `backend/tests/architecture/test_layer_import_rules.py`. Remove the 4 B2-2 prompt_gateway entries so the remaining KNOWN_VIOLATIONS is:
```python
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # B2-2: move ConversationContextManager into application/ports/
    ("infra/langchain/tools.py", "app.application.context_manager"),
    # B2-3: move rrf_fusion to domain/services/retrieval.py
    ("infra/langchain/retrievers.py", "app.application.retrieval"),
}
```

- [ ] **Step 5: Run full verification**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6
```
Expected: 756 passed. In particular, `test_known_violations_still_exist` passes (no stale allowlist entries) and `test_infra_does_not_import_application_or_api` passes (only 2 violations left, both still in the updated allowlist).

```bash
cd /home/singer/MuseAI && uv run mypy backend/ && uv run ruff check backend/
```
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/application/ports/prompt_gateway.py backend/app/application/prompt_service_adapter.py backend/app/application/prompt_gateway.py backend/app/infra/langchain/ backend/app/workflows/reflection_prompts.py backend/app/workflows/query_transform.py backend/tests/architecture/test_layer_import_rules.py && git commit -m "$(cat <<'EOF'
refactor(arch): move PromptGateway to application/ports/ (ARCH-P1-01 part 1)

Four infra/langchain/* files + one workflows/ file + prompt_service_adapter
previously imported PromptGateway directly from application/. This is a
layering violation (infra → application). Moves the Protocol into
application/ports/prompt_gateway.py; infra and workflows now import from
the canonical ports location. Closes 4 of the 6 KNOWN_VIOLATIONS entries.

Closes ARCH-P1-01 (B2-2a) from 2026-04-17 audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: B2-2b — Define `ConversationContextManagerPort` in `application/ports/`

**Scope:** `ConversationContextManager` is a concrete class that `infra/langchain/tools.py` imports. Introduce a Protocol (`ConversationContextManagerPort`) and flip infra to import the Port. The concrete class stays in `application/context_manager.py` — it implements the Port by duck-typing.

**Files:**
- Create: `backend/app/application/ports/context_manager.py`
- Modify: `backend/app/infra/langchain/tools.py:11`
- Modify: `backend/tests/architecture/test_layer_import_rules.py` (remove B2-2 context_manager entry)

- [ ] **Step 1: Inspect concrete class to extract its surface**

Read the public methods used by `infra/langchain/tools.py`:
```bash
cd /home/singer/MuseAI && rg -n "context_manager\.\w+\(" backend/app/infra/langchain/tools.py
```
Expected: a handful of methods like `get_context`, `add_message`, `clear`, etc. Note the exact signatures used.

For a thorough view:
```bash
cd /home/singer/MuseAI && rg -n "^\s+(async )?def " backend/app/application/context_manager.py
```

- [ ] **Step 2: Create the port**

Create `backend/app/application/ports/context_manager.py`:
```python
"""ConversationContextManager port — Protocol for multi-turn context storage.

Deep modules (infra/langchain) use this Protocol to read/write conversation
context without depending on the concrete Redis-backed implementation that
lives in application/context_manager.py.
"""

from typing import Any, Protocol


class ConversationContextManagerPort(Protocol):
    """Protocol for storing and retrieving conversation context."""

    async def get_context(self, session_id: str) -> list[dict[str, Any]]:
        """Return the message history for a session (oldest first)."""
        ...

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's history."""
        ...

    async def clear(self, session_id: str) -> None:
        """Remove all context for a session."""
        ...
```

**Adjust method signatures to match the concrete class.** Before committing, compare:
```bash
cd /home/singer/MuseAI && python -c "
import inspect
from app.application.context_manager import ConversationContextManager
from app.application.ports.context_manager import ConversationContextManagerPort
c = {n: inspect.signature(getattr(ConversationContextManager, n)) for n in dir(ConversationContextManager) if not n.startswith('_') and callable(getattr(ConversationContextManager, n))}
p = {n: inspect.signature(getattr(ConversationContextManagerPort, n)) for n in dir(ConversationContextManagerPort) if not n.startswith('_') and callable(getattr(ConversationContextManagerPort, n))}
print('Concrete:', list(c.keys()))
print('Port:    ', list(p.keys()))
for name in p:
    if name not in c:
        print(f'PORT HAS {name} but CONCRETE DOES NOT')
    elif str(c[name]) != str(p[name]):
        print(f'SIGNATURE DIFF {name}: concrete={c[name]} port={p[name]}')
"
```
Expected: port methods are a subset of concrete methods with matching signatures. Port methods that `infra/langchain/tools.py` actually calls must all exist on the concrete class; otherwise adjust the Port to match.

- [ ] **Step 3: Flip the infra import**

Edit `backend/app/infra/langchain/tools.py:11`. Replace:
```python
from app.application.context_manager import ConversationContextManager
```
with:
```python
from app.application.ports.context_manager import ConversationContextManagerPort
```

Update every in-file use of the type name. Grep:
```bash
cd /home/singer/MuseAI && rg -n "ConversationContextManager\b" backend/app/infra/langchain/tools.py
```
For each match, change `ConversationContextManager` → `ConversationContextManagerPort`. Typical site: constructor parameter type annotations.

- [ ] **Step 4: Remove the context_manager entry from KNOWN_VIOLATIONS**

Edit `backend/tests/architecture/test_layer_import_rules.py`. After this task, KNOWN_VIOLATIONS should contain only:
```python
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # B2-3: move rrf_fusion to domain/services/retrieval.py
    ("infra/langchain/retrievers.py", "app.application.retrieval"),
}
```

- [ ] **Step 5: Verify**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6 && uv run mypy backend/ && uv run ruff check backend/
```
Expected: 756 passed, mypy Success, ruff clean. In particular, `test_infra_does_not_import_application_or_api` should find the `retrievers.py → app.application.retrieval` violation (last one) and allow it via the remaining KNOWN_VIOLATIONS entry.

- [ ] **Step 6: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/application/ports/context_manager.py backend/app/infra/langchain/tools.py backend/tests/architecture/test_layer_import_rules.py && git commit -m "$(cat <<'EOF'
refactor(arch): add ConversationContextManagerPort (ARCH-P1-01 part 2)

Introduce a Protocol in application/ports/ for ConversationContextManager
so infra/langchain/tools.py can depend on the port instead of the concrete
Redis-backed class. The concrete class in application/context_manager.py
satisfies the Port by structural typing (no explicit Protocol inheritance
required). One more KNOWN_VIOLATIONS entry closed.

Closes ARCH-P1-01 (B2-2b) from 2026-04-17 audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: B2-3 — Move `rrf_fusion` to `domain/services/retrieval.py`

**Scope:** `rrf_fusion` is a pure algorithm with no framework coupling. It belongs in `domain/services/` (algorithm), not `application/retrieval.py` (which, per DDD, should coordinate domain services rather than host them). Relocating unblocks the last KNOWN_VIOLATIONS entry.

**Files:**
- Create: `backend/app/domain/services/__init__.py`
- Create: `backend/app/domain/services/retrieval.py`
- Delete: `backend/app/application/retrieval.py`
- Modify: `backend/app/infra/langchain/retrievers.py` (3 sites at lines 8, 38, 93, 162)
- Modify: `backend/tests/unit/test_rag_fusion.py`
- Modify: `backend/tests/architecture/test_layer_import_rules.py` (remove last entry)

- [ ] **Step 1: Create domain/services package**

```bash
cd /home/singer/MuseAI && mkdir -p backend/app/domain/services
```

Create `backend/app/domain/services/__init__.py`:
```python
"""Domain services — stateless algorithms that operate on domain types.

Services in this package must not import from application/, infra/, or api/.
"""
```

- [ ] **Step 2: Move rrf_fusion**

Copy the full contents of `backend/app/application/retrieval.py` into `backend/app/domain/services/retrieval.py` unchanged. The file currently has only the `rrf_fusion` function and its imports (`from typing import Any`). No changes needed to the function body.

Run:
```bash
cd /home/singer/MuseAI && cp backend/app/application/retrieval.py backend/app/domain/services/retrieval.py
```

Verify identity:
```bash
cd /home/singer/MuseAI && diff backend/app/application/retrieval.py backend/app/domain/services/retrieval.py
```
Expected: empty output.

- [ ] **Step 3: Delete the old file**

```bash
cd /home/singer/MuseAI && rm backend/app/application/retrieval.py
```

- [ ] **Step 4: Update callers**

Three groups:

(a) `backend/app/infra/langchain/retrievers.py:8` — import:
```python
# old
from app.application.retrieval import rrf_fusion
# new
from app.domain.services.retrieval import rrf_fusion
```
(The 3 call sites at lines 38, 93, 162 use the imported name; they don't need changes.)

(b) `backend/tests/unit/test_rag_fusion.py:2`:
```python
# old
from app.application.retrieval import rrf_fusion
# new
from app.domain.services.retrieval import rrf_fusion
```

(c) Any other caller:
```bash
cd /home/singer/MuseAI && rg -n "from app\.application\.retrieval|app\.application\.retrieval" backend/
```
Expected: empty after (a) and (b). If any other caller appears, update them.

- [ ] **Step 5: Empty KNOWN_VIOLATIONS**

Edit `backend/tests/architecture/test_layer_import_rules.py`. After this task, KNOWN_VIOLATIONS must be literally empty:
```python
KNOWN_VIOLATIONS: set[tuple[str, str]] = set()
```

Leave the inline comment explaining the purpose of the structure so a future reviewer doesn't delete the mechanism:
```python
# KNOWN_VIOLATIONS: intentional exceptions to the layer rules, each paired with the
# batch/PR that will remove the entry. Prefer fixing the import over adding a row.
KNOWN_VIOLATIONS: set[tuple[str, str]] = set()
```

- [ ] **Step 6: Verify — all 6 KNOWN_VIOLATIONS now cleared**

```bash
cd /home/singer/MuseAI && rg -n "^from app\.application" backend/app/infra/ 2>&1
```
Expected: empty. This is the acceptance: zero infra→application imports.

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/architecture/test_layer_import_rules.py -v
```
Expected: all 8 tests PASS. `test_known_violations_still_exist` trivially passes for an empty set.

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6 && uv run mypy backend/ && uv run ruff check backend/
```
Expected: 756 passed, mypy Success, ruff clean.

- [ ] **Step 7: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/domain/services/ backend/app/application/retrieval.py backend/app/infra/langchain/retrievers.py backend/tests/unit/test_rag_fusion.py backend/tests/architecture/test_layer_import_rules.py && git commit -m "$(cat <<'EOF'
refactor(arch): move rrf_fusion to domain/services/retrieval.py (ARCH-P1-01 part 3)

The RRF algorithm has zero framework coupling (just `from typing import Any`)
and belongs with domain primitives. Moving it out of application/ closes the
last of the six infra→application KNOWN_VIOLATIONS entries from B2.

After this commit:
  rg '^from app.application' backend/app/infra/   →  empty
  KNOWN_VIOLATIONS in test_layer_import_rules.py  →  set()

Closes ARCH-P1-01 (B2-3) from 2026-04-17 audit; completes SYS-1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: B2-4 — Consolidate `infra/postgres/` adapters

**Scope:** Pure reorganization. Split `infra/postgres/repositories.py` into two adapter files; move `prompt_repository.py` into `adapters/`. Update imports at ~10 call sites. No behavior change.

**Files:**
- Create: `backend/app/infra/postgres/adapters/exhibit_repository.py` (split from `repositories.py`)
- Create: `backend/app/infra/postgres/adapters/visitor_profile_repository.py` (split from `repositories.py`)
- Create (move): `backend/app/infra/postgres/adapters/prompt_repository.py` (from `../prompt_repository.py`)
- Delete: `backend/app/infra/postgres/repositories.py`
- Delete: `backend/app/infra/postgres/prompt_repository.py`
- Modify: 5 callers of `infra.postgres.repositories` (api/*)
- Modify: 5 callers of `infra.postgres.prompt_repository` (application/*, infra/cache, main, api/admin)
- Modify: `backend/tests/unit/test_repositories.py`

- [ ] **Step 1: Inspect current `repositories.py` to identify the split lines**

```bash
cd /home/singer/MuseAI && awk '/^class PostgresExhibitRepository/,/^class PostgresVisitorProfileRepository/' backend/app/infra/postgres/repositories.py | wc -l
```
Also:
```bash
cd /home/singer/MuseAI && grep -n "^class\|^from\|^import" backend/app/infra/postgres/repositories.py | head -20
```
Identify: top-of-file imports, start line of `PostgresExhibitRepository` (line 18), start line of `PostgresVisitorProfileRepository` (line 228).

- [ ] **Step 2: Create `adapters/exhibit_repository.py`**

Open `backend/app/infra/postgres/repositories.py` and copy lines 1 through 227 (top imports through the end of `PostgresExhibitRepository`) into a new file `backend/app/infra/postgres/adapters/exhibit_repository.py`.

Prune imports to just what this adapter uses. Typical contents:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location
from app.infra.postgres.models import Exhibit as ExhibitModel


class PostgresExhibitRepository:
    # ... body unchanged from repositories.py ...
```

Remove unused imports by running ruff after the copy:
```bash
cd /home/singer/MuseAI && uv run ruff check --fix backend/app/infra/postgres/adapters/exhibit_repository.py
```

- [ ] **Step 3: Create `adapters/visitor_profile_repository.py`**

Same procedure for `PostgresVisitorProfileRepository` (line 228 to end of `repositories.py`). Place in `backend/app/infra/postgres/adapters/visitor_profile_repository.py`. Ruff-autofix unused imports.

- [ ] **Step 4: Move `prompt_repository.py` into `adapters/`**

```bash
cd /home/singer/MuseAI && git mv backend/app/infra/postgres/prompt_repository.py backend/app/infra/postgres/adapters/prompt_repository.py
```
(Using `git mv` preserves file history.)

- [ ] **Step 5: Delete the old top-level `repositories.py`**

```bash
cd /home/singer/MuseAI && rm backend/app/infra/postgres/repositories.py
```

- [ ] **Step 6: Update callers**

Five files import `app.infra.postgres.repositories`:

| File | Old import | New import |
|---|---|---|
| `backend/app/api/exhibits.py:11` | `from app.infra.postgres.repositories import PostgresExhibitRepository` | `from app.infra.postgres.adapters.exhibit_repository import PostgresExhibitRepository` |
| `backend/app/api/curator.py:15` | `from app.infra.postgres.repositories import PostgresExhibitRepository, PostgresVisitorProfileRepository` | two imports from `adapters.exhibit_repository` and `adapters.visitor_profile_repository` |
| `backend/app/api/profile.py:10` | `from app.infra.postgres.repositories import PostgresVisitorProfileRepository` | `from app.infra.postgres.adapters.visitor_profile_repository import PostgresVisitorProfileRepository` |
| `backend/app/api/admin/exhibits.py:14` | `from app.infra.postgres.repositories import PostgresExhibitRepository` | `from app.infra.postgres.adapters.exhibit_repository import PostgresExhibitRepository` |
| `backend/tests/unit/test_repositories.py:14` | `from app.infra.postgres.repositories import (...)` | same pattern — split the import across two `adapters.*` lines |

Five files import `app.infra.postgres.prompt_repository`:

| File | Old import | New import |
|---|---|---|
| `backend/app/application/prompt_service.py:7` | `from app.infra.postgres.prompt_repository import PostgresPromptRepository` | `from app.infra.postgres.adapters.prompt_repository import PostgresPromptRepository` |
| `backend/app/application/prompt_service_adapter.py:12` | same | same |
| `backend/app/infra/cache/prompt_cache.py:9` | same | same |
| `backend/app/main.py:34` | same | same |
| `backend/app/api/admin/prompts.py:9` | same | same |

For each of these 10 changes, do the edit and verify no stragglers:
```bash
cd /home/singer/MuseAI && rg -n "from app\.infra\.postgres\.repositories|from app\.infra\.postgres\.prompt_repository" backend/
```
Expected: empty.

- [ ] **Step 7: Verify**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6 && uv run mypy backend/ && uv run ruff check backend/
```
Expected: 756 passed, mypy Success, ruff clean.

If the architecture test `test_infra_has_repository_adapters` (which positively asserts `auth_repository.py` and `document_repository.py` exist under `adapters/`) still passes — good. No changes needed to it; those two files are unaffected.

- [ ] **Step 8: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/infra/postgres/adapters/ backend/app/infra/postgres/repositories.py backend/app/infra/postgres/prompt_repository.py backend/app/api/ backend/app/application/prompt_service.py backend/app/application/prompt_service_adapter.py backend/app/infra/cache/prompt_cache.py backend/app/main.py backend/tests/unit/test_repositories.py && git commit -m "$(cat <<'EOF'
refactor(infra): consolidate Postgres adapters into adapters/ (ARCH-P2-01)

Three placements for the same kind of file collapsed into one:
  adapters/exhibit_repository.py           (from repositories.py)
  adapters/visitor_profile_repository.py   (from repositories.py)
  adapters/prompt_repository.py            (git mv from ../)

The two existing adapters (auth_repository.py, document_repository.py)
were already in the right place. Deletes the old top-level repositories.py
and prompt_repository.py. 10 import-site updates across api/, application/,
infra/cache/, main, tests.

No behavior change. Closes ARCH-P2-01 from 2026-04-17 audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: B2-5 — Remove `document_service.py` bottom-of-file `noqa: E402` import

**Scope:** The `noqa: E402` workaround exists because a top-of-file import from `app.application.ports.repositories` caused a circular. After Task 2 moved PromptGateway out of `application/` root, the circular may have already dissolved. Try the natural fix first; escalate only if a cycle remains.

**Files:**
- Modify: `backend/app/application/document_service.py` (move one import)

- [ ] **Step 1: Try moving the import to the top**

Edit `backend/app/application/document_service.py`. Locate the bottom-of-file block:
```python
# Import the protocol for type hints
from app.application.ports.repositories import DocumentRepositoryPort  # noqa: E402

__all__ = [
    ...
]
```

Move the `from app.application.ports.repositories import DocumentRepositoryPort` line to the top with the other imports (just below `import`/`from` at lines ~1-15). Remove the `# Import the protocol for type hints` comment and the `# noqa: E402` suffix.

- [ ] **Step 2: Run the test suite to confirm no circular**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract --tb=short 2>&1 | tail -6
```

**Branch A — all tests pass**: You're done. Move to Step 3.

**Branch B — `ImportError` or `ImportError: cannot import name 'X' from partially initialized module 'Y'`**: A circular remains. Diagnose:
```bash
cd /home/singer/MuseAI && uv run python -c "import app.application.document_service" 2>&1
```
The stack trace points to the cycle. Common root cause: `app.application.ports.repositories` imports from `app.domain.entities`, which works; but if `document_service` is itself imported during the `ports.repositories` resolution path (via some `__init__.py`), the cycle returns.

If Branch B: choose the narrowest fix:
- Option (i): keep the import at the bottom but wrap in `TYPE_CHECKING` if `DocumentRepositoryPort` is only needed at runtime for `__all__` re-export (it probably is). Replace the bottom import with:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.ports.repositories import DocumentRepositoryPort
```
And drop `"DocumentRepositoryPort"` from `__all__` (since it's no longer importable at runtime from this module). Consumers that imported `DocumentRepositoryPort` from `document_service` should be retargeted to `app.application.ports.repositories` — grep:
```bash
cd /home/singer/MuseAI && rg -n "from app\.application\.document_service import.*DocumentRepositoryPort" backend/
```
Update each caller.

- Option (ii): if Port is genuinely needed at runtime (unlikely for a re-export), then the circular is structural — report it and do NOT fix in this task; add a comment `# TODO(arch): break the cycle by inverting doc_service ↔ ports.repositories dependency` and leave the noqa in place. Escalate to the spec author.

- [ ] **Step 3: Run ruff to confirm no E402 is outstanding**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/application/document_service.py
```
Expected: `All checks passed!`. The `# noqa: E402` is gone so ruff evaluates the import at its new position (top).

- [ ] **Step 4: Verify full suite**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6
```
Expected: 756 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/application/document_service.py && git commit -m "$(cat <<'EOF'
refactor(imports): remove document_service noqa E402 workaround (CQ-P2-01)

The bottom-of-file import with `# noqa: E402` was a circular-import
workaround from an earlier layout. After Task B2-2 moved PromptGateway
out of application/ root, the cycle dissolves. Import moves to the top;
noqa removed.

Closes CQ-P2-01 / ARCH-P2-04 from 2026-04-17 audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: B2-6 — Absorb `workflows/` into `application/workflows/` with explicit DI

**Scope:** Move all files; refactor `reflection_prompts.py` from module-level mutable state (`_prompt_gateway`, `set_prompt_gateway()`) to a class with constructor injection; rewire `main.py`. Change `multi_turn.py` to depend on `LLMProviderPort` instead of concrete `LLMProvider`.

**Files:**
- Move: `backend/app/workflows/` → `backend/app/application/workflows/` (3 files + __init__.py)
- Refactor: `reflection_prompts.py` — class replaces globals
- Refactor: `multi_turn.py` — `LLMProvider` → `LLMProviderPort`
- Modify: `backend/app/main.py` — instantiate `ReflectionPromptsProvider`, remove `set_prompt_gateway` call
- Modify: all callers of `app.workflows.*` (~6 import sites + tests)
- Modify: `backend/tests/architecture/test_layer_import_rules.py` — delete the `test_workflows_does_not_import_api` function (no longer applicable — workflows is now under application/)
- Possibly: delete `backend/app/workflows/__init__.py` and the directory

- [ ] **Step 1: Inventory all callers**

```bash
cd /home/singer/MuseAI && rg -n "from app\.workflows|app\.workflows import" backend/ 2>&1
```
Expected ~9 matches:
- `backend/app/main.py:38` — `from app.workflows.reflection_prompts import set_prompt_gateway` (call-site at :84)
- `backend/app/infra/langchain/agents.py:17` — `from app.workflows.query_transform import ConversationAwareQueryRewriter`
- `backend/app/infra/langchain/__init__.py:25` — same
- `backend/app/infra/langchain/curator_tools.py:21` — `from app.workflows.reflection_prompts import ...`
- `backend/app/workflows/multi_turn.py:5` — internal
- `backend/tests/unit/test_conversation_query_rewrite.py:6`
- `backend/tests/unit/test_state_machine.py:4`
- `backend/tests/unit/test_query_transform.py:5`
- `backend/tests/unit/test_rag_agent.py:208`
- `backend/tests/unit/test_reflection_prompts.py:4`

- [ ] **Step 2: Refactor `reflection_prompts.py` — kill the module-level globals**

Open `backend/app/workflows/reflection_prompts.py`. Current shape (from grep earlier):
```python
_prompt_gateway: PromptGateway | None = None

def set_prompt_gateway(gateway: PromptGateway | None) -> None:
    global _prompt_gateway
    _prompt_gateway = gateway

# ... get_reflection_prompt() reads from _prompt_gateway
```

Refactor to:
```python
class ReflectionPromptsProvider:
    """Provides reflection prompts. Fetches from PromptGateway with fallback to hardcoded defaults."""

    def __init__(self, prompt_gateway: PromptGateway | None = None) -> None:
        self._prompt_gateway = prompt_gateway

    async def get_reflection_prompt(self, ...) -> str:
        # body from existing get_reflection_prompt, with `self._prompt_gateway` replacing `_prompt_gateway`
        ...
```

Keep all the existing `KnowledgeLevel`/`NarrativeStyle` enums, hardcoded fallbacks, and other helpers — only the state-holding mechanism changes.

Delete the module-level `_prompt_gateway`, `set_prompt_gateway()`, and any direct global-reading functions (fold them into the class as methods).

- [ ] **Step 3: Move files to `application/workflows/`**

```bash
cd /home/singer/MuseAI && \
  mkdir -p backend/app/application/workflows && \
  git mv backend/app/workflows/__init__.py backend/app/application/workflows/__init__.py && \
  git mv backend/app/workflows/reflection_prompts.py backend/app/application/workflows/reflection_prompts.py && \
  git mv backend/app/workflows/query_transform.py backend/app/application/workflows/query_transform.py && \
  git mv backend/app/workflows/multi_turn.py backend/app/application/workflows/multi_turn.py && \
  rmdir backend/app/workflows
```

- [ ] **Step 4: Refactor `multi_turn.py` to use `LLMProviderPort`**

Edit `backend/app/application/workflows/multi_turn.py`. Replace:
```python
from app.infra.providers.llm import LLMProvider
```
with:
```python
from app.application.ports.repositories import LLMProviderPort
```

Update every in-file type reference `LLMProvider` → `LLMProviderPort`.

Update the internal import:
```python
# old
from app.workflows.query_transform import (
# new (relative or absolute — use relative for sibling module)
from .query_transform import (
```

- [ ] **Step 5: Update `reflection_prompts.py` and `query_transform.py` imports**

In `backend/app/application/workflows/reflection_prompts.py`:
```python
# old
from app.application.prompt_gateway import PromptGateway
# new (after Task 2 this was already `from app.application.ports.prompt_gateway`; now update further to sibling relative)
from app.application.ports.prompt_gateway import PromptGateway
```

Same for `query_transform.py`. (If Task 2 already updated these, this step is a no-op.)

- [ ] **Step 6: Update `main.py` — instantiate provider, remove set_prompt_gateway**

Edit `backend/app/main.py`:

Replace line 38:
```python
# old
from app.workflows.reflection_prompts import set_prompt_gateway
# new
from app.application.workflows.reflection_prompts import ReflectionPromptsProvider
```

Replace the call near line 84:
```python
# old
set_prompt_gateway(prompt_gateway)
# new
reflection_prompts_provider = ReflectionPromptsProvider(prompt_gateway)
app.state.reflection_prompts = reflection_prompts_provider
```

- [ ] **Step 7: Update all other callers**

For each file listed in Step 1 (except `main.py`, which is done), change:
```python
from app.workflows.<module> import <name>
```
to:
```python
from app.application.workflows.<module> import <name>
```

Verify:
```bash
cd /home/singer/MuseAI && rg -n "from app\.workflows|app\.workflows import" backend/
```
Expected: empty.

- [ ] **Step 8: Update callers of the old `get_reflection_prompt()` function (if any)**

If `infra/langchain/curator_tools.py` was calling `get_reflection_prompt(...)` directly at the module level (relying on the global gateway), it now needs a `ReflectionPromptsProvider` instance. Grep:
```bash
cd /home/singer/MuseAI && rg -n "get_reflection_prompt\|from .* import get_reflection_prompt" backend/
```
For each call site: pass a `ReflectionPromptsProvider` (or accept one in the enclosing class's constructor). If `curator_tools.py`'s tool classes already receive a `prompt_gateway`, they can construct `ReflectionPromptsProvider(prompt_gateway)` locally.

- [ ] **Step 9: Clean up layer-rules test**

Edit `backend/tests/architecture/test_layer_import_rules.py`. Delete the `test_workflows_does_not_import_api` function (the `workflows/` directory no longer exists at `backend/app/workflows/` — the `if not (APP_ROOT / "workflows").exists(): return` guard would silently pass anyway, but the rule is obsolete).

Also update the module docstring to drop the `workflows` rule.

- [ ] **Step 10: Full verification**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -6 && uv run mypy backend/ && uv run ruff check backend/
```
Expected: 756 passed (or minimally-higher if any new tests were added for `ReflectionPromptsProvider`), mypy Success, ruff clean.

If tests fail with `AttributeError: module 'app.workflows' has no attribute 'reflection_prompts'` or similar, the grep in Step 7 missed a caller — find and update it.

- [ ] **Step 11: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/application/workflows/ backend/app/workflows backend/app/main.py backend/app/infra/langchain/ backend/tests/ && git commit -m "$(cat <<'EOF'
refactor(arch): absorb workflows/ into application/workflows/ (ARCH-P1-03, ARCH-P2-03)

The workflows/ directory was a layer without a defined position. Its three
files are orchestration logic that naturally belongs in the application
layer. Moves them; drops the separate test_workflows_does_not_import_api
architecture test as obsolete.

reflection_prompts.py dropped its module-level mutable _prompt_gateway +
set_prompt_gateway() setter. New class ReflectionPromptsProvider takes the
gateway via constructor injection. main.py instantiates the provider and
stores it on app.state instead of calling a module-level setter.

multi_turn.py migrates its LLMProvider dependency to LLMProviderPort
(defined in application/ports/repositories.py), matching the port-based
discipline of the rest of the application.

Closes ARCH-P1-03 (B2-6) and ARCH-P2-03 from 2026-04-17 audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: B2 Final Verification

**Scope:** No code changes. Confirms the batch's acceptance criteria and surfaces any drift.

- [ ] **Step 1: The six KNOWN_VIOLATIONS are all closed**

```bash
cd /home/singer/MuseAI && grep -A20 "^KNOWN_VIOLATIONS" backend/tests/architecture/test_layer_import_rules.py | head -5
```
Expected: `KNOWN_VIOLATIONS: set[tuple[str, str]] = set()` (literal empty set).

- [ ] **Step 2: Zero infra→application reverse-deps**

```bash
cd /home/singer/MuseAI && rg -n "^from app\.application" backend/app/infra/
```
Expected: empty.

- [ ] **Step 3: `domain/repositories.py` is gone; `application/ports/` is the single surface**

```bash
cd /home/singer/MuseAI && [ ! -f backend/app/domain/repositories.py ] && echo "domain/repositories.py DELETED ✓" || echo "FAIL: still exists"
cd /home/singer/MuseAI && ls backend/app/application/ports/
```
Expected: `domain/repositories.py DELETED ✓`; `application/ports/` contains `repositories.py`, `prompt_gateway.py`, `context_manager.py` (+ `__init__.py`).

- [ ] **Step 4: `workflows/` fully absorbed**

```bash
cd /home/singer/MuseAI && [ ! -d backend/app/workflows ] && echo "workflows/ DELETED ✓" || echo "FAIL: still exists"
cd /home/singer/MuseAI && ls backend/app/application/workflows/
```
Expected: `workflows/ DELETED ✓`; `application/workflows/` contains 4 files (including `__init__.py`).

- [ ] **Step 5: `rrf_fusion` lives in `domain/services/`**

```bash
cd /home/singer/MuseAI && grep -l "def rrf_fusion" backend/app/domain/services/retrieval.py && [ ! -f backend/app/application/retrieval.py ] && echo "rrf_fusion relocated ✓"
```
Expected: the grep prints the path; the `[ ! -f ... ]` test succeeds; `✓` printed.

- [ ] **Step 6: No more `noqa: E402` in application**

```bash
cd /home/singer/MuseAI && rg "# noqa: E402" backend/app/application/
```
Expected: empty.

- [ ] **Step 7: Adapter layout is canonical**

```bash
cd /home/singer/MuseAI && ls backend/app/infra/postgres/adapters/
```
Expected: `__init__.py auth_repository.py document_repository.py exhibit_repository.py prompt_repository.py visitor_profile_repository.py`.

```bash
cd /home/singer/MuseAI && [ ! -f backend/app/infra/postgres/repositories.py ] && [ ! -f backend/app/infra/postgres/prompt_repository.py ] && echo "old adapter files deleted ✓"
```

- [ ] **Step 8: All tests green, mypy clean, ruff clean**

```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -5 && \
  uv run mypy backend/ && \
  uv run ruff check backend/
```

Expected: ≥ 756 passed; mypy Success; ruff clean.

- [ ] **Step 9: Confirm architecture-debt audit items closed**

- ARCH-P1-01 ✅ Tasks 2, 3, 4
- ARCH-P1-02 ✅ Task 1
- ARCH-P1-03 ✅ Task 7
- ARCH-P2-01 ✅ Task 5
- ARCH-P2-02 (anemic entities) — explicitly deferred (not in B2 scope per spec §2)
- ARCH-P2-03 ✅ Task 7 (module-level mutable state removed)
- ARCH-P2-04 ✅ Task 6 (circular-import noqa removed)
- CQ-P2-01 ✅ Task 6
- CQ-P2-02 ✅ Task 1
- SYS-1 (infra reverse-deps) ✅ Tasks 2, 3, 4
- SYS-2 (dual Ports) ✅ Task 1

No additional commit — this is verification only. Report the eight green checks to the reviewer.

---

## Rollback Notes

All seven feature tasks are independent commits on `feature/tour-visitor-flow`. Safe rollback order (reverse-dependency):
- Task 7 (workflows absorb) — revert resurrects `backend/app/workflows/` and its globals
- Task 6 (noqa removal) — self-contained
- Task 5 (adapters) — import churn; revert restores the old top-level files
- Task 4 (rrf_fusion) — restores `application/retrieval.py`, adds back KNOWN_VIOLATIONS entry
- Task 3 (context manager) — restores KNOWN_VIOLATIONS entry
- Task 2 (prompt gateway) — restores `application/prompt_gateway.py` and 4 KNOWN_VIOLATIONS entries
- Task 1 (port unification) — restores `domain/repositories.py`

Each revert requires restoring the corresponding KNOWN_VIOLATIONS entries via the same commit revert; the hygiene test guards against mismatch.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: B2 spec has 6 work packages (B2-1 through B2-6). Task map: T1=B2-1, T2=B2-2a, T3=B2-2b, T4=B2-3, T5=B2-4, T6=B2-5, T7=B2-6, T8=final verification. ✓
- **Placeholder scan**: no "TBD" / "add appropriate" / "similar to". One explicit decision branch in Task 6 (Branch A vs B) is guidance, not a placeholder — both branches have concrete instructions. ✓
- **Type / name consistency**:
  - `PromptGateway` kept as the class name throughout (not renamed to `PromptGatewayPort`) per the existing convention in `application/prompt_gateway.py`. ✓
  - `ConversationContextManagerPort` chosen for the new Protocol — keeps the `*Port` suffix for new introductions.
  - `ExhibitRepositoryPort` / `VisitorProfileRepositoryPort` already have `*Port` suffix in `application/ports/repositories.py`.
- **Dependency ordering**: Tasks 2→3→4 each remove specific KNOWN_VIOLATIONS entries in the order listed in the allowlist. Task 5 (adapters) is independent. Task 6 depends on Task 2 for the cycle to dissolve. Task 7 depends on Task 2 for the sibling-relative import to work.
- **Known gotchas captured**: circular-import branch in Task 6; module-level mutable in Task 7; the `TourPathRepository` YAGNI drop in Task 1.
