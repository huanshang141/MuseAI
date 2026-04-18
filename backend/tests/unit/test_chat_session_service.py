"""Unit tests for chat_session_service — pure session-level mocking, no DB."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.chat_session_service import (
    count_sessions_by_user,
    create_session,
    delete_session,
    get_session_by_id,
    get_sessions_by_user,
)


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_session_persists_new_row_and_returns_it():
    session = _mock_session()

    result = await create_session(session, title="My chat", user_id="user-123")

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.title == "My chat"
    assert added.user_id == "user-123"
    assert added.id
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added)
    assert result is added


@pytest.mark.asyncio
async def test_create_session_generates_unique_ids():
    session = _mock_session()
    a = await create_session(session, title="a", user_id="u")
    b = await create_session(session, title="b", user_id="u")
    assert a.id != b.id


@pytest.mark.asyncio
async def test_get_sessions_by_user_applies_limit_and_offset():
    session = _mock_session()
    fake_sessions = [MagicMock(), MagicMock()]
    scalars = MagicMock()
    scalars.all.return_value = fake_sessions
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    result = await get_sessions_by_user(session, user_id="u-1", limit=5, offset=10)

    assert result == fake_sessions
    session.execute.assert_awaited_once()
    stmt = session.execute.call_args[0][0]
    rendered = str(stmt).lower()
    assert "select" in rendered
    assert "chat_sessions" in rendered


@pytest.mark.asyncio
async def test_get_sessions_by_user_returns_empty_list_when_no_rows():
    session = _mock_session()
    scalars = MagicMock()
    scalars.all.return_value = []
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    result = await get_sessions_by_user(session, user_id="u-empty")
    assert result == []


@pytest.mark.asyncio
async def test_count_sessions_by_user_returns_int():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = 7
    session.execute.return_value = result_obj

    count = await count_sessions_by_user(session, user_id="u-1")
    assert count == 7


@pytest.mark.asyncio
async def test_count_sessions_by_user_returns_zero_when_null():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = None
    session.execute.return_value = result_obj

    count = await count_sessions_by_user(session, user_id="u-1")
    assert count == 0


@pytest.mark.asyncio
async def test_get_session_by_id_returns_session_on_match():
    session = _mock_session()
    target = MagicMock()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = target
    session.execute.return_value = result_obj

    result = await get_session_by_id(session, session_id="s-1", user_id="u-1")
    assert result is target


@pytest.mark.asyncio
async def test_get_session_by_id_returns_none_when_not_found():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = None
    session.execute.return_value = result_obj

    result = await get_session_by_id(session, session_id="missing", user_id="u-1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_session_deletes_and_returns_true_when_found():
    session = _mock_session()
    target = MagicMock()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = target
    session.execute.return_value = result_obj

    ok = await delete_session(session, session_id="s-1", user_id="u-1")

    assert ok is True
    session.delete.assert_awaited_once_with(target)


@pytest.mark.asyncio
async def test_delete_session_returns_false_when_not_found():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = None
    session.execute.return_value = result_obj

    ok = await delete_session(session, session_id="missing", user_id="u-1")
    assert ok is False
    session.delete.assert_not_awaited()
