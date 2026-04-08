# Unified Content Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify document and exhibit indexing into a single pipeline, enabling RAG to retrieve both content types through one RRF fusion retriever.

**Architecture:** Introduce a `ContentSource` abstraction that both documents and exhibits implement. Create `UnifiedIndexingService` to handle chunking and embedding for all content types. Replace `RRFRetriever` and `ExhibitAwareRetriever` with a single `UnifiedRetriever` that searches all content types using RRF fusion.

**Tech Stack:** FastAPI, SQLAlchemy, Elasticsearch, LangChain, Pydantic

---

## Affected Files Analysis

### Core Files to Modify
- `backend/app/application/ingestion_service.py` - Refactor to use unified model
- `backend/app/application/exhibit_indexing_service.py` - Deprecate, migrate to unified service
- `backend/app/infra/langchain/retrievers.py` - Add UnifiedRetriever, deprecate old retrievers
- `backend/app/infra/langchain/__init__.py` - Update factory functions
- `backend/app/infra/elasticsearch/client.py` - Update ES schema and search methods
- `backend/app/api/admin.py` - Use UnifiedIndexingService for exhibits
- `backend/app/api/documents.py` - Use UnifiedIndexingService for documents
- `backend/app/main.py` - Update initialization

### Test Files to Update
- `backend/tests/unit/test_ingestion_service.py`
- `backend/tests/unit/test_rrf_retriever.py`
- `backend/tests/contract/test_admin_api.py`
- `backend/tests/unit/test_repositories.py`
- `backend/tests/unit/test_parallel_indexing.py`
- `backend/tests/unit/test_rag_agent.py`

### Scripts to Update
- `scripts/init_exhibits.py`

---

## Task 1: Define Unified Content Model

**Files:**
- Create: `backend/app/application/content_source.py`

- [ ] **Step 1: Write the test for ContentSource dataclass**

```python
# backend/tests/unit/test_content_source.py
import pytest
from app.application.content_source import ContentSource, ContentMetadata

def test_content_source_creation():
    """Test creating a ContentSource instance."""
    metadata = ContentMetadata(
        name="Test Exhibit",
        category="Ceramics",
        hall="Hall A",
        floor=1,
    )
    source = ContentSource(
        source_id="test-123",
        source_type="exhibit",
        content="This is test content for the exhibit.",
        metadata=metadata,
    )
    assert source.source_id == "test-123"
    assert source.source_type == "exhibit"
    assert source.metadata.name == "Test Exhibit"

def test_content_metadata_optional_fields():
    """Test ContentMetadata with optional fields."""
    metadata = ContentMetadata()
    assert metadata.name is None
    assert metadata.category is None
    assert metadata.filename is None

def test_content_source_for_document():
    """Test creating ContentSource for a document."""
    metadata = ContentMetadata(filename="test.pdf")
    source = ContentSource(
        source_id="doc-456",
        source_type="document",
        content="Document content here.",
        metadata=metadata,
    )
    assert source.source_type == "document"
    assert source.metadata.filename == "test.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_content_source.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.application.content_source'"

- [ ] **Step 3: Implement ContentSource dataclass**

```python
# backend/app/application/content_source.py
"""Unified content source model for indexing."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentMetadata:
    """Metadata for content sources."""

    # Common fields
    name: str | None = None

    # Document-specific
    filename: str | None = None

    # Exhibit-specific
    category: str | None = None
    hall: str | None = None
    floor: int | None = None
    era: str | None = None
    importance: int | None = None
    location_x: float | None = None
    location_y: float | None = None

    # Allow additional fields
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        if self.name is not None:
            result["name"] = self.name
        if self.filename is not None:
            result["filename"] = self.filename
        if self.category is not None:
            result["category"] = self.category
        if self.hall is not None:
            result["hall"] = self.hall
        if self.floor is not None:
            result["floor"] = self.floor
        if self.era is not None:
            result["era"] = self.era
        if self.importance is not None:
            result["importance"] = self.importance
        if self.location_x is not None:
            result["location_x"] = self.location_x
        if self.location_y is not None:
            result["location_y"] = self.location_y
        result.update(self.extra)
        return result


@dataclass
class ContentSource:
    """Unified content source for indexing.

    Represents any content that can be chunked and embedded for RAG retrieval.
    """

    source_id: str
    source_type: str  # "document" | "exhibit"
    content: str
    metadata: ContentMetadata = field(default_factory=ContentMetadata)

    def __post_init__(self):
        """Validate source_type."""
        valid_types = {"document", "exhibit"}
        if self.source_type not in valid_types:
            raise ValueError(f"source_type must be one of {valid_types}, got '{self.source_type}'")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_content_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/content_source.py backend/tests/unit/test_content_source.py
git commit -m "feat: add unified ContentSource model for indexing"
```

---

## Task 2: Create UnifiedIndexingService

**Files:**
- Create: `backend/app/application/unified_indexing_service.py`
- Modify: `backend/tests/unit/test_ingestion_service.py`

- [ ] **Step 1: Write the test for UnifiedIndexingService**

```python
# backend/tests/unit/test_unified_indexing_service.py
from unittest.mock import AsyncMock

import pytest
from app.application.chunking import ChunkConfig
from app.application.content_source import ContentSource, ContentMetadata
from app.application.unified_indexing_service import UnifiedIndexingService


@pytest.mark.asyncio
async def test_unified_indexing_service_indexes_content_source():
    """Test that UnifiedIndexingService indexes a ContentSource."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)],
    )

    source = ContentSource(
        source_id="test-doc-123",
        source_type="document",
        content="This is a test document content for chunking and indexing.",
        metadata=ContentMetadata(filename="test.txt"),
    )

    count = await service.index_source(source)

    assert count > 0
    assert mock_es.index_chunk.call_count == count

    # Verify the indexed document has correct fields
    call_args = mock_es.index_chunk.call_args
    indexed_doc = call_args[0][0]
    assert indexed_doc["source_id"] == "test-doc-123"
    assert indexed_doc["source_type"] == "document"
    assert "chunk_id" in indexed_doc
    assert "content_vector" in indexed_doc


