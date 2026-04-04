import pytest
from app.workflows.multi_turn import (
    MultiTurnResult,
    MultiTurnStateMachine,
    State,
)


def test_state_machine_starts_in_start_state():
    state_machine = MultiTurnStateMachine()
    assert state_machine.current_state == State.START


def test_state_machine_transitions_to_retrieve_on_first_query():
    state_machine = MultiTurnStateMachine()
    state_machine.process(query="What is machine learning?")
    assert state_machine.current_state == State.RETRIEVE


def test_state_machine_evaluates_retrieval_quality():
    state_machine = MultiTurnStateMachine()
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.8)
    assert state_machine.current_state == State.EVALUATE


def test_high_quality_retrieval_transitions_to_generate():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.8)
    state_machine.evaluate()
    assert state_machine.current_state == State.GENERATE


def test_low_quality_retrieval_transitions_to_transform():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.5)
    state_machine.evaluate()
    assert state_machine.current_state == State.TRANSFORM


def test_transform_increments_attempt_counter():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.5)
    state_machine.evaluate()
    assert state_machine.attempts == 1


def test_transform_retries_retrieve():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.5)
    state_machine.apply_transform()
    assert state_machine.current_state == State.RETRIEVE


def test_max_attempts_forces_generate_on_low_quality():
    state_machine = MultiTurnStateMachine(score_threshold=0.7, max_attempts=3)
    state_machine.process(query="What is machine learning?")

    state_machine.set_retrieval_score(0.5)
    state_machine.evaluate()
    assert state_machine.attempts == 1
    state_machine.apply_transform()

    state_machine.set_retrieval_score(0.5)
    state_machine.evaluate()
    assert state_machine.attempts == 2
    state_machine.apply_transform()

    state_machine.set_retrieval_score(0.5)
    state_machine.evaluate()
    assert state_machine.attempts == 3
    state_machine.apply_transform()

    state_machine.set_retrieval_score(0.5)
    state_machine.evaluate()
    assert state_machine.current_state == State.GENERATE


def test_state_machine_returns_result_on_end():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    result = state_machine.run(
        query="What is machine learning?",
        retrieval_score=0.8,
        generated_answer="Machine learning is a subset of AI.",
    )
    assert result.state == State.END
    assert result.answer == "Machine learning is a subset of AI."
    assert result.attempts == 0


def test_result_includes_trace_info():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    result = state_machine.run(
        query="What is machine learning?",
        retrieval_score=0.8,
        generated_answer="Machine learning is a subset of AI.",
    )
    assert result.query == "What is machine learning?"
    assert result.retrieval_score == 0.8
    assert result.transformations == []


def test_result_tracks_transformations():
    state_machine = MultiTurnStateMachine(score_threshold=0.7, max_attempts=3)
    result = state_machine.run(
        query="What is machine learning?",
        retrieval_score=0.5,
        generated_answer="Machine learning is a subset of AI.",
    )
    assert result.attempts == 3
    assert len(result.transformations) == 3


def test_placeholder_transform_returns_original_query():
    state_machine = MultiTurnStateMachine()
    transformed = state_machine.transform_query("What is machine learning?")
    assert transformed == "What is machine learning?"


def test_custom_threshold_and_max_attempts():
    state_machine = MultiTurnStateMachine(score_threshold=0.8, max_attempts=5)
    assert state_machine.score_threshold == 0.8
    assert state_machine.max_attempts == 5


def test_result_dataclass_has_all_fields():
    result = MultiTurnResult(
        state=State.END,
        query="test query",
        answer="test answer",
        retrieval_score=0.8,
        attempts=1,
        transformations=["placeholder"],
    )
    assert result.state == State.END
    assert result.query == "test query"
    assert result.answer == "test answer"
    assert result.retrieval_score == 0.8
    assert result.attempts == 1
    assert result.transformations == ["placeholder"]


def test_evaluate_without_retrieval_score_raises_error():
    state_machine = MultiTurnStateMachine()
    state_machine.process(query="What is machine learning?")
    with pytest.raises(ValueError, match="No retrieval score set"):
        state_machine.evaluate()


def test_state_machine_default_parameters():
    state_machine = MultiTurnStateMachine()
    assert state_machine.score_threshold == 0.7
    assert state_machine.max_attempts == 3


def test_threshold_boundary_exact_match():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.7)
    state_machine.evaluate()
    assert state_machine.current_state == State.GENERATE


def test_threshold_boundary_just_below():
    state_machine = MultiTurnStateMachine(score_threshold=0.7)
    state_machine.process(query="What is machine learning?")
    state_machine.set_retrieval_score(0.69)
    state_machine.evaluate()
    assert state_machine.current_state == State.TRANSFORM


def test_run_with_high_score_no_transformations():
    state_machine = MultiTurnStateMachine(score_threshold=0.7, max_attempts=3)
    result = state_machine.run(
        query="What is machine learning?",
        retrieval_score=0.9,
        generated_answer="Machine learning is a subset of AI.",
    )
    assert result.attempts == 0
    assert result.transformations == []


def test_multiple_retrieval_attempts_in_run():
    state_machine = MultiTurnStateMachine(score_threshold=0.7, max_attempts=2)
    result = state_machine.run(
        query="What is machine learning?",
        retrieval_score=0.5,
        generated_answer="Machine learning is a subset of AI.",
    )
    assert result.attempts == 2
    assert result.transformations == ["placeholder", "placeholder"]
