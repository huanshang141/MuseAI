import os
import tempfile

import pytest
from app.api.deps import get_db_session as original_get_db_session
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
async def test_upload_document(db_session, admin_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(tmp_path, "rb") as f:
                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )

        os.unlink(tmp_path)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["status"] == "pending"
        assert "id" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_list_documents(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document(db_session, auth_token):
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/documents/{doc.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc.id
        assert data["filename"] == "test.pdf"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document_not_found(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents/nonexistent-id",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document_status(db_session, auth_token):
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "status-test.pdf", 2048, TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/documents/{doc.id}/status",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc.id
        assert data["status"] == "pending"
        assert data["chunk_count"] == 0
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document_status_document_not_found(db_session, auth_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents/nonexistent-id/status",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_document(db_session, admin_token):
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "to-delete.pdf", 512, TEST_ADMIN_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/documents/{doc.id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["document_id"] == doc.id
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_document_not_found(db_session, admin_token):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/documents/nonexistent-id",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_upload_rate_limit_exceeded(db_session, admin_token):
    """Test that rate limit returns 429 when exceeded."""
    from unittest.mock import AsyncMock

    from app.api.deps import get_redis_cache

    async def override_get_db():
        yield db_session

    # Create a mock Redis cache that simulates rate limit exceeded
    mock_redis = AsyncMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=False)
    mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

    def override_redis():
        return mock_redis

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[get_redis_cache] = override_redis

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(tmp_path, "rb") as f:
                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )

        os.unlink(tmp_path)

        assert response.status_code == 429
        assert response.json()["detail"] == "Rate limit exceeded"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_upload_rate_limit_allows_requests_within_limit(db_session, admin_token):
    """Test that rate limit allows requests within limit."""
    from unittest.mock import AsyncMock

    from app.api.deps import get_redis_cache

    async def override_get_db():
        yield db_session

    # Create a mock Redis cache that allows the request
    mock_redis = AsyncMock()
    mock_redis.check_rate_limit = AsyncMock(return_value=True)
    mock_redis.is_token_blacklisted = AsyncMock(return_value=False)

    def override_redis():
        return mock_redis

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[get_redis_cache] = override_redis

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(tmp_path, "rb") as f:
                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )

        os.unlink(tmp_path)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["status"] == "pending"
        assert "id" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_document_error_field_accessible_via_api(db_session, auth_token):
    """Test that the error field is accessible via the API when set."""
    from app.application.document_service import create_document, update_document_status

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "error-test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        # Update document to failed status with error
        await update_document_status(db_session, doc.id, "failed", "Processing failed: test error")
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/documents/{doc.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Processing failed: test error"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_document_list_shows_error_field(db_session, auth_token):
    """Test that the error field is included in document list responses."""
    from app.application.document_service import create_document, update_document_status

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "error-list-test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        # Update document to failed status with error
        await update_document_status(db_session, doc.id, "failed", "Test error message")
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
        assert doc_data["error"] == "Test error message"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_update_document_status_function(db_session):
    """Test that update_document_status correctly updates the document."""
    from app.application.document_service import create_document, get_document_by_id, update_document_status

    doc = await create_document(db_session, "status-update-test.pdf", 1024, TEST_USER_ID)
    await db_session.commit()

    # Update the document status
    updated_doc = await update_document_status(db_session, doc.id, "failed", "Test error")
    await db_session.commit()

    assert updated_doc is not None
    assert updated_doc.status == "failed"
    assert updated_doc.error == "Test error"

    # Verify the update persisted
    fetched_doc = await get_document_by_id(db_session, doc.id, TEST_USER_ID)
    assert fetched_doc is not None
    assert fetched_doc.status == "failed"
    assert fetched_doc.error == "Test error"


@pytest.mark.asyncio
async def test_list_documents_public_access(db_session):
    """Test that documents can be listed without authentication."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_upload_requires_admin(db_session, auth_token):
    """Test that upload requires admin role."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(tmp_path, "rb") as f:
                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )

        os.unlink(tmp_path)

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_requires_admin(db_session, auth_token):
    """Test that delete requires admin role."""
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/documents/{doc.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 403
    finally:
        app.dependency_overrides = {}
