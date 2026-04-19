from loguru import logger

from app.config.settings import Settings
from app.infra.providers.rerank.base import BaseRerankProvider
from app.infra.providers.rerank.mock import MockRerankProvider
from app.infra.providers.rerank.openai import OpenAICompatibleRerankProvider
from app.infra.providers.rerank.siliconflow import SiliconFlowRerankProvider


def create_rerank_provider(settings: Settings) -> BaseRerankProvider | None:
    masked_key = (
        "***" + settings.RERANK_API_KEY[-4:]
        if settings.RERANK_API_KEY and len(settings.RERANK_API_KEY) > 4
        else "***" if settings.RERANK_API_KEY
        else "None"
    )
    logger.info(
        f"create_rerank_provider called: RERANK_PROVIDER={settings.RERANK_PROVIDER}, "
        f"RERANK_API_KEY={masked_key}, RERANK_MODEL={settings.RERANK_MODEL}"
    )

    provider_type = settings.RERANK_PROVIDER.lower()

    if provider_type != "mock" and not settings.RERANK_API_KEY:
        logger.debug("Rerank not configured (no API key), returning None")
        return None

    if provider_type == "siliconflow":
        logger.info(f"Creating SiliconFlow rerank provider with model: {settings.RERANK_MODEL}")
        provider = SiliconFlowRerankProvider(
            api_key=settings.RERANK_API_KEY,
            model=settings.RERANK_MODEL,
        )
        logger.info(f"SiliconFlow rerank provider created successfully, base_url: {provider.base_url}")
        return provider
    elif provider_type in ("openai", "cohere", "custom"):
        logger.info(f"Creating OpenAI-compatible rerank provider: {provider_type}")
        if not settings.RERANK_BASE_URL:
            logger.warning(f"RERANK_BASE_URL not set for provider: {provider_type}")
            return None
        return OpenAICompatibleRerankProvider(
            base_url=settings.RERANK_BASE_URL,
            api_key=settings.RERANK_API_KEY,
            model=settings.RERANK_MODEL,
        )
    elif provider_type == "mock":
        logger.debug("Creating Mock rerank provider")
        return MockRerankProvider()
    else:
        logger.warning(f"Unknown rerank provider: {provider_type}, returning None")
        return None
