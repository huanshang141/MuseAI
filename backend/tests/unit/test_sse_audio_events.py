from app.application.sse_events import (
    sse_chat_audio_start,
    sse_chat_audio_chunk,
    sse_chat_audio_end,
    sse_chat_audio_error,
    sse_tour_audio_start,
    sse_tour_audio_chunk,
    sse_tour_audio_end,
    sse_tour_audio_error,
)
import json


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
