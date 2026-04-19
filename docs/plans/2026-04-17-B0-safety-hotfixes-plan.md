# B0 Safety Hot-fixes Implementation Plan
**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three P1 safety items in under one person-day: patch a high-severity vite CVE, tighten JWT `verify_token` to enforce `type == "access"`, and delete the half-built refresh-token plumbing.

**Architecture:** Three independent work packages. B0-1 is a dependency upgrade verified with `npm audit`. B0-2 is a TDD cycle on `JWTHandler.verify_token`. B0-3 is a targeted deletion (grep → delete → verify no callers). Each task ends in its own commit; all changes stay within existing module boundaries.

**Tech Stack:** Python 3.11, FastAPI, python-jose (JWT via `jose.jwt`), bcrypt, pytest, uv; Node 24, npm, vite, vitest for the frontend upgrade.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B0.

**Related audit findings:** SEC-P1-01 (vite CVE), SEC-P1-02 (verify_token type), SEC-P2-01 (refresh token dead code).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/package-lock.json` | Modify (via `npm update`) | Advance vite within caret to patch GHSA-4w7w-66w2-5vf9 |
| `backend/app/infra/security/jwt_handler.py` | Modify | (a) add `type == "access"` gate in `verify_token`; (b) delete `create_refresh_token`, `verify_refresh_token`, `REFRESH_EXPIRE_DAYS` |
| `backend/tests/unit/test_jwt_handler.py` | Modify | Add tests for (a); remove any refresh-token tests (currently none) |

No other files change. The `decode_token` and `get_jti` methods stay untouched (they're used elsewhere).

---

## Task 1: B0-1 — Upgrade vite to patch path-traversal CVE

**Scope:** Refresh `frontend/package-lock.json` so installed vite ≥ 8.0.8 (caret range already permits it). Verify with `npm audit`.

**Files:**
- Modify: `frontend/package-lock.json` (via `npm update`, not hand-edited)

- [ ] **Step 1: Capture audit baseline**

Run:
```bash
cd /home/singer/MuseAI/frontend && npm audit --json > /tmp/audit-before.json 2>&1 ; tail -40 /tmp/audit-before.json
```
Expected: output includes `"vite"` with `"severity": "high"` and advisory `GHSA-4w7w-66w2-5vf9` (path traversal). Record the `metadata.vulnerabilities` counts for later comparison.

- [ ] **Step 2: Update packages within caret ranges**

Run:
```bash
cd /home/singer/MuseAI/frontend && npm update
```
Expected: npm updates several packages including vite. `package.json` is **not** modified (caret ranges unchanged). Only `package-lock.json` changes.

- [ ] **Step 3: Verify vite was bumped**

Run:
```bash
cd /home/singer/MuseAI/frontend && node -e "console.log(require('./node_modules/vite/package.json').version)"
```
Expected: `8.0.8` or newer (within `^8.0.3`).

- [ ] **Step 4: Re-run audit and confirm HIGH count is zero**

Run:
```bash
cd /home/singer/MuseAI/frontend && npm audit --json > /tmp/audit-after.json 2>&1 ; node -e "const d=require('/tmp/audit-after.json'); console.log(JSON.stringify(d.metadata.vulnerabilities,null,2))"
```
Expected: `"high": 0`. (`moderate` may still be non-zero due to vitest 1.x / esbuild — those are scheduled for a separate batch and are dev-only.)

- [ ] **Step 5: Smoke-test the frontend build**

Run:
```bash
cd /home/singer/MuseAI/frontend && npm run build 2>&1 | tail -20
```
Expected: `vite build` completes; final line reports success and emits `dist/` assets. No new warnings about removed APIs.

- [ ] **Step 6: Smoke-test the frontend test suite**

Run:
```bash
cd /home/singer/MuseAI/frontend && npm run test -- --run 2>&1 | tail -20
```
Expected: all existing vitest tests pass. If any test fails solely due to a vitest 1.x quirk (unlikely within patch bump), note it but do not fix in this plan — record for B?-follow-up.

- [ ] **Step 7: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add frontend/package-lock.json && git commit -m "$(cat <<'EOF'
fix(deps): bump vite to patch path-traversal CVE (GHSA-4w7w-66w2-5vf9)

Closes SEC-P1-01 from midterm debt audit. `npm update` refreshes vite
to 8.0.8 within the existing caret range, clearing the HIGH-severity
advisory. package.json is unchanged; only the lockfile moved.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: one commit containing only `frontend/package-lock.json`.

---

## Task 2: B0-2 — `verify_token` must enforce `type == "access"`

**Scope:** TDD cycle. `JWTHandler.verify_token` currently returns `sub` for any successfully-decoded token regardless of whether it's `type="access"` or `type="refresh"`. Add the missing check. This task uses the refresh-token methods that Task 3 will delete — **order matters**: run Task 2 before Task 3, and write the test using the `create_refresh_token` method that still exists.

**Files:**
- Modify: `backend/tests/unit/test_jwt_handler.py` (add 1 test)
- Modify: `backend/app/infra/security/jwt_handler.py:45-50` (1-line change)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_jwt_handler.py`:
```python
def test_verify_token_rejects_refresh_token():
    """A refresh token (type='refresh') must NOT be accepted by verify_token."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    # Build a refresh token directly via the existing create_refresh_token API.
    # (After B0-3 this method is deleted; this test will then forge the token inline.)
    refresh_token = handler.create_refresh_token("user-123")

    # verify_token is for access tokens only.
    user_id = handler.verify_token(refresh_token)

    assert user_id is None, (
        "verify_token must reject refresh tokens: got sub=%r" % user_id
    )


def test_verify_token_accepts_access_token_explicitly():
    """Sanity: a normal access token still passes verify_token."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)
    access_token = handler.create_token("user-123")

    user_id = handler.verify_token(access_token)

    assert user_id == "user-123"
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_jwt_handler.py::test_verify_token_rejects_refresh_token -v
```
Expected: FAIL with `AssertionError: verify_token must reject refresh tokens: got sub='user-123'`. (`test_verify_token_accepts_access_token_explicitly` should already PASS — sanity baseline.)

