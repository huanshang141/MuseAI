# MuseAI Backend

MuseAI backend is the FastAPI service for the Banpo Museum WeChat mini-program. It provides tour sessions, SSE guide chat, exhibit browsing, report generation, curator route planning, admin content management, RAG retrieval, LLM tracing, and optional TTS.

Current product stage: Stage 10C. The mini-program is the primary delivery target. The production server target is Tencent Cloud 2 CPU cores / 4 GB RAM, so backend changes should avoid unnecessary model calls and heavy background services.

## Current Status

Implemented and active:

- WeChat mini-program visitor tour flow.
- Guest tour sessions with session token support.
- SSE streaming guide answers for `/api/v1/tour/sessions/{id}/chat/stream`.
- Tour events, hall visits, and report generation.
- Four guide personas:
  - `A` Archaeology Researcher
  - `B` Study Tour Recorder
  - `C` History Inquirer
  - `D` Artifact Researcher
- Banpo hall slug normalization and compatibility aliases.
- Public exhibit browsing and search.
- Admin APIs for exhibits, halls, documents, prompts, LLM traces, and TTS personas.
- RAG pipeline with query rewrite, Elasticsearch retrieval, rerank, document filtering, and streaming generation.
- DeepSeek thinking disabled by default through `LLM_ENABLE_THINKING=false`.
- LLM model tiering:
  - `LLM_TOUR_MODEL=deepseek-v4-flash` for guide chat and normal tour work.
  - `LLM_REPORT_MODEL=deepseek-v4-pro` for report summaries.
  - `LLM_MODEL` retained as fallback compatibility.
- Lightweight count queries for exhibit list/search totals.
- Degraded startup mode for Redis or Elasticsearch failure.

Retained but not currently emphasized in the mini-program UX:

- `/api/v1/curator/plan-tour` structured route API.
- General chat APIs.
- Document upload and ingestion APIs.
- TTS synthesis API.

Not production-complete yet:

- Camera-based exhibit recognition.
- Voice input.
- End-to-end TTS playback in the mini-program.
- Official museum map and exhibit-position data.
- Full authorized exhibit images and complete museum-owned exhibit catalogue.

## Tech Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Pydantic v2 |
| Runtime | Python 3.11+, uv, Uvicorn |
| Database | PostgreSQL 16 via SQLAlchemy async |
| Cache | Redis 7 |
| Search | Elasticsearch 8 with IK analyzer image |
| RAG | LangChain, LangGraph, custom retriever/filtering |
| LLM | OpenAI-compatible provider, currently DeepSeek-compatible config |
| Rerank | SiliconFlow/OpenAI/Cohere/custom/mock |
| TTS | Xiaomi MiMo or mock provider, optional |
| Tests | pytest, pytest-asyncio |

## Directory Layout

```text
backend/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routers
│   │   │   ├── admin/              # Admin content, prompt, trace, TTS APIs
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── curator.py
│   │   │   ├── documents.py
│   │   │   ├── exhibits.py
│   │   │   ├── health.py
│   │   │   ├── profile.py
│   │   │   ├── tour.py
│   │   │   └── tts.py
│   │   ├── application/            # Use cases and service layer
│   │   ├── config/                 # Settings and environment validation
│   │   ├── domain/                 # Domain entities and errors
│   │   ├── infra/                  # PostgreSQL, Redis, ES, providers, LangChain
│   │   ├── observability/          # Logging and request middleware
│   │   └── main.py                 # FastAPI app entrypoint
│   ├── alembic/                    # Database migrations
│   └── tests/                      # Unit, contract, e2e tests
├── deploy/
│   └── nginx.conf                  # HTTPS/SSE reverse proxy template
├── docker/
│   └── elasticsearch/              # ES image with analyzer support
├── docs/
│   ├── reference/展品.md            # Banpo exhibit import source
│   └── *.md                        # Audit, latency, and handoff docs
├── scripts/
│   ├── init_db.py
│   ├── seed_prompts_and_personas.py
│   ├── import_real_exhibits_via_api.py
│   └── ...
├── .env.example
├── CONFIGURATION.md
├── docker-compose.yml              # PostgreSQL, Redis, Elasticsearch only
├── pyproject.toml
└── uv.lock
```

## API Surface

All application routes are mounted under `/api/v1`.

| Area | Endpoint Examples | Purpose |
| --- | --- | --- |
| Health | `GET /health`, `GET /ready` | Service and dependency checks |
| Auth | `POST /auth/register`, `POST /auth/login` | User/admin authentication |
| Tour | `POST /tour/sessions`, `POST /tour/sessions/{id}/chat/stream` | Mini-program tour session and SSE guide chat |
| Tour report | `POST /tour/sessions/{id}/report`, `GET /tour/sessions/{id}/report` | Generate or fetch visit report |
| Exhibits | `GET /exhibits`, `GET /exhibits/{id}` | Public exhibit browsing/search |
| Curator | `POST /curator/plan-tour`, `/narrative`, `/reflection` | Structured route and exhibit-level AI helpers |
| TTS | `POST /tts/synthesize` | Optional TTS synthesis |
| Admin | `/admin/exhibits`, `/admin/halls`, `/admin/prompts`, `/admin/documents`, `/admin/llm-traces`, `/admin/tts/personas` | Content and operations management |

