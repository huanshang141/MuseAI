import re
from enum import Enum
from typing import Any, Protocol

from app.application.ports.prompt_gateway import PromptGateway


class QueryTransformStrategy(Enum):
    NONE = "none"
    STEP_BACK = "step_back"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"


class LLMProviderPort(Protocol):
    async def generate(self, messages: list[dict[str, Any]]) -> Any: ...


class LLMResponseProtocol(Protocol):
    content: str


class ConversationAwareQueryRewriter:
    REWRITE_PROMPT = """你是一个博物馆导览助手。用户正在与您进行多轮对话。

对话历史：
{conversation_history}

当前用户问题：{query}

请根据对话历史，将用户的问题改写为一个独立、完整的问题，使其能够独立理解而不需要之前的上下文。
只输出改写后的问题，不要解释："""

    def __init__(
        self,
        llm_provider: LLMProviderPort,
        prompt_gateway: PromptGateway | None = None,
    ):
        self.llm_provider = llm_provider
        self.prompt_gateway = prompt_gateway

    def _format_conversation_history(self, history: list[dict[str, str]]) -> str:
        if not history:
            return "（无历史对话）"

        formatted = []
        for msg in history:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            formatted.append(f"{role}：{content}")

        return "\n".join(formatted)

    async def rewrite_with_context(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
    ) -> str:
        if not conversation_history:
            return query

        formatted_history = self._format_conversation_history(conversation_history)

        prompt = None
        if self.prompt_gateway:
            prompt = await self.prompt_gateway.render(
                "query_rewrite",
                {"conversation_history": formatted_history, "query": query},
            )

        if prompt is None:
            prompt = self.REWRITE_PROMPT.format(
                conversation_history=formatted_history,
                query=query,
            )

        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return str(response.content).strip()


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

    def __init__(
        self,
        llm_provider: Any,
        prompt_gateway: PromptGateway | None = None,
    ):
        self.llm_provider = llm_provider
        self.prompt_gateway = prompt_gateway

    async def transform_step_back(self, query: str) -> str:
        prompt = None
        if self.prompt_gateway:
            prompt = await self.prompt_gateway.render("query_step_back", {"query": query})

        if prompt is None:
            prompt = self.STEP_BACK_PROMPT.format(query=query)

        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return str(response.content).strip()

    async def transform_hyde(self, query: str) -> str:
        prompt = None
        if self.prompt_gateway:
            prompt = await self.prompt_gateway.render("query_hyde", {"query": query})

        if prompt is None:
            prompt = self.HYDE_PROMPT.format(query=query)

        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return str(response.content).strip()

    async def transform_multi_query(self, query: str) -> list[str]:
        prompt = None
        if self.prompt_gateway:
            prompt = await self.prompt_gateway.render("query_multi", {"query": query})

        if prompt is None:
            prompt = self.MULTI_QUERY_PROMPT.format(query=query)

        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])

        lines = str(response.content).strip().split("\n")
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
