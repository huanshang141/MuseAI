from app.application.ports.prompt_gateway import PromptGateway
from app.config.settings import get_settings
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig


class TTSService:
    def __init__(self, provider: BaseTTSProvider, prompt_gateway: PromptGateway):
        self.provider = provider
        self.prompt_gateway = prompt_gateway

    def get_qa_tts_config(self, user_voice: str | None = None) -> TTSConfig:
        settings = get_settings()
        return TTSConfig(
            voice=user_voice or settings.TTS_DEFAULT_VOICE,
            style="用清晰专业的语气讲解，语速适中",
        )

    async def get_tour_tts_config(self, persona: str) -> TTSConfig:
        settings = get_settings()
        prompt_key = f"tour_tts_persona_{persona}"
        style = await self.prompt_gateway.get(prompt_key)
        return TTSConfig(
            voice=settings.TTS_DEFAULT_VOICE,
            style=style or "用温和亲切的语气讲解，语速适中",
        )
