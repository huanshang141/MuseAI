import pytest
from app.api.deps import check_auth_rate_limit
from app.api.deps import get_db_session as original_get_db_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base
from app.main import app
from httpx import ASGITransport, AsyncClient

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
    # Override auth rate limit to allow tests to run without Redis
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "Password123!",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == "test@example.com"
        assert "role" in data
        assert data["role"] == "user"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_login_endpoint(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    # Override auth rate limit to allow tests to run without Redis
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "login@example.com",
                    "password": "LoginPass123!",
                },
            )

            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "login@example.com",
                    "password": "LoginPass123!",
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
    # Override auth rate limit to allow tests to run without Redis
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "wrong@example.com",
                    "password": "WrongPass123!",
                },
            )

            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "wrong@example.com",
                    "password": "Wrongpassword1!",
                },
            )

        assert response.status_code == 401
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_login_sets_http_only_cookie(db_session):
    """Test that login sets an HttpOnly cookie for the access token."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a user first
            await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "cookie@example.com",
                    "password": "CookiePass123!",
                },
            )

            # Login and check for HttpOnly cookie
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "cookie@example.com",
                    "password": "CookiePass123!",
                },
            )

        assert response.status_code == 200
        cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in cookie
        assert "HttpOnly" in cookie
    finally:
        app.dependency_overrides = {}
