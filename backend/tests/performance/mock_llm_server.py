"""Mock LLM server for performance testing.

Simulates an OpenAI-compatible API with configurable delays.
"""
import asyncio
import random
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import TestConfig, get_config

app = FastAPI(title="Mock LLM Server")

# Global config (can be overridden)
config = get_config()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int | None = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: dict[str, int]


class StreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[dict[str, Any]]


def generate_mock_response(query: str, length: int | None = None) -> str:
    """Generate a mock response text."""
    length = length or config.mock_llm_response_length

    # Museum-themed mock responses
    templates = [
        "根据您的询问，这件展品是博物馆的重要藏品之一。它展示了精湛的工艺和深厚的历史文化价值。",
        "这是一个非常有趣的问题。关于这件文物，我们可以从多个角度来理解它的历史意义。",
        "感谢您的提问。这件藏品代表了其时代最高水平的技术和艺术成就，值得我们深入了解。",
        "您提到的这个话题很有深度。让我为您详细介绍这件展品的背景和特点。",
        "这是一件极具研究价值的文物。它的发现为我们理解那个时代提供了重要线索。",
    ]

    base_response = random.choice(templates)
    # Pad to desired length
    if len(base_response) < length:
        padding = " 详细信息包括展品的历史背景、制作工艺、文化意义等方面。" * ((length // 50) + 1)
        base_response = base_response + padding

    return base_response[:length]


async def stream_response(
    response_id: str,
    model: str,
    content: str,
    chunk_size: int | None = None,
    min_delay_ms: int | None = None,
    max_delay_ms: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream response in SSE format with realistic delays."""
    chunk_size = chunk_size or config.mock_llm_chunk_size
    min_delay = (min_delay_ms or config.mock_llm_min_delay_ms) / 1000
    max_delay = (max_delay_ms or config.mock_llm_max_delay_ms) / 1000

    created = int(time.time())

    # Split content into chunks
    chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]

    for i, chunk in enumerate(chunks):
        # Simulate processing delay
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

        # Build SSE chunk
        delta = {"content": chunk} if i < len(chunks) - 1 else {"content": chunk, "finish_reason": "stop"}

        chunk_data = StreamChunk(
            id=response_id,
            created=created,
            model=model,
            choices=[{"index": 0, "delta": delta, "finish_reason": None if i < len(chunks) - 1 else "stop"}],
        )

        yield f"data: {chunk_data.model_dump_json()}\n\n"

    # Send final [DONE] marker
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> StreamingResponse | ChatCompletionResponse:
    """Handle chat completion requests (OpenAI-compatible)."""
    response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created = int(time.time())

    # Get user query
    user_message = request.messages[-1].content if request.messages else ""

    # Generate mock response
    response_content = generate_mock_response(user_message)

    if request.stream:
        # Streaming response
        return StreamingResponse(
            stream_response(response_id, request.model, response_content),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    else:
        # Non-streaming response
        # Simulate processing delay
        await asyncio.sleep(random.uniform(0.5, 1.5))

        return ChatCompletionResponse(
            id=response_id,
            created=created,
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_content),
                )
            ],
            usage={"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-llm"}


def run_server(port: int | None = None) -> None:
    """Run the mock LLM server."""
    import uvicorn

    port = port or config.mock_llm_port
    uvicorn.run(app, host=config.mock_llm_host, port=port)


if __name__ == "__main__":
    run_server()
