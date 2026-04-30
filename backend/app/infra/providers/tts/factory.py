from loguru import logger

from app.config.settings import Settings
from app.infra.providers.tts.base import BaseTTSProvider
from app.infra.providers.tts.mock import MockTTSProvider
from app.infra.providers.tts.xiaomi import XiaomiTTSProvider


def create_tts_provider(settings: Settings) -> BaseTTSProvider | None:
    if not settings.TTS_ENABLED:
        logger.debug("TTS disabled via config, returning None")
        return None

    provider_type = settings.TTS_PROVIDER.lower()

    if provider_type != "mock" and not settings.TTS_API_KEY:
        logger.debug("TTS not configured (no API key), returning None")
        return None

    if provider_type == "xiaomi":
        masked_key = (
            "***" + settings.TTS_API_KEY[-4:]
            if len(settings.TTS_API_KEY) > 4
            else "***"
        )
        logger.info(
            f"Creating Xiaomi TTS provider: model={settings.TTS_MODEL}, "
            f"key={masked_key}"
        )
        return XiaomiTTSProvider(
            base_url=settings.TTS_BASE_URL,
            api_key=settings.TTS_API_KEY,
            model=settings.TTS_MODEL,
            timeout=settings.TTS_TIMEOUT,
        )
    elif provider_type == "mock":
        logger.debug("Creating Mock TTS provider")
        return MockTTSProvider()
    else:
        logger.warning(f"Unknown TTS provider: {provider_type}, returning None")
        return None
