import re
from enum import Enum
from typing import Any


class QueryTransformStrategy(Enum):
    NONE = "none"
    STEP_BACK = "step_back"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"


class QueryTransformer:
    STEP_BACK_PROMPT = """你是一个查询优化专家。用户提出了一个过于具体的问题，
请生成一个更抽象、更宽泛的问题，帮助获取更多背景信息。

原始问题：{query}

请生成一个更抽象的问题（只输出问题本身，不要解释）："""

    HYDE_PROMPT = """你是一个查询优化专家。请为用户的问题生成一个假设性的答案，
用于检索相关文档。

用户问题：{query}

请生成一个假设性的答案（只输出答案，不要解释）："""

    MULTI_QUERY_PROMPT = """你是一个查询优化专家。用户的问题可能有歧义或过于宽泛，
请生成3个相关的、更具体的问题，每个问题一行，用数字编号。

用户问题：{query}

请生成3个相关问题："""

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    async def transform_step_back(self, query: str) -> str:
        prompt = self.STEP_BACK_PROMPT.format(query=query)
        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return response.content.strip()

    async def transform_hyde(self, query: str) -> str:
        prompt = self.HYDE_PROMPT.format(query=query)
        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return response.content.strip()

    async def transform_multi_query(self, query: str) -> list[str]:
        prompt = self.MULTI_QUERY_PROMPT.format(query=query)
        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])

        lines = response.content.strip().split("\n")
        queries = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                cleaned = line.lstrip("0123456789.-) ")
                if cleaned:
                    queries.append(cleaned)

        return queries[:3] if queries else [query]


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
    for word in ambiguous_words:
        if any(ord(c) > 127 for c in word):
            if word in query_lower:
                return True
        else:
            if re.search(r"\b" + re.escape(word) + r"\b", query_lower):
                return True
    return len(query) < 10


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
