import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestChatAPIIntegration:
    def test_get_rag_agent_function_exists(self):
        from app.api.chat import get_rag_agent

        assert callable(get_rag_agent)

    def test_chat_service_uses_rag_agent(self):
        from app.application import chat_service

        assert hasattr(chat_service, "ask_question_with_rag")

    @pytest.mark.asyncio
    async def test_ask_question_with_rag_calls_agent(self):
        mock_rag_agent = AsyncMock()
        mock_rag_agent.run = AsyncMock(
            return_value={
                "query": "test query",
                "documents": [],
                "retrieval_score": 0.8,
                "attempts": 0,
                "transformations": [],
                "answer": "Generated answer from RAG",
            }
        )

        mock_session = AsyncMock()

        with patch("app.application.chat_service.add_message", new_callable=AsyncMock) as mock_add_msg:
            mock_add_msg.return_value = MagicMock()

            from app.application.chat_service import ask_question_with_rag

            result = await ask_question_with_rag(
                session=mock_session,
                session_id="test-session",
                message="test query",
                rag_agent=mock_rag_agent,
            )

            assert result is not None
            assert "answer" in result
            mock_rag_agent.run.assert_called_once_with("test query")
