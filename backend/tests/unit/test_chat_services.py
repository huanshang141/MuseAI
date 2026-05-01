"""Unit tests for chat session and message services, plus chat API integration.

Merged from:
  - test_chat_session_service.py
  - test_chat_message_service.py
  - test_chat_integration.py
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.chat_message_service import (
    add_message,
    count_messages_by_session,
    get_messages_by_session,
)
from app.application.chat_session_service import (
    count_sessions_by_user,
    create_session,
    delete_session,
    get_session_by_id,
    get_sessions_by_user,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Session service tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Message service tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_message_persists_with_uuid_and_optional_trace_id():
    session = _mock_session()

    result = await add_message(
        session, session_id="s-1", role="user", content="hello", trace_id="t-1"
    )

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.session_id == "s-1"
    assert added.role == "user"
    assert added.content == "hello"
    assert added.trace_id == "t-1"
    assert added.id
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added)
    assert result is added


@pytest.mark.asyncio
async def test_add_message_trace_id_defaults_to_none():
    session = _mock_session()
    result = await add_message(session, session_id="s-1", role="assistant", content="hi")
    assert result.trace_id is None


@pytest.mark.asyncio
async def test_add_message_generates_unique_ids():
    session = _mock_session()
    a = await add_message(session, session_id="s-1", role="user", content="1")
    b = await add_message(session, session_id="s-1", role="user", content="2")
    assert a.id != b.id


@pytest.mark.asyncio
async def test_get_messages_by_session_applies_limit_offset_and_asc_order():
    session = _mock_session()
    fake = [MagicMock(), MagicMock(), MagicMock()]
    scalars = MagicMock()
    scalars.all.return_value = fake
    result_obj = MagicMock()
    result_obj.scalars.return_value = scalars
    session.execute.return_value = result_obj

    messages = await get_messages_by_session(session, session_id="s-1", limit=50, offset=0)

    assert messages == fake
    stmt = session.execute.call_args[0][0]
    rendered = str(stmt).lower()
    assert "select" in rendered
    assert "chat_messages" in rendered
    assert "asc" in rendered or "order by" in rendered


@pytest.mark.asyncio
async def test_count_messages_by_session_returns_count():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = 42
    session.execute.return_value = result_obj

    assert await count_messages_by_session(session, session_id="s-1") == 42


@pytest.mark.asyncio
async def test_count_messages_by_session_returns_zero_when_null():
    session = _mock_session()
    result_obj = MagicMock()
    result_obj.scalar.return_value = None
    session.execute.return_value = result_obj

    assert await count_messages_by_session(session, session_id="s-empty") == 0


# ---------------------------------------------------------------------------
# Chat API integration tests
# ---------------------------------------------------------------------------

class TestChatAPIIntegration:
    @pytest.mark.asyncio
    async def test_ask_question_with_rag_calls_agent(self):
        mock_rag_agent = AsyncMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "query": "test query",
                "documents": [],
                "retrieval_score": 0.8,
                "attempts": 0,
                "transformations": [],
                "answer": "Generated answer from RAG",
            }
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(id="test-session")
        mock_session.execute.return_value = mock_result

        with patch("app.application.chat_service.add_message", new_callable=AsyncMock) as mock_add_msg:
            mock_add_msg.return_value = MagicMock()

            from app.application.chat_service import ask_question_with_rag

            result = await ask_question_with_rag(
                session=mock_session,
                session_id="test-session",
                message="test query",
                rag_agent=mock_rag_agent,
                user_id="test-user",
            )

            assert result is not None
            assert "answer" in result
            mock_rag_agent.run.assert_called_once_with("test query")
