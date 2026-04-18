from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.application.workflows.query_transform import (
    QueryTransformer,
    QueryTransformStrategy,
    select_strategy,
)


class State(Enum):
    START = "start"
    RETRIEVE = "retrieve"
    EVALUATE = "evaluate"
    TRANSFORM = "transform"
    GENERATE = "generate"
    END = "end"


@dataclass
class MultiTurnResult:
    state: State
    query: str
    answer: str
    retrieval_score: float
    attempts: int
    transformations: list[str]


class MultiTurnStateMachine:
    def __init__(
        self,
        score_threshold: float = 0.7,
        max_attempts: int = 3,
        llm_provider: Any | None = None,
    ):
        self.score_threshold = score_threshold
        self.max_attempts = max_attempts
        self.llm_provider = llm_provider
        self.current_state = State.START
        self.attempts = 0
        self._query: str | None = None
        self._retrieval_score: float | None = None
        self._transformations: list[str] = []

    def process(self, query: str) -> None:
        self._query = query
        self.current_state = State.RETRIEVE

    def set_retrieval_score(self, score: float) -> None:
        self._retrieval_score = score
        self.current_state = State.EVALUATE

    def evaluate(self) -> None:
        if self._retrieval_score is None:
            raise ValueError("No retrieval score set")

        if self._retrieval_score >= self.score_threshold:
            self.current_state = State.GENERATE
        elif self.attempts < self.max_attempts:
            self.current_state = State.TRANSFORM
            self.attempts += 1
        else:
            self.current_state = State.GENERATE

    def apply_transform(self) -> None:
        self._transformations.append("placeholder")
        self.current_state = State.RETRIEVE

    async def transform_query(self, query: str, retrieval_score: float) -> list[str]:
        strategy = select_strategy(query, retrieval_score, self.attempts)

        if strategy == QueryTransformStrategy.NONE:
            return [query]

        if self.llm_provider is None:
            return [query]

        transformer = QueryTransformer(self.llm_provider)

        if strategy == QueryTransformStrategy.STEP_BACK:
            transformed = await transformer.transform_step_back(query)
            self._transformations.append(f"step_back: {transformed}")
            return [transformed]
        elif strategy == QueryTransformStrategy.HYDE:
            transformed = await transformer.transform_hyde(query)
            self._transformations.append(f"hyde: {transformed}")
            return [transformed]
        elif strategy == QueryTransformStrategy.MULTI_QUERY:
            queries = await transformer.transform_multi_query(query)
            self._transformations.append(f"multi_query: {', '.join(queries)}")
            return queries

        return [query]

    def run(
        self,
        query: str,
        retrieval_score: float,
        generated_answer: str,
    ) -> MultiTurnResult:
        self.current_state = State.START
        self.attempts = 0
        self._transformations = []

        self.process(query)

        while self.current_state != State.GENERATE:
            self.set_retrieval_score(retrieval_score)
            self.evaluate()

            if self.current_state == State.TRANSFORM:
                self.apply_transform()

        self.current_state = State.END

        return MultiTurnResult(
            state=self.current_state,
            query=query,
            answer=generated_answer,
            retrieval_score=retrieval_score,
            attempts=self.attempts,
            transformations=self._transformations,
        )
