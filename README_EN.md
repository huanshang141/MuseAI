# MuseAI Backend

Chinese version: [README.md](./README.md)

MuseAI backend is the FastAPI service for the Banpo Museum WeChat mini-program. It provides tour sessions, SSE streaming answers, hall and exhibit data, AI-curated routes, visit reports, the Reflection Engine, RAG retrieval, LLM calls, and TTS synthesis.

## Current Stage

The backend is in the **data-driven mini-program framework validation stage**. The names and introductions of the nine halls are confirmed; current exhibits and images are test data or pending replacement, while maps, routes, and spatial points still await museum data. The backend now provides one CSV/XLSX import contract, deterministic content-specific suggestions, report `next_step` guidance, and exhibit-image management. Production uses systemd, while each release still requires its own backup, migration, health-check, rollback, and real-data acceptance evidence. See [Mini-program content maintenance](./docs/miniapp-content-maintenance.md) for the authoritative maintenance and deployment procedure.


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
- Unified CSV/XLSX museum-data import with whole-batch validation, stable source IDs, dry-run support, and authoritative replacement.
- Data-driven 8–18 character suggestion questions. Explicit values must all pass validation; only a wholly blank cell enables deterministic derivation from trusted exhibit fields.
- Exhibit images through HTTPS `image_url` imports or administrator upload/replace/delete for JPEG, PNG, and WebP. Public APIs return `null` when no image exists so the mini-program can use its default image.
- Visit report generation: visited halls, exhibit views, reflection, record summary, and basic stats.
  - Visited halls are counted from non-clarification `exhibit_question` or `exhibit_view` events; deterministic clarification turns are excluded.
  - Question totals count user-sent messages: every `exhibit_question` counts once, without deduplicating repeated question text.
  - Exhibit views are counted separately from hall visits and deduped by exhibit.
  - Record notes are grouped by hall from user questions and AI answers, using the report model first and falling back to a rule-based summary if generation fails.
  - `exploration_guidance` is led by one concise `next_step` and retains exactly one compatibility `action`; it no longer emits refusal copy for low interaction.
- Reflection Engine without new database tables, new APIs, or new model calls.
- RAG pipeline with query rewrite, Elasticsearch retrieval, rerank, document filtering, and streaming generation.
- LLM model tiers:
  - `LLM_TOUR_MODEL` for normal guide chat.
  - `LLM_REPORT_MODEL` for report summaries.
  - `LLM_MODEL` as compatibility fallback.
- OpenAI-compatible DeepSeek/Qwen calling:
  - DeepSeek thinking can be disabled.
  - Qwen/DashScope thinking can be disabled.
- Server-persisted trusted history is compressed per hall for follow-ups. Client-restored display history and client-supplied `conversation_history` never enter model prompts, retrieval rewrites, or grounding.
- Degraded startup if Redis or Elasticsearch is unavailable.
- TTS synthesis API at `/api/v1/tts/synthesize`, currently defaulting to the "冰糖" voice and returning audio data playable by the mini-program.

## Not Complete Or Still Needs Release Acceptance

HTTPS status, split in two parts:

- Done: ICP filing for `banpo-museai.xyz` has passed; `api.banpo-museai.xyz` DNS, SSL certificate, and Nginx 443 reverse proxy are configured; `https://api.banpo-museai.xyz/api/v1/health` returns healthy.
- Current development state: the mini-program uses `https://api.banpo-museai.xyz/api/v1` exclusively; the legacy public HTTP development endpoint is disabled and is no longer a fallback or debugging path.
- Done (WeChat side): the WeChat request legal domain is configured, DevTools domain settings were refreshed, and real-device testing passed with the legal-domain exemption turned off.

Other items:

- OCR service has not been purchased or configured; OCR recognition is currently handled mainly by the mini-program side with exhibit text matching fallback; no backend OCR API was added.
- Official museum exhibit catalogue, images, map, positions, and spatial layout still need confirmation. The current data is not the final real museum data.
- The LLM Qwen API is provided by Alex, while other API keys are provided by another teammate. Release needs explicit ownership, quota, billing, alerting, and rotation rules.
- Current Qwen calls consume free or trial quota. Confirm quota, rate limits, and billing policy in the provider console before experience-version testing.
- The production backend is managed by systemd. Loguru rotates application files daily with seven-day retention, while the PostgreSQL backup service/timer lives under `deploy/`; each release still records its actual backup, checksum, health checks, and rollback evidence.
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

Local development may derive a machine-local `.env` from the repository sample. This README does not enumerate concrete fields, service endpoints, models, key owners, or production values; production configuration remains only in the controlled server environment file.

```bash
cp .env.example .env
```

Never commit `.env`. After a production change, restart through the controlled release procedure and verify readiness. Quotas, billing alerts, and key rotation belong in private operations records.

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
- The mini-program uses `https://api.banpo-museai.xyz/api/v1` exclusively. Port `3000` is no longer a release, debugging, or rollback path; both WeChat DevTools and real-device checks must exercise the HTTPS domain.

Recommended for 2 CPU cores / 8 GB RAM:

- Keep the backend at one Uvicorn worker by default, so Redis, Elasticsearch, PostgreSQL, and Python do not compete aggressively for memory.
- RAG, rerank, and TTS rely on external services; control concurrency and timeouts to protect streaming guide latency.
- If Elasticsearch, Redis, PostgreSQL, and the backend run on the same host, monitor memory continuously and split search or database services first as data grows.

Production releases use systemd only. Back up PostgreSQL before switching code and include the persistent exhibit-image directory in the same release backup whenever uploaded images exist. The exact release source is `origin/main`; fetch and check out its resolved SHA instead of using an unconditional pull, killing processes by name, or using `nohup` as a production launcher.

The single authoritative procedure for backup, exact-SHA checkout, frozen dependency sync, migrations, systemd stop/start, health checks, and rollback is [Mini-program content maintenance: production deployment and acceptance](./docs/miniapp-content-maintenance.md#7-生产部署和验收). `deploy/DEPLOYMENT_NOTES.md` documents systemd, Nginx, application-managed log retention, backup scheduling, and Swap configuration; it does not define a second release procedure.

## Launch Blockers

- The WeChat request legal domain is configured and passed real-device testing with the exemption disabled. If future features upload files or download remote file URLs, confirm uploadFile/downloadFile legal domains.
- Frontend API endpoints have been switched from the temporary development HTTP endpoint to `https://api.banpo-museai.xyz/api/v1`.
- Import and sample-check official museum exhibit, hall, image, and spatial data.
- Decide the OCR release strategy: buy/configure OCR service ID, or hide OCR and keep text search only.
- Confirm Qwen/DashScope free quota, paid activation, rate limits, and bill alerts.
- Define API-key owners and rotation process.
- Rotate any AppSecret or API keys that were exposed during testing.
- Record and verify the backup, checksum, systemd health checks, and rollback evidence for each production release.
- Complete iOS/Android real-device validation for onboarding, routes, tour chat, TTS, OCR, and reports.

## Security Notes

- Do not commit `.env`, `.env.backup*`, private keys, AppSecret, LLM keys, or TTS keys.
- Keep SSL private keys only on the server with restrictive permissions, for example `600`.
- Do not print full API keys, AppSecrets, user tokens, or raw private data in debug logs.
