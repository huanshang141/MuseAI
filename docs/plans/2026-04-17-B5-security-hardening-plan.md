# B5 Security Hardening Implementation Plan
**Status:** completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two backend-only security gaps from the audit in ~1.5–2 person-days: document-upload content validation (SEC-P1-03) and bcrypt 72-byte truncation (SEC-P2-03).

**Scope boundary — what this batch does NOT do (intentional):**

1. **SEC-P1-04 (cookie→Bearer cutover) is deferred.** The frontend currently depends on `credentials: 'include'` in 5 request sites and its composable tests assert `localStorage.getItem('access_token')).toBeNull()`. The cutover needs a coordinated frontend rewrite (api/index.js, useAuth.js, 3+ test files) plus a brief migration grace window. Bundling that with the two safe backend changes in this batch would bloat the commit and risk shipping the backend half without the frontend half. A dedicated follow-up batch will handle SEC-P1-04 end-to-end.

2. **SEC-P2-04 is already closed.** `auth.py:24-39` implements the full password-strength policy (min 8 / max 128 chars, upper/lower/digit/special required) and `test_auth_service.py:200-218+` already covers it. No work needed.

3. **SEC-P2-05 (prompt injection) is out of scope.** It is a design-level concern requiring retrieval-side guardrails + output validation + red-team testing — a batch of its own.

4. **Deprecated service coverage** (`exhibit_indexing_service`, `ingestion_service`) flagged in the B4 review-back is out of scope for B5. `exhibit_indexing_service` has a `DeprecationWarning` at import and zero production callers; `ingestion_service` is live but being replaced by `unified_indexing_service`. Test coverage for deprecated/phase-out code wastes effort.

**Tech Stack:** Python 3.11, FastAPI, `python-magic` (optional — fallback to magic-number sniff in-code), bcrypt, hashlib, pytest, uv.

**Parent spec:** `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md` §4 Batch B5.

**Related audit findings:** SEC-P1-03, SEC-P2-03.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/api/documents.py` | Modify | Add `validate_upload(file)` call before `stream_to_temp_file`; return 400 for rejected files |
| `backend/tests/contract/test_documents_upload_validation.py` | Create | Contract tests covering rejected file types + null-byte content |
| `backend/app/infra/security/password.py` | Modify | SHA-256 pre-hash with `v1:` version prefix; backward-compat verify for un-prefixed (legacy) hashes |
| `backend/tests/unit/test_password.py` | Modify | Extend existing tests: pin 72-byte-truncation fix, backward-compat for legacy hashes |

No other files change.

---

## Task 1: B5-1 — Document upload content validation (SEC-P1-03)

**Scope:** Reject uploads that aren't plaintext/markdown before spending disk + background-task cycles on them. Validation layers (all three required — belt-and-braces):

1. **Filename extension allowlist** — `.txt`, `.md`, `.markdown` (case-insensitive).
2. **Declared content-type allowlist** — `text/plain`, `text/markdown`. Reject obvious mismatches (e.g. `image/png` with `.md` rename).
3. **Magic-number sniff on first 8 KiB** — after streaming the bytes to temp, verify: no null bytes in the first 8 KiB, and UTF-8-decodable. This catches cases where the client lies about content-type.

**Failure mode:** any failure → 415 Unsupported Media Type (or 400 if the filename itself is malformed). Temp file is cleaned up. No background task enqueued. No document row created.

**Why magic-number on 8 KiB and not the whole file:** text files can legitimately be large; the first 8 KiB is enough to catch binary signatures (PNG `\x89PNG`, PDF `%PDF`, ZIP `PK\x03\x04`, etc.) without reading the entire file twice. If the first 8 KiB is text-safe, we trust the rest (size is already capped at 50 MiB).

**Why extension allowlist first:** cheapest check. Fail fast before touching disk.

**Files:**
- Modify: `backend/app/api/documents.py`
- Create: `backend/tests/contract/test_documents_upload_validation.py`

- [ ] **Step 1: Write the failing contract tests (TDD red phase)**

Create `backend/tests/contract/test_documents_upload_validation.py`:
```python
"""Contract tests for SEC-P1-03 — document upload content validation.

Each test posts a file to /api/v1/documents/upload via the admin-auth path
and asserts the rejection is clean: status code, detail shape, no document
row created (the repo's add method must not be called on rejected paths).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import get_current_admin, rate_limit
from app.main import app
from fastapi.testclient import TestClient


TEST_ADMIN = {"id": "admin-1", "email": "admin@test.local"}


@pytest.fixture
def override_admin_auth():
    app.dependency_overrides[get_current_admin] = lambda: TEST_ADMIN
    app.dependency_overrides[rate_limit] = lambda: True
    yield
    app.dependency_overrides.pop(get_current_admin, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def patch_document_side_effects(monkeypatch):
    """Capture whether the endpoint reached document creation.

    Any rejected upload MUST NOT reach create_document. Calls against these
    mocks count reach-throughs that constitute a bypass bug.
    """
    mock_create = AsyncMock()
    monkeypatch.setattr("app.api.documents.create_document", mock_create)

    mock_service = MagicMock()
    monkeypatch.setattr(
        "app.api.documents.get_unified_indexing_service",
        lambda: mock_service,
    )
    return mock_create


def test_rejects_disallowed_extension(override_admin_auth, patch_document_side_effects):
    """A .pdf upload must be rejected at the validation boundary."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("evil.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 415
    assert "not allowed" in response.json()["detail"].lower() or \
           "unsupported" in response.json()["detail"].lower()
    patch_document_side_effects.assert_not_called()


