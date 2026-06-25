# MuseAI Backend

Chinese version: [README.md](./README.md)

MuseAI backend is the FastAPI service for the Banpo Museum WeChat mini-program. It provides tour sessions, SSE streaming answers, hall and exhibit data, AI-curated routes, visit reports, the Reflection Engine, RAG retrieval, LLM calls, and TTS synthesis.

## Current Stage

The backend is now in the **launch preparation and release closeout stage**. The core mini-program experience is supported and the planned mini-program features have completed real-device testing. ICP filing and the WeChat request legal-domain flow have passed; formal release still depends on real data, OCR service decisions, API-key governance, production process management, and experience-version release work. See [上线准备.md](../project_materials/docs/上线准备.md) for the operational checklist.


## Implemented Capabilities

- Guest tour sessions with `X-Session-Token`.
- SSE guide chat at `/api/v1/tour/sessions/{id}/chat/stream`.
- Four guide personas:
  - `A` Archaeology Researcher
  - `B` Study Tour Recorder
  - `C` History Inquirer
  - `D` Artifact Researcher
- Three-step onboarding context: focus, assumption, and guide mode.
- Canonical hall slug normalization and Chinese display names. Only the nine halls from the Banpo hall contract are accepted.
- Event tracking for hall enter, exhibit view, questions, and deep dives.
- AI curator route API: `/api/v1/curator/plan-tour`.
- Exhibit listing, detail lookup, hall filtering, and text search.
- Visit report generation: visited halls, exhibit views, reflection, record summary, and basic stats.
  - Visited halls are counted from `exhibit_question` or `exhibit_view`, with `assistant_answer` retained for historical compatibility.
  - Question totals count user-sent messages: every `exhibit_question` counts once, without deduplicating repeated question text.
  - Exhibit views are counted separately from hall visits and deduped by exhibit.
  - Record notes are grouped by hall from user questions and AI answers, using the report model first and falling back to a rule-based summary if generation fails.
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

## Not Complete Or Still Needs Release Acceptance

HTTPS status, split in two parts:

- Done: ICP filing for `banpo-museai.xyz` has passed; `api.banpo-museai.xyz` DNS, SSL certificate, and Nginx 443 reverse proxy are configured; `https://api.banpo-museai.xyz/api/v1/health` returns healthy.
- Current development state: the mini-program frontend now uses `https://api.banpo-museai.xyz/api/v1` for testing; the public HTTP development endpoint is retained only as emergency fallback or historical debugging context.
- Done (WeChat side): the WeChat request legal domain is configured, DevTools domain settings were refreshed, and real-device testing passed with the legal-domain exemption turned off.

Other items:

- OCR service has not been purchased or configured; OCR recognition is currently handled mainly by the mini-program side with exhibit text matching fallback; no backend OCR API was added.
- Official museum exhibit catalogue, images, map, positions, and spatial layout still need confirmation. The current data is not the final real museum data.
- The LLM Qwen API is provided by Alex, while other API keys are provided by another teammate. Release needs explicit ownership, quota, billing, alerting, and rotation rules.
- Current Qwen calls consume free or trial quota. Confirm quota, rate limits, and billing policy in the provider console before experience-version testing.
- Production process management (systemd), log rotation, and database backup now have deployment assets (see `deploy/`), but they have not been applied on the server yet.
- Experience-version upload, tester distribution, and a final full regression before upload are not complete.

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

## Report And Event Contract

Report statistics depend on `tour_events`. Frontend events should use one of the nine canonical hall slugs, or the matching Chinese hall name. Legacy hall slugs are no longer mapped; hall values that cannot be normalized to the nine-hall contract are dropped.

Visited halls are counted from:

- `exhibit_question`
- `exhibit_view`
- `assistant_answer`

Simply entering a hall is not enough. A hall is counted after the user sends a message in that hall, or opens any exhibit detail page from that hall. `halls_visited` is deduped by canonical hall slug. Question totals are counted from `exhibit_question`, one per user-sent message, without deduplicating repeated text. Exhibit detail entry records `exhibit_view` and affects exhibit stats separately, deduped by exhibit.

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

API-key ownership guidance:

- `LLM_API_KEY` is currently maintained by Alex and is used mainly for Qwen/DashScope guide chat and report summaries.
- `RERANK_API_KEY`, `TTS_API_KEY`, and future OCR or other service keys should each have an explicit owner.
- The repository records config names only, never real key values.
- Free quota must not be treated as the long-term production plan. Before experience-version testing, confirm billing, bill alerts, rate limits, and fallback model ids.
- Prefer provider replacement through `.env` OpenAI-compatible settings. Do not change RAG or SSE contracts during the launch window.

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
py -3 -m py_compile backend/app/application/tour_event_service.py
uv run --extra dev pytest backend/tests/unit/test_tour_chat.py -q
uv run --extra dev pytest backend/tests/unit/test_tour_services.py -q
uv run --extra dev pytest backend/tests/unit/test_tts_core.py backend/tests/unit/test_tts_advanced.py backend/tests/unit/test_voice_description_helpers.py -q
uv run --extra dev pytest backend/tests/contract/test_tour_api.py -q
```

Full test run:

```bash
uv run --extra dev pytest -q
# If an old Windows pytest temp directory is locked:
uv run --extra dev pytest -q --basetemp .pytest-tmp
```

## Server Deployment Notes

The current server resource budget is now **2 CPU cores / 8 GB RAM**. Deployment and performance tuning should use that budget. The current server has used this shape:

- Uvicorn listens on `127.0.0.1:8000`.
- Nginx proxies traffic to the backend.
- The mini-program should now use `https://api.banpo-museai.xyz/api/v1` for testing. If it temporarily falls back to `http://122.152.232.190:3000/api/v1`, release builds must switch back to HTTPS and disable the WeChat DevTools legal-domain exemption.
- Historical note: early development used `http://122.152.232.190:3000/api/v1`; the public HTTP entry should be closed once HTTPS real-device validation passes (see `deploy/DEPLOYMENT_NOTES.md`).

Recommended for 2 CPU cores / 8 GB RAM:

- Keep the backend at one Uvicorn worker by default, so Redis, Elasticsearch, PostgreSQL, and Python do not compete aggressively for memory.
- RAG, rerank, and TTS rely on external services; control concurrency and timeouts to protect streaming guide latency.
- If Elasticsearch, Redis, PostgreSQL, and the backend run on the same host, monitor memory continuously and split search or database services first as data grows.

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

- The WeChat request legal domain is configured and passed real-device testing with the exemption disabled. If future features upload files or download remote file URLs, confirm uploadFile/downloadFile legal domains.
- Frontend API endpoints have been switched from the temporary development HTTP endpoint to `https://api.banpo-museai.xyz/api/v1`.
- Import and sample-check official museum exhibit, hall, image, and spatial data.
- Decide the OCR release strategy: buy/configure OCR service ID, or hide OCR and keep text search only.
- Confirm Qwen/DashScope free quota, paid activation, rate limits, and bill alerts.
- Define API-key owners and rotation process.
- Rotate any AppSecret or API keys that were exposed during testing.
- Add systemd/Docker Compose, log rotation, database backups, and rollback steps.
- Complete iOS/Android real-device validation for onboarding, routes, tour chat, TTS, OCR, and reports.

## Security Notes

- Do not commit `.env`, `.env.backup*`, private keys, AppSecret, LLM keys, or TTS keys.
- Keep SSL private keys only on the server with restrictive permissions, for example `600`.
- Do not print full API keys, AppSecrets, user tokens, or raw private data in debug logs.
