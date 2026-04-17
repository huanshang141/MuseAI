# B1 CI Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `mypy`, `ruff`, `pytest`, and the architectural layer-rules test from decorative CI jobs into actual defenses. After this batch, any future regression (type error, lint error, layer violation, unregistered forbidden import) fails CI — which is the precondition for every subsequent batch (B2-B8).

**Architecture:** Four independent work packages. Each fixes one part of CI: mypy (unblock and set real baseline), ruff (drive the 36-error backlog to zero), layer-rules test (swap narrow whitelist for generic 4-rule enforcement with a temporary allowlist of the 6 known B2 violations), pytest (kill two known warnings). All tasks are pure config / tests / targeted cleanup — no product-code changes beyond what ruff flags and the TestConfig rename.

**Tech Stack:** Python 3.13, FastAPI, uv, pytest 9, mypy 1.20, ruff 0.15, Alembic.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B1.

**Related audit findings:** TEST-P1-03 (layer rules too narrow), TEST-P2-03 (pytest config warning), TEST-P2-04 (TestConfig collection warning), cross-cutting "mypy completely unchecked" (appendix A of audit).

**Execution note — ordering:**
Tasks are listed in spec order (B1-1 → B1-4). The mypy task (Task 1) carries the most open-ended risk (latent type errors surfacing). If schedule pressure arises, tackle Tasks 2/3/4 first and leave Task 1 for a second day.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify `[tool.mypy]` | Eliminate duplicate-module path; possibly narrow `strict` to specific packages |
| `pyproject.toml` | Modify `[tool.pytest.ini_options]` | Remove invalid `collect_ignore_glob` key; move to conftest |
| `pyproject.toml` | Add `[tool.ruff.lint.per-file-ignores]` | Tolerate E402 for performance scripts that must manipulate sys.path |
| `backend/conftest.py` | Create | House `collect_ignore_glob` for pytest 9; exclude performance dir from default runs |
| `backend/tests/architecture/test_layer_import_rules.py` | Rewrite | Four generic layer rules + known-violation allowlist |
| `backend/alembic/versions/002_add_created_at_indexes.py` | Modify L10 | Delete unused sqlalchemy import |
| `backend/alembic/versions/20260415_add_tour_tables.py` | Modify L162 | Break long loop line |
| `backend/scripts/migrate_prompts.py` | Modify lines 69, 79, 84, 345, 361 | Break overlong lines |
| `backend/tests/architecture/test_no_main_runtime_imports.py` | Modify L58 + L102 | Fix B023 loop binding + break long line |
| `backend/tests/e2e/conftest.py` | Modify L44 | Break long SQL string |
| `backend/tests/integration/test_rate_limit_integration.py` | Modify L254 | Break long assertion message |
| `backend/tests/performance/start_mock_services.py` | Modify L104 | Rename `proc` → `_` for unused loop var |
| `backend/tests/unit/test_parallel_indexing.py` | Modify L322-331 | Bind `lock` via default arg in nested functions |
| `backend/tests/performance/config.py` | Modify L9 | Rename `TestConfig` → `PerfTestConfig`; update call sites |

All product code in `backend/app/**` is untouched in this batch (exception: if mypy Task 1 surfaces fewer than ~20 real type errors, those are fixed inline; otherwise config-level scoping absorbs them).

---

## Task 1: B1-1 — Unblock mypy (fix duplicate-module error and establish working baseline)

**Scope:** `mypy backend/` currently exits after one error: `Source file found twice under different module names: "app.infra.postgres.models" and "backend.app.infra.postgres.models"`. Fix the config so mypy actually traverses the tree. Then decide how to handle the real type errors that surface (there may be zero, or many).

**Files:**
- Modify: `pyproject.toml` `[tool.mypy]` section
- Possibly modify: individual `.py` files if few real errors surface
- Possibly add: `[[tool.mypy.overrides]]` subsections if many

- [ ] **Step 1: Capture the "before" state**

Run:
```bash
cd /home/singer/MuseAI && uv run mypy backend/ 2>&1 | tee /tmp/mypy-before.txt ; echo "---exit=$?"
```
Expected: last lines contain `Source file found twice under different module names: "app.infra.postgres.models" and "backend.app.infra.postgres.models"` followed by `Found 1 error in 1 file (errors prevented further checking)`; exit code non-zero.

