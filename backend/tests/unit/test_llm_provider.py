from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config.settings import Settings
from app.domain.exceptions import LLMError
from app.infra.providers.llm import LLMResponse, OpenAICompatibleProvider
from loguru import logger


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
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
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
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
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
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
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
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
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
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
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
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
            )
            messages = [{"role": "user", "content": "Hi"}]
            chunks = []
            async for chunk in provider.generate_stream(messages):
                chunks.append(chunk)

        assert chunks == ["Hi", "!"]

    @pytest.mark.asyncio
    async def test_from_settings_creates_provider(self):
        mock_settings = MagicMock(spec=Settings)
        mock_settings.LLM_BASE_URL = "https://api.example.com/v1"
        mock_settings.LLM_API_KEY = "test-api-key"
        mock_settings.LLM_MODEL = "gemini-2.5-flash"
        mock_settings.LLM_HEADERS = ""

        with patch("app.infra.providers.llm.AsyncOpenAI") as mock_client_class:
            provider = OpenAICompatibleProvider.from_settings(mock_settings)

            assert provider.model == "gemini-2.5-flash"
            mock_client_class.assert_called_once_with(
                base_url="https://api.example.com/v1",
                api_key="test-api-key",
                timeout=60.0,
                default_headers=None,
            )

    @pytest.mark.asyncio
    async def test_generate_retries_on_error(self):
        from openai import APIConnectionError

        mock_client = AsyncMock()
        call_count = 0

        async def increment_and_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIConnectionError(message="Connection failed", request=MagicMock())
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Success"
            mock_response.model = "gemini-2.5-flash"
            mock_response.usage.prompt_tokens = 5
            mock_response.usage.completion_tokens = 5
            return mock_response

        mock_client.chat.completions.create = increment_and_fail

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1",
                api_key="test-key",
                model="gemini-2.5-flash",
                max_retries=3,
                retry_delay=0.01,
            )
            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.generate(messages)

        assert result.content == "Success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generate_warns_on_none_usage(self, caplog: pytest.LogCaptureFixture, tmp_path):
        """Test that a warning is logged when usage is None."""


        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.model = "gemini-2.5-flash"
        mock_response.usage = None
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Setup loguru to capture warnings to a file
        log_file = tmp_path / "test.log"
        logger.add(str(log_file), level="WARNING", format="{message}")

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
            )
            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.generate(messages)

        # Read log file and check for warning
        log_content = log_file.read_text()
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert "LLM response usage is None" in log_content

    @pytest.mark.asyncio
    async def test_close_method(self):
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            provider = OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash"
            )
            await provider.close()

        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello"
        mock_response.model = "gemini-2.5-flash"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 5
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        with patch("app.infra.providers.llm.AsyncOpenAI", return_value=mock_client):
            async with OpenAICompatibleProvider(
                base_url="https://api.example.com/v1", api_key="test-key", model="gemini-2.5-flash", max_retries=1
            ) as provider:
                result = await provider.generate([{"role": "user", "content": "Hi"}])
                assert result.content == "Hello"

        mock_client.close.assert_called_once()

    def test_llm_error_has_status_code_503(self):
        error = LLMError("test error")
        assert error.status_code == 503
