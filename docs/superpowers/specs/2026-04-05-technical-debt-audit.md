# Technical Debt Audit Report - MuseAI

**Date**: 2026-04-05
**Scope**: Full audit (backend Python, frontend Vue, tests, config/deployment)
**Focus Dimensions**: Security, Architecture, Test Quality, Performance
**Total Issues**: 56

---

## Executive Summary

| Priority | Count | Description |
|----------|-------|-------------|
| **P0 - Critical** | 8 | Must fix immediately - security vulnerabilities, data loss risk |
| **P1 - High** | 21 | Fix this sprint - architectural defects, performance bottlenecks |
| **P2 - Medium** | 21 | Fix next sprint - code quality, missing tests |
| **P3 - Low** | 6 | Backlog - style issues, documentation, minor improvements |

### Risk Assessment

**Overall Risk Level: HIGH**

- 2 hardcoded production secrets (JWT, LLM API key)
- Dead domain layer violating Clean Architecture
- No frontend test infrastructure
- Redis connection churn on every request
- Missing pagination on list endpoints

---

## P0 - Critical (Must Fix Immediately)

### [P0] [SECURITY] Hardcoded Default JWT Secret
- **Location**: [backend/app/config/settings.py:16](backend/app/config/settings.py#L16)
- **Problem**: JWT secret has hardcoded default `"test-secret"`. In production, attackers can forge valid JWT tokens.
- **Impact**: Complete authentication bypass - attackers can generate valid tokens for any user.
- **Recommendation**: Remove default value, require `JWT_SECRET` via environment variable, validate minimum 256 bits at startup.

### [P0] [SECURITY] Hardcoded Default LLM API Key
- **Location**: [backend/app/config/settings.py:22](backend/app/config/settings.py#L22)
- **Problem**: LLM API key has hardcoded default `"test-key"` that could be used in production.
- **Impact**: Unauthorized access to LLM services, credential exposure.
- **Recommendation**: Remove default, require `LLM_API_KEY` in production, add startup validation.

### [P0] [ARCHITECTURE] Domain Entities Not Used - ORM Models Leak into Application Layer
- **Location**: [backend/app/application/*.py](backend/app/application/)
- **Problem**: Application services directly use SQLAlchemy ORM models instead of domain entities in `domain/entities.py`. Domain layer is dead code.
- **Impact**: Violates Clean Architecture, tight coupling to infrastructure, hard to test business logic independently.
- **Recommendation**: Implement repository pattern to convert between ORM models and domain entities.

### [P0] [ARCHITECTURE] Duplicate Session Maker Implementations with Global State
- **Location**: [backend/app/api/deps.py:17-26](backend/app/api/deps.py#L17), [backend/app/infra/postgres/database.py:40-52](backend/app/infra/postgres/database.py#L40)
- **Problem**: Two separate implementations of session maker management exist with unsynchronized global variables.
- **Impact**: Multiple engine instances, connection pool exhaustion, inconsistent state.
- **Recommendation**: Consolidate session management into single location, use FastAPI's `app.state` or proper lifecycle management.

### [P0] [TEST] No Frontend Test Infrastructure
- **Location**: [frontend/](frontend/)
- **Problem**: No test framework configured. 20 source files including 10 Vue components with zero test coverage.
- **Impact**: Critical quality risk - no automated testing for authentication logic, API integration, chat streaming.
- **Recommendation**: Add Vitest + Vue Test Utils, create unit tests for composables and component tests for critical UI flows.

### [P0] [TEST] No Tests for API Dependencies Module (deps.py)
- **Location**: [backend/app/api/deps.py](backend/app/api/deps.py)
- **Problem**: Critical authentication/rate-limiting middleware has zero direct tests. Handles JWT validation, token blacklisting, rate limiting.
- **Impact**: Security vulnerabilities may go undetected, fail-open behavior for Redis outages untested.
- **Recommendation**: Create `test_api_deps.py` with tests for `get_current_user`, rate limiting, token blacklisting flows.

### [P0] [PERFORMANCE] Redis Connection Created Per Request
- **Location**: [backend/app/api/deps.py:44-46](backend/app/api/deps.py#L44)
- **Problem**: `get_redis_cache()` creates new `RedisCache` instance (and Redis connection) for every request.
- **Impact**: Connection churn, increased latency, resource exhaustion under load.
- **Recommendation**: Use singleton pattern, create Redis client during app lifespan and reuse.

### [P0] [PERFORMANCE] OllamaEmbeddingProvider Creates New HTTP Client Per Embedding
- **Location**: [backend/app/infra/langchain/embeddings.py:18-26](backend/app/infra/langchain/embeddings.py#L18)
- **Problem**: `_get_provider()` creates new `OllamaEmbeddingProvider` with new `httpx.AsyncClient` every time.
- **Impact**: HTTP connection pool exhaustion, memory leaks, increased latency.
- **Recommendation**: Initialize provider once during startup, add to lifespan management in `main.py`.

---

## P1 - High (Fix This Sprint)

### [P1] [SECURITY] Open CORS Configuration
- **Location**: [backend/app/main.py:100-106](backend/app/main.py#L100)
- **Problem**: `allow_origins=["*"]` combined with `allow_credentials=True` enables CSRF attacks.
- **Impact**: Malicious websites can make authenticated requests on behalf of logged-in users.
- **Recommendation**: Restrict to known frontend domains in production, implement CSRF protection.

### [P1] [SECURITY] No Rate Limiting on Auth Endpoints
- **Location**: [backend/app/api/auth.py:81-107](backend/app/api/auth.py#L81)
- **Problem**: `/auth/login` and `/auth/register` have no rate limiting.
- **Impact**: Brute-force password attacks and account enumeration possible.
- **Recommendation**: Implement IP-based rate limiting on auth endpoints with stricter limits.

### [P1] [SECURITY] Token Blacklisting Fails Open
- **Location**: [backend/app/api/deps.py:70-73](backend/app/api/deps.py#L70)
- **Problem**: When Redis unavailable, token blacklist check silently passes.
- **Impact**: Logged-out users can continue using revoked tokens during Redis outages.
- **Recommendation**: Fail closed for security-critical operations, or implement fallback mechanism.

### [P1] [SECURITY] Error Messages Leak Internal Details
- **Location**: [backend/app/application/chat_service.py:160-161,212-213](backend/app/application/chat_service.py#L160)
- **Problem**: Full exception messages sent to clients in SSE error events.
- **Impact**: Information disclosure - stack traces, internal paths, database errors.
- **Recommendation**: Sanitize error messages, return generic messages to clients, log details server-side.

### [P1] [ARCHITECTURE] Infrastructure Layer Imports from Application Layer
- **Location**: [backend/app/infra/langchain/retrievers.py:8](backend/app/infra/langchain/retrievers.py#L8)
- **Problem**: `RRFRetriever` in infra imports `rrf_fusion` from application layer.
- **Impact**: Wrong dependency direction, potential circular dependencies.
- **Recommendation**: Move `rrf_fusion` to domain service or create interface/protocol.

### [P1] [ARCHITECTURE] API Layer Accesses main.py for Dependencies
- **Location**: [backend/app/api/documents.py:55-73](backend/app/api/documents.py#L55), [backend/app/api/chat.py:75-78](backend/app/api/chat.py#L75)
- **Problem**: API routes import from `main.py` using late imports.
- **Impact**: Hidden dependencies, difficult testing, prevents independent module imports.
- **Recommendation**: Move singleton factories to dedicated dependency container module.

### [P1] [ARCHITECTURE] Global Singletons Without Thread-Safety in main.py
- **Location**: [backend/app/main.py:16-74](backend/app/main.py#L16)
- **Problem**: Multiple global variables with lazy initialization, no thread-safety locks.
- **Impact**: Race conditions in concurrent environments, potential resource leaks.
- **Recommendation**: Use `asyncio.Lock` for initialization, or use FastAPI's `app.state`.

### [P1] [ARCHITECTURE] New RedisCache Instance on Every Request
- **Location**: [backend/app/api/deps.py:44-49](backend/app/api/deps.py#L44)
- **Problem**: Same as P0 Performance issue - creates new Redis connection per request.
- **Recommendation**: Consolidate with P0 fix.

### [P1] [ARCHITECTURE] LLM Provider Singleton in Wrong Location
- **Location**: [backend/app/api/chat.py:64-72](backend/app/api/chat.py#L64)
- **Problem**: `_llm_provider` global in API route file while `main.py` has separate `llm` singleton.
- **Impact**: Duplicate state management, potential inconsistent instances.
- **Recommendation**: Consolidate all provider singletons in one location.

### [P1] [ARCHITECTURE] Duplicate Vue Components with Similar Functionality
- **Location**:
  - [frontend/src/components/DocumentList.vue](frontend/src/components/DocumentList.vue) vs [frontend/src/components/knowledge/DocumentList.vue](frontend/src/components/knowledge/DocumentList.vue)
  - [frontend/src/components/DocumentUpload.vue](frontend/src/components/DocumentUpload.vue) vs [frontend/src/components/knowledge/DocumentUpload.vue](frontend/src/components/knowledge/DocumentUpload.vue)
- **Problem**: Two versions of DocumentList and DocumentUpload exist - root components are simple/unused, knowledge/ are full-featured.
- **Impact**: Dead code, confusion, maintenance burden.
- **Recommendation**: Remove unused root-level components, keep well-designed ones.

### [P1] [ARCHITECTURE] Services in Application Layer Mix Concerns
- **Location**: [backend/app/application/chat_service.py](backend/app/application/chat_service.py) (213 lines)
- **Problem**: Contains CRUD, complex business logic, and direct infrastructure access in one file.
- **Impact**: Violates Single Responsibility Principle, hard to test and maintain.
- **Recommendation**: Split into ChatRepository, ChatService, keep domain logic separate.

### [P1] [ARCHITECTURE] Inconsistent Error Handling - Domain Exceptions Not Used
- **Location**: [backend/app/domain/exceptions.py](backend/app/domain/exceptions.py), various services
- **Problem**: Domain exceptions exist but used sporadically. Some code uses HTTPException directly in application layer.
- **Impact**: Application layer coupled to HTTP concerns, inconsistent error handling.
- **Recommendation**: Use domain exceptions consistently, convert to HTTP at API boundary.

### [P1] [ARCHITECTURE] State Machine Implementation Incomplete
- **Location**: [backend/app/workflows/multi_turn.py](backend/app/workflows/multi_turn.py)
- **Problem**: `MultiTurnStateMachine` has `async transform_query()` never called by sync `run()` method.
- **Impact**: Dead code, confusing API.
- **Recommendation**: Make state machine fully async or sync, remove unused paths.

### [P1] [TEST] No Coverage Thresholds Configured
- **Location**: [pyproject.toml](pyproject.toml)
- **Problem**: pytest-cov installed but no coverage thresholds or reporting configuration.
- **Impact**: Coverage can degrade without detection.
- **Recommendation**: Add coverage config with minimum threshold (80%) and fail-under option.

### [P1] [TEST] document_service.py Lacks Dedicated Test File
- **Location**: [backend/app/application/document_service.py](backend/app/application/document_service.py)
- **Problem**: Critical service only tested indirectly through API contract tests.
- **Impact**: Edge cases untested at service level.
- **Recommendation**: Create `test_document_service.py` with unit tests.

### [P1] [TEST] chat_service.py Streaming Functions Undertested
- **Location**: [backend/app/application/chat_service.py](backend/app/application/chat_service.py)
- **Problem**: `ask_question_stream()` has no direct unit tests - complex async generators with error handling.
- **Impact**: Streaming failures, partial message saves untested.
- **Recommendation**: Add dedicated streaming function tests with error injection.

### [P1] [TEST] Ingestion Service Test Coverage Minimal
- **Location**: [backend/tests/unit/test_ingestion_service.py](backend/tests/unit/test_ingestion_service.py)
- **Problem**: Only 1 test exists for complex `process_document` method.
- **Impact**: Failures in document processing pipeline may go undetected.
- **Recommendation**: Add tests for error scenarios, different chunk configurations.

### [P1] [TEST] No Tests for FastAPI Lifespan and Startup Logic
- **Location**: [backend/app/main.py](backend/app/main.py)
- **Problem**: Lifespan handler (database init, ES index creation) untested.
- **Impact**: Startup failures in production won't be caught.
- **Recommendation**: Add tests for lifespan initialization and error handling.

### [P1] [PERFORMANCE] No Pagination on List Endpoints
- **Location**:
  - [backend/app/api/documents.py:135-149](backend/app/api/documents.py#L135)
  - [backend/app/api/chat.py:94-105](backend/app/api/chat.py#L94)
  - [backend/app/api/chat.py:129-149](backend/app/api/chat.py#L129)
- **Problem**: All list endpoints return complete datasets without pagination.
- **Impact**: Memory exhaustion, slow response times, OOM with many records.
- **Recommendation**: Implement cursor/offset pagination with default limits.

### [P1] [PERFORMANCE] Missing Connection Pool Configuration for Database
- **Location**: [backend/app/infra/postgres/database.py:21,48](backend/app/infra/postgres/database.py#L21)
- **Problem**: `create_async_engine()` called without pool configuration.
- **Impact**: Default pool size (5) insufficient for production.
- **Recommendation**: Add explicit pool_size, max_overflow, pool_timeout, pool_recycle.

### [P1] [PERFORMANCE] Sequential Elasticsearch Indexing in Ingestion
- **Location**: [backend/app/application/ingestion_service.py:53-66](backend/app/application/ingestion_service.py#L53)
- **Problem**: Chunks indexed sequentially in `for` loop.
- **Impact**: Slow document ingestion, blocks event loop.
- **Recommendation**: Use `asyncio.gather()` with semaphore for concurrent indexing.

---

## P2 - Medium (Fix Next Sprint)

### [P2] [SECURITY] Rate Limiting Fails Open
- **Location**: [backend/app/api/deps.py:112-115](backend/app/api/deps.py#L112)
- **Problem**: Rate limiting silently passes when Redis unavailable.
- **Impact**: DoS vulnerability during Redis outages.
- **Recommendation**: Implement secondary in-memory rate limiting or return 503.

### [P2] [SECURITY] Missing Input Validation on Chat Fields
- **Location**: [backend/app/api/chat.py:24-25,48-50](backend/app/api/chat.py#L24)
- **Problem**: No length limits on `title` and `message` fields.
- **Impact**: Storage abuse, log injection, DoS through large payloads.
- **Recommendation**: Add max length constraints (title: 200, message: 10000 chars).

### [P2] [SECURITY] Missing Special Character Requirement in Password
- **Location**: [backend/app/api/auth.py:21-34](backend/app/api/auth.py#L21)
- **Problem**: Password validation doesn't require special characters.
- **Impact**: Passwords like "Password1" pass but vulnerable to dictionary attacks.
- **Recommendation**: Add requirement for at least one special character.

### [P2] [SECURITY] Token Stored in localStorage
- **Location**: [frontend/src/composables/useAuth.js:14,35](frontend/src/composables/useAuth.js#L14)
- **Problem**: JWT tokens in localStorage accessible to any JavaScript.
- **Impact**: XSS can steal tokens for session hijacking.
- **Recommendation**: Use httpOnly cookies with Secure and SameSite flags.

### [P2] [SECURITY] Health Endpoint Exposes Infrastructure Details
- **Location**: [backend/app/api/health.py:68-79](backend/app/api/health.py#L68)
- **Problem**: `/ready` exposes detailed infrastructure status to unauthenticated users.
- **Impact**: Attackers can enumerate infrastructure components.
- **Recommendation**: Require auth for detailed checks or provide simple status only.

### [P2] [SECURITY] Python Dependencies Use Minimum Version Constraints
- **Location**: [pyproject.toml:7-29](pyproject.toml#L7)
- **Problem**: Dependencies use `>=x.y.z` without upper bounds.
- **Impact**: Vulnerable versions could be installed via `pip install -U`.
- **Recommendation**: Pin exact versions, regularly audit with `pip-audit`.

### [P2] [ARCHITECTURE] Settings Instance Created on Every Call
- **Location**: Multiple files, 12 occurrences of `get_settings()`
- **Problem**: Creates new Settings instance each time.
- **Impact**: Minor performance overhead, potential inconsistency.
- **Recommendation**: Cache settings or use singleton via `app.state`.

### [P2] [ARCHITECTURE] Duplicate Authentication Checks in Frontend
- **Location**: [frontend/src/composables/useChat.js:26,45,67,86,105](frontend/src/composables/useChat.js#L26), [frontend/src/composables/useDocuments.js:22,41,56,71](frontend/src/composables/useDocuments.js#L22)
- **Problem**: Both composables have identical `if (!isAuthenticated.value)` checks.
- **Impact**: Code duplication, maintenance burden.
- **Recommendation**: Create wrapper/composable for auth checks and error handling.

### [P2] [ARCHITECTURE] Missing Repository Abstraction Layer
- **Location**: [backend/app/application/*.py](backend/app/application/)
- **Problem**: All services directly use SQLAlchemy AsyncSession.
- **Impact**: Cannot swap DB implementations, hard to unit test.
- **Recommendation**: Implement repository interfaces in domain layer.

### [P2] [ARCHITECTURE] Duplicate RRF Implementation
- **Location**: [backend/app/application/retrieval.py:1-66](backend/app/application/retrieval.py#L1), [backend/app/infra/langchain/retrievers.py](backend/app/infra/langchain/retrievers.py)
- **Problem**: RRF in application layer tightly coupled to LangChain retriever.
- **Impact**: Cannot easily reuse or test algorithm independently.
- **Recommendation**: Move RRF to domain service, inject into retriever.

### [P2] [ARCHITECTURE] Missing Protocol/Interface for External Dependencies
- **Location**: [backend/app/infra/providers/llm.py:25-28](backend/app/infra/providers/llm.py#L25)
- **Problem**: LLMProvider Protocol exists but not used consistently.
- **Impact**: Tied to LangChain implementation, cannot swap providers.
- **Recommendation**: Define protocols for all external dependencies.

### [P2] [TEST] Mock Usage Bypasses Real Integration
- **Location**: [backend/tests/unit/test_auth_service.py](backend/tests/unit/test_auth_service.py), [test_chat_integration.py](backend/tests/unit/test_chat_integration.py)
- **Problem**: Tests use MagicMock for database sessions, don't verify actual SQL.
- **Impact**: Transaction issues, constraint violations won't be caught.
- **Recommendation**: Use real async database (SQLite in-memory) for service tests.

### [P2] [TEST] No Tests for Domain Exceptions
- **Location**: [backend/app/domain/exceptions.py](backend/app/domain/exceptions.py)
- **Problem**: Custom exception classes have no tests.
- **Impact**: Exception handling may not work as expected.
- **Recommendation**: Test exceptions are properly raised and caught.

### [P2] [TEST] E2E Tests Require External Services
- **Location**: [backend/tests/e2e/conftest.py](backend/tests/e2e/conftest.py)
- **Problem**: E2E tests require live ES, Ollama, PostgreSQL.
- **Impact**: CI may fail intermittently, can't run without full infrastructure.
- **Recommendation**: Add test markers, provide mocked alternatives for CI.

### [P2] [TEST] No Concurrent Access Tests
- **Location**: Multiple services
- **Problem**: No tests for behavior under concurrent access.
- **Impact**: Race conditions and deadlocks may exist.
- **Recommendation**: Add tests using `asyncio.gather()` for concurrent requests.

### [P2] [TEST] Test Isolation Issues in Contract Tests
- **Location**: [backend/tests/contract/test_chat_api.py](backend/tests/contract/test_chat_api.py), [test_documents_api.py](backend/tests/contract/test_documents_api.py)
- **Problem**: Tests share database state, don't clean up between tests.
- **Impact**: Test order dependencies cause flaky tests.
- **Recommendation**: Add fixtures to truncate tables or use nested transactions.

### [P2] [TEST] No Tests for RRF Retriever Integration
- **Location**: [backend/tests/unit/test_rrf_retriever.py](backend/tests/unit/test_rrf_retriever.py)
- **Problem**: Only 1 test exists, missing error handling tests.
- **Impact**: Retrieval failures may go undetected.
- **Recommendation**: Add tests for search failures, embedding failures, edge cases.

### [P2] [PERFORMANCE] Sequential Dense and BM25 Searches
- **Location**: [backend/app/infra/langchain/retrievers.py:26-29](backend/app/infra/langchain/retrievers.py#L26)
- **Problem**: Dense and BM25 searches executed sequentially.
- **Impact**: Latency is sum of both instead of maximum.
- **Recommendation**: Use `asyncio.gather()` for parallel execution.

### [P2] [PERFORMANCE] asyncio.run() in Sync Context
- **Location**: [backend/app/infra/langchain/embeddings.py:28-31,37-40](backend/app/infra/langchain/embeddings.py#L28)
- **Problem**: Creates new event loop, problematic in async contexts.
- **Impact**: Event loop conflicts, performance overhead.
- **Recommendation**: Only use async methods, raise NotImplementedError for sync.

### [P2] [PERFORMANCE] No Pool Size Configuration for Elasticsearch
- **Location**: [backend/app/infra/elasticsearch/client.py:21-26](backend/app/infra/elasticsearch/client.py#L21)
- **Problem**: AsyncElasticsearch created without connection pool config.
- **Impact**: Limited concurrent requests to ES.
- **Recommendation**: Add explicit `maxsize` parameter.

### [P2] [PERFORMANCE] No Embedding Caching at Service Level
- **Location**: [backend/app/application/ingestion_service.py:51](backend/app/application/ingestion_service.py#L51)
- **Problem**: Embeddings computed every time without cache check.
- **Impact**: Redundant API calls, increased cost and latency.
- **Recommendation**: Check Redis cache for existing embeddings.

### [P2] [PERFORMANCE] Large File Content in Memory
- **Location**: [backend/app/api/documents.py:105-116](backend/app/api/documents.py#L105)
- **Problem**: Entire file read into memory for files up to 50MB.
- **Impact**: Memory exhaustion with concurrent uploads.
- **Recommendation**: Stream file content or use temporary files.

---

## P3 - Low (Backlog)

### [P3] [SECURITY] Debug Mode Default Enabled
- **Location**: [backend/app/config/settings.py:10](backend/app/config/settings.py#L10)
- **Problem**: `DEBUG: bool = True` default could leak info in error pages.
- **Recommendation**: Default to False, only enable in development.

### [P3] [SECURITY] Email Case Sensitivity
- **Location**: [backend/app/application/auth_service.py:52](backend/app/application/auth_service.py#L52)
- **Problem**: Emails queried without normalization.
- **Recommendation**: Normalize emails to lowercase.

### [P3] [SECURITY] Missing Content Security Policy
- **Location**: Frontend application
- **Problem**: No CSP headers set.
- **Recommendation**: Implement strict CSP headers.

### [P3] [ARCHITECTURE] Large File - chat_service.py
- **Location**: [backend/app/application/chat_service.py](backend/app/application/chat_service.py) (213 lines)
- **Recommendation**: Split into focused modules.

### [P3] [ARCHITECTURE] Frontend State via Module-level Refs
- **Location**: [frontend/src/composables/*.js](frontend/src/composables/)
- **Problem**: Shared state via module-level `ref()` can cause issues.
- **Recommendation**: Consider Pinia or document the singleton pattern.

### [P3] [PERFORMANCE] Rate Limiting Uses Simple Counter
- **Location**: [backend/app/infra/redis/cache.py:48-54](backend/app/infra/redis/cache.py#L48)
- **Problem**: Simple counter that resets every 60 seconds.
- **Recommendation**: Implement sliding window or token bucket.

---

## Files Requiring Most Attention

| File | Issues | Highest Priority |
|------|--------|------------------|
| backend/app/api/deps.py | 6 | P0 |
| backend/app/config/settings.py | 3 | P0 |
| backend/app/application/chat_service.py | 4 | P1 |
| backend/app/main.py | 4 | P1 |
| frontend/src/composables/*.js | 3 | P2 |
| backend/app/infra/langchain/embeddings.py | 2 | P0 |

---

## Recommendations Summary

### Immediate Action (P0)
1. Remove hardcoded secrets, add environment validation
2. Consolidate session maker management
3. Fix Redis/HTTP connection reuse
4. Add frontend test infrastructure
5. Add tests for `api/deps.py` security module

### This Sprint (P1)
1. Configure CORS properly
2. Add rate limiting to auth endpoints
3. Implement pagination on all list endpoints
4. Configure database connection pool
5. Parallelize Elasticsearch indexing
6. Remove duplicate Vue components
7. Add coverage thresholds

### Next Sprint (P2)
1. Implement repository pattern
2. Fix dependency direction violations
3. Add service-level tests with real database
4. Implement embedding caching
5. Add concurrent access tests

---

**Report Generated**: 2026-04-05
**Audit Method**: Multi-Agent Parallel Audit
**Agents Used**: Security, Architecture, Test Quality, Performance
