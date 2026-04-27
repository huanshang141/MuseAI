from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.document_filter import FilterConfig
from app.infra.langchain.agents import RAGAgent, RAGState
from langchain_core.documents import Document


def test_rag_state_typeddict_has_required_fields():
    state = RAGState(
        query="test query",
        rewritten_query="",
        documents=[],
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )
    assert state["query"] == "test query"
    assert state["merged_documents"] == []


def test_rag_agent_initialization():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)

    assert agent.llm == mock_llm
    assert agent.retriever == mock_retriever
    assert agent.score_threshold == 0.7
    assert agent.max_attempts == 3


def test_rag_agent_custom_threshold_and_max_attempts():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        score_threshold=0.8,
        max_attempts=5,
    )

    assert agent.score_threshold == 0.8
    assert agent.max_attempts == 5


@pytest.mark.asyncio
async def test_rag_agent_retrieve_node():
    mock_llm = MagicMock()
    mock_retriever = AsyncMock()
    mock_retriever.ainvoke = AsyncMock(
        return_value=[
            Document(page_content="doc1", metadata={"chunk_id": "1"}),
            Document(page_content="doc2", metadata={"chunk_id": "2"}),
        ]
    )

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)
    state = RAGState(
        query="test query",
        rewritten_query="test query",
        documents=[],
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.retrieve(state)

    assert len(result["documents"]) == 2
    assert result["documents"][0].page_content == "doc1"


@pytest.mark.asyncio
async def test_rag_agent_evaluate_node_high_score():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)

    docs = [
        Document(page_content="relevant content", metadata={"rrf_score": 0.85}),
        Document(page_content="more content", metadata={"rrf_score": 0.75}),
    ]
    state = RAGState(
        query="test query",
        rewritten_query="test query",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = agent.evaluate(state)

    assert result["retrieval_score"] >= 0.7


@pytest.mark.asyncio
async def test_rag_agent_transform_node():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)
    state = RAGState(
        query="test query",
        rewritten_query="test query",
        documents=[],
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.5,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.transform(state)

    assert result["attempts"] == 1
    assert len(result["transformations"]) == 1


@pytest.mark.asyncio
async def test_rag_agent_transform_with_llm_provider():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate = AsyncMock(
        return_value=MagicMock(content="1. 博物馆中的公共烹饪设施有哪些\n2. 古代大型灶具的用途\n3. 连通灶的历史背景")
    )

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever, llm_provider=mock_llm_provider)
    state = RAGState(
        query="介绍一下连通灶",
        rewritten_query="介绍一下连通灶",
        documents=[],
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.3,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.transform(state)

    assert result["attempts"] == 1
    assert len(result["transformations"]) == 1
    assert "rewritten_query" in result
    assert result["rewritten_query"] != "介绍一下连通灶"


@pytest.mark.asyncio
async def test_rag_agent_transform_without_llm_provider():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)
    state = RAGState(
        query="test query",
        rewritten_query="test query",
        documents=[],
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.3,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.transform(state)

    assert result["attempts"] == 1
    assert "rewritten_query" not in result


@pytest.mark.asyncio
async def test_rag_agent_transform_failure_fallback():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate = AsyncMock(side_effect=Exception("LLM unavailable"))

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever, llm_provider=mock_llm_provider)
    state = RAGState(
        query="test query",
        rewritten_query="test query",
        documents=[],
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.3,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.transform(state)

    assert result["attempts"] == 1
    assert "rewritten_query" not in result


@pytest.mark.asyncio
async def test_rag_agent_generate_node():
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Generated answer"))
    mock_retriever = MagicMock()

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)

    docs = [Document(page_content="context", metadata={})]
    state = RAGState(
        query="test query",
        rewritten_query="test query",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.8,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.generate(state)

    assert result["answer"] == "Generated answer"


@pytest.mark.asyncio
async def test_rag_agent_run_full_flow():
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Final answer"))

    mock_retriever = AsyncMock()
    mock_retriever.ainvoke = AsyncMock(
        return_value=[
            Document(page_content="relevant doc", metadata={"rrf_score": 0.9}),
        ]
    )

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever)
    result = await agent.run("What is machine learning?")

    assert result["answer"] == "Final answer"
    assert result["retrieval_score"] >= 0.7
    assert result["attempts"] == 0