def test_rejects_executable_disguised_as_txt(override_admin_auth, patch_document_side_effects):
    """A .txt filename with ELF binary content must be rejected by the
    magic-number check even though the extension is allowed."""
    client = TestClient(app)
    elf_bytes = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100 + b"payload"
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("exploit.txt", elf_bytes, "text/plain")},
    )
    assert response.status_code == 415
    patch_document_side_effects.assert_not_called()


def test_rejects_null_bytes_in_text_file(override_admin_auth, patch_document_side_effects):
    """Null bytes in the first 8 KiB are a binary-file signal."""
    client = TestClient(app)
    content = b"legit text\x00followed by null byte\n" + b"more text\n" * 10
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("doc.txt", content, "text/plain")},
    )
    assert response.status_code == 415
    patch_document_side_effects.assert_not_called()


def test_rejects_content_type_mismatch(override_admin_auth, patch_document_side_effects):
    """A .md file with image/png content-type declared is suspicious — reject."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("doc.md", b"# hi\nvalid markdown", "image/png")},
    )
    assert response.status_code == 415
    patch_document_side_effects.assert_not_called()


def test_rejects_filename_without_extension(override_admin_auth, patch_document_side_effects):
    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("README", b"# hi", "text/plain")},
    )
    # Missing extension: extension allowlist check rejects.
    assert response.status_code in {400, 415}
    patch_document_side_effects.assert_not_called()


def test_accepts_valid_txt_upload(override_admin_auth, patch_document_side_effects, monkeypatch):
    """Baseline: a clean text/plain file with .txt extension must still succeed.
    If this test fails, the validator is too strict."""
    # Stub the session + indexing bits the happy path touches.
    monkeypatch.setattr("app.api.documents.PostgresDocumentRepository", MagicMock())
    # create_document returns a shaped-enough object for DocumentResponse.
    fake_doc = MagicMock()
    fake_doc.id = "doc-1"
    fake_doc.filename = "ok.txt"
    fake_doc.status = "pending"
    fake_doc.error = None
    from datetime import UTC, datetime
    fake_doc.created_at = datetime.now(UTC)
    patch_document_side_effects.return_value = fake_doc

    # session.commit must not blow up
    class _FakeSession:
        async def commit(self):
            return None
    # Override the session dep:
    from app.api.deps import get_db_session
    app.dependency_overrides[get_db_session] = lambda: _FakeSession()

    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("ok.txt", b"hello world\nclean ASCII\n", "text/plain")},
    )
    app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200, response.text
    patch_document_side_effects.assert_awaited_once()


def test_accepts_valid_markdown_upload(override_admin_auth, patch_document_side_effects, monkeypatch):
    monkeypatch.setattr("app.api.documents.PostgresDocumentRepository", MagicMock())
    fake_doc = MagicMock()
    fake_doc.id = "doc-2"
    fake_doc.filename = "ok.md"
    fake_doc.status = "pending"
    fake_doc.error = None
    from datetime import UTC, datetime
    fake_doc.created_at = datetime.now(UTC)
    patch_document_side_effects.return_value = fake_doc

    class _FakeSession:
        async def commit(self):
            return None
    from app.api.deps import get_db_session
    app.dependency_overrides[get_db_session] = lambda: _FakeSession()

    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("doc.md", "# 标题\n内容".encode("utf-8"), "text/markdown")},
    )
    app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200, response.text
```

- [ ] **Step 2: Run the new tests — all 7 should FAIL or ERROR (RED phase)**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_documents_upload_validation.py -v 2>&1 | tail -30
```
Expected: 5 rejection tests FAIL (the endpoint currently accepts anything → 200 instead of 415). The 2 "accepts" tests may pass or fail depending on fixture interactions; focus on the rejection-test failures. This is the RED baseline.

- [ ] **Step 3: Implement the validator in `documents.py`**

Edit `backend/app/api/documents.py`:

(a) Add these module-level constants near the other size constants (around line 92):
```python
ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
ALLOWED_CONTENT_TYPES = frozenset({
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",  # Some browsers send this for unknown; content check catches binary.
})
MAGIC_SNIFF_BYTES = 8192
```

(b) Add a new validator function immediately before `stream_to_temp_file`:
```python
def validate_upload_metadata(file: UploadFile) -> None:
    """Pre-content validation: extension + content-type. Raises HTTPException on failure.

    Called BEFORE streaming to disk to fail fast on obvious mismatches.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=415,
            detail=f"File extension not allowed. Accepted: {sorted(ALLOWED_EXTENSIONS)}",
        )

    ct = (file.content_type or "").lower()
    # content_type can be empty for some clients; reject only when explicitly set AND mismatched.
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Content-type not allowed: {ct}",
        )