@pytest.mark.asyncio
async def test_unified_indexing_service_indexes_exhibit():
    """Test that UnifiedIndexingService indexes an exhibit ContentSource."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=200, overlap=20)],
    )

    source = ContentSource(
        source_id="exhibit-456",
        source_type="exhibit",
        content="Ming Dynasty Blue and White Porcelain Vase. This exquisite piece dates back to the 15th century.",
        metadata=ContentMetadata(
            name="Blue and White Vase",
            category="Ceramics",
            hall="Hall A",
            floor=2,
            era="Ming Dynasty",
            importance=5,
        ),
    )

    count = await service.index_source(source)

    assert count > 0

    # Verify metadata is preserved
    call_args = mock_es.index_chunk.call_args
    indexed_doc = call_args[0][0]
    assert indexed_doc["source_type"] == "exhibit"
    assert indexed_doc["metadata"]["name"] == "Blue and White Vase"
    assert indexed_doc["metadata"]["category"] == "Ceramics"


@pytest.mark.asyncio
async def test_unified_indexing_service_delete_source():
    """Test that UnifiedIndexingService can delete a source."""
    mock_es = AsyncMock()
    mock_es.delete_by_query = AsyncMock(return_value={"deleted": 5})

    mock_embeddings = AsyncMock()

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
    )

    await service.delete_source("test-doc-123")

    mock_es.delete_by_query.assert_called_once()
    call_args = mock_es.delete_by_query.call_args
    query = call_args[1]["body"]
    assert query["query"]["term"]["source_id"] == "test-doc-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_unified_indexing_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement UnifiedIndexingService**

```python
# backend/app/application/unified_indexing_service.py
"""Unified indexing service for all content types."""

import asyncio
from typing import Any

from loguru import logger

from app.application.chunking import ChunkConfig, TextChunker
from app.application.content_source import ContentSource
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings


class UnifiedIndexingService:
    """Unified service for indexing any content source.

    Handles chunking, embedding, and indexing for both documents and exhibits.
    """

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
        ]

    async def index_source(
        self,
        source: ContentSource,
        max_concurrency: int = 10,
    ) -> int:
        """Index a content source to Elasticsearch.

        Args:
            source: The ContentSource to index.
            max_concurrency: Maximum concurrent ES indexing operations.

        Returns:
            Total number of chunks indexed.
        """
        total_chunks = 0

        for config in self.chunk_configs:
            chunker = TextChunker(config)
            chunks = chunker.chunk(
                text=source.content,
                document_id=source.source_id,
                source=source.source_type,
            )

            if not chunks:
                continue

            # Batch embed
            chunk_texts = [c.content for c in chunks]
            embeddings_list = await self.embeddings.aembed_documents(chunk_texts)

            # Prepare documents with unified schema
            docs = []
            for chunk, embedding in zip(chunks, embeddings_list):
                doc = {
                    # Unified fields
                    "chunk_id": chunk.id,
                    "source_id": source.source_id,
                    "source_type": source.source_type,
                    "content": chunk.content,
                    "content_vector": embedding,
                    "chunk_level": chunk.level,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    # Metadata as nested object
                    "metadata": source.metadata.to_dict(),
                }
                docs.append(doc)
                total_chunks += 1

            # Concurrent indexing with semaphore
            semaphore = asyncio.Semaphore(max_concurrency)

            async def index_with_semaphore(doc: dict) -> None:
                async with semaphore:
                    await self.es_client.index_chunk(doc)

            await asyncio.gather(*[index_with_semaphore(doc) for doc in docs])

        logger.info(f"Indexed {total_chunks} chunks for source {source.source_id}")
        return total_chunks

    async def delete_source(
        self,
        source_id: str,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """Delete all chunks for a source from Elasticsearch.

        Args:
            source_id: The ID of the source to delete.
            source_type: Optional source type filter.

        Returns:
            Result from Elasticsearch delete operation.
        """
        if source_type:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"source_id": source_id}},
                            {"term": {"source_type": source_type}},
                        ]
                    }
                }
            }
        else:
            query = {"query": {"term": {"source_id": source_id}}}

        result = await self.es_client.delete_by_query(
            index=self.es_client.index_name,
            body=query,
        )
        logger.info(f"Deleted source {source_id} from index")
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_unified_indexing_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/unified_indexing_service.py backend/tests/unit/test_unified_indexing_service.py
git commit -m "feat: add UnifiedIndexingService for all content types"
```

---

## Task 3: Update ES Client Schema

**Files:**
- Modify: `backend/app/infra/elasticsearch/client.py`
- Modify: `backend/tests/unit/test_es_client.py`

- [ ] **Step 1: Write test for unified schema fields**

```python
# Add to backend/tests/unit/test_es_client.py

@pytest.mark.asyncio
async def test_create_index_includes_unified_fields():
    """Test that index creation includes unified schema fields."""
    from app.infra.elasticsearch.client import ElasticsearchClient

    mock_es = AsyncMock()
    mock_es.indices = AsyncMock()
    mock_es.indices.exists = AsyncMock(return_value=False)
    mock_es.indices.create = AsyncMock(return_value={"acknowledged": True})

    client = ElasticsearchClient.__new__(ElasticsearchClient)
    client.client = mock_es
    client.index_name = "test_index"

    await client.create_index("test_index", dims=768)

    call_args = mock_es.indices.create.call_args
    mapping = call_args[1]["body"]["mappings"]["properties"]

    # Verify unified fields
    assert "source_id" in mapping
    assert mapping["source_id"]["type"] == "keyword"
    assert "source_type" in mapping
    assert mapping["source_type"]["type"] == "keyword"
    assert "metadata" in mapping
    assert mapping["metadata"]["type"] == "object"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_es_client.py::test_create_index_includes_unified_fields -v`
Expected: FAIL

- [ ] **Step 3: Update ES client create_index method**

```python
# backend/app/infra/elasticsearch/client.py
# Update the create_index method mapping:

async def create_index(self, index_name: str, dims: int = 1536) -> dict[str, Any]:
    try:
        if await self.client.indices.exists(index=index_name):
            return {"status": "already_exists"}

        mapping = {
            "mappings": {
                "properties": {
                    # Unified schema fields
                    "chunk_id": {"type": "keyword"},
                    "source_id": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "chunk_level": {"type": "integer"},
                    "parent_chunk_id": {"type": "keyword"},
                    "start_char": {"type": "integer"},
                    "end_char": {"type": "integer"},
                    "content": {"type": "text", "analyzer": "ik_max_word"},
                    "content_vector": {"type": "dense_vector", "dims": dims, "index": True, "similarity": "cosine"},
                    # Metadata as nested object
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "keyword"},
                            "filename": {"type": "keyword"},
                            "category": {"type": "keyword"},
                            "hall": {"type": "keyword"},
                            "floor": {"type": "integer"},
                            "era": {"type": "keyword"},
                            "importance": {"type": "integer"},
                            "location_x": {"type": "float"},
                            "location_y": {"type": "float"},
                        },
                    },
                    # Legacy fields for backward compatibility
                    "document_id": {"type": "keyword"},
                    "title": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    # Legacy exhibit fields
                    "doc_type": {"type": "keyword"},
                    "exhibit_id": {"type": "keyword"},
                }
            }
        }

        await self.client.indices.create(index=index_name, body=mapping)
        logger.info(f"Created ES index: {index_name}")
        return {"status": "created"}
    except (ApiError, TransportError) as e:
        logger.error(f"Failed to create index {index_name}: {repr(e)}")
        raise RetrievalError(f"Failed to create index: {type(e).__name__}")
```

- [ ] **Step 4: Update search methods to support unified schema**

```python
# backend/app/infra/elasticsearch/client.py
# Update search_dense and search_bm25 methods:

async def search_dense(
    self,
    query_vector: list[float],
    top_k: int = 5,
    source_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Dense vector search with optional source type filter."""
    try:
        filter_clauses = []
        if source_types:
            filter_clauses.append({"terms": {"source_type": source_types}})

        query = {
            "knn": {
                "field": "content_vector",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": top_k * 10,
            },
            "size": top_k,
        }

        if filter_clauses:
            query["knn"]["filter"] = {"bool": {"filter": filter_clauses}}

        response = await self.client.search(index=self.index_name, body=query)
        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
    except (ApiError, TransportError) as e:
        logger.error(f"Dense search failed: {type(e).__name__}")
        raise RetrievalError("Dense search failed")


