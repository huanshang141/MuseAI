"""Tests for CuratorAgent module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.infra.langchain.curator_agent import CuratorAgent


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))
    return llm


@pytest.fixture
def mock_agent():
    """Create a mock compiled agent."""
    agent = MagicMock()
    agent.ainvoke = AsyncMock()
    return agent


class TestCuratorAgent:
    """Test cases for CuratorAgent."""

    def test_initialization(self, mock_llm, mock_agent):
        """Test agent initialization."""
        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=mock_agent,
        ):
            agent = CuratorAgent(
                llm=mock_llm,
                tools=[],  # Empty tools to avoid recursion issues
                session_id="test-session-456",
                verbose=True,
            )

        assert agent.llm == mock_llm
        assert agent.tools == []
        assert agent.session_id == "test-session-456"
        assert agent.verbose is True
        assert agent._agent is not None

    def test_get_system_prompt(self):
        """Test system prompt generation."""
        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=MagicMock(),
        ):
            agent = CuratorAgent(
                llm=MagicMock(),
                tools=[],
                session_id="test",
            )

        prompt = agent._get_system_prompt()

        assert "博物馆" in prompt
        assert "策展人" in prompt
        assert "path_planning" in prompt
        assert "knowledge_retrieval" in prompt
        assert "narrative_generation" in prompt
        assert "reflection_prompts" in prompt
        assert "preference_management" in prompt

    def test_format_chat_history(self):
        """Test chat history formatting."""
        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=MagicMock(),
        ):
            agent = CuratorAgent(
                llm=MagicMock(),
                tools=[],
                session_id="test",
            )

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "Tell me about exhibits"},
        ]

        formatted = agent._format_chat_history(history)

        assert len(formatted) == 3
        assert isinstance(formatted[0], HumanMessage)
        assert formatted[0].content == "Hello"
        assert isinstance(formatted[1], AIMessage)
        assert formatted[1].content == "Hi there"
        assert isinstance(formatted[2], HumanMessage)
        assert formatted[2].content == "Tell me about exhibits"

    def test_format_empty_chat_history(self):
        """Test empty chat history formatting."""
        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=MagicMock(),
        ):
            agent = CuratorAgent(
                llm=MagicMock(),
                tools=[],
                session_id="test",
            )

        formatted = agent._format_chat_history([])
        assert len(formatted) == 0

    @pytest.mark.asyncio
    async def test_run_success(self, mock_llm, mock_agent):
        """Test successful agent run."""
        # Create mock response messages
        mock_messages = [
            HumanMessage(content="Test input"),
            AIMessage(content="Test output"),
        ]
        mock_result = {
            "messages": mock_messages,
        }
        mock_agent.ainvoke = AsyncMock(return_value=mock_result)

        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=mock_agent,
        ):
            agent = CuratorAgent(
                llm=mock_llm,
                tools=[],
                session_id="test-session-123",
                verbose=False,
            )

            result = await agent.run(
                user_input="Test input",
                chat_history=[{"role": "user", "content": "Hello"}],
            )

        assert result["output"] == "Test output"
        assert result["session_id"] == "test-session-123"
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_run_without_chat_history(self, mock_llm, mock_agent):
        """Test agent run without chat history."""
        mock_messages = [
            HumanMessage(content="Test input"),
            AIMessage(content="Test output"),
        ]
        mock_result = {
            "messages": mock_messages,
        }
        mock_agent.ainvoke = AsyncMock(return_value=mock_result)

        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=mock_agent,
        ):
            agent = CuratorAgent(
                llm=mock_llm,
                tools=[],
                session_id="test-session-123",
                verbose=False,
            )

            result = await agent.run(user_input="Test input")

        assert result["output"] == "Test output"
        assert result["session_id"] == "test-session-123"

    @pytest.mark.asyncio
    async def test_run_error_handling(self, mock_llm, mock_agent):
        """Test error handling during agent run."""
        mock_agent.ainvoke = AsyncMock(side_effect=Exception("Test error"))

        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=mock_agent,
        ):
            agent = CuratorAgent(
                llm=mock_llm,
                tools=[],
                session_id="test-session-123",
                verbose=False,
            )

            result = await agent.run(user_input="Test input")

        assert "抱歉" in result["output"] or "error" in result.get("error", "").lower()
        assert "error" in result
        assert result["session_id"] == "test-session-123"

    def test_create_agent(self, mock_llm, mock_agent):
        """Test agent creation."""
        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=mock_agent,
        ) as mock_create:
            agent = CuratorAgent(
                llm=mock_llm,
                tools=[],
                session_id="test-session",
                verbose=False,
            )

            assert agent._agent is not None
            mock_create.assert_called_once()


class TestCuratorAgentIntegration:
    """Integration-style tests for CuratorAgent."""

    @pytest.mark.asyncio
    async def test_agent_with_complex_chat_history(self):
        """Test agent with complex chat history."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        complex_history = [
            {"role": "user", "content": "I like ancient history"},
            {"role": "assistant", "content": "Great! Let me suggest some exhibits."},
            {"role": "user", "content": "What about ceramics?"},
            {"role": "assistant", "content": "We have excellent ceramic collections."},
        ]

        mock_messages = [
            HumanMessage(content="I like ancient history"),
            AIMessage(content="Great! Let me suggest some exhibits."),
            HumanMessage(content="What about ceramics?"),
            AIMessage(content="We have excellent ceramic collections."),
            HumanMessage(content="Tell me more"),
            AIMessage(content="Here are some ceramic exhibits..."),
        ]
        mock_result = {
            "messages": mock_messages,
        }
        mock_agent.ainvoke = AsyncMock(return_value=mock_result)

        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=mock_agent,
        ):
            agent = CuratorAgent(
                llm=mock_llm,
                tools=[],
                session_id="complex-test",
                verbose=False,
            )

            result = await agent.run(
                user_input="Tell me more",
                chat_history=complex_history,
            )

        assert "Here are some ceramic exhibits..." in result["output"]

    def test_system_prompt_contains_all_tools(self):
        """Verify system prompt contains all tool descriptions."""
        with patch(
            "app.infra.langchain.curator_agent.create_react_agent",
            return_value=MagicMock(),
        ):
            agent = CuratorAgent(
                llm=MagicMock(),
                tools=[],
                session_id="test",
            )

        prompt = agent._get_system_prompt()

        # Check for all tool names
        assert "path_planning" in prompt
        assert "knowledge_retrieval" in prompt
        assert "narrative_generation" in prompt
        assert "reflection_prompts" in prompt
        assert "preference_management" in prompt

        # Check for tool usage guidelines
        assert "分析需求" in prompt
        assert "选择工具" in prompt
        assert "准备输入" in prompt
        assert "执行工具" in prompt
        assert "整合回复" in prompt