def validate_upload_content(temp_path: str) -> None:
    """Post-stream magic-number / text check on the first MAGIC_SNIFF_BYTES.

    Called AFTER bytes land on disk. Looks for:
    - null bytes (signal of binary content)
    - invalid UTF-8 (indicates the file isn't text)

    Raises HTTPException(415) on failure. Caller is responsible for cleanup.
    """
    with open(temp_path, "rb") as f:
        head = f.read(MAGIC_SNIFF_BYTES)

    if b"\x00" in head:
        raise HTTPException(
            status_code=415,
            detail="File content appears binary (null bytes detected)",
        )

    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=415,
            detail="File content is not valid UTF-8 text",
        ) from e
```

(c) Wire the validators into the upload endpoint. The handler becomes:
```python
@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_admin: CurrentAdmin,
    _: RateLimitDep,
    unified_indexing_service: UnifiedIndexingServiceDep,
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    validate_upload_metadata(file)

    tmp_path, file_size = await stream_to_temp_file(file, MAX_FILE_SIZE)

    try:
        validate_upload_content(tmp_path)
    except HTTPException:
        # Clean up the temp file before re-raising — validate_upload_content
        # doesn't touch the filesystem on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    doc_repo = PostgresDocumentRepository(session)
    document = await create_document(doc_repo, file.filename, current_admin["id"])
    await session.commit()

    background_tasks.add_task(
        process_document_background,
        document.id,
        tmp_path,
        file.filename,
        unified_indexing_service,
    )

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )
```

- [ ] **Step 4: Re-run the new tests — all 7 should PASS (GREEN phase)**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_documents_upload_validation.py -v 2>&1 | tail -30
```
Expected: 7 passed. If the two "accepts" tests still fail, inspect the fixture — it likely needs additional dep overrides that match the actual request path (e.g. `get_db_session_maker` or `get_unified_indexing_service` if those are touched before validation).

- [ ] **Step 5: Run the existing documents contract tests to ensure no regression**

Run:
```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_documents_api.py backend/tests/contract/test_documents_public_contract.py backend/tests/contract/test_documents_error_sanitization.py -v 2>&1 | tail -10
```
Expected: all pass. If any existing test posts a non-text/non-allowed file and expected success, update that test to use a `.txt` payload with clean content — the validator is the new reality.

