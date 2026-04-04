import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestDocumentsAPIIntegration:
    def test_get_ingestion_service_function_exists(self):
        from app.api.documents import get_ingestion_service

        assert callable(get_ingestion_service)

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
            get_es_client,
            get_embeddings,
            get_llm,
            get_retriever,
            get_rag_agent,
            get_ingestion_service,
        )

        assert callable(get_es_client)
        assert callable(get_embeddings)
        assert callable(get_llm)
        assert callable(get_retriever)
        assert callable(get_rag_agent)
        assert callable(get_ingestion_service)

    def test_main_has_global_variables(self):
        from app.main import (
            es_client,
            embeddings,
            llm,
            retriever,
            rag_agent,
            ingestion_service,
        )

        assert es_client is None
        assert embeddings is None
        assert llm is None
        assert retriever is None
        assert rag_agent is None
        assert ingestion_service is None
