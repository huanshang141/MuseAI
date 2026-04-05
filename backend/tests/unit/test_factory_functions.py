from unittest.mock import MagicMock

from app.config.settings import Settings


class TestFactoryFunctions:
    def test_create_embeddings_returns_custom_ollama_embeddings(self):
        from app.infra.langchain import create_embeddings

        settings = Settings(
            APP_NAME="test",
            APP_ENV="test",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://test",
            REDIS_URL="redis://test",
            ELASTICSEARCH_URL="http://localhost:9200",
            JWT_SECRET="test-secret",
            JWT_ALGORITHM="HS256",
            JWT_EXPIRE_MINUTES=60,
            LLM_PROVIDER="openai",
            LLM_BASE_URL="http://localhost:11434",
            LLM_API_KEY="test-key",
            LLM_MODEL="llama2",
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
            EMBEDDING_OLLAMA_MODEL="nomic-embed-text",
            ELASTICSEARCH_INDEX="test_index",
            EMBEDDING_DIMS=768,
        )

        embeddings = create_embeddings(settings)

        assert embeddings.base_url == settings.EMBEDDING_OLLAMA_BASE_URL
        assert embeddings.model == settings.EMBEDDING_OLLAMA_MODEL
        assert embeddings.dims == settings.EMBEDDING_DIMS

    def test_create_llm_returns_chat_openai(self):
        from app.infra.langchain import create_llm

        settings = Settings(
            APP_NAME="test",
            APP_ENV="test",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://test",
            REDIS_URL="redis://test",
            ELASTICSEARCH_URL="http://localhost:9200",
            JWT_SECRET="test-secret",
            JWT_ALGORITHM="HS256",
            JWT_EXPIRE_MINUTES=60,
            LLM_PROVIDER="openai",
            LLM_BASE_URL="http://localhost:11434/v1",
            LLM_API_KEY="test-key",
            LLM_MODEL="llama2",
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
            EMBEDDING_OLLAMA_MODEL="nomic-embed-text",
            ELASTICSEARCH_INDEX="test_index",
            EMBEDDING_DIMS=768,
        )

        llm = create_llm(settings)

        assert llm is not None
        assert hasattr(llm, "ainvoke")

    def test_create_retriever_returns_rrf_retriever(self):
        from app.infra.langchain import create_retriever

        mock_es_client = MagicMock()
        mock_embeddings = MagicMock()

        settings = Settings(
            APP_NAME="test",
            APP_ENV="test",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://test",
            REDIS_URL="redis://test",
            ELASTICSEARCH_URL="http://localhost:9200",
            JWT_SECRET="test-secret",
            JWT_ALGORITHM="HS256",
            JWT_EXPIRE_MINUTES=60,
            LLM_PROVIDER="openai",
            LLM_BASE_URL="http://localhost:11434/v1",
            LLM_API_KEY="test-key",
            LLM_MODEL="llama2",
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
            EMBEDDING_OLLAMA_MODEL="nomic-embed-text",
            ELASTICSEARCH_INDEX="test_index",
            EMBEDDING_DIMS=768,
        )

        retriever = create_retriever(mock_es_client, mock_embeddings, settings)

        assert retriever is not None
        assert hasattr(retriever, "_aget_relevant_documents")

    def test_create_rag_agent_returns_agent(self):
        from app.infra.langchain import create_rag_agent

        mock_llm = MagicMock()
        mock_retriever = MagicMock()

        settings = Settings(
            APP_NAME="test",
            APP_ENV="test",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://test",
            REDIS_URL="redis://test",
            ELASTICSEARCH_URL="http://localhost:9200",
            JWT_SECRET="test-secret",
            JWT_ALGORITHM="HS256",
            JWT_EXPIRE_MINUTES=60,
            LLM_PROVIDER="openai",
            LLM_BASE_URL="http://localhost:11434/v1",
            LLM_API_KEY="test-key",
            LLM_MODEL="llama2",
            EMBEDDING_PROVIDER="ollama",
            EMBEDDING_OLLAMA_BASE_URL="http://localhost:11434",
            EMBEDDING_OLLAMA_MODEL="nomic-embed-text",
            ELASTICSEARCH_INDEX="test_index",
            EMBEDDING_DIMS=768,
        )

        agent = create_rag_agent(mock_llm, mock_retriever, settings)

        assert agent is not None
        assert hasattr(agent, "run")
