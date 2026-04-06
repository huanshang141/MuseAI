"""LangChain集成模块。

提供LLM、Embeddings、Retriever和RAG Agent的工厂函数。
"""

from typing import Any

from langchain_openai import ChatOpenAI

from app.config.settings import Settings
from app.infra.langchain.agents import RAGAgent
from app.infra.langchain.embeddings import CustomOllamaEmbeddings
from app.infra.langchain.retrievers import RRFRetriever
from app.infra.providers.rerank import OpenAICompatibleRerankProvider
from app.workflows.query_transform import ConversationAwareQueryRewriter


def create_embeddings(settings: Settings) -> CustomOllamaEmbeddings:
    """创建Embeddings实例。"""
    return CustomOllamaEmbeddings(
        base_url=settings.EMBEDDING_OLLAMA_BASE_URL,
        model=settings.EMBEDDING_OLLAMA_MODEL,
        dims=settings.EMBEDDING_DIMS,
    )


def create_llm(settings: Settings) -> ChatOpenAI:
    """创建LLM实例。"""
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
    """创建Retriever实例。"""
    return RRFRetriever(
        es_client=es_client,
        embeddings=embeddings,
        top_k=5,
        rrf_k=60,
    )


def create_rerank_provider(settings: Settings) -> OpenAICompatibleRerankProvider | None:
    """创建Rerank提供者实例。

    Args:
        settings: 应用配置

    Returns:
        Rerank提供者实例，如果未配置则返回None
    """
    if not settings.RERANK_BASE_URL:
        return None
    return OpenAICompatibleRerankProvider(
        base_url=settings.RERANK_BASE_URL,
        api_key=settings.RERANK_API_KEY,
        model=settings.RERANK_MODEL,
    )


def create_query_rewriter(llm_provider: Any) -> ConversationAwareQueryRewriter:
    """创建查询重写器实例。

    Args:
        llm_provider: LLM提供者实例

    Returns:
        查询重写器实例
    """
    return ConversationAwareQueryRewriter(llm_provider)


def create_rag_agent(
    llm: Any,
    retriever: Any,
    settings: Settings,
    rerank_provider: OpenAICompatibleRerankProvider | None = None,
    query_rewriter: ConversationAwareQueryRewriter | None = None,
) -> RAGAgent:
    """创建RAG Agent实例。

    Args:
        llm: 语言模型实例
        retriever: 检索器实例
        settings: 应用配置
        rerank_provider: Rerank提供者（可选）
        query_rewriter: 查询重写器（可选）

    Returns:
        RAG Agent实例
    """
    return RAGAgent(
        llm=llm,
        retriever=retriever,
        rerank_provider=rerank_provider,
        query_rewriter=query_rewriter,
        score_threshold=0.7,
        max_attempts=3,
        rerank_top_n=settings.RERANK_TOP_N,
    )


__all__ = [
    "CustomOllamaEmbeddings",
    "create_embeddings",
    "create_llm",
    "create_retriever",
    "create_rerank_provider",
    "create_query_rewriter",
    "create_rag_agent",
]
