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
│   ├── client_ip.py       # Client IP extraction from proxy headers
│   ├── curator.py         # Curator AI agent endpoints
│   ├── documents.py       # Document upload API
│   ├── exhibits.py        # Public exhibit browsing endpoints
│   ├── health.py          # Health check endpoints
│   ├── profile.py         # Visitor profile endpoints
│   ├── tour.py            # Tour session and guided-visit endpoints
│   └── admin/             # Admin-only router namespace
│       ├── exhibits.py    # Admin exhibit management
│       └── prompts.py     # Admin prompt template management
├── application/            # Business logic and services
│   ├── auth_service.py    # User registration/login
│   ├── chat_service.py    # Chat message handling, SSE streaming
│   ├── chat_message_service.py  # Chat message CRUD
│   ├── chat_session_service.py  # Chat session CRUD
│   ├── chat_stream_service.py   # RAG streaming orchestration
│   ├── document_service.py # Document CRUD
│   ├── ingestion_service.py # Document chunking and embedding
│   ├── unified_indexing_service.py # Unified ES indexing pipeline
│   ├── exhibit_service.py  # Exhibit CRUD
│   ├── exhibit_indexing_service.py # Exhibit ES indexing
│   ├── content_source.py   # Content source abstraction
│   ├── curator_service.py  # Curator AI agent orchestration
│   ├── profile_service.py  # Visitor profile CRUD
│   ├── prompt_service.py   # Prompt template CRUD
│   ├── prompt_service_adapter.py # Prompt service adapter
│   ├── tour_chat_service.py # Tour chat streaming
│   ├── tour_session_service.py # Tour session CRUD
│   ├── tour_event_service.py  # Tour event recording
│   ├── tour_report_service.py # Tour report generation
│   ├── chunking.py        # Text chunking algorithms
│   ├── context_manager.py # Context window management
│   ├── error_handling.py  # Centralized error handling
│   ├── sse_events.py      # SSE event type definitions
│   ├── ports/             # Port interfaces (dependency inversion)
│   └── workflows/         # Multi-turn conversation workflows
│       ├── multi_turn.py  # State machine for retrieval evaluation
│       ├── query_transform.py # Query transformation (HyDE, step-back)
│       └── reflection_prompts.py # Reflection prompt templates
├── domain/                 # Domain entities and value objects
│   ├── entities.py        # User, ChatSession, Document, IngestionJob, Exhibit, TourSession, etc.
│   ├── value_objects.py   # Typed IDs (UserId, SessionId, ExhibitId, TourSessionId, etc.)
│   ├── exceptions.py      # Domain-specific exceptions
│   └── services/          # Domain services
│       └── retrieval.py   # RRF fusion algorithm
├── infra/                  # Infrastructure layer
│   ├── postgres/          # Database models and session management
│   │   ├── models.py      # SQLAlchemy ORM models (13 classes)
│   │   └── database.py    # Engine lifecycle, session factory
│   ├── elasticsearch/     # ES client for vector/BM25 search
│   ├── redis/             # Caching and token blacklist
│   ├── langchain/         # LangChain integrations
│   │   ├── embeddings.py  # Custom Ollama embeddings
│   │   ├── retrievers.py  # RRF retriever implementation
│   │   ├── agents.py      # RAG agent with LangGraph state machine
│   │   ├── curator_agent.py # Curator agent with LangGraph
│   │   ├── curator_tools.py # Curator tool definitions (path planning, narrative, etc.)
│   │   └── tools.py       # Shared tool utilities
│   ├── providers/         # External service providers
│   │   ├── llm.py         # OpenAI-compatible LLM provider
│   │   ├── embedding.py   # Embedding provider abstraction
│   │   └── rerank.py      # Rerank provider (Dashscope, Local, Noop)
│   └── security/          # JWT handling, password hashing
├── config/                 # Configuration management
│   └── settings.py        # Pydantic settings with validation
└── main.py                 # FastAPI app and global singletons
```

### Key Architectural Patterns

1. **Dependency Injection**: FastAPI's `Depends()` for session management, authentication, and rate limiting. See `api/deps.py` for the dependency chain.

2. **Global Singletons**: `main.py` manages global instances (ES client, LLM, embeddings, retriever, RAG agent) with lazy initialization.

3. **RRF Fusion Retrieval**: Combines dense (vector) and sparse (BM25) search using Reciprocal Rank Fusion. See `domain/services/retrieval.py` and `infra/langchain/retrievers.py`.

4. **RAG Agent with LangGraph**: State machine that evaluates retrieval quality and can transform queries if scores are low. See `infra/langchain/agents.py`.

5. **SSE Streaming**: Chat responses stream via Server-Sent Events with structured event types (`thinking`, `chunk`, `done`, `error`).

### Database Schema

PostgreSQL tables:
- `users`: id, email, password_hash, role, created_at
- `documents`: id, user_id, filename, status, error, created_at
- `ingestion_jobs`: id, document_id, status, chunk_count, error, created_at, updated_at
- `chat_sessions`: id, user_id, title, created_at
- `chat_messages`: id, session_id, role, content, trace_id, created_at
- `exhibits`: id, name, description, location_x/y, floor, hall, category, era, importance, estimated_visit_time, document_id, is_active, display_order, created_at, updated_at
- `visitor_profiles`: id, user_id, interests, knowledge_level, narrative_preference, reflection_depth, visited_exhibit_ids, feedback_history, created_at, updated_at
- `tour_paths`: id, name, description, theme, estimated_duration, exhibit_ids, is_active, created_by, created_at, updated_at
- `tour_sessions`: id, user_id, guest_id, session_token, interest_type, persona, assumption, current_hall, current_exhibit_id, visited_halls, visited_exhibit_ids, status, last_active_at, started_at, completed_at, created_at
- `tour_events`: id, tour_session_id, event_type, exhibit_id, hall, duration_seconds, metadata, created_at
- `tour_reports`: id, tour_session_id, total_duration_minutes, most_viewed_exhibit_id, most_viewed_exhibit_duration, longest_hall, longest_hall_duration, total_questions, total_exhibits_viewed, ceramic_questions, identity_tags, radar_scores, one_liner, report_theme, created_at
- `prompts`: id, key, name, description, category, content, variables, is_active, created_at, updated_at
- `prompt_versions`: id, prompt_id, version, content, changed_by, change_reason, created_at

### Elasticsearch Index

Index `museai_chunks_v1` with:
- `chunk_id` (keyword), `document_id` (keyword)
- `content` (text with ik_max_word analyzer)
- `content_vector` (dense_vector, configurable dims)
- `chunk_level`, `source` fields

## Configuration

Environment variables (see `.env.example` for full reference):

### Core
- `APP_NAME`: str, default `"MuseAI"` — Application display name
- `APP_ENV`: str, default `"development"` — One of: development, test, local, production
- `DEBUG`: bool, default `False` — Enable debug mode

### Auth
- `JWT_SECRET`: str, default `""` — **Required in production** (≥32 chars)
- `JWT_ALGORITHM`: str, default `"HS256"` — JWT signing algorithm
- `JWT_EXPIRE_MINUTES`: int, default `60` — Token lifetime in minutes
- `ADMIN_EMAILS`: str, default `""` — Comma-separated admin emails

### Database
- `DATABASE_URL`: str, default `"sqlite+aiosqlite:///:memory:"` — PostgreSQL connection string

### Elasticsearch
- `ELASTICSEARCH_URL`: str, default `"http://localhost:9200"` — ES endpoint
- `ELASTICSEARCH_INDEX`: str, default `"museai_chunks_v1"` — ES index name
- `EMBEDDING_DIMS`: int, default `768` — Vector dimensionality (1–4096)

### Redis
- `REDIS_URL`: str, default `"redis://localhost:6379"` — Redis endpoint

### LLM
- `LLM_PROVIDER`: str, default `"openai"` — LLM provider name
- `LLM_BASE_URL`: str, default `"https://api.openai.com/v1"` — LLM API base URL
- `LLM_API_KEY`: str, default `""` — **Required in production**
- `LLM_MODEL`: str, default `"gpt-4o-mini"` — Model identifier

### Embedding
- `EMBEDDING_PROVIDER`: str, default `"ollama"` — Embedding provider
- `EMBEDDING_OLLAMA_BASE_URL`: str, default `"http://localhost:11434"` — Ollama endpoint
- `EMBEDDING_OLLAMA_MODEL`: str, default `"nomic-embed-text"` — Ollama model name

### Rerank
- `RERANK_PROVIDER`: str, default `"openai"` — Rerank provider (openai, cohere, custom)
- `RERANK_BASE_URL`: str, default `""` — Rerank API base URL
- `RERANK_API_KEY`: str, default `""` — **Required in production when RERANK_PROVIDER is set**
- `RERANK_MODEL`: str, default `"rerank-v1"` — Rerank model identifier
- `RERANK_TOP_N`: int, default `5` — Number of results to return

### Logging
- `LOG_LEVEL`: str, default `"INFO"` — One of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `LOG_DIR`: str, default `"logs"` — Log file directory
- `LOG_FORMAT`: str, default `"json"` — Log format ("json" or "text")

### Rate Limiting
- `RATE_LIMIT_ENABLED`: bool, default `True` — Enable/disable rate limiting

### Security
- `ALLOW_INSECURE_DEV_DEFAULTS`: bool, default `False` — Allow dev secrets in non-production environments
- `TRUSTED_PROXIES`: str, default `""` — Comma-separated trusted proxy IPs for X-Forwarded-For

### CORS
- `CORS_ORIGINS`: str, default `"http://localhost:3000"` — Comma-separated origins or `"*"` (wildcard forbidden in production)
- `CORS_ALLOW_CREDENTIALS`: bool, default `True` — Allow credentials in CORS

Production requires `JWT_SECRET` (≥32 chars), `LLM_API_KEY`, and `RERANK_API_KEY` (when rerank is configured).

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

### Database migrations (Alembic)

The project uses Alembic for schema migrations. Configuration is in `alembic.ini` and `backend/alembic/env.py`.

```bash
# Generate a migration after model changes
alembic revision --autogenerate -m "add_new_table"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration state
alembic current
```

Guidelines:
- Always review auto-generated migrations before applying — Alembic may miss column renames or detect false changes
- Never edit applied migrations — create a new revision instead
- Test migrations against a clean database before deploying: `alembic upgrade head` from scratch
- Include `backfill` logic in the migration for data transformations, not in application code