- [ ] **Step 2: Update pyproject mypy config**

Edit `pyproject.toml`. Find:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

Replace with:
```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
explicit_package_bases = true
mypy_path = "backend"
namespace_packages = true
exclude = [
    "^backend/tests/performance/",
    "^backend/alembic/versions/",
]
```

Explanation (for the executor):
- `explicit_package_bases = true` tells mypy to use the configured `mypy_path` instead of auto-inferring package roots from every directory.
- `mypy_path = "backend"` makes `backend/` the only source root, so `backend/app/infra/postgres/models.py` resolves uniquely to `app.infra.postgres.models` (not also to `backend.app.infra.postgres.models`).
- `namespace_packages = true` allows the `backend` directory (no `__init__.py`) to still be a valid source root.
- `exclude` skips two noisy areas that are not part of the production surface: performance scripts (sys.path manipulation) and Alembic auto-generated migrations.

- [ ] **Step 3: Run mypy with the new config and triage**

Run:
```bash
cd /home/singer/MuseAI && uv run mypy backend/ 2>&1 | tee /tmp/mypy-after.txt ; echo "---exit=$?"
```

Now interpret the output. Possible branches:

**Branch A — zero real errors** (exit 0, output like `Success: no issues found in N source files`). Proceed to Step 4.

**Branch B — fewer than 20 real errors**. Fix them inline. For each reported error, open the file, read the surrounding context, and apply the narrowest correct fix (type hint, `# type: ignore[<code>]` with a short rationale comment if the library itself has bad stubs, or a small refactor). Re-run `uv run mypy backend/` after each fix and confirm the count strictly decreases. Do NOT mass-add `# type: ignore` without a code and rationale.

**Branch C — 20 or more real errors**. Do not try to fix all of them in B1. Instead scope `strict` narrowly. Modify `pyproject.toml` further:
```toml
[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
explicit_package_bases = true
mypy_path = "backend"
namespace_packages = true
exclude = [
    "^backend/tests/performance/",
    "^backend/alembic/versions/",
]

# Strict only for well-structured layers; the rest is tech debt for later batches.
[[tool.mypy.overrides]]
module = ["app.domain.*", "app.application.ports.*"]
strict = true
```
Then re-run `uv run mypy backend/` and iterate: your goal is exit code 0. Any remaining errors outside `domain/` and `application/ports/` are acknowledged tech debt; leave a one-line comment in `pyproject.toml` above the overrides section: `# TODO(B8): re-enable strict once tech debt from 2026-04-17 audit is repaid`.

- [ ] **Step 4: Verify mypy passes**

Run:
```bash
cd /home/singer/MuseAI && uv run mypy backend/ ; echo "---exit=$?"
```
Expected: exit code `0`; output ends with `Success: no issues found in N source files` (where N > 60 — confirms mypy actually traversed the tree, not just one file).

- [ ] **Step 5: Verify no test regression**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -5
```
Expected: all tests pass (the same count as before B1 started, modulo unrelated flakes).

- [ ] **Step 6: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add pyproject.toml $(git diff --name-only | tr '\n' ' ') && git status && git commit -m "$(cat <<'EOF'
build(mypy): fix duplicate-module-path blocker and set working baseline

mypy was exiting at the first file with "Source file found twice under
different module names: app.infra.postgres.models vs
backend.app.infra.postgres.models", so no type-checking actually ran.

Sets explicit_package_bases + mypy_path="backend" + namespace_packages
so there is a single canonical package root (`app.*`). Excludes
performance scripts and Alembic versions from the mypy sweep.

Closes the "mypy unchecked" finding from the 2026-04-17 midterm audit
(appendix A). CI type-checking now actually runs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: commit contains `pyproject.toml` and any files fixed in Step 3 Branch B. If Branch C was taken, the commit message should include an extra sentence: "Global strict is temporarily disabled; strict is retained only for app.domain.* and app.application.ports.*. Full strict will be restored in B8 after the intervening batches repay type debt."

---

## Task 2: B1-2 — Strict, generic layer-import rules

**Scope:** Replace the current `test_layer_import_rules.py` — which forbids only two specific submodules — with four general rules: `domain/` cannot import from `application/`/`infra/`/`api/`/`workflows/`; `application/` cannot import from `api/`; `infra/` cannot import from `application/` or `api/` (except TYPE_CHECKING); `workflows/` will be relocated in B2 (for now, allow but log). The six known `infra/langchain → app.application.*` violations must be listed in an explicit allowlist with pointers to B2-1/B2-2.

**Files:**
- Rewrite: `backend/tests/architecture/test_layer_import_rules.py`

- [ ] **Step 1: Write the rewritten test (red for one new rule by design)**

Replace the full contents of `backend/tests/architecture/test_layer_import_rules.py` with:

```python
"""Architecture tests enforcing layer dependency direction.

Rules (from CLAUDE.md):
    domain     ← no imports of application/infra/api/workflows
    application ← no imports of api
    infra       ← no imports of application/api (except TYPE_CHECKING)
    workflows   ← currently undefined; will be absorbed into application/workflows/ by B2-6

Any violation MUST either be fixed OR added to KNOWN_VIOLATIONS with a
pointer to the batch that will resolve it.
"""
import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"