- [ ] **Step 6: Run ruff + mypy on the edited file**

Run:
```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/api/documents.py backend/tests/contract/test_documents_upload_validation.py && uv run mypy backend/app/api/documents.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/api/documents.py backend/tests/contract/test_documents_upload_validation.py && git commit -m "$(cat <<'EOF'
feat(security): document upload content validation (SEC-P1-03)

Three layered checks on /api/v1/documents/upload:
1. Extension allowlist (.txt / .md / .markdown) — rejected upfront with 415.
2. Content-type allowlist — rejects obvious mismatches; permissive for
   application/octet-stream since the content check below catches binaries.
3. Magic-number / UTF-8 sniff on the first 8 KiB after streaming — rejects
   null-byte content and non-UTF-8 payloads with 415 and cleans up the temp file.

Seven contract tests pin the behavior: rejects disallowed extensions,
executable-disguised-as-txt, null-byte content, content-type mismatch,
extension-less filenames; accepts clean .txt and .md.

Closes SEC-P1-03 from midterm debt audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: B5-2 — Bcrypt SHA-256 pre-hash with version prefix (SEC-P2-03)

**Scope:** Bcrypt silently truncates passwords to 72 bytes. Two passwords sharing the first 72 bytes hash identically — a subtle bug that becomes a credential-confusion risk for users with long passwords or passphrases. Fix: SHA-256 pre-hash so every input collapses to a 64-byte digest (base64-encoded → 44 bytes, comfortably below 72).

**Backward compatibility:** Existing users have un-prefixed bcrypt hashes. Add a `v1:` prefix to newly-produced hashes; `verify_password` dispatches on presence of the prefix:
- `v1:$2b$...` → SHA-256 pre-hash + bcrypt check.
- `$2b$...` (no prefix) → legacy direct bcrypt check. Still works, still safe for short passwords, just not truncation-safe.

No migration job is needed — users naturally re-hash on next password change. If a later policy wants forced migration, it's a separate batch.

**Files:**
- Modify: `backend/app/infra/security/password.py`
- Modify: `backend/tests/unit/test_password.py`

- [ ] **Step 1: Capture baseline — run existing password tests**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_password.py -v 2>&1 | tail -10
```
Expected: all existing tests pass. Record the count.

- [ ] **Step 2: Write a failing test that proves the current 72-byte truncation bug**

Append to `backend/tests/unit/test_password.py` (keep all existing tests):
```python
def test_long_passwords_differing_only_after_72_bytes_produce_DIFFERENT_hashes():
    """SEC-P2-03 regression: with plain bcrypt, passwords that share the
    first 72 bytes collide. After SHA-256 pre-hash they don't."""
    a = "A" * 72 + "suffix_a"
    b = "A" * 72 + "suffix_b"
    hash_a = hash_password(a)
    # Verify that password `b` does NOT match the hash produced from `a`.
    assert verify_password(a, hash_a) is True
    assert verify_password(b, hash_a) is False, (
        "72-byte truncation regression: `b` verifies against `a`'s hash. "
        "hash_password must pre-hash long inputs."
    )


def test_hash_password_produces_v1_prefixed_output():
    """New hashes must carry the 'v1:' version prefix so verify can dispatch."""
    result = hash_password("SomeStrong!Password42")
    assert result.startswith("v1:"), (
        f"Expected 'v1:'-prefixed hash, got {result[:10]!r}"
    )
    # The portion after v1: must still be a valid bcrypt hash.
    assert result[3:].startswith("$2b$")


def test_verify_password_accepts_v1_prefixed_hash():
    password = "SomeStrong!Password42"
    stored = hash_password(password)
    assert verify_password(password, stored) is True
    assert verify_password("wrong", stored) is False


def test_verify_password_accepts_legacy_unprefixed_bcrypt_hash():
    """Backward compat: hashes produced before SEC-P2-03 fix (no 'v1:' prefix)
    must continue to verify. Simulate one by calling bcrypt directly."""
    import bcrypt as _bcrypt
    password = "LegacyUser!Password"
    legacy_hash = _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    assert not legacy_hash.startswith("v1:")  # sanity: truly legacy format

    assert verify_password(password, legacy_hash) is True
    assert verify_password("wrong", legacy_hash) is False


def test_verify_password_rejects_malformed_hash_without_crashing():
    """Unknown / malformed stored hashes return False, not raise."""
    assert verify_password("anything", "not-a-real-hash") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", "v1:notbcrypt") is False
```

