"""Unit tests for ExhibitService — mocks ExhibitRepositoryPort."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.application.exhibit_service import ExhibitService
from app.domain.entities import Exhibit
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, Location


def _make_exhibit(id_: str = "e-1", name: str = "青铜鼎", hall: str = "main", floor: int = 1) -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId(id_),
        name=name,
        description="desc",
        location=Location(x=1.0, y=2.0, floor=floor),
        hall=hall,
        category="bronze",
        era="shang",
        importance=3,
        estimated_visit_time=10,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock(side_effect=lambda e: e)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    repo.list_all = AsyncMock(return_value=[])
    repo.list_with_filters = AsyncMock(return_value=[])
    repo.list_by_category = AsyncMock(return_value=[])
    repo.list_by_hall = AsyncMock(return_value=[])
    repo.list_all_active = AsyncMock(return_value=[])
    repo.find_by_interests = AsyncMock(return_value=[])
    repo.search_by_name = AsyncMock(return_value=[])
    repo.get_distinct_categories = AsyncMock(return_value=[])
    repo.get_distinct_halls = AsyncMock(return_value=[])
    return repo


@pytest.mark.asyncio
async def test_create_exhibit_passes_fields_and_saves():
    repo = _mock_repo()
    service = ExhibitService(repo)

    result = await service.create_exhibit(
        name="玉琮",
        description="新石器时代",
        location_x=3.0,
        location_y=4.0,
        floor=2,
        hall="east",
        category="jade",
        era="neolithic",
        importance=5,
        estimated_visit_time=15,
        document_id="d-2",
    )

    repo.save.assert_awaited_once()
    saved = repo.save.call_args[0][0]
    assert saved.name == "玉琮"
    assert saved.location.x == 3.0
    assert saved.location.floor == 2
    assert saved.is_active is True
    assert saved.id.value
    assert result is saved


@pytest.mark.asyncio
async def test_get_exhibit_returns_none_when_missing():
    repo = _mock_repo()
    service = ExhibitService(repo)
    assert await service.get_exhibit("missing") is None


@pytest.mark.asyncio
async def test_get_exhibit_returns_entity_when_found():
    repo = _mock_repo()
    target = _make_exhibit()
    repo.get_by_id.return_value = target

    service = ExhibitService(repo)
    assert await service.get_exhibit("e-1") is target


@pytest.mark.asyncio
async def test_list_exhibits_floor_branch_calls_list_with_filters():
    repo = _mock_repo()
    repo.list_with_filters.return_value = [_make_exhibit()]

    service = ExhibitService(repo)
    await service.list_exhibits(floor=2, category="bronze", hall="east")

    repo.list_with_filters.assert_awaited_once_with(category="bronze", hall="east", floor=2)
    repo.list_by_category.assert_not_awaited()
    repo.list_by_hall.assert_not_awaited()
    repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_exhibits_category_branch_calls_list_by_category():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.list_exhibits(category="bronze")

    repo.list_by_category.assert_awaited_once_with("bronze")
    repo.list_with_filters.assert_not_awaited()
    repo.list_by_hall.assert_not_awaited()
    repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_exhibits_hall_branch_calls_list_by_hall():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.list_exhibits(hall="east")

    repo.list_by_hall.assert_awaited_once_with("east")
    repo.list_by_category.assert_not_awaited()
    repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_exhibits_no_filter_branch_calls_list_all():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.list_exhibits()

    repo.list_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_exhibits_applies_python_side_pagination():
    repo = _mock_repo()
    repo.list_all.return_value = [_make_exhibit(id_=f"e-{i}") for i in range(10)]

    service = ExhibitService(repo)
    page = await service.list_exhibits(skip=3, limit=2)

    assert len(page) == 2
    assert page[0].id.value == "e-3"
    assert page[1].id.value == "e-4"


@pytest.mark.asyncio
async def test_update_exhibit_partial_updates_and_location_merge():
    repo = _mock_repo()
    existing = _make_exhibit()
    repo.get_by_id.return_value = existing

    service = ExhibitService(repo)
    result = await service.update_exhibit(
        exhibit_id="e-1",
        name="新名",
        location_x=9.0,
    )

    assert result.name == "新名"
    assert result.location.x == 9.0
    assert result.location.y == 2.0
    assert result.location.floor == 1
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_exhibit_raises_when_missing():
    repo = _mock_repo()
    repo.get_by_id.return_value = None

    service = ExhibitService(repo)
    with pytest.raises(EntityNotFoundError):
        await service.update_exhibit("missing", name="x")


@pytest.mark.asyncio
async def test_update_exhibit_location_partial_without_x_still_merges():
    repo = _mock_repo()
    existing = _make_exhibit()
    repo.get_by_id.return_value = existing

    service = ExhibitService(repo)
    result = await service.update_exhibit("e-1", location_y=7.0)

    assert result.location.x == 1.0
    assert result.location.y == 7.0


@pytest.mark.asyncio
async def test_delete_exhibit_delegates_to_repo():
    repo = _mock_repo()
    repo.delete.return_value = True

    service = ExhibitService(repo)
    assert await service.delete_exhibit("e-1") is True
    repo.delete.assert_awaited_once_with(ExhibitId("e-1"))


@pytest.mark.asyncio
async def test_find_by_interests_passes_through():
    repo = _mock_repo()
    repo.find_by_interests.return_value = [_make_exhibit()]

    service = ExhibitService(repo)
    result = await service.find_by_interests(["bronze"], limit=5)

    repo.find_by_interests.assert_awaited_once_with(["bronze"], 5)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_search_exhibits_passes_all_kwargs_to_repo():
    repo = _mock_repo()
    service = ExhibitService(repo)
    await service.search_exhibits(
        query="鼎", skip=5, limit=10, category="bronze", hall="east", floor=1
    )

    repo.search_by_name.assert_awaited_once_with(
        query="鼎", category="bronze", hall="east", floor=1, skip=5, limit=10
    )


@pytest.mark.asyncio
async def test_get_all_categories_and_halls_pass_through():
    repo = _mock_repo()
    repo.get_distinct_categories.return_value = ["bronze", "jade"]
    repo.get_distinct_halls.return_value = ["east", "main"]

    service = ExhibitService(repo)
    assert await service.get_all_categories() == ["bronze", "jade"]
    assert await service.get_all_halls() == ["east", "main"]


@pytest.mark.asyncio
async def test_list_all_active_delegates():
    repo = _mock_repo()
    repo.list_all_active.return_value = [_make_exhibit()]
    service = ExhibitService(repo)
    result = await service.list_all_active()
    assert len(result) == 1
    repo.list_all_active.assert_awaited_once()
