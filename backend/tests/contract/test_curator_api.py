"""Contract tests for Curator API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.deps import check_rate_limit, get_db_session as original_get_db_session
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


@pytest.fixture
async def auth_token(db_session):
    """Create a user and return an auth token."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a user
            await client.post(
                "/api/v1/auth/register",
                json={"email": "curator_test@example.com", "password": "TestPass123"},
            )

            # Login to get token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "curator_test@example.com", "password": "TestPass123"},
            )
            token = login_response.json()["access_token"]
            return token
    finally:
        app.dependency_overrides = {}


@pytest.fixture
async def admin_auth_token(db_session):
    """Create an admin user and return an auth token."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a user first
            await client.post(
                "/api/v1/auth/register",
                json={"email": "admin_curator@example.com", "password": "AdminPass123"},
            )

            # Login to get token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "admin_curator@example.com", "password": "AdminPass123"},
            )
            token = login_response.json()["access_token"]

            # Update user role to admin directly in database
            from app.infra.postgres.models import User
            from sqlalchemy import select

            result = await db_session.execute(
                select(User).where(User.email == "admin_curator@example.com")
            )
            user = result.scalar_one()
            user.role = "admin"
            await db_session.commit()

            return token
    finally:
        app.dependency_overrides = {}


@pytest.fixture
async def exhibit_id(db_session, admin_auth_token):
    """Create an exhibit and return its ID."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_auth_token}"},
                json={
                    "name": "Test Exhibit",
                    "description": "A test exhibit for curator API tests",
                    "location_x": 10.0,
                    "location_y": 20.0,
                    "floor": 1,
                    "hall": "Main Hall",
                    "category": "Test",
                    "era": "Modern",
                    "importance": 5,
                    "estimated_visit_time": 15,
                    "document_id": "doc-123",
                },
            )
            return response.json()["id"]
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_plan_tour_endpoint(db_session, auth_token):
    """Test POST /api/v1/curator/plan-tour endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    # Mock the CuratorAgent to avoid LLM calls
    mock_result = {
        "output": "Here's your personalized tour plan: Start at the entrance...",
        "session_id": "test-session-123",
    }

    with patch(
        "app.api.curator.CuratorAgent",
        return_value=MagicMock(run=AsyncMock(return_value=mock_result)),
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/curator/plan-tour",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={
                        "available_time": 120,
                        "interests": ["art", "history"],
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "user_id" in data
            assert "available_time" in data
            assert data["available_time"] == 120
            assert "interests" in data
            assert "plan" in data
            assert "session_id" in data
        finally:
            app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_plan_tour_without_interests(db_session, auth_token):
    """Test POST /api/v1/curator/plan-tour without providing interests."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    mock_result = {
        "output": "Tour plan based on your profile...",
        "session_id": "test-session-456",
    }

    with patch(
        "app.api.curator.CuratorAgent",
        return_value=MagicMock(run=AsyncMock(return_value=mock_result)),
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/curator/plan-tour",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={"available_time": 60},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["available_time"] == 60
            assert "interests" in data
            assert "plan" in data
        finally:
            app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_narrative_endpoint(db_session, auth_token, exhibit_id):
    """Test POST /api/v1/curator/narrative endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    mock_result = {
        "output": "This magnificent exhibit showcases...",
        "session_id": "test-session-789",
    }

    with patch(
        "app.api.curator.CuratorAgent",
        return_value=MagicMock(run=AsyncMock(return_value=mock_result)),
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/curator/narrative",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={"exhibit_id": exhibit_id},
                )

            assert response.status_code == 200
            data = response.json()
            assert "user_id" in data
            assert "exhibit_id" in data
            assert data["exhibit_id"] == exhibit_id
            assert "exhibit_name" in data
            assert "narrative" in data
            assert "knowledge_level" in data
            assert "narrative_preference" in data
            assert "session_id" in data
        finally:
            app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_narrative_endpoint_not_found(db_session, auth_token):
    """Test POST /api/v1/curator/narrative with non-existent exhibit."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/curator/narrative",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"exhibit_id": "non-existent-id"},
            )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_reflection_endpoint(db_session, auth_token, exhibit_id):
    """Test POST /api/v1/curator/reflection endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    mock_result = {
        "output": "1. What emotions does this exhibit evoke in you?\n2. How does this relate to your own experiences?",
        "session_id": "test-session-abc",
    }

    with patch(
        "app.api.curator.CuratorAgent",
        return_value=MagicMock(run=AsyncMock(return_value=mock_result)),
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/curator/reflection",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={"exhibit_id": exhibit_id},
                )

            assert response.status_code == 200
            data = response.json()
            assert "user_id" in data
            assert "exhibit_id" in data
            assert data["exhibit_id"] == exhibit_id
            assert "exhibit_name" in data
            assert "reflection_prompts" in data
            assert "knowledge_level" in data
            assert "reflection_depth" in data
            assert "session_id" in data
        finally:
            app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_reflection_endpoint_not_found(db_session, auth_token):
    """Test POST /api/v1/curator/reflection with non-existent exhibit."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/curator/reflection",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"exhibit_id": "non-existent-id"},
            )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_profile_endpoint(db_session, auth_token):
    """Test GET /api/v1/profile endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "user_id" in data
        assert "interests" in data
        assert "knowledge_level" in data
        assert "narrative_preference" in data
        assert "reflection_depth" in data
        assert "visited_exhibit_ids" in data
        assert "feedback_history" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Verify default values
        assert data["knowledge_level"] == "beginner"
        assert data["narrative_preference"] == "balanced"
        assert data["reflection_depth"] == "2"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_update_profile_endpoint(db_session, auth_token):
    """Test PUT /api/v1/profile endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First get/create the profile
            await client.get(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            # Then update it
            response = await client.put(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "interests": ["art", "history", "science"],
                    "knowledge_level": "intermediate",
                    "narrative_preference": "detailed",
                    "reflection_depth": "3",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["interests"] == ["art", "history", "science"]
        assert data["knowledge_level"] == "intermediate"
        assert data["narrative_preference"] == "detailed"
        assert data["reflection_depth"] == "3"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_update_profile_partial(db_session, auth_token):
    """Test PUT /api/v1/profile with partial update."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First get/create the profile
            await client.get(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            # First update all fields
            await client.put(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "interests": ["art"],
                    "knowledge_level": "expert",
                    "narrative_preference": "concise",
                    "reflection_depth": "4",
                },
            )

            # Then update only interests
            response = await client.put(
                "/api/v1/profile",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"interests": ["history", "technology"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["interests"] == ["history", "technology"]
        # Other fields should remain unchanged
        assert data["knowledge_level"] == "expert"
        assert data["narrative_preference"] == "concise"
        assert data["reflection_depth"] == "4"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_curator_endpoints_require_auth(db_session):
    """Test that curator endpoints require authentication."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test plan-tour without auth - should return 401 (Unauthorized)
            response = await client.post(
                "/api/v1/curator/plan-tour",
                json={"available_time": 60},
            )
            assert response.status_code == 401

            # Test narrative without auth - should return 401 (Unauthorized)
            response = await client.post(
                "/api/v1/curator/narrative",
                json={"exhibit_id": "some-id"},
            )
            assert response.status_code == 401

            # Test reflection without auth - should return 401 (Unauthorized)
            response = await client.post(
                "/api/v1/curator/reflection",
                json={"exhibit_id": "some-id"},
            )
            assert response.status_code == 401

            # Test profile without auth - should return 401 (Unauthorized)
            response = await client.get("/api/v1/profile")
            assert response.status_code == 401
    finally:
        app.dependency_overrides = {}
