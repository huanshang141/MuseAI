# backend/tests/unit/test_embedding_lifecycle.py

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def test_ollama_provider_supports_external_client():
    """OllamaEmbeddingProvider should accept external httpx client."""
    from app.infra.providers.embedding import OllamaEmbeddingProvider
    import httpx

    external_client = httpx.AsyncClient()
    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dims=768,
        client=external_client,  # Should accept external client
    )

    assert provider.client is external_client


def test_custom_embeddings_reuses_provider():
    """CustomOllamaEmbeddings should not create new provider each call."""
    from app.infra.langchain.embeddings import CustomOllamaEmbeddings

    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dims=768,
    )

    # Get provider twice
    provider1 = embeddings._get_provider()
    provider2 = embeddings._get_provider()

    # Should be same instance
    assert provider1 is provider2


@pytest.mark.asyncio
async def test_embeddings_close_provider():
    """CustomOllamaEmbeddings should close provider on demand."""
    from app.infra.langchain.embeddings import CustomOllamaEmbeddings

    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dims=768,
    )

    provider = embeddings._get_provider()
    provider.close = AsyncMock()

    await embeddings.close()

    provider.close.assert_called_once()
