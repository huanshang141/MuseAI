"""Contract tests for api/profile.py — GET and PUT endpoints."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.api.deps import check_rate_limit, get_current_user, get_db_session
from app.domain.entities import VisitorProfile
from app.domain.value_objects import ProfileId, UserId
from app.main import app
from fastapi.testclient import TestClient

TEST_USER = {"id": "u-contract-1", "email": "contract@test.local"}


def _override_user():
    return TEST_USER


def _noop_rate_limit():
    return None


def _make_profile() -> VisitorProfile:
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId("p-1"),
        user_id=UserId(TEST_USER["id"]),
        interests=["bronze"],
        knowledge_level="beginner",
        narrative_preference="balanced",
        reflection_depth="2",
        visited_exhibit_ids=[],
        feedback_history=[],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[check_rate_limit] = _noop_rate_limit
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(check_rate_limit, None)


@pytest.fixture
def patch_profile_service(monkeypatch):
    mock_service = AsyncMock()
    mock_service.get_or_create_profile = AsyncMock(return_value=_make_profile())
    mock_service.update_profile = AsyncMock(return_value=_make_profile())

    def fake_factory(session):
        return mock_service

    monkeypatch.setattr("app.api.profile.get_profile_service", fake_factory)
    return mock_service


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


def test_get_profile_returns_200_and_profile_json(override_auth, override_db, patch_profile_service):
    client = TestClient(app)
    response = client.get("/api/v1/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == TEST_USER["id"]
    assert body["interests"] == ["bronze"]
    assert body["knowledge_level"] == "beginner"


def test_put_profile_updates_and_returns_updated(override_auth, override_db, patch_profile_service):
    updated = _make_profile()
    updated.knowledge_level = "expert"
    patch_profile_service.update_profile.return_value = updated

    client = TestClient(app)
    response = client.put(
        "/api/v1/profile",
        json={"knowledge_level": "expert"},
    )

    assert response.status_code == 200
    assert response.json()["knowledge_level"] == "expert"
    patch_profile_service.update_profile.assert_awaited_once()


def test_put_profile_returns_404_when_entity_not_found(override_auth, override_db, patch_profile_service):
    from app.domain.exceptions import EntityNotFoundError

    patch_profile_service.update_profile.side_effect = EntityNotFoundError("no profile")

    client = TestClient(app)
    response = client.put(
        "/api/v1/profile",
        json={"knowledge_level": "expert"},
    )

    assert response.status_code == 404
    assert "no profile" not in response.json()["detail"]


def test_get_profile_requires_auth(override_db):
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(check_rate_limit, None)
    client = TestClient(app)
    response = client.get("/api/v1/profile")
    assert response.status_code in {401, 403}
