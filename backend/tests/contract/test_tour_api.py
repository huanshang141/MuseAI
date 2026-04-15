from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import (
    get_db_session as original_get_db_session,
)
from app.api.deps import (
    get_llm_provider as original_get_llm_provider,
)
from app.api.deps import (
    get_rag_agent as original_get_rag_agent,
)
from app.api.deps import (
    get_redis_cache as original_get_redis_cache,
)
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, User
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = "test-tour-user-001"


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

        existing = await session.execute(select(User).where(User.id == TEST_USER_ID))
        if not existing.scalar_one_or_none():
            test_user = User(
                id=TEST_USER_ID,
                email="tour-test@example.com",
                password_hash="test_hash",
                role="user",
            )
            session.add(test_user)
            await session.commit()

        yield session


@pytest.fixture
async def auth_token(db_session):
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
def mock_redis():
    mock = AsyncMock()
    mock.check_rate_limit = AsyncMock(return_value=True)
    mock.is_token_blacklisted = AsyncMock(return_value=False)
    mock.get_guest_session = AsyncMock(return_value=None)
    mock.set_guest_session = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def override_dependencies(db_session, mock_redis):
    async def override_get_db():
        yield db_session

    def override_redis():
        return mock_redis

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[original_get_redis_cache] = override_redis

    yield

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_tour_session_guest(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-test-001",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "session_token" in data
    assert data["interest_type"] == "A"
    assert data["persona"] == "A"
    assert data["assumption"] == "A"
    assert data["status"] == "onboarding"
    assert data["current_hall"] is None
    assert data["visited_halls"] == []


@pytest.mark.asyncio
async def test_create_tour_session_authenticated(override_dependencies, auth_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tour/sessions",
            json={"interest_type": "B", "persona": "B", "assumption": "B"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["interest_type"] == "B"
    assert data["persona"] == "B"


@pytest.mark.asyncio
async def test_create_tour_session_returns_existing(override_dependencies, auth_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response1 = await client.post(
            "/api/v1/tour/sessions",
            json={"interest_type": "A", "persona": "A", "assumption": "A"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data1 = response1.json()

        response2 = await client.post(
            "/api/v1/tour/sessions",
            json={"interest_type": "C", "persona": "C", "assumption": "C"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data2 = response2.json()

    assert data1["id"] == data2["id"]
    assert data2["interest_type"] == "A"


@pytest.mark.asyncio
async def test_get_tour_session(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-get-test",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        get_resp = await client.get(
            f"/api/v1/tour/sessions/{session_id}",
            headers={"X-Session-Token": token},
        )

    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == session_id
    assert data["interest_type"] == "A"


@pytest.mark.asyncio
async def test_get_tour_session_not_found(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tour/sessions/nonexistent-id",
            headers={"X-Session-Token": "fake-token"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tour_session_no_auth(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tour/sessions/some-id",
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_tour_session_wrong_token(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-wrong-token",
            },
        )
        session_id = create_resp.json()["id"]

        get_resp = await client.get(
            f"/api/v1/tour/sessions/{session_id}",
            headers={"X-Session-Token": "wrong-token"},
        )

    assert get_resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_tour_session(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-patch-test",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        patch_resp = await client.patch(
            f"/api/v1/tour/sessions/{session_id}",
            json={"current_hall": "relic-hall", "status": "touring"},
            headers={"X-Session-Token": token},
        )

    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["current_hall"] == "relic-hall"
    assert data["status"] == "touring"


@pytest.mark.asyncio
async def test_patch_tour_session_not_found(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/tour/sessions/nonexistent-id",
            json={"status": "touring"},
            headers={"X-Session-Token": "fake-token"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_record_tour_events(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-events-test",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        events_resp = await client.post(
            f"/api/v1/tour/sessions/{session_id}/events",
            json={
                "events": [
                    {
                        "event_type": "exhibit_view",
                        "exhibit_id": "exhibit-1",
                        "hall": "relic-hall",
                        "duration_seconds": 120,
                    },
                    {
                        "event_type": "exhibit_question",
                        "exhibit_id": "exhibit-1",
                        "hall": "relic-hall",
                    },
                ]
            },
            headers={"X-Session-Token": token},
        )

    assert events_resp.status_code == 200
    data = events_resp.json()
    assert data["recorded"] == 2


@pytest.mark.asyncio
async def test_list_tour_events(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-list-events",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        await client.post(
            f"/api/v1/tour/sessions/{session_id}/events",
            json={
                "events": [
                    {
                        "event_type": "hall_enter",
                        "hall": "relic-hall",
                    },
                ]
            },
            headers={"X-Session-Token": token},
        )

        list_resp = await client.get(
            f"/api/v1/tour/sessions/{session_id}/events",
            headers={"X-Session-Token": token},
        )

    assert list_resp.status_code == 200
    data = list_resp.json()
    assert "events" in data
    assert len(data["events"]) == 1
    assert data["events"][0]["event_type"] == "hall_enter"
    assert data["events"][0]["hall"] == "relic-hall"


@pytest.mark.asyncio
async def test_complete_hall(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-complete-hall",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        await client.patch(
            f"/api/v1/tour/sessions/{session_id}",
            json={"current_hall": "relic-hall", "status": "touring"},
            headers={"X-Session-Token": token},
        )

        complete_resp = await client.post(
            f"/api/v1/tour/sessions/{session_id}/complete-hall",
            headers={"X-Session-Token": token},
        )

    assert complete_resp.status_code == 200
    data = complete_resp.json()
    assert "relic-hall" in data["visited_halls"]
    assert data["all_halls_visited"] is False
    assert data["status"] == "touring"


@pytest.mark.asyncio
async def test_complete_hall_all_visited(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-all-halls",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        await client.patch(
            f"/api/v1/tour/sessions/{session_id}",
            json={"current_hall": "relic-hall", "status": "touring"},
            headers={"X-Session-Token": token},
        )
        await client.post(
            f"/api/v1/tour/sessions/{session_id}/complete-hall",
            headers={"X-Session-Token": token},
        )

        await client.patch(
            f"/api/v1/tour/sessions/{session_id}",
            json={"current_hall": "site-hall"},
            headers={"X-Session-Token": token},
        )
        complete_resp = await client.post(
            f"/api/v1/tour/sessions/{session_id}/complete-hall",
            headers={"X-Session-Token": token},
        )

    assert complete_resp.status_code == 200
    data = complete_resp.json()
    assert data["all_halls_visited"] is True
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_tour_report(override_dependencies):
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="半坡一日游达成")

    app.dependency_overrides[original_get_llm_provider] = lambda: mock_llm

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-report-gen",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        await client.patch(
            f"/api/v1/tour/sessions/{session_id}",
            json={"current_hall": "relic-hall", "status": "touring"},
            headers={"X-Session-Token": token},
        )
        await client.post(
            f"/api/v1/tour/sessions/{session_id}/complete-hall",
            headers={"X-Session-Token": token},
        )
        await client.patch(
            f"/api/v1/tour/sessions/{session_id}",
            json={"current_hall": "site-hall"},
            headers={"X-Session-Token": token},
        )
        await client.post(
            f"/api/v1/tour/sessions/{session_id}/complete-hall",
            headers={"X-Session-Token": token},
        )

        report_resp = await client.post(
            f"/api/v1/tour/sessions/{session_id}/report",
            headers={"X-Session-Token": token},
        )

    app.dependency_overrides.pop(original_get_llm_provider, None)

    assert report_resp.status_code == 200
    data = report_resp.json()
    assert "id" in data
    assert data["tour_session_id"] == session_id
    assert "identity_tags" in data
    assert "radar_scores" in data
    assert "one_liner" in data
    assert data["report_theme"] == "archaeology"


@pytest.mark.asyncio
async def test_get_tour_report_not_found(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-report-notfound",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        get_resp = await client.get(
            f"/api/v1/tour/sessions/{session_id}/report",
            headers={"X-Session-Token": token},
        )

    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_list_tour_halls(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tour/halls")

    assert response.status_code == 200
    data = response.json()
    assert "halls" in data
    assert len(data["halls"]) == 2
    assert data["halls"][0]["slug"] == "relic-hall"
    assert data["halls"][1]["slug"] == "site-hall"


@pytest.mark.asyncio
async def test_tour_chat_stream(override_dependencies):
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "这是考古队长的回答",
        "documents": [],
        "retrieval_score": 0.8,
    })

    app.dependency_overrides[original_get_rag_agent] = lambda: mock_rag_agent

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/tour/sessions",
            json={
                "interest_type": "A",
                "persona": "A",
                "assumption": "A",
                "guest_id": "guest-chat-stream",
            },
        )
        created = create_resp.json()
        session_id = created["id"]
        token = created["session_token"]

        chat_resp = await client.post(
            f"/api/v1/tour/sessions/{session_id}/chat/stream",
            json={"message": "人面鱼纹盆是什么？"},
            headers={"X-Session-Token": token},
        )

    app.dependency_overrides.pop(original_get_rag_agent, None)

    assert chat_resp.status_code == 200
    assert chat_resp.headers["content-type"] == "text/event-stream; charset=utf-8"


@pytest.mark.asyncio
async def test_tour_chat_stream_no_auth(override_dependencies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tour/sessions/nonexistent/chat/stream",
            json={"message": "test"},
        )

    assert response.status_code == 403
