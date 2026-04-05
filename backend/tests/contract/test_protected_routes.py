import pytest
from httpx import AsyncClient, ASGITransport

from app.api.deps import get_db_session as original_get_db_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base
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
async def test_protected_route_without_token(db_session):
    """Test that protected routes return 401 when no token is provided."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/chat/sessions")

        assert response.status_code == 401
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(db_session):
    """Test that protected routes return 401 when an invalid token is provided."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/chat/sessions",
                headers={"Authorization": "Bearer invalid-token"},
            )

        assert response.status_code == 401
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(db_session):
    """Test that protected routes return 200 when a valid token is provided."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a user
            await client.post(
                "/api/v1/auth/register",
                json={"email": "protected@example.com", "password": "Protected123"},
            )

            # Login to get a token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "protected@example.com", "password": "Protected123"},
            )
            token = login_response.json()["access_token"]

            # Access protected route with token
            response = await client.get(
                "/api/v1/chat/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
    finally:
        app.dependency_overrides = {}
