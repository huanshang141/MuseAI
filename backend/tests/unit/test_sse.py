"""Byte-exact tests for SSE event builders and audio events.

The frontend (useChat.js, useTour.js) parses the exact strings these
builders produce. Any whitespace or key-order change is a wire-protocol
break — hence the strict string equality.
"""
import json

from app.application.sse_events import (
    sse_chat_audio_chunk,
    sse_chat_audio_end,
    sse_chat_audio_error,
    sse_chat_audio_start,
    sse_tour_audio_chunk,
    sse_tour_audio_end,
    sse_tour_audio_error,
    sse_tour_audio_start,
)


def test_sse_chat_event_basic():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("chunk", stage="generate", content="hello")

    expected = f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': 'hello'})}\n\n"
    assert result == expected


def test_sse_chat_event_error():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("error", code="LLM_ERROR", message="boom")
    expected = f"data: {json.dumps({'type': 'error', 'code': 'LLM_ERROR', 'message': 'boom'})}\n\n"
    assert result == expected


def test_sse_chat_event_rag_step():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("rag_step", step="retrieve", status="running", message="...")
    payload = {
        'type': 'rag_step', 'step': 'retrieve',
        'status': 'running', 'message': '...',
    }
    expected = f"data: {json.dumps(payload)}\n\n"
    assert result == expected


def test_sse_chat_event_done_with_list_field():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("done", stage="generate", trace_id="t-1", chunks=["a", "b"])
    expected = (
        f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': 't-1', 'chunks': ['a', 'b']})}\n\n"
    )
    assert result == expected


def test_sse_chat_event_preserves_insertion_order():
    from app.application.sse_events import sse_chat_event

    result = sse_chat_event("thinking", stage="retrieve", content="x")
    assert result.startswith('data: {"type": "thinking"')


def test_sse_tour_event_chunk_with_data_wrapper():
    from app.application.sse_events import sse_tour_event

    result = sse_tour_event("chunk", data={"content": "hello"})
    expected = f"data: {json.dumps({'event': 'chunk', 'data': {'content': 'hello'}})}\n\n"
    assert result == expected


def test_sse_tour_event_done_flat_fields():
    from app.application.sse_events import sse_tour_event

    result = sse_tour_event("done", trace_id="t-1", is_ceramic_question=True)
    expected = f"data: {json.dumps({'event': 'done', 'trace_id': 't-1', 'is_ceramic_question': True})}\n\n"
    assert result == expected


def test_sse_tour_event_error_with_data_wrapper():
    from app.application.sse_events import sse_tour_event

    result = sse_tour_event("error", data={"code": "llm_error", "message": "AI导览暂时不可用，请稍后再试"})
    payload = {
        'event': 'error',
        'data': {'code': 'llm_error', 'message': 'AI导览暂时不可用，请稍后再试'},
    }
    expected_ascii = f"data: {json.dumps(payload)}\n\n"
    assert result == expected_ascii


class TestChatAudioEvents:
    def test_audio_start(self):
        result = sse_chat_audio_start(voice="冰糖", format="pcm16")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_start"
        assert payload["voice"] == "冰糖"
        assert payload["format"] == "pcm16"

    def test_audio_chunk(self):
        result = sse_chat_audio_chunk(data="dGVzdA==")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_chunk"
        assert payload["data"] == "dGVzdA=="

    def test_audio_end(self):
        result = sse_chat_audio_end()
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_end"

    def test_audio_error(self):
        result = sse_chat_audio_error(code="TTS_ERROR", message="failed")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["type"] == "audio_error"
        assert payload["code"] == "TTS_ERROR"


class TestTourAudioEvents:
    def test_audio_start(self):
        result = sse_tour_audio_start(voice="冰糖", format="pcm16")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_start"
        assert payload["voice"] == "冰糖"

    def test_audio_chunk(self):
        result = sse_tour_audio_chunk(data="dGVzdA==")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_chunk"
        assert payload["data"] == "dGVzdA=="

    def test_audio_end(self):
        result = sse_tour_audio_end()
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_end"

    def test_audio_error(self):
        result = sse_tour_audio_error(code="TTS_ERROR", message="failed")
        payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
        assert payload["event"] == "audio_error"
