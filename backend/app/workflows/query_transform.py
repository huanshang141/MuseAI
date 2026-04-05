import re
from enum import Enum


class QueryTransformStrategy(Enum):
    NONE = "none"
    STEP_BACK = "step_back"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"


def has_specific_details(query: str) -> bool:
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}",
        r"\d{1,2}:\d{2}",
        r"\d+%",
        r"\d+\s*(万|千|百|ten|hundred|thousand|million)",
    ]
    return any(re.search(p, query) for p in patterns)


def is_ambiguous(query: str) -> bool:
    ambiguous_words = ["那个", "这个", "它", "那个东西", "something", "it", "that"]
    query_lower = query.lower()
    return any(word in query_lower for word in ambiguous_words) or len(query) < 10


def select_strategy(query: str, retrieval_score: float, attempt: int) -> QueryTransformStrategy:
    if retrieval_score >= 0.7:
        return QueryTransformStrategy.NONE

    if attempt == 1:
        if has_specific_details(query):
            return QueryTransformStrategy.STEP_BACK
        elif is_ambiguous(query):
            return QueryTransformStrategy.MULTI_QUERY
        else:
            return QueryTransformStrategy.HYDE

    if attempt == 2:
        return QueryTransformStrategy.HYDE

    return QueryTransformStrategy.MULTI_QUERY
