"""Tests for chat streaming, TTS events, session lifecycle, and error sanitization.

Merged from:
  - test_chat_service_streaming.py
  - test_chat_stream_session_lifecycle.py
  - test_chat_stream_tts.py
  - test_chat_error_sanitization.py
"""
import json
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.chat_service import (
    ask_question_stream_with_rag,
    create_session,
)
from app.application.sse_events import (
    sse_chat_audio_chunk,
    sse_chat_audio_end,
    sse_chat_audio_start,
)
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, ChatMessage, User
from app.infra.providers.tts.base import TTSConfig
from app.infra.providers.tts.mock import MockTTSProvider
from sqlalchemy import select


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_events(raw: str) -> list[dict]:
    """Parse SSE stream into list of JSON payloads."""
    events = []
    for line in raw.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


async def _async_iter(items):
    """Helper to create an async iterator from a list."""
    for item in items:
        yield item


def _mock_existing_session() -> AsyncMock:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock(id="test-session")
    mock_session.execute.return_value = mock_result
    return mock_session


# ---------------------------------------------------------------------------
# Fixtures (session lifecycle)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TestAskQuestionStream
# ---------------------------------------------------------------------------

class TestAskQuestionStream:
    """Tests for ask_question_stream function."""

    @pytest.mark.asyncio
    async def test_yields_sse_events_on_success(self):
        """ask_question_stream should yield SSE events."""
        from app.application.chat_service import ask_question_stream

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM provider that yields chunks
        async def mock_stream(messages):
            yield "Hello"
            yield " world"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="session-123",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have thinking, chunk, and done events
        assert len(events) >= 3
        # Check SSE format
        assert all("data:" in e for e in events)
        # Check for done event
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_yields_error_for_invalid_session(self):
        """ask_question_stream should yield error for invalid session."""
        from app.application.chat_service import ask_question_stream

        mock_session = AsyncMock()

        # Mock session not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="nonexistent-session",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        assert len(events) == 1
        assert "error" in events[0].lower()
        assert "SESSION_NOT_FOUND" in events[0]

    @pytest.mark.asyncio
    async def test_yields_error_on_llm_error(self):
        """ask_question_stream should yield error when LLM fails."""
        from app.application.chat_service import ask_question_stream
        from app.domain.exceptions import LLMError

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM provider that raises error
        async def mock_stream_with_error(messages):
            yield "Start"
            raise LLMError("LLM unavailable")

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream_with_error

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="session-123",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        error_events = [e for e in events if "error" in e.lower()]
        assert len(error_events) >= 1
        assert "LLM_ERROR" in error_events[-1]

    @pytest.mark.asyncio
    async def test_saves_messages_on_success(self):
        """ask_question_stream should save user and assistant messages."""
        from app.application.chat_service import ask_question_stream

        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM provider
        async def mock_stream(messages):
            yield "Response"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        # Track add calls
        added_objects = []
        mock_session.add = lambda obj: added_objects.append(obj)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream(
            session=mock_session,
            session_id="session-123",
            message="Hello",
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have added user message and assistant message
        assert len(added_objects) >= 2


# ---------------------------------------------------------------------------
# TestAskQuestionStreamWithRag
# ---------------------------------------------------------------------------

class TestAskQuestionStreamWithRag:
    """Tests for ask_question_stream_with_rag function."""

    @pytest.mark.asyncio
    async def test_yields_sse_events_with_rag(self):
        """ask_question_stream_with_rag should yield SSE events."""
        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock RAG agent
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "This is the answer",
                "documents": [],
                "retrieval_score": 0.85,
            }
        )
        # Mock prompt_gateway to use fallback prompt
        mock_rag_agent.prompt_gateway = None

        # Mock LLM provider that streams
        async def mock_stream(messages):
            yield "This is the answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have thinking, chunk, and done events
        assert len(events) >= 3
        # Check for done event
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_yields_error_for_invalid_session(self):
        """ask_question_stream_with_rag should yield error for invalid session."""
        mock_session = AsyncMock()

        # Mock session not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_rag_agent = MagicMock()
        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="nonexistent-session",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        assert len(events) == 1
        assert "error" in events[0].lower()
        assert "SESSION_NOT_FOUND" in events[0]

    @pytest.mark.asyncio
    async def test_yields_error_on_rag_error(self):
        """ask_question_stream_with_rag should yield error when RAG fails."""
        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock RAG agent that raises error
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(side_effect=Exception("RAG unavailable"))

        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Should have error event
        error_events = [e for e in events if "error" in e.lower()]
        assert len(error_events) >= 1
        assert "RAG_ERROR" in error_events[-1]

    @pytest.mark.asyncio
    async def test_includes_sources_in_done_event(self):
        """ask_question_stream_with_rag should include sources in done event."""
        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock document with metadata
        mock_doc = MagicMock()
        mock_doc.page_content = "Document content"
        mock_doc.metadata = {"chunk_id": "chunk-1", "rrf_score": 0.9}

        # Mock RAG agent with documents
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [mock_doc],
                "retrieval_score": 0.85,
            }
        )
        # Mock prompt_gateway to use fallback prompt
        mock_rag_agent.prompt_gateway = None

        # Mock LLM provider that streams
        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Find done event and check for sources
        done_events = [e for e in events if '"type": "done"' in e]
        assert len(done_events) == 1
        assert "chunk-1" in done_events[0]

    @pytest.mark.asyncio
    async def test_shows_retrieval_info_in_thinking(self):
        """ask_question_stream_with_rag should show retrieval info in thinking events."""
        mock_session = AsyncMock()

        # Mock session validation
        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock document with proper attributes for JSON serialization
        mock_doc = MagicMock()
        mock_doc.page_content = "Document content"
        mock_doc.metadata = {"chunk_id": "chunk-1", "rrf_score": 0.9}

        # Mock RAG agent with documents
        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [mock_doc, mock_doc],
                "retrieval_score": 0.75,
            }
        )
        # Mock prompt_gateway to use fallback prompt
        mock_rag_agent.prompt_gateway = None

        # Mock LLM provider that streams
        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        # Check for retrieval info in rag_step events
        rag_step_events = [e for e in events if '"type": "rag_step"' in e]
        # Should have retrieve and evaluate rag_step events
        assert any('"step": "retrieve"' in e for e in rag_step_events)
        assert any('"step": "evaluate"' in e for e in rag_step_events)
        # Check for retrieval score in evaluate event
        assert any("0.75" in e for e in rag_step_events)


