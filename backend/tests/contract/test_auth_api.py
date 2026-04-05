import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.api.deps import get_db_session as original_get_db_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, User
from app.main import app

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

        yield session


@pytest.mark.asyncio
async def test_register_endpoint(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "password123",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == "test@example.com"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_login_endpoint(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "login@example.com",
                    "password": "password123",
                },
            )

            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "login@example.com",
                    "password": "password123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "wrong@example.com",
                    "password": "password123",
                },
            )

            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "wrong@example.com",
                    "password": "wrongpassword",
                },
            )

        assert response.status_code == 401
    finally:
        app.dependency_overrides = {}
