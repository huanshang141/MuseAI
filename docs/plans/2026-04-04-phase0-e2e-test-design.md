# Phase 0 E2E Test Design

## Overview

Design for end-to-end integration tests to verify Phase 0 (Tasks 1-11) implementation is complete and functional with real services.

## Scope

### Real Services
- PostgreSQL (asyncpg)
- Elasticsearch
- Ollama Embedding

### Test Data
Preset museum documentation content for realistic RAG testing.

### Verification Level
Basic verification:
- HTTP status codes correct
- Response data structures valid
- Non-empty results where expected
- Vector dimensions correct

## Test Architecture

```
backend/tests/e2e/
├── conftest.py               # E2E fixtures (real services)
├── test_ingestion_flow.py    # Document ingestion pipeline
├── test_retrieval_flow.py    # Search and retrieval pipeline
└── test_data/
    └── museum_sample.txt     # Sample museum document
```

## Test Cases

### 1. test_ingestion_flow.py

| Step | Action | Verification |
|------|--------|--------------|
| 1.1 | Upload document | 200, document_id returned |
| 1.2 | Create chunks | chunks non-empty |
| 1.3 | Generate embeddings | dims == EMBEDDING_DIMS |
| 1.4 | Index to ES | index created |

### 2. test_retrieval_flow.py

| Step | Action | Verification |
|------|--------|--------------|
| 2.1 | Dense search | results non-empty |
| 2.2 | BM25 search | results non-empty |
| 2.3 | RRF fusion | fused results sorted by score |
| 2.4 | Full pipeline | end-to-end query returns relevant chunks |

## Fixtures

### conftest.py
```python
# Real service connections
- postgres_session: Real PostgreSQL session
- es_client: Real Elasticsearch client
- embedding_provider: Real Ollama provider
- sample_document: Museum sample text

# Test data
- MUSEUM_SAMPLE_TEXT: Multi-paragraph museum content
```

## Test Data

### museum_sample.txt
```
博物馆藏品介绍

青铜器展区
本展区展示了中国古代青铜器的精湛工艺。商代晚期的司母戊鼎重达832.84公斤...

书画艺术厅
这里收藏了唐宋元明清各代名家真迹。王羲之《兰亭序》摹本...

瓷器珍品馆
宋代五大名窑的代表作品尽收于此。汝窑天青釉...
```

## Dependencies

### Environment Variables Required
- DATABASE_URL
- ELASTICSEARCH_URL
- EMBEDDING_OLLAMA_BASE_URL
- EMBEDDING_OLLAMA_MODEL
- EMBEDDING_DIMS
- ELASTICSEARCH_INDEX

### Service Requirements
- PostgreSQL running and accessible
- Elasticsearch running with index created
- Ollama serving embedding model

## Success Criteria

1. All E2E tests pass with real services
2. Document upload → chunking → embedding → indexing flow works
3. Dense + BM25 + RRF retrieval returns results
4. No errors or exceptions in the pipeline

## Implementation Notes

- Tests should be idempotent (cleanup after each test)
- Use unique indices/documents per test run
- Skip tests if services unavailable (graceful degradation)
- Log detailed error messages for debugging