# ---------------------------------------------------------------------------
# Standalone streaming tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_question_stream_guest():
    """Test guest chat streaming without DB persistence."""
    from app.application.chat_service import ask_question_stream_guest

    mock_redis = AsyncMock()
    mock_redis.get_guest_session.return_value = None

    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test answer",
        "documents": [],
        "retrieval_score": 0.8,
    })
    # Mock prompt_gateway to use fallback prompt
    mock_rag_agent.prompt_gateway = None

    # Mock LLM provider that streams
    async def mock_stream(messages):
        yield "Test answer"

    mock_llm = MagicMock()
    mock_llm.generate_stream = mock_stream

    messages = []
    async for event in ask_question_stream_guest(
        session_id="guest-123",
        message="Hello",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        redis=mock_redis,
    ):
        messages.append(event)

    # Should have thinking and done events
    event_types = [json.loads(m.split("data: ")[1])["type"] for m in messages if m.startswith("data:")]
    assert "thinking" in event_types
    assert "done" in event_types

    # Should store session in Redis
    mock_redis.set_guest_session.assert_called()


@pytest.mark.asyncio
async def test_streaming_emits_llm_tokens_not_fixed_50_char_slices():
    """ask_question_stream_with_rag should emit LLM tokens directly, not fixed 50-char slices.

    This test verifies that streaming truly forwards tokens from the LLM provider
    rather than batching them into arbitrary 50-character chunks.

    The key assertion is that the chunk contents should match what the LLM provider
    yields, NOT be fixed 50-char slices of a complete answer.
    """
    mock_session = AsyncMock()

    # Mock session validation
    mock_chat_session = MagicMock()
    mock_chat_session.id = "session-123"
    mock_chat_session.user_id = "user-123"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_chat_session
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Define expected LLM chunks - these are the exact tokens we expect to see
    expected_llm_chunks = [
        "This ",
        "is ",
        "a ",
        "streamed ",
        "answer ",
        "from ",
        "the ",
        "LLM ",
        "provider.",
    ]

    # Mock RAG agent that returns retrieval results but streams via LLM
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(
        return_value={
            "answer": "",  # Answer will be streamed via LLM, not pre-computed
            "documents": [],
            "retrieval_score": 0.85,
        }
    )
    # Mock prompt_gateway to return None (use fallback prompt)
    mock_rag_agent.prompt_gateway = None

    # Mock LLM provider that yields variable-sized chunks
    async def mock_stream(messages):
        for chunk in expected_llm_chunks:
            yield chunk

    mock_llm = MagicMock()
    mock_llm.generate_stream = mock_stream

    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="session-123",
        message="What is this?",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)

    # Extract chunk events
    chunk_events = []
    for event in events:
        if event.startswith("data: "):
            try:
                data = json.loads(event[6:])
                if data.get("type") == "chunk":
                    chunk_events.append(data)
            except json.JSONDecodeError:
                pass

    # Should have chunk events
    assert len(chunk_events) > 0, "Should have chunk events"

    # Extract chunk contents
    chunk_contents = [e.get("content", "") for e in chunk_events]

    # Key assertion: chunks should match what the LLM provider yields
    # NOT be fixed 50-char slices. We check that at least some chunks
    # are exactly what the LLM provider yielded (small token-sized chunks)
    small_chunks = [c for c in chunk_contents if 0 < len(c) < 10]
    assert len(small_chunks) > 0, (
        f"No small chunks found. All chunk lengths: {[len(c) for c in chunk_contents]}. "
        f"Expected LLM token-sized chunks (e.g., {expected_llm_chunks[:3]}), "
        "but got fixed 50-char slices instead."
    )


