import pytest
from unittest.mock import patch
from app.infra.providers.embedding import OllamaEmbeddingProvider


class MockResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class MockAsyncClient:
    def __init__(self, response_data):
        self._response_data = response_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, *args, **kwargs):
        return MockResponse(self._response_data)


@pytest.mark.asyncio
async def test_embed_single_text():
    provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)

    response_data = {"embedding": [0.1] * 768}

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = MockAsyncClient(response_data)

        embedding = await provider.embed("test text")

        assert len(embedding) == 768
        assert all(v == 0.1 for v in embedding)


@pytest.mark.asyncio
async def test_embed_batch():
    provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)

    response_data = {"embedding": [0.1] * 768}

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = MockAsyncClient(response_data)

        texts = ["text 1", "text 2", "text 3"]
        embeddings = await provider.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 768 for e in embeddings)
