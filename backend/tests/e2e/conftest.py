# backend/tests/e2e/conftest.py
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import get_session_maker, get_session, init_database, close_database
from app.infra.postgres.models import Base, User
from app.infra.providers.embedding import OllamaEmbeddingProvider


def get_test_settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return get_test_settings()


@pytest.fixture(scope="session")
async def db_engine(test_settings: Settings):
    await init_database(test_settings.DATABASE_URL)
    yield
    await close_database()


@pytest.fixture
async def db_session(db_engine, test_settings: Settings):
    session_maker = get_session_maker(test_settings.DATABASE_URL)
    async with get_session(session_maker) as session:
        engine = session_maker.kw.get("bind")
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        existing_user = await session.execute(text("SELECT id FROM users WHERE id = 'test-user-e2e'"))
        if not existing_user.scalar_one_or_none():
            test_user = User(id="test-user-e2e", email="e2e@test.com", password_hash="test_hash")
            session.add(test_user)
            await session.commit()

        yield session


@pytest.fixture
async def es_client(test_settings: Settings):
    async with ElasticsearchClient(
        hosts=[test_settings.ELASTICSEARCH_URL],
        index_name=f"{test_settings.ELASTICSEARCH_INDEX}_e2e_test",
    ) as client:
        yield client


@pytest.fixture
async def embedding_provider(test_settings: Settings):
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
