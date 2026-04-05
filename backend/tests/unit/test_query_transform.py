import pytest
from app.workflows.query_transform import (
    QueryTransformStrategy,
    select_strategy,
    has_specific_details,
    is_ambiguous,
)


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
