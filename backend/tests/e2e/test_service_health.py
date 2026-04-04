# backend/tests/e2e/test_service_health.py
import pytest

from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import get_session_maker, get_session
from app.infra.providers.embedding import OllamaEmbeddingProvider


@pytest.mark.asyncio
async def test_postgres_connection(test_settings):
    session_maker = get_session_maker(test_settings.DATABASE_URL)
    async with get_session(session_maker) as session:
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_elasticsearch_connection(es_client: ElasticsearchClient):
    is_healthy = await es_client.health_check()
    assert is_healthy, "Elasticsearch should be healthy"


@pytest.mark.asyncio
async def test_ollama_embedding_connection(embedding_provider: OllamaEmbeddingProvider):
    embedding = await embedding_provider.embed("test")
    assert len(embedding) > 0, "Ollama embedding should return non-empty vector"
