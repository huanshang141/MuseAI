from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.infra.providers.rerank.base import BaseRerankProvider, RerankRequest, RerankResult, RerankResponse
from app.infra.providers.rerank.mock import MockRerankProvider
from app.infra.providers.rerank.openai import OpenAICompatibleRerankProvider
from app.infra.providers.rerank.siliconflow import SiliconFlowRerankProvider
from app.infra.providers.rerank.factory import create_rerank_provider

__all__ = [
    "RerankRequest",
    "RerankResult",
    "RerankResponse",
    "BaseRerankProvider",
    "OpenAICompatibleRerankProvider",
    "SiliconFlowRerankProvider",
    "MockRerankProvider",
    "create_rerank_provider",
]
