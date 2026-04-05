import pytest
from app.workflows.query_transform import QueryTransformStrategy, select_strategy


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
