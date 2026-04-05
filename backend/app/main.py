from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.application.ingestion_service import IngestionService
from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import create_embeddings, create_llm, create_rag_agent, create_retriever
from app.infra.postgres.database import close_database, init_database
from app.infra.redis.cache import RedisCache
from app.observability.logging import setup_logging
from app.observability.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize and cleanup resources."""
    settings = get_settings()

    # Initialize logging first
    setup_logging(settings)

    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    try:
        # Initialize database
        await init_database(settings.DATABASE_URL)

        # Initialize Redis
        redis_cache = RedisCache(settings.REDIS_URL)

        # Initialize Elasticsearch client
        es_client = ElasticsearchClient(
            hosts=[settings.ELASTICSEARCH_URL],
            index_name=settings.ELASTICSEARCH_INDEX,
        )
        await es_client.create_index(settings.ELASTICSEARCH_INDEX, settings.EMBEDDING_DIMS)

        # Initialize other singletons
        embeddings = create_embeddings(settings)
        llm = create_llm(settings)
        retriever = create_retriever(es_client, embeddings, settings)
        rag_agent = create_rag_agent(llm, retriever, settings)
        ingestion_service = IngestionService(
            es_client=es_client,
            embeddings=embeddings,
        )

        # Store in app.state
        app.state.redis_cache = redis_cache
        app.state.es_client = es_client
        app.state.embeddings = embeddings
        app.state.llm = llm
        app.state.retriever = retriever
        app.state.rag_agent = rag_agent
        app.state.ingestion_service = ingestion_service
        app.state.settings = settings

        yield

    except Exception as e:
        logger.exception(f"Failed to initialize: {e}")
        raise
    finally:
        await close_database()
        if hasattr(app.state, "redis_cache") and app.state.redis_cache:
            await app.state.redis_cache.close()
        if hasattr(app.state, "es_client") and app.state.es_client:
            await app.state.es_client.close()
        logger.info("Shutting down")


app = FastAPI(title="MuseAI", description="Museum AI Guide System", version="2.0.0", lifespan=lifespan)


# Getter functions that retrieve from app.state
# Note: These are defined after `app` so they can reference it directly without circular imports
def get_es_client() -> ElasticsearchClient:
    """Get Elasticsearch client from app.state."""
    if hasattr(app.state, "es_client"):
        return app.state.es_client
    raise RuntimeError("Elasticsearch client not initialized. App not started?")


def get_embeddings():
    """Get embeddings from app.state."""
    if hasattr(app.state, "embeddings"):
        return app.state.embeddings
    raise RuntimeError("Embeddings not initialized. App not started?")


def get_llm():
    """Get LLM from app.state."""
    if hasattr(app.state, "llm"):
        return app.state.llm
    raise RuntimeError("LLM not initialized. App not started?")


def get_retriever():
    """Get retriever from app.state."""
    if hasattr(app.state, "retriever"):
        return app.state.retriever
    raise RuntimeError("Retriever not initialized. App not started?")


def get_rag_agent():
    """Get RAG agent from app.state."""
    if hasattr(app.state, "rag_agent"):
        return app.state.rag_agent
    raise RuntimeError("RAG agent not initialized. App not started?")


def get_ingestion_service() -> IngestionService:
    """Get ingestion service from app.state."""
    if hasattr(app.state, "ingestion_service"):
        return app.state.ingestion_service
    raise RuntimeError("Ingestion service not initialized. App not started?")


def get_redis_cache() -> RedisCache:
    """Get Redis cache from app.state."""
    if hasattr(app.state, "redis_cache"):
        return app.state.redis_cache
    raise RuntimeError("Redis cache not initialized. App not started?")


# Get settings for CORS configuration
_settings = get_settings()
cors_origins = _settings.get_cors_origins()

# In production, don't allow credentials with wildcard
allow_credentials = _settings.CORS_ALLOW_CREDENTIALS and "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(auth_router, prefix="/api/v1")
