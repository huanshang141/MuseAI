# ruff: noqa: E501
"""Curator Agent module for Digital Curation Agent System.

This module implements a ReAct (Reasoning + Acting) agent that acts as a museum curator,
using tools to plan paths, retrieve knowledge, generate narratives, create reflection prompts,
and manage user preferences.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.application.prompt_gateway import PromptGateway


class CuratorAgent:
    """博物馆策展人智能体，使用ReAct模式进行推理和行动。

    该智能体作为博物馆数字导览系统的核心，通过调用各种工具来：
    - 规划参观路线
    - 检索展品知识
    - 生成叙事内容
    - 提供反思提示
    - 管理用户偏好
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        session_id: str,
        prompt_gateway: PromptGateway | None = None,
        verbose: bool = False,
    ):
        self.llm = llm
        self.tools = tools
        self.session_id = session_id
        self.prompt_gateway = prompt_gateway
        self.verbose = verbose
        self._agent: Any = None

    @classmethod
    async def create(
        cls,
        llm: BaseChatModel,
        tools: list[BaseTool],
        session_id: str,
        prompt_gateway: PromptGateway | None = None,
        verbose: bool = False,
    ) -> "CuratorAgent":
        """Async factory method for creating a CuratorAgent.

        Use this instead of __init__ to properly await async prompt loading.
        """
        instance = cls(llm, tools, session_id, prompt_gateway, verbose)
        instance._agent = await instance._create_agent()
        return instance

    async def _create_agent(self) -> Any:
        system_prompt = await self._get_system_prompt()

        agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            debug=self.verbose,
        )

        return agent

    async def _get_system_prompt(self) -> str:
        if self.prompt_gateway:
            try:
                result = await self.prompt_gateway.get("curator_system")
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Failed to get curator system prompt: {e}, using fallback")

        return self._get_fallback_system_prompt()

    def _get_fallback_system_prompt(self) -> str:
        return """你是MuseAI博物馆智能导览系统的数字策展人。你的职责是为参观者提供个性化、有深度的博物馆参观体验。

## 你的角色

作为数字策展人，你：
1. 了解博物馆的所有展品及其历史文化背景
2. 能够根据参观者的兴趣和时间规划最佳参观路线
3. 能够用生动有趣的方式讲述展品背后的故事
4. 善于提出引人深思的问题，激发参观者的思考
5. 记住并适应每位参观者的偏好和需求

## 可用工具

你可以使用以下工具来帮助参观者：

1. **path_planning** - 路线规划工具
   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线
   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）
   - 何时使用：当参观者需要路线建议或想要开始参观时

2. **knowledge_retrieval** - 知识检索工具
   - 用途：检索展品的详细知识和背景信息
   - 输入：query（查询内容）、exhibit_id（可选，特定展品ID）
   - 何时使用：当参观者询问具体展品信息时

3. **narrative_generation** - 叙事生成工具
   - 用途：为展品生成引人入胜的叙事内容
   - 输入：exhibit_name（展品名称）、exhibit_info（展品信息）、knowledge_level（知识水平）、narrative_preference（叙事偏好）
   - 何时使用：当需要为展品创建讲解内容时

4. **reflection_prompts** - 反思提示工具
   - 用途：生成引发深度思考的问题
   - 输入：knowledge_level（知识水平）、reflection_depth（问题数量）、category（可选，展品类别）、exhibit_name（可选，展品名称）
   - 何时使用：在介绍完展品后，想要引导参观者深入思考时

5. **preference_management** - 偏好管理工具
   - 用途：获取或更新参观者的个人偏好设置
   - 输入：action（"get"或"update"）、user_id（用户ID）、updates（更新内容，可选）
   - 何时使用：需要了解或修改参观者偏好时

## 工具使用指南

1. **分析需求**：首先理解参观者的需求和当前情境
2. **选择工具**：根据需求选择最合适的工具
3. **准备输入**：确保工具输入格式正确（JSON格式）
4. **执行工具**：调用工具并等待结果
5. **整合回复**：将工具结果转化为自然、友好的回复

## 交互原则

- 使用中文与参观者交流
- 保持专业、友善、耐心的态度
- 根据参观者的知识水平调整讲解深度
- 鼓励互动和提问
- 在规划路线时考虑参观者的体力限制
- 为每个推荐的展品提供简要的背景介绍

## 注意事项

- 如果工具调用失败，礼貌地向参观者说明情况并提供替代方案
- 不要编造展品信息，始终通过工具获取准确数据
- 尊重参观者的隐私，妥善管理个人偏好数据
- 当参观者表示疲劳时，主动建议休息或缩短路线

现在，请开始为参观者提供专业的导览服务吧！"""

    def _format_chat_history(
        self, chat_history: list[dict[str, str]]
    ) -> list[HumanMessage | AIMessage]:
        messages = []
        for msg in chat_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages

    async def run(
        self,
        user_input: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """执行智能体运行。"""
        if self._agent is None:
            self._agent = await self._create_agent()

        try:
            messages = self._format_chat_history(chat_history or [])
            messages.append(HumanMessage(content=user_input))

            result = await self._agent.ainvoke(
                {"messages": messages},
                config={"configurable": {"session_id": self.session_id}},
            )

            output_messages = result.get("messages", [])
            final_output = ""
            if output_messages:
                last_message = output_messages[-1]
                if isinstance(last_message, AIMessage):
                    final_output = last_message.content

            return {
                "output": final_output,
                "messages": output_messages,
                "session_id": self.session_id,
            }

        except Exception as e:
            logger.error(f"CuratorAgent execution error: {e}")
            return {
                "output": "抱歉，我在处理您的请求时遇到了问题。请稍后再试，或者尝试用不同的方式提问。",
                "error": str(e),
                "session_id": self.session_id,
            }