- [ ] **Step 3: Run the failing tests — verify the 72-byte regression fails**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_password.py -v 2>&1 | tail -15
```
Expected:
- `test_long_passwords_differing_only_after_72_bytes_produce_DIFFERENT_hashes` → FAIL with a clear regression message.
- `test_hash_password_produces_v1_prefixed_output` → FAIL (no prefix yet).
- `test_verify_password_accepts_v1_prefixed_hash` → depends on whether legacy hash_password accidentally produces something v1-like; expect FAIL.
- `test_verify_password_accepts_legacy_unprefixed_bcrypt_hash` → PASS (current implementation does this).
- `test_verify_password_rejects_malformed_hash_without_crashing` → may PASS or ERROR depending on current bcrypt.checkpw behavior on junk input. If it ERRORS (raises ValueError), that itself is a bug to fix in Step 4.

- [ ] **Step 4: Implement the fix in `password.py`**

Replace the entire contents of `backend/app/infra/security/password.py` with:
```python
"""Password hashing with SHA-256 pre-hash to avoid bcrypt's 72-byte truncation.

SEC-P2-03: bcrypt silently truncates input to 72 bytes. Pre-hashing with
SHA-256 + base64 encoding compresses any input to 44 ASCII bytes so every
byte of the user's password contributes to the final hash.

Backward compatibility: pre-SEC-P2-03 hashes carry no prefix. verify_password
dispatches on the 'v1:' prefix:
- 'v1:$2b$...' → SHA-256 pre-hash + bcrypt.checkpw
- '$2b$...'    → legacy direct bcrypt.checkpw (still correct for ≤72-byte passwords)

New hashes always carry the 'v1:' prefix. Users migrate naturally on next
password change.
"""
import base64
import hashlib

import bcrypt

_V1_PREFIX = "v1:"


