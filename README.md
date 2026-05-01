# MuseAI

Museum AI Guide System - An intelligent museum content interaction platform powered by RAG (Retrieval-Augmented Generation).

[中文文档](README_CN.md)

## Features

- **Intelligent Q&A**: RAG-based question answering with contextual retrieval from museum knowledge base
- **Hybrid Search**: Combines dense vector search and BM25 keyword search using Reciprocal Rank Fusion (RRF) with source deduplication
- **Multi-turn Conversation**: Stateful conversations with query transformation strategies (HyDE, Step-back, Multi-query) and dynamic document filtering
- **Document Ingestion**: Automatic hierarchical document chunking (parent-child) and embedding with Elasticsearch indexing
- **Streaming Responses**: Real-time SSE (Server-Sent Events) streaming with optional TTS audio events
- **User Authentication**: JWT-based authentication with rate limiting and token blacklisting
- **Tour System**: Guided museum tours with session management, hall tracking, event recording, and post-visit reports
- **Curator AI Agent**: AI-powered tour planning, exhibit narrative generation, and reflection prompts via LangGraph
- **Text-to-Speech**: Sentence-level TTS streaming with persona management, Redis caching, and multiple provider support (Xiaomi, Mock)
- **Visitor Profiles**: Personalized visitor profiles with interests, knowledge level, and narrative preferences
- **Admin Panel**: Full admin interface for exhibits, halls, documents, prompts, TTS personas, and LLM trace auditing
- **Design System**: Museum-themed design tokens and components built on Element Plus
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
- **Migrations**: Alembic

### Frontend
- **Framework**: Vue 3 with Composition API
- **UI Library**: Element Plus (with museum design system)
- **Build Tool**: Vite
- **Routing**: Vue Router
- **Composables**: Reusable hooks for auth, chat, tour, TTS, exhibits, etc.

### Infrastructure
- **Database**: PostgreSQL 16
- **Search Engine**: Elasticsearch 8.x with IK analyzer
- **Cache**: Redis 7
- **LLM**: OpenAI-compatible providers (GPT-4o-mini)
- **Embeddings**: Ollama (nomic-embed-text)
- **Rerank**: OpenAI-compatible or SiliconFlow rerank providers
- **TTS**: Xiaomi TTS provider (with Redis caching)

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

### 5. Initialize Database

```bash
# Run database migrations (creates table schema)
python scripts/init_db.py

# Create an admin user
python scripts/init_db.py --admin-email admin@museai.local --admin-password YourPassword123
```

