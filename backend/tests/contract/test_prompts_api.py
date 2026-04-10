"""Contract tests for prompt management API."""

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


@pytest.fixture
async def admin_token(db_session):
    """Create an admin user and return an auth token."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a user
            await client.post(
                "/api/v1/auth/register",
                json={"email": "admin_prompts@example.com", "password": "AdminPass123!"},
            )

            # Login to get token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "admin_prompts@example.com", "password": "AdminPass123!"},
            )
            token = login_response.json()["access_token"]

            # Update user role to admin directly in database
            from app.infra.postgres.models import User
            from sqlalchemy import select

            result = await db_session.execute(
                select(User).where(User.email == "admin_prompts@example.com")
            )
            user = result.scalar_one()
            user.role = "admin"
            await db_session.commit()

            return token
    finally:
        app.dependency_overrides = {}


@pytest.fixture
async def user_token(db_session):
    """Create a regular user and return an auth token."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a user
            await client.post(
                "/api/v1/auth/register",
                json={"email": "user_prompts@example.com", "password": "UserPass123!"},
            )

            # Login to get token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "user_prompts@example.com", "password": "UserPass123!"},
            )
            return login_response.json()["access_token"]
    finally:
        app.dependency_overrides = {}


@pytest.fixture
def mock_prompt_cache():
    """Create mock prompt cache for tests."""
    from unittest.mock import AsyncMock, MagicMock

    from app.main import app as fastapi_app

    cache = MagicMock()
    cache.get = AsyncMock()
    cache.refresh = MagicMock()
    cache.get_all_keys = MagicMock(return_value=["test_prompt"])
    cache.set_repository = MagicMock()
    cache.load_all = AsyncMock()

    # Set the mock cache on app.state
    fastapi_app.state.prompt_cache = cache

    yield cache

    # Clean up
    if hasattr(fastapi_app.state, "prompt_cache"):
        delattr(fastapi_app.state, "prompt_cache")


@pytest.fixture
async def created_prompt_id(db_session, admin_token, mock_prompt_cache):
    """Create a prompt and return its ID."""
    import uuid
    from datetime import UTC, datetime

    from app.infra.postgres.models import Prompt, PromptVersion

    prompt_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    # Create prompt in database
    prompt = Prompt(
        id=prompt_id,
        key="test_prompt_for_api",
        name="Test Prompt for API",
        description="A test prompt for API tests",
        category="test",
        content="Test content {variable}",
        variables=[{"name": "variable", "description": "A test variable"}],
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(prompt)

    # Create initial version
    version = PromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt_id,
        version=1,
        content="Test content {variable}",
        changed_by="admin_prompts@example.com",
        change_reason="Initial version",
        created_at=now,
    )
    db_session.add(version)
    await db_session.commit()

    return prompt_id


class TestListPrompts:
    """Tests for GET /admin/prompts endpoint."""

    @pytest.mark.asyncio
    async def test_list_prompts_unauthorized(self, db_session):
        """Test listing prompts without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/prompts")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_prompts_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test listing prompts as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_prompts_success(self, db_session, admin_token, mock_prompt_cache):
        """Test listing prompts as admin returns success."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert "prompts" in data
                assert "total" in data
                assert isinstance(data["prompts"], list)
        finally:
            app.dependency_overrides = {}


class TestGetPrompt:
    """Tests for GET /admin/prompts/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_get_prompt_unauthorized(self, db_session):
        """Test getting prompt without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/prompts/test_prompt")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_prompt_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test getting prompt as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/test_prompt",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(self, db_session, admin_token, mock_prompt_cache):
        """Test getting non-existent prompt returns 404."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/nonexistent_prompt",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_prompt_success(self, db_session, admin_token, mock_prompt_cache, created_prompt_id):
        """Test getting existing prompt returns correct data."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/test_prompt_for_api",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["key"] == "test_prompt_for_api"
                assert data["name"] == "Test Prompt for API"
                assert "content" in data
                assert "variables" in data
        finally:
            app.dependency_overrides = {}


class TestUpdatePrompt:
    """Tests for PUT /admin/prompts/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_update_prompt_unauthorized(self, db_session):
        """Test updating prompt without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/admin/prompts/test_prompt",
                    json={"content": "New content"}
                )
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_update_prompt_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test updating prompt as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/admin/prompts/test_prompt",
                    json={"content": "New content"},
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_update_prompt_not_found(self, db_session, admin_token, mock_prompt_cache):
        """Test updating non-existent prompt returns 404."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/admin/prompts/nonexistent_prompt",
                    json={"content": "New content"},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_update_prompt_success(self, db_session, admin_token, mock_prompt_cache, created_prompt_id):
        """Test updating existing prompt returns updated data."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/admin/prompts/test_prompt_for_api",
                    json={"content": "Updated content {variable}", "change_reason": "Test update"},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["content"] == "Updated content {variable}"
                assert data["key"] == "test_prompt_for_api"
                assert "current_version" in data
                # Verify cache refresh was called
                mock_prompt_cache.refresh.assert_called_once()
        finally:
            app.dependency_overrides = {}


