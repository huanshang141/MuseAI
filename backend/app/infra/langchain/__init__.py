from typing import Any

from langchain_openai import ChatOpenAI

from app.config.settings import Settings
from app.infra.langchain.agents import RAGAgent
from app.infra.langchain.embeddings import CustomOllamaEmbeddings
from app.infra.langchain.retrievers import RRFRetriever


def create_embeddings(settings: Settings) -> CustomOllamaEmbeddings:
    return CustomOllamaEmbeddings(
        base_url=settings.EMBEDDING_OLLAMA_BASE_URL,
        model=settings.EMBEDDING_OLLAMA_MODEL,
        dims=settings.EMBEDDING_DIMS,
    )


def create_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
    )


def create_retriever(
    es_client: Any,
    embeddings: CustomOllamaEmbeddings,
    settings: Settings,
) -> RRFRetriever:
    return RRFRetriever(
        es_client=es_client,
        embeddings=embeddings,
        top_k=5,
        rrf_k=60,
    )


def create_rag_agent(
    llm: Any,
    retriever: Any,
    settings: Settings,
) -> RAGAgent:
    return RAGAgent(
        llm=llm,
        retriever=retriever,
        score_threshold=0.7,
        max_attempts=3,
    )


__all__ = [
    "CustomOllamaEmbeddings",
    "create_embeddings",
    "create_llm",
    "create_retriever",
    "create_rag_agent",
]
