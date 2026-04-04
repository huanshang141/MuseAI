from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.domain.exceptions import LLMError
from app.infra.providers.llm import LLMResponse, OpenAICompatibleProvider


class TestOpenAICompatibleProvider:
    @pytest.mark.asyncio
    async def test_generate_returns_structured_response(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, how can I help?"
        mock_response.model = "gemini-2.5-flash"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.generate(messages)

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, how can I help?"
        assert result.model == "gemini-2.5-flash"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_generate_stream_yields_chunks(self):
        mock_client = AsyncMock()

        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=" there"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
            ]
            for chunk in chunks:
                yield chunk

        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            messages = [{"role": "user", "content": "Hi"}]
            chunks = []
            async for chunk in provider.generate_stream(messages):
                chunks.append(chunk)

        assert chunks == ["Hello", " there", "!"]

    @pytest.mark.asyncio
    async def test_generate_wraps_errors_in_llm_error(self):
        from openai import APIConnectionError

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(message="Connection failed", request=MagicMock())
        )

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            messages = [{"role": "user", "content": "Hello"}]

            with pytest.raises(LLMError):
                await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_stream_wraps_errors_in_llm_error(self):
        from openai import APIConnectionError

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(message="Connection failed", request=MagicMock())
        )

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            messages = [{"role": "user", "content": "Hi"}]

            with pytest.raises(LLMError):
                async for _ in provider.generate_stream(messages):
                    pass

    @pytest.mark.asyncio
    async def test_generate_handles_none_content(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.model = "gemini-2.5-flash"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 0
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.generate(messages)

        assert result.content == ""

    @pytest.mark.asyncio
    async def test_generate_stream_handles_none_content(self):
        mock_client = AsyncMock()

        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hi"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
            ]
            for chunk in chunks:
                yield chunk

        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            messages = [{"role": "user", "content": "Hi"}]
            chunks = []
            async for chunk in provider.generate_stream(messages):
                chunks.append(chunk)

        assert chunks == ["Hi", "!"]
