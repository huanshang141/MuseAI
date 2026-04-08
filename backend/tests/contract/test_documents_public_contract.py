"""Contract tests for public document read boundary governance.

These tests verify that public endpoints expose only whitelisted fields,
formalizing the public document read contract.
"""

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
async def doc_id(db_session):
    """Create a test document and return its ID."""
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "public-test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()
        yield doc.id
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_document_list_uses_public_field_whitelist(db_session):
    """Test that guest document list response only contains whitelisted public fields."""
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        # Create a test document
        doc = await create_document(db_session, "public-list-test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) > 0

        # Find our document
        doc_data = next((d for d in data["documents"] if d["id"] == doc.id), None)
        assert doc_data is not None

        # Verify only whitelisted public fields are present
        assert set(doc_data.keys()) == {"id", "filename", "status", "created_at"}
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_document_detail_uses_public_field_whitelist(db_session, doc_id):
    """Test that guest document detail response only contains whitelisted public fields."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{doc_id}")

        assert response.status_code == 200
        data = response.json()

        # Verify only whitelisted public fields are present
        assert set(data.keys()) == {"id", "filename", "status", "created_at"}
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_guest_document_status_uses_public_field_whitelist(db_session, doc_id):
    """Test that guest document status response only contains whitelisted public fields."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{doc_id}/status")

        assert response.status_code == 200
        data = response.json()

        # Verify only whitelisted public fields are present
        assert set(data.keys()) == {"id", "document_id", "status", "chunk_count", "created_at", "updated_at"}
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_authenticated_user_document_list_uses_public_field_whitelist(db_session):
    """Test that authenticated user document list response also uses public field whitelist."""
    from app.application.document_service import create_document
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        # Create a test document
        doc = await create_document(db_session, "auth-list-test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        # Get auth token
        settings = get_settings()
        jwt_handler = JWTHandler(
            secret=settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
            expire_minutes=settings.JWT_EXPIRE_MINUTES,
        )
        token = jwt_handler.create_token(TEST_USER_ID)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data

        # Find our document
        doc_data = next((d for d in data["documents"] if d["id"] == doc.id), None)
        assert doc_data is not None

        # Verify only whitelisted public fields are present
        assert set(doc_data.keys()) == {"id", "filename", "status", "created_at"}
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_upload_response_includes_error_field(db_session):
    """Test that admin upload response still includes error field for operational needs."""
    from app.config.settings import get_settings
    from app.infra.security.jwt_handler import JWTHandler

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        # Get admin token
        settings = get_settings()
        jwt_handler = JWTHandler(
            secret=settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
            expire_minutes=settings.JWT_EXPIRE_MINUTES,
        )
        admin_token = jwt_handler.create_token(TEST_ADMIN_ID)

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

        # Admin upload response should still have error field (nullable)
        assert "error" in data
        assert data["error"] is None  # No error on successful upload
    finally:
        app.dependency_overrides = {}
