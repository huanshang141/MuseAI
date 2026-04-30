"""Sentence-level TTS streaming helpers.

Accumulates LLM text chunks and yields TTS audio events at sentence boundaries,
enabling continuous audio playback as the LLM generates text.

Design notes:
- Xiaomi TTS API is currently in "compatible mode" (returns all audio at once
  after inference completes), but the code uses the streaming API format so it
  will work transparently when true streaming is enabled.
- TTS synthesis runs in a background asyncio task so LLM streaming is not blocked.
- Audio events are yielded from an asyncio.Queue as they become available.
"""
import asyncio
import re
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

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
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig

# Sentence boundary: Chinese/English punctuation followed by optional whitespace,
# or double newline.
_SENTENCE_RE = re.compile(r'(?<=[。！？\.\!\?])\s*|\n\n+')


def extract_sentences(buffer: str) -> tuple[list[str], str]:
    """Split buffer into complete sentences, returning (sentences, remainder).

    A sentence is complete when it ends with 。！？.!? or is followed by
    a double newline. The remainder is any trailing text that doesn't yet
    form a complete sentence.
    """
    sentences: list[str] = []
    last_end = 0
    for match in _SENTENCE_RE.finditer(buffer):
        end = match.end()
        candidate = buffer[last_end:end].strip()
        if candidate:
            sentences.append(candidate)
        last_end = end
    remainder = buffer[last_end:]
    return sentences, remainder


_SENTINEL = object()


async def _tts_worker(
    sentence_queue: asyncio.Queue,
    audio_queue: asyncio.Queue,
    tts_provider: BaseTTSProvider,
    tts_config: TTSConfig,
    schema: str,
) -> None:
    """Background task: read sentences, synthesize, put audio events in queue."""
    if schema == "chat":
        start_fn = sse_chat_audio_start
        chunk_fn = sse_chat_audio_chunk
        end_fn = sse_chat_audio_end
        error_fn = sse_chat_audio_error
    else:
        start_fn = sse_tour_audio_start
        chunk_fn = sse_tour_audio_chunk
        end_fn = sse_tour_audio_end
        error_fn = sse_tour_audio_error

    while True:
        text = await sentence_queue.get()
        if text is _SENTINEL:
            break
        await audio_queue.put(start_fn(voice=tts_config.voice, format="pcm16"))
        try:
            async for audio_chunk in tts_provider.synthesize_stream(text, tts_config):
                await audio_queue.put(chunk_fn(audio_chunk))
            await audio_queue.put(end_fn())
        except Exception as e:
            logger.warning(f"TTS synthesis failed for sentence: {e}")
            await audio_queue.put(error_fn("TTS_ERROR", "语音合成失败"))


_SENTINEL_TUPLE = (None, None)


async def _drain_audio_queue(
    audio_queue: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    """Yield all currently-available audio events from the queue (non-blocking)."""
    while not audio_queue.empty():
        yield audio_queue.get_nowait()


class TTSStreamManager:
    """Manages sentence-level TTS streaming alongside LLM text generation.

    Usage in a streaming function:

        tts_mgr = TTSStreamManager(tts_provider, tts_config, schema="chat")
        async for chunk in llm_stream:
            yield text_event(chunk)
            async for audio_event in tts_mgr.feed(chunk):
                yield audio_event
        async for audio_event in tts_mgr.flush():
            yield audio_event
    """

    def __init__(
        self,
        tts_provider: BaseTTSProvider | None,
        tts_config: TTSConfig | None,
        schema: str = "chat",
    ):
        self.enabled = tts_provider is not None and tts_config is not None
        self.schema = schema
        self._provider = tts_provider
        self._config = tts_config
        self._buffer = ""
        self._sentence_queue: asyncio.Queue = asyncio.Queue()
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def _ensure_worker(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(
                _tts_worker(
                    self._sentence_queue,
                    self._audio_queue,
                    self._provider,
                    self._config,
                    self.schema,
                )
            )

    async def feed(self, text_chunk: str) -> AsyncGenerator[str, None]:
        """Feed an LLM text chunk; yield any ready audio SSE events."""
        if not self.enabled:
            return
        self._buffer += text_chunk
        sentences, self._buffer = extract_sentences(self._buffer)
        for sent in sentences:
            await self._sentence_queue.put(sent)
            self._ensure_worker()
        async for event in _drain_audio_queue(self._audio_queue):
            yield event

    async def flush(self) -> AsyncGenerator[str, None]:
        """Flush remaining text and yield all remaining audio events.

        Must be called after the LLM stream is exhausted.
        """
        if not self.enabled:
            return
        if self._buffer.strip():
            await self._sentence_queue.put(self._buffer.strip())
            self._ensure_worker()
            self._buffer = ""
        if self._task is not None:
            await self._sentence_queue.put(_SENTINEL)
            await self._task
        async for event in _drain_audio_queue(self._audio_queue):
            yield event
