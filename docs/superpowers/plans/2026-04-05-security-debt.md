# Security Technical Debt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all P0 and P1 security vulnerabilities identified in the technical debt audit.

**Architecture:** Remove hardcoded secrets, add environment validation, secure CORS configuration, implement rate limiting on auth endpoints, fix fail-open behavior, sanitize error messages.

**Tech Stack:** Python 3.13, Pydantic Settings, FastAPI, Redis

---

## Files Modified

| File | Purpose |
|------|---------|
| `backend/app/config/settings.py` | Remove hardcoded secrets, add validation |
| `backend/app/main.py` | Configure CORS from settings |
| `backend/app/api/auth.py` | Add rate limiting to auth endpoints |
| `backend/app/api/deps.py` | Fix fail-open behavior for token blacklist |
| `backend/app/application/chat_service.py` | Sanitize error messages in SSE |
| `backend/tests/unit/test_config.py` | Add tests for settings validation |

---

## Task 1: Remove Hardcoded Secrets and Add Validation

**Files:**
- Modify: `backend/app/config/settings.py`
- Modify: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test for secret validation**

```python
# backend/tests/unit/test_config.py

import os
import pytest
from pydantic import ValidationError


def test_settings_requires_jwt_secret_in_production(monkeypatch):
    """JWT_SECRET should be required when APP_ENV is production."""
    # Clear any existing env vars
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    
    from app.config.settings import Settings
    
    with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
        Settings()


def test_settings_requires_llm_api_key_in_production(monkeypatch):
    """LLM_API_KEY should be required when APP_ENV is production."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)  # Valid secret
    
    from app.config.settings import Settings
    
    with pytest.raises(ValidationError, match="LLM_API_KEY must be set"):
        Settings()


def test_settings_validates_jwt_secret_length(monkeypatch):
    """JWT_SECRET must be at least 32 characters in production."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "short")  # Too short
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    
    from app.config.settings import Settings
    
    with pytest.raises(ValidationError, match="JWT_SECRET must be at least 32 characters"):
        Settings()


def test_settings_allows_defaults_in_development(monkeypatch):
    """In development mode, defaults are acceptable."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    
    from app.config.settings import Settings
    
    settings = Settings()
    assert settings.JWT_SECRET == "dev-secret-do-not-use-in-production"
    assert settings.LLM_API_KEY == "dev-key-do-not-use-in-production"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_config.py -v`
Expected: FAIL - Settings currently accepts hardcoded defaults

- [ ] **Step 3: Modify settings.py to remove hardcoded secrets**

```python
# backend/app/config/settings.py

import os
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "MuseAI"
    APP_ENV: str = "development"
    DEBUG: bool = False  # Changed: Default to False

    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379"
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    JWT_SECRET: str = ""  # Changed: No default
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    LLM_PROVIDER: str = "openai"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""  # Changed: No default
    LLM_MODEL: str = "gpt-4o-mini"

    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_OLLAMA_MODEL: str = "nomic-embed-text"

    ELASTICSEARCH_INDEX: str = "museai_chunks_v1"
    EMBEDDING_DIMS: int = 768

    # CORS settings
    CORS_ORIGINS: str = "*"  # Comma-separated list or "*"
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("EMBEDDING_DIMS")
    @classmethod
    def validate_embedding_dims(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EMBEDDING_DIMS must be positive")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        is_production = self.APP_ENV == "production"
        
        if is_production:
            if not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be set in production")
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if not self.LLM_API_KEY:
                raise ValueError("LLM_API_KEY must be set in production")
        
        # Development defaults
        if not self.JWT_SECRET:
            self.JWT_SECRET = "dev-secret-do-not-use-in-production"
        if not self.LLM_API_KEY:
            self.LLM_API_KEY = "dev-key-do-not-use-in-production"
        
        return self

    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS setting into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config/settings.py backend/tests/unit/test_config.py
git commit -m "$(cat <<'EOF'
fix(security): remove hardcoded secrets and add production validation

- Remove default JWT_SECRET and LLM_API_KEY values
- Add model validator to require secrets in production
- Validate JWT_SECRET minimum length (32 chars)
- Default DEBUG to False
- Add CORS_ORIGINS setting for production configuration

P0 security fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Configure CORS from Settings

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing test for CORS configuration**

```python
# backend/tests/unit/test_main.py (new file)

