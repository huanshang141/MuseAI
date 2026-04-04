from dataclasses import dataclass
from enum import Enum


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
    ):
        self.score_threshold = score_threshold
        self.max_attempts = max_attempts
        self.current_state = State.START
        self.attempts = 0
        self._query: str | None = None
        self._retrieval_score: float | None = None
        self._transformations: list[str] = []
        self._answer: str | None = None

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

    def transform_query(self, query: str) -> str:
        return query

    def run(
        self,
        query: str,
        retrieval_score: float,
        generated_answer: str,
    ) -> MultiTurnResult:
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
