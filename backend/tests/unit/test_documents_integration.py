from unittest.mock import MagicMock, patch


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
            get_embeddings,
            get_es_client,
            get_ingestion_service,
            get_llm,
            get_rag_agent,
            get_retriever,
        )

        assert callable(get_es_client)
        assert callable(get_embeddings)
        assert callable(get_llm)
        assert callable(get_retriever)
        assert callable(get_rag_agent)
        assert callable(get_ingestion_service)

    def test_main_has_global_variables(self):
        import app.main as main

        mock_settings = MagicMock(
            ELASTICSEARCH_URL="http://localhost:9200",
            ELASTICSEARCH_INDEX="test_index",
        )

        mock_es_client = MagicMock(name="es_client")
        mock_embeddings = object()
        mock_llm = object()
        mock_retriever = object()
        mock_rag_agent = object()
        mock_ingestion_service = MagicMock(name="ingestion_service")

        mock_es_factory = MagicMock(return_value=mock_es_client)
        mock_embeddings_factory = MagicMock(return_value=mock_embeddings)
        mock_llm_factory = MagicMock(return_value=mock_llm)
        mock_retriever_factory = MagicMock(return_value=mock_retriever)
        mock_rag_agent_factory = MagicMock(return_value=mock_rag_agent)
        mock_ingestion_factory = MagicMock(return_value=mock_ingestion_service)

        with (
            patch.object(main, "es_client", None),
            patch.object(main, "embeddings", None),
            patch.object(main, "llm", None),
            patch.object(main, "retriever", None),
            patch.object(main, "rag_agent", None),
            patch.object(main, "ingestion_service", None),
            patch.object(main, "get_settings", return_value=mock_settings),
            patch.object(main, "ElasticsearchClient", mock_es_factory),
            patch.object(main, "create_embeddings", mock_embeddings_factory),
            patch.object(main, "create_llm", mock_llm_factory),
            patch.object(main, "create_retriever", mock_retriever_factory),
            patch.object(main, "create_rag_agent", mock_rag_agent_factory),
            patch.object(main, "IngestionService", mock_ingestion_factory),
        ):
            es_first = main.get_es_client()
            es_second = main.get_es_client()
            assert es_first is mock_es_client
            assert es_second is es_first
            mock_es_factory.assert_called_once_with(
                hosts=[mock_settings.ELASTICSEARCH_URL],
                index_name=mock_settings.ELASTICSEARCH_INDEX,
            )

            embeddings_first = main.get_embeddings()
            embeddings_second = main.get_embeddings()
            assert embeddings_first is mock_embeddings
            assert embeddings_second is embeddings_first
            mock_embeddings_factory.assert_called_once_with(mock_settings)

            llm_first = main.get_llm()
            llm_second = main.get_llm()
            assert llm_first is mock_llm
            assert llm_second is llm_first
            mock_llm_factory.assert_called_once_with(mock_settings)

            retriever_first = main.get_retriever()
            retriever_second = main.get_retriever()
            assert retriever_first is mock_retriever
            assert retriever_second is retriever_first
            mock_retriever_factory.assert_called_once_with(mock_es_client, mock_embeddings, mock_settings)

            rag_agent_first = main.get_rag_agent()
            rag_agent_second = main.get_rag_agent()
            assert rag_agent_first is mock_rag_agent
            assert rag_agent_second is rag_agent_first
            mock_rag_agent_factory.assert_called_once_with(mock_llm, mock_retriever, mock_settings)

            ingestion_first = main.get_ingestion_service()
            ingestion_second = main.get_ingestion_service()
            assert ingestion_first is mock_ingestion_service
            assert ingestion_second is ingestion_first
            mock_ingestion_factory.assert_called_once_with(
                es_client=mock_es_client,
                embeddings=mock_embeddings,
            )
