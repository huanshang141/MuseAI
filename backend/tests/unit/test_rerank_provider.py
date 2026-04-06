"""Rerank Provider单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.infra.providers.rerank import (
    MockRerankProvider,
    OpenAICompatibleRerankProvider,
    RerankRequest,
    RerankResult,
)
from app.config.settings import Settings


class TestRerankRequest:
    def test_rerank_request_creation(self):
        request = RerankRequest(
            model="test-model",
            query="test query",
            documents=["doc1", "doc2"],
            top_n=5,
        )
        assert request.model == "test-model"
        assert request.query == "test query"
        assert request.documents == ["doc1", "doc2"]
        assert request.top_n == 5


class TestRerankResult:
    def test_rerank_result_creation(self):
        result = RerankResult(
            index=0,
            relevance_score=0.95,
            document="test document",
        )
        assert result.index == 0
        assert result.relevance_score == 0.95
        assert result.document == "test document"


class TestMockRerankProvider:
    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        provider = MockRerankProvider()
        results = await provider.rerank("query", [], 5)
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_basic(self):
        provider = MockRerankProvider()
        documents = [
            "This is about machine learning and AI.",
            "This document is unrelated.",
            "Machine learning models are powerful.",
        ]
        results = await provider.rerank("machine learning", documents, 3)

        assert len(results) == 3
        # 结果应按相关性降序排列
        assert results[0].relevance_score >= results[1].relevance_score
        # 最相关的文档应该是包含最多查询词的
        assert "machine learning" in results[0].document.lower()

    @pytest.mark.asyncio
    async def test_rerank_top_n(self):
        provider = MockRerankProvider()
        documents = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        results = await provider.rerank("query", documents, 2)
        assert len(results) == 2


class TestOpenAICompatibleRerankProvider:
    def test_from_settings_with_config(self):
        settings = Settings(
            RERANK_BASE_URL="https://api.example.com",
            RERANK_API_KEY="test-key",
            RERANK_MODEL="rerank-v1",
        )
        provider = OpenAICompatibleRerankProvider.from_settings(settings)
        assert provider is not None
        assert provider.base_url == "https://api.example.com"
        assert provider.model == "rerank-v1"

    def test_from_settings_without_config(self):
        settings = Settings(
            RERANK_BASE_URL="",
            RERANK_API_KEY="",
            RERANK_MODEL="",
        )
        provider = OpenAICompatibleRerankProvider.from_settings(settings)
        assert provider is None

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        provider = OpenAICompatibleRerankProvider(
            base_url="https://api.example.com",
            api_key="test-key",
            model="rerank-v1",
        )
        results = await provider.rerank("query", [], 5)
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_success(self):
        provider = OpenAICompatibleRerankProvider(
            base_url="https://api.example.com",
            api_key="test-key",
            model="rerank-v1",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.95, "document": "doc2"},
                {"index": 0, "relevance_score": 0.85, "document": "doc1"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            results = await provider.rerank("query", ["doc1", "doc2"], 5)

            assert len(results) == 2
            # 结果应按分数降序排列
            assert results[0].relevance_score == 0.95
            assert results[0].index == 1

    @pytest.mark.asyncio
    async def test_rerank_handles_cohere_format(self):
        """测试Cohere API响应格式（没有document字段）。"""
        provider = OpenAICompatibleRerankProvider(
            base_url="https://api.example.com",
            api_key="test-key",
            model="rerank-v1",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.7},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            results = await provider.rerank("query", ["doc1", "doc2"], 5)

            assert len(results) == 2
            assert results[0].document == ""  # 默认空字符串

    @pytest.mark.asyncio
    async def test_rerank_retries_on_error(self):
        """测试API调用失败时的重试机制。"""
        provider = OpenAICompatibleRerankProvider(
            base_url="https://api.example.com",
            api_key="test-key",
            model="rerank-v1",
            max_retries=3,
            retry_delay=0.1,
        )

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock(status_code=500))
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [{"index": 0, "relevance_score": 0.9, "document": "doc"}]}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post_method:
            mock_post_method.side_effect = mock_post

            results = await provider.rerank("query", ["doc"], 5)

            assert len(results) == 1
            assert call_count == 3  # 初始调用 + 2次重试 = 第3次成功


class TestCreateRerankProvider:
    def test_create_siliconflow_provider(self):
        """测试创建 SiliconFlow provider。"""
        from app.infra.providers.rerank import create_rerank_provider, SiliconFlowRerankProvider

        settings = Settings(
            RERANK_PROVIDER="siliconflow",
            RERANK_API_KEY="test-api-key",
            RERANK_MODEL="BAAI/bge-reranker-v2-m3",
        )
        provider = create_rerank_provider(settings)

        assert provider is not None
        assert isinstance(provider, SiliconFlowRerankProvider)
        assert provider.model == "BAAI/bge-reranker-v2-m3"
        assert provider.api_key == "test-api-key"

    def test_create_openai_provider(self):
        """测试创建 OpenAI compatible provider。"""
        from app.infra.providers.rerank import create_rerank_provider, OpenAICompatibleRerankProvider

        settings = Settings(
            RERANK_PROVIDER="openai",
            RERANK_BASE_URL="https://api.openai.com",
            RERANK_API_KEY="test-key",
            RERANK_MODEL="rerank-v1",
        )
        provider = create_rerank_provider(settings)

        assert provider is not None
        assert isinstance(provider, OpenAICompatibleRerankProvider)

    def test_create_mock_provider(self):
        """测试创建 Mock provider。"""
        from app.infra.providers.rerank import create_rerank_provider, MockRerankProvider

        settings = Settings(
            RERANK_PROVIDER="mock",
        )
        provider = create_rerank_provider(settings)

        assert provider is not None
        assert isinstance(provider, MockRerankProvider)

    def test_create_provider_no_config_returns_none(self):
        """测试无配置时返回None。"""
        from app.infra.providers.rerank import create_rerank_provider

        settings = Settings(
            RERANK_PROVIDER="openai",
            RERANK_BASE_URL="",
            RERANK_API_KEY="",
        )
        provider = create_rerank_provider(settings)

        assert provider is None

    def test_create_unknown_provider_returns_none(self):
        """测试未知provider返回None。"""
        from app.infra.providers.rerank import create_rerank_provider

        settings = Settings(
            RERANK_PROVIDER="unknown_provider",
            RERANK_BASE_URL="https://example.com",
            RERANK_API_KEY="test-key",
        )
        provider = create_rerank_provider(settings)

        assert provider is None

    def test_create_provider_case_insensitive(self):
        """测试provider名称大小写不敏感。"""
        from app.infra.providers.rerank import create_rerank_provider, SiliconFlowRerankProvider

        settings = Settings(
            RERANK_PROVIDER="SILICONFLOW",  # 大写
            RERANK_API_KEY="test-key",
        )
        provider = create_rerank_provider(settings)

        assert provider is not None
        assert isinstance(provider, SiliconFlowRerankProvider)
