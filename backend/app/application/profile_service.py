# backend/app/application/profile_service.py
from datetime import UTC, datetime
from typing import List, Optional

from app.domain.entities import VisitorProfile
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, ProfileId, UserId
from app.domain.repositories import VisitorProfileRepository


class ProfileService:
    """访客画像服务，管理用户偏好和参观历史。"""

    def __init__(self, profile_repository: VisitorProfileRepository):
        self._repository = profile_repository

    async def get_or_create_profile(self, user_id: str) -> VisitorProfile:
        """获取或创建访客画像。

        如果用户已存在画像则返回，否则创建默认画像。

        Args:
            user_id: 用户ID

        Returns:
            访客画像实体
        """
        user_id_vo = UserId(user_id)
        profile = await self._repository.get_by_user_id(user_id_vo)

        if profile is None:
            # 创建默认画像
            import uuid

            now = datetime.now(UTC)
            profile = VisitorProfile(
                id=ProfileId(str(uuid.uuid4())),
                user_id=user_id_vo,
                interests=[],
                knowledge_level="beginner",
                narrative_preference="balanced",
                reflection_depth="2",
                visited_exhibit_ids=[],
                feedback_history=[],
                created_at=now,
                updated_at=now,
            )
            profile = await self._repository.save(profile)

        return profile

    async def get_profile(self, user_id: str) -> Optional[VisitorProfile]:
        """根据用户ID获取访客画像。

        Args:
            user_id: 用户ID

        Returns:
            访客画像实体，如果不存在则返回None
        """
        return await self._repository.get_by_user_id(UserId(user_id))

    async def update_profile(
        self,
        user_id: str,
        interests: Optional[List[str]] = None,
        knowledge_level: Optional[str] = None,
        narrative_preference: Optional[str] = None,
        reflection_depth: Optional[str] = None,
    ) -> VisitorProfile:
        """更新访客画像。

        Args:
            user_id: 用户ID
            interests: 兴趣标签列表（可选）
            knowledge_level: 知识水平（beginner/intermediate/expert）（可选）
            narrative_preference: 叙事偏好（concise/balanced/detailed）（可选）
            reflection_depth: 反思深度（1-5）（可选）

        Returns:
            更新后的访客画像实体

        Raises:
            EntityNotFoundError: 如果用户画像不存在
        """
        profile = await self._repository.get_by_user_id(UserId(user_id))
        if profile is None:
            raise EntityNotFoundError(f"Profile not found for user: {user_id}")

        # 更新字段
        if interests is not None:
            profile.interests = interests
        if knowledge_level is not None:
            profile.knowledge_level = knowledge_level
        if narrative_preference is not None:
            profile.narrative_preference = narrative_preference
        if reflection_depth is not None:
            profile.reflection_depth = reflection_depth

        profile.updated_at = datetime.now(UTC)

        return await self._repository.save(profile)

    async def record_visit(self, user_id: str, exhibit_id: str) -> VisitorProfile:
        """记录用户参观展品。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            更新后的访客画像实体
        """
        profile = await self.get_or_create_profile(user_id)

        exhibit_id_vo = ExhibitId(exhibit_id)
        if exhibit_id_vo not in profile.visited_exhibit_ids:
            profile.visited_exhibit_ids.append(exhibit_id_vo)
            profile.updated_at = datetime.now(UTC)
            profile = await self._repository.save(profile)

        return profile

    async def add_feedback(self, user_id: str, feedback: str) -> VisitorProfile:
        """添加用户反馈。

        Args:
            user_id: 用户ID
            feedback: 反馈内容

        Returns:
            更新后的访客画像实体
        """
        profile = await self.get_or_create_profile(user_id)

        profile.feedback_history.append(feedback)
        profile.updated_at = datetime.now(UTC)

        return await self._repository.save(profile)

    async def get_visited_exhibits(self, user_id: str) -> List[ExhibitId]:
        """获取用户已参观的展品ID列表。

        Args:
            user_id: 用户ID

        Returns:
            已参观展品ID列表
        """
        profile = await self._repository.get_by_user_id(UserId(user_id))
        if profile is None:
            return []
        return profile.visited_exhibit_ids

    async def has_visited(self, user_id: str, exhibit_id: str) -> bool:
        """检查用户是否已参观过某展品。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            是否已参观
        """
        visited = await self.get_visited_exhibits(user_id)
        return ExhibitId(exhibit_id) in visited
