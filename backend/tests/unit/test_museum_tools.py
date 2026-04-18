"""博物馆导览工具单元测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.ports.context_manager import ConversationContextManagerPort
from app.infra.langchain.tools import (
    ContextSummaryTool,
    PreferenceTool,
    RAGRetrievalTool,
    RecommendTool,
    create_museum_tools,
)


class TestRAGRetrievalTool:
    def test_tool_properties(self):
        """测试工具基本属性。"""
        mock_agent = MagicMock()
        tool = RAGRetrievalTool(rag_agent=mock_agent)

        assert tool.name == "museum_knowledge_search"
        assert "博物馆知识库" in tool.description

    @pytest.mark.asyncio
    async def test_arun_success(self):
        """测试异步检索成功。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {"answer": "这是商代青铜器"}

        tool = RAGRetrievalTool(rag_agent=mock_agent)
        result = await tool._arun("这件青铜器是什么？")

        assert result == "这是商代青铜器"
        mock_agent.run.assert_called_once_with("这件青铜器是什么？")

    @pytest.mark.asyncio
    async def test_arun_no_answer(self):
        """测试检索无结果。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {}

        tool = RAGRetrievalTool(rag_agent=mock_agent)
        result = await tool._arun("未知问题")

        assert "抱歉，未找到相关信息" in result

    def test_run_not_supported(self):
        """测试同步执行不支持。"""
        mock_agent = MagicMock()
        tool = RAGRetrievalTool(rag_agent=mock_agent)

        with pytest.raises(NotImplementedError):
            tool._run("test query")


class TestRecommendTool:
    def test_tool_properties(self):
        """测试工具基本属性。"""
        mock_agent = MagicMock()
        tool = RecommendTool(rag_agent=mock_agent)

        assert tool.name == "recommend_exhibits"
        assert "推荐" in tool.description

    @pytest.mark.asyncio
    async def test_arun_recommend(self):
        """测试推荐功能。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {"answer": "推荐您参观青铜器展厅"}

        tool = RecommendTool(rag_agent=mock_agent)
        result = await tool._arun("我对青铜器感兴趣")

        assert "青铜器展厅" in result
        # 验证调用时添加了推荐前缀
        call_args = mock_agent.run.call_args[0][0]
        assert "推荐与" in call_args
        assert "青铜器感兴趣" in call_args


class TestPreferenceTool:
    @pytest.fixture
    def mock_context_manager(self):
        manager = MagicMock(spec=ConversationContextManagerPort)
        manager.get_user_preferences = AsyncMock(return_value=None)
        manager.set_user_preferences = AsyncMock()
        return manager

    def test_tool_properties(self, mock_context_manager):
        """测试工具基本属性。"""
        tool = PreferenceTool(context_manager=mock_context_manager, session_id="test-session")

        assert tool.name == "guide_preferences"
        assert "偏好" in tool.description

    @pytest.mark.asyncio
    async def test_set_language_preference(self, mock_context_manager):
        """测试设置语言偏好。"""
        tool = PreferenceTool(context_manager=mock_context_manager, session_id="test-session")

        result = await tool._arun("请用中文回答")

        assert "已更新" in result
        assert "中文" in result
        mock_context_manager.set_user_preferences.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_style_preference(self, mock_context_manager):
        """测试设置风格偏好。"""
        tool = PreferenceTool(context_manager=mock_context_manager, session_id="test-session")

        result = await tool._arun("我喜欢详细的讲解")

        assert "已更新" in result
        assert "detailed" in result
        mock_context_manager.set_user_preferences.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_existing_preferences(self, mock_context_manager):
        """测试获取已有偏好。"""
        mock_context_manager.get_user_preferences.return_value = {
            "language": "中文",
            "style": "detailed",
        }

        tool = PreferenceTool(context_manager=mock_context_manager, session_id="test-session")
        result = await tool._arun("我的偏好是什么")

        assert "当前的导览偏好" in result

    @pytest.mark.asyncio
    async def test_no_preferences_set(self, mock_context_manager):
        """测试未设置偏好。"""
        mock_context_manager.get_user_preferences.return_value = None

        tool = PreferenceTool(context_manager=mock_context_manager, session_id="test-session")
        result = await tool._arun("我的偏好是什么")

        assert "还未设置导览偏好" in result


class TestContextSummaryTool:
    @pytest.fixture
    def mock_context_manager(self):
        manager = MagicMock(spec=ConversationContextManagerPort)
        manager.get_formatted_context = AsyncMock(return_value="用户：你好\n助手：您好！")
        return manager

    def test_tool_properties(self, mock_context_manager):
        """测试工具基本属性。"""
        tool = ContextSummaryTool(context_manager=mock_context_manager, session_id="test-session")

        assert tool.name == "conversation_context"
        assert "上下文" in tool.description

    @pytest.mark.asyncio
    async def test_arun_get_context(self, mock_context_manager):
        """测试获取上下文摘要。"""
        tool = ContextSummaryTool(context_manager=mock_context_manager, session_id="test-session")

        result = await tool._arun("")

        assert "用户：你好" in result
        mock_context_manager.get_formatted_context.assert_called_once_with("test-session")


class TestCreateMuseumTools:
    def test_create_all_tools(self):
        """测试创建所有工具。"""
        mock_agent = MagicMock()
        mock_context = MagicMock(spec=ConversationContextManagerPort)

        tools = create_museum_tools(mock_agent, mock_context, "test-session")

        assert len(tools) == 4
        tool_names = [tool.name for tool in tools]
        assert "museum_knowledge_search" in tool_names
        assert "recommend_exhibits" in tool_names
        assert "guide_preferences" in tool_names
        assert "conversation_context" in tool_names
