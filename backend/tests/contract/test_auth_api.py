import pytest
from app.api.deps import check_auth_rate_limit
from app.api.deps import get_db_session as original_get_db_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, User
from app.infra.security.password import hash_password
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def session_maker():
    return get_session_maker(TEST_DATABASE_URL)


@pytest.fixture
async def db_session(session_maker):
    async with get_session(session_maker) as session:
        engine = session_maker.kw.get("bind")
        if engine:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        await session.execute(delete(User))
        await session.commit()
        yield session


def _override_auth_dependencies(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None


async def _add_user(db_session, *, user_id, email, password, role):
    db_session.add(
        User(
            id=user_id,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_public_registration_route_does_not_exist(db_session):
    _override_auth_dependencies(db_session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "visitor@example.com", "password": "VisitorPass123!"},
            )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 404
    assert not any(
        getattr(route, "path", None) == "/api/v1/auth/register"
        for route in app.routes
    )


@pytest.mark.asyncio
async def test_non_admin_cannot_login(db_session):
    await _add_user(
        db_session,
        user_id="visitor-login-denied",
        email="visitor-login-denied@example.com",
        password="VisitorPass123!",
        role="user",
    )
    _override_auth_dependencies(db_session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "visitor-login-denied@example.com", "password": "VisitorPass123!"},
            )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_admin_can_login_with_bearer_token_and_no_cookie(db_session):
    await _add_user(
        db_session,
        user_id="single-admin-login",
        email="single-admin@example.com",
        password="AdminPass123!",
        role="admin",
    )
    _override_auth_dependencies(db_session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "single-admin@example.com", "password": "AdminPass123!"},
            )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert "access_token=" not in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_admin_wrong_password_is_rejected(db_session):
    await _add_user(
        db_session,
        user_id="admin-wrong-password",
        email="admin-wrong-password@example.com",
        password="AdminPass123!",
        role="admin",
    )
    _override_auth_dependencies(db_session)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "admin-wrong-password@example.com", "password": "WrongPass123!"},
            )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 401
