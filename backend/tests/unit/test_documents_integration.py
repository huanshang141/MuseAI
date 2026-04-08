from unittest.mock import MagicMock


class TestDocumentsAPIIntegration:
    def test_get_unified_indexing_service_function_exists(self):
        from app.api.documents import get_unified_indexing_service

        assert callable(get_unified_indexing_service)

    def test_get_es_client_function_exists(self):
        from app.api.documents import get_es_client

        assert callable(get_es_client)

    def test_get_embeddings_function_exists(self):
        from app.api.documents import get_embeddings

        assert callable(get_embeddings)

    def test_process_document_background_function_exists(self):
        from app.api.documents import process_document_background

        assert callable(process_document_background)

    def test_upload_endpoint_accepts_file(self):
        from app.api.documents import upload_document

        assert callable(upload_document)

    def test_main_provides_global_instances(self):
        from app.main import (
            get_embeddings,
            get_es_client,
            get_llm,
            get_rag_agent,
            get_retriever,
            get_unified_indexing_service,
        )

        assert callable(get_es_client)
        assert callable(get_embeddings)
        assert callable(get_llm)
        assert callable(get_retriever)
        assert callable(get_rag_agent)
        assert callable(get_unified_indexing_service)

    def test_main_getters_use_app_state(self):
        """Test that getter functions retrieve from app.state."""
        from app.main import (
            app,
            get_embeddings,
            get_es_client,
            get_llm,
            get_rag_agent,
            get_retriever,
            get_unified_indexing_service,
        )

        # Create mock singletons
        mock_es_client = MagicMock(name="es_client")
        mock_embeddings = MagicMock(name="embeddings")
        mock_llm = MagicMock(name="llm")
        mock_retriever = MagicMock(name="retriever")
        mock_rag_agent = MagicMock(name="rag_agent")
        mock_unified_indexing_service = MagicMock(name="unified_indexing_service")

        # Set up app.state
        app.state.es_client = mock_es_client
        app.state.embeddings = mock_embeddings
        app.state.llm = mock_llm
        app.state.retriever = mock_retriever
        app.state.rag_agent = mock_rag_agent
        app.state.unified_indexing_service = mock_unified_indexing_service

        try:
            # Verify getters return the mocked values from app.state
            assert get_es_client() is mock_es_client
            assert get_embeddings() is mock_embeddings
            assert get_llm() is mock_llm
            assert get_retriever() is mock_retriever
            assert get_rag_agent() is mock_rag_agent
            assert get_unified_indexing_service() is mock_unified_indexing_service
        finally:
            # Clean up app.state
            delattr(app.state, "es_client")
            delattr(app.state, "embeddings")
            delattr(app.state, "llm")
            delattr(app.state, "retriever")
            delattr(app.state, "rag_agent")
            delattr(app.state, "unified_indexing_service")

    def test_main_getters_raise_error_when_not_initialized(self):
        """Test that getter functions raise error when app.state is not initialized."""
        import pytest
        from app.main import app, get_es_client

        # Ensure app.state does not have es_client
        if hasattr(app.state, "es_client"):
            delattr(app.state, "es_client")

        with pytest.raises(RuntimeError, match="Elasticsearch client not initialized"):
            get_es_client()
