from unittest.mock import AsyncMock, MagicMock

import pytest
from app.infra.langchain.agents import RAGAgent, RAGState
from langchain_core.documents import Document


def test_rag_state_typeddict_has_required_fields():
    state = RAGState(
        query="test query",
        rewritten_query="",
        documents=[],
        reranked_documents=[],
        retrieval_score=0.0,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )
    assert state["query"] == "test query"
    assert state["rewritten_query"] == ""
    assert state["documents"] == []
    assert state["reranked_documents"] == []
    assert state["retrieval_score"] == 0.0
    assert state["attempts"] == 0
    assert state["transformations"] == []
    assert state["answer"] == ""
    assert state["conversation_history"] == []


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
        reranked_documents=[],
        retrieval_score=0.5,
        attempts=0,
        transformations=[],
        answer="",
        conversation_history=[],
    )

    result = agent.transform(state)

    assert result["attempts"] == 1
    assert len(result["transformations"]) == 1


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
