import pytest
import tempfile
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.infra.postgres.database import get_session_maker, get_session
from app.infra.postgres.models import Base, Document, IngestionJob, User
from app.api.documents import get_db_session as original_get_db_session
from app.application.document_service import MOCK_USER_ID


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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

        existing_user = await session.execute(select(User).where(User.id == MOCK_USER_ID))
        if not existing_user.scalar_one_or_none():
            test_user = User(id=MOCK_USER_ID, email="test@example.com", password_hash="test_hash")
            session.add(test_user)
            await session.commit()

        yield session


@pytest.mark.asyncio
async def test_upload_document(db_session):
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
async def test_list_documents(db_session):
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
        assert isinstance(data["documents"], list)
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document(db_session):
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "test.pdf", 1024)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{doc.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc.id
        assert data["filename"] == "test.pdf"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document_not_found(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/nonexistent-id")

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document_status(db_session):
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "status-test.pdf", 2048)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/documents/{doc.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == doc.id
        assert data["status"] == "pending"
        assert data["chunk_count"] == 0
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_document_status_document_not_found(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/nonexistent-id/status")

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_document(db_session):
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "to-delete.pdf", 512)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/documents/{doc.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["document_id"] == doc.id
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_document_not_found(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/documents/nonexistent-id")

        assert response.status_code == 404
    finally:
        app.dependency_overrides = {}
