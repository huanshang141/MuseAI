from typing import Any, TypedDict
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import StateGraph, END


SCORE_THRESHOLD = 0.7
MAX_ATTEMPTS = 3


class RAGState(TypedDict):
    query: str
    documents: list[Document]
    retrieval_score: float
    attempts: int
    transformations: list[str]
    answer: str


class RAGAgent:
    def __init__(
        self,
        llm: BaseChatModel,
        retriever: BaseRetriever,
        score_threshold: float = SCORE_THRESHOLD,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self.llm = llm
        self.retriever = retriever
        self.score_threshold = score_threshold
        self.max_attempts = max_attempts
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(RAGState)

        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("evaluate", self.evaluate)
        workflow.add_node("transform", self.transform)
        workflow.add_node("generate", self.generate)

        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "evaluate")
        workflow.add_conditional_edges(
            "evaluate",
            self._should_transform,
            {
                "transform": "transform",
                "generate": "generate",
            },
        )
        workflow.add_conditional_edges(
            "transform",
            self._should_retry,
            {
                "retry": "retrieve",
                "generate": "generate",
            },
        )
        workflow.add_edge("generate", END)

        return workflow.compile()

    def _should_transform(self, state: RAGState) -> str:
        if state["retrieval_score"] >= self.score_threshold:
            return "generate"
        if state["attempts"] >= self.max_attempts:
            return "generate"
        return "transform"

    def _should_retry(self, state: RAGState) -> str:
        if state["attempts"] >= self.max_attempts:
            return "generate"
        return "retry"

    async def retrieve(self, state: RAGState) -> dict[str, Any]:
        documents = await self.retriever._aget_relevant_documents(state["query"])
        return {"documents": documents}

    def evaluate(self, state: RAGState) -> dict[str, Any]:
        if not state["documents"]:
            return {"retrieval_score": 0.0}

        scores = []
        for doc in state["documents"]:
            score = doc.metadata.get("rrf_score", 0.5)
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        return {"retrieval_score": avg_score}

    def transform(self, state: RAGState) -> dict[str, Any]:
        return {
            "attempts": state["attempts"] + 1,
            "transformations": state["transformations"] + ["placeholder"],
        }

    async def generate(self, state: RAGState) -> dict[str, Any]:
        context = "\n\n".join(doc.page_content for doc in state["documents"])

        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {state["query"]}

Answer:"""

        response = await self.llm.ainvoke(prompt)
        return {"answer": response.content}

    async def run(self, query: str) -> RAGState:
        initial_state: RAGState = {
            "query": query,
            "documents": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
        }
        result = await self._graph.ainvoke(initial_state)
        return result
