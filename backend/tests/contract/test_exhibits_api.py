"""Contract tests for api/exhibits.py — public (unauthenticated) endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import get_db_session
from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location
from app.main import app
from fastapi.testclient import TestClient

VALID_UUID = "00000000-0000-0000-0000-000000000001"


def _make_exhibit(
    id_: str = VALID_UUID,
    name: str = "青铜鼎",
    hall: str = "basic-exhibition-hall",
    image_url: str | None = None,
    image_path: str | None = None,
) -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId(id_),
        name=name,
        description="desc",
        location=Location(x=1.0, y=2.0, floor=1),
        hall=hall,
        category="bronze",
        era="shang",
        importance=3,
        estimated_visit_time=10,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
        image_url=image_url,
        image_path=image_path,
    )


@pytest.fixture
def patch_exhibit_service(monkeypatch):
    mock = AsyncMock()
    mock.list_exhibits = AsyncMock(return_value=[_make_exhibit()])
    mock.list_all_active = AsyncMock(return_value=[_make_exhibit()])
    mock.search_exhibits = AsyncMock(return_value=[_make_exhibit()])
    mock.count_exhibits = AsyncMock(return_value=1)
    mock.count_search_exhibits = AsyncMock(return_value=1)
    mock.get_exhibit = AsyncMock(return_value=_make_exhibit())
    mock.get_all_categories = AsyncMock(return_value=["bronze", "jade"])
    mock.get_all_halls = AsyncMock(return_value=["basic-exhibition-hall", "site-protection-hall"])

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
    hall_result = MagicMock()
    hall_result.all.return_value = [("basic-exhibition-hall", "基本陈列展厅")]
    mock_session.execute.return_value = hall_result

    async def _get_mock_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_mock_session
    yield mock_session
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
    assert body["exhibits"][0]["hall_name"] == "基本陈列展厅"
    assert body["exhibits"][0]["image_url"] is None


def test_list_exhibits_resolves_real_hall_names_in_one_batch(
    override_db,
    patch_exhibit_service,
):
    patch_exhibit_service.list_exhibits.return_value = [
        _make_exhibit(hall="basic-exhibition-hall"),
        _make_exhibit(
            id_="00000000-0000-0000-0000-000000000002",
            hall="site-protection-hall",
        ),
    ]
    patch_exhibit_service.count_exhibits.return_value = 2
    override_db.execute.return_value.all.return_value = [
        ("basic-exhibition-hall", "基本陈列展厅"),
        ("site-protection-hall", "遗址保护大厅"),
    ]

    client = TestClient(app)
    response = client.get("/api/v1/exhibits?skip=0&limit=10")

    assert response.status_code == 200
    assert [item["hall_name"] for item in response.json()["exhibits"]] == [
        "基本陈列展厅",
        "遗址保护大厅",
    ]
    override_db.execute.assert_awaited_once()


def test_list_exhibits_keeps_real_records_with_legacy_placeholder_names(override_db, patch_exhibit_service):
    patch_exhibit_service.list_exhibits.return_value = [
        _make_exhibit(name="半坡人"),
        _make_exhibit(id_="00000000-0000-0000-0000-000000000002", name="尖底瓶"),
    ]
    patch_exhibit_service.count_exhibits.return_value = 2

    client = TestClient(app)
    response = client.get("/api/v1/exhibits?skip=0&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["exhibits"]] == ["半坡人", "尖底瓶"]
    assert body["total"] == 2


def test_list_exhibits_does_not_create_name_for_missing_hall(
    override_db,
    patch_exhibit_service,
):
    patch_exhibit_service.list_exhibits.return_value = [_make_exhibit(hall="legacy-hall")]
    patch_exhibit_service.count_exhibits.return_value = 0
    override_db.execute.return_value.all.return_value = []

    response = TestClient(app).get("/api/v1/exhibits?skip=0&limit=10")

    assert response.status_code == 200
    assert response.json()["exhibits"] == []
    assert response.json()["total"] == 0


def test_list_exhibits_applies_filter_query_params(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits?category=bronze&hall=site-protection-hall&floor=1")

    assert response.status_code == 200
    call = patch_exhibit_service.list_exhibits.call_args
    assert call.kwargs.get("category") == "bronze"
    assert call.kwargs.get("hall") == "site-protection-hall"
    assert call.kwargs.get("floor") == 1
    count_call = patch_exhibit_service.count_exhibits.call_args
    assert count_call.kwargs.get("category") == "bronze"
    assert count_call.kwargs.get("hall") == "site-protection-hall"
    assert count_call.kwargs.get("floor") == 1


def test_search_exhibits_uses_lightweight_count(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits?search=pottery&limit=10")

    assert response.status_code == 200
    patch_exhibit_service.search_exhibits.assert_called_once()
    patch_exhibit_service.count_search_exhibits.assert_called_once()
    assert patch_exhibit_service.count_search_exhibits.call_args.kwargs.get("query") == "pottery"
    assert response.json()["total"] == 1


def test_get_exhibit_detail_returns_200(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get(f"/api/v1/exhibits/{VALID_UUID}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == VALID_UUID
    assert body["name"] == "青铜鼎"
    assert body["hall_name"] == "基本陈列展厅"
    assert body["image_url"] is None


def test_exhibit_responses_use_https_external_url_or_uploaded_api_path(
    override_db,
    patch_exhibit_service,
):
    patch_exhibit_service.list_exhibits.return_value = [_make_exhibit(image_url="https://museum.example/pottery.png")]
    external = TestClient(app).get("/api/v1/exhibits")
    assert external.json()["exhibits"][0]["image_url"] == "https://museum.example/pottery.png"

    patch_exhibit_service.get_exhibit.return_value = _make_exhibit(
        image_url="https://museum.example/pottery.png",
        image_path=f"{VALID_UUID}/uploaded.png",
    )
    uploaded = TestClient(app).get(f"/api/v1/exhibits/{VALID_UUID}")
    assert uploaded.json()["image_url"] == f"/api/v1/exhibits/{VALID_UUID}/image"


def test_get_exhibit_detail_returns_404_when_missing(override_db, patch_exhibit_service):
    patch_exhibit_service.get_exhibit.return_value = None

    client = TestClient(app)
    response = client.get(f"/api/v1/exhibits/{VALID_UUID}")
    assert response.status_code == 404


def test_get_exhibit_detail_returns_404_when_hall_is_not_visible(
    override_db,
    patch_exhibit_service,
):
    override_db.execute.return_value.all.return_value = []

    response = TestClient(app).get(f"/api/v1/exhibits/{VALID_UUID}")

    assert response.status_code == 404


def test_get_exhibit_detail_keeps_real_record_with_legacy_placeholder_name(override_db, patch_exhibit_service):
    patch_exhibit_service.get_exhibit.return_value = _make_exhibit(name="半坡人")

    client = TestClient(app)
    response = client.get(f"/api/v1/exhibits/{VALID_UUID}")
    assert response.status_code == 200
    assert response.json()["name"] == "半坡人"


def test_get_categories_list_returns_distinct_categories(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/categories/list")
    assert response.status_code == 200
    assert response.json() == ["bronze", "jade"]


def test_get_halls_list_returns_distinct_halls(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/halls/list")
    assert response.status_code == 200
    assert response.json() == ["basic-exhibition-hall", "site-protection-hall"]


def test_get_exhibits_stats_returns_200(override_db, patch_exhibit_service):
    client = TestClient(app)
    response = client.get("/api/v1/exhibits/stats")
    assert response.status_code == 200
    body = response.json()
    assert "total_exhibits" in body
    assert "categories" in body
    assert "halls" in body