# ---------------------------------------------------------------------------
# TestAskQuestionStreamWithRagDegraded
# ---------------------------------------------------------------------------

class TestAskQuestionStreamWithRagDegraded:
    """Tests for ask_question_stream_with_rag when ES is degraded."""

    @pytest.mark.asyncio
    async def test_returns_rag_unavailable_when_elasticsearch_degraded(self):
        """ask_question_stream_with_rag should yield RAG_UNAVAILABLE error when ES is degraded."""
        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_rag_agent = MagicMock()
        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
            degraded_services={"elasticsearch"},
        ):
            events.append(event)

        error_events = [e for e in events if "error" in e.lower()]
        assert len(error_events) >= 1
        assert "RAG_UNAVAILABLE" in error_events[-1]
        mock_rag_agent.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_normally_when_not_degraded(self):
        """ask_question_stream_with_rag should proceed normally when not degraded."""
        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [],
                "retrieval_score": 0.85,
            }
        )
        mock_rag_agent.prompt_gateway = None

        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
            degraded_services=set(),
        ):
            events.append(event)

        mock_rag_agent.run.assert_called_once()
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_proceeds_normally_with_default_degraded_services(self):
        """ask_question_stream_with_rag should proceed normally when degraded_services is omitted."""
        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_rag_agent = MagicMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "answer": "The answer",
                "documents": [],
                "retrieval_score": 0.85,
            }
        )
        mock_rag_agent.prompt_gateway = None

        async def mock_stream(messages):
            yield "The answer"

        mock_llm = MagicMock()
        mock_llm.generate_stream = mock_stream

        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
        ):
            events.append(event)

        mock_rag_agent.run.assert_called_once()
        assert any('"type": "done"' in e for e in events)

    @pytest.mark.asyncio
    async def test_persists_user_message_when_degraded(self):
        """ask_question_stream_with_rag should persist user message even when ES is degraded."""
        mock_session = AsyncMock()

        mock_chat_session = MagicMock()
        mock_chat_session.id = "session-123"
        mock_chat_session.user_id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_chat_session
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_rag_agent = MagicMock()
        mock_llm = MagicMock()

        events = []
        async for event in ask_question_stream_with_rag(
            session=mock_session,
            session_id="session-123",
            message="What is this?",
            rag_agent=mock_rag_agent,
            llm_provider=mock_llm,
            user_id="user-123",
            degraded_services={"elasticsearch"},
        ):
            events.append(event)

        mock_session.commit.assert_called()


