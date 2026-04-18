"""Unit tests for CuratorService — mocks CuratorAgentPort + ProfileService + ExhibitService."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.application.curator_service import CuratorService
from app.domain.entities import Exhibit, VisitorProfile
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, Location, ProfileId, UserId


def _make_profile(interests: list[str] | None = None) -> VisitorProfile:
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId("p-1"),
        user_id=UserId("u-1"),
        interests=interests or ["bronze"],
        knowledge_level="intermediate",
        narrative_preference="storytelling",
        reflection_depth="3",
        visited_exhibit_ids=[ExhibitId("e-old")],
        feedback_history=[],
        created_at=now,
        updated_at=now,
    )


def _make_exhibit() -> Exhibit:
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId("e-1"),
        name="青铜鼎",
        description="商代礼器",
        location=Location(x=1.0, y=2.0, floor=1),
        hall="main",
        category="bronze",
        era="shang",
        importance=5,
        estimated_visit_time=15,
        document_id="d-1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _mocks():
    agent = AsyncMock()
    agent.run = AsyncMock(return_value={"output": "agent response", "session_id": "sess-1"})

    profile_svc = AsyncMock()
    profile_svc.get_or_create_profile = AsyncMock(return_value=_make_profile())
    profile_svc.record_visit = AsyncMock()

    exhibit_svc = AsyncMock()
    exhibit_svc.get_exhibit = AsyncMock(return_value=_make_exhibit())

    return agent, profile_svc, exhibit_svc


@pytest.mark.asyncio
async def test_plan_tour_uses_profile_interests_when_not_overridden():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.plan_tour(user_id="u-1", available_time=60)

    assert result["interests"] == ["bronze"]
    assert result["available_time"] == 60
    assert result["visited_exhibit_ids"] == ["e-old"]
    agent.run.assert_awaited_once()
    prompt_sent = agent.run.call_args.kwargs["user_input"]
    assert "60分钟" in prompt_sent
    assert "bronze" in prompt_sent


@pytest.mark.asyncio
async def test_plan_tour_override_interests_win():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)
    result = await service.plan_tour(user_id="u-1", available_time=30, interests=["jade"])

    assert result["interests"] == ["jade"]
    assert "jade" in agent.run.call_args.kwargs["user_input"]


@pytest.mark.asyncio
async def test_generate_narrative_raises_when_exhibit_missing():
    agent, prof, exh = _mocks()
    exh.get_exhibit.return_value = None

    service = CuratorService(agent, prof, exh)
    with pytest.raises(EntityNotFoundError):
        await service.generate_narrative(user_id="u-1", exhibit_id="missing")

    agent.run.assert_not_awaited()
    prof.record_visit.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_narrative_records_visit_after_success():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.generate_narrative(user_id="u-1", exhibit_id="e-1")

    assert result["narrative"] == "agent response"
    assert result["exhibit_name"] == "青铜鼎"
    prof.record_visit.assert_awaited_once_with("u-1", "e-1")


@pytest.mark.asyncio
async def test_get_reflection_prompts_raises_when_exhibit_missing():
    agent, prof, exh = _mocks()
    exh.get_exhibit.return_value = None

    service = CuratorService(agent, prof, exh)
    with pytest.raises(EntityNotFoundError):
        await service.get_reflection_prompts(user_id="u-1", exhibit_id="missing")


@pytest.mark.asyncio
async def test_get_reflection_prompts_includes_profile_level():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.get_reflection_prompts(user_id="u-1", exhibit_id="e-1")

    assert result["knowledge_level"] == "intermediate"
    assert result["reflection_depth"] == "3"
    prompt = agent.run.call_args.kwargs["user_input"]
    assert "intermediate" in prompt
    assert "反思深度：3" in prompt


@pytest.mark.asyncio
async def test_chat_passes_history_through_and_includes_profile_context():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    history = [{"role": "user", "content": "hi"}]
    result = await service.chat(user_id="u-1", message="tell me about jade", chat_history=history)

    agent.run.assert_awaited_once()
    assert agent.run.call_args.kwargs["chat_history"] == history
    assert "tell me about jade" in agent.run.call_args.kwargs["user_input"]
    assert result["response"] == "agent response"


@pytest.mark.asyncio
async def test_chat_defaults_history_to_empty_list():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    await service.chat(user_id="u-1", message="hi")
    assert agent.run.call_args.kwargs["chat_history"] == []


@pytest.mark.asyncio
async def test_get_exhibit_info_raises_when_exhibit_missing():
    agent, prof, exh = _mocks()
    exh.get_exhibit.return_value = None

    service = CuratorService(agent, prof, exh)
    with pytest.raises(EntityNotFoundError):
        await service.get_exhibit_info(user_id="u-1", exhibit_id="missing")


@pytest.mark.asyncio
async def test_get_exhibit_info_returns_exhibit_dict_and_knowledge():
    agent, prof, exh = _mocks()
    service = CuratorService(agent, prof, exh)

    result = await service.get_exhibit_info(user_id="u-1", exhibit_id="e-1")

    assert result["exhibit"]["id"] == "e-1"
    assert result["exhibit"]["name"] == "青铜鼎"
    assert result["exhibit"]["era"] == "shang"
    assert result["knowledge"] == "agent response"
