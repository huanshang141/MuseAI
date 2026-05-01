from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from app.application.tts_service import TTSService
from app.domain.entities import Prompt
from app.domain.value_objects import PromptId
from app.infra.providers.tts.mock import MockTTSProvider


def _make_prompt(
    key: str,
    content: str,
    voice: str | None = None,
    voice_description: str | None = None,
) -> Prompt:
    variables = []
    if voice:
        variables.append({"name": "__voice__", "description": voice})
    if voice_description:
        variables.append({"name": "__voice_description__", "description": voice_description})
    return Prompt(
        id=PromptId(value=f"prompt-{key}"),
        key=key,
        name=f"Test {key}",
        description=None,
        category="tts",
        content=content,
        variables=variables,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestTTSService:
    def _make_service(self, prompt_gateway=None):
        provider = MockTTSProvider()
        if prompt_gateway is None:
            prompt_gateway = AsyncMock()
            prompt_gateway.get_entity = AsyncMock(return_value=None)
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
    async def test_get_tour_tts_config_with_persona_voice(self):
        gateway = AsyncMock()
        prompt = _make_prompt("tour_tts_persona_a", "用沉稳专业的语气讲解", voice="白桦")
        gateway.get_entity = AsyncMock(return_value=prompt)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("A")
        assert config.voice == "白桦"
        assert config.style == "用沉稳专业的语气讲解"
        gateway.get_entity.assert_called_once_with("tour_tts_persona_a")

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_to_default_voice(self):
        gateway = AsyncMock()
        prompt = _make_prompt("tour_tts_persona_a", "用沉稳专业的语气讲解")
        gateway.get_entity = AsyncMock(return_value=prompt)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("A")
        assert config.voice == "冰糖"
        assert config.style == "用沉稳专业的语气讲解"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_fallback_when_no_prompt(self):
        gateway = AsyncMock()
        gateway.get_entity = AsyncMock(return_value=None)
        service = self._make_service(prompt_gateway=gateway)

        config = await service.get_tour_tts_config("B")
        assert config.voice == "冰糖"
        assert config.style == "用温和亲切的语气讲解，语速适中"

    @pytest.mark.asyncio
    async def test_get_tour_tts_config_all_personas(self):
        for persona, voice in [("A", "白桦"), ("B", "苏打"), ("C", "茉莉")]:
            gateway = AsyncMock()
            prompt = _make_prompt(
                f"tour_tts_persona_{persona.lower()}",
                f"Style for {persona}",
                voice=voice,
            )
            gateway.get_entity = AsyncMock(return_value=prompt)
            service = self._make_service(prompt_gateway=gateway)

            config = await service.get_tour_tts_config(persona)
            assert config.voice == voice
            assert config.style == f"Style for {persona}"