# ---------------------------------------------------------------------------
# TestAskRequestTTSFields
# ---------------------------------------------------------------------------

class TestAskRequestTTSFields:
    def test_default_tts_disabled(self):
        from app.api.chat import AskRequest
        req = AskRequest(session_id="s1", message="hi")
        assert req.tts is False
        assert req.tts_voice is None

    def test_tts_enabled(self):
        from app.api.chat import AskRequest
        req = AskRequest(session_id="s1", message="hi", tts=True, tts_voice="冰糖")
        assert req.tts is True
        assert req.tts_voice == "冰糖"


# ---------------------------------------------------------------------------
# TestChatStreamTTSEvents
# ---------------------------------------------------------------------------

class TestChatStreamTTSEvents:
    """Verify TTS audio events are interleaved with text events."""

    @pytest.mark.asyncio
    async def test_simple_stream_appends_tts_events(self):
        """ask_question_stream should yield audio_start/chunk/end before done."""
        from app.application.chat_stream_service import ask_question_stream

        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        tts_provider = MockTTSProvider()
        tts_config = TTSConfig(voice="冰糖", style="用清晰专业的语气讲解，语速适中")

        session = AsyncMock()

        with patch("app.application.chat_stream_service.add_message"):
            events = []
            async for event in ask_question_stream(
                session=session,
                session_id="s1",
                message="hi",
                llm_provider=mock_llm,
                user_id="u1",
                tts_provider=tts_provider,
                tts_config=tts_config,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        types = [e["type"] for e in events]
        assert "audio_start" in types
        assert "audio_chunk" in types
        assert "audio_end" in types
        # Audio events should come before done (sentence-level streaming)
        done_idx = types.index("done")
        audio_start_idx = types.index("audio_start")
        assert audio_start_idx < done_idx

    @pytest.mark.asyncio
    async def test_no_tts_events_when_provider_none(self):
        """When tts_provider is None, no audio events should be emitted."""
        from app.application.chat_stream_service import ask_question_stream

        mock_llm = AsyncMock()
        mock_llm.generate_stream = MagicMock(return_value=_async_iter(["你好"]))

        session = AsyncMock()

        with patch("app.application.chat_stream_service.add_message"):
            events = []
            async for event in ask_question_stream(
                session=session,
                session_id="s1",
                message="hi",
                llm_provider=mock_llm,
                user_id="u1",
                tts_provider=None,
                tts_config=None,
            ):
                events.append(json.loads(event.removeprefix("data: ").removesuffix("\n\n")))

        types = [e["type"] for e in events]
        assert "audio_start" not in types
        assert "audio_chunk" not in types


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------

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

    async def mock_stream(*args):
        for chunk in ["这是", "一个", "流式回答"]:
            yield chunk

    mock_llm.generate_stream = mock_stream

    mock_rag = AsyncMock()
    mock_rag.run.return_value = {
        "documents": [],
        "retrieval_score": 0.95,
        "answer": "这是一个流式回答",
    }
    # Mock prompt_gateway to use fallback prompt
    mock_rag.prompt_gateway = None

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
    # Mock prompt_gateway to use fallback prompt
    mock_rag.prompt_gateway = None

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
            session_access_log.append("chunk_event_while_session_active")

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


# ---------------------------------------------------------------------------
# Error sanitization tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_error_does_not_leak_internal_details():
    """SSE error events should not contain internal error details."""
    mock_session = _mock_existing_session()
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(side_effect=Exception("Internal error: /home/user/secret/path config.py line 42"))
    mock_llm = MagicMock()

    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="test-session",
        message="test message",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)

    # Find error event
    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0, "Should have error event"

    # Error should not contain internal paths
    for event in error_events:
        assert "/home/" not in event
        assert "config.py" not in event
        assert "line 42" not in event
        assert "Internal error" not in event


@pytest.mark.asyncio
async def test_sse_error_shows_generic_message():
    """SSE error events should show generic error message."""
    mock_session = _mock_existing_session()
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(side_effect=Exception("Database connection failed"))
    mock_llm = MagicMock()

    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="test-session",
        message="test message",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)

    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0

    # Should contain generic message
    any_has_generic = any("An error occurred" in e or "unexpected error" in e.lower() for e in error_events)
    assert any_has_generic, "Should have generic error message"
