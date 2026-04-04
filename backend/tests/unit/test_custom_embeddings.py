import pytest
from unittest.mock import AsyncMock, patch
from app.infra.langchain.embeddings import CustomOllamaEmbeddings


@pytest.mark.asyncio
async def test_embeddings_embed_query():
    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="test-model",
        dims=768,
    )

    with patch.object(embeddings, "_get_provider") as mock_provider:
        provider = AsyncMock()
        provider.embed = AsyncMock(return_value=[0.1] * 768)
        mock_provider.return_value = provider

        result = await embeddings.aembed_query("test query")

        assert len(result) == 768
        assert all(v == 0.1 for v in result)


@pytest.mark.asyncio
async def test_embeddings_embed_documents():
    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="test-model",
        dims=768,
    )

    with patch.object(embeddings, "_get_provider") as mock_provider:
        provider = AsyncMock()
        provider.embed_batch = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
        mock_provider.return_value = provider

        result = await embeddings.aembed_documents(["text1", "text2"])

        assert len(result) == 2
        assert len(result[0]) == 768
