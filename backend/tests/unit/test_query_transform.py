from unittest.mock import AsyncMock

import pytest
from app.application.workflows.query_transform import (
    QueryTransformer,
    QueryTransformStrategy,
    has_specific_details,
    is_ambiguous,
    select_strategy,
)
from app.infra.providers.llm import LLMResponse


def test_strategy_enum_values():
    assert QueryTransformStrategy.NONE.value == "none"
    assert QueryTransformStrategy.STEP_BACK.value == "step_back"
    assert QueryTransformStrategy.HYDE.value == "hyde"
    assert QueryTransformStrategy.MULTI_QUERY.value == "multi_query"


def test_select_strategy_high_score_returns_none():
    strategy = select_strategy(query="test query", retrieval_score=0.8, attempt=1)
    assert strategy == QueryTransformStrategy.NONE


def test_select_strategy_low_score_first_attempt_with_details():
    strategy = select_strategy(query="What happened on 2024-01-15?", retrieval_score=0.3, attempt=1)
    assert strategy == QueryTransformStrategy.STEP_BACK


def test_select_strategy_low_score_second_attempt():
    strategy = select_strategy(query="test query", retrieval_score=0.3, attempt=2)
    assert strategy == QueryTransformStrategy.HYDE


def test_select_strategy_low_score_third_attempt():
    strategy = select_strategy(query="test query", retrieval_score=0.3, attempt=3)
    assert strategy == QueryTransformStrategy.MULTI_QUERY


def test_select_strategy_ambiguous_query_returns_multi_query():
    strategy = select_strategy(query="那个", retrieval_score=0.3, attempt=1)
    assert strategy == QueryTransformStrategy.MULTI_QUERY


def test_select_strategy_no_details_not_ambiguous_returns_hyde():
    strategy = select_strategy(
        query="What is the weather like today in Beijing?",
        retrieval_score=0.3,
        attempt=1,
    )
    assert strategy == QueryTransformStrategy.HYDE


class TestHasSpecificDetails:
    def test_date_yyyy_mm_dd(self):
        assert has_specific_details("What happened on 2024-01-15?") is True

    def test_date_yyyy_mm_dd_slash(self):
        assert has_specific_details("Event on 2024/01/15") is True

    def test_time_format(self):
        assert has_specific_details("Meeting at 14:30") is True

    def test_percentage(self):
        assert has_specific_details("Growth of 50%") is True

    def test_chinese_number_words(self):
        assert has_specific_details("价格上涨了3万") is True

    def test_english_number_words(self):
        assert has_specific_details("Over 1 thousand items") is True

    def test_no_specific_details(self):
        assert has_specific_details("What is the weather?") is False

    def test_plain_text(self):
        assert has_specific_details("Hello world") is False


class TestIsAmbiguous:
    def test_chinese_ambiguous_word_nage(self):
        assert is_ambiguous("那个是什么") is True

    def test_chinese_ambiguous_word_zhege(self):
        assert is_ambiguous("这个东西很好") is True

    def test_chinese_ambiguous_word_ta(self):
        assert is_ambiguous("它在哪里") is True

    def test_english_ambiguous_word_something(self):
        assert is_ambiguous("Tell me about something") is True

    def test_english_ambiguous_word_it(self):
        assert is_ambiguous("What is it?") is True

    def test_english_ambiguous_word_that(self):
        assert is_ambiguous("Show me that") is True

    def test_short_query(self):
        assert is_ambiguous("short") is True

    def test_query_exactly_10_chars(self):
        assert is_ambiguous("1234567890") is False

    def test_non_ambiguous_query(self):
        assert is_ambiguous("What is the weather like today?") is False

    def test_it_in_word_not_ambiguous(self):
        assert is_ambiguous("iterate through items") is False

    def test_that_in_word_not_ambiguous(self):
        assert is_ambiguous("thatch roof design") is False

    def test_standalone_it_is_ambiguous(self):
        assert is_ambiguous("what is it?") is True

    def test_standalone_that_is_ambiguous(self):
        assert is_ambiguous("I want that") is True


class TestQueryTransformer:
    @pytest.mark.asyncio
    async def test_transform_step_back(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(
            content="这个时期有什么重要的历史事件？",
            model="mock",
            prompt_tokens=10,
            completion_tokens=10,
            duration_ms=100,
        )

        transformer = QueryTransformer(mock_llm)
        result = await transformer.transform_step_back("2024年1月发生了什么？")

        assert result == "这个时期有什么重要的历史事件？"
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_transform_hyde(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(
            content="这是一件青铜器，用于祭祀仪式，年代可追溯到商朝。",
            model="mock",
            prompt_tokens=10,
            completion_tokens=10,
            duration_ms=100,
        )

        transformer = QueryTransformer(mock_llm)
        result = await transformer.transform_hyde("这件文物是什么？")

        assert "青铜器" in result
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_transform_multi_query(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(
            content="1. 这件文物的历史背景是什么？\n2. 这件文物的用途是什么？\n3. 这件文物的制作工艺如何？",
            model="mock",
            prompt_tokens=10,
            completion_tokens=10,
            duration_ms=100,
        )

        transformer = QueryTransformer(mock_llm)
        result = await transformer.transform_multi_query("这件文物是什么？")

        assert len(result) == 3
        assert "历史背景" in result[0]
        assert "用途" in result[1]
        assert "制作工艺" in result[2]

    @pytest.mark.asyncio
    async def test_transform_multi_query_empty_response_returns_original(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(
            content="",
            model="mock",
            prompt_tokens=10,
            completion_tokens=10,
            duration_ms=100,
        )

        transformer = QueryTransformer(mock_llm)
        result = await transformer.transform_multi_query("original query")

        assert result == ["original query"]
