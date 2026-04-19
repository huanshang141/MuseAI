# Midterm 14-Issue Remediation Implementation Plan
**Status:** completed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all 14 midterm audit issues with test-driven, production-safe changes across backend, frontend, and CI/CD.

**Architecture:** Execute by issue track in strict order: policy/contract -> architecture boundaries -> runtime resource lifecycle -> security hardening -> performance improvements -> delivery governance -> frontend consistency. Every issue starts with a failing test (or failing contract check), then minimal implementation, then targeted verification. Keep each issue in an isolated commit to simplify review and rollback.

**Tech Stack:** FastAPI, SQLAlchemy async, Redis, Elasticsearch, LangChain/LangGraph, Vue 3, Vite, Vitest, GitHub Actions, Pytest

---

### Task 1: Issue-01 Public Document Read Boundary Governance

**Files:**
- Create: `docs/security/public-document-read-policy.md`
- Create: `backend/tests/contract/test_documents_public_contract.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/tests/contract/test_documents_api.py`

**Step 1: Write the failing contract test for public field whitelist**

```python
@pytest.mark.asyncio
async def test_guest_document_list_uses_public_field_whitelist(client):
    resp = await client.get("/api/v1/documents")
    assert resp.status_code == 200
    doc = resp.json()["documents"][0]
    assert set(doc.keys()) == {"id", "filename", "status", "created_at"}


@pytest.mark.asyncio
async def test_guest_document_status_uses_public_field_whitelist(client, doc_id):
    resp = await client.get(f"/api/v1/documents/{doc_id}/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert set(payload.keys()) == {"id", "document_id", "status", "chunk_count", "created_at", "updated_at"}
```

**Step 2: Run test to verify it fails**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_documents_public_contract.py -v`
Expected: FAIL because current response exposes non-whitelisted fields.

**Step 3: Write minimal implementation for explicit public response models**

```python
class PublicDocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: str


class PublicIngestionJobResponse(BaseModel):
    id: str
    document_id: str
    status: str
    chunk_count: int
    created_at: str
    updated_at: str
```

Wire `GET /documents`, `GET /documents/{doc_id}`, and `GET /documents/{doc_id}/status` to these public models and document the policy in `docs/security/public-document-read-policy.md`.

**Step 4: Run targeted tests to verify pass**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_documents_api.py backend/tests/contract/test_documents_public_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/security/public-document-read-policy.md backend/app/api/documents.py backend/tests/contract/test_documents_api.py backend/tests/contract/test_documents_public_contract.py
git commit -m "feat: formalize public document read contract and whitelist fields"
```

---

### Task 2: Issue-02 Layered Architecture Boundary Enforcement

**Files:**
- Create: `backend/tests/architecture/test_layer_import_rules.py`
- Create: `backend/app/application/ports/repositories.py`
- Create: `backend/app/infra/postgres/adapters/auth_repository.py`
- Create: `backend/app/infra/postgres/adapters/document_repository.py`
- Modify: `backend/app/application/auth_service.py`
- Modify: `backend/app/application/document_service.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/api/documents.py`

**Step 1: Write failing architecture test**

```python
def test_application_layer_does_not_import_infra_modules():
    violations = scan_imports("backend/app/application", forbidden_prefix="app.infra")
    assert violations == []
```

