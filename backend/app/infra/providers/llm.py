import time
from collections.abc import AsyncGenerator
from typing import Any, Protocol

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from app.domain.exceptions import LLMError


class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int


class LLMProvider(Protocol):
    async def generate(self, messages: list[dict[str, Any]]) -> LLMResponse: ...

    async def generate_stream(self, messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]: ...


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.model = model
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    async def generate(self, messages: list[dict[str, Any]]) -> LLMResponse:
        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(model=self.model, messages=messages)  # type: ignore[arg-type]
            duration_ms = int((time.time() - start_time) * 1000)

            content = response.choices[0].message.content or ""
            usage = response.usage

            return LLMResponse(
                content=content,
                model=response.model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                duration_ms=duration_ms,
            )
        except APIError as e:
            raise LLMError(str(e)) from e

    async def generate_stream(self, messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(model=self.model, messages=messages, stream=True)  # type: ignore[arg-type]
            async for chunk in stream:  # type: ignore[union-attr]
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content
        except APIError as e:
            raise LLMError(str(e)) from e
