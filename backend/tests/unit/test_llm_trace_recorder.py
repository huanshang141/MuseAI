# backend/tests/unit/test_llm_trace_recorder.py
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.llm_trace.context import set_trace_context
from app.application.llm_trace.recorder import LLMTraceRecorder


@pytest.fixture
def mock_session_maker():
    mock_session = AsyncMock()
    mock_maker = MagicMock()
    mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_maker, mock_session


@pytest.mark.asyncio
async def test_record_call_success(mock_session_maker):
    mock_maker, mock_session = mock_session_maker
    recorder = LLMTraceRecorder(session_maker=mock_maker)
    started = datetime.now(UTC)
    ended = datetime.now(UTC)
    with set_trace_context(request_id="req-1", trace_id="trace-1", source="chat_stream"):
        with patch("app.application.llm_trace.repository.LLMTraceEventRepository") as MockRepo:
            mock_repo = AsyncMock()
            MockRepo.return_value = mock_repo
            await recorder.record_call_success(
                call_id="call-1",
                response_payload={"choices": [{"message": {"content": "hi"}}]},
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                started_at=started,
                ended_at=ended,
            )
            mock_repo.create_event.assert_awaited_once()
            event = mock_repo.create_event.call_args[0][0]
            assert event["call_id"] == "call-1"
            assert event["status"] == "success"
            assert event["request_id"] == "req-1"
            assert event["trace_id"] == "trace-1"
            assert event["source"] == "chat_stream"
            assert event["prompt_tokens"] == 10
            assert event["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_record_call_error(mock_session_maker):
    mock_maker, mock_session = mock_session_maker
    recorder = LLMTraceRecorder(session_maker=mock_maker)
    started = datetime.now(UTC)
    ended = datetime.now(UTC)
    with patch("app.application.llm_trace.repository.LLMTraceEventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        await recorder.record_call_error(
            call_id="call-2",
            error_type="TimeoutError",
            error_message="Connection timed out",
            started_at=started,
            ended_at=ended,
        )
        mock_repo.create_event.assert_awaited_once()
        event = mock_repo.create_event.call_args[0][0]
        assert event["call_id"] == "call-2"
        assert event["status"] == "error"
        assert event["error_type"] == "TimeoutError"


@pytest.mark.asyncio
async def test_record_call_once(mock_session_maker):
    mock_maker, mock_session = mock_session_maker
    recorder = LLMTraceRecorder(session_maker=mock_maker)
    started = datetime.now(UTC)
    with patch("app.application.llm_trace.repository.LLMTraceEventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        await recorder.record_call_once(
            call_id="call-3",
            provider="openai-compatible",
            model="gpt-4",
            status="success",
            base_url="https://api.openai.com/v1",
            request_payload={"messages": [{"role": "user", "content": "hello"}]},
            response_payload={"choices": [{"message": {"content": "world"}}]},
            started_at=started,
        )
        mock_repo.create_event.assert_awaited_once()
        event = mock_repo.create_event.call_args[0][0]
        assert event["provider"] == "openai-compatible"
        assert event["model"] == "gpt-4"
        assert event["request_readable"].startswith("Model:")
        assert event["response_readable"].startswith("  1.")


@pytest.mark.asyncio
async def test_record_repo_exception_does_not_raise(mock_session_maker):
    mock_maker, mock_session = mock_session_maker
    recorder = LLMTraceRecorder(session_maker=mock_maker)
    with patch("app.application.llm_trace.repository.LLMTraceEventRepository") as MockRepo:
        mock_repo = AsyncMock()
        mock_repo.create_event.side_effect = RuntimeError("db down")
        MockRepo.return_value = mock_repo
        await recorder.record_call_once(
            call_id="call-4",
            provider="p",
            model="m",
            status="success",
        )


@pytest.mark.asyncio
async def test_record_without_session_maker():
    recorder = LLMTraceRecorder(session_maker=None)
    await recorder.record_call_once(
        call_id="call-5",
        provider="p",
        model="m",
        status="success",
    )