# Known violations pending remediation. Each entry is (source_file_relative_to_app, imported_module, resolving_batch).
# When the batch lands and removes the violation, delete the entry.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # B2-2: move PromptGateway/ConversationContextManager into application/ports/
    ("infra/langchain/agents.py", "app.application.prompt_gateway"),
    ("infra/langchain/__init__.py", "app.application.prompt_gateway"),
    ("infra/langchain/curator_agent.py", "app.application.prompt_gateway"),
    ("infra/langchain/curator_tools.py", "app.application.prompt_gateway"),
    ("infra/langchain/tools.py", "app.application.context_manager"),
    # B2-3: move rrf_fusion to domain/services/retrieval.py
    ("infra/langchain/retrievers.py", "app.application.retrieval"),
}


def _get_module_imports(file_path: Path) -> list[str]:
    """Return module-level import targets, skipping TYPE_CHECKING guarded blocks."""
    try:
        tree = ast.parse(file_path.read_text())
    except SyntaxError:
        return []

    type_checking_lines: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for child in ast.walk(node):
                if isinstance(child, (ast.ImportFrom, ast.Import)) and getattr(child, "end_lineno", None):
                    for ln in range(child.lineno, child.end_lineno + 1):
                        type_checking_lines.add(ln)

    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.lineno not in type_checking_lines:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


def _files_in(layer: str) -> list[Path]:
    return sorted(p for p in (APP_ROOT / layer).rglob("*.py") if "__pycache__" not in p.parts)


def _violations(layer: str, forbidden_prefixes: tuple[str, ...]) -> list[tuple[str, str]]:
    """Return a list of (relative_path_from_app, offending_import) tuples."""
    out: list[tuple[str, str]] = []
    for path in _files_in(layer):
        rel = str(path.relative_to(APP_ROOT))
        for imp in _get_module_imports(path):
            for prefix in forbidden_prefixes:
                if imp == prefix or imp.startswith(prefix + "."):
                    out.append((rel, imp))
    return out


def _assert_no_new_violations(layer: str, forbidden_prefixes: tuple[str, ...]) -> None:
    """Fail if the layer contains violations NOT in KNOWN_VIOLATIONS."""
    violations = _violations(layer, forbidden_prefixes)
    unexpected = [v for v in violations if v not in KNOWN_VIOLATIONS]

    if unexpected:
        formatted = "\n".join(f"  - {src} imports {imp}" for src, imp in unexpected)
        raise AssertionError(
            f"Layer '{layer}' has {len(unexpected)} unexpected import(s) of "
            f"forbidden prefixes {forbidden_prefixes}:\n{formatted}\n"
            f"Either remove the import (preferred) or, if tracked by an upcoming "
            f"batch, add the (source, import) tuple to KNOWN_VIOLATIONS in this file."
        )


# ---------- Rules ----------


def test_domain_imports_nothing_forbidden():
    """domain/ must be a pure layer — no imports from any higher layer."""
    _assert_no_new_violations(
        "domain",
        ("app.application", "app.infra", "app.api", "app.workflows"),
    )


def test_application_does_not_import_api():
    """application/ may use domain/infra ports but never calls routers."""
    _assert_no_new_violations("application", ("app.api",))