## Configuration

Runtime config is loaded from `backend/.env` by `backend/app/config/settings.py`. Do not commit real `.env` files.

Important fields:

| Field | Current Meaning |
| --- | --- |
| `APP_ENV` | `development`, `test`, `local`, or `production` |
| `DEBUG` | Keep `false` in production |
| `ALLOW_INSECURE_DEV_DEFAULTS` | Local-only escape hatch; keep `false` in production |
| `DATABASE_URL` | PostgreSQL async URL |
| `REDIS_URL` | Redis URL |
| `ELASTICSEARCH_URL` | Elasticsearch endpoint |
| `JWT_SECRET` | Required and at least 32 chars in production |
| `LLM_BASE_URL` | OpenAI-compatible LLM base URL |
| `LLM_API_KEY` | Required unless explicitly using insecure local defaults |
| `LLM_MODEL` | Backward-compatible fallback model |
| `LLM_TOUR_MODEL` | Default model for guide chat and normal tour generation |
| `LLM_REPORT_MODEL` | Stronger model for report summaries |
| `LLM_ENABLE_THINKING` | `false` sends `thinking.disabled` to supported models |
| `LLM_HEADERS` | Optional JSON string for extra upstream headers |
| `RERANK_PROVIDER` | `siliconflow`, `openai`, `cohere`, `custom`, or `mock` |
| `TTS_ENABLED` | Optional; leave `false` until mini-program voice playback is complete |
| `CORS_ORIGINS` | Must not be wildcard in production |
| `TRUSTED_PROXIES` | Set only to trusted reverse proxy IPs, e.g. `127.0.0.1` behind local Nginx |

See `CONFIGURATION.md` and the root `后端配置文档.md` for operational procedures.

## Local Setup

```bash
cd backend

# 1. Create local config
cp .env.example .env

# 2. Install Python dependencies
uv sync

# 3. Start infrastructure
docker compose up -d

# 4. Initialize database schema and ES index
uv run python scripts/init_db.py --init-es

# 5. Seed prompts, personas, and halls
uv run python scripts/seed_prompts_and_personas.py

# 6. Start API in development mode
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health checks:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/ready
```

## Data Import

The current Banpo exhibit import path is:

```bash
cd backend
uv run python scripts/import_real_exhibits_via_api.py \
  --base-url http://127.0.0.1:8000/api/v1 \
  --email <admin-email> \
  --password '<admin-password>'
```

Important: this script clears existing exhibits/documents/halls before importing from `docs/reference/展品.md`. Use it only when you intentionally want to reset imported content.

## Tests

Common checks:

```bash
cd backend

py -3 -m compileall -q backend scripts backend/tests
uv run --extra dev pytest -q
```

Focused checks:

```bash
uv run --extra dev pytest backend/tests/contract/test_tour_api.py -q
uv run --extra dev pytest backend/tests/contract/test_exhibits_api.py -q
uv run --extra dev pytest backend/tests/unit/test_tour_chat.py -q
uv run --extra dev pytest backend/tests/unit/test_llm_provider.py backend/tests/unit/test_config.py -q
```

Recent verified baseline from the change summary:

```text
996 passed, 23 skipped, 12 warnings
```

If Windows local pytest hits a temp-directory permission error, set `TMP` and `TEMP` to a project-local temporary directory before running pytest.

## Production Deployment Notes

The current `docker-compose.yml` starts PostgreSQL, Redis, and Elasticsearch only. It does not run the FastAPI service. Recommended production shape for the current 2C/4G server:

1. `docker compose up -d` for infrastructure.
2. Run migrations and seed scripts.
3. Start FastAPI through `systemd` with `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1`.
4. Use Nginx or BT reverse proxy on HTTPS domain, forwarding `/api/` to `127.0.0.1:8000`.
5. Disable public exposure of PostgreSQL, Redis, Elasticsearch, and port 8000.
6. Configure WeChat mini-program request domain to the HTTPS API domain.

For SSE, proxy buffering must be off and read timeouts should be long enough for streaming responses.

## Operational Rules

- Never commit `backend/.env`.
- Keep `.env.example`, `settings.py`, `CONFIGURATION.md`, `README.md`, `README_CN.md`, and root `后端配置文档.md` synchronized when config changes.
- Keep ordinary guide chat on `LLM_TOUR_MODEL`; reserve `LLM_REPORT_MODEL` for report/research-like generation.
- Do not reintroduce duplicate LLM calls into tour chat.
- Keep new backend features within the 2C/4G production budget.
- Hide or disable unfinished camera/OCR/voice features until backend, frontend, privacy, and WeChat review requirements are complete.
