"""博物馆导览Agent工具模块。

定义LangChain工具供Agent调用。
"""

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from app.application.context_manager import ConversationContextManager


class RAGRetrievalTool(BaseTool):
    """博物馆知识库检索工具。"""

    name: str = "museum_knowledge_search"
    description: str = (
        "搜索博物馆知识库，获取关于展品、文物、历史背景的信息。"
        "输入应该是具体的问题，如'这件青铜器的用途是什么？'"
    )

    rag_agent: Any = Field(..., description="RAG Agent实例")

    async def _arun(self, query: str) -> str:
        """异步执行检索。"""
        result = await self.rag_agent.run(query)
        return result.get("answer", "抱歉，未找到相关信息。")

    def _run(self, query: str) -> str:
        """同步执行（不支持）。"""
        raise NotImplementedError("This tool only supports async execution")


class RecommendTool(BaseTool):
    """展品推荐工具。"""

    name: str = "recommend_exhibits"
    description: str = (
        "根据用户兴趣推荐相关展品。"
        "输入应该是用户的兴趣描述，如'我对青铜器很感兴趣'。"
    )

    rag_agent: Any = Field(..., description="RAG Agent实例")

    async def _arun(self, interest: str) -> str:
        """异步执行推荐。"""
        # 构建推荐查询
        query = f"推荐与{interest}相关的展品或文物"
        result = await self.rag_agent.run(query)
        return result.get("answer", "抱歉，暂时无法提供推荐。")

    def _run(self, interest: str) -> str:
        """同步执行（不支持）。"""
        raise NotImplementedError("This tool only supports async execution")


class PreferenceTool(BaseTool):
    """导览偏好工具。"""

    name: str = "guide_preferences"
    description: str = (
        "获取或设置用户的导览偏好。"
        "输入应该是偏好描述，如'请用中文回答'或'我喜欢详细的讲解'。"
    )

    context_manager: ConversationContextManager = Field(..., description="上下文管理器实例")
    session_id: str = Field(..., description="当前会话ID")

    async def _arun(self, preference: str) -> str:
        """异步执行偏好设置。"""
        # 解析偏好
        preferences: dict[str, str] = {}

        if "中文" in preference or "英文" in preference or "英语" in preference:
            preferences["language"] = "中文" if "中文" in preference else "English"

        if "详细" in preference:
            preferences["detail_level"] = "detailed"
        elif "简洁" in preference or "简短" in preference:
            preferences["detail_level"] = "brief"

        if "专业" in preference:
            preferences["style"] = "professional"
        elif "通俗" in preference or "简单" in preference:
            preferences["style"] = "casual"

        # 保存偏好
        if preferences:
            existing = await self.context_manager.get_user_preferences(self.session_id) or {}
            existing.update(preferences)
            await self.context_manager.set_user_preferences(self.session_id, existing)
            return f"已更新您的导览偏好：{preferences}"

        # 如果没有明确偏好，返回当前偏好
        current = await self.context_manager.get_user_preferences(self.session_id)
        if current:
            return f"您当前的导览偏好：{current}"
        return "您还未设置导览偏好。可以告诉我想使用什么语言、详细的还是简洁的讲解风格等。"

    def _run(self, preference: str) -> str:
        """同步执行（不支持）。"""
        raise NotImplementedError("This tool only supports async execution")


class ContextSummaryTool(BaseTool):
    """上下文摘要工具。"""

    name: str = "conversation_context"
    description: str = (
        "获取当前对话的上下文摘要。"
        "用于了解之前讨论过的内容。无需输入参数。"
    )

    context_manager: ConversationContextManager = Field(..., description="上下文管理器实例")
    session_id: str = Field(..., description="当前会话ID")

    async def _arun(self, _: str = "") -> str:
        """异步获取上下文摘要。"""
        formatted = await self.context_manager.get_formatted_context(self.session_id)
        return formatted

    def _run(self, _: str = "") -> str:
        """同步执行（不支持）。"""
        raise NotImplementedError("This tool only supports async execution")


def create_museum_tools(
    rag_agent: Any,
    context_manager: ConversationContextManager,
    session_id: str,
) -> list[BaseTool]:
    """创建博物馆导览工具集。

    Args:
        rag_agent: RAG Agent实例
        context_manager: 上下文管理器实例
        session_id: 当前会话ID

    Returns:
        工具列表
    """
    return [
        RAGRetrievalTool(rag_agent=rag_agent),
        RecommendTool(rag_agent=rag_agent),
        PreferenceTool(context_manager=context_manager, session_id=session_id),
        ContextSummaryTool(context_manager=context_manager, session_id=session_id),
    ]