def test_infra_does_not_import_application_or_api():
    """infra/ implements ports defined in domain/application; never calls them at module load."""
    _assert_no_new_violations("infra", ("app.application", "app.api"))


def test_workflows_does_not_import_api():
    """workflows/ is a floating layer pending B2-6 absorption; for now forbid only api imports."""
    # After B2-6 moves everything into application/workflows/, this test will be deleted.
    if not (APP_ROOT / "workflows").exists():
        return  # Already absorbed.
    _assert_no_new_violations("workflows", ("app.api",))


# ---------- Allowlist hygiene ----------


def test_known_violations_still_exist():
    """Every entry in KNOWN_VIOLATIONS must actually exist. Stale entries mean a
    violation was fixed without removing the allowlist row — clean it up."""
    for src, imp in KNOWN_VIOLATIONS:
        path = APP_ROOT / src
        assert path.exists(), (
            f"KNOWN_VIOLATIONS references nonexistent file {src}. Remove the stale entry."
        )
        actual_imports = _get_module_imports(path)
        assert imp in actual_imports, (
            f"KNOWN_VIOLATIONS expects {src} to import {imp}, but it does not. "
            f"Remove the stale entry (violation was likely fixed by a batch)."
        )


# ---------- Positive assertions kept from the prior version ----------


def test_application_layer_has_repository_ports():
    ports_file = APP_ROOT / "application" / "ports" / "repositories.py"
    assert ports_file.exists(), "Repository ports file should exist"

    content = ports_file.read_text()
    required_ports = [
        "UserRepositoryPort",
        "DocumentRepositoryPort",
        "ExhibitRepositoryPort",
        "VisitorProfileRepositoryPort",
        "ChatSessionRepositoryPort",
        "ChatMessageRepositoryPort",
        "LLMProviderPort",
        "CachePort",
        "CuratorAgentPort",
    ]
    for port in required_ports:
        assert port in content, f"Repository port {port} should be defined in ports/repositories.py"


def test_infra_has_repository_adapters():
    adapters_dir = APP_ROOT / "infra" / "postgres" / "adapters"
    assert adapters_dir.exists(), "Adapters directory should exist"

    required_adapters = [
        "auth_repository.py",
        "document_repository.py",
    ]
    for adapter in required_adapters:
        assert (adapters_dir / adapter).exists(), f"Adapter {adapter} should exist"


def test_domain_layer_does_not_import_sqlalchemy():
    for path in _files_in("domain"):
        for imp in _get_module_imports(path):
            assert "sqlalchemy" not in imp, (
                f"Domain layer should not use SQLAlchemy directly. "
                f"{path.relative_to(BACKEND_ROOT)} imports {imp}"
            )
```

- [ ] **Step 2: Run the architecture tests**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/architecture/test_layer_import_rules.py -v
```
Expected: all 8 tests PASS. `test_infra_does_not_import_application_or_api` passes because the 6 real violations are in `KNOWN_VIOLATIONS`; `test_known_violations_still_exist` passes because each entry resolves to a real file with the listed import.

If `test_known_violations_still_exist` fails saying an entry doesn't exist, re-verify with: `rg "^from app\.application" /home/singer/MuseAI/backend/app/infra/ 2>&1` and correct the allowlist. If `test_infra_does_not_import_application_or_api` fails with *unexpected* violations, investigate — someone added a new reverse dep between the audit and now.

- [ ] **Step 3: Simulate a future violation, confirm test fails, then revert**

This proves the rule is active (not just accepting the current state as baseline). Append a dummy violation:
```bash
cd /home/singer/MuseAI && python -c "
p = 'backend/app/domain/entities.py'
with open(p) as f: original = f.read()
with open(p, 'w') as f: f.write('from app.infra.postgres import models  # TEMPORARY CHECK\n' + original)
"
```

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/architecture/test_layer_import_rules.py::test_domain_imports_nothing_forbidden -v
```
Expected: FAIL with `AssertionError: Layer 'domain' has 1 unexpected import(s) ... domain/entities.py imports app.infra.postgres`.

Revert immediately:
```bash
cd /home/singer/MuseAI && git checkout -- backend/app/domain/entities.py
```

Re-run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/architecture/test_layer_import_rules.py -v
```
Expected: all 8 tests PASS again.

