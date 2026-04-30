from contextlib import asynccontextmanager
from typing import Any, TypeVar

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.admin import documents_router as admin_documents_router
from app.api.admin import exhibits_router as admin_exhibits_router
from app.api.admin import halls_router as admin_halls_router
from app.api.admin import llm_traces_router as admin_llm_traces_router
from app.api.admin import prompts_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.curator import router as curator_router
from app.api.documents import router as documents_router
from app.api.exhibits import router as exhibits_router
from app.api.health import router as health_router
from app.api.profile import router as profile_router
from app.api.tour import router as tour_router
from app.application.context_manager import ConversationContextManager
from app.application.ingestion_service import IngestionService
from app.application.prompt_service_adapter import PromptServiceAdapter
from app.application.unified_indexing_service import UnifiedIndexingService
from app.application.workflows.reflection_prompts import ReflectionPromptService
from app.config.settings import get_settings
from app.infra.cache.prompt_cache import PromptCache
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import (
    create_embeddings,
    create_llm,
    create_query_rewriter,
    create_rag_agent,
    create_rerank_provider,
    create_retriever,
)
from app.infra.langchain.llm_trace_callback import LLMTraceCallbackHandler
from app.infra.postgres.adapters import PostgresPromptRepository
from app.infra.postgres.database import close_database, get_session, get_session_maker, init_database
from app.infra.redis.cache import RedisCache
from app.observability.logging import setup_logging
from app.observability.middleware import RequestLoggingMiddleware

T = TypeVar("T")


def _get_state_attr(name: str, type_name: str) -> Any:
    if hasattr(app.state, name):
        return getattr(app.state, name)
    raise RuntimeError(f"{type_name} not initialized. App not started?")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize and cleanup resources."""
    settings = get_settings()

    setup_logging(settings)

    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    app.state.degraded: set[str] = set()

    try:
        await init_database(settings.DATABASE_URL)

        redis_cache = RedisCache(settings.REDIS_URL)
        try:
            await redis_cache.client.ping()
        except Exception as e:
            logger.error(f"Redis unavailable at startup: {e}; entering degraded mode")
            app.state.degraded.add("redis")

        es_client = ElasticsearchClient(
            hosts=[settings.ELASTICSEARCH_URL],
            index_name=settings.ELASTICSEARCH_INDEX,
        )
        try:
            await es_client.health_check()
            await es_client.create_index(settings.ELASTICSEARCH_INDEX, settings.EMBEDDING_DIMS)
        except Exception as e:
            logger.error(f"ES unavailable at startup: {e}; entering degraded mode")
            app.state.degraded.add("elasticsearch")

        embeddings = create_embeddings(settings)

        from app.application.llm_trace.recorder import LLMTraceRecorder

        session_maker = get_session_maker()
        trace_recorder = LLMTraceRecorder(session_maker=session_maker)
        llm_trace_callback = LLMTraceCallbackHandler(trace_recorder=trace_recorder)
        llm = create_llm(settings, callbacks=[llm_trace_callback])
        retriever = create_retriever(es_client, embeddings, settings)

        rerank_provider = create_rerank_provider(settings)

        prompt_cache = PromptCache()
        async with get_session() as session:
            prompt_repository = PostgresPromptRepository(session)
            prompt_cache.set_repository(prompt_repository)
            await prompt_cache.load_all()
        app.state.prompt_cache = prompt_cache

        prompt_gateway = PromptServiceAdapter(prompt_cache)

        app.state.reflection_service = ReflectionPromptService(prompt_gateway)

        from app.infra.providers.llm import OpenAICompatibleProvider

        llm_provider = OpenAICompatibleProvider.from_settings(settings, trace_recorder=trace_recorder)
        query_rewriter = create_query_rewriter(llm_provider, prompt_gateway=prompt_gateway)

        rag_agent = create_rag_agent(
            llm=llm,
            retriever=retriever,
            settings=settings,
            rerank_provider=rerank_provider,
            query_rewriter=query_rewriter,
            prompt_gateway=prompt_gateway,
            llm_provider=llm_provider,
        )

        ingestion_service = IngestionService(
            es_client=es_client,
            embeddings=embeddings,
        )

        unified_indexing_service = UnifiedIndexingService(
            es_client=es_client,
            embeddings=embeddings,
        )

        context_manager = ConversationContextManager(redis_cache=redis_cache)

        app.state.redis_cache = redis_cache
        app.state.es_client = es_client
        app.state.embeddings = embeddings
        app.state.llm = llm
        app.state.llm_provider = llm_provider
        app.state.retriever = retriever
        app.state.rag_agent = rag_agent
        app.state.rerank_provider = rerank_provider
        app.state.query_rewriter = query_rewriter
        app.state.context_manager = context_manager
        app.state.ingestion_service = ingestion_service
        app.state.unified_indexing_service = unified_indexing_service
        app.state.settings = settings
        app.state.prompt_gateway = prompt_gateway

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


def get_es_client() -> ElasticsearchClient:
    return _get_state_attr("es_client", "Elasticsearch client")


def get_embeddings():
    return _get_state_attr("embeddings", "Embeddings")


def get_llm():
    return _get_state_attr("llm", "LLM")


def get_retriever():
    return _get_state_attr("retriever", "Retriever")


def get_rag_agent():
    return _get_state_attr("rag_agent", "RAG agent")


def get_ingestion_service() -> IngestionService:
    return _get_state_attr("ingestion_service", "Ingestion service")


def get_unified_indexing_service() -> UnifiedIndexingService:
    return _get_state_attr("unified_indexing_service", "Unified indexing service")


def get_redis_cache() -> RedisCache:
    return _get_state_attr("redis_cache", "Redis cache")


def get_rerank_provider():
    return _get_state_attr("rerank_provider", "Rerank provider")


def get_query_rewriter():
    return _get_state_attr("query_rewriter", "Query rewriter")


def get_context_manager() -> ConversationContextManager:
    return _get_state_attr("context_manager", "Context manager")


def get_prompt_cache() -> PromptCache:
    return _get_state_attr("prompt_cache", "Prompt cache")


_settings = get_settings()
cors_origins = _settings.get_cors_origins()

allow_credentials = _settings.CORS_ALLOW_CREDENTIALS and "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Session-Token"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_exhibits_router, prefix="/api/v1")
app.include_router(admin_documents_router, prefix="/api/v1")
app.include_router(admin_halls_router, prefix="/api/v1")
app.include_router(admin_llm_traces_router, prefix="/api/v1")
app.include_router(prompts_router, prefix="/api/v1")
app.include_router(curator_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(tour_router, prefix="/api/v1")
app.include_router(exhibits_router, prefix="/api/v1")
