"""Tests for document error sanitization to prevent internal exception leakage.

This module tests that document processing errors are sanitized before being
exposed through public API responses, preventing internal implementation details
from leaking to users.
"""


import pytest
from app.api.deps import (
    get_db_session as original_get_db_session,
)
from app.infra.postgres.adapters.document_repository import PostgresDocumentRepository
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, User
from app.main import app
from httpx import ASGITransport, AsyncClient

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = "test-user-001"
TEST_ADMIN_ID = "test-admin-001"


@pytest.fixture
async def session_maker():
    return get_session_maker(TEST_DATABASE_URL)


@pytest.fixture
async def db_session(session_maker):
    async with get_session(session_maker) as session:
        engine = session_maker.kw.get("bind")
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        from sqlalchemy import select

        existing_user = await session.execute(select(User).where(User.id == TEST_USER_ID))
        if not existing_user.scalar_one_or_none():
            test_user = User(id=TEST_USER_ID, email="test@example.com", password_hash="test_hash", role="user")
            session.add(test_user)

        existing_admin = await session.execute(select(User).where(User.id == TEST_ADMIN_ID))
        if not existing_admin.scalar_one_or_none():
            test_admin = User(id=TEST_ADMIN_ID, email="admin@example.com", password_hash="test_hash", role="admin")
            session.add(test_admin)

        await session.commit()

        yield session


