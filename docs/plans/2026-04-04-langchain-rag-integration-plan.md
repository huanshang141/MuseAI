# LangChain RAG Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 集成 LangChain 生态，修复 Ingestion Pipeline，实现 RAG Agent

**Architecture:** 使用 LangChain 1.x + LangGraph 构建 RAG Agent，保留自定义多层级分块和 ES 索引，通过包装器适配 LangChain 接口

**Tech Stack:** LangChain 1.2.x, LangGraph 1.1.x, langchain-elasticsearch 0.2.x, langchain-openai 1.1.x

---

## Task 1: Add LangChain Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependencies to pyproject.toml**

在 `[project.dependencies]` 数组中添加：

```toml
"langchain>=1.2.14,<2.0.0",
"langchain-core>=1.2.22,<2.0.0",
"langchain-community>=0.3.0,<0.4.0",
"langchain-openai>=1.1.12,<2.0.0",
"langchain-elasticsearch>=0.2.0,<0.3.0",
"langgraph>=1.1.3,<2.0.0",
```

**Step 2: Sync dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add langchain ecosystem dependencies"
```

---

## Task 2: Create CustomOllamaEmbeddings

**Files:**
- Create: `backend/app/infra/langchain/__init__.py`
- Create: `backend/app/infra/langchain/embeddings.py`
- Create: `backend/tests/unit/test_custom_embeddings.py`

**Step 1: Create package init file**

Create `backend/app/infra/langchain/__init__.py`:

```python
from app.infra.langchain.embeddings import CustomOllamaEmbeddings

__all__ = ["CustomOllamaEmbeddings"]
```

**Step 2: Write failing test for embeddings**

Create `backend/tests/unit/test_custom_embeddings.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.infra.langchain.embeddings import CustomOllamaEmbeddings


@pytest.mark.asyncio
async def test_embeddings_embed_query():
    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="test-model",
        dims=768,
    )
    
    with patch.object(embeddings, "_get_provider") as mock_provider:
        provider = AsyncMock()
        provider.embed = AsyncMock(return_value=[0.1] * 768)
        mock_provider.return_value = provider
        
        result = await embeddings.aembed_query("test query")
        
        assert len(result) == 768
        assert all(v == 0.1 for v in result)


@pytest.mark.asyncio
async def test_embeddings_embed_documents():
    embeddings = CustomOllamaEmbeddings(
        base_url="http://localhost:11434",
        model="test-model",
        dims=768,
    )
    
    with patch.object(embeddings, "_get_provider") as mock_provider:
        provider = AsyncMock()
        provider.embed_batch = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
        mock_provider.return_value = provider
        
        result = await embeddings.aembed_documents(["text1", "text2"])
        
        assert len(result) == 2
        assert len(result[0]) == 768
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_custom_embeddings.py -v`
Expected: FAIL with "module not found" or "class not defined"

**Step 4: Implement CustomOllamaEmbeddings**

Create `backend/app/infra/langchain/embeddings.py`:

```python
from typing import List
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, PrivateAttr

from app.infra.providers.embedding import OllamaEmbeddingProvider


class CustomOllamaEmbeddings(BaseModel, Embeddings):
    """包装 OllamaEmbeddingProvider 到 LangChain Embeddings 接口"""
    
    base_url: str
    model: str
    dims: int
    timeout: float = 60.0
    
    _provider: OllamaEmbeddingProvider | None = PrivateAttr(default=None)
    
    def _get_provider(self) -> OllamaEmbeddingProvider:
        if self._provider is None:
            self._provider = OllamaEmbeddingProvider(
                base_url=self.base_url,
                model=self.model,
                dims=self.dims,
                timeout=self.timeout,
            )
        return self._provider
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        return asyncio.run(self.aembed_documents(texts))
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        provider = self._get_provider()
        return await provider.embed_batch(texts)
    
    def embed_query(self, text: str) -> List[float]:
        import asyncio
        return asyncio.run(self.aembed_query(text))
    
    async def aembed_query(self, text: str) -> List[float]:
        provider = self._get_provider()
        return await provider.embed(text)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_custom_embeddings.py -v`
Expected: 2 passed

**Step 6: Commit**

```bash
git add backend/app/infra/langchain/ backend/tests/unit/test_custom_embeddings.py
git commit -m "feat: add CustomOllamaEmbeddings wrapper for LangChain"
```

---

## Task 3: Create RRFRetriever

**Files:**
- Create: `backend/app/infra/langchain/retrievers.py`
- Create: `backend/tests/unit/test_rrf_retriever.py`

**Step 1: Write failing test for retriever**

Create `backend/tests/unit/test_rrf_retriever.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.infra.langchain.retrievers import RRFRetriever
from langchain_core.documents import Document