- [ ] **Step 3: Implement the minimal fix**

Edit `backend/app/infra/security/jwt_handler.py`. Replace the body of `verify_token` (lines 45-50):

Old:
```python
    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except JWTError:
            return None
```

New:
```python
    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
```

- [ ] **Step 4: Run the new test to verify it passes**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_jwt_handler.py -v
```
Expected: all tests in the file PASS (the new one + all existing).

- [ ] **Step 5: Run the full unit + contract test suites to guard against regression**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract -v --tb=short 2>&1 | tail -30
```
Expected: 768 collected, 0 failed, 0 errors. Pay particular attention to auth-related tests (`test_auth_service`, `test_auth_logout`, `test_auth_rate_limit`, `test_api_deps`, `test_deps_security`) and contract tests that hit protected endpoints. All should still pass because `create_token` already sets `type="access"`.

- [ ] **Step 6: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/app/infra/security/jwt_handler.py backend/tests/unit/test_jwt_handler.py && git commit -m "$(cat <<'EOF'
fix(security): verify_token enforces type='access' (SEC-P1-02)

Previously verify_token returned sub for any successfully-decoded JWT,
so a refresh token could satisfy access-token-protected endpoints.
Adds an explicit type check and corresponding unit test.

Closes SEC-P1-02 from midterm debt audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: B0-3 — Delete half-built refresh-token plumbing

**Scope:** Remove `create_refresh_token`, `verify_refresh_token`, and `REFRESH_EXPIRE_DAYS` from `JWTHandler`. Per `rg -l "create_refresh_token|verify_refresh_token|REFRESH_EXPIRE"` run during planning, only `jwt_handler.py` itself references these — so deletion is safe and requires no call-site fixes. Also update the test added in Task 2 so it no longer depends on the deleted method.

**Files:**
- Modify: `backend/app/infra/security/jwt_handler.py` (delete 3 items)
- Modify: `backend/tests/unit/test_jwt_handler.py` (rewrite one test to forge the refresh token inline)

- [ ] **Step 1: Confirm zero external callers (safety check before deleting)**

Run:
```bash
cd /home/singer/MuseAI && rg -l "create_refresh_token|verify_refresh_token|REFRESH_EXPIRE_DAYS" --glob '!*.pyc' --glob '!__pycache__'
```
Expected: only `backend/app/infra/security/jwt_handler.py` (and possibly `backend/tests/unit/test_jwt_handler.py` after Task 2). If any other file appears, STOP and update this plan — this indicates a caller that was missed during audit.

- [ ] **Step 2: Delete refresh methods from jwt_handler.py**

Edit `backend/app/infra/security/jwt_handler.py`. Remove the `REFRESH_EXPIRE_DAYS = 7` class attribute (currently line 8), the entire `create_refresh_token` method (lines 32-43), and the entire `verify_refresh_token` method (lines 52-58).

The file should now look like:
```python
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt


class JWTHandler:
    def __init__(self, secret: str, algorithm: str, expire_minutes: int):
        self.secret = secret
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def create_token(self, user_id: str, extra_data: dict[str, Any] | None = None) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self.expire_minutes)

        payload = dict(extra_data) if extra_data else {}
        payload.update({
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "access",
        })

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None
        if payload.get("type") != "access":
            return None
        return payload.get("sub")

    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except JWTError:
            return None

    def get_jti(self, token: str) -> str | None:
        payload = self.decode_token(token)
        return payload.get("jti") if payload else None
```

- [ ] **Step 3: Rewrite the Task-2 test so it forges a refresh token inline**

The test previously called `handler.create_refresh_token("user-123")`, which now no longer exists. Replace that test in `backend/tests/unit/test_jwt_handler.py` with this version:

