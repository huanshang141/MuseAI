"""多轮对话上下文管理器单元测试。"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.context_manager import ConversationContextManager
from app.infra.redis.cache import RedisCache


class TestConversationContextManager:
    @pytest.fixture
    def mock_redis(self):
        """创建mock Redis缓存。"""
        redis = MagicMock(spec=RedisCache)
        redis.client = AsyncMock()
        redis.get_session_context = AsyncMock(return_value=None)
        redis.set_session_context = AsyncMock()
        redis.delete_session_context = AsyncMock()
        return redis

    @pytest.fixture
    def context_manager(self, mock_redis):
        """创建上下文管理器实例。"""
        return ConversationContextManager(mock_redis, max_history=10, ttl=3600)

    @pytest.mark.asyncio
    async def test_get_context_empty(self, context_manager, mock_redis):
        """测试获取空上下文。"""
        mock_redis.get_session_context.return_value = None

        result = await context_manager.get_context("session-1")

        assert result == []
        mock_redis.get_session_context.assert_called_once_with("session-1")

    @pytest.mark.asyncio
    async def test_get_context_with_history(self, context_manager, mock_redis):
        """测试获取有历史的上下文。"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        mock_redis.get_session_context.return_value = history

        result = await context_manager.get_context("session-1")

        assert result == history

    @pytest.mark.asyncio
    async def test_add_message_first(self, context_manager, mock_redis):
        """测试添加第一条消息。"""
        mock_redis.get_session_context.return_value = None

        await context_manager.add_message("session-1", "user", "Hello")

        mock_redis.set_session_context.assert_called_once()
        call_args = mock_redis.set_session_context.call_args
        assert call_args[0][0] == "session-1"
        assert call_args[0][1] == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_add_message_appends(self, context_manager, mock_redis):
        """测试追加消息到现有历史。"""
        existing = [{"role": "user", "content": "Hello"}]
        mock_redis.get_session_context.return_value = existing

        await context_manager.add_message("session-1", "assistant", "Hi!")

        call_args = mock_redis.set_session_context.call_args
        assert call_args[0][1] == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

    @pytest.mark.asyncio
    async def test_add_message_respects_max_history(self, mock_redis):
        """测试消息数量限制。"""
        context_manager = ConversationContextManager(mock_redis, max_history=3, ttl=3600)

        # 创建超过max_history的消息
        existing = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
        ]
        mock_redis.get_session_context.return_value = existing

        await context_manager.add_message("session-1", "assistant", "msg4")

        call_args = mock_redis.set_session_context.call_args
        saved_history = call_args[0][1]
        assert len(saved_history) == 3
        # 应该保留最新的3条
        assert saved_history[0]["content"] == "msg2"

    @pytest.mark.asyncio
    async def test_get_context_window(self, context_manager, mock_redis):
        """测试获取上下文窗口。"""
        history = [
            {"role": "user", "content": f"msg{i}"} for i in range(10)
        ]
        mock_redis.get_session_context.return_value = history

        result = await context_manager.get_context_window("session-1", window_size=3)

        assert len(result) == 3
        assert result[0]["content"] == "msg7"
        assert result[2]["content"] == "msg9"

    @pytest.mark.asyncio
    async def test_get_formatted_context_empty(self, context_manager, mock_redis):
        """测试格式化空上下文。"""
        mock_redis.get_session_context.return_value = None

        result = await context_manager.get_formatted_context("session-1")

        assert result == "（无历史对话）"

    @pytest.mark.asyncio
    async def test_get_formatted_context_with_history(self, context_manager, mock_redis):
        """测试格式化有历史的上下文。"""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！"},
        ]
        mock_redis.get_session_context.return_value = history

        result = await context_manager.get_formatted_context("session-1")

        assert "用户：你好" in result
        assert "助手：您好！" in result

    @pytest.mark.asyncio
    async def test_clear_context(self, context_manager, mock_redis):
        """测试清除上下文。"""
        await context_manager.clear_context("session-1")

        mock_redis.delete_session_context.assert_called_once_with("session-1")

    @pytest.mark.asyncio
    async def test_get_message_count(self, context_manager, mock_redis):
        """测试获取消息数量。"""
        history = [{"role": "user", "content": "msg1"}, {"role": "assistant", "content": "msg2"}]
        mock_redis.get_session_context.return_value = history

        count = await context_manager.get_message_count("session-1")

        assert count == 2

    @pytest.mark.asyncio
    async def test_set_user_preferences(self, context_manager, mock_redis):
        """测试设置用户偏好。"""
        preferences = {"language": "中文", "style": "detailed"}

        await context_manager.set_user_preferences("session-1", preferences)

        mock_redis.client.setex.assert_called_once()
        call_args = mock_redis.client.setex.call_args
        assert call_args[0][0] == "session:session-1:preferences"
        assert json.loads(call_args[0][2]) == preferences

    @pytest.mark.asyncio
    async def test_get_user_preferences(self, context_manager, mock_redis):
        """测试获取用户偏好。"""
        preferences = {"language": "中文"}
        mock_redis.client.get.return_value = json.dumps(preferences)

        result = await context_manager.get_user_preferences("session-1")

        assert result == preferences
        mock_redis.client.get.assert_called_once_with("session:session-1:preferences")

    @pytest.mark.asyncio
    async def test_get_user_preferences_not_found(self, context_manager, mock_redis):
        """测试获取不存在的用户偏好。"""
        mock_redis.client.get.return_value = None

        result = await context_manager.get_user_preferences("session-1")

        assert result is None
