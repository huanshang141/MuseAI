from dataclasses import dataclass

from langchain_core.documents import Document


@dataclass(frozen=True)
class FilterConfig:
    absolute_threshold: float = 0.25
    relative_gap: float = 0.25
    min_docs: int = 1
    max_docs: int = 8

    def __post_init__(self):
        if self.min_docs < 1:
            raise ValueError(f"min_docs must be >= 1, got {self.min_docs}")
        if self.max_docs < self.min_docs:
            raise ValueError(
                f"max_docs must be >= min_docs, got max_docs={self.max_docs}, min_docs={self.min_docs}"
            )
        if not 0.0 <= self.absolute_threshold <= 1.0:
            raise ValueError(
                f"absolute_threshold must be between 0 and 1, got {self.absolute_threshold}"
            )
        if not 0.0 <= self.relative_gap <= 1.0:
            raise ValueError(
                f"relative_gap must be between 0 and 1, got {self.relative_gap}"
            )


class DynamicDocumentFilter:

    def __init__(self, config: FilterConfig | None = None):
        self.config = config or FilterConfig()

    def _get_score(self, doc: Document) -> float:
        return doc.metadata.get("rerank_score", doc.metadata.get("rrf_score", 0.0))

    def filter(self, documents: list[Document]) -> list[Document]:
        if not documents:
            return []

        sorted_docs = sorted(documents, key=self._get_score, reverse=True)
        scores = [self._get_score(d) for d in sorted_docs]
        max_score = scores[0]

        absolute_cutoff_index = len(sorted_docs)
        for i, score in enumerate(scores):
            if score < self.config.absolute_threshold and i >= self.config.min_docs:
                absolute_cutoff_index = i
                break

        candidates = sorted_docs[:absolute_cutoff_index]
        candidate_scores = scores[:absolute_cutoff_index]

        if not candidates:
            return sorted_docs[: self.config.min_docs]

        relative_cutoff = max_score * (1.0 - self.config.relative_gap)
        gap_cutoff_index = len(candidates)
        for i, score in enumerate(candidate_scores):
            if score < relative_cutoff and i >= self.config.min_docs:
                gap_cutoff_index = i
                break

        result = candidates[:gap_cutoff_index]

        if len(result) < self.config.min_docs:
            result = sorted_docs[: self.config.min_docs]
        if len(result) > self.config.max_docs:
            result = result[: self.config.max_docs]

        return result