**Step 2: Run test to verify it fails**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/architecture/test_layer_import_rules.py -v`
Expected: FAIL due to direct infra imports in application services.

**Step 3: Implement repository port + adapter split**

```python
class UserRepositoryPort(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_id(self, user_id: str) -> User | None: ...
    async def add(self, user: User) -> None: ...
```

Refactor `auth_service` and `document_service` to depend on ports, then inject Postgres adapters from API layer.

**Step 4: Run architecture + service tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/architecture/test_layer_import_rules.py backend/tests/unit/test_auth_service.py backend/tests/unit/test_document_service.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/tests/architecture/test_layer_import_rules.py backend/app/application/ports/repositories.py backend/app/infra/postgres/adapters/auth_repository.py backend/app/infra/postgres/adapters/document_repository.py backend/app/application/auth_service.py backend/app/application/document_service.py backend/app/api/auth.py backend/app/api/documents.py
git commit -m "refactor: enforce layered architecture with repository ports and adapters"
```

---

### Task 3: Issue-03 Remove Router Fallback Singletons and Runtime Constructors

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/test_api_state_dependencies.py`

**Step 1: Write failing test for no fallback construction in routers**

```python
def test_chat_router_has_no_module_level_fallback_singletons():
    from app.api import chat
    src = inspect.getsource(chat)
    assert "_rag_agent" not in src
    assert "_llm_provider" not in src
    assert "_get_app_state_attr" not in src
```

**Step 2: Run test to verify it fails**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_api_state_dependencies.py -v`
Expected: FAIL against current router source.

**Step 3: Implement strict app.state dependency accessors**

```python
def get_rag_agent(request: Request) -> Any:
    if hasattr(request.app.state, "rag_agent"):
        return request.app.state.rag_agent
    raise HTTPException(status_code=503, detail="RAG agent not initialized")
```

Replace router-local constructors with dependency injection from `deps.py`.

**Step 4: Run chat/documents contract tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_chat_api.py backend/tests/contract/test_documents_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/app/api/documents.py backend/app/api/deps.py backend/app/main.py backend/tests/unit/test_api_state_dependencies.py
git commit -m "refactor: remove router fallback singletons and enforce app.state dependencies"
```

---

### Task 4: Issue-04 Remove Runtime Imports from `app.main` in Deep Modules

**Files:**
- Create: `backend/app/application/prompt_gateway.py`
- Create: `backend/app/application/prompt_service_adapter.py`
- Modify: `backend/app/workflows/query_transform.py`
- Modify: `backend/app/infra/langchain/agents.py`
- Modify: `backend/app/infra/langchain/__init__.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/architecture/test_no_main_runtime_imports.py`

**Step 1: Write failing architecture test for runtime imports**

```python
def test_no_runtime_import_from_main_outside_main_module():
    violations = find_runtime_imports("backend/app", pattern="from app.main import")
    assert violations == []
```

**Step 2: Run test to verify it fails**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/architecture/test_no_main_runtime_imports.py -v`
Expected: FAIL for `query_transform.py` and `agents.py`.

**Step 3: Inject prompt gateway into workflow and agent constructors**

```python
class PromptGateway(Protocol):
    async def render(self, key: str, variables: dict[str, str]) -> str | None: ...
```

Pass `PromptGateway` from `main.py` to query rewriter and `RAGAgent`, removing runtime imports from deep modules.

**Step 4: Run workflow/agent unit tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_query_transform.py backend/tests/unit/test_rag_agent.py backend/tests/architecture/test_no_main_runtime_imports.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/application/prompt_gateway.py backend/app/application/prompt_service_adapter.py backend/app/workflows/query_transform.py backend/app/infra/langchain/agents.py backend/app/infra/langchain/__init__.py backend/app/main.py backend/tests/architecture/test_no_main_runtime_imports.py
git commit -m "refactor: remove deep runtime imports from main via prompt gateway injection"
```

---

### Task 5: Issue-05 Decouple DB Session Lifetime from SSE Stream Lifetime

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/application/chat_service.py`
- Create: `backend/tests/unit/test_chat_stream_session_lifecycle.py`
- Modify: `backend/tests/contract/test_sse_events.py`

**Step 1: Write failing lifecycle test**

```python
@pytest.mark.asyncio
async def test_stream_generator_does_not_hold_request_session_for_entire_stream():
    events = [e async for e in stream_chat_with_rag(...)]
    assert any('"type": "chunk"' in e for e in events)
    assert request_scoped_session.commit.await_count == 0
```

**Step 2: Run test to verify it fails**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_chat_stream_session_lifecycle.py -v`
Expected: FAIL because current stream function uses request session until completion.

**Step 3: Implement short-lived persistence session flow**

```python
async def persist_stream_result(session_maker, session_id, user_msg, answer, trace_id):
    async with get_session(session_maker) as session:
        await add_message(session, session_id, "user", user_msg)
        await add_message(session, session_id, "assistant", answer, trace_id=trace_id)
```

Use request session only for pre-check (`session ownership`), then stream without DB, then persist using a new short-lived session.

**Step 4: Run SSE contract + unit tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_chat_stream_session_lifecycle.py backend/tests/contract/test_sse_events.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/app/application/chat_service.py backend/tests/unit/test_chat_stream_session_lifecycle.py backend/tests/contract/test_sse_events.py
git commit -m "perf: decouple db session lifecycle from sse stream lifecycle"
```

---

### Task 6: Issue-06 Parallel Retrieval and Real Token Streaming

**Files:**
- Modify: `backend/app/infra/langchain/retrievers.py`
- Modify: `backend/app/application/chat_service.py`
- Create: `backend/tests/unit/test_retriever_parallelism.py`
- Modify: `backend/tests/unit/test_chat_service_streaming.py`

**Step 1: Write failing parallel retrieval + streaming behavior tests**

```python
@pytest.mark.asyncio
async def test_unified_retriever_executes_dense_and_bm25_in_parallel():
    started = time.perf_counter()
    await retriever._aget_relevant_documents("q")
    assert time.perf_counter() - started < 0.18
```

```python
@pytest.mark.asyncio
async def test_streaming_emits_llm_tokens_not_fixed_50_char_slices():
    events = [e async for e in ask_question_stream_with_rag(...)]
    assert any('"type": "chunk"' in e for e in events)
    assert not all(len(extract_chunk(e)) == 50 for e in events if '"type": "chunk"' in e)
```

**Step 2: Run tests to verify they fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_retriever_parallelism.py backend/tests/unit/test_chat_service_streaming.py -v`
Expected: FAIL.

**Step 3: Implement parallel retrieval + token forwarding**

```python
dense_results, bm25_results = await asyncio.gather(
    self.es_client.search_dense(query_vector, self.top_k * 2, source_types=self.source_types),
    self.es_client.search_bm25(query, self.top_k * 2, source_types=self.source_types),
)
```

Build generation prompt from retrieved context and forward `llm_provider.generate_stream(...)` chunks directly to SSE.

**Step 4: Run performance-sensitive unit tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_retriever_parallelism.py backend/tests/unit/test_chat_service_streaming.py backend/tests/contract/test_sse_events.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/infra/langchain/retrievers.py backend/app/application/chat_service.py backend/tests/unit/test_retriever_parallelism.py backend/tests/unit/test_chat_service_streaming.py backend/tests/contract/test_sse_events.py
git commit -m "perf: parallelize hybrid retrieval and switch to true token streaming"
```

---

### Task 7: Issue-07 Harden Auth Rate-Limit Client IP Trust Model

**Files:**
- Create: `backend/app/api/client_ip.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/observability/middleware.py`
- Modify: `backend/app/config/settings.py`
- Create: `backend/tests/unit/test_client_ip.py`
- Modify: `backend/tests/unit/test_deps_security.py`

**Step 1: Write failing tests for trusted-proxy behavior**

```python
def test_ignores_xff_when_request_not_from_trusted_proxy():
    ip = extract_client_ip(request_with_xff("1.2.3.4", peer_ip="8.8.8.8"), trusted_proxies={"10.0.0.1"})
    assert ip == "8.8.8.8"
```

**Step 2: Run tests to verify fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_client_ip.py backend/tests/unit/test_deps_security.py -v`
Expected: FAIL.

**Step 3: Implement centralized client IP extractor**

```python
def extract_client_ip(request: Request, trusted_proxies: set[str]) -> str:
    peer_ip = request.client.host if request.client else "unknown"
    if peer_ip in trusted_proxies:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return peer_ip
```

Use this helper from both auth rate-limiter and request logging middleware.

**Step 4: Run security-related tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_client_ip.py backend/tests/unit/test_deps_security.py backend/tests/contract/test_auth_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/client_ip.py backend/app/api/deps.py backend/app/observability/middleware.py backend/app/config/settings.py backend/tests/unit/test_client_ip.py backend/tests/unit/test_deps_security.py backend/tests/contract/test_auth_api.py
git commit -m "security: trust x-forwarded-for only behind configured proxies"
```

---

### Task 8: Issue-08 Add Guest Chat Abuse Controls

**Files:**
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/tests/contract/test_chat_api.py`
- Create: `backend/tests/unit/test_guest_rate_limit.py`

**Step 1: Write failing guest-rate-limit tests**

```python
@pytest.mark.asyncio
async def test_guest_message_returns_429_when_guest_limit_exceeded(client):
    for _ in range(6):
        last = await client.post("/api/v1/chat/guest/message", json={"message": "hello"})
    assert last.status_code == 429
```

**Step 2: Run tests to verify fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_guest_rate_limit.py backend/tests/contract/test_chat_api.py::test_guest_can_send_chat_message -v`
Expected: FAIL because endpoint currently has no guest limiter.

**Step 3: Implement guest rate-limit dependency**

```python
async def check_guest_rate_limit(request: Request, redis: RedisCache = Depends(get_redis_cache)) -> None:
    client_key = extract_client_ip(request, trusted_proxies)
    if not await redis.check_rate_limit(f"guest:{client_key}", max_requests=20):
        raise HTTPException(status_code=429, detail="Guest rate limit exceeded")
```

Attach dependency to `POST /chat/guest/message`.

**Step 4: Run guest chat contract tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_guest_rate_limit.py backend/tests/contract/test_chat_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/app/api/chat.py backend/tests/unit/test_guest_rate_limit.py backend/tests/contract/test_chat_api.py
git commit -m "security: add rate limiting controls for guest chat streaming"
```

---

### Task 9: Issue-09 Remove Sensitive Frontend API Logging

**Files:**
- Create: `frontend/src/utils/logger.js`
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/composables/useChat.js`
- Modify: `frontend/src/components/ChatPanel.vue`
- Modify: `frontend/src/api/__tests__/index.test.js`

**Step 1: Write failing test that forbids production debug logs in API layer**

```javascript
it('does not emit request/response body logs during api calls', async () => {
  const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'ok' }) }))
  await api.health()
  expect(logSpy).not.toHaveBeenCalled()
})
```

**Step 2: Run test to verify fail**

Run: `npm run test --prefix frontend -- --run src/api/__tests__/index.test.js`
Expected: FAIL because `console.log` is currently called.

**Step 3: Implement environment-gated logger and replace raw console logs**

```javascript
export function debug(...args) {
  if (import.meta.env.DEV) {
    console.debug(...args)
  }
}
```

Replace direct `console.log` calls in API/composable/component hot paths.

**Step 4: Run frontend tests**

Run: `npm run test --prefix frontend -- --run`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/utils/logger.js frontend/src/api/index.js frontend/src/composables/useChat.js frontend/src/components/ChatPanel.vue frontend/src/api/__tests__/index.test.js
git commit -m "security: remove sensitive frontend request/response logging"
```

---

### Task 10: Issue-10 Migrate Auth from localStorage Token to HttpOnly Cookie Flow

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/config/settings.py`
- Modify: `backend/tests/contract/test_auth_api.py`
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/composables/useAuth.js`
- Modify: `frontend/src/composables/__tests__/useAuth.test.js`

**Step 1: Write failing auth cookie contract test**

```python
@pytest.mark.asyncio
async def test_login_sets_http_only_cookie(client):
    response = await client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "Password123"})
    assert response.status_code == 200
    cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in cookie
    assert "HttpOnly" in cookie
