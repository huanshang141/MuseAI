"""Unit tests for ProfileService — mocks VisitorProfileRepositoryPort."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.application.profile_service import ProfileService
from app.domain.entities import VisitorProfile
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, ProfileId, UserId


def _make_profile(user_id: str = "u-1", interests: list[str] | None = None) -> VisitorProfile:
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId("p-1"),
        user_id=UserId(user_id),
        interests=interests or [],
        knowledge_level="beginner",
        narrative_preference="balanced",
        reflection_depth="2",
        visited_exhibit_ids=[],
        feedback_history=[],
        created_at=now,
        updated_at=now,
    )


def _mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_user_id = AsyncMock(return_value=None)
    repo.save = AsyncMock(side_effect=lambda p: p)
    return repo


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_profile_when_found():
    repo = _mock_repo()
    existing = _make_profile()
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.get_or_create_profile("u-1")

    assert result is existing
    repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_create_creates_default_when_missing():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None

    service = ProfileService(repo)
    result = await service.get_or_create_profile("u-new")

    repo.save.assert_awaited_once()
    saved = repo.save.call_args[0][0]
    assert saved.user_id.value == "u-new"
    assert saved.knowledge_level == "beginner"
    assert saved.interests == []
    assert saved.visited_exhibit_ids == []
    assert result is saved


@pytest.mark.asyncio
async def test_get_profile_returns_none_when_missing():
    repo = _mock_repo()
    service = ProfileService(repo)
    assert await service.get_profile("nobody") is None


@pytest.mark.asyncio
async def test_update_profile_applies_partial_updates():
    repo = _mock_repo()
    existing = _make_profile(interests=["pottery"])
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.update_profile(
        "u-1",
        interests=["bronze", "pottery"],
        knowledge_level="expert",
    )

    assert result.interests == ["bronze", "pottery"]
    assert result.knowledge_level == "expert"
    assert result.narrative_preference == "balanced"
    assert result.reflection_depth == "2"
    repo.save.assert_awaited_once_with(existing)


@pytest.mark.asyncio
async def test_update_profile_raises_when_profile_missing():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None

    service = ProfileService(repo)
    with pytest.raises(EntityNotFoundError):
        await service.update_profile("u-missing", interests=["x"])


@pytest.mark.asyncio
async def test_update_profile_refreshes_updated_at_even_with_no_field_changes():
    repo = _mock_repo()
    existing = _make_profile()
    old_ts = existing.updated_at
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.update_profile("u-1")

    assert result.updated_at > old_ts


@pytest.mark.asyncio
async def test_record_visit_appends_new_exhibit_and_saves():
    repo = _mock_repo()
    existing = _make_profile()
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.record_visit("u-1", "e-1")

    assert ExhibitId("e-1") in result.visited_exhibit_ids
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_visit_skips_save_when_already_visited():
    repo = _mock_repo()
    existing = _make_profile()
    existing.visited_exhibit_ids.append(ExhibitId("e-1"))
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    await service.record_visit("u-1", "e-1")

    repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_visit_creates_profile_when_none_exists():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None

    service = ProfileService(repo)
    result = await service.record_visit("u-new", "e-1")

    assert ExhibitId("e-1") in result.visited_exhibit_ids
    assert repo.save.await_count == 2


@pytest.mark.asyncio
async def test_add_feedback_appends_and_saves():
    repo = _mock_repo()
    existing = _make_profile()
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    result = await service.add_feedback("u-1", "great tour!")

    assert "great tour!" in result.feedback_history
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_visited_exhibits_returns_empty_when_profile_missing():
    repo = _mock_repo()
    repo.get_by_user_id.return_value = None
    service = ProfileService(repo)
    assert await service.get_visited_exhibits("u-missing") == []


@pytest.mark.asyncio
async def test_has_visited_true_false_cases():
    repo = _mock_repo()
    existing = _make_profile()
    existing.visited_exhibit_ids.append(ExhibitId("e-1"))
    repo.get_by_user_id.return_value = existing

    service = ProfileService(repo)
    assert await service.has_visited("u-1", "e-1") is True
    assert await service.has_visited("u-1", "e-other") is False