- [ ] **Step 4: Run the full architecture dir**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/architecture/ -v --tb=short
```
Expected: both `test_layer_import_rules.py` and `test_no_main_runtime_imports.py` pass.

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/tests/architecture/test_layer_import_rules.py && git commit -m "$(cat <<'EOF'
test(architecture): replace narrow whitelist with four generic layer rules

Previously test_layer_import_rules.py only forbade two specific submodules.
The 2026-04-17 audit found 6 genuine infra→application reverse-imports
that the test did not catch. This rewrite enforces the dependency direction
for every layer:

  domain ← no imports of application/infra/api/workflows
  application ← no imports of api
  infra ← no imports of application/api (except TYPE_CHECKING)
  workflows ← no imports of api (layer pending B2-6 absorption)

The 6 known violations (all in infra/langchain/) are explicitly listed in
KNOWN_VIOLATIONS with their resolving batch. A hygiene test prevents stale
entries: once B2 removes a reverse import, its allowlist row must be deleted
or the test fails.

Closes TEST-P1-03 from midterm debt audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: B1-3 — Drive ruff errors from 36 to 0

**Scope:** Each of the 36 errors is mechanically fixable. Scope the fixes narrowly: for tests/performance/* which are standalone scripts that must manipulate `sys.path` before importing, add a `per-file-ignores` rule instead of churning the files. Everything else is direct source edits.

**Files:**
- 9 source files (per the table in File Structure above)
- `pyproject.toml` — add `[tool.ruff.lint.per-file-ignores]`

- [ ] **Step 1: Baseline**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/ --statistics 2>&1 | tail -20
```
Expected: 36 errors total, split into: 1× F401, 11× E501, 2× B023 (tests/architecture + tests/unit), 1× B007, ~21× E402 (all under `tests/performance/`).

- [ ] **Step 2: Delete unused import (F401)**

Edit `backend/alembic/versions/002_add_created_at_indexes.py` — remove line 10 entirely:
```diff
-import sqlalchemy as sa
```
The migration uses only `op.*` from alembic (confirmed by reading the file). No other changes.

- [ ] **Step 3: Fix B023 in test_no_main_runtime_imports.py**

Edit `backend/tests/architecture/test_no_main_runtime_imports.py`. Find the loop around line 58 where `type_checking_nodes` is captured in a function defined inside the loop. Replace:

Old (approximately):
```python
            if is_type_checking:
                type_checking_nodes.add(id(node))

            for child in ast.iter_child_nodes(node):
```

The B023 complaint is about a nested function or comprehension later that closes over `type_checking_nodes` without binding it. Locate the offending function (usually a `def` inside a `for`-loop that uses `type_checking_nodes`) and fix by binding the variable as a default parameter:

```python
            def _is_inside_type_checking(n: ast.AST, _tc_nodes: set = type_checking_nodes) -> bool:
                # body uses _tc_nodes instead of the enclosing type_checking_nodes
                ...
```

Then run: `cd /home/singer/MuseAI && uv run ruff check backend/tests/architecture/test_no_main_runtime_imports.py`. Confirm B023 is gone.

- [ ] **Step 4: Fix E501 in test_no_main_runtime_imports.py:102**

Edit `backend/tests/architecture/test_no_main_runtime_imports.py:100-105`. Current:
```python
        raise AssertionError(f"Deep modules should not import from app.main at runtime.\n" f"Use dependency injection through constructors instead.\n" f"Found {len(violations)} violations:\n{violation_details}")
```
Replace with:
```python
        raise AssertionError(
            "Deep modules should not import from app.main at runtime.\n"
            "Use dependency injection through constructors instead.\n"
            f"Found {len(violations)} violations:\n{violation_details}"
        )
```

- [ ] **Step 5: Fix E501 in migration 20260415_add_tour_tables.py:162**

Edit `backend/alembic/versions/20260415_add_tour_tables.py:160-163`. Current:
```python
        for idx_name in ['ix_tour_sessions_status', 'ix_tour_sessions_session_token', 'ix_tour_sessions_guest_id', 'ix_tour_sessions_user_id']:
```
Replace with:
```python
        for idx_name in [
            'ix_tour_sessions_status',
            'ix_tour_sessions_session_token',
            'ix_tour_sessions_guest_id',
            'ix_tour_sessions_user_id',
        ]:
```

