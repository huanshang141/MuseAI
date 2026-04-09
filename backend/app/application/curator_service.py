# backend/app/application/curator_service.py
from typing import Any

from app.application.ports.repositories import CuratorAgentPort
from app.domain.exceptions import EntityNotFoundError

from .exhibit_service import ExhibitService
from .profile_service import ProfileService


class CuratorService:
    """策展人协调服务，整合展品、画像和策展智能体提供导览服务。"""

    def __init__(
        self,
        curator_agent: CuratorAgentPort,
        profile_service: ProfileService,
        exhibit_service: ExhibitService,
    ):
        self._curator_agent = curator_agent
        self._profile_service = profile_service
        self._exhibit_service = exhibit_service

    async def plan_tour(
        self,
        user_id: str,
        available_time: int,
        interests: list[str] | None = None,
    ) -> dict[str, Any]:
        """规划参观路线。

        Args:
            user_id: 用户ID
            available_time: 可用时间（分钟）
            interests: 兴趣标签列表（可选，默认使用用户画像中的兴趣）

        Returns:
            包含路线规划结果的字典
        """
        # 获取或创建用户画像
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 使用用户兴趣或传入的兴趣
        tour_interests = interests if interests is not None else profile.interests

        # 获取已参观的展品ID
        visited_ids = [eid.value for eid in profile.visited_exhibit_ids]

        # 构建规划请求
        plan_request = f"""请为我规划一条博物馆参观路线。

可用时间：{available_time}分钟
兴趣标签：{', '.join(tour_interests) if tour_interests else '无特定偏好'}
已参观展品：{', '.join(visited_ids) if visited_ids else '无'}

请使用path_planning工具规划路线。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=plan_request,
            chat_history=[],
        )

        return {
            "user_id": user_id,
            "available_time": available_time,
            "interests": tour_interests,
            "visited_exhibit_ids": visited_ids,
            "plan": result.get("output", ""),
            "session_id": result.get("session_id", ""),
        }

    async def generate_narrative(
        self,
        user_id: str,
        exhibit_id: str,
    ) -> dict[str, Any]:
        """为展品生成叙事内容。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            包含叙事内容的字典

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        # 获取展品信息
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 获取用户画像
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 构建叙事生成请求
        narrative_request = f"""请为以下展品生成讲解内容：

展品名称：{exhibit.name}
展品描述：{exhibit.description}
展品年代：{exhibit.era}
展品类别：{exhibit.category}

用户知识水平：{profile.knowledge_level}
用户叙事偏好：{profile.narrative_preference}

请使用narrative_generation工具生成叙事内容。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=narrative_request,
            chat_history=[],
        )

        # 记录参观
        await self._profile_service.record_visit(user_id, exhibit_id)

        return {
            "user_id": user_id,
            "exhibit_id": exhibit_id,
            "exhibit_name": exhibit.name,
            "narrative": result.get("output", ""),
            "knowledge_level": profile.knowledge_level,
            "narrative_preference": profile.narrative_preference,
            "session_id": result.get("session_id", ""),
        }

    async def get_reflection_prompts(
        self,
        user_id: str,
        exhibit_id: str,
    ) -> dict[str, Any]:
        """获取展品的反思提示问题。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            包含反思提示的字典

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        # 获取展品信息
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 获取用户画像
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 构建反思提示请求
        reflection_request = f"""请为以下展品生成反思提示问题：

展品名称：{exhibit.name}
展品类别：{exhibit.category}

用户知识水平：{profile.knowledge_level}
反思深度：{profile.reflection_depth}

请使用reflection_prompts工具生成反思问题。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=reflection_request,
            chat_history=[],
        )

        return {
            "user_id": user_id,
            "exhibit_id": exhibit_id,
            "exhibit_name": exhibit.name,
            "reflection_prompts": result.get("output", ""),
            "knowledge_level": profile.knowledge_level,
            "reflection_depth": profile.reflection_depth,
            "session_id": result.get("session_id", ""),
        }

    async def chat(
        self,
        user_id: str,
        message: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """与策展人进行对话。

        Args:
            user_id: 用户ID
            message: 用户消息
            chat_history: 聊天历史（可选）

        Returns:
            包含回复内容的字典
        """
        # 获取用户画像以提供上下文
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 构建系统上下文
        context = f"""当前用户信息：
- 知识水平：{profile.knowledge_level}
- 叙事偏好：{profile.narrative_preference}
- 兴趣标签：{', '.join(profile.interests) if profile.interests else '无'}
- 已参观展品数：{len(profile.visited_exhibit_ids)}

用户问题：{message}"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=context,
            chat_history=chat_history or [],
        )

        return {
            "user_id": user_id,
            "message": message,
            "response": result.get("output", ""),
            "session_id": result.get("session_id", ""),
            "error": result.get("error"),
        }

    async def get_exhibit_info(
        self,
        user_id: str,
        exhibit_id: str,
    ) -> dict[str, Any]:
        """获取展品详细信息（包含知识检索）。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            包含展品信息和相关知识的字典

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        # 获取展品信息
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 获取用户画像
        await self._profile_service.get_or_create_profile(user_id)

        # 构建知识检索请求
        knowledge_request = f"""请检索以下展品的相关知识：

展品名称：{exhibit.name}
展品描述：{exhibit.description}
展品年代：{exhibit.era}
展品类别：{exhibit.category}

请使用knowledge_retrieval工具检索相关知识，exhibit_id为"{exhibit_id}"。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=knowledge_request,
            chat_history=[],
        )

        return {
            "user_id": user_id,
            "exhibit_id": exhibit_id,
            "exhibit": {
                "id": exhibit.id.value,
                "name": exhibit.name,
                "description": exhibit.description,
                "category": exhibit.category,
                "era": exhibit.era,
                "hall": exhibit.hall,
                "importance": exhibit.importance,
                "estimated_visit_time": exhibit.estimated_visit_time,
            },
            "knowledge": result.get("output", ""),
            "session_id": result.get("session_id", ""),
        }
