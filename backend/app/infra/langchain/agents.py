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
from app.application.workflows.query_transform import (
    ConversationAwareQueryRewriter,
    QueryTransformer,
    QueryTransformStrategy,
    select_strategy,
)
from app.infra.providers.rerank import BaseRerankProvider, RerankResult

SCORE_THRESHOLD = 0.7
MAX_ATTEMPTS = 3


class RAGState(TypedDict):
    """RAG状态机的状态定义。"""

    query: str
    rewritten_query: str
    documents: list[Document]
    merged_documents: list[Document]
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
        llm_provider: Any | None = None,
        score_threshold: float = SCORE_THRESHOLD,
        max_attempts: int = MAX_ATTEMPTS,
        rerank_top_n: int = 5,
        merge_enabled: bool = True,
        merge_max_level: int = 1,
        merge_max_parents: int = 3,
    ):
        """初始化RAG Agent。

        Args:
            llm: 语言模型
            retriever: 检索器
            rerank_provider: Rerank服务提供者（可选）
            query_rewriter: 查询重写器（可选）
            prompt_gateway: Prompt网关（可选）
            llm_provider: LLM提供者（可选，用于查询转换）
            score_threshold: 检索评分阈值
            max_attempts: 最大重试次数
            rerank_top_n: Rerank返回的文档数量
            merge_enabled: 是否启用层级合并
            merge_max_level: 合并时允许的最大chunk_level
            merge_max_parents: 最多替换多少个父文档
        """
        self.llm = llm
        self.retriever = retriever
        self.rerank_provider = rerank_provider
        self.query_rewriter = query_rewriter
        self.prompt_gateway = prompt_gateway
        self.llm_provider = llm_provider
        self.score_threshold = score_threshold
        self.max_attempts = max_attempts
        self.rerank_top_n = rerank_top_n
        self.merge_enabled = merge_enabled
        self.merge_max_level = merge_max_level
        self.merge_max_parents = merge_max_parents
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建LangGraph状态机。"""
        workflow = StateGraph(RAGState)

        # 添加节点
        workflow.add_node("rewrite", self.rewrite_query)
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("merge", self.merge_chunks)
        workflow.add_node("rerank", self.rerank)
        workflow.add_node("evaluate", self.evaluate)
        workflow.add_node("transform", self.transform)
        workflow.add_node("generate", self.generate)

        workflow.set_entry_point("rewrite")

        workflow.add_edge("rewrite", "retrieve")
        workflow.add_edge("retrieve", "merge")
        workflow.add_edge("merge", "rerank")
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
        query = state.get("rewritten_query") or state["query"]
        documents = await self.retriever.ainvoke(query)
        logger.debug(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
        return {"documents": documents}

    async def merge_chunks(self, state: RAGState) -> dict[str, Any]:
        """层级合并：将细粒度 chunk 替换为其父级粗粒度 chunk。

        对于 chunk_level > merge_max_level 的文档，查找其 parent_chunk_id
        对应的父文档并替换，去重后返回合并结果。
        """
        documents = state["documents"]

        if not self.merge_enabled or not documents:
            return {"merged_documents": documents}

        es_client = getattr(self.retriever, "es_client", None)
        if es_client is None:
            logger.warning("merge_chunks: retriever has no es_client, skipping merge")
            return {"merged_documents": documents}

        merged: list[Document] = []
        parent_ids_seen: set[str] = set()
        parents_replaced = 0

        for doc in documents:
            chunk_level = doc.metadata.get("chunk_level")

            if chunk_level is not None and chunk_level > self.merge_max_level:
                parent_id = doc.metadata.get("parent_chunk_id")
                if parent_id is None:
                    merged.append(doc)
                    continue

                if parent_id in parent_ids_seen:
                    continue

                if parents_replaced >= self.merge_max_parents:
                    merged.append(doc)
                    continue

                try:
                    parent_data = await es_client.get_chunk_by_id(parent_id)
                    if parent_data is None:
                        merged.append(doc)
                        continue

                    parent_doc = Document(
                        page_content=parent_data.get("content", ""),
                        metadata={
                            "chunk_id": parent_data.get("chunk_id"),
                            "source_id": parent_data.get("source_id"),
                            "source_type": parent_data.get("source_type"),
                            "chunk_level": parent_data.get("chunk_level"),
                            "parent_chunk_id": parent_data.get("parent_chunk_id"),
                            "source": parent_data.get("source") or parent_data.get("source_id"),
                            "rrf_score": doc.metadata.get("rrf_score"),
                            "merged_from_child": doc.metadata.get("chunk_id"),
                        },
                    )
                    merged.append(parent_doc)
                    parents_replaced += 1
                    parent_ids_seen.add(parent_id)
                except Exception as e:
                    logger.warning(f"merge_chunks: failed to get parent {parent_id}: {e}")
                    merged.append(doc)
            else:
                merged.append(doc)

        logger.info(
            f"merge_chunks: {len(documents)} docs -> {len(merged)} docs "
            f"({parents_replaced} parents replaced)"
        )
        return {"merged_documents": merged}

    async def rerank(self, state: RAGState) -> dict[str, Any]:
        """对检索结果进行重排序。"""
        documents = state.get("merged_documents") or state["documents"]
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
        docs = state.get("reranked_documents") or state.get("merged_documents") or state["documents"]

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

    async def transform(self, state: RAGState) -> dict[str, Any]:
        """查询转换（当检索质量不佳时）。"""
        new_attempts = state["attempts"] + 1
        new_transformations = state["transformations"] + ["query_transform"]

        query = state.get("rewritten_query") or state["query"]
        retrieval_score = state["retrieval_score"]

        strategy = select_strategy(query, retrieval_score, new_attempts)
        logger.info(
            f"Query transform: attempt={new_attempts}, strategy={strategy.value}, "
            f"score={retrieval_score:.3f}, query='{query[:50]}...'"
        )

        if strategy == QueryTransformStrategy.NONE or self.llm_provider is None:
            return {"attempts": new_attempts, "transformations": new_transformations}

        try:
            transformer = QueryTransformer(self.llm_provider, prompt_gateway=self.prompt_gateway)

            if strategy == QueryTransformStrategy.STEP_BACK:
                transformed = await transformer.transform_step_back(query)
                new_transformations[-1] = f"step_back: {transformed[:80]}"
            elif strategy == QueryTransformStrategy.HYDE:
                transformed = await transformer.transform_hyde(query)
                new_transformations[-1] = f"hyde: {transformed[:80]}"
            elif strategy == QueryTransformStrategy.MULTI_QUERY:
                queries = await transformer.transform_multi_query(query)
                transformed = queries[0] if queries else query
                new_transformations[-1] = f"multi_query: {', '.join(queries)[:80]}"
            else:
                transformed = query

            logger.info(f"Query transformed: '{query[:50]}' -> '{transformed[:50]}'")
            return {
                "attempts": new_attempts,
                "transformations": new_transformations,
                "rewritten_query": transformed,
            }
        except Exception as e:
            logger.warning(f"Query transform failed: {e}, keeping original query")
            return {"attempts": new_attempts, "transformations": new_transformations}

    async def generate(self, state: RAGState) -> dict[str, Any]:
        """生成答案。"""
        docs = state.get("reranked_documents") or state.get("merged_documents") or state["documents"]
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
            "merged_documents": [],
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
