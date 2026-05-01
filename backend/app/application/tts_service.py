from loguru import logger

from app.application.ports.prompt_gateway import PromptGateway
from app.config.settings import get_settings
from app.infra.providers.tts.base import BaseTTSProvider, TTSConfig

VOICE_DESCRIPTION_KEY = "__voice_description__"
VOICE_KEY = "__voice__"


def extract_voice_description(variables: list[dict[str, str]]) -> str | None:
    """Extract voice_description from the variables metadata list."""
    for var in variables:
        if var.get("name") == VOICE_DESCRIPTION_KEY:
            return var.get("description", "")
    return None


def extract_voice(variables: list[dict[str, str]]) -> str | None:
    """Extract preset voice name from the variables metadata list."""
    for var in variables:
        if var.get("name") == VOICE_KEY:
            return var.get("description", "")
    return None


def store_voice_description(
    variables: list[dict[str, str]], voice_description: str
) -> list[dict[str, str]]:
    """Store voice_description in the variables metadata list."""
    cleaned = [v for v in variables if v.get("name") != VOICE_DESCRIPTION_KEY]
    if voice_description:
        cleaned.append({"name": VOICE_DESCRIPTION_KEY, "description": voice_description})
    return cleaned


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
        prompt_key = f"tour_tts_persona_{persona.lower()}"
        prompt = await self.prompt_gateway.get_entity(prompt_key)
        if prompt:
            logger.debug(f"TTS prompt found: key={prompt_key}, variables={prompt.variables}")
        else:
            logger.warning(f"TTS prompt NOT found: key={prompt_key}")
        style = prompt.content if prompt else None
        voice = extract_voice(prompt.variables) if prompt else None
        final_voice = voice or settings.TTS_DEFAULT_VOICE
        logger.debug(f"TTS config: persona={persona}, prompt_key={prompt_key}, voice={voice}, final_voice={final_voice}")
        return TTSConfig(
            voice=final_voice,
            style=style or "用温和亲切的语气讲解，语速适中",
        )
