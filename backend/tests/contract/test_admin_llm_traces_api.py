# backend/tests/contract/test_admin_llm_traces_api.py
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import check_auth_rate_limit, get_db_session as original_get_db_session
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base
from app.infra.postgres.models.llm_trace import LLMTraceEvent
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


@pytest.fixture
async def admin_token(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/register",
                json={"email": "admin_llm@example.com", "password": "AdminPass123!"},
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "admin_llm@example.com", "password": "AdminPass123!"},
            )
            token = login_response.json()["access_token"]

            from app.infra.postgres.models import User
            from sqlalchemy import select

            result = await db_session.execute(select(User).where(User.email == "admin_llm@example.com"))
            user = result.scalar_one()
            user.role = "admin"
            await db_session.commit()

            return token
    finally:
        app.dependency_overrides = {}


@pytest.fixture
async def user_token(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/register",
                json={"email": "user_llm@example.com", "password": "UserPass123!"},
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "user_llm@example.com", "password": "UserPass123!"},
            )
            return login_response.json()["access_token"]
    finally:
        app.dependency_overrides = {}


@pytest.fixture
async def sample_event(db_session):
    event = LLMTraceEvent(
        id="evt-1",
        call_id="call-abc",
        request_id="req-1",
        trace_id="trace-1",
        source="chat_stream",
        provider="openai-compatible",
        model="gpt-4o-mini",
        status="success",
        started_at=datetime.now(UTC),
    )
    db_session.add(event)
    await db_session.commit()
    return event


class TestAdminLLMTracesAPI:
    @pytest.mark.asyncio
    async def test_list_unauthorized(self, db_session):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/llm-traces")
            assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_forbidden(self, db_session, user_token):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/llm-traces",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
            assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_admin_success(self, db_session, admin_token, sample_event):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/llm-traces",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["limit"] == 20
            assert data["offset"] == 0
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_filter_by_source(self, db_session, admin_token, sample_event):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/llm-traces?source=chat_stream",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
            assert response.status_code == 200
            data = response.json()
            assert all(i["source"] == "chat_stream" for i in data["items"])
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_detail_not_found(self, db_session, admin_token):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/llm-traces/nonexistent",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_detail_success(self, db_session, admin_token, sample_event):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/admin/llm-traces/{sample_event.call_id}",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["call_id"] == sample_event.call_id
            assert data["source"] == "chat_stream"
            assert data["model"] == "gpt-4o-mini"
        finally:
            app.dependency_overrides = {}
