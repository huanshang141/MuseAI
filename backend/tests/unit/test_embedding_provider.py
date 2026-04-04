import pytest
from unittest.mock import patch, MagicMock
from app.infra.providers.embedding import OllamaEmbeddingProvider


class MockResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class MockAsyncClient:
    def __init__(self, response_data=None):
        self._response_data = response_data
        self.post_count = 0
    
    async def post(self, *args, **kwargs):
        self.post_count += 1
        return MockResponse(self._response_data)
    
    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_embed_single_text():
    response_data = {"embedding": [0.1] * 768}
    mock_client = MockAsyncClient(response_data)

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        embedding = await provider.embed("test text")

        assert len(embedding) == 768
        assert all(v == 0.1 for v in embedding)
        assert mock_client.post_count == 1


@pytest.mark.asyncio
async def test_embed_batch_concurrent():
    response_data = {"embedding": [0.1] * 768}
    mock_client = MockAsyncClient(response_data)

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        texts = ["text 1", "text 2", "text 3"]
        embeddings = await provider.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 768 for e in embeddings)
        assert mock_client.post_count == 3


@pytest.mark.asyncio
async def test_embed_dimension_validation():
    response_data = {"embedding": [0.1] * 512}
    mock_client = MockAsyncClient(response_data)

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        
        with pytest.raises(ValueError, match="Embedding dimension mismatch: expected 768, got 512"):
            await provider.embed("test text")


@pytest.mark.asyncio
async def test_timeout_parameter():
    mock_client = MockAsyncClient({"embedding": [0.1] * 768})

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(
            base_url="http://localhost:11434",
            model="qwen3-embedding:8b",
            dims=768,
            timeout=30.0
        )

        assert provider.timeout == 30.0
        mock_client_class.assert_called_once_with(timeout=30.0)


@pytest.mark.asyncio
async def test_close_method():
    mock_client = MagicMock()
    mock_client.aclose = MagicMock(return_value=None)
    mock_client.aclose.return_value = None
    
    async def mock_aclose():
        pass
    
    mock_client.aclose = mock_aclose

    with patch("app.infra.providers.embedding.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_client

        provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="qwen3-embedding:8b", dims=768)
        await provider.close()
