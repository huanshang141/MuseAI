# ruff: noqa: E501
"""RAG Agent模块。

使用LangGraph实现多轮RAG检索状态机。
"""

from typing import Any, TypedDict

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, StateGraph
from loguru import logger

from app.application.ports.prompt_gateway import PromptGateway
from app.application.workflows.query_transform import ConversationAwareQueryRewriter
from app.infra.providers.rerank import BaseRerankProvider, RerankResult

SCORE_THRESHOLD = 0.7
MAX_ATTEMPTS = 3


class RAGState(TypedDict):
    """RAG状态机的状态定义。"""

    query: str
    rewritten_query: str
    documents: list[Document]
    reranked_documents: list[Document]
    retrieval_score: float
    attempts: int
    transformations: list[str]
    answer: str
    conversation_history: list[dict[str, str]]
    system_prompt: str


class RAGAgent:
    """RAG检索Agent，使用LangGraph状态机管理检索流程。"""

    FALLBACK_PROMPT = """你是一个博物馆导览助手。请基于以下上下文回答用户的问题。
如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。

上下文：
{context}

用户问题：{query}

请提供准确、友好的回答："""

    def __init__(
        self,
        llm: BaseChatModel,
        retriever: BaseRetriever,
        rerank_provider: BaseRerankProvider | None = None,
        query_rewriter: ConversationAwareQueryRewriter | None = None,
        prompt_gateway: PromptGateway | None = None,
        score_threshold: float = SCORE_THRESHOLD,
        max_attempts: int = MAX_ATTEMPTS,
        rerank_top_n: int = 5,
    ):
        """初始化RAG Agent。

        Args:
            llm: 语言模型
            retriever: 检索器
            rerank_provider: Rerank服务提供者（可选）
            query_rewriter: 查询重写器（可选）
            prompt_gateway: Prompt网关（可选）
            score_threshold: 检索评分阈值
            max_attempts: 最大重试次数
            rerank_top_n: Rerank返回的文档数量
        """
        self.llm = llm
        self.retriever = retriever
        self.rerank_provider = rerank_provider
        self.query_rewriter = query_rewriter
        self.prompt_gateway = prompt_gateway
        self.score_threshold = score_threshold
        self.max_attempts = max_attempts
        self.rerank_top_n = rerank_top_n
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建LangGraph状态机。"""
        workflow = StateGraph(RAGState)

        # 添加节点
        workflow.add_node("rewrite", self.rewrite_query)
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("rerank", self.rerank)
        workflow.add_node("evaluate", self.evaluate)
        workflow.add_node("transform", self.transform)
        workflow.add_node("generate", self.generate)

        # 设置入口点
        workflow.set_entry_point("rewrite")

        # 定义边
        workflow.add_edge("rewrite", "retrieve")
        workflow.add_edge("retrieve", "rerank")
        workflow.add_edge("rerank", "evaluate")

        # 条件边：评估后决定是转换还是生成
        workflow.add_conditional_edges(
            "evaluate",
            self._should_transform,
            {
                "transform": "transform",
                "generate": "generate",
            },
        )

        # 条件边：转换后决定是重试还是生成
        workflow.add_conditional_edges(
            "transform",
            self._should_retry,
            {
                "retry": "rewrite",
                "generate": "generate",
            },
        )

        workflow.add_edge("generate", END)

        return workflow.compile()

    def _should_transform(self, state: RAGState) -> str:
        """判断是否需要查询转换。"""
        if state["retrieval_score"] >= self.score_threshold:
            return "generate"
        if state["attempts"] >= self.max_attempts:
            return "generate"
        return "transform"

    def _should_retry(self, state: RAGState) -> str:
        """判断是否应该重试检索。"""
        if state["attempts"] >= self.max_attempts:
            return "generate"
        return "retry"

    async def rewrite_query(self, state: RAGState) -> dict[str, Any]:
        """重写查询（基于多轮对话历史）。"""
        query = state["query"]
        history = state.get("conversation_history", [])

        # 如果有查询重写器且有对话历史，则进行上下文感知的重写
        if self.query_rewriter and history:
            try:
                rewritten = await self.query_rewriter.rewrite_with_context(query, history)
                logger.info(f"Query rewritten: '{query}' -> '{rewritten}'")
                return {"rewritten_query": rewritten}
            except Exception as e:
                logger.warning(f"Query rewrite failed: {e}, using original query")

        return {"rewritten_query": query}

    async def retrieve(self, state: RAGState) -> dict[str, Any]:
        """检索相关文档。"""
        # 使用重写后的查询进行检索
        query = state.get("rewritten_query") or state["query"]
        documents = await self.retriever.ainvoke(query)
        logger.debug(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
        return {"documents": documents}

    async def rerank(self, state: RAGState) -> dict[str, Any]:
        """对检索结果进行重排序。"""
        documents = state["documents"]
        query = state.get("rewritten_query") or state["query"]

        logger.debug(f"Rerank node called: documents_count={len(documents)}, rerank_provider={self.rerank_provider is not None}")

        # 如果没有Rerank服务或没有文档，直接返回原结果
        if not self.rerank_provider or not documents:
            logger.info(f"Rerank skipped: rerank_provider={'configured' if self.rerank_provider else 'None'}, docs_count={len(documents)}")
            return {"reranked_documents": documents}

        try:
            # 提取文档内容用于rerank
            doc_contents = [doc.page_content for doc in documents]

            logger.info(f"Calling rerank service: query='{query[:50]}...', docs_count={len(documents)}")

            # 调用rerank服务
            rerank_results: list[RerankResult] = await self.rerank_provider.rerank(
                query=query,
                documents=doc_contents,
                top_n=min(self.rerank_top_n, len(documents)),
            )

            # 根据rerank结果重新排序文档
            reranked_docs = []
            for result in rerank_results:
                original_doc = documents[result.index]
                # 更新文档的metadata，添加rerank分数
                updated_metadata = {**original_doc.metadata, "rerank_score": result.relevance_score}
                reranked_doc = Document(
                    page_content=original_doc.page_content,
                    metadata=updated_metadata,
                )
                reranked_docs.append(reranked_doc)

            logger.info(f"Reranked {len(reranked_docs)} documents successfully")
            return {"reranked_documents": reranked_docs}

        except Exception as e:
            logger.warning(f"Rerank failed: {e}, using original order")
            return {"reranked_documents": documents}

    def evaluate(self, state: RAGState) -> dict[str, Any]:
        """评估检索质量。"""
        # 优先使用rerank后的文档
        docs = state.get("reranked_documents") or state["documents"]

        if not docs:
            return {"retrieval_score": 0.0}

        # 计算平均分数
        scores = []
        for doc in docs:
            # 优先使用rerank分数，其次使用rrf分数
            score = doc.metadata.get("rerank_score", doc.metadata.get("rrf_score", 0.5))
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        logger.debug(f"Evaluation score: {avg_score:.3f} from {len(docs)} documents")
        return {"retrieval_score": avg_score}

    def transform(self, state: RAGState) -> dict[str, Any]:
        """查询转换（当检索质量不佳时）。"""
        return {
            "attempts": state["attempts"] + 1,
            "transformations": state["transformations"] + ["query_transform"],
        }

    async def generate(self, state: RAGState) -> dict[str, Any]:
        """生成答案。"""
        docs = state.get("reranked_documents") or state["documents"]
        context = "\n\n".join(doc.page_content for doc in docs)

        custom_system_prompt = state.get("system_prompt", "")

        if custom_system_prompt:
            prompt = f"{custom_system_prompt}\n\n参考上下文：\n{context}\n\n用户问题：{state['query']}\n\n请基于以上信息回答："
        else:
            prompt = None
            if self.prompt_gateway:
                prompt = await self.prompt_gateway.render(
                    "rag_answer_generation",
                    {"context": context, "query": state["query"]}
                )
            if prompt is None:
                prompt = self.FALLBACK_PROMPT.format(
                    context=context,
                    query=state["query"],
                )

        response = await self.llm.ainvoke(prompt)
        return {"answer": response.content}

    async def run(
        self,
        query: str,
        conversation_history: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> RAGState:
        """运行RAG流程。

        Args:
            query: 用户查询
            conversation_history: 对话历史（可选）
            system_prompt: 自定义系统提示词（可选，用于导览等场景）

        Returns:
            最终状态
        """
        initial_state: RAGState = {
            "query": query,
            "rewritten_query": "",
            "documents": [],
            "reranked_documents": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": conversation_history or [],
            "system_prompt": system_prompt or "",
        }
        result = await self._graph.ainvoke(initial_state)
        return result  # type: ignore[no-any-return]
