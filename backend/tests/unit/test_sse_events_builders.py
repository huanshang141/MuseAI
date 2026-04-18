"""Byte-exact tests for SSE event builders.

The frontend (useChat.js, useTour.js) parses the exact strings these
builders produce. Any whitespace or key-order change is a wire-protocol
break — hence the strict string equality.
"""
import json


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