@pytest.mark.asyncio
async def test_retriever_returns_documents():
    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(return_value=[
        {"chunk_id": "1", "content": "dense result", "document_id": "doc1", "chunk_level": 1}
    ])
    mock_es.search_bm25 = AsyncMock(return_value=[
        {"chunk_id": "2", "content": "bm25 result", "document_id": "doc2", "chunk_level": 1}
    ])
    
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)
    
    retriever = RRFRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
    )
    
    docs = await retriever._aget_relevant_documents("test query")
    
    assert len(docs) > 0
    assert isinstance(docs[0], Document)
    assert "chunk_id" in docs[0].metadata
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_rrf_retriever.py -v`
Expected: FAIL with "module not found"

**Step 3: Implement RRFRetriever**

Create `backend/app/infra/langchain/retrievers.py`:

```python
from typing import List
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from pydantic import BaseModel

from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings
from app.application.retrieval import rrf_fusion


class RRFRetriever(BaseModel, BaseRetriever):
    """RRF 融合检索器"""
    
    es_client: ElasticsearchClient
    embeddings: CustomOllamaEmbeddings
    top_k: int = 5
    rrf_k: int = 60
    
    class Config:
        arbitrary_types_allowed = True
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        import asyncio
        return asyncio.run(self._aget_relevant_documents(query))
    
    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        query_vector = await self.embeddings.aembed_query(query)
        
        dense_results = await self.es_client.search_dense(query_vector, self.top_k * 2)
        bm25_results = await self.es_client.search_bm25(query, self.top_k * 2)
        
        fused = rrf_fusion(dense_results, bm25_results, k=self.rrf_k)
        
        documents = []
        for item in fused[:self.top_k]:
            doc = Document(
                page_content=item.get("content", ""),
                metadata={
                    "chunk_id": item.get("chunk_id"),
                    "document_id": item.get("document_id"),
                    "chunk_level": item.get("chunk_level"),
                    "source": item.get("source"),
                    "rrf_score": item.get("rrf_score"),
                }
            )
            documents.append(doc)
        
        return documents
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_rrf_retriever.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add backend/app/infra/langchain/retrievers.py backend/tests/unit/test_rrf_retriever.py
git commit -m "feat: add RRFRetriever with LangChain BaseRetriever interface"
```

---

## Task 4: Create IngestionService

**Files:**
- Create: `backend/app/application/ingestion_service.py`
- Create: `backend/tests/unit/test_ingestion_service.py`

**Step 1: Write failing test for ingestion service**

Create `backend/tests/unit/test_ingestion_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.ingestion_service import IngestionService
from app.application.chunking import ChunkConfig


@pytest.mark.asyncio
async def test_ingestion_service_chunks_and_indexes():
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})
    
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])
    
    service = IngestionService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)],
    )
    
    count = await service.ingest(
        document_id="test-doc",
        content="This is a test document content for chunking and indexing.",
        source="test.txt",
    )
    
    assert count > 0
    assert mock_es.index_chunk.call_count == count
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_ingestion_service.py -v`
Expected: FAIL with "module not found"

**Step 3: Implement IngestionService**

Create `backend/app/application/ingestion_service.py`:

```python
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.postgres.models import IngestionJob
from app.application.chunking import TextChunker, ChunkConfig
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings

logger = logging.getLogger(__name__)