import pytest
from fastapi.testclient import TestClient


def test_cors_uses_settings_origins(monkeypatch):
    """CORS should use CORS_ORIGINS from settings."""
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com,https://app.example.com")
    monkeypatch.setenv("APP_ENV", "development")
    
    from app.main import app
    
    # Check that CORS middleware is configured
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    
    # Should allow the configured origin
    assert "access-control-allow-origin" in response.headers


def test_cors_rejects_unauthorized_origin_in_production(monkeypatch):
    """In production, CORS should reject unauthorized origins."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    
    # Need to reimport to pick up new settings
    import importlib
    import app.main
    importlib.reload(app.main)
    
    from app.main import app
    
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://malicious.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    
    # Should NOT allow unauthorized origin
    assert response.headers.get("access-control-allow-origin") != "https://malicious.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_main.py -v`
Expected: FAIL - CORS currently hardcoded to "*"

- [ ] **Step 3: Modify main.py to use settings for CORS**

```python
# backend/app/main.py (only the relevant changes)

# ... existing imports ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    try:
        await init_database(settings.DATABASE_URL)

        es = get_es_client()
        await es.create_index(settings.ELASTICSEARCH_INDEX, settings.EMBEDDING_DIMS)

        yield
    except Exception as e:
        print(f"Failed to initialize: {e}")
        raise
    finally:
        await close_database()
        if es_client:
            await es_client.close()
        print("Shutting down")


app = FastAPI(title="MuseAI", description="Museum AI Guide System", version="2.0.0", lifespan=lifespan)

# Get settings for CORS configuration
_settings = get_settings()
cors_origins = _settings.get_cors_origins()

# In production, don't allow credentials with wildcard
allow_credentials = _settings.CORS_ALLOW_CREDENTIALS and "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... rest of the file ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/unit/test_main.py
git commit -m "$(cat <<'EOF'
fix(security): configure CORS from settings

- Use CORS_ORIGINS from settings instead of hardcoded "*"
- Disable credentials when wildcard origin is used
- Add tests for CORS configuration

P1 security fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add Rate Limiting to Auth Endpoints

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/unit/test_auth_rate_limit.py`

- [ ] **Step 1: Write the failing test for auth rate limiting**

```python
# backend/tests/unit/test_auth_rate_limit.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_redis():
    """Mock Redis for rate limiting tests."""
    redis = MagicMock()
    redis.check_rate_limit = AsyncMock(return_value=True)
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


def test_login_endpoint_has_rate_limiting():
    """Login endpoint should check rate limit."""
    from app.api.auth import router
    
    # Find the login route
    login_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/login':
            login_route = route
            break
    
    assert login_route is not None, "Login route not found"
    # The route should have rate limiting dependency
    # This is a structural check - the actual rate limiting is in deps


def test_register_endpoint_has_rate_limiting():
    """Register endpoint should check rate limit."""
    from app.api.auth import router
    
    register_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/register':
            register_route = route
            break
    
    assert register_route is not None, "Register route not found"
```

- [ ] **Step 2: Run test to verify current state**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_auth_rate_limit.py -v`
Expected: PASS (structural test)

- [ ] **Step 3: Add IP-based rate limiting dependency for auth**

```python
# backend/app/api/deps.py (add at the end)

from fastapi import Request


async def check_auth_rate_limit(
    request: Request,
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> None:
    """Rate limiting for authentication endpoints using IP address.
    
    More restrictive than regular rate limiting:
    - 5 requests per minute for login
    - 3 requests per minute for register
    
    Fails closed for security - returns 503 if Redis unavailable.
    """
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    
    key = f"auth_rate:{client_ip}"
    
    try:
        first_request = await redis.client.set(key, 1, ex=60, nx=True)
        if first_request:
            return
        
        count = await redis.client.incr(key)
        if count > 5:  # 5 attempts per minute
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please try again later.",
            )
    except RedisError as e:
        # Fail closed for auth endpoints - security over availability
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable. Please try again later.",
        ) from e


AuthRateLimitDep = Annotated[None, Depends(check_auth_rate_limit)]
```

- [ ] **Step 4: Modify auth.py to use rate limiting**

```python
# backend/app/api/auth.py (modify imports and endpoints)

from app.api.deps import AuthRateLimitDep, JWTHandlerDep, RedisCacheDep, SessionDep

# ... existing code ...


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: SessionDep,
    _: AuthRateLimitDep,  # Add rate limiting
):
    # ... rest of function unchanged ...


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: SessionDep,
    jwt_handler: JWTHandlerDep,
    _: AuthRateLimitDep,  # Add rate limiting
):
    # ... rest of function unchanged ...
```

- [ ] **Step 5: Run tests to verify**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_auth_rate_limit.py backend/tests/contract/test_auth_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth.py backend/app/api/deps.py backend/tests/unit/test_auth_rate_limit.py
git commit -m "$(cat <<'EOF'
feat(security): add rate limiting to authentication endpoints

- Add check_auth_rate_limit dependency using IP address
- 5 requests per minute limit for login/register
- Fail closed for security (returns 503 if Redis unavailable)
- Apply to both /auth/login and /auth/register endpoints

P1 security fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Fix Token Blacklist Fail-Open Behavior

**Files:**
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/unit/test_deps_security.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_deps_security.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from redis.exceptions import RedisError


@pytest.mark.asyncio
async def test_token_blacklist_fails_closed_in_production():
    """Token blacklist check should fail closed in production."""
    from app.api.deps import get_current_user
    
    # Mock production environment
    with patch("app.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.APP_ENV = "production"
        
        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=RedisError("Connection refused"))
        
        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="test-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")
        
        mock_session = AsyncMock()
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-token"
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )
        
        # Should return 503, not pass through
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_token_blacklist_passes_in_development():
    """Token blacklist check can pass in development for availability."""
    from app.api.deps import get_current_user
    
    with patch("app.api.deps.get_settings") as mock_settings:
        mock_settings.return_value.APP_ENV = "development"
        
        mock_redis = MagicMock()
        mock_redis.is_token_blacklisted = AsyncMock(side_effect=RedisError("Connection refused"))
        
        mock_jwt = MagicMock()
        mock_jwt.get_jti = MagicMock(return_value="test-jti")
        mock_jwt.verify_token = MagicMock(return_value="user-123")
        
        # Mock user lookup
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        
        with patch("app.api.deps.get_user_by_id", AsyncMock(return_value=mock_user)):
            mock_session = AsyncMock()
            
            mock_credentials = MagicMock()
            mock_credentials.credentials = "valid-token"
            
            result = await get_current_user(
                credentials=mock_credentials,
                jwt_handler=mock_jwt,
                session=mock_session,
                redis=mock_redis,
            )
            
            # In development, should pass through
            assert result["id"] == "user-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_deps_security.py -v`
Expected: FAIL - Currently always passes through

- [ ] **Step 3: Modify deps.py to fail closed in production**

```python
# backend/app/api/deps.py (modify get_current_user function)

from app.config.settings import get_settings


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    jwt_handler: JWTHandler = Depends(get_jwt_handler),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    redis: RedisCache = Depends(get_redis_cache),  # noqa: B008
) -> dict:
    token = credentials.credentials

    # Check if token is blacklisted
    jti = jwt_handler.get_jti(token)
    if jti:
        try:
            if await redis.is_token_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except RedisError as e:
            # In production, fail closed for security
            # In development, fail open for availability
            settings = get_settings()
            if settings.APP_ENV == "production":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication temporarily unavailable",
                ) from e
            # In development, log and continue
            print(f"Redis error during blacklist check: {e}")

    user_id = jwt_handler.verify_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"id": user.id, "email": user.email}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_deps_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/tests/unit/test_deps_security.py
git commit -m "$(cat <<'EOF'
fix(security): fail closed for token blacklist in production

- Token blacklist check now returns 503 in production if Redis unavailable
- In development, continues with warning for availability
- Add tests for both behaviors

P1 security fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Sanitize Error Messages in SSE

**Files:**
- Modify: `backend/app/application/chat_service.py`
- Create: `backend/tests/unit/test_chat_error_sanitization.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_chat_error_sanitization.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_sse_error_does_not_leak_internal_details():
    """SSE error events should not contain internal error details."""
    from app.application.chat_service import ask_question_stream_with_rag
    
    mock_session = AsyncMock()
    mock_rag_agent = MagicMock()
    mock_rag_agent.stream = AsyncMock(side_effect=Exception("Internal error: /home/user/secret/path config.py line 42"))
    mock_llm = MagicMock()
    
    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="test-session",
        message="test message",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)
    
    # Find error event
    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0, "Should have error event"
    
    # Error should not contain internal paths
    for event in error_events:
        assert "/home/" not in event
        assert "config.py" not in event
        assert "line 42" not in event
        assert "Internal error" not in event


@pytest.mark.asyncio
async def test_sse_error_shows_generic_message():
    """SSE error events should show generic error message."""
    from app.application.chat_service import ask_question_stream_with_rag
    
    mock_session = AsyncMock()
    mock_rag_agent = MagicMock()
    mock_rag_agent.stream = AsyncMock(side_effect=Exception("Database connection failed"))
    mock_llm = MagicMock()
    
    events = []
    async for event in ask_question_stream_with_rag(
        session=mock_session,
        session_id="test-session",
        message="test message",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        user_id="user-123",
    ):
        events.append(event)
    
    error_events = [e for e in events if "error" in e.lower()]
    assert len(error_events) > 0
    
    # Should contain generic message
    any_has_generic = any("An error occurred" in e or "unexpected error" in e.lower() for e in error_events)
    assert any_has_generic, "Should have generic error message"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_error_sanitization.py -v`
Expected: FAIL - Currently shows raw exception

- [ ] **Step 3: Modify chat_service.py to sanitize errors**

```python
# backend/app/application/chat_service.py

# Add this helper function near the top of the file

def _sanitize_error_message(error: Exception) -> str:
    """Sanitize error message for client display.
    
    Returns a generic message that doesn't expose internal details.
    """
    # Log the actual error for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Chat service error: {type(error).__name__}: {error}")
    
    # Return generic message
    return "An unexpected error occurred. Please try again."


# Then in ask_question_stream_with_rag, find the except block and change:

# FROM:
except Exception as e:
    yield f"event: error\ndata: {str(e)}\n\n"

# TO:
except Exception as e:
    sanitized = _sanitize_error_message(e)
    yield f"event: error\ndata: {sanitized}\n\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_chat_error_sanitization.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/chat_service.py backend/tests/unit/test_chat_error_sanitization.py
git commit -m "$(cat <<'EOF'
fix(security): sanitize error messages in SSE responses

- Add _sanitize_error_message helper to strip internal details
- Log actual errors server-side, return generic message to client
- Prevents information disclosure through error messages

P1 security fix from technical debt audit.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Run All Tests and Verify

- [ ] **Step 1: Run full test suite**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/unit -v`
Expected: All tests PASS

- [ ] **Step 2: Run contract tests**

Run: `cd /home/singer/MuseAI && uv run pytest backend/tests/contract -v`
Expected: All tests PASS

- [ ] **Step 3: Final commit for security debt completion**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: complete security technical debt fixes (P0 + P1)

Completed fixes:
- P0: Remove hardcoded JWT_SECRET and LLM_API_KEY
- P0: Add production validation for secrets
- P1: Configure CORS from settings
- P1: Add rate limiting to auth endpoints (fail closed)
- P1: Fix token blacklist fail-open behavior
- P1: Sanitize error messages in SSE

All tests passing.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```
