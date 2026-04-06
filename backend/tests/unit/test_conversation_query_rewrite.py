"""多轮对话查询重写单元测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.workflows.query_transform import ConversationAwareQueryRewriter


class TestConversationAwareQueryRewriter:
    def test_format_conversation_history_empty(self):
        """测试空对话历史格式化。"""
        mock_llm = MagicMock()
        rewriter = ConversationAwareQueryRewriter(mock_llm)
        result = rewriter._format_conversation_history([])
        assert result == "（无历史对话）"

    def test_format_conversation_history_single(self):
        """测试单条对话历史格式化。"""
        mock_llm = MagicMock()
        rewriter = ConversationAwareQueryRewriter(mock_llm)
        history = [{"role": "user", "content": "你好"}]
        result = rewriter._format_conversation_history(history)
        assert result == "用户：你好"

    def test_format_conversation_history_multiple(self):
        """测试多条对话历史格式化。"""
        mock_llm = MagicMock()
        rewriter = ConversationAwareQueryRewriter(mock_llm)
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！有什么可以帮助您的？"},
            {"role": "user", "content": "我想了解青铜器"},
        ]
        result = rewriter._format_conversation_history(history)
        assert "用户：你好" in result
        assert "助手：您好！有什么可以帮助您的？" in result
        assert "用户：我想了解青铜器" in result

    @pytest.mark.asyncio
    async def test_rewrite_with_context_empty_history(self):
        """测试空历史时返回原查询。"""
        mock_llm = AsyncMock()
        rewriter = ConversationAwareQueryRewriter(mock_llm)

        result = await rewriter.rewrite_with_context("这是什么？", [])

        assert result == "这是什么？"
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_rewrite_with_context_success(self):
        """测试成功重写查询。"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(content="这件青铜器是什么时候制作的？")
        )
        rewriter = ConversationAwareQueryRewriter(mock_llm)

        history = [
            {"role": "user", "content": "请介绍一下这件青铜器"},
            {"role": "assistant", "content": "这是一件商代青铜器"},
        ]

        result = await rewriter.rewrite_with_context("它是什么时候制作的？", history)

        assert result == "这件青铜器是什么时候制作的？"
        mock_llm.generate.assert_called_once()

        # 验证prompt包含对话历史
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0][0]["content"]
        assert "用户：请介绍一下这件青铜器" in prompt
        assert "助手：这是一件商代青铜器" in prompt
        assert "它是什么时候制作的？" in prompt

    @pytest.mark.asyncio
    async def test_rewrite_with_context_strips_whitespace(self):
        """测试重写结果去除首尾空白。"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(content="  重写后的查询  \n")
        )
        rewriter = ConversationAwareQueryRewriter(mock_llm)

        history = [{"role": "user", "content": "之前的问题"}]
        result = await rewriter.rewrite_with_context("它是什么？", history)

        assert result == "重写后的查询"