@pytest.mark.asyncio
async def test_rag_agent_run_with_low_score_retries():
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Answer after retries"))

    mock_retriever = AsyncMock()
    mock_retriever.ainvoke = AsyncMock(
        return_value=[
            Document(page_content="doc", metadata={"rrf_score": 0.3}),
        ]
    )

    agent = RAGAgent(llm=mock_llm, retriever=mock_retriever, max_attempts=2)
    result = await agent.run("unclear query")

    assert result["answer"] == "Answer after retries"
    assert result["attempts"] == 2


@pytest.mark.asyncio
async def test_rag_agent_rewrite_with_history():
    """测试多轮对话查询重写。"""
    from app.application.workflows.query_transform import ConversationAwareQueryRewriter

    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate = AsyncMock(
        return_value=MagicMock(content="这件青铜器是什么时候制作的？")
    )

    query_rewriter = ConversationAwareQueryRewriter(mock_llm_provider)

    mock_llm = MagicMock()
    mock_retriever = AsyncMock()
    mock_retriever.ainvoke = AsyncMock(
        return_value=[
            Document(page_content="doc", metadata={"rrf_score": 0.8}),
        ]
    )
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Answer"))

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        query_rewriter=query_rewriter,
    )

    history = [
        {"role": "user", "content": "请介绍一下这件青铜器"},
        {"role": "assistant", "content": "这是一件商代青铜器"},
    ]

    result = await agent.run("那它是什么时候制作的？", conversation_history=history)

    assert result["answer"] == "Answer"


@pytest.mark.asyncio
async def test_merge_chunks_replaces_child_with_parent():
    mock_llm = MagicMock()
    mock_es = AsyncMock()
    mock_es.get_chunk_by_id = AsyncMock(return_value={
        "chunk_id": "parent-1",
        "source_id": "doc-a",
        "source_type": "document",
        "content": "Parent chunk content",
        "chunk_level": 1,
        "parent_chunk_id": None,
    })

    mock_retriever = MagicMock()
    mock_retriever.es_client = mock_es

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_max_level=1,
        merge_max_parents=3,
    )

    docs = [
        Document(
            page_content="Child content 1",
            metadata={"chunk_id": "child-1", "chunk_level": 2, "parent_chunk_id": "parent-1", "rrf_score": 0.8},
        ),
        Document(
            page_content="Child content 2",
            metadata={"chunk_id": "child-2", "chunk_level": 2, "parent_chunk_id": "parent-1", "rrf_score": 0.7},
        ),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)

    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "Parent chunk content"
    assert result["merged_documents"][0].metadata["chunk_level"] == 1
    assert result["merged_documents"][0].metadata["merged_from_child"] == "child-1"