- [ ] **Step 6: Fix E501s in scripts/migrate_prompts.py (5 lines)**

Edit `backend/scripts/migrate_prompts.py` at lines 69, 79, 84, 345, 361.

For lines 69, 79, 84 (inside long Chinese docstring content in a `content` dict value), wrap to fit 120 columns. Example transformation for line 69:

Old:
```python
        "content": "你可以使用以下工具来帮助参观者：\n\n1. **path_planning** - 路线规划工具\n   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线\n   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）\n   - 何时使用：当参观者需要路线建议或想要开始参观时\n\n...",
```
Replace with multi-line `(...)` concatenation or explicit `"\n".join([...])`. The content *must* stay byte-identical (these go into the DB). Confirm with `python -c "from backend.scripts.migrate_prompts import PROMPTS; print(hash(str(PROMPTS)))"` before and after edits — hash must not change. If preserving identity is tricky, prefer moving each overlong `"..."` onto a variable:

```python
_PATH_PLANNING_DESC = (
    "你可以使用以下工具来帮助参观者：\n\n"
    "1. **path_planning** - 路线规划工具\n"
    "   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线\n"
    "   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、"
    "current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）\n"
    "   - 何时使用：当参观者需要路线建议或想要开始参观时\n\n"
    ...
)
```
Apply similarly to lines 79, 84, 345, 361.

After each file edit: `cd /home/singer/MuseAI && uv run ruff check backend/scripts/migrate_prompts.py` — confirm errors decrease.

- [ ] **Step 7: Fix E501 in tests/e2e/conftest.py:44**

Edit `backend/tests/e2e/conftest.py:42-46`. Current:
```python
        await session.execute(
            text(
                "INSERT INTO users (id, email, password_hash) VALUES ('test-user-e2e', 'e2e@test.com', 'test_hash') ON CONFLICT (id) DO NOTHING"
            )
        )
```
Replace with:
```python
        await session.execute(
            text(
                "INSERT INTO users (id, email, password_hash) "
                "VALUES ('test-user-e2e', 'e2e@test.com', 'test_hash') "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
```

- [ ] **Step 8: Fix E501 in tests/integration/test_rate_limit_integration.py:254**

Edit `backend/tests/integration/test_rate_limit_integration.py:250-256`. Current:
```python
        assert blocked == num_concurrent - max_requests, f"Expected {num_concurrent - max_requests} blocked, got {blocked}"
```
Replace with:
```python
        assert blocked == num_concurrent - max_requests, (
            f"Expected {num_concurrent - max_requests} blocked, got {blocked}"
        )
```

- [ ] **Step 9: Fix B023 in tests/unit/test_parallel_indexing.py (2 occurrences)**

Edit `backend/tests/unit/test_parallel_indexing.py:320-335`. The problem: an inner async function `mock_index_chunk` closes over `lock` defined in the enclosing scope, but ruff's late-binding check flags this.

Current:
```python
            async def mock_index_chunk(doc):
                nonlocal concurrent_count, max_observed
                async with lock:
                    concurrent_count += 1
                    max_observed = max(max_observed, concurrent_count)

                await asyncio.sleep(0.01)

                async with lock:
                    concurrent_count -= 1
```

Replace the signature line and internal `lock` references with a default-bound parameter:
```python
            async def mock_index_chunk(doc, _lock: asyncio.Lock = lock):
                nonlocal concurrent_count, max_observed
                async with _lock:
                    concurrent_count += 1
                    max_observed = max(max_observed, concurrent_count)

                await asyncio.sleep(0.01)

                async with _lock:
                    concurrent_count -= 1
```

- [ ] **Step 10: Fix B007 in tests/performance/start_mock_services.py:104**

Edit `backend/tests/performance/start_mock_services.py:100-110`. Current:
```python
        for name, proc, url in processes:
            if wait_for_server(url):
                print(f"  ✓ {name} server ready at {url}")
            else:
                print(f"  ✗ {name} server failed to start")
                all_ready = False
```
Replace the loop line with:
```python
        for name, _proc, url in processes:
```
(The unused binding is renamed `_proc` to signal intent. Ruff B007 is about "loop control variable not used in the body" — the `_` prefix suppresses it.)

