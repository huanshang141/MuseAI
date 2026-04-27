import asyncio
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Protocol, Self

from loguru import logger
from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from app.config.settings import Settings
from app.domain.exceptions import LLMError


class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int


class LLMProvider(Protocol):
    async def generate(self, messages: list[dict[str, Any]]) -> LLMResponse: ...

    def generate_stream(self, messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]: ...


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        trace_recorder: Any | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.trace_recorder = trace_recorder

    @classmethod
    def from_settings(cls, settings: Settings, trace_recorder: Any | None = None) -> Self:
        return cls(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            trace_recorder=trace_recorder,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self.client.close()

    async def generate(self, messages: list[dict[str, Any]]) -> LLMResponse:
        start_time = time.time()
        last_error: APIError | None = None
        call_id = f"llm-{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC)

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(model=self.model, messages=messages)  # type: ignore[arg-type]
                duration_ms = int((time.time() - start_time) * 1000)
                ended_at = datetime.now(UTC)

                content = response.choices[0].message.content or ""
                usage = response.usage

                if usage is None:
                    logger.warning("LLM response usage is None, defaulting token counts to 0")

                if self.trace_recorder is not None:
                    await self.trace_recorder.record_call_once(
                        call_id=call_id,
                        provider="openai-compatible",
                        model=self.model,
                        status="success",
                        source="openai-compatible",
                        base_url=self.base_url,
                        request_payload={"model": self.model, "messages": messages},
                        response_payload={
                            "model": response.model,
                            "choices": [{"message": {"content": content}}],
                            "usage": {
                                "prompt_tokens": usage.prompt_tokens if usage else 0,
                                "completion_tokens": usage.completion_tokens if usage else 0,
                                "total_tokens": usage.total_tokens if usage else 0,
                            },
                        },
                        prompt_tokens=usage.prompt_tokens if usage else 0,
                        completion_tokens=usage.completion_tokens if usage else 0,
                        total_tokens=usage.total_tokens if usage else 0,
                        started_at=started_at,
                        ended_at=ended_at,
                    )

                return LLMResponse(
                    content=content,
                    model=response.model,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    duration_ms=duration_ms,
                )
            except APIError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))

        ended_at = datetime.now(UTC)
        if self.trace_recorder is not None:
            await self.trace_recorder.record_call_error(
                call_id=call_id,
                error_type=type(last_error).__name__ if last_error else "UnknownError",
                error_message=str(last_error) if last_error else "unknown error",
                source="openai-compatible",
                started_at=started_at,
                ended_at=ended_at,
            )
        raise LLMError(str(last_error)) from last_error

    async def generate_stream(self, messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
        call_id = f"llm-{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC)
        chunks: list[str] = []
        try:
            stream = await self.client.chat.completions.create(model=self.model, messages=messages, stream=True)  # type: ignore[arg-type]
            async for chunk in stream:  # type: ignore[union-attr]
                content = chunk.choices[0].delta.content
                if content is not None:
                    chunks.append(content)
                    yield content
            ended_at = datetime.now(UTC)
            if self.trace_recorder is not None:
                await self.trace_recorder.record_call_once(
                    call_id=call_id,
                    provider="openai-compatible",
                    model=self.model,
                    status="success",
                    source="openai-compatible",
                    base_url=self.base_url,
                    request_payload={"model": self.model, "messages": messages},
                    response_payload={"content": "".join(chunks)},
                    started_at=started_at,
                    ended_at=ended_at,
                )
        except APIError as e:
            ended_at = datetime.now(UTC)
            if self.trace_recorder is not None:
                await self.trace_recorder.record_call_error(
                    call_id=call_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    source="openai-compatible",
                    started_at=started_at,
                    ended_at=ended_at,
                )
            raise LLMError(str(e)) from e
