import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Protocol, Self

from loguru import logger
from openai import APIError, APIStatusError, AsyncOpenAI
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
        default_headers: dict[str, str] | None = None,
        trace_recorder: Any | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            default_headers=default_headers or None,
        )
        self.trace_recorder = trace_recorder

    @classmethod
    def from_settings(cls, settings: Settings, trace_recorder: Any | None = None) -> Self:
        default_headers: dict[str, str] | None = None
        if settings.LLM_HEADERS:
            try:
                default_headers = json.loads(settings.LLM_HEADERS)
            except json.JSONDecodeError:
                logger.warning("LLM_HEADERS is not valid JSON, ignoring: {}", settings.LLM_HEADERS)
        return cls(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            default_headers=default_headers,
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

    def _log_api_error(self, error: APIError, call_id: str, attempt: int | None = None) -> None:
        """Log detailed API error info for debugging third-party provider issues."""
        attempt_str = f" attempt={attempt}" if attempt is not None else ""
        logger.warning(
            "LLM API error[{call_id}]{attempt}: type={err_type}, message={msg}",
            call_id=call_id,
            attempt=attempt_str,
            err_type=type(error).__name__,
            msg=str(error),
        )
        if isinstance(error, APIStatusError):
            logger.debug(
                "LLM API status error detail[{call_id}]: status={status}, headers={headers}, body={body}",
                call_id=call_id,
                status=error.status_code,
                headers=dict(error.response.headers) if error.response else None,
                body=error.body,
            )
        else:
            logger.debug(
                "LLM API error detail[{call_id}]: body={body}",
                call_id=call_id,
                body=getattr(error, "body", None),
            )

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

                if not response.choices:
                    raise LLMError("LLM returned empty choices in response")
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
                self._log_api_error(e, call_id, attempt)
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
                if not chunk.choices:
                    continue
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
            self._log_api_error(e, call_id)
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
