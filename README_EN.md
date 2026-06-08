# MuseAI Backend

Chinese version: [README.md](./README.md)

MuseAI backend is the FastAPI service for the Banpo Museum WeChat mini-program. It provides tour sessions, SSE streaming answers, hall and exhibit data, AI-curated routes, visit reports, the Reflection Engine, RAG retrieval, LLM calls, and TTS synthesis.

## Current Stage

The backend is currently in **Stage 13: pre-launch closed-loop validation and release preparation**. The core mini-program experience is supported, but formal release still depends on filing, WeChat legal-domain approval, real-device testing, and production process management.


## Implemented Capabilities

- Guest tour sessions with `X-Session-Token`.
- SSE guide chat at `/api/v1/tour/sessions/{id}/chat/stream`.
- Four guide personas:
  - `A` Archaeology Researcher
  - `B` Study Tour Recorder
  - `C` History Inquirer
  - `D` Artifact Researcher
- Three-step onboarding context: focus, assumption, and guide mode.
- Canonical hall slug normalization, Chinese display names, and legacy alias compatibility.
- Event tracking for hall enter, exhibit view, questions, and deep dives.
- AI curator route API: `/api/v1/curator/plan-tour`.
- Exhibit listing, detail lookup, hall filtering, and text search.
- Visit report generation: visited halls, reflection, record summary, and basic stats.
- Reflection Engine without new database tables, new APIs, or new model calls.
- RAG pipeline with query rewrite, Elasticsearch retrieval, rerank, document filtering, and streaming generation.
- LLM model tiers:
  - `LLM_TOUR_MODEL` for normal guide chat.
  - `LLM_REPORT_MODEL` for report summaries.
  - `LLM_MODEL` as compatibility fallback.
- OpenAI-compatible DeepSeek/Qwen calling:
  - DeepSeek thinking can be disabled.
  - Qwen/DashScope thinking can be disabled.
- Structured `conversation_history` for guide chat, improving follow-up relevance.
- Degraded startup if Redis or Elasticsearch is unavailable.
- TTS synthesis API at `/api/v1/tts/synthesize`, currently defaulting to the "冰糖" voice and returning audio data playable by the mini-program.

## Not Complete Or Still Needs Real-Device Validation

- Formal WeChat mini-program filing and request legal-domain approval.
- `api.banpo-museai.xyz` has DNS/SSL/Nginx setup, but may be blocked in real WeChat devices before filing is accepted.
- OCR recognition is currently handled mainly by the mini-program side with exhibit text matching fallback; no backend OCR API was added.
- Official museum exhibit catalogue, images, map, positions, and spatial layout still need confirmation.
- Production process management, log rotation, and database backup must be finalized.

## Tech Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Pydantic v2 |
| Runtime | Python 3.11+, uv, Uvicorn |
| Database | PostgreSQL / SQLAlchemy async |
| Cache | Redis |
| Search | Elasticsearch |
| RAG | LangChain, LangGraph, custom retriever/filtering |
| LLM | OpenAI-compatible provider |
| Rerank | SiliconFlow / OpenAI / Cohere / custom / mock |
| TTS | Xiaomi MiMo or mock provider |
| Tests | pytest, pytest-asyncio |

## Directory Layout

```text
backend/
├── backend/app/
│   ├── api/                 # FastAPI routers
│   ├── application/         # Application services and orchestration
│   ├── config/              # Settings and environment validation
│   ├── domain/              # Domain entities and exceptions
│   ├── infra/               # LLM/RAG/database/external adapters
│   ├── observability/       # Logging and tracing context
│   └── main.py              # FastAPI app entrypoint
├── backend/tests/
├── scripts/
├── docs/
├── docker/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── README.md
└── README_EN.md
```

## Key APIs

| Feature | Method and path |
| --- | --- |
| Health check | `GET /api/v1/health` |
| Create tour session | `POST /api/v1/tour/sessions` |
| Update tour session | `PATCH /api/v1/tour/sessions/{session_id}` |
| Stream guide answer | `POST /api/v1/tour/sessions/{session_id}/chat/stream` |
| Append tour events | `POST /api/v1/tour/sessions/{session_id}/events` |
| Generate report | `POST /api/v1/tour/sessions/{session_id}/report` |
| Curator route | `POST /api/v1/curator/plan-tour` |
| Exhibit list | `GET /api/v1/exhibits` |
| Exhibit detail | `GET /api/v1/exhibits/{id}` |
| TTS synthesize | `POST /api/v1/tts/synthesize` |

## Environment Variables

Copy the sample file:

```bash
cp .env.example .env
```

Important fields:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379/0
ELASTICSEARCH_URL=http://localhost:9200
JWT_SECRET=

LLM_PROVIDER=qwen
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=
LLM_MODEL=qwen-flash
LLM_TOUR_MODEL=qwen-flash
LLM_REPORT_MODEL=qwen-plus
LLM_HEADERS=
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=800
LLM_ENABLE_THINKING=false
LLM_COMPAT_MODE=qwen

RERANK_PROVIDER=siliconflow
RERANK_API_KEY=
RERANK_MODEL=BAAI/bge-reranker-v2-m3

TTS_PROVIDER=xiaomi
TTS_API_KEY=
TTS_MODEL=mimo-v2.5-tts
TTS_DEFAULT_VOICE=冰糖
```

Never commit `.env`. Restart the backend process after changing production `.env`.

## Local Development

```bash
cd backend
uv sync --extra dev
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Tests

Common checks:

```bash
cd backend
py -3 -m py_compile backend/app/api/tour.py backend/app/api/curator.py backend/app/api/tts.py backend/app/application/tour_chat_service.py backend/app/application/tour_report_service.py
uv run --extra dev pytest backend/tests/unit/test_tour_chat.py -q
uv run --extra dev pytest backend/tests/unit/test_tts_core.py backend/tests/unit/test_tts_advanced.py backend/tests/unit/test_voice_description_helpers.py -q
uv run --extra dev pytest backend/tests/contract/test_tour_api.py -q
```

Full test run:

```bash
uv run --extra dev pytest -q
```

## Server Deployment Notes

The current server has used this shape:

- Uvicorn listens on `127.0.0.1:8000`.
- Nginx proxies traffic to the backend.
- Development debugging can use `http://122.152.232.190:3000/api/v1`.
- Formal mini-program traffic should use `https://api.banpo-museai.xyz/api/v1`, but it cannot be treated as production-ready before filing and WeChat legal-domain approval pass.

Typical manual update flow:

```bash
cd ~/MuseAI
git pull myfork main
pkill -f "uv run uvicorn backend.app.main:app" || true
nohup uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > backend_uvicorn.log 2>&1 &
sleep 3
curl -i http://127.0.0.1:8000/api/v1/health
curl -i https://api.banpo-museai.xyz/api/v1/health
```

Before launch, replace manual `nohup` with systemd or Docker Compose.

## Launch Blockers

- Decide the mini-program filing subject: individual, university/project institution, or museum partner.
- After filing passes, configure WeChat legal domains for request/uploadFile/downloadFile.
- Switch frontend API endpoints from development IP to HTTPS domain.
- Rotate any AppSecret or API keys that were exposed during testing.
- Add systemd/Docker Compose, log rotation, database backups, and rollback steps.
- Complete iOS/Android real-device validation for onboarding, routes, tour chat, TTS, OCR, and reports.

## Security Notes

- Do not commit `.env`, `.env.backup*`, private keys, AppSecret, LLM keys, or TTS keys.
- Keep SSL private keys only on the server with restrictive permissions, for example `600`.
- Do not print full API keys, AppSecrets, user tokens, or raw private data in debug logs.
