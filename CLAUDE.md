# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MuseAI is a Museum AI Guide System - a RAG (Retrieval-Augmented Generation) application for intelligent museum content interaction. It uses FastAPI for the backend, Vue 3 + Element Plus for the frontend, and integrates with Elasticsearch, PostgreSQL, Redis, and OpenAI-compatible LLM providers.

## Development Commands

### Backend

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest backend/tests/unit backend/tests/contract -v

# Run a single test file
uv run pytest backend/tests/unit/test_domain_entities.py -v

# Run a single test
uv run pytest backend/tests/unit/test_domain_entities.py::test_user_creation -v

# Run e2e tests (requires running infrastructure)
uv run pytest backend/tests/e2e -v

# Linting
uv run ruff check backend/

# Type checking
uv run mypy backend/

# Start development server
uv run uvicorn backend.app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # Development server
npm run build    # Production build
```

### Infrastructure

```bash
# Start all services (Elasticsearch, PostgreSQL, Redis)
docker-compose up -d

# Stop all services
docker-compose down
```

## Architecture

### Backend Structure

The backend follows a strict layered architecture (API → Application → Domain → Infrastructure):

```
backend/app/
├── api/                    # FastAPI routers and request/response models
│   ├── deps.py            # Dependency injection (DB session, auth, rate limiting)
│   ├── auth.py            # Authentication endpoints
│   ├── chat.py            # Chat session and message endpoints
│   ├── documents.py       # Document upload API
│   └── health.py          # Health check endpoints
├── application/            # Business logic and services
│   ├── auth_service.py    # User registration/login
│   ├── chat_service.py    # Chat message handling, SSE streaming
│   ├── document_service.py # Document CRUD
│   ├── ingestion_service.py # Document chunking and embedding
│   ├── chunking.py        # Text chunking algorithms
│   └── retrieval.py       # RRF fusion algorithm
├── domain/                 # Domain entities and value objects
│   ├── entities.py        # User, ChatSession, Document, IngestionJob
│   ├── value_objects.py   # Typed IDs (UserId, SessionId, etc.)
│   └── exceptions.py      # Domain-specific exceptions
├── infra/                  # Infrastructure layer
│   ├── postgres/          # Database models and session management
│   │   ├── models.py      # SQLAlchemy ORM models
│   │   └── database.py    # Engine lifecycle, session factory
│   ├── elasticsearch/     # ES client for vector/BM25 search
│   ├── redis/             # Caching and token blacklist
│   ├── langchain/         # LangChain integrations
│   │   ├── embeddings.py  # Custom Ollama embeddings
│   │   ├── retrievers.py  # RRF retriever implementation
│   │   └── agents.py      # RAG agent with LangGraph state machine
│   ├── providers/         # External service providers
│   │   ├── llm.py         # OpenAI-compatible LLM provider
│   │   └── embedding.py   # Embedding provider abstraction
│   └── security/          # JWT handling, password hashing
├── workflows/              # Multi-turn conversation workflows
│   ├── multi_turn.py      # State machine for retrieval evaluation
│   └── query_transform.py # Query transformation strategies (HyDE, step-back)
├── config/                 # Configuration management
│   └── settings.py        # Pydantic settings with validation
└── main.py                 # FastAPI app and global singletons
```

### Key Architectural Patterns

1. **Dependency Injection**: FastAPI's `Depends()` for session management, authentication, and rate limiting. See `api/deps.py` for the dependency chain.

2. **Global Singletons**: `main.py` manages global instances (ES client, LLM, embeddings, retriever, RAG agent) with lazy initialization.

3. **RRF Fusion Retrieval**: Combines dense (vector) and sparse (BM25) search using Reciprocal Rank Fusion. See `application/retrieval.py` and `infra/langchain/retrievers.py`.

4. **RAG Agent with LangGraph**: State machine that evaluates retrieval quality and can transform queries if scores are low. See `infra/langchain/agents.py`.

5. **SSE Streaming**: Chat responses stream via Server-Sent Events with structured event types (`thinking`, `chunk`, `done`, `error`).

### Database Schema

PostgreSQL tables:
- `users`: id, email, password_hash, created_at
- `documents`: id, user_id, filename, status, error, created_at
- `ingestion_jobs`: id, document_id, status, chunk_count, error, created_at, updated_at
- `chat_sessions`: id, user_id, title, created_at
- `chat_messages`: id, session_id, role, content, trace_id, created_at

### Elasticsearch Index

Index `museai_chunks_v1` with:
- `chunk_id` (keyword), `document_id` (keyword)
- `content` (text with ik_max_word analyzer)
- `content_vector` (dense_vector, configurable dims)
- `chunk_level`, `source` fields

## Configuration

Environment variables (see `.env.example`):
- `APP_ENV`: development/production (affects secret validation)
- `DATABASE_URL`: PostgreSQL connection string
- `ELASTICSEARCH_URL`: ES endpoint
- `REDIS_URL`: Redis endpoint
- `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`: LLM configuration
- `EMBEDDING_PROVIDER`, `EMBEDDING_OLLAMA_BASE_URL`, `EMBEDDING_OLLAMA_MODEL`: Embedding configuration
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`: Auth settings

Production requires `JWT_SECRET` (≥32 chars) and `LLM_API_KEY`.

## Testing Structure

```
backend/tests/
├── unit/           # Unit tests (fast, mocked dependencies)
├── contract/       # API contract tests (FastAPI TestClient)
├── e2e/            # End-to-end tests (requires running infra)
├── integration/    # Integration tests
└── fixtures/       # Test fixtures and mocks
```

Test configuration in `pyproject.toml`: `asyncio_mode = "auto"`, `testpaths = ["backend/tests"]`.

## Authentication Flow

1. Register/login via `/api/v1/auth/*` endpoints
2. JWT token in `Authorization: Bearer <token>` header
3. Token blacklist in Redis for logout
4. Rate limiting: regular endpoints (fail-open), auth endpoints (fail-closed)

## Common Patterns

### Adding a new API endpoint

1. Create request/response Pydantic models in the router file
2. Add router function with appropriate dependencies (`SessionDep`, `CurrentUser`, `RateLimitDep`)
3. Business logic goes in `application/` layer
4. Database operations use SQLAlchemy async session

### Adding a new test

1. Unit tests: mock external dependencies, test in isolation
2. Contract tests: use `FastAPI TestClient`, mock database with `aiosqlite`
3. E2E tests: require running infrastructure (docker-compose)

### Working with the RAG pipeline

1. Query enters through `chat_service.ask_question_stream_with_rag()`
2. RAG agent retrieves documents, evaluates score
3. If score < threshold, query transformation may occur
4. Response generated with context, streamed via SSE