- [ ] **Step 11: Add per-file ignore for tests/performance/* E402**

Edit `pyproject.toml`. Find the `[tool.ruff.lint]` section (currently small). After it (or at the end of the file), add:
```toml
[tool.ruff.lint.per-file-ignores]
# Performance test scripts manipulate sys.path before importing project code.
# E402 "module level import not at top" is intentional for these files.
"backend/tests/performance/*.py" = ["E402"]
# Alembic migrations are auto-generated and sometimes have stylistic
# patterns that aren't worth churning (unused F401 on sa-aliased imports, etc.).
# B1 left only one such issue; keeping this narrow to just migration files.
"backend/alembic/versions/*.py" = []  # placeholder in case future migrations need a carve-out
```
(If the rule format differs in the project's current pyproject, confirm the correct TOML key by consulting `uv run ruff check --help | head` and project documentation.)

- [ ] **Step 12: Verify ruff is clean**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/ 2>&1 | tail -5
```
Expected: `All checks passed!` (or if `--fix` is applicable, `Found 0 errors`).

- [ ] **Step 13: Run the full test suites to catch any accidental behavior change**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -5
```
Expected: all tests pass.

If migrate_prompts.py was edited in Step 6: also run a smoke test to ensure string concatenation preserved byte-identity of prompt content. If the project has an invocation script, run it in dry-run mode. Otherwise inspect a sample `PROMPTS` entry before/after.

- [ ] **Step 14: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add pyproject.toml backend/alembic backend/scripts backend/tests && git commit -m "$(cat <<'EOF'
chore(lint): drive ruff from 36 errors to 0

Multi-file mechanical cleanup of the existing backlog:
  - F401  backend/alembic/versions/002_add_created_at_indexes.py (delete unused sa import)
  - E501  migration/script/test files (break long lines; content preserved byte-identical in migrate_prompts.py)
  - B023  tests/architecture + tests/unit (bind loop variable via default parameter)
  - B007  tests/performance/start_mock_services.py (rename proc → _proc)
  - E402  tests/performance/* (add per-file-ignore — sys.path manipulation is intentional in script-style test fixtures)

After this commit: `uv run ruff check backend/` is green, so CI can
start failing on any newly introduced lint violations.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: B1-4 — Eliminate pytest warnings (`collect_ignore_glob` + `TestConfig`)

**Scope:** Move `collect_ignore_glob` out of pyproject (pytest 9 ignores it there) into a root `conftest.py`. Rename `tests/performance/config.py:TestConfig` to `PerfTestConfig` so pytest stops trying to collect it as a test class.

**Files:**
- Modify: `pyproject.toml` — remove the `collect_ignore_glob` key from `[tool.pytest.ini_options]`
- Create: `backend/conftest.py` — one-liner with `collect_ignore_glob`
- Modify: `backend/tests/performance/config.py` — rename class
- Modify: any call sites of `TestConfig` in performance tests

- [ ] **Step 1: Baseline — capture warning count**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests --collect-only 2>&1 | grep -c -i "warning" || echo 0
```
Expected: non-zero (currently 2 distinct warnings: `Unknown config option: collect_ignore_glob`, `cannot collect test class 'TestConfig'`).

- [ ] **Step 2: Move `collect_ignore_glob` from pyproject to conftest**

Edit `pyproject.toml`. Remove this line from `[tool.pytest.ini_options]`:
```diff
-collect_ignore_glob = ["backend/tests/performance/*"]
```

Create `backend/conftest.py` (at the `backend/` root, NOT `backend/tests/conftest.py`) with:
```python
"""Backend-root pytest conftest.

pytest 9 no longer reads `collect_ignore_glob` from pyproject.toml; declare
it here instead. Performance tests under backend/tests/performance/ run
standalone (sys.path manipulation, live servers) and are excluded from the
default `pytest backend/tests` invocation.
"""
collect_ignore_glob = ["tests/performance/*"]
```

(Note: the paths in a conftest `collect_ignore_glob` are relative to the conftest's directory. Placing it at `backend/conftest.py` lets the glob be `tests/performance/*` — tidier than the absolute form.)

- [ ] **Step 3: Rename TestConfig → PerfTestConfig**

Edit `backend/tests/performance/config.py:9`. Change:
```diff
-@dataclass
-class TestConfig:
+@dataclass
+class PerfTestConfig:
     """Test configuration settings."""
```

Find and update all call sites:
```bash
cd /home/singer/MuseAI && rg -l "TestConfig" backend/tests/performance/ backend/tests/__init__.py 2>/dev/null
```
For each match, replace `TestConfig` with `PerfTestConfig`. Typical call sites:
- `backend/tests/performance/test_users.py` (constructor invocations)
- `backend/tests/performance/locustfile.py`
- `backend/tests/performance/analyze_results.py`
- Any `from .config import TestConfig` imports

Run to confirm no residual:
```bash
cd /home/singer/MuseAI && rg "TestConfig\b" backend/
```
Expected: empty (or only `PerfTestConfig` if the regex matches both; use `\bTestConfig\b` with ripgrep word boundaries).

- [ ] **Step 4: Verify no warnings in the default pytest run**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests --collect-only 2>&1 | tail -10
```
Expected: no `PytestConfigWarning` or `PytestCollectionWarning`. The summary should read approximately `N tests collected in X.XXs` with no warnings listed.

- [ ] **Step 5: Verify the full suite still passes**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -5
```
Expected: all green.

- [ ] **Step 6: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add pyproject.toml backend/conftest.py backend/tests/performance/ && git commit -m "$(cat <<'EOF'
test(pytest): silence two long-standing collection warnings

- collect_ignore_glob was set in pyproject.toml but pytest 9 no longer
  reads it from there; move to backend/conftest.py so the performance
  suite is actually excluded from the default run.
- Rename tests/performance/config.py:TestConfig to PerfTestConfig
  (pytest was trying to collect it as a test class because of the
  leading "Test", then warning that a dataclass cannot be collected).

Closes TEST-P2-03 and TEST-P2-04 from the 2026-04-17 midterm audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch B1 Verification

After all four tasks commit:

- [ ] **Run the full acceptance sweep**

```bash
cd /home/singer/MuseAI && \
  uv run mypy backend/ 2>&1 | tail -3 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture --tb=short 2>&1 | tail -3 && \
  uv run pytest backend/tests --collect-only 2>&1 | grep -i "warning" | head -3
```

Expected:
- mypy: `Success: no issues found in N source files` (exit 0)
- ruff: `All checks passed!` (exit 0)
- pytest unit+contract+architecture: all green; count stays at ≈ 739 plus Tasks 1/2 additions (if any)
- pytest collect-only: no lines starting with `warning`

- [ ] **Confirm the four audit items are closed**:
  - TEST-P1-03 (layer rules too narrow) ✅ by Task 2
  - TEST-P2-03 (pytest config warning) ✅ by Task 4
  - TEST-P2-04 (TestConfig collection warning) ✅ by Task 4
  - "mypy completely unchecked" (audit appendix A) ✅ by Task 1
  - 36 ruff errors → 0 (audit §1 P3) ✅ by Task 3

B1 complete. The next batch (B2 — architecture unification) will delete entries from `KNOWN_VIOLATIONS` in Task 2 as it fixes the reverse dependencies, and can rely on both `mypy` and `ruff` failing CI on any regression.

---

## Rollback Notes

Each task is its own commit on `feature/tour-visitor-flow`. Any single task can be reverted independently with `git revert <sha>`. If Task 1 branches into Branch C (per-module strict), reverting the commit also reverts the de-stricting — safe.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: four B1 work packages (B1-1 through B1-4) each map to one task. ✓
- **Placeholder scan**: no "TBD" / "fill in" / "similar to" patterns. Step 3 Branch B says "apply the narrowest correct fix" which is guidance, not a placeholder — the specific fix depends on what mypy surfaces. ✓
- **Type / name consistency**: `KNOWN_VIOLATIONS` is a `set[tuple[str, str]]` in all three references (definition, Task 2 Step 1, commit message). `PerfTestConfig` consistent throughout Task 4. ✓
- **Dependency order**: Task 2 uses `KNOWN_VIOLATIONS` to pre-acknowledge B2 violations; this prevents the new layer rule from blocking work before B2 runs. ✓
- **Decision tree in Task 1** handles both optimistic (0 errors) and realistic (many errors) scenarios; CI reaches green in both.