class TestListVersions:
    """Tests for GET /admin/prompts/{key}/versions endpoint."""

    @pytest.mark.asyncio
    async def test_list_versions_unauthorized(self, db_session):
        """Test listing versions without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/prompts/test_prompt/versions")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_versions_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test listing versions as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/test_prompt/versions",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_list_versions_success(self, db_session, admin_token, mock_prompt_cache, created_prompt_id):
        """Test listing versions returns version history."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/test_prompt_for_api/versions",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert "versions" in data
                assert "total" in data
                assert len(data["versions"]) >= 1
                version = data["versions"][0]
                assert "version" in version
                assert "content" in version
                assert "created_at" in version
        finally:
            app.dependency_overrides = {}


class TestGetVersion:
    """Tests for GET /admin/prompts/{key}/versions/{version} endpoint."""

    @pytest.mark.asyncio
    async def test_get_version_unauthorized(self, db_session):
        """Test getting version without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/prompts/test_prompt/versions/1")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_version_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test getting version as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/test_prompt/versions/1",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, db_session, admin_token, mock_prompt_cache):
        """Test getting non-existent version returns 404."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/nonexistent_prompt/versions/1",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_get_version_success(self, db_session, admin_token, mock_prompt_cache, created_prompt_id):
        """Test getting specific version returns version data."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/admin/prompts/test_prompt_for_api/versions/1",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["version"] == 1
                assert "content" in data
                assert "prompt_id" in data
        finally:
            app.dependency_overrides = {}


class TestRollbackVersion:
    """Tests for POST /admin/prompts/{key}/versions/{version}/rollback endpoint."""

    @pytest.mark.asyncio
    async def test_rollback_unauthorized(self, db_session):
        """Test rollback without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/admin/prompts/test_prompt/versions/1/rollback")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_rollback_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test rollback as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/test_prompt/versions/1/rollback",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_rollback_not_found(self, db_session, admin_token, mock_prompt_cache):
        """Test rollback non-existent prompt returns 404."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/nonexistent_prompt/versions/1/rollback",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_rollback_success(self, db_session, admin_token, mock_prompt_cache, created_prompt_id):
        """Test rollback creates new version with old content."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # First update the prompt to create version 2
                await client.put(
                    "/api/v1/admin/prompts/test_prompt_for_api",
                    json={"content": "Version 2 content"},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )

                # Reset mock
                mock_prompt_cache.reset_mock()

                # Rollback to version 1
                response = await client.post(
                    "/api/v1/admin/prompts/test_prompt_for_api/versions/1/rollback",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                # Verify rollback returns the original content
                assert data["content"] == "Test content {variable}"
                assert "current_version" in data
                # Cache should be refreshed
                mock_prompt_cache.refresh.assert_called_once()
        finally:
            app.dependency_overrides = {}


class TestReloadPrompt:
    """Tests for POST /admin/prompts/{key}/reload endpoint."""

    @pytest.mark.asyncio
    async def test_reload_prompt_unauthorized(self, db_session):
        """Test reloading prompt without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/admin/prompts/test_prompt/reload")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_reload_prompt_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test reloading prompt as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/test_prompt/reload",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_reload_prompt_not_found(self, db_session, admin_token, mock_prompt_cache):
        """Test reloading non-existent prompt returns 404."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/nonexistent_prompt/reload",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 404
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_reload_prompt_success(self, db_session, admin_token, mock_prompt_cache, created_prompt_id):
        """Test reloading existing prompt returns success."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/test_prompt_for_api/reload",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "reloaded" in data["message"].lower()
                # Verify cache refresh was called
                mock_prompt_cache.refresh.assert_called_once()
        finally:
            app.dependency_overrides = {}


class TestReloadAllPrompts:
    """Tests for POST /admin/prompts/reload-all endpoint."""

    @pytest.mark.asyncio
    async def test_reload_all_unauthorized(self, db_session):
        """Test reloading all prompts without auth returns 401."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/admin/prompts/reload-all")
                assert response.status_code == 401
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_reload_all_forbidden_for_non_admin(self, db_session, user_token, mock_prompt_cache):
        """Test reloading all prompts as non-admin returns 403."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/reload-all",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                assert response.status_code == 403
        finally:
            app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_reload_all_success(self, db_session, admin_token, mock_prompt_cache):
        """Test reloading all prompts returns success."""
        async def override_get_db():
            yield db_session

        app.dependency_overrides[original_get_db_session] = override_get_db
        app.dependency_overrides[check_auth_rate_limit] = lambda: None

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/prompts/reload-all",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "reloaded" in data["message"].lower()
                # Verify load_all was called
                mock_prompt_cache.load_all.assert_called_once()
        finally:
            app.dependency_overrides = {}
