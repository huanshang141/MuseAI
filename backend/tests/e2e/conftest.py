# backend/tests/e2e/conftest.py
import asyncio
from pathlib import Path

import pytest
from app.config.settings import Settings, get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import close_database, get_session_maker, init_database
from app.infra.postgres.models import Base
from app.infra.providers.embedding import OllamaEmbeddingProvider
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
async def db_engine(test_settings: Settings) -> AsyncEngine:
    session_maker = await init_database(test_settings.DATABASE_URL)
    engine = session_maker.kw.get("bind")
    if engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield engine
    await close_database()


@pytest.fixture
async def db_session(db_engine: AsyncEngine, test_settings: Settings) -> AsyncSession:
    session_maker = get_session_maker(test_settings.DATABASE_URL)
    async with session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, email, password_hash) VALUES ('test-user-e2e', 'e2e@test.com', 'test_hash') ON CONFLICT (id) DO NOTHING"
            )
        )
        await session.commit()

        async with session.begin_nested():
            yield session


@pytest.fixture
async def es_client(test_settings: Settings) -> ElasticsearchClient:
    async with ElasticsearchClient(
        hosts=[test_settings.ELASTICSEARCH_URL],
        index_name=f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test",
    ) as client:
        yield client


@pytest.fixture
async def embedding_provider(test_settings: Settings) -> OllamaEmbeddingProvider:
    async with OllamaEmbeddingProvider(
        base_url=test_settings.EMBEDDING_OLLAMA_BASE_URL,
        model=test_settings.EMBEDDING_OLLAMA_MODEL,
        dims=test_settings.EMBEDDING_DIMS,
    ) as provider:
        yield provider


@pytest.fixture
def sample_document_path() -> Path:
    return Path(__file__).parent / "test_data" / "museum_sample.txt"


@pytest.fixture
def sample_document_content(sample_document_path: Path) -> str:
    return sample_document_path.read_text(encoding="utf-8")


@pytest.fixture
async def clean_es_index(es_client: ElasticsearchClient, test_settings: Settings):
    index_name = f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test"
    try:
        await es_client.client.indices.delete(index=index_name, ignore_unavailable=True)
    except Exception:
        pass

    yield

    try:
        await es_client.client.indices.delete(index=index_name, ignore_unavailable=True)
    except Exception:
        pass
