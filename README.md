# MuseAI

Museum AI Guide System - An intelligent museum content interaction platform powered by RAG (Retrieval-Augmented Generation).

[中文文档](README_CN.md)

## Features

- **Intelligent Q&A**: RAG-based question answering with contextual retrieval from museum knowledge base
- **Hybrid Search**: Combines dense vector search and BM25 keyword search using Reciprocal Rank Fusion (RRF)
- **Multi-turn Conversation**: Stateful conversations with query transformation strategies (HyDE, Step-back, Multi-query)
- **Document Ingestion**: Automatic document chunking and embedding with hierarchical structure support
- **Streaming Responses**: Real-time SSE (Server-Sent Events) streaming for better user experience
- **User Authentication**: JWT-based authentication with rate limiting and token blacklisting
- **Health Monitoring**: Built-in health check endpoints for service observability

## Architecture

MuseAI follows a strict layered architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                      │
├─────────────────────────────────────────────────────────┤
│                    API Layer (FastAPI)                   │
├─────────────────────────────────────────────────────────┤
│                  Application Layer                       │
│         (Auth, Chat, Document, Ingestion Services)       │
├─────────────────────────────────────────────────────────┤
│                    Domain Layer                          │
│              (Entities, Value Objects)                   │
├─────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                     │
│      (PostgreSQL, Elasticsearch, Redis, LLM)            │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

### Backend
- **Framework**: FastAPI with async support
- **ORM**: SQLAlchemy 2.0 (async)
- **Validation**: Pydantic v2
- **AI/ML**: LangChain, LangGraph, OpenAI-compatible LLMs

### Frontend
- **Framework**: Vue 3 with Composition API
- **UI Library**: Element Plus
- **Build Tool**: Vite

### Infrastructure
- **Database**: PostgreSQL 16
- **Search Engine**: Elasticsearch 8.x with IK analyzer
- **Cache**: Redis 7
- **LLM**: OpenAI-compatible providers (GPT-4o-mini)
- **Embeddings**: Ollama (nomic-embed-text)

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- uv (Python package manager)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/museai.git
cd museai
```

### 2. Start Infrastructure Services

```bash
docker-compose up -d
```

This starts PostgreSQL, Elasticsearch, and Redis.

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration. Required settings:

```env
# LLM Configuration (required in production)
LLM_API_KEY=your-openai-api-key

# JWT Secret (must be ≥32 characters in production)
JWT_SECRET=your-secure-jwt-secret-key-here
```

### 4. Install Backend Dependencies

```bash
uv sync
```

### 5. Run Backend Server

```bash
uv run uvicorn backend.app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 6. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 7. Run Frontend Development Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.

## API Documentation

Once the backend is running, access the interactive API documentation:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register new user |
| `/api/v1/auth/login` | POST | Login and get JWT token |
| `/api/v1/auth/logout` | POST | Logout (blacklist token) |
| `/api/v1/documents/upload` | POST | Upload document for ingestion |
| `/api/v1/documents` | GET | List user's documents |
| `/api/v1/chat/sessions` | GET/POST | Manage chat sessions |
| `/api/v1/chat/ask` | POST | Ask question (non-streaming) |
| `/api/v1/chat/ask/stream` | POST | Ask question (SSE streaming) |
| `/api/v1/health` | GET | Health check |
| `/api/v1/ready` | GET | Readiness check |

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/production) | `development` |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `ELASTICSEARCH_URL` | Elasticsearch endpoint | Required |
| `JWT_SECRET` | JWT signing secret (≥32 chars in prod) | Required |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `JWT_EXPIRE_MINUTES` | Token expiration time | `1440` |
| `LLM_PROVIDER` | LLM provider | `openai` |
| `LLM_BASE_URL` | LLM API base URL | `https://api.openai.com/v1` |
| `LLM_API_KEY` | LLM API key | Required |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `EMBEDDING_PROVIDER` | Embedding provider | `ollama` |
| `EMBEDDING_OLLAMA_BASE_URL` | Ollama base URL | `http://localhost:11434` |
| `EMBEDDING_OLLAMA_MODEL` | Embedding model | `nomic-embed-text` |
| `ELASTICSEARCH_INDEX` | ES index name | `museai_chunks_v1` |
| `EMBEDDING_DIMS` | Embedding dimensions | `1536` |

## Development

### One-command local verification

```bash
bash scripts/verify_local_quality.sh
```

### Run Tests

```bash
# Unit and contract tests
uv run pytest backend/tests/unit backend/tests/contract -v

# Single test file
uv run pytest backend/tests/unit/test_domain_entities.py -v

# E2E tests (requires running infrastructure)
uv run pytest backend/tests/e2e -v
```

### Code Quality

```bash
# Linting
uv run ruff check backend/

# Type checking
uv run mypy backend/
```

### Frontend Development

```bash
cd frontend

# Development server
npm run dev

# Production build
npm run build
```

## Project Structure

```
museai/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI routers
│   │   │   ├── auth.py         # Authentication endpoints
│   │   │   ├── chat.py         # Chat endpoints
│   │   │   ├── documents.py    # Document management
│   │   │   └── health.py       # Health checks
│   │   ├── application/         # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── document_service.py
│   │   │   ├── ingestion_service.py
│   │   │   └── retrieval.py    # RRF fusion
│   │   ├── domain/             # Domain entities
│   │   │   ├── entities.py
│   │   │   └── value_objects.py
│   │   ├── infra/              # Infrastructure
│   │   │   ├── postgres/
│   │   │   ├── elasticsearch/
│   │   │   ├── redis/
│   │   │   ├── langchain/      # RAG agent, retrievers
│   │   │   ├── providers/      # LLM, embedding providers
│   │   │   └── security/
│   │   ├── workflows/          # Multi-turn state machine
│   │   └── main.py
│   └── tests/
│       ├── unit/
│       ├── contract/
│       └── e2e/
├── frontend/
│   ├── src/
│   │   ├── api/               # API client
│   │   ├── components/        # Vue components
│   │   ├── composables/       # Vue composables
│   │   └── main.js
│   └── package.json
├── docker/
├── docs/
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## RAG Pipeline

1. **Query Processing**: User query enters through chat endpoint
2. **Retrieval**: Dense vector search + BM25 keyword search in parallel
3. **Fusion**: Reciprocal Rank Fusion (RRF) combines results
4. **Evaluation**: Score threshold check for retrieval quality
5. **Query Transformation** (if needed): HyDE, Step-back, or Multi-query
6. **Generation**: LLM generates answer with retrieved context
7. **Streaming**: Response streamed via SSE

## License

MIT License