```

**Step 2: Run test to verify fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_auth_api.py -v`
Expected: FAIL because login currently returns token body only.

**Step 3: Implement backend cookie issuance and cookie-based auth extraction**

```python
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=settings.APP_ENV == "production",
    samesite="lax",
    max_age=jwt_handler.expire_minutes * 60,
)
```

Update `get_current_user` to read bearer token from Authorization first, then fallback to cookie token.

**Step 4: Implement frontend credentialed requests and remove token localStorage reads**

```javascript
response = await fetch(`${BASE_URL}${path}`, {
  credentials: 'include',
  headers,
  ...options,
})
```

Remove `localStorage.getItem('access_token')` dependency from API/composable auth flow.

**Step 5: Run backend + frontend auth tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_auth_api.py backend/tests/unit/test_api_deps.py -v && npm run test --prefix frontend -- --run src/composables/__tests__/useAuth.test.js`
Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/api/auth.py backend/app/api/deps.py backend/app/config/settings.py backend/tests/contract/test_auth_api.py frontend/src/api/index.js frontend/src/composables/useAuth.js frontend/src/composables/__tests__/useAuth.test.js
git commit -m "security: migrate auth session handling to httpOnly cookie flow"
```

---

### Task 11: Issue-11 Prevent Internal Exception Leakage in Document APIs

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/application/document_service.py`
- Modify: `backend/tests/contract/test_documents_api.py`
- Create: `backend/tests/contract/test_documents_error_sanitization.py`

**Step 1: Write failing sanitization tests**

```python
@pytest.mark.asyncio
async def test_public_document_response_does_not_expose_raw_processing_exception(client, failed_doc_id):
    resp = await client.get(f"/api/v1/documents/{failed_doc_id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert "stack" not in str(payload)
    assert payload.get("error") in (None, "processing_failed")
```

**Step 2: Run test to verify fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_documents_error_sanitization.py -v`
Expected: FAIL because current API can return raw error strings.

**Step 3: Implement sanitized persistence and response mapping**

```python
except Exception as e:
    error_id = str(uuid.uuid4())
    logger.exception(f"Document processing failed id={error_id}: {e}")
    await update_document_status(session, document_id, "failed", "processing_failed")
```

Ensure public endpoints only expose sanitized error value.

**Step 4: Run document contract tests**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_documents_api.py backend/tests/contract/test_documents_error_sanitization.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/documents.py backend/app/application/document_service.py backend/tests/contract/test_documents_api.py backend/tests/contract/test_documents_error_sanitization.py
git commit -m "security: sanitize document processing errors in public api responses"
```

---

### Task 12: Issue-12 Expand CI Quality Gates and Coverage Enforcement

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `backend/tests/unit/test_ci_workflow_contract.py`
- Modify: `scripts/verify_local_quality.sh`

**Step 1: Write failing CI workflow contract test**

```python
def test_ci_workflow_contains_required_quality_jobs():
    workflow = load_yaml('.github/workflows/ci.yml')
    jobs = set(workflow['jobs'].keys())
    required = {'lint', 'test-unit', 'test-contract', 'frontend-quality', 'backend-coverage', 'security-scan'}
    assert required.issubset(jobs)
```

**Step 2: Run test to verify fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_ci_workflow_contract.py -v`
Expected: FAIL because current workflow lacks required jobs.

**Step 3: Implement CI job expansion**

```yaml
frontend-quality:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: npm ci --prefix frontend
    - run: npm run build --prefix frontend
    - run: npm run test --prefix frontend -- --run
```

Add backend coverage job with `pytest --cov=backend/app` and fail-under enforcement, plus security scan job.

**Step 4: Run workflow contract test and local quality script**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_ci_workflow_contract.py -v && bash scripts/verify_local_quality.sh`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml backend/tests/unit/test_ci_workflow_contract.py scripts/verify_local_quality.sh
git commit -m "ci: enforce frontend gates coverage threshold and security checks"
```

---

### Task 13: Issue-13 Add Integration Layer and Replace Brittle Source-Inspection Tests

**Files:**
- Create: `backend/tests/integration/test_document_repository_integration.py`
- Create: `backend/tests/integration/test_rate_limit_integration.py`
- Modify: `backend/tests/unit/test_parallel_indexing.py`
- Create: `backend/tests/unit/test_unified_indexing_behavior.py`

**Step 1: Write failing integration tests**

```python
@pytest.mark.asyncio
async def test_document_repo_roundtrip_with_real_session(test_db_session):
    doc = await create_document(test_db_session, 'a.txt', 10, 'user-1')
    await test_db_session.commit()
    fetched = await get_document_by_id_public(test_db_session, doc.id)
    assert fetched is not None
```

**Step 2: Run integration tests to verify fail**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/integration -v`
Expected: FAIL initially (new integration suite not fully wired).

**Step 3: Replace source-string assertions with behavior assertions**

```python
@pytest.mark.asyncio
async def test_index_source_indexes_all_chunks_and_respects_concurrency_limit():
    count = await service.index_source(source, max_concurrency=3)
    assert count == expected_chunk_count
    assert max_observed_concurrency <= 3
```

Remove `inspect.getsource(...)` dependency checks from `test_parallel_indexing.py`.

**Step 4: Run unit + integration test slices**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit/test_parallel_indexing.py backend/tests/unit/test_unified_indexing_behavior.py backend/tests/integration -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/tests/integration/test_document_repository_integration.py backend/tests/integration/test_rate_limit_integration.py backend/tests/unit/test_parallel_indexing.py backend/tests/unit/test_unified_indexing_behavior.py
git commit -m "test: add integration layer and replace brittle source-inspection tests"
```

---

### Task 14: Issue-14 Frontend Boundary Consistency and Critical UX Path Completion

**Files:**
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/components/profile/ProfileSettings.vue`
- Modify: `frontend/src/api/index.js`
- Create: `frontend/src/components/layout/__tests__/AppSidebar.test.js`
- Create: `frontend/src/components/profile/__tests__/ProfileSettings.test.js`

**Step 1: Write failing component tests for sidebar login and profile API boundary**

```javascript
it('clicking sidebar login calls injected showAuthModal', async () => {
  const showAuthModal = vi.fn()
  const wrapper = mount(AppSidebar, { global: { provide: { showAuthModal } } })
  await wrapper.find('button').trigger('click')
  expect(showAuthModal).toHaveBeenCalledWith(true)
})
```

```javascript
it('profile settings uses centralized api.profile methods', async () => {
  expect(api.profile.get).toHaveBeenCalled()
  expect(api.profile.update).toHaveBeenCalled()
})
```

**Step 2: Run tests to verify fail**

Run: `npm run test --prefix frontend -- --run src/components/layout/__tests__/AppSidebar.test.js src/components/profile/__tests__/ProfileSettings.test.js`
Expected: FAIL because sidebar handler is no-op and profile has local fetch wrapper.

**Step 3: Implement injected login action + API boundary unification**

```javascript
const showAuthModal = inject('showAuthModal', () => {})
function handleLogin() {
  showAuthModal(true)
}
```

In `ProfileSettings.vue`, replace local `request(...)` with centralized `api.profile.get()` and `api.profile.update(...)`.

**Step 4: Run full frontend tests**

Run: `npm run test --prefix frontend -- --run`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/layout/AppSidebar.vue frontend/src/components/profile/ProfileSettings.vue frontend/src/api/index.js frontend/src/components/layout/__tests__/AppSidebar.test.js frontend/src/components/profile/__tests__/ProfileSettings.test.js
git commit -m "fix: complete sidebar login path and unify profile api boundary"
```

---

### Task 15: Final Cross-Issue Verification and Audit Closure

**Files:**
- Modify: `docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md`
- Create: `docs/audit/2026-04-08-remediation-summary.md`

**Step 1: Run backend quality matrix**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run ruff check backend/ && ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run mypy backend/ && ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/unit backend/tests/contract backend/tests/integration -v`
Expected: PASS.

**Step 2: Run frontend matrix**

Run: `npm run build --prefix frontend && npm run test --prefix frontend -- --run`
Expected: PASS.

**Step 3: Run policy-level smoke checks**

Run: `ALLOW_INSECURE_DEV_DEFAULTS=true JWT_SECRET=dev-secret-do-not-use-in-production LLM_API_KEY=dev-key-do-not-use-in-production uv run pytest backend/tests/contract/test_documents_public_contract.py backend/tests/contract/test_documents_error_sanitization.py backend/tests/contract/test_auth_api.py backend/tests/contract/test_chat_api.py -v`
Expected: PASS.

**Step 4: Update remediation summary document**

```markdown
# Midterm Remediation Summary (2026-04-08)
**Status:** completed

- Closed Issues: 14/14
- Residual Risk: <list>
- Deferred Items: <list>
- Verification Evidence: <commands + results>
```

**Step 5: Commit final closure docs**

```bash
git add docs/TECHNICAL_DEBT_AUDIT_2026-04-06.md docs/audit/2026-04-08-remediation-summary.md
git commit -m "docs: publish remediation closure and verification evidence for 14 issues"
```
