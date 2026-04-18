"""Contract tests for api/exhibits.py — public (unauthenticated) endpoints."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.api.deps import get_db_session
from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location
from app.main import app
from fastapi.testclient import TestClient

VALID_UUID = "00000000-0000-0000-0000-000000000001"


def _make_exhibit(id_: str = VALID_UUID, name: str = "青铜鼎") -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId(id_),
        name=name,
        description="desc",
        location=Location(x=1.0, y=2.0, floor=1),
        hall="main",
        category="bronze",
        era="shang",
        importance=3,
        estimated_visit_time=10,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def patch_exhibit_service(monkeypatch):
    mock = AsyncMock()
    mock.list_exhibits = AsyncMock(return_value=[_make_exhibit()])
    mock.list_all_active = AsyncMock(return_value=[_make_exhibit()])
    mock.search_exhibits = AsyncMock(return_value=[_make_exhibit()])
    mock.get_exhibit = AsyncMock(return_value=_make_exhibit())
    mock.get_all_categories = AsyncMock(return_value=["bronze", "jade"])
    mock.get_all_halls = AsyncMock(return_value=["east", "main"])

    def fake_factory(session):
        return mock

    monkeypatch.setattr("app.api.exhibits.get_exhibit_service", fake_factory)
    return mock


@pytest.fixture
def override_db():
    mock_session = AsyncMock()
    mock_session.add = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    async def _get_mock_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_mock_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


def test_list_exhibits_returns_200_with_pagination(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits?skip=0&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert "exhibits" in body
    assert "total" in body
    assert body["skip"] == 0
    assert body["limit"] == 10


def test_list_exhibits_applies_filter_query_params(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get(
        "/api/v1/exhibits?category=bronze&hall=east&floor=1"
    )

    assert response.status_code == 200
    call = patch_exhibit_service.list_exhibits.call_args
    assert call.kwargs.get("category") == "bronze"
    assert call.kwargs.get("hall") == "east"
    assert call.kwargs.get("floor") == 1


def test_get_exhibit_detail_returns_200(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get(f"/api/v1/exhibits/{VALID_UUID}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == VALID_UUID
    assert body["name"] == "青铜鼎"


def test_get_exhibit_detail_returns_404_when_missing(override_db, patch_exhibit_service):
    patch_exhibit_service.get_exhibit.return_value = None

    client = TestClient(app)
    response = client.get(f"/api/v1/exhibits/{VALID_UUID}")
    assert response.status_code == 404


def test_get_categories_list_returns_distinct_categories(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/categories/list")
    assert response.status_code == 200
    assert response.json() == ["bronze", "jade"]


def test_get_halls_list_returns_distinct_halls(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/halls/list")
    assert response.status_code == 200
    assert response.json() == ["east", "main"]


def test_get_exhibits_stats_returns_200(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/stats")
    assert response.status_code == 200
    body = response.json()
    assert "total_exhibits" in body
    assert "categories" in body
    assert "halls" in body