class IngestionService:
    """文档摄取服务"""
    
    def __init__(
        self,
        es_client: ElasticsearchClient,
        embeddings: CustomOllamaEmbeddings,
        chunk_configs: list[ChunkConfig] | None = None,
    ):
        self.es_client = es_client
        self.embeddings = embeddings
        self.chunk_configs = chunk_configs or [
            ChunkConfig(level=1, window_size=2000, overlap=200),
            ChunkConfig(level=2, window_size=500, overlap=50),
            ChunkConfig(level=3, window_size=100, overlap=10),
        ]
    
    async def ingest(
        self,
        document_id: str,
        content: str,
        source: str | None = None,
    ) -> int:
        total_chunks = 0
        
        for config in self.chunk_configs:
            chunker = TextChunker(config)
            chunks = chunker.chunk(
                text=content,
                document_id=document_id,
                source=source,
            )
            
            if not chunks:
                continue
            
            chunk_texts = [c.content for c in chunks]
            embeddings_list = await self.embeddings.aembed_documents(chunk_texts)
            
            for chunk, embedding in zip(chunks, embeddings_list):
                doc = {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_level": chunk.level,
                    "content": chunk.content,
                    "content_vector": embedding,
                    "source": chunk.source,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                }
                await self.es_client.index_chunk(doc)
                total_chunks += 1
        
        return total_chunks
    
    async def process_document(
        self,
        session: AsyncSession,
        document_id: str,
        content: str,
        source: str | None = None,
    ) -> IngestionJob:
        job = await self._get_job(session, document_id)
        job.status = "processing"
        await session.flush()
        
        try:
            chunk_count = await self.ingest(document_id, content, source)
            job.status = "completed"
            job.chunk_count = chunk_count
            await session.flush()
            
            logger.info(f"Document {document_id} ingested: {chunk_count} chunks")
            return job
            
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            await session.flush()
            logger.error(f"Document {document_id} ingestion failed: {e}")
            raise
    
    async def _get_job(self, session: AsyncSession, document_id: str) -> IngestionJob:
        stmt = select(IngestionJob).where(IngestionJob.document_id == document_id)
        result = await session.execute(stmt)
        return result.scalar_one()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_ingestion_service.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add backend/app/application/ingestion_service.py backend/tests/unit/test_ingestion_service.py
git commit -m "feat: add IngestionService for document processing pipeline"
```

---

## Task 5: Create RAG Agent

**Files:**
- Create: `backend/app/infra/langchain/agents.py`
- Create: `backend/tests/unit/test_rag_agent.py`

**Step 1: Write failing test for RAG agent**

Create `backend/tests/unit/test_rag_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.infra.langchain.agents import RAGAgent, RAGState
from langchain_openai import ChatOpenAI


@pytest.mark.asyncio
async def test_rag_agent_retrieves_and_generates():
    mock_llm = MagicMock(spec=ChatOpenAI)
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test answer"))
    
    mock_retriever = AsyncMock()
    mock_retriever._aget_relevant_documents = AsyncMock(return_value=[])
    
    mock_settings = MagicMock()
    
    agent = RAGAgent(
        llm=mock_llm,
        retriever=mock_retriever,
        settings=mock_settings,
    )
    
    result = await agent.run("test question")
    
    assert "messages" in result
    assert len(result["messages"]) > 0
    assert "trace_id" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_rag_agent.py -v`
Expected: FAIL with "module not found"

**Step 3: Implement RAG Agent**

Create `backend/app/infra/langchain/agents.py`:

```python
import uuid
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from app.infra.langchain.retrievers import RRFRetriever
from app.config.settings import Settings


class RAGState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    question: str
    context: list[str]
    retrieval_score: float
    attempts: int
    transformations: list[str]
    trace_id: str


class RAGAgent:
    SCORE_THRESHOLD = 0.7
    MAX_ATTEMPTS = 3
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retriever: RRFRetriever,
        settings: Settings,
    ):
        self.llm = llm
        self.retriever = retriever
        self.settings = settings
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(RAGState)
        
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("evaluate", self._evaluate_node)
        workflow.add_node("transform", self._transform_node)
        workflow.add_node("generate", self._generate_node)
        
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "evaluate")
        workflow.add_conditional_edges(
            "evaluate",
            self._should_transform,
            {
                "transform": "transform",
                "generate": "generate",
            }
        )
        workflow.add_edge("transform", "retrieve")
        workflow.add_edge("generate", END)
        
        return workflow.compile()
    
    async def _retrieve_node(self, state: RAGState) -> dict:
        question = state["question"]
        documents = await self.retriever._aget_relevant_documents(question)
        
        context = [doc.page_content for doc in documents]
        avg_score = sum(doc.metadata.get("rrf_score", 0) for doc in documents) / len(documents) if documents else 0.0
        
        return {
            "context": context,
            "retrieval_score": avg_score,
        }
    
    async def _evaluate_node(self, state: RAGState) -> dict:
        return {"attempts": state["attempts"] + 1}
    
    async def _transform_node(self, state: RAGState) -> dict:
        return {
            "transformations": state["transformations"] + ["query_rewrite"],
            "question": f"请详细说明：{state['question']}",
        }
    
    async def _generate_node(self, state: RAGState) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个智能助手。基于以下上下文回答问题：\n\n{context}"),
            ("human", "{question}"),
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({
            "context": "\n\n".join(state["context"]) if state["context"] else "无相关上下文",
            "question": state["question"],
        })
        
        return {
            "messages": [AIMessage(content=response.content)],
            "trace_id": str(uuid.uuid4()),
        }
    
    def _should_transform(self, state: RAGState) -> str:
        if state["retrieval_score"] >= self.SCORE_THRESHOLD:
            return "generate"
        if state["attempts"] >= self.MAX_ATTEMPTS:
            return "generate"
        return "transform"
    
    async def run(self, question: str) -> dict:
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "question": question,
            "context": [],
            "retrieval_score": 0.0,
            "attempts": 0,
            "transformations": [],
            "trace_id": "",
        }
        
        return await self.graph.ainvoke(initial_state)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_rag_agent.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add backend/app/infra/langchain/agents.py backend/tests/unit/test_rag_agent.py
