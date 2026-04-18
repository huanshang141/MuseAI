"""Contract tests for SEC-P1-03 — document upload content validation.

Each test posts a file to /api/v1/documents/upload via the admin-auth path
and asserts the rejection is clean: status code, detail shape, no document
row created (the repo's add method must not be called on rejected paths).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import (
    check_rate_limit,
    get_current_admin,
    get_db_session,
    get_unified_indexing_service_dep,
)
from app.main import app
from fastapi.testclient import TestClient

TEST_ADMIN = {"id": "admin-1", "email": "admin@test.local", "role": "admin"}


class _FakeSession:
    async def commit(self):
        return None


@pytest.fixture
def override_admin_auth():
    mock_service = MagicMock()
    app.dependency_overrides[get_current_admin] = lambda: TEST_ADMIN
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[get_db_session] = lambda: _FakeSession()
    app.dependency_overrides[get_unified_indexing_service_dep] = lambda: mock_service
    yield
    app.dependency_overrides.pop(get_current_admin, None)
    app.dependency_overrides.pop(check_rate_limit, None)
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_unified_indexing_service_dep, None)


@pytest.fixture
def patch_document_side_effects(monkeypatch):
    """Capture whether the endpoint reached document creation.

    Any rejected upload MUST NOT reach create_document. Calls against these
    mocks count reach-throughs that constitute a bypass bug.
    """
    mock_create = AsyncMock()
    monkeypatch.setattr("app.api.documents.create_document", mock_create)
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
    assert response.status_code in {400, 415}
    patch_document_side_effects.assert_not_called()


def test_accepts_valid_txt_upload(override_admin_auth, patch_document_side_effects, monkeypatch):
    """Baseline: a clean text/plain file with .txt extension must still succeed.
    If this test fails, the validator is too strict."""
    monkeypatch.setattr("app.api.documents.PostgresDocumentRepository", MagicMock())
    fake_doc = MagicMock()
    fake_doc.id = "doc-1"
    fake_doc.filename = "ok.txt"
    fake_doc.status = "pending"
    fake_doc.error = None
    from datetime import UTC, datetime
    fake_doc.created_at = datetime.now(UTC)
    patch_document_side_effects.return_value = fake_doc

    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("ok.txt", b"hello world\nclean ASCII\n", "text/plain")},
    )

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

    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("doc.md", "# 标题\n内容".encode(), "text/markdown")},
    )

    assert response.status_code == 200, response.text