async def search_bm25(
    self,
    query_text: str,
    top_k: int = 5,
    source_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """BM25 text search with optional source type filter."""
    try:
        must_clause = [{"match": {"content": query_text}}]
        if source_types:
            must_clause.append({"terms": {"source_type": source_types}})

        query = {
            "query": {"bool": {"must": must_clause}},
            "size": top_k,
        }

        response = await self.client.search(index=self.index_name, body=query)
        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
    except (ApiError, TransportError) as e:
        logger.error(f"BM25 search failed: {type(e).__name__}")
        raise RetrievalError("BM25 search failed")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_es_client.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/elasticsearch/client.py backend/tests/unit/test_es_client.py
git commit -m "feat: update ES schema for unified content indexing"
```

---

## Task 4: Create UnifiedRetriever

**Files:**
- Modify: `backend/app/infra/langchain/retrievers.py`
- Modify: `backend/tests/unit/test_rrf_retriever.py`

- [ ] **Step 1: Write test for UnifiedRetriever**

```python
# Add to backend/tests/unit/test_rrf_retriever.py

@pytest.mark.asyncio
async def test_unified_retriever_searches_all_content_types():
    """Test that UnifiedRetriever searches all content types."""
    from app.infra.langchain.retrievers import UnifiedRetriever

    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(
        return_value=[
            {"chunk_id": "1", "content": "document chunk", "source_id": "doc1", "source_type": "document"},
            {"chunk_id": "2", "content": "exhibit chunk", "source_id": "ex1", "source_type": "exhibit"},
        ]
    )
    mock_es.search_bm25 = AsyncMock(
        return_value=[
            {"chunk_id": "1", "content": "document chunk", "source_id": "doc1", "source_type": "document"},
        ]
    )

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
    )

    docs = await retriever._aget_relevant_documents("test query")

    assert len(docs) > 0
    # Verify both dense and bm25 were called
    mock_es.search_dense.assert_called_once()
    mock_es.search_bm25.assert_called_once()