git commit -m "feat: add RAGAgent with LangGraph state machine"
```

---

## Task 6: Update Factory Functions

**Files:**
- Modify: `backend/app/infra/langchain/__init__.py`

**Step 1: Add factory functions**

Modify `backend/app/infra/langchain/__init__.py`:

```python
from app.config.settings import Settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings
from app.infra.langchain.retrievers import RRFRetriever
from app.infra.langchain.agents import RAGAgent
from langchain_openai import ChatOpenAI

__all__ = [
    "CustomOllamaEmbeddings",
    "RRFRetriever",
    "RAGAgent",
    "create_embeddings",
    "create_llm",
    "create_retriever",
    "create_rag_agent",
]


def create_embeddings(settings: Settings) -> CustomOllamaEmbeddings:
    return CustomOllamaEmbeddings(
        base_url=settings.EMBEDDING_OLLAMA_BASE_URL,
        model=settings.EMBEDDING_OLLAMA_MODEL,
        dims=settings.EMBEDDING_DIMS,
    )


def create_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.7,
    )


def create_retriever(
    es_client: ElasticsearchClient,
    embeddings: CustomOllamaEmbeddings,
    top_k: int = 5,
) -> RRFRetriever:
    return RRFRetriever(
        es_client=es_client,
        embeddings=embeddings,
        top_k=top_k,
    )


def create_rag_agent(
    llm: ChatOpenAI,
    retriever: RRFRetriever,
    settings: Settings,
) -> RAGAgent:
    return RAGAgent(
        llm=llm,
        retriever=retriever,
        settings=settings,
    )
```

**Step 2: Run tests to verify nothing breaks**

Run: `uv run pytest backend/tests/unit/ -v`
Expected: All unit tests pass

**Step 3: Commit**

```bash
git add backend/app/infra/langchain/__init__.py
git commit -m "feat: add factory functions for LangChain components"
```

---

## Task 7: Integrate with Documents API

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/main.py`

**Step 1: Add dependencies to main.py**

Modify `backend/app/main.py`, add global instances and dependency injection:

```python
from app.infra.langchain import (
    create_embeddings,
    create_llm,
    create_retriever,
    create_rag_agent,
)

# Add global instances at module level
es_client: ElasticsearchClient | None = None
embeddings = None
llm = None
retriever = None
rag_agent = None

# In lifespan function, after ES client initialization:
embeddings = create_embeddings(settings)
llm = create_llm(settings)
retriever = create_retriever(es_client, embeddings)
rag_agent = create_rag_agent(llm, retriever, settings)

# Add dependency functions at end of file:
def get_es_client() -> ElasticsearchClient:
    if es_client is None:
        raise RuntimeError("ES client not initialized")
    return es_client


def get_embeddings() -> CustomOllamaEmbeddings:
    if embeddings is None:
        raise RuntimeError("Embeddings not initialized")
    return embeddings


def get_rag_agent() -> RAGAgent:
    if rag_agent is None:
        raise RuntimeError("RAG agent not initialized")
    return rag_agent
```

**Step 2: Modify documents upload endpoint**

Modify `backend/app/api/documents.py`:

