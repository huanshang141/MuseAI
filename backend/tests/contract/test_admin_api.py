"""Contract tests for Admin API endpoints."""

import pytest
from app.api.deps import check_auth_rate_limit, get_db_session as original_get_db_session
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
                json={"email": "admin_test@example.com", "password": "AdminPass123"},
            )

            # Login to get token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "admin_test@example.com", "password": "AdminPass123"},
            )
            token = login_response.json()["access_token"]

            # Update user role to admin directly in database
            from app.infra.postgres.models import User
            from sqlalchemy import select

            result = await db_session.execute(
                select(User).where(User.email == "admin_test@example.com")
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
                json={"email": "user_test@example.com", "password": "UserPass123"},
            )

            # Login to get token
            login_response = await client.post(
                "/api/v1/auth/login",
                json={"email": "user_test@example.com", "password": "UserPass123"},
            )
            return login_response.json()["access_token"]
    finally:
        app.dependency_overrides = {}


@pytest.fixture
async def created_exhibit_id(db_session, admin_token):
    """Create an exhibit and return its ID."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Ancient Pottery",
                    "description": "A collection of ancient pottery from various civilizations",
                    "location_x": 15.5,
                    "location_y": 25.0,
                    "floor": 2,
                    "hall": "Hall A",
                    "category": "Archaeology",
                    "era": "Ancient",
                    "importance": 8,
                    "estimated_visit_time": 20,
                    "document_id": "doc-pottery-001",
                },
            )
            return response.json()["id"]
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_exhibit_endpoint(db_session, admin_token):
    """Test POST /api/v1/admin/exhibits endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Renaissance Paintings",
                    "description": "Masterpieces from the Renaissance period",
                    "location_x": 30.0,
                    "location_y": 40.0,
                    "floor": 1,
                    "hall": "Hall B",
                    "category": "Painting",
                    "era": "Renaissance",
                    "importance": 9,
                    "estimated_visit_time": 30,
                    "document_id": "doc-paintings-001",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Renaissance Paintings"
        assert data["description"] == "Masterpieces from the Renaissance period"
        assert data["location_x"] == 30.0
        assert data["location_y"] == 40.0
        assert data["floor"] == 1
        assert data["hall"] == "Hall B"
        assert data["category"] == "Painting"
        assert data["era"] == "Renaissance"
        assert data["importance"] == 9
        assert data["estimated_visit_time"] == 30
        assert data["document_id"] == "doc-paintings-001"
        assert data["is_active"] is True
        assert "created_at" in data
        assert "updated_at" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_exhibit_default_floor(db_session, admin_token):
    """Test POST /api/v1/admin/exhibits with default floor value."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Modern Sculpture",
                    "description": "Contemporary sculptures",
                    "location_x": 5.0,
                    "location_y": 10.0,
                    "hall": "Hall C",
                    "category": "Sculpture",
                    "era": "Modern",
                    "importance": 7,
                    "estimated_visit_time": 15,
                    "document_id": "doc-sculpture-001",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["floor"] == 1  # Default value
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_list_exhibits_endpoint(db_session, admin_token, created_exhibit_id):
    """Test GET /api/v1/admin/exhibits endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "exhibits" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert isinstance(data["exhibits"], list)
        assert len(data["exhibits"]) >= 1

        # Check exhibit structure
        exhibit = data["exhibits"][0]
        assert "id" in exhibit
        assert "name" in exhibit
        assert "description" in exhibit
        assert "location_x" in exhibit
        assert "location_y" in exhibit
        assert "floor" in exhibit
        assert "hall" in exhibit
        assert "category" in exhibit
        assert "era" in exhibit
        assert "importance" in exhibit
        assert "estimated_visit_time" in exhibit
        assert "document_id" in exhibit
        assert "is_active" in exhibit
        assert "created_at" in exhibit
        assert "updated_at" in exhibit
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_list_exhibits_with_pagination(db_session, admin_token):
    """Test GET /api/v1/admin/exhibits with pagination parameters."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create multiple exhibits
            for i in range(3):
                await client.post(
                    "/api/v1/admin/exhibits",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={
                        "name": f"Test Exhibit {i}",
                        "description": f"Description {i}",
                        "location_x": float(i * 10),
                        "location_y": float(i * 10),
                        "hall": f"Hall {i}",
                        "category": "Test",
                        "era": "Modern",
                        "importance": 5,
                        "estimated_visit_time": 10,
                        "document_id": f"doc-{i}",
                    },
                )

            # Test with limit
            response = await client.get(
                "/api/v1/admin/exhibits?limit=2",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 2
            assert len(data["exhibits"]) <= 2

            # Test with skip
            response = await client.get(
                "/api/v1/admin/exhibits?skip=1&limit=1",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["skip"] == 1
            assert data["limit"] == 1
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_list_exhibits_with_category_filter(db_session, admin_token):
    """Test GET /api/v1/admin/exhibits with category filter."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create exhibits with different categories
            await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Painting 1",
                    "description": "A painting",
                    "location_x": 1.0,
                    "location_y": 1.0,
                    "hall": "Hall 1",
                    "category": "Painting",
                    "era": "Modern",
                    "importance": 5,
                    "estimated_visit_time": 10,
                    "document_id": "doc-painting",
                },
            )

            await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Sculpture 1",
                    "description": "A sculpture",
                    "location_x": 2.0,
                    "location_y": 2.0,
                    "hall": "Hall 2",
                    "category": "Sculpture",
                    "era": "Ancient",
                    "importance": 6,
                    "estimated_visit_time": 15,
                    "document_id": "doc-sculpture",
                },
            )

            # Filter by category
            response = await client.get(
                "/api/v1/admin/exhibits?category=Painting",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert all(e["category"] == "Painting" for e in data["exhibits"])
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_list_exhibits_with_hall_filter(db_session, admin_token):
    """Test GET /api/v1/admin/exhibits with hall filter."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create exhibits with different halls
            await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Exhibit in Main Hall",
                    "description": "An exhibit",
                    "location_x": 1.0,
                    "location_y": 1.0,
                    "hall": "Main Hall",
                    "category": "General",
                    "era": "Modern",
                    "importance": 5,
                    "estimated_visit_time": 10,
                    "document_id": "doc-main",
                },
            )

            await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Exhibit in Side Hall",
                    "description": "Another exhibit",
                    "location_x": 2.0,
                    "location_y": 2.0,
                    "hall": "Side Hall",
                    "category": "General",
                    "era": "Modern",
                    "importance": 5,
                    "estimated_visit_time": 10,
                    "document_id": "doc-side",
                },
            )

            # Filter by hall
            response = await client.get(
                "/api/v1/admin/exhibits?hall=Main%20Hall",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert all(e["hall"] == "Main Hall" for e in data["exhibits"])
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_exhibit_endpoint(db_session, admin_token):
    """Test DELETE /api/v1/admin/exhibits/{id} endpoint."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create an exhibit to delete
            create_response = await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "Exhibit to Delete",
                    "description": "This exhibit will be deleted",
                    "location_x": 99.0,
                    "location_y": 99.0,
                    "hall": "Temp Hall",
                    "category": "Temp",
                    "era": "Modern",
                    "importance": 1,
                    "estimated_visit_time": 5,
                    "document_id": "doc-temp",
                },
            )
            exhibit_id = create_response.json()["id"]

            # Delete the exhibit
            delete_response = await client.delete(
                f"/api/v1/admin/exhibits/{exhibit_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            assert delete_response.status_code == 200
            delete_data = delete_response.json()
            assert delete_data["status"] == "deleted"
            assert delete_data["exhibit_id"] == exhibit_id

            # Verify it's gone by listing exhibits
            list_response = await client.get(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            list_data = list_response.json()
            exhibit_ids = [e["id"] for e in list_data["exhibits"]]
            assert exhibit_id not in exhibit_ids
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_exhibit_not_found(db_session, admin_token):
    """Test DELETE /api/v1/admin/exhibits/{id} with non-existent exhibit."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/admin/exhibits/non-existent-id",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin_role(db_session, user_token):
    """Test that admin endpoints require admin role."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test create exhibit with regular user token
            response = await client.post(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "name": "Test Exhibit",
                    "description": "Test",
                    "location_x": 1.0,
                    "location_y": 1.0,
                    "hall": "Test Hall",
                    "category": "Test",
                    "era": "Modern",
                    "importance": 5,
                    "estimated_visit_time": 10,
                    "document_id": "doc-test",
                },
            )
            assert response.status_code == 403

            # Test list exhibits with regular user token
            response = await client.get(
                "/api/v1/admin/exhibits",
                headers={"Authorization": f"Bearer {user_token}"},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_endpoints_require_auth(db_session):
    """Test that admin endpoints require authentication."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db
    app.dependency_overrides[check_auth_rate_limit] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test create exhibit without auth - should return 401 (Unauthorized)
            response = await client.post(
                "/api/v1/admin/exhibits",
                json={
                    "name": "Test Exhibit",
                    "description": "Test",
                    "location_x": 1.0,
                    "location_y": 1.0,
                    "hall": "Test Hall",
                    "category": "Test",
                    "era": "Modern",
                    "importance": 5,
                    "estimated_visit_time": 10,
                    "document_id": "doc-test",
                },
            )
            assert response.status_code == 401

            # Test list exhibits without auth - should return 401 (Unauthorized)
            response = await client.get("/api/v1/admin/exhibits")
            assert response.status_code == 401

            # Test delete exhibit without auth - should return 401 (Unauthorized)
            response = await client.delete("/api/v1/admin/exhibits/some-id")
            assert response.status_code == 401
    finally:
        app.dependency_overrides = {}