> See [Database Initialization](#database-initialization) below for detailed instructions.

### 6. Run Backend Server

```bash
uv run uvicorn backend.app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 7. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 8. Run Frontend Development Server

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
| `/api/v1/chat/guest/message` | POST | Send guest message (SSE) |
| `/api/v1/exhibits` | GET | Browse exhibits (public) |
| `/api/v1/exhibits/{id}` | GET | Get exhibit detail |
| `/api/v1/profile` | GET/PUT | Get/update visitor profile |
| `/api/v1/tour/sessions` | POST | Create tour session |
| `/api/v1/tour/sessions/{id}/chat/stream` | POST | Stream tour chat (SSE) |
| `/api/v1/tour/sessions/{id}/report` | GET/POST | Generate/get tour report |
| `/api/v1/curator/plan-tour` | POST | Plan museum tour (AI) |
| `/api/v1/curator/narrative` | POST | Generate exhibit narrative (AI) |
| `/api/v1/tts/synthesize` | POST | Synthesize speech from text |
| `/api/v1/admin/exhibits` | GET/POST | Admin exhibit management |
| `/api/v1/admin/halls` | GET/POST | Admin hall management |
| `/api/v1/admin/prompts` | GET | Admin prompt management |
| `/api/v1/admin/documents` | GET/POST | Admin document management |
| `/api/v1/admin/llm-traces` | GET | View LLM call traces |
| `/api/v1/admin/tts/personas` | GET/PUT | Manage TTS personas |
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
| `RERANK_PROVIDER` | Rerank provider (openai, cohere, custom) | `openai` |
| `RERANK_MODEL` | Rerank model identifier | `rerank-v1` |
| `RERANK_TOP_N` | Number of rerank results | `10` |
| `TTS_ENABLED` | Enable text-to-speech | `false` |
| `TTS_PROVIDER` | TTS provider (xiaomi, mock) | `xiaomi` |
| `TTS_DEFAULT_VOICE` | Default TTS voice/persona | `冰糖` |

## Database Initialization

The project uses Alembic for database schema migrations. The app also auto-creates missing tables on startup, but using migrations is recommended to ensure correct schema versioning.

### Initialization Script

`scripts/init_db.py` is the unified initialization entry point covering PostgreSQL migrations, Elasticsearch index creation, and service connectivity checks:

```bash
# Run migrations + ES index creation + service checks
python scripts/init_db.py

# Run migrations + create admin user
python scripts/init_db.py --admin-email admin@museai.local --admin-password YourPassword123

# Full init: migrations + ES index + admin + dev test data
python scripts/init_db.py --admin-email admin@museai.local --admin-password YourPassword123 --seed-dev

# Only run PostgreSQL migrations
python scripts/init_db.py --schema-only

# Only create ES index (idempotent, skips if exists)
python scripts/init_db.py --init-es
```

### Production Deployment

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Configure environment
cp .env.example .env
# Edit .env: set JWT_SECRET, LLM_API_KEY, etc.

# 3. Install dependencies
uv sync

# 4. Initialize all services (DB migrations + ES index + admin)
python scripts/init_db.py --init-es --admin-email admin@museum.cn --admin-password 'YourStr0ngPass!'

# 5. Start the service
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### Local Development

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Configure environment
cp .env.example .env
# Edit .env: ensure DATABASE_URL points to local PostgreSQL

# 3. Install dependencies
uv sync

# 4. Full init: DB migrations + ES index + admin + test data
python scripts/init_db.py --admin-email admin@museai.local --admin-password dev12345678 --seed-dev

# 5. Start backend
uv run uvicorn backend.app.main:app --reload

# 6. Start frontend
cd frontend && npm install && npm run dev
```

### Manual Alembic Commands

```bash
# Check current migration status
uv run alembic current

# Upgrade to latest
uv run alembic upgrade head

# Rollback one version
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

### Seed Data Scripts

The following standalone seed scripts are available in `scripts/`:

| Script | Purpose | Required Services |
|--------|---------|-------------------|
| `seed_dev_user.py` | Create a dev test user | PostgreSQL |
| `bootstrap_admin.py` | Create/promote admin user | PostgreSQL |
| `init_exhibits.py` | Seed 70+ exhibits (bronze, ceramics, calligraphy, etc.) | PostgreSQL, Elasticsearch, Ollama |
| `init_test_data.py` | Full test data (users, documents, chat sessions) | PostgreSQL, Elasticsearch, Ollama |
| `import_real_exhibits_via_api.py` | Import exhibits via REST API | Full backend running |
| `cleanup_llm_traces.py` | Clean up expired LLM trace records | PostgreSQL |

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
│   │   │   ├── curator.py      # Curator AI agent endpoints
│   │   │   ├── documents.py    # Document management
│   │   │   ├── exhibits.py     # Exhibit browsing
│   │   │   ├── health.py       # Health checks
│   │   │   ├── profile.py      # Visitor profile
│   │   │   ├── tour.py         # Tour session management
│   │   │   ├── tts.py          # TTS synthesis
│   │   │   └── admin/          # Admin routers
│   │   │       ├── documents.py
│   │   │       ├── exhibits.py
│   │   │       ├── halls.py
│   │   │       ├── llm_traces.py
│   │   │       ├── prompts.py
│   │   │       └── tts_persona.py
│   │   ├── application/         # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── curator_service.py
│   │   │   ├── document_service.py
│   │   │   ├── ingestion_service.py
│   │   │   ├── tour_*_service.py
│   │   │   ├── tts_service.py
│   │   │   ├── llm_trace/      # LLM call tracing
│   │   │   └── workflows/      # Multi-turn state machine
│   │   ├── domain/              # Domain entities
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   └── services/       # RRF fusion
│   │   ├── infra/              # Infrastructure
│   │   │   ├── postgres/
│   │   │   ├── elasticsearch/
│   │   │   ├── redis/
│   │   │   ├── cache/          # Prompt cache
│   │   │   ├── langchain/      # RAG agent, retrievers, curator agent
│   │   │   ├── providers/      # LLM, embedding, rerank, TTS providers
│   │   │   └── security/
│   │   └── main.py
│   └── tests/
│       ├── unit/
│       ├── contract/
│       └── e2e/
├── frontend/
│   ├── src/
│   │   ├── api/               # API client
│   │   ├── components/        # Vue components (chat, tour, exhibits, admin, etc.)
│   │   ├── composables/       # Vue composables (useAuth, useChat, useTour, useTTSPlayer, etc.)
│   │   ├── design-system/     # Museum design tokens and components
│   │   ├── views/             # Page views (Home, Tour, Curator, Exhibits, Admin, etc.)
│   │   ├── router/            # Vue Router configuration
│   │   ├── styles/            # Global styles
│   │   └── main.js
│   └── package.json
├── scripts/                   # Utility scripts (seed, init, cleanup)
├── docker/
├── docs/
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## RAG Pipeline

1. **Query Processing**: User query enters through chat endpoint
2. **Retrieval**: Dense vector search + BM25 keyword search in parallel
3. **Fusion**: Reciprocal Rank Fusion (RRF) combines results with source deduplication
4. **Rerank**: Rerank provider scores and filters results
5. **Dynamic Filtering**: Absolute/relative gap strategies filter low-quality results
6. **Chunk Merge**: Parent chunks promoted when child chunks are retrieved (hierarchical)
7. **Evaluation**: Score threshold check for retrieval quality
8. **Query Transformation** (if needed): HyDE, Step-back, or Multi-query
9. **Generation**: LLM generates answer with retrieved context
10. **Streaming**: Response streamed via SSE (with optional TTS audio events)

## License

MIT License