```python
from app.application.ingestion_service import IngestionService

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    file: UploadFile = File(...),
    es_client: ElasticsearchClient = Depends(get_es_client),
    embeddings: CustomOllamaEmbeddings = Depends(get_embeddings),
) -> DocumentResponse:
    # ... existing validation ...
    
    document = await create_document(session, file.filename, file_size)
    
    # Trigger ingestion
    ingestion = IngestionService(es_client, embeddings)
    try:
        text_content = content.decode("utf-8")
        await ingestion.process_document(
            session,
            document.id,
            text_content,
            source=file.filename
        )
    except UnicodeDecodeError:
        pass
    
    return DocumentResponse(...)
```

**Step 3: Run contract tests**

Run: `uv run pytest backend/tests/contract/test_documents_api.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/app/api/documents.py backend/app/main.py
git commit -m "feat: integrate IngestionService into documents upload API"
```

---

## Task 8: Integrate RAG Agent with Chat API

**Files:**
- Modify: `backend/app/application/chat_service.py`
- Modify: `backend/app/api/chat.py`

**Step 1: Refactor chat_service.py**

Modify `backend/app/application/chat_service.py`:

```python
from app.infra.langchain.agents import RAGAgent

# Keep existing CRUD functions unchanged

async def ask_question_stream(
    session: AsyncSession,
    session_id: str,
    message: str,
    agent: RAGAgent,
) -> AsyncGenerator[str, None]:
    chat_session = await get_session_by_id(session, session_id)
    if chat_session is None:
        yield f"data: {json.dumps({'type': 'error', 'code': 'SESSION_NOT_FOUND', 'message': 'Session not found'})}\n\n"
        return
    
    yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"
    
    try:
        result = await agent.run(message)
        
        ai_message = result["messages"][-1]
        answer = ai_message.content
        trace_id = result["trace_id"]
        
        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'generate', 'content': '生成回答...'})}\n\n"
        yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': answer})}\n\n"
        
        await add_message(session, session_id, "user", message)
        await add_message(session, session_id, "assistant", answer, trace_id=trace_id)
        await session.commit()
        
        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'chunks': [answer]})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': str(e)})}\n\n"
```

**Step 2: Update chat API endpoint**

Modify `backend/app/api/chat.py`:

```python
from app.infra.langchain.agents import RAGAgent
from app.main import get_rag_agent

@router.post("/ask/stream")
async def ask_question_stream(
    session: SessionDep,
    request: AskRequest,
    agent: RAGAgent = Depends(get_rag_agent),
) -> StreamingResponse:
    return StreamingResponse(
        chat_service.ask_question_stream(session, request.session_id, request.message, agent),
        media_type="text/event-stream",
    )
```

**Step 3: Run contract tests**

Run: `uv run pytest backend/tests/contract/test_chat_api.py backend/tests/contract/test_sse_events.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/app/application/chat_service.py backend/app/api/chat.py
git commit -m "feat: integrate RAG Agent into chat streaming API"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run all unit tests**

Run: `uv run pytest backend/tests/unit/ -v`
Expected: All unit tests pass

**Step 2: Run all contract tests**

Run: `uv run pytest backend/tests/contract/ -v`
Expected: All contract tests pass

**Step 3: Run e2e tests (if environment available)**

Run: `uv run pytest backend/tests/e2e/ -v`
Expected: Tests pass or skip gracefully if services not available

---

## Task 10: Final Verification

**Step 1: Start backend server**

Run: `uv run uvicorn backend.app.main:app --reload --port 8000`
Expected: Server starts without errors

**Step 2: Test document upload**

Upload a text document via frontend or curl, verify:
- `chunk_count > 0`
- Document status is `completed`

**Step 3: Test RAG chat**

Send a question related to uploaded document, verify:
- RAG retrieves relevant chunks
- Answer contains information from document

**Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete LangChain RAG integration"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add dependencies | pyproject.toml |
| 2 | CustomOllamaEmbeddings | infra/langchain/embeddings.py |
| 3 | RRFRetriever | infra/langchain/retrievers.py |
| 4 | IngestionService | application/ingestion_service.py |
| 5 | RAG Agent | infra/langchain/agents.py |
| 6 | Factory functions | infra/langchain/__init__.py |
| 7 | Documents API integration | api/documents.py, main.py |
| 8 | Chat API integration | api/chat.py, chat_service.py |
| 9 | Test suite | All tests |
| 10 | Final verification | Manual testing |