@pytest.fixture
async def auth_token(db_session):
    """Get a valid JWT token for the test user."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    return jwt_handler.create_token(TEST_USER_ID)


@pytest.fixture
async def admin_token(db_session):
    """Get a valid JWT token for the test admin."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    settings = get_settings()
    jwt_handler = JWTHandler(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    return jwt_handler.create_token(TEST_ADMIN_ID)


@pytest.mark.asyncio
async def test_document_error_sanitized_not_raw_exception(db_session):
    """Test that update_document_status sanitizes raw exceptions.

    When an exception occurs during document processing, the error stored
    should be a generic message like 'processing_failed' rather than
    exposing internal details like stack traces, file paths, or connection URLs.
    """
    from app.application.document_service import create_document, get_document_by_id, update_document_status

    doc_repo = PostgresDocumentRepository(db_session)
    doc = await create_document(doc_repo, "sanitization-test.pdf", TEST_USER_ID)
    await db_session.commit()

    # Simulate an exception with sensitive internal details
    raw_exception = Exception(
        "ConnectionError: Failed to connect to Elasticsearch at http://elasticsearch:9200 - "
        "Connection refused. Stack trace: File '/app/infra/elasticsearch/client.py', line 45"
    )

    # Update document status with the raw exception string (what currently happens)
    await update_document_status(doc_repo, doc.id, "failed", str(raw_exception))
    await db_session.commit()

    # Verify the stored error is sanitized
    fetched_doc = await get_document_by_id(doc_repo, doc.id, TEST_USER_ID)
    assert fetched_doc is not None
    assert fetched_doc.status == "failed"

    # The error should be sanitized - should NOT contain:
    # - Internal file paths
    # - Stack traces
    # - Connection URLs
    # - Internal hostnames
    error_lower = (fetched_doc.error or "").lower()
    assert "/app/" not in error_lower
    assert "stack" not in error_lower
    assert "trace" not in error_lower
    assert "http://" not in error_lower
    assert "elasticsearch" not in error_lower

    # The error should be a generic sanitized value
    assert fetched_doc.error in (None, "processing_failed")


@pytest.mark.asyncio
async def test_public_document_response_does_not_expose_raw_processing_exception(
    db_session, auth_token
):
    """Test that public document responses don't expose raw processing exceptions.

    Even if a raw exception was somehow stored, the public API should not
    expose internal implementation details.
    """
    from app.application.document_service import create_document, update_document_status

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        # Create a document and set a raw error message
        doc_repo = PostgresDocumentRepository(db_session)
        doc = await create_document(doc_repo, "public-error-test.pdf", TEST_USER_ID)
        await db_session.commit()

        # Store a raw exception message (simulating what we want to prevent)
        await update_document_status(
            doc_repo,
            doc.id,
            "failed",
            "RuntimeError: Internal error at /app/services/processor.py:123 - API key sk-xxxxx",
        )
        await db_session.commit()

        # Get the document through public API
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/documents/{doc.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert resp.status_code == 200
        payload = resp.json()

        # The public response should not have an error field at all
        assert "error" not in payload

        # Status should be failed
        assert payload.get("status") == "failed"

        # The response should not contain any trace of internal details
        response_str = str(payload).lower()
        assert "/app/" not in response_str
        assert "api key" not in response_str
        assert "sk-xxxxx" not in response_str
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_document_list_does_not_expose_internal_errors(
    db_session, auth_token
):
    """Test that document list responses don't expose internal error details."""
    from app.application.document_service import create_document, update_document_status

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        # Create a document with an error containing internal details
        doc_repo = PostgresDocumentRepository(db_session)
        doc = await create_document(doc_repo, "internal-error-test.pdf", TEST_USER_ID)
        # Simulate a raw exception being stored
        await update_document_status(
            doc_repo,
            doc.id,
            "failed",
            "RuntimeError: Internal connection to database at postgres://admin:secret@db:5432 failed",
        )
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()

        # Find our document in the list
        doc_data = next((d for d in data["documents"] if d["id"] == doc.id), None)
        assert doc_data is not None
        assert doc_data["status"] == "failed"

        # Error field should NOT be present in public response
        assert "error" not in doc_data

        # Response should not contain sensitive internal details
        response_str = str(doc_data).lower()
        assert "postgres://" not in response_str
        assert "secret" not in response_str
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_ingestion_job_error_sanitized_in_public_response(
    db_session, auth_token
):
    """Test that ingestion job errors are also sanitized in public responses."""
    from app.application.document_service import create_document, update_document_status

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        # Create a document
        doc_repo = PostgresDocumentRepository(db_session)
        doc = await create_document(doc_repo, "job-error-test.pdf", TEST_USER_ID)
        await db_session.commit()

        # Update status with a detailed error message
        await update_document_status(
            doc_repo,
            doc.id,
            "failed",
            "ChunkingError: Failed at line 234 in /app/application/chunking.py - memory allocation failed",
        )
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/documents/{doc.id}/status",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()

        # Public ingestion job response should not have error field
        assert "error" not in data

        # No internal file paths or details should be exposed
        response_str = str(data).lower()
        assert "/app/" not in response_str
        assert "chunking.py" not in response_str
        assert "memory allocation" not in response_str
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_common_exception_types_are_sanitized(db_session):
    """Test that common exception types are properly sanitized.

    Various types of exceptions (connection errors, file errors, etc.)
    should all result in a sanitized error message.
    """
    from app.application.document_service import create_document, get_document_by_id, update_document_status

    test_cases = [
        (
            "ConnectionError: Failed to connect to http://internal-server:8080/api",
            "Connection error",
        ),
        (
            "FileNotFoundError: [Errno 2] No such file or directory: '/etc/secrets/api_key.txt'",
            "File not found",
        ),
        (
            "PermissionError: [Errno 13] Permission denied: '/root/config.yaml'",
            "Permission denied",
        ),
        (
            "ValueError: Invalid API key format: sk-proj-xxxxx",
            "Invalid value",
        ),
        (
            "RuntimeError: Unexpected state in /app/workers/processor.py:456",
            "Runtime error",
        ),
    ]

    doc_repo = PostgresDocumentRepository(db_session)

    for i, (raw_error, _description) in enumerate(test_cases):
        doc = await create_document(doc_repo, f"test-{i}.pdf", TEST_USER_ID)
        await db_session.commit()

        # Update with the raw error
        await update_document_status(doc_repo, doc.id, "failed", raw_error)
        await db_session.commit()

        # Verify the stored error is sanitized
        fetched_doc = await get_document_by_id(doc_repo, doc.id, TEST_USER_ID)
        assert fetched_doc is not None

        # The error should be sanitized
        error_lower = (fetched_doc.error or "").lower()

        # Should not contain sensitive patterns
        assert "sk-proj" not in error_lower, f"API key leaked in: {fetched_doc.error}"
        assert "/etc/secrets" not in error_lower, f"Internal path leaked in: {fetched_doc.error}"
        assert "/root/" not in error_lower, f"Internal path leaked in: {fetched_doc.error}"
        assert "/app/" not in error_lower, f"Internal path leaked in: {fetched_doc.error}"
        assert "http://" not in error_lower, f"URL leaked in: {fetched_doc.error}"


@pytest.mark.asyncio
async def test_sanitized_error_value_is_consistent(db_session):
    """Test that the sanitized error value is consistent and predictable."""
    from app.application.document_service import create_document, get_document_by_id, update_document_status

    doc_repo = PostgresDocumentRepository(db_session)

    # Create multiple documents with different errors
    for i in range(3):
        doc = await create_document(doc_repo, f"consistent-{i}.pdf", TEST_USER_ID)
        await db_session.commit()

        await update_document_status(
            doc_repo,
            doc.id,
            "failed",
            f"Detailed error {i} at /internal/path/{i}.py",
        )
        await db_session.commit()

        fetched_doc = await get_document_by_id(doc_repo, doc.id, TEST_USER_ID)
        assert fetched_doc is not None

        # All errors should be sanitized to the same value
        assert fetched_doc.error in (None, "processing_failed"), \
            f"Error should be sanitized to 'processing_failed', got: {fetched_doc.error}"