def _prehash(password: str) -> bytes:
    """SHA-256 → base64. 44 ASCII bytes, well under bcrypt's 72-byte cap."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 pre-hash + bcrypt with 'v1:' prefix."""
    salt = bcrypt.gensalt()
    bcrypt_hash = bcrypt.hashpw(_prehash(password), salt).decode("utf-8")
    return f"{_V1_PREFIX}{bcrypt_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password, dispatching on the 'v1:' prefix for backward compat.

    Returns False (not raises) for malformed stored hashes.
    """
    if not hashed_password:
        return False

    try:
        if hashed_password.startswith(_V1_PREFIX):
            stored = hashed_password[len(_V1_PREFIX):]
            return bcrypt.checkpw(_prehash(plain_password), stored.encode("utf-8"))
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 5: Re-run all password tests — all must PASS (GREEN phase)**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_password.py -v 2>&1 | tail -15
```
Expected: all tests pass — the baseline ones, plus the 5 new ones from Step 2.

One subtlety: the existing `test_hash_password` asserts `hashed.startswith("$2b$")`. After this change, hashes start with `v1:$2b$`. Update that assertion to `hashed.startswith("v1:$2b$")`, but **only if** it currently fails. Do not silence a failure; fix the expectation to reflect the new contract.

- [ ] **Step 6: Run the full auth test surface — guard against regression**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_auth_service.py backend/tests/unit/test_password.py backend/tests/unit/test_deps_security.py backend/tests/unit/test_auth_rate_limit.py backend/tests/contract/ -v --tb=short 2>&1 | tail -15
```
Expected: all pass. Auth flows use `hash_password` / `verify_password` symmetrically, so round-trip register → login works transparently.

- [ ] **Step 7: Run ruff + mypy**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/app/infra/security/password.py backend/tests/unit/test_password.py && uv run mypy backend/app/infra/security/password.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
cd /home/singer/MuseAI && git add backend/app/infra/security/password.py backend/tests/unit/test_password.py && git commit -m "$(cat <<'EOF'
fix(security): SHA-256 pre-hash to sidestep bcrypt 72-byte truncation (SEC-P2-03)

hash_password now pre-hashes with SHA-256 + base64 (44 ASCII bytes) before
feeding bcrypt, and prefixes the stored string with 'v1:' so verify can
dispatch. Without this, passwords sharing the first 72 bytes hash identically
— a subtle credential-confusion risk for long passphrases.

Backward compat: legacy (un-prefixed) bcrypt hashes still verify via the
original direct-bcrypt path. Users migrate naturally on next password change.
verify_password now returns False (not raises) for malformed stored hashes.

Five new unit tests: 72-byte collision regression, v1:-prefix production,
v1:-prefix verification, legacy-hash backward-compat, malformed-hash safety.

Closes SEC-P2-03 from midterm debt audit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch B5 Verification

After both tasks commit:

- [ ] **Run the full verification sweep**

```bash
cd /home/singer/MuseAI && \
  uv run pytest backend/tests --tb=short 2>&1 | tail -5 && \
  uv run ruff check backend/ 2>&1 | tail -3 && \
  uv run mypy backend/ 2>&1 | tail -3
```

Expected:
- pytest: ~893 passed (post-B4 was 881; +7 upload validation + +5 password = +12 = 893).
- ruff: `All checks passed!`
- mypy: `Success: no issues found in 90 source files`

- [ ] **Confirm audit IDs closed:**
  - SEC-P1-03 (upload validation) ✅ by Task 1
  - SEC-P2-03 (bcrypt 72-byte) ✅ by Task 2

- [ ] **Audit IDs explicitly NOT closed (deferred by design):**
  - SEC-P1-04 (cookie→Bearer cutover) — follow-up batch, coordinated backend+frontend
  - SEC-P2-02 (admin whitelist → bootstrap CLI fork) — follow-up batch
  - SEC-P2-05 (prompt injection) — design-level, requires retrieval-side guardrails

- [ ] **Manual smoke test (not automated — worth a human eye after merge):**
  1. Try uploading `evil.pdf` via the frontend — should show 415 error.
  2. Try uploading a binary renamed to `.txt` — should show 415 error.
  3. Register a new user with a long passphrase (>72 bytes). Log out. Log back in. Must succeed.
  4. If a legacy user exists (pre-fix), their login must still work without error.

---

## Rollback Notes

Each task is its own commit. Reverting Task 2 is safe: old `password.py` works against both old and new hashes (new hashes start with `v1:` which old bcrypt would refuse — so freshly-registered users would fail to log in after a revert). If you must revert Task 2 after ANY user has registered under the new code, plan to also reset those users' passwords.

Reverting Task 1 is trivially safe — it only removes validation; no data format change.

---

## Self-Review Check (completed inline during authoring)

- **Spec coverage**: Parent-spec §4 Batch B5 nominally includes SEC-P1-03, SEC-P1-04, SEC-P2-03, SEC-P2-04, SEC-P2-05. This plan explicitly handles the two that are clean backend-only work (SEC-P1-03, SEC-P2-03), confirms one is already closed (SEC-P2-04), and defers two requiring coordinated frontend or design work (SEC-P1-04, SEC-P2-05). The deferrals are documented in the scope boundary section with reasons. ✓
- **Placeholder scan**: no "TBD" / "TODO" / "similar to" patterns. One explicit conditional ("update the assertion only if it fails") is guarded with "do not silence a failure; fix the expectation." ✓
- **Backward compatibility**: legacy password hashes still verify via the un-prefixed path. Existing document-upload contract tests either continue to work (if they use text content) or need a tiny payload update to `.txt` — Step 5 of Task 1 explicitly calls out the check + fix direction. ✓
- **Test-first discipline**: Task 2 writes a failing 72-byte regression test before the fix (true TDD). Task 1 writes all 7 contract tests before the validator (RED → GREEN). ✓
- **Blast radius**: Task 1 touches one router + one test file. Task 2 touches one 20-LOC module + one test file. Nothing else changes. No production state migration required. ✓