Old (delete):
```python
def test_verify_token_rejects_refresh_token():
    """A refresh token (type='refresh') must NOT be accepted by verify_token."""
    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    # Build a refresh token directly via the existing create_refresh_token API.
    # (After B0-3 this method is deleted; this test will then forge the token inline.)
    refresh_token = handler.create_refresh_token("user-123")

    # verify_token is for access tokens only.
    user_id = handler.verify_token(refresh_token)

    assert user_id is None, (
        "verify_token must reject refresh tokens: got sub=%r" % user_id
    )
```

New:
```python
def test_verify_token_rejects_non_access_token():
    """A token with type != 'access' must NOT be accepted by verify_token."""
    from datetime import UTC, datetime, timedelta
    from jose import jwt

    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    # Forge a refresh-style token directly to simulate a malicious or legacy token.
    now = datetime.now(UTC)
    forged_payload = {
        "sub": "user-123",
        "exp": now + timedelta(days=7),
        "iat": now,
        "type": "refresh",
    }
    forged_token = jwt.encode(forged_payload, handler.secret, algorithm=handler.algorithm)

    user_id = handler.verify_token(forged_token)

    assert user_id is None, (
        "verify_token must reject non-access tokens: got sub=%r" % user_id
    )


def test_verify_token_rejects_token_with_missing_type():
    """A token without a 'type' claim must NOT be accepted by verify_token."""
    from datetime import UTC, datetime, timedelta
    from jose import jwt

    handler = JWTHandler(secret="test-secret", algorithm="HS256", expire_minutes=60)

    now = datetime.now(UTC)
    payload = {
        "sub": "user-123",
        "exp": now + timedelta(minutes=60),
        "iat": now,
        # no "type" key
    }
    legacy_token = jwt.encode(payload, handler.secret, algorithm=handler.algorithm)

    user_id = handler.verify_token(legacy_token)

    assert user_id is None
```

- [ ] **Step 4: Run the JWT handler tests — all should pass**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_jwt_handler.py -v
```
Expected: all tests PASS including the two rewritten ones.

- [ ] **Step 5: Run the full test suite — guard against regression**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract backend/tests/architecture -v --tb=short 2>&1 | tail -20
```
Expected: 0 failed, 0 errors.

- [ ] **Step 6: Grep verify no stale references remain**

Run:
```bash
cd /home/singer/MuseAI && rg "create_refresh_token|verify_refresh_token|REFRESH_EXPIRE_DAYS" --glob '!*.pyc' --glob '!__pycache__'
```
Expected: no output. If any match appears (comments, docs, old tests), remove them now before committing.

- [ ] **Step 7: Run ruff on the edited files**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/infra/security/jwt_handler.py backend/tests/unit/test_jwt_handler.py
```
Expected: `All checks passed!`.

- [ ] **Step 8: Commit**

Run:
```bash
cd /home/singer/MuseAI && git add backend/app/infra/security/jwt_handler.py backend/tests/unit/test_jwt_handler.py && git commit -m "$(cat <<'EOF'
refactor(security): delete unused refresh-token plumbing (SEC-P2-01)

create_refresh_token, verify_refresh_token, and REFRESH_EXPIRE_DAYS
have no callers anywhere in the codebase. Half-built crypto surface
is a footgun — remove it. If a refresh flow is needed later, design
it fresh with rotation, blacklisting, and paired issuance.

The Task-2 test is rewritten to forge a type='refresh' token inline
so the access-type-gating guarantee is still covered.

Closes SEC-P2-01 from midterm debt audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch B0 Verification

After all three tasks commit:

- [ ] **Run the full verification sweep**

```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests -v --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ | tail -5 && \
  (cd frontend && npm audit --production 2>&1 | grep -E "high|critical" || echo "frontend: 0 high/critical in production deps")
```

Expected:
- All 768 tests pass (possibly + 2 new ones added in Task 2/3, so 770)
- Ruff: same 36 pre-existing errors (unchanged — B1 handles those)
- Frontend audit: no HIGH or CRITICAL in production dependencies

- [ ] **Confirm the three audit IDs are closed** — no further code changes required:
  - SEC-P1-01 (vite CVE) ✅ by Task 1
  - SEC-P1-02 (verify_token type) ✅ by Task 2
  - SEC-P2-01 (refresh token dead code) ✅ by Task 3

B0 complete. Proceed to B1 (CI guardrails) per the parent spec's batch dependency graph.

---

## Rollback Notes

Each task is its own commit on `feature/tour-visitor-flow`. Any single task can be reverted independently with `git revert <sha>`. None of the three tasks share state across files, so partial rollback is safe.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: B0 spec covers 3 work packages (B0-1, B0-2, B0-3) — each has a corresponding task. ✓
- **Placeholder scan**: no "TBD" / "TODO" / "add appropriate …" / "similar to" patterns. All code blocks are complete. ✓
- **Type consistency**: `JWTHandler.verify_token` signature stays `(self, token: str) -> str | None` throughout. `test_verify_token_rejects_non_access_token` uses the same `handler.secret` / `handler.algorithm` attributes that the existing tests use. ✓
- **Ordering**: Task 2 must run before Task 3 (Task 2 uses `create_refresh_token`, which Task 3 deletes — the plan explicitly notes this and rewrites the test in Task 3 Step 3).
