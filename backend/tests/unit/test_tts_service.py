from unittest.mock import AsyncMock

import pytest
from app.application.tts_service import TTSService
from app.infra.providers.tts.mock import MockTTSProvider


class TestTTSService:
    def _make_service(self, prompt_gateway=None):
        provider = MockTTSProvider()
        if prompt_gateway is None:
            prompt_gateway = AsyncMock()
            prompt_gateway.get = AsyncMock(return_value=None)
        return TTSService(provider=provider, prompt_gateway=prompt_gateway)

    def test_get_qa_tts_config_default_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config()
        assert config.voice == "冰糖"
        assert config.style == "用清晰专业的语气讲解，语速适中"

    def test_get_qa_tts_config_user_voice(self):
        service = self._make_service()
        config = service.get_qa_tts_config(user_voice="苏打")
        assert config.voice == "苏打"
        assert config.style == "用清晰专业的语气讲解，语速适中"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_with_prompt(self):
        gateway = AsyncMock()
        gateway.get = AsyncMock(return_value="用沉稳专业的语气讲解")
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("a")
        assert config.voice == "冰糖"
        assert config.style == "用沉稳专业的语气讲解"
        gateway.get.assert_called_once_with("tour_tts_persona_a")

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_style(self):
        gateway = AsyncMock()
        gateway.get = AsyncMock(return_value=None)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("b")
        assert config.style == "用温和亲切的语气讲解，语速适中"