@pytest.mark.asyncio
async def test_unified_retriever_filters_by_source_type():
    """Test that UnifiedRetriever can filter by source type."""
    from app.infra.langchain.retrievers import UnifiedRetriever

    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(return_value=[])
    mock_es.search_bm25 = AsyncMock(return_value=[])

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
        source_types=["exhibit"],
    )

    await retriever._aget_relevant_documents("test query")

    # Verify source_types was passed
    call_args = mock_es.search_dense.call_args
    assert call_args[1]["source_types"] == ["exhibit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_rrf_retriever.py -v`
Expected: FAIL with "ImportError: cannot import name 'UnifiedRetriever'"

- [ ] **Step 3: Implement UnifiedRetriever**

```python
# Add to backend/app/infra/langchain/retrievers.py

class UnifiedRetriever(BaseRetriever):
    """Unified retriever for all content types using RRF fusion.

    Searches both documents and exhibits through a single interface.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    es_client: Any
    embeddings: Any
    top_k: int = 5
    rrf_k: int = 60
    source_types: list[str] | None = None

    def _get_relevant_documents(self, query: str) -> list[Document]:
        raise NotImplementedError(
            "Sync retrieval not supported. Use _aget_relevant_documents instead."
        )

    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        """Retrieve documents using RRF fusion of dense and BM25 search."""
        query_vector = await self.embeddings.aembed_query(query)

        # Parallel search
        dense_results = await self.es_client.search_dense(
            query_vector,
            top_k=self.top_k * 2,
            source_types=self.source_types,
        )
        bm25_results = await self.es_client.search_bm25(
            query,
            top_k=self.top_k * 2,
            source_types=self.source_types,
        )

        # RRF fusion
        fused = self._rrf_fusion(dense_results, bm25_results)

        return [self._to_document(item) for item in fused[: self.top_k]]

    def _rrf_fusion(
        self,
        dense_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply RRF fusion to merge dense and BM25 results."""
        doc_map: dict[str, dict[str, Any]] = {}
        dense_ranks: dict[str, int] = {}
        bm25_ranks: dict[str, int] = {}

        for rank, doc in enumerate(dense_results, start=1):
            chunk_id = doc.get("chunk_id", doc.get("chunk_id"))
            if chunk_id:
                dense_ranks[chunk_id] = rank
                doc_map[chunk_id] = doc

        for rank, doc in enumerate(bm25_results, start=1):
            chunk_id = doc.get("chunk_id", doc.get("chunk_id"))
            if chunk_id:
                bm25_ranks[chunk_id] = rank
                if chunk_id not in doc_map:
                    doc_map[chunk_id] = doc

        rrf_scores: dict[str, float] = {}
        for chunk_id in doc_map:
            score = 0.0
            if chunk_id in dense_ranks:
                score += 1.0 / (self.rrf_k + dense_ranks[chunk_id])
            if chunk_id in bm25_ranks:
                score += 1.0 / (self.rrf_k + bm25_ranks[chunk_id])
            rrf_scores[chunk_id] = score

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        result = []
        for chunk_id in sorted_ids:
            doc = doc_map[chunk_id].copy()
            doc["rrf_score"] = rrf_scores[chunk_id]
            result.append(doc)

        return result

    def _to_document(self, item: dict[str, Any]) -> Document:
        """Convert ES result to LangChain Document."""
        metadata = item.get("metadata", {})

        return Document(
            page_content=item.get("content", ""),
            metadata={
                "chunk_id": item.get("chunk_id"),
                "source_id": item.get("source_id"),
                "source_type": item.get("source_type"),
                "chunk_level": item.get("chunk_level"),
                "rrf_score": item.get("rrf_score"),
                # Include metadata fields
                **metadata,
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_rrf_retriever.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/langchain/retrievers.py backend/tests/unit/test_rrf_retriever.py
git commit -m "feat: add UnifiedRetriever for all content types"
```

---

## Task 5: Update Factory Functions

**Files:**
- Modify: `backend/app/infra/langchain/__init__.py`
- Modify: `backend/tests/unit/test_factory_functions.py`

- [ ] **Step 1: Update create_retriever to use UnifiedRetriever**

```python
# backend/app/infra/langchain/__init__.py
# Update the import and create_retriever function:

from app.infra.langchain.retrievers import UnifiedRetriever

def create_retriever(
    es_client: Any,
    embeddings: CustomOllamaEmbeddings,
    settings: Settings,
) -> UnifiedRetriever:
    """Create UnifiedRetriever instance."""
    return UnifiedRetriever(
        es_client=es_client,
        embeddings=embeddings,
        top_k=5,
        rrf_k=60,
    )
```

- [ ] **Step 2: Update __all__ exports**

```python
# backend/app/infra/langchain/__init__.py
# Update __all__:

__all__ = [
    "CustomOllamaEmbeddings",
    "create_embeddings",
    "create_llm",
    "create_retriever",
    "create_rerank_provider",
    "create_query_rewriter",
    "create_rag_agent",
    "create_curator_agent",
    "CuratorAgent",
    "PathPlanningTool",
    "KnowledgeRetrievalTool",
    "NarrativeGenerationTool",
    "ReflectionPromptTool",
    "PreferenceManagementTool",
    "create_curator_tools",
    "UnifiedRetriever",
]
```

- [ ] **Step 3: Run factory function tests**

Run: `uv run pytest backend/tests/unit/test_factory_functions.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/infra/langchain/__init__.py
git commit -m "refactor: update create_retriever to use UnifiedRetriever"
```

---

## Task 6: Update Admin API for Exhibits

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `backend/tests/contract/test_admin_api.py`

- [ ] **Step 1: Update admin.py to use UnifiedIndexingService**

```python
# backend/app/api/admin.py
# Replace ExhibitIndexingService import and usage:

from app.application.unified_indexing_service import UnifiedIndexingService
from app.application.content_source import ContentSource, ContentMetadata

# Update create_exhibit endpoint:
@router.post("/exhibits", response_model=ExhibitResponse, status_code=status.HTTP_201_CREATED)
async def create_exhibit(
    session: SessionDep,
    request: CreateExhibitRequest,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ExhibitResponse:
    """Create a new exhibit (admin only)."""
    service = get_exhibit_service(session)

    exhibit = await service.create_exhibit(
        name=request.name,
        description=request.description,
        location_x=request.location_x,
        location_y=request.location_y,
        floor=request.floor,
        hall=request.hall,
        category=request.category,
        era=request.era,
        importance=request.importance,
        estimated_visit_time=request.estimated_visit_time,
        document_id=request.document_id,
    )

    # Index the exhibit using UnifiedIndexingService
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        indexing_service = UnifiedIndexingService(es_client, embeddings)

        # Build content for indexing
        content = f"{exhibit.name}\n\n{exhibit.description}"

        source = ContentSource(
            source_id=exhibit.id.value,
            source_type="exhibit",
            content=content,
            metadata=ContentMetadata(
                name=exhibit.name,
                category=exhibit.category,
                hall=exhibit.hall,
                floor=exhibit.location.floor,
                era=exhibit.era,
                importance=exhibit.importance,
                location_x=exhibit.location.x,
                location_y=exhibit.location.y,
            ),
        )
        await indexing_service.index_source(source)
    except Exception as e:
        logger.error(f"Failed to index exhibit {exhibit.id.value}: {e}")

    return ExhibitResponse(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        location_x=exhibit.location.x,
        location_y=exhibit.location.y,
        floor=exhibit.location.floor,
        hall=exhibit.hall,
        category=exhibit.category,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        document_id=exhibit.document_id,
        is_active=exhibit.is_active,
        created_at=exhibit.created_at.isoformat(),
        updated_at=exhibit.updated_at.isoformat(),
    )
```

- [ ] **Step 2: Update update_exhibit endpoint similarly**

```python
# backend/app/api/admin.py
# Update update_exhibit endpoint:

@router.put("/exhibits/{exhibit_id}", response_model=ExhibitResponse)
async def update_exhibit(
    session: SessionDep,
    exhibit_id: str,
    request: UpdateExhibitRequest,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ExhibitResponse:
    """Update an exhibit (admin only)."""
    # ... existing validation code ...

    try:
        exhibit = await service.update_exhibit(
            exhibit_id=exhibit_id,
            name=request.name,
            description=request.description,
            location_x=request.location_x,
            location_y=request.location_y,
            floor=request.floor,
            hall=request.hall,
            category=request.category,
            era=request.era,
            importance=request.importance,
            estimated_visit_time=request.estimated_visit_time,
            document_id=request.document_id,
            is_active=request.is_active,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None

    # Update Elasticsearch index
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        indexing_service = UnifiedIndexingService(es_client, embeddings)

        if exhibit.is_active:
            # Reindex with updated content
            content = f"{exhibit.name}\n\n{exhibit.description}"
            source = ContentSource(
                source_id=exhibit.id.value,
                source_type="exhibit",
                content=content,
                metadata=ContentMetadata(
                    name=exhibit.name,
                    category=exhibit.category,
                    hall=exhibit.hall,
                    floor=exhibit.location.floor,
                    era=exhibit.era,
                    importance=exhibit.importance,
                    location_x=exhibit.location.x,
                    location_y=exhibit.location.y,
                ),
            )
            # Delete old chunks first
            await indexing_service.delete_source(exhibit.id.value)
            await indexing_service.index_source(source)
        else:
            await indexing_service.delete_source(exhibit.id.value)
    except Exception as e:
        logger.error(f"Failed to update exhibit index {exhibit.id.value}: {e}")

    return ExhibitResponse(...)
```

- [ ] **Step 3: Update delete_exhibit endpoint**

```python
# backend/app/api/admin.py

@router.delete("/exhibits/{exhibit_id}", response_model=DeleteResponse)
async def delete_exhibit(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> DeleteResponse:
    """Delete an exhibit (admin only)."""
    service = get_exhibit_service(session)

    try:
        success = await service.delete_exhibit(exhibit_id)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    # Delete from Elasticsearch using UnifiedIndexingService
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        indexing_service = UnifiedIndexingService(es_client, embeddings)
        await indexing_service.delete_source(exhibit_id, source_type="exhibit")
    except Exception as e:
        logger.error(f"Failed to delete exhibit index {exhibit_id}: {e}")

    return DeleteResponse(status="deleted", exhibit_id=exhibit_id)
```

- [ ] **Step 4: Update reindex endpoint**

```python
# backend/app/api/admin.py

@router.post("/exhibits/reindex", response_model=ReindexResponse)
async def reindex_all_exhibits(
    session: SessionDep,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ReindexResponse:
    """Reindex all active exhibits to Elasticsearch (admin only)."""
    service = get_exhibit_service(session)
    exhibits = await service.list_all_active()

    if not hasattr(http_request.app.state, "es_client"):
        raise RuntimeError("Elasticsearch client not initialized.")
    if not hasattr(http_request.app.state, "embeddings"):
        raise RuntimeError("Embeddings not initialized.")

    es_client = http_request.app.state.es_client
    embeddings = http_request.app.state.embeddings
    indexing_service = UnifiedIndexingService(es_client, embeddings)

    indexed_count = 0
    failed_count = 0

    for exhibit in exhibits:
        try:
            content = f"{exhibit.name}\n\n{exhibit.description}"
            source = ContentSource(
                source_id=exhibit.id.value,
                source_type="exhibit",
                content=content,
                metadata=ContentMetadata(
                    name=exhibit.name,
                    category=exhibit.category,
                    hall=exhibit.hall,
                    floor=exhibit.location.floor,
                    era=exhibit.era,
                    importance=exhibit.importance,
                    location_x=exhibit.location.x,
                    location_y=exhibit.location.y,
                ),
            )
            await indexing_service.index_source(source)
            indexed_count += 1
        except Exception as e:
            logger.error(f"Failed to index exhibit {exhibit.id.value}: {e}")
            failed_count += 1

    return ReindexResponse(
        status="completed",
        total=len(exhibits),
        indexed=indexed_count,
        failed=failed_count,
    )
```

- [ ] **Step 5: Run admin API tests**

Run: `uv run pytest backend/tests/contract/test_admin_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin.py backend/tests/contract/test_admin_api.py
git commit -m "refactor: update admin API to use UnifiedIndexingService"
```

---

## Task 7: Update Documents API

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update documents.py to use UnifiedIndexingService**

```python
# backend/app/api/documents.py
# Update the get_ingestion_service function and process_document_background:

from app.application.unified_indexing_service import UnifiedIndexingService
from app.application.content_source import ContentSource, ContentMetadata

def get_unified_indexing_service() -> UnifiedIndexingService:
    """Get unified indexing service from app.state or create fallback."""
    service = _get_app_state_attr("unified_indexing_service")
    if service is not None:
        return service

    settings = get_settings()
    es_client = ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )
    embeddings = create_embeddings(settings)
    return UnifiedIndexingService(es_client=es_client, embeddings=embeddings)


async def process_document_background(
    document_id: str,
    content: str,
    filename: str,
    indexing_service: UnifiedIndexingService,
):
    """Background task to process uploaded document."""
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with get_session(session_maker) as session:
        try:
            source = ContentSource(
                source_id=document_id,
                source_type="document",
                content=content,
                metadata=ContentMetadata(filename=filename),
            )
            chunk_count = await indexing_service.index_source(source)

            # Update document status
            await update_document_status(session, document_id, "completed")
            await session.commit()
        except Exception as e:
            logger.exception(f"Failed to process document {document_id}: {e}")
            await update_document_status(session, document_id, "failed", str(e))
            await session.commit()
```

- [ ] **Step 2: Update main.py initialization**

```python
# backend/app/main.py
# Update imports and lifespan:

from app.application.unified_indexing_service import UnifiedIndexingService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing initialization ...

    # Replace IngestionService with UnifiedIndexingService
    unified_indexing_service = UnifiedIndexingService(
        es_client=es_client,
        embeddings=embeddings,
    )

    # Store in app.state
    app.state.unified_indexing_service = unified_indexing_service
    # Keep ingestion_service for backward compatibility
    app.state.ingestion_service = unified_indexing_service

    # ... rest of lifespan ...
```

- [ ] **Step 3: Add getter function for unified service**

```python
# backend/app/main.py

def get_unified_indexing_service() -> UnifiedIndexingService:
    """Get unified indexing service from app.state."""
    if hasattr(app.state, "unified_indexing_service"):
        return app.state.unified_indexing_service
    raise RuntimeError("Unified indexing service not initialized. App not started?")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest backend/tests/unit/test_ingestion_service.py backend/tests/contract/test_documents_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/documents.py backend/app/main.py
git commit -m "refactor: update documents API to use UnifiedIndexingService"
```

---

## Task 8: Update init_exhibits.py Script

**Files:**
- Modify: `scripts/init_exhibits.py`

- [ ] **Step 1: Update script to use UnifiedIndexingService**

```python
# scripts/init_exhibits.py
# Update imports and usage:

from app.application.unified_indexing_service import UnifiedIndexingService
from app.application.content_source import ContentSource, ContentMetadata

async def create_exhibits_with_documents(
    session_maker,
    es_client: ElasticsearchClient,
    embeddings: CustomOllamaEmbeddings,
    user_id: str,
) -> None:
    """Create exhibits with documents and embeddings using unified service."""
    indexing_service = UnifiedIndexingService(
        es_client=es_client,
        embeddings=embeddings,
    )

    created_exhibits = 0
    created_documents = 0
    skipped_count = 0

    for item in SAMPLE_EXHIBITS:
        async with get_session(session_maker) as session:
            # Check if exhibit already exists
            result = await session.execute(
                select(Exhibit).where(Exhibit.name == item["name"])
            )
            existing = result.scalars().first()

            if existing:
                print(f"  Exhibit already exists: {item['name']}")
                skipped_count += 1
                continue

            # Create document first (for tracking)
            doc_id = str(uuid.uuid4())
            document = Document(
                id=doc_id,
                user_id=user_id,
                filename=f"{item['name']}.txt",
                status="pending",
            )
            session.add(document)
            await session.commit()

        # Index content using UnifiedIndexingService
        try:
            source = ContentSource(
                source_id=doc_id,
                source_type="document",
                content=item["content"],
                metadata=ContentMetadata(filename=f"{item['name']}.txt"),
            )
            chunk_count = await indexing_service.index_source(source)
            created_documents += 1
            print(f"  Created document: {item['name']}.txt ({len(item['content'])} chars, {chunk_count} chunks)")
        except Exception as e:
            print(f"  Failed to create document {item['name']}: {e}")
            continue

        # Create exhibit linked to document
        async with get_session(session_maker) as session:
            now = datetime.now(UTC)
            exhibit = Exhibit(
                id=str(uuid.uuid4()),
                name=item["name"],
                description=item["description"],
                location_x=item["location_x"],
                location_y=item["location_y"],
                floor=item["floor"],
                hall=item["hall"],
                category=item["category"],
                era=item["era"],
                importance=item["importance"],
                estimated_visit_time=item["estimated_visit_time"],
                document_id=doc_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(exhibit)
            await session.commit()
            created_exhibits += 1
            print(f"  Created exhibit: {item['name']} ({item['category']}, {item['hall']}, {item['floor']}F)")

    print(f"\nSummary:")
    print(f"  Exhibits: {created_exhibits} created, {skipped_count} skipped")
    print(f"  Documents: {created_documents} created with embeddings")
```

- [ ] **Step 2: Commit**

```bash
git add scripts/init_exhibits.py
git commit -m "refactor: update init_exhibits.py to use UnifiedIndexingService"
```

---

## Task 9: Update and Add Tests

**Files:**
- Modify: `backend/tests/unit/test_ingestion_service.py`
- Modify: `backend/tests/unit/test_rag_agent.py`
- Modify: `backend/tests/unit/test_parallel_indexing.py`

- [ ] **Step 1: Update test_ingestion_service.py to test unified service**

```python
# backend/tests/unit/test_ingestion_service.py
# Update to test both document and exhibit sources:

import pytest
from app.application.chunking import ChunkConfig
from app.application.content_source import ContentSource, ContentMetadata
from app.application.unified_indexing_service import UnifiedIndexingService


@pytest.mark.asyncio
async def test_unified_indexing_service_indexes_document():
    """Test indexing a document content source."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)],
    )

    source = ContentSource(
        source_id="test-doc",
        source_type="document",
        content="This is test content for indexing.",
        metadata=ContentMetadata(filename="test.txt"),
    )

    count = await service.index_source(source)

    assert count > 0
    assert mock_es.index_chunk.call_count == count


@pytest.mark.asyncio
async def test_unified_indexing_service_indexes_exhibit():
    """Test indexing an exhibit content source."""
    mock_es = AsyncMock()
    mock_es.index_chunk = AsyncMock(return_value={"result": "created"})

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])

    service = UnifiedIndexingService(
        es_client=mock_es,
        embeddings=mock_embeddings,
        chunk_configs=[ChunkConfig(level=1, window_size=100, overlap=10)],
    )

    source = ContentSource(
        source_id="test-exhibit",
        source_type="exhibit",
        content="Ming Dynasty Vase description.",
        metadata=ContentMetadata(
            name="Vase",
            category="Ceramics",
            hall="Hall A",
        ),
    )

    count = await service.index_source(source)

    assert count > 0
    call_args = mock_es.index_chunk.call_args
    indexed_doc = call_args[0][0]
    assert indexed_doc["metadata"]["name"] == "Vase"
```

- [ ] **Step 2: Update test_rag_agent.py**

```python
# backend/tests/unit/test_rag_agent.py
# Update retriever mock to use UnifiedRetriever:

@pytest.mark.asyncio
async def test_rag_agent_uses_unified_retriever():
    """Test that RAG agent works with UnifiedRetriever."""
    from app.infra.langchain.retrievers import UnifiedRetriever

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test answer"))

    mock_es = AsyncMock()
    mock_es.search_dense = AsyncMock(return_value=[])
    mock_es.search_bm25 = AsyncMock(return_value=[])

    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 768)

    retriever = UnifiedRetriever(
        es_client=mock_es,
        embeddings=mock_embeddings,
        top_k=5,
    )

    agent = RAGAgent(
        llm=mock_llm,
        retriever=retriever,
        score_threshold=0.7,
        max_attempts=3,
    )

    result = await agent.run("test query")

    assert result["answer"] == "Test answer"
```

- [ ] **Step 3: Run all unit tests**

Run: `uv run pytest backend/tests/unit -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/unit/test_ingestion_service.py backend/tests/unit/test_rag_agent.py backend/tests/unit/test_parallel_indexing.py
git commit -m "test: update tests for unified content indexing"
```

---

## Task 10: Deprecate Old Services

**Files:**
- Modify: `backend/app/application/exhibit_indexing_service.py`
- Modify: `backend/app/infra/langchain/retrievers.py`

- [ ] **Step 1: Add deprecation warnings**

```python
# backend/app/application/exhibit_indexing_service.py
"""Exhibit indexing service - DEPRECATED.

This module is deprecated. Use UnifiedIndexingService instead.
"""

import warnings

warnings.warn(
    "ExhibitIndexingService is deprecated. Use UnifiedIndexingService instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ... rest of file unchanged for backward compatibility ...
```

```python
# backend/app/infra/langchain/retrievers.py
# Add deprecation notices to old classes:

class RRFRetriever(BaseRetriever):
    """RRF 融合检索器 - DEPRECATED.

    Use UnifiedRetriever instead.
    """
    # ... existing code ...


class ExhibitAwareRetriever(BaseRetriever):
    """展品感知检索器 - DEPRECATED.

    Use UnifiedRetriever instead.
    """
    # ... existing code ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/application/exhibit_indexing_service.py backend/app/infra/langchain/retrievers.py
git commit -m "chore: add deprecation warnings to old indexing and retriever classes"
```

---

## Task 11: Integration Testing

**Files:**
- Modify: `backend/tests/e2e/test_ingestion_flow.py`
- Modify: `backend/tests/e2e/test_retrieval_flow.py`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest backend/tests/ -v`
Expected: PASS (may have some skips for e2e tests without infrastructure)

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest backend/tests/contract backend/tests/integration -v`
Expected: PASS

- [ ] **Step 3: Verify with manual test**

```bash
# Start services
docker-compose up -d

# Run init script
uv run python scripts/init_exhibits.py

# Start dev server
uv run uvicorn backend.app.main:app --reload

# Test API endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "明代瓷器有哪些特点？"}'
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: verify unified content indexing integration"
```

---

## Summary

This migration unifies document and exhibit indexing into a single pipeline:

1. **ContentSource** - Unified data model for all content types
2. **UnifiedIndexingService** - Single service for chunking + embedding
3. **UnifiedRetriever** - Single retriever with RRF fusion for all content
4. **Updated ES Schema** - `source_type`, `source_id`, `metadata` fields
5. **Backward Compatibility** - Deprecation warnings, legacy field support

### Migration Checklist for Existing Deployments

1. Deploy new code
2. Run `POST /api/v1/admin/exhibits/reindex` to reindex all exhibits
3. Run `scripts/init_exhibits.py` if needed for initial data
4. Monitor logs for deprecation warnings
