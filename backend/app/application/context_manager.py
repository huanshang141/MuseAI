"""多轮对话上下文管理模块。

使用Redis存储和管理会话上下文。
"""

import json
from typing import Any

from loguru import logger

from app.infra.redis.cache import RedisCache


class ConversationContextManager:
    """多轮对话上下文管理器。

    使用Redis存储会话历史，支持上下文窗口管理。
    """

    def __init__(self, redis_cache: RedisCache, max_history: int = 10, ttl: int = 3600):
        """初始化上下文管理器。

        Args:
            redis_cache: Redis缓存实例
            max_history: 最大历史消息数
            ttl: 缓存过期时间（秒）
        """
        self.redis = redis_cache
        self.max_history = max_history
        self.ttl = ttl

    async def get_context(self, session_id: str) -> list[dict[str, str]]:
        """获取会话的完整上下文。

        Args:
            session_id: 会话ID

        Returns:
            消息列表，每项包含role和content
        """
        messages = await self.redis.get_session_context(session_id)
        return messages if messages else []

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """添加消息到会话上下文。

        Args:
            session_id: 会话ID
            role: 消息角色（user/assistant）
            content: 消息内容
        """
        messages = await self.get_context(session_id)
        messages.append({"role": role, "content": content})

        # 保持历史消息数量限制
        if len(messages) > self.max_history:
            messages = messages[-self.max_history:]

        await self.redis.set_session_context(session_id, messages, ttl=self.ttl)
        logger.debug(f"Added {role} message to session {session_id}, total: {len(messages)}")

    async def get_context_window(
        self,
        session_id: str,
        window_size: int = 5,
    ) -> list[dict[str, str]]:
        """获取最近N条消息的上下文窗口。

        Args:
            session_id: 会话ID
            window_size: 窗口大小

        Returns:
            最近N条消息列表
        """
        messages = await self.get_context(session_id)
        return messages[-window_size:] if messages else []

    async def get_formatted_context(
        self,
        session_id: str,
        window_size: int = 5,
    ) -> str:
        """获取格式化的上下文文本（用于LLM prompt）。

        Args:
            session_id: 会话ID
            window_size: 窗口大小

        Returns:
            格式化的对话历史文本
        """
        messages = await self.get_context_window(session_id, window_size)

        if not messages:
            return "（无历史对话）"

        formatted = []
        for msg in messages:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            formatted.append(f"{role}：{content}")

        return "\n".join(formatted)

    async def clear_context(self, session_id: str) -> None:
        """清除会话上下文。

        Args:
            session_id: 会话ID
        """
        await self.redis.delete_session_context(session_id)
        logger.info(f"Cleared context for session {session_id}")

    async def get_message_count(self, session_id: str) -> int:
        """获取会话消息数量。

        Args:
            session_id: 会话ID

        Returns:
            消息数量
        """
        messages = await self.get_context(session_id)
        return len(messages)

    async def set_user_preferences(
        self,
        session_id: str,
        preferences: dict[str, Any],
    ) -> None:
        """设置用户的导览偏好。

        Args:
            session_id: 会话ID
            preferences: 偏好设置（如语言、风格等）
        """
        key = f"session:{session_id}:preferences"
        await self.redis.client.setex(key, self.ttl, json.dumps(preferences))

    async def get_user_preferences(self, session_id: str) -> dict[str, Any] | None:
        """获取用户的导览偏好。

        Args:
            session_id: 会话ID

        Returns:
            偏好设置，如果不存在则返回None
        """
        key = f"session:{session_id}:preferences"
        data = await self.redis.client.get(key)
        return json.loads(data) if data else None
