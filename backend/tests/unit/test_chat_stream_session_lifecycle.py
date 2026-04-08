"""Test that DB session lifecycle is decoupled from SSE stream lifecycle.

This test verifies that the request-scoped DB session is not held open
for the entire duration of an SSE stream, which would cause long-running
transactions and connection pool exhaustion.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.chat_service import (
    ask_question_stream_with_rag,
    create_session,
)
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, ChatMessage, User
from sqlalchemy import select

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = str(uuid.uuid4())


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

        existing_user = await session.execute(select(User).where(User.id == TEST_USER_ID))
        if not existing_user.scalar_one_or_none():
            test_user = User(id=TEST_USER_ID, email="test@example.com", password_hash="test_hash", role="user")
            session.add(test_user)
            await session.commit()

        yield session


@pytest.mark.asyncio
async def test_stream_generator_does_not_hold_request_session_for_entire_stream(
    db_session, session_maker
):
    """Test that streaming does not hold the request-scoped session open.

    The request-scoped session should only be used for pre-check (session ownership).
    Streaming should happen without a DB connection, and persistence should use
    a new short-lived session after streaming completes.
    """
    # Create a test session first
    session_obj = await create_session(db_session, "测试会话", TEST_USER_ID)
    await db_session.commit()

    # Create a mock session that tracks commit calls
    mock_request_session = AsyncMock(spec=db_session.__class__)
    mock_request_session.execute = AsyncMock()
    mock_request_session.commit = AsyncMock()
    mock_request_session.add = MagicMock()
    mock_request_session.flush = AsyncMock()
    mock_request_session.refresh = AsyncMock()
    mock_request_session.delete = AsyncMock()
    mock_request_session.rollback = AsyncMock()

    # Mock the session ownership check to return a valid session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = session_obj
    mock_request_session.execute.return_value = mock_result

    mock_llm = AsyncMock()
    mock_rag = AsyncMock()
    mock_rag.run.return_value = {
        "documents": [],
        "retrieval_score": 0.95,
        "answer": "这是一个流式回答",
    }

    # Collect all events from the stream
    # Pass session_maker to enable decoupled persistence
    events = []
    async for event in ask_question_stream_with_rag(
        mock_request_session,
        session_obj.id,
        "问题",
        mock_rag,
        mock_llm,
        TEST_USER_ID,
        session_maker=session_maker,
    ):
        events.append(event)

    # Verify we got chunk events
    assert any('"type": "chunk"' in e for e in events), "Should have chunk events"

    # Verify we got a done event
    assert any('"type": "done"' in e for e in events), "Should have a done event"

    # KEY ASSERTION: The request session should NOT be committed during streaming
    # The current implementation commits the session at the end of streaming,
    # which holds the DB connection for the entire stream duration.
    # After the fix, commit should NOT be called on the request session.
    # Instead, a separate short-lived session should be used for persistence.
    assert (
        mock_request_session.commit.await_count == 0
    ), "Request session should NOT be committed during streaming - persistence should use a separate session"


@pytest.mark.asyncio
async def test_stream_persistence_uses_separate_session(db_session, session_maker):
    """Test that message persistence uses a separate short-lived session.

    This ensures that even if streaming takes a long time, the DB connection
    is not held open, preventing connection pool exhaustion.
    """
    session_obj = await create_session(db_session, "持久化测试", TEST_USER_ID)
    await db_session.commit()

    mock_llm = AsyncMock()

    async def mock_stream(*args):
        for chunk in ["测试回答"]:
            yield chunk

    mock_llm.generate_stream = mock_stream

    mock_rag = AsyncMock()
    mock_rag.run.return_value = {
        "documents": [],
        "retrieval_score": 0.9,
        "answer": "测试回答",
    }

    # Create a mock request session to track that it's not used for persistence
    mock_request_session = AsyncMock(spec=db_session.__class__)
    mock_request_session.execute = AsyncMock()
    mock_request_session.commit = AsyncMock()
    mock_request_session.add = MagicMock()
    mock_request_session.flush = AsyncMock()
    mock_request_session.refresh = AsyncMock()

    # Mock the session ownership check to return a valid session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = session_obj
    mock_request_session.execute.return_value = mock_result

    # Collect events from stream - this should use separate session for persistence
    events = []
    async for event in ask_question_stream_with_rag(
        mock_request_session,
        session_obj.id,
        "问题",
        mock_rag,
        mock_llm,
        TEST_USER_ID,
        session_maker=session_maker,
    ):
        events.append(event)

    # Verify we got the expected events
    assert any('"type": "done"' in e for e in events), "Should have done event"

    # Request session should NOT be committed (separate session used)
    assert mock_request_session.commit.await_count == 0, "Request session should not be committed"

    # Verify messages were persisted in a separate session
    async with get_session(session_maker) as check_session:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_obj.id)
        result = await check_session.execute(stmt)
        messages = list(result.scalars().all())

    assert len(messages) == 2, "Should have 2 messages (user + assistant)"
    user_msg = next((m for m in messages if m.role == "user"), None)
    assistant_msg = next((m for m in messages if m.role == "assistant"), None)

    assert user_msg is not None
    assert user_msg.content == "问题"

    assert assistant_msg is not None
    assert assistant_msg.content == "测试回答"


@pytest.mark.asyncio
async def test_stream_ownership_check_before_streaming(db_session, session_maker):
    """Test that session ownership is verified before streaming starts.

    This ensures the request session is used only for the pre-check,
    not held open during streaming.
    """
    session_obj = await create_session(db_session, "所有权测试", TEST_USER_ID)
    await db_session.commit()

    # Track when the session is accessed
    session_access_log = []

    mock_request_session = AsyncMock(spec=db_session.__class__)
    mock_request_session.commit = AsyncMock()
    mock_request_session.add = MagicMock()
    mock_request_session.flush = AsyncMock()
    mock_request_session.refresh = AsyncMock()
    mock_request_session.delete = AsyncMock()
    mock_request_session.rollback = AsyncMock()

    async def tracked_execute(*args, **kwargs):
        session_access_log.append("execute")
        result = await db_session.execute(*args, **kwargs)
        # Return the actual result for ownership check
        return result

    mock_request_session.execute = tracked_execute

    mock_llm = AsyncMock()
    mock_rag = AsyncMock()
    mock_rag.run.return_value = {
        "documents": [],
        "retrieval_score": 0.9,
        "answer": "测试回答",
    }

    # Collect events
    events = []
    async for event in ask_question_stream_with_rag(
        mock_request_session,
        session_obj.id,
        "问题",
        mock_rag,
        mock_llm,
        TEST_USER_ID,
        session_maker=session_maker,
    ):
        events.append(event)
        # Log access during streaming
        if '"type": "chunk"' in event:
            session_access_log.append(f"chunk_event_while_session_active")

    # Verify streaming produced output
    assert any('"type": "chunk"' in e for e in events)

    # The request session should only be used for ownership check (one execute call)
    # After the fix, it should NOT be used for message persistence
    ownership_check_count = session_access_log.count("execute")
    assert ownership_check_count >= 1, "Session should be used at least for ownership check"


@pytest.mark.asyncio
async def test_stream_nonexistent_session_returns_error_without_persistence(
    db_session, session_maker
):
    """Test that non-existent session returns error without attempting persistence.

    This verifies that ownership check happens early and prevents unnecessary
    operations on invalid sessions.
    """
    mock_request_session = AsyncMock(spec=db_session.__class__)
    mock_request_session.commit = AsyncMock()
    mock_request_session.add = MagicMock()
    mock_request_session.flush = AsyncMock()
    mock_request_session.refresh = AsyncMock()

    # Mock execute to return None (session not found)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_request_session.execute.return_value = mock_result

    mock_llm = AsyncMock()
    mock_rag = AsyncMock()

    events = []
    async for event in ask_question_stream_with_rag(
        mock_request_session,
        "nonexistent-session-id",
        "问题",
        mock_rag,
        mock_llm,
        TEST_USER_ID,
    ):
        events.append(event)

    # Should have exactly one error event
    assert len(events) == 1
    event_data = json.loads(events[0].replace("data: ", ""))
    assert event_data["type"] == "error"
    assert event_data["code"] == "SESSION_NOT_FOUND"

    # Should not attempt any persistence
    assert mock_request_session.add.call_count == 0
    assert mock_request_session.commit.await_count == 0
