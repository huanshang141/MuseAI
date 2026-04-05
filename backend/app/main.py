from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.application.ingestion_service import IngestionService
from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import create_embeddings, create_llm, create_rag_agent, create_retriever
from app.infra.postgres.database import close_database, init_database

es_client: ElasticsearchClient | None = None
embeddings = None
llm = None
retriever = None
rag_agent = None
ingestion_service: IngestionService | None = None


def get_es_client() -> ElasticsearchClient:
    global es_client
    if es_client is None:
        settings = get_settings()
        es_client = ElasticsearchClient(
            hosts=[settings.ELASTICSEARCH_URL],
            index_name=settings.ELASTICSEARCH_INDEX,
        )
    return es_client


def get_embeddings():
    global embeddings
    if embeddings is None:
        settings = get_settings()
        embeddings = create_embeddings(settings)
    return embeddings


def get_llm():
    global llm
    if llm is None:
        settings = get_settings()
        llm = create_llm(settings)
    return llm


def get_retriever():
    global retriever
    if retriever is None:
        settings = get_settings()
        retriever = create_retriever(get_es_client(), get_embeddings(), settings)
    return retriever


def get_rag_agent():
    global rag_agent
    if rag_agent is None:
        settings = get_settings()
        rag_agent = create_rag_agent(get_llm(), get_retriever(), settings)
    return rag_agent


def get_ingestion_service() -> IngestionService:
    global ingestion_service
    if ingestion_service is None:
        ingestion_service = IngestionService(
            es_client=get_es_client(),
            embeddings=get_embeddings(),
        )
    return ingestion_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    try:
        await init_database(settings.DATABASE_URL)

        es = get_es_client()
        await es.create_index(settings.ELASTICSEARCH_INDEX, settings.EMBEDDING_DIMS)

        yield
    except Exception as e:
        print(f"Failed to initialize: {e}")
        raise
    finally:
        await close_database()
        if es_client:
            await es_client.close()
        print("Shutting down")


app = FastAPI(title="MuseAI", description="Museum AI Guide System", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(auth_router, prefix="/api/v1")