@pytest.mark.asyncio
async def test_merge_chunks_disabled():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=False,
    )

    docs = [
        Document(page_content="child", metadata={"chunk_id": "c1", "chunk_level": 2, "parent_chunk_id": "p1"}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "child"


@pytest.mark.asyncio
async def test_merge_chunks_keeps_level_1_docs():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_max_level=1,
    )

    docs = [
        Document(page_content="level 1 doc", metadata={"chunk_id": "c1", "chunk_level": 1}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "level 1 doc"


@pytest.mark.asyncio
async def test_merge_chunks_respects_max_parents():
    mock_llm = MagicMock()
    mock_es = AsyncMock()

    async def mock_get_chunk(chunk_id):
        return {
            "chunk_id": chunk_id,
            "source_id": "doc-a",
            "content": f"Parent {chunk_id}",
            "chunk_level": 1,
        }

    mock_es.get_chunk_by_id = mock_get_chunk

    mock_retriever = MagicMock()
    mock_retriever.es_client = mock_es

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_max_level=1,
        merge_max_parents=1,
    )

    docs = [
        Document(page_content="c1", metadata={"chunk_id": "c1", "chunk_level": 2, "parent_chunk_id": "p1"}),
        Document(page_content="c2", metadata={"chunk_id": "c2", "chunk_level": 2, "parent_chunk_id": "p2"}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 2
    merged_levels = [d.metadata.get("chunk_level") for d in result["merged_documents"]]
    assert 1 in merged_levels
    assert 2 in merged_levels


@pytest.mark.asyncio
async def test_merge_chunks_no_es_client():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    del mock_retriever.es_client

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
    )

    docs = [
        Document(page_content="child", metadata={"chunk_id": "c1", "chunk_level": 2, "parent_chunk_id": "p1"}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "child"


@pytest.mark.asyncio
async def test_merge_chunks_parent_not_found():
    mock_llm = MagicMock()
    mock_es = AsyncMock()
    mock_es.get_chunk_by_id = AsyncMock(return_value=None)

    mock_retriever = MagicMock()
    mock_retriever.es_client = mock_es

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_max_level=1,
    )

    docs = [
        Document(page_content="child", metadata={"chunk_id": "c1", "chunk_level": 2, "parent_chunk_id": "p1"}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "child"


@pytest.mark.asyncio
async def test_merge_chunks_es_error_fallback():
    mock_llm = MagicMock()
    mock_es = AsyncMock()
    mock_es.get_chunk_by_id = AsyncMock(side_effect=Exception("ES down"))

    mock_retriever = MagicMock()
    mock_retriever.es_client = mock_es

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_max_level=1,
    )

    docs = [
        Document(page_content="child", metadata={"chunk_id": "c1", "chunk_level": 2, "parent_chunk_id": "p1"}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "child"


@pytest.mark.asyncio
async def test_merge_chunks_no_parent_chunk_id():
    mock_llm = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.es_client = AsyncMock()

    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        merge_enabled=True,
        merge_max_level=1,
    )

    docs = [
        Document(page_content="orphan", metadata={"chunk_id": "c1", "chunk_level": 2}),
    ]

    state = RAGState(
        query="test",
        rewritten_query="test",
        documents=docs,
        merged_documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = await agent.merge_chunks(state)
    assert len(result["merged_documents"]) == 1
    assert result["merged_documents"][0].page_content == "orphan"


class TestRAGAgentFilterNode:
    @pytest.fixture
    def mock_rag_agent(self):
        mock_llm = MagicMock()
        mock_retriever = MagicMock()
        agent = RAGAgent(
            llm=mock_llm,
            retriever=mock_retriever,
            rerank_provider=None,
            filter_config=FilterConfig(
                absolute_threshold=0.25,
                relative_gap=0.25,
                min_docs=1,
                max_docs=8,
            ),
        )
        return agent

    def test_filter_node_with_specific_exhibit(self, mock_rag_agent):
        """模拟连通灶场景"""
        state: RAGState = {
            "query": "介绍一下连通灶",
            "rewritten_query": "介绍一下连通灶",
            "documents": [],
            "merged_documents": [],
            "reranked_documents": [
                Document(page_content="连通灶是大型公共灶...", metadata={"rerank_score": 0.41}),
                Document(page_content="青铜馆A厅介绍...", metadata={"rerank_score": 0.001}),
                Document(page_content="半坡人生活方式...", metadata={"rerank_score": 0.00006}),
            ],
            "filtered_documents": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": [],
            "system_prompt": "",
        }
        result = mock_rag_agent.filter_documents(state)
        filtered = result["filtered_documents"]
        assert len(filtered) == 1
        assert filtered[0].metadata["rerank_score"] == pytest.approx(0.41)

    def test_filter_node_with_broad_topic(self, mock_rag_agent):
        """模拟半坡陶器场景"""
        state: RAGState = {
            "query": "介绍一下半坡的陶器",
            "rewritten_query": "介绍一下半坡的陶器",
            "documents": [],
            "merged_documents": [],
            "reranked_documents": [
                Document(page_content="陶器的造型与纹饰...", metadata={"rerank_score": 0.97}),
                Document(page_content="雕塑艺术...", metadata={"rerank_score": 0.97}),
                Document(page_content="彩陶图案集萃...", metadata={"rerank_score": 0.88}),
            ],
            "filtered_documents": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": [],
            "system_prompt": "",
        }
        result = mock_rag_agent.filter_documents(state)
        filtered = result["filtered_documents"]
        assert len(filtered) == 3

    def test_evaluate_uses_filtered_documents(self, mock_rag_agent):
        """评估节点应优先使用 filtered_documents"""
        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "documents": [],
            "merged_documents": [],
            "reranked_documents": [
                Document(page_content="a", metadata={"rerank_score": 0.9}),
                Document(page_content="b", metadata={"rerank_score": 0.1}),
            ],
            "filtered_documents": [
                Document(page_content="a", metadata={"rerank_score": 0.9}),
            ],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "answer": "",
            "conversation_history": [],
            "system_prompt": "",
        }
        result = mock_rag_agent.evaluate(state)
        assert result["retrieval_score"] == pytest.approx(0.945)
