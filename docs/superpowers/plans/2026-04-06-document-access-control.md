# Document Access Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform document system from user-private to public-read with admin-only write access using RBAC.

**Architecture:** Add `role` field to User model, create `OptionalUser` and `CurrentAdmin` dependencies, remove user_id filtering from document retrieval, and update frontend for guest/admin access.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus

---

## File Structure

### Backend Files to Modify
- `backend/app/infra/postgres/models.py` - Add role field to User
- `backend/app/domain/entities.py` - Add role to User entity
- `backend/app/config/settings.py` - Add ADMIN_EMAILS configuration
- `backend/app/api/deps.py` - Add OptionalUser and CurrentAdmin dependencies
- `backend/app/api/documents.py` - Update endpoint authentication
- `backend/app/api/auth.py` - Pass admin_emails to register_user
- `backend/app/api/chat.py` - Support guest sessions
- `backend/app/application/auth_service.py` - Role assignment on registration
- `backend/app/application/document_service.py` - Add public document functions
- `backend/app/application/chat_service.py` - Add guest chat support
- `backend/app/infra/redis/cache.py` - Add guest session methods

### Backend Tests to Modify/Create
- `backend/tests/unit/test_auth_service.py` - Test admin registration
- `backend/tests/unit/test_api_deps.py` - Test OptionalUser, CurrentAdmin
- `backend/tests/contract/test_documents_api.py` - Test public access, admin restrictions
- `backend/tests/contract/test_auth_api.py` - Test role in user response

### Frontend Files to Modify
- `frontend/src/composables/useAuth.js` - Add role tracking
- `frontend/src/composables/useDocuments.js` - Update auth logic
- `frontend/src/components/knowledge/DocumentUpload.vue` - Admin-only UI
- `frontend/src/components/knowledge/DocumentList.vue` - Conditional delete button

### Database Migration
- Create new Alembic migration for `role` column

---

## Task 1: Add Role to User Model and Entity

**Files:**
- Modify: `backend/app/infra/postgres/models.py:12-18`
- Modify: `backend/app/domain/entities.py:9-14`
- Test: `backend/tests/unit/test_db_models.py`

- [ ] **Step 1: Write the failing test for User role field**

Create test in `backend/tests/unit/test_db_models.py`:

```python
def test_user_has_role_field():
    """Test that User model has role field with default 'user'."""
    from app.infra.postgres.models import User

    user = User(
        id="test-id",
        email="test@example.com",
        password_hash="hash",
    )
    assert hasattr(user, "role")
    assert user.role == "user"


def test_user_role_can_be_admin():
    """Test that User role can be set to 'admin'."""
    from app.infra.postgres.models import User

    user = User(
        id="test-id",
        email="admin@example.com",
        password_hash="hash",
        role="admin",
    )
    assert user.role == "admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_db_models.py::test_user_has_role_field -v`
Expected: FAIL with "User has no attribute 'role'"

- [ ] **Step 3: Add role field to User model**

Modify `backend/app/infra/postgres/models.py`:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

- [ ] **Step 4: Add role to User domain entity**

Modify `backend/app/domain/entities.py`:

```python
@dataclass
class User:
    id: UserId
    email: str
    password_hash: str
    role: str
    created_at: datetime
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_db_models.py::test_user_has_role_field backend/tests/unit/test_db_models.py::test_user_role_can_be_admin -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/postgres/models.py backend/app/domain/entities.py backend/tests/unit/test_db_models.py
git commit -m "feat(models): add role field to User model with default 'user'"
```

---

## Task 2: Add ADMIN_EMAILS Configuration

**Files:**
- Modify: `backend/app/config/settings.py:5-76`
- Test: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test for ADMIN_EMAILS**

Add to `backend/tests/unit/test_config.py`:

```python
def test_settings_has_admin_emails():
    """Test that Settings has ADMIN_EMAILS field."""
    from app.config.settings import Settings

    settings = Settings()
    assert hasattr(settings, "ADMIN_EMAILS")
    assert isinstance(settings.ADMIN_EMAILS, list)


def test_settings_parses_admin_emails_from_string():
    """Test that ADMIN_EMAILS is parsed from comma-separated string."""
    from app.config.settings import Settings

    settings = Settings(ADMIN_EMAILS="admin@example.com,another@example.com")
    assert settings.ADMIN_EMAILS == ["admin@example.com", "another@example.com"]


def test_settings_admin_emails_defaults_to_empty():
    """Test that ADMIN_EMAILS defaults to empty list."""
    from app.config.settings import Settings

    settings = Settings()
    assert settings.ADMIN_EMAILS == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_config.py::test_settings_has_admin_emails -v`
Expected: FAIL with "Settings has no attribute 'ADMIN_EMAILS'"

- [ ] **Step 3: Add ADMIN_EMAILS to Settings**

Modify `backend/app/config/settings.py`, add after line 38:

```python
    # Admin configuration
    ADMIN_EMAILS: list[str] = Field(default_factory=list)

    @field_validator("ADMIN_EMAILS", mode="before")
    @classmethod
    def parse_admin_emails(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [email.strip() for email in v.split(",") if email.strip()]
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config/settings.py backend/tests/unit/test_config.py
git commit -m "feat(config): add ADMIN_EMAILS configuration with string parsing"
```

---

## Task 3: Update Auth Service for Role Assignment

**Files:**
- Modify: `backend/app/application/auth_service.py:11-39`
- Test: `backend/tests/unit/test_auth_service.py`

- [ ] **Step 1: Write the failing test for role assignment**

Add to `backend/tests/unit/test_auth_service.py`:

```python
@pytest.mark.asyncio
async def test_register_user_with_admin_role():
    """Test that user gets admin role when email is in admin_emails."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        session=mock_session,
        email="admin@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=["admin@example.com"],
    )

    assert user is not None
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_register_user_with_user_role():
    """Test that user gets user role when email is not in admin_emails."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        session=mock_session,
        email="regular@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=["admin@example.com"],
    )

    assert user is not None
    assert user.role == "user"


@pytest.mark.asyncio
async def test_register_user_default_role_when_no_admin_emails():
    """Test that user gets user role when admin_emails is empty."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_hash_func = MagicMock(return_value="hashed_password_123")

    user = await register_user(
        session=mock_session,
        email="regular@example.com",
        password="password123",
        hash_password_func=mock_hash_func,
        admin_emails=[],
    )

    assert user is not None
    assert user.role == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_auth_service.py::test_register_user_with_admin_role -v`
Expected: FAIL with "unexpected keyword argument 'admin_emails'"

- [ ] **Step 3: Update register_user function**

Modify `backend/app/application/auth_service.py`:

```python
async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    hash_password_func: Callable[[str], str],
    admin_emails: list[str] | None = None,
) -> User:
    """Register a new user with the given email and password.

    Args:
        session: AsyncSession for database operations.
        email: The user's email address.
        password: The user's plain text password.
        hash_password_func: Function to hash the password.
        admin_emails: List of admin email addresses.

    Returns:
        The newly created User instance.
    """
    user_id = str(uuid.uuid4())
    password_hash = hash_password_func(password)

    admin_emails = admin_emails or []
    role = "admin" if email in admin_emails else "user"

    user = User(
        id=user_id,
        email=email,
        password_hash=password_hash,
        role=role,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_auth_service.py::test_register_user_with_admin_role backend/tests/unit/test_auth_service.py::test_register_user_with_user_role backend/tests/unit/test_auth_service.py::test_register_user_default_role_when_no_admin_emails -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/auth_service.py backend/tests/unit/test_auth_service.py
git commit -m "feat(auth): assign admin role based on ADMIN_EMAILS during registration"
```

---

## Task 4: Update Auth API for Role Assignment

**Files:**
- Modify: `backend/app/api/auth.py:54-79`
- Modify: `backend/app/api/auth.py:42-44`
- Test: `backend/tests/contract/test_auth_api.py`

- [ ] **Step 1: Write the failing test for role in response**

Add to `backend/tests/contract/test_auth_api.py`:

```python
@pytest.mark.asyncio
async def test_register_returns_user_with_role():
    """Test that registration returns user with role field."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@example.com", "password": "ValidPass1"},
        )

    assert response.status_code == 201
    data = response.json()
    assert "role" in data
    assert data["role"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/contract/test_auth_api.py::test_register_returns_user_with_role -v`
Expected: FAIL with "KeyError: 'role'" or similar

- [ ] **Step 3: Update UserResponse model and register endpoint**

Modify `backend/app/api/auth.py`:

```python
class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    created_at: str
```

Update the register endpoint:

```python
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: SessionDep,
    _: AuthRateLimitDep,
):
    existing_user = await get_user_by_email(session, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    settings = get_settings()
    user = await register_user(
        session=session,
        email=request.email,
        password=request.password,
        hash_password_func=hash_password,
        admin_emails=settings.ADMIN_EMAILS,
    )
    await session.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/contract/test_auth_api.py::test_register_returns_user_with_role -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/auth.py backend/tests/contract/test_auth_api.py
git commit -m "feat(auth): return role in UserResponse and pass ADMIN_EMAILS to register"
```

---

## Task 5: Add OptionalUser and CurrentAdmin Dependencies

**Files:**
- Modify: `backend/app/api/deps.py:50-100`
- Test: `backend/tests/unit/test_api_deps.py`

- [ ] **Step 1: Write the failing tests for OptionalUser**

Add to `backend/tests/unit/test_api_deps.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_without_token():
    """Test that get_optional_user returns None when no token is provided."""
    from app.api.deps import get_optional_user
    from fastapi.security import HTTPAuthorizationCredentials

    result = await get_optional_user(
        credentials=None,
        jwt_handler=MagicMock(),
        session=AsyncMock(),
        redis=AsyncMock(),
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_optional_user_returns_user_with_valid_token():
    """Test that get_optional_user returns user dict when valid token is provided."""
    from app.api.deps import get_optional_user
    from fastapi.security import HTTPAuthorizationCredentials

    mock_credentials = MagicMock()
    mock_credentials.credentials = "valid_token"

    mock_jwt_handler = MagicMock()
    mock_jwt_handler.get_jti.return_value = "jti-123"
    mock_jwt_handler.verify_token.return_value = "user-123"

    mock_redis = AsyncMock()
    mock_redis.is_token_blacklisted.return_value = False

    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.email = "test@example.com"
    mock_user.role = "user"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    with patch("app.api.deps.get_current_user.__wrapped__", None):
        # We need to call the actual function, not the Depends
        from app.api.deps import get_optional_user

        result = await get_optional_user(
            credentials=mock_credentials,
            jwt_handler=mock_jwt_handler,
            session=mock_session,
            redis=mock_redis,
        )

    assert result is not None
    assert result["id"] == "user-123"
    assert result["role"] == "user"


@pytest.mark.asyncio
async def test_get_current_admin_raises_for_non_admin():
    """Test that get_current_admin raises 403 for non-admin users."""
    from fastapi import HTTPException
    from app.api.deps import get_current_admin

    current_user = {"id": "user-123", "email": "test@example.com", "role": "user"}

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(current_user)

    assert exc_info.value.status_code == 403
    assert "Admin access required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_admin_returns_admin_user():
    """Test that get_current_admin returns admin user dict."""
    from app.api.deps import get_current_admin

    current_user = {"id": "admin-123", "email": "admin@example.com", "role": "admin"}

    result = await get_current_admin(current_user)

    assert result == current_user
    assert result["role"] == "admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_api_deps.py::test_get_optional_user_returns_none_without_token -v`
Expected: FAIL with "cannot import name 'get_optional_user'"

- [ ] **Step 3: Add OptionalUser and CurrentAdmin dependencies**

Modify `backend/app/api/deps.py`, add after line 99 (after CurrentUser definition):

```python
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_db_session),
    redis: RedisCache = Depends(get_redis_cache),
) -> dict | None:
    """Get current user if authenticated, else return None (for guest access)."""
    from redis.exceptions import RedisError

    if credentials is None:
        return None

    token = credentials.credentials

    # Check if token is blacklisted
    jti = jwt_handler.get_jti(token)
    if jti:
        try:
            if await redis.is_token_blacklisted(jti):
                return None
        except RedisError:
            # In development, continue without blacklist check
            pass

    user_id = jwt_handler.verify_token(token)
    if user_id is None:
        return None

    user = await get_user_by_id(session, user_id)
    if user is None:
        return None

    return {"id": user.id, "email": user.email, "role": user.role}


OptionalUser = Annotated[dict | None, Depends(get_optional_user)]


async def get_current_admin(
    current_user: CurrentUser,
) -> dict:
    """Require admin role for endpoint access."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


CurrentAdmin = Annotated[dict, Depends(get_current_admin)]
```

- [ ] **Step 4: Update get_current_user to include role**

Modify `backend/app/api/deps.py`, update the return statement in `get_current_user`:

```python
    return {"id": user.id, "email": user.email, "role": user.role}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_api_deps.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/tests/unit/test_api_deps.py
git commit -m "feat(deps): add OptionalUser and CurrentAdmin dependencies with role support"
```

---

## Task 6: Update Document Service for Public Access

**Files:**
- Modify: `backend/app/application/document_service.py`
- Test: `backend/tests/unit/test_document_service.py`

- [ ] **Step 1: Write the failing tests for public document functions**

Add to `backend/tests/unit/test_document_service.py`:

```python
@pytest.mark.asyncio
async def test_get_all_documents():
    """Test that get_all_documents returns all documents."""
    from app.application.document_service import get_all_documents

    mock_session = AsyncMock()
    mock_doc1 = MagicMock()
    mock_doc1.id = "doc-1"
    mock_doc1.filename = "doc1.pdf"
    mock_doc2 = MagicMock()
    mock_doc2.id = "doc-2"
    mock_doc2.filename = "doc2.pdf"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc1, mock_doc2]
    mock_session.execute.return_value = mock_result

    docs = await get_all_documents(mock_session, limit=20, offset=0)

    assert len(docs) == 2
    assert docs[0].id == "doc-1"
    assert docs[1].id == "doc-2"


@pytest.mark.asyncio
async def test_count_all_documents():
    """Test that count_all_documents returns total count."""
    from app.application.document_service import count_all_documents

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 42
    mock_session.execute.return_value = mock_result

    count = await count_all_documents(mock_session)

    assert count == 42


@pytest.mark.asyncio
async def test_get_document_by_id_public():
    """Test that get_document_by_id_public returns document without user check."""
    from app.application.document_service import get_document_by_id_public

    mock_session = AsyncMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc-123"
    mock_doc.filename = "test.pdf"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_session.execute.return_value = mock_result

    doc = await get_document_by_id_public(mock_session, "doc-123")

    assert doc is not None
    assert doc.id == "doc-123"


@pytest.mark.asyncio
async def test_delete_document_by_id():
    """Test that delete_document_by_id deletes without user check."""
    from app.application.document_service import delete_document_by_id

    mock_session = AsyncMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc-123"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_session.execute.return_value = mock_result
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    success = await delete_document_by_id(mock_session, "doc-123")

    assert success is True
    mock_session.delete.assert_called_once_with(mock_doc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_document_service.py::test_get_all_documents -v`
Expected: FAIL with "cannot import name 'get_all_documents'"

- [ ] **Step 3: Add public document service functions**

Modify `backend/app/application/document_service.py`, add after line 53:

```python
async def get_all_documents(
    session: AsyncSession, limit: int = 20, offset: int = 0
) -> list[Document]:
    """Get all documents with pagination (public access)."""
    stmt = (
        select(Document)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_all_documents(session: AsyncSession) -> int:
    """Count total documents (public access)."""
    stmt = select(func.count()).select_from(Document)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_document_by_id_public(session: AsyncSession, doc_id: str) -> Document | None:
    """Get document by ID without user filter (public access)."""
    stmt = select(Document).where(Document.id == doc_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_document_by_id(session: AsyncSession, doc_id: str) -> bool:
    """Delete document by ID (admin only, no user check)."""
    stmt = select(Document).where(Document.id == doc_id)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_document_service.py::test_get_all_documents backend/tests/unit/test_document_service.py::test_count_all_documents backend/tests/unit/test_document_service.py::test_get_document_by_id_public backend/tests/unit/test_document_service.py::test_delete_document_by_id -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/document_service.py backend/tests/unit/test_document_service.py
git commit -m "feat(documents): add public document access functions without user filtering"
```

---

## Task 7: Update Document API Endpoints

**Files:**
- Modify: `backend/app/api/documents.py:143-253`
- Test: `backend/tests/contract/test_documents_api.py`

- [ ] **Step 1: Write the failing tests for public access and admin restrictions**

Add to `backend/tests/contract/test_documents_api.py`:

```python
@pytest.mark.asyncio
async def test_list_documents_public_access(db_session):
    """Test that documents can be listed without authentication."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_upload_requires_admin(db_session, auth_token):
    """Test that upload requires admin role."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(tmp_path, "rb") as f:
                response = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.txt", f, "text/plain")},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )

        os.unlink(tmp_path)

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_delete_requires_admin(db_session, auth_token):
    """Test that delete requires admin role."""
    from app.application.document_service import create_document

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    try:
        doc = await create_document(db_session, "test.pdf", 1024, TEST_USER_ID)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/documents/{doc.id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 403
    finally:
        app.dependency_overrides = {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/contract/test_documents_api.py::test_list_documents_public_access -v`
Expected: FAIL with 401 Unauthorized

- [ ] **Step 3: Update document API imports**

Modify `backend/app/api/documents.py`, update imports:

```python
from app.api.deps import CurrentAdmin, CurrentUser, OptionalUser, RateLimitDep, SessionDep
```

- [ ] **Step 4: Update list_documents endpoint**

Modify `backend/app/api/documents.py`:

```python
@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: SessionDep,
    _: OptionalUser,  # Optional auth, allows guest access
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> DocumentListResponse:
    documents = await get_all_documents(session, limit=limit, offset=offset)
    total = await count_all_documents(session)
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                error=doc.error,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 5: Update get_document endpoint**

Modify `backend/app/api/documents.py`:

```python
@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(session: SessionDep, doc_id: str, _: OptionalUser) -> DocumentResponse:
    document = await get_document_by_id_public(session, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )
```

- [ ] **Step 6: Update get_document_status endpoint**

Modify `backend/app/api/documents.py`:

```python
@router.get("/{doc_id}/status", response_model=IngestionJobResponse)
async def get_document_status(session: SessionDep, doc_id: str, _: OptionalUser) -> IngestionJobResponse:
    document = await get_document_by_id_public(session, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ingestion_job = await get_ingestion_job_by_document(session, doc_id)
    if ingestion_job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return IngestionJobResponse(
        id=ingestion_job.id,
        document_id=ingestion_job.document_id,
        status=ingestion_job.status,
        chunk_count=ingestion_job.chunk_count,
        error=ingestion_job.error,
        created_at=ingestion_job.created_at.isoformat(),
        updated_at=ingestion_job.updated_at.isoformat(),
    )
```

- [ ] **Step 7: Update upload_document endpoint**

Modify `backend/app/api/documents.py`:

```python
@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_admin: CurrentAdmin,  # Changed from CurrentUser
    _: RateLimitDep,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    file: UploadFile = File(...),
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    document = await create_document(session, file.filename, file_size, current_admin["id"])
    await session.commit()

    try:
        text_content = content.decode("utf-8")
        background_tasks.add_task(
            process_document_background,
            document.id,
            text_content,
            file.filename,
            ingestion_service,
        )
    except UnicodeDecodeError:
        pass

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )
```

- [ ] **Step 8: Update delete_document endpoint**

Modify `backend/app/api/documents.py`:

```python
@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document_endpoint(session: SessionDep, doc_id: str, current_admin: CurrentAdmin) -> DeleteResponse:
    success = await delete_document_by_id(session, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return DeleteResponse(status="deleted", document_id=doc_id)
```

- [ ] **Step 9: Add missing imports**

Modify `backend/app/api/documents.py`, add to imports:

```python
from app.application.document_service import (
    count_all_documents,
    count_documents_by_user,
    create_document,
    delete_document_by_id,
    delete_document,
    get_all_documents,
    get_document_by_id,
    get_document_by_id_public,
    get_documents_by_user,
    get_ingestion_job_by_document,
    update_document_status,
)
```

- [ ] **Step 10: Run test to verify it passes**

Run: `uv run pytest backend/tests/contract/test_documents_api.py -v`
Expected: All tests PASS

- [ ] **Step 11: Commit**

```bash
git add backend/app/api/documents.py backend/tests/contract/test_documents_api.py
git commit -m "feat(documents): update API for public read and admin-only write access"
```

---

## Task 8: Add Guest Session Support to Redis Cache

**Files:**
- Modify: `backend/app/infra/redis/cache.py`
- Test: `backend/tests/unit/test_redis_cache.py`

- [ ] **Step 1: Write the failing tests for guest session methods**

Add to `backend/tests/unit/test_redis_cache.py`:

```python
@pytest.mark.asyncio
async def test_set_guest_session():
    """Test setting a guest chat session."""
    from app.infra.redis.cache import RedisCache

    cache = RedisCache("redis://localhost:6379")
    # Mock the redis client
    cache.client = AsyncMock()

    messages = [{"role": "user", "content": "Hello"}]
    await cache.set_guest_session("guest-123", messages, ttl=3600)

    cache.client.setex.assert_called_once()
    call_args = cache.client.setex.call_args
    assert "guest:guest-123:session" in call_args[0]


@pytest.mark.asyncio
async def test_get_guest_session():
    """Test getting a guest chat session."""
    from app.infra.redis.cache import RedisCache
    import json

    cache = RedisCache("redis://localhost:6379")
    cache.client = AsyncMock()
    cache.client.get.return_value = json.dumps([{"role": "user", "content": "Hello"}])

    messages = await cache.get_guest_session("guest-123")

    assert messages is not None
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_get_guest_session_not_found():
    """Test getting a non-existent guest session."""
    from app.infra.redis.cache import RedisCache

    cache = RedisCache("redis://localhost:6379")
    cache.client = AsyncMock()
    cache.client.get.return_value = None

    messages = await cache.get_guest_session("nonexistent")

    assert messages is None


@pytest.mark.asyncio
async def test_delete_guest_session():
    """Test deleting a guest chat session."""
    from app.infra.redis.cache import RedisCache

    cache = RedisCache("redis://localhost:6379")
    cache.client = AsyncMock()

    await cache.delete_guest_session("guest-123")

    cache.client.delete.assert_called_once()
    call_args = cache.client.delete.call_args
    assert "guest:guest-123:session" in call_args[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_redis_cache.py::test_set_guest_session -v`
Expected: FAIL with "RedisCache has no attribute 'set_guest_session'"

- [ ] **Step 3: Add guest session methods to RedisCache**

Modify `backend/app/infra/redis/cache.py`, add after line 69:

```python
    async def set_guest_session(self, session_id: str, messages: list[dict], ttl: int = 3600) -> None:
        """Store guest chat session with TTL."""
        key = f"guest:{session_id}:session"
        await self.client.setex(key, ttl, json.dumps(messages))

    async def get_guest_session(self, session_id: str) -> list[dict] | None:
        """Get guest chat session."""
        key = f"guest:{session_id}:session"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def delete_guest_session(self, session_id: str) -> None:
        """Delete guest chat session."""
        key = f"guest:{session_id}:session"
        await self.client.delete(key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_redis_cache.py::test_set_guest_session backend/tests/unit/test_redis_cache.py::test_get_guest_session backend/tests/unit/test_redis_cache.py::test_get_guest_session_not_found backend/tests/unit/test_redis_cache.py::test_delete_guest_session -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/redis/cache.py backend/tests/unit/test_redis_cache.py
git commit -m "feat(redis): add guest session storage methods with TTL"
```

---

## Task 9: Add Guest Chat Service

**Files:**
- Modify: `backend/app/application/chat_service.py`
- Test: `backend/tests/unit/test_chat_service_streaming.py`

- [ ] **Step 1: Write the failing test for guest chat**

Add to `backend/tests/unit/test_chat_service_streaming.py`:

```python
@pytest.mark.asyncio
async def test_ask_question_stream_guest():
    """Test guest chat streaming without DB persistence."""
    from app.application.chat_service import ask_question_stream_guest
    from unittest.mock import MagicMock, AsyncMock
    import json

    mock_redis = AsyncMock()
    mock_redis.get_guest_session.return_value = None

    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test answer",
        "documents": [],
        "retrieval_score": 0.8,
    })

    mock_llm = MagicMock()

    messages = []
    async for event in ask_question_stream_guest(
        session_id="guest-123",
        message="Hello",
        rag_agent=mock_rag_agent,
        llm_provider=mock_llm,
        redis=mock_redis,
    ):
        messages.append(event)

    # Should have thinking and done events
    event_types = [json.loads(m.split("data: ")[1])["type"] for m in messages if m.startswith("data:")]
    assert "thinking" in event_types
    assert "done" in event_types

    # Should store session in Redis
    mock_redis.set_guest_session.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/test_chat_service_streaming.py::test_ask_question_stream_guest -v`
Expected: FAIL with "cannot import name 'ask_question_stream_guest'"

- [ ] **Step 3: Add guest chat service function**

Modify `backend/app/application/chat_service.py`, add after line 261:

```python
async def ask_question_stream_guest(
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProvider,
    redis: RedisCache,
) -> AsyncGenerator[str, None]:
    """Stream chat response for guest users (no DB persistence)."""
    trace_id = str(uuid.uuid4())

    yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': '正在检索...'})}\n\n"

    try:
        result = await rag_agent.run(message)

        doc_count = len(result.get("documents", []))
        retrieval_score = result.get("retrieval_score", 0)

        retrieve_msg = f"检索完成，找到 {doc_count} 个相关文档"
        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'retrieve', 'content': retrieve_msg})}\n\n"

        eval_msg = f"检索评分: {retrieval_score:.2f}"
        yield f"data: {json.dumps({'type': 'thinking', 'stage': 'evaluate', 'content': eval_msg})}\n\n"

        answer = result.get("answer", "")

        for chunk in [answer[i : i + 50] for i in range(0, len(answer), 50)]:
            yield f"data: {json.dumps({'type': 'chunk', 'stage': 'generate', 'content': chunk})}\n\n"

        # Store session context for guest (no DB persistence)
        existing_messages = await redis.get_guest_session(session_id) or []
        existing_messages.append({"role": "user", "content": message})
        existing_messages.append({"role": "assistant", "content": answer})
        await redis.set_guest_session(session_id, existing_messages, ttl=3600)

        sources = []
        for doc in result.get("documents", []):
            sources.append(
                {
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "score": doc.metadata.get("rrf_score"),
                }
            )

        yield f"data: {json.dumps({'type': 'done', 'stage': 'generate', 'trace_id': trace_id, 'sources': sources})}\n\n"
    except Exception as e:
        sanitized = _sanitize_error_message(e)
        yield f"data: {json.dumps({'type': 'error', 'code': 'RAG_ERROR', 'message': sanitized})}\n\n"
```

- [ ] **Step 4: Add RedisCache import**

Modify `backend/app/application/chat_service.py`, add to imports:

```python
from app.infra.redis.cache import RedisCache
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/test_chat_service_streaming.py::test_ask_question_stream_guest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/chat_service.py backend/tests/unit/test_chat_service_streaming.py
git commit -m "feat(chat): add guest chat service with Redis session storage"
```

---

## Task 10: Update Chat API for Guest Access

**Files:**
- Modify: `backend/app/api/chat.py`
- Test: `backend/tests/contract/test_chat_api.py`

- [ ] **Step 1: Write the failing test for guest chat**

Add to `backend/tests/contract/test_chat_api.py`:

```python
@pytest.mark.asyncio
async def test_guest_can_send_chat_message(db_session):
    """Test that guests can send chat messages without authentication."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import AsyncMock, MagicMock, patch

    async def override_get_db():
        yield db_session

    app.dependency_overrides[original_get_db_session] = override_get_db

    # Mock RAG agent
    mock_rag_agent = MagicMock()
    mock_rag_agent.run = AsyncMock(return_value={
        "answer": "Test response",
        "documents": [],
        "retrieval_score": 0.8,
    })

    with patch.object(app.state, 'rag_agent', mock_rag_agent):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chat/guest/message",
                    json={"message": "Hello"},
                )

            assert response.status_code == 200
        finally:
            app.dependency_overrides = {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/contract/test_chat_api.py::test_guest_can_send_chat_message -v`
Expected: FAIL with 404 Not Found

- [ ] **Step 3: Add guest chat endpoint**

Modify `backend/app/api/chat.py`, add after imports:

```python
from app.api.deps import OptionalUser, RedisCacheDep
```

Add new endpoint after existing endpoints:

```python
@router.post("/guest/message")
async def send_guest_message(
    request: MessageRequest,
    redis: RedisCacheDep,
    rag_agent = Depends(get_rag_agent),
    llm_provider = Depends(get_llm_provider),
) -> StreamingResponse:
    """Send a message and get streaming response (guest mode, no auth required)."""
    session_id = request.session_id or str(uuid.uuid4())

    return StreamingResponse(
        ask_question_stream_guest(
            session_id=session_id,
            message=request.message,
            rag_agent=rag_agent,
            llm_provider=llm_provider,
            redis=redis,
        ),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 4: Update imports in chat.py**

Modify `backend/app/api/chat.py`:

```python
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, StreamingResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, OptionalUser, RateLimitDep, RedisCacheDep, SessionDep
from app.application.chat_service import (
    ask_question_stream,
    ask_question_stream_guest,
    ask_question_stream_with_rag,
)
from app.infra.providers.llm import LLMProvider
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest backend/tests/contract/test_chat_api.py::test_guest_can_send_chat_message -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/chat.py backend/tests/contract/test_chat_api.py
git commit -m "feat(chat): add guest chat endpoint without authentication requirement"
```

---

## Task 11: Update Frontend Auth Composable

**Files:**
- Modify: `frontend/src/composables/useAuth.js`

- [ ] **Step 1: Read current useAuth.js**

Read the file to understand current structure.

- [ ] **Step 2: Add role tracking to useAuth**

Modify `frontend/src/composables/useAuth.js`:

```javascript
import { ref, computed } from 'vue'
import { api } from '../api/index.js'

const user = ref(null)
const userRole = ref(null)
const token = ref(localStorage.getItem('token'))
const isAuthenticated = computed(() => !!token.value)
const isAdmin = computed(() => userRole.value === 'admin')

export function useAuth() {
  async function login(email, password) {
    const result = await api.auth.login(email, password)
    if (result.ok) {
      token.value = result.data.access_token
      localStorage.setItem('token', result.data.access_token)
      // Fetch user info to get role
      await fetchUser()
    }
    return result
  }

  async function register(email, password) {
    const result = await api.auth.register(email, password)
    if (result.ok) {
      // Auto-login after registration
      return await login(email, password)
    }
    return result
  }

  async function fetchUser() {
    if (!token.value) return { ok: false }
    const result = await api.auth.me()
    if (result.ok) {
      user.value = result.data
      userRole.value = result.data.role
    }
    return result
  }

  function logout() {
    token.value = null
    user.value = null
    userRole.value = null
    localStorage.removeItem('token')
  }

  // Initialize user on load
  if (token.value && !user.value) {
    fetchUser()
  }

  return {
    user,
    userRole,
    token,
    isAuthenticated,
    isAdmin,
    login,
    register,
    logout,
    fetchUser,
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useAuth.js
git commit -m "feat(frontend): add role tracking and isAdmin computed property"
```

---

## Task 12: Update Frontend Documents Composable

**Files:**
- Modify: `frontend/src/composables/useDocuments.js`

- [ ] **Step 1: Read current useDocuments.js**

Read the file to understand current structure.

- [ ] **Step 2: Update useDocuments for public access**

Modify `frontend/src/composables/useDocuments.js`:

```javascript
import { ref } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'

const documents = ref([])
const loading = ref(false)
const error = ref(null)

export function useDocuments() {
  const { isAdmin, isAuthenticated } = useAuth()

  function handleError(result) {
    if (result.status === 401) {
      error.value = '请先登录'
    } else if (result.status === 403) {
      error.value = '需要管理员权限'
    } else {
      error.value = result.data?.detail || '请求失败'
    }
    return result
  }

  async function fetchDocuments() {
    // Public access - no authentication required
    loading.value = true
    error.value = null
    const result = await api.documents.list()
    loading.value = false

    if (!result.ok) {
      return handleError(result)
    }

    documents.value = result.data.documents
    return result
  }

  async function uploadDocument(file) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    if (!isAdmin.value) {
      error.value = '需要管理员权限'
      return { ok: false, status: 403, data: { detail: '需要管理员权限' } }
    }

    const result = await api.documents.upload(file)
    if (!result.ok) {
      return handleError(result)
    }

    documents.value.unshift(result.data)
    return result
  }

  async function deleteDocument(docId) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    if (!isAdmin.value) {
      error.value = '需要管理员权限'
      return { ok: false, status: 403, data: { detail: '需要管理员权限' } }
    }

    const result = await api.documents.delete(docId)
    if (!result.ok) {
      return handleError(result)
    }

    documents.value = documents.value.filter(d => d.id !== docId)
    return result
  }

  async function getDocumentStatus(docId) {
    // Public access - no authentication required
    const result = await api.documents.status(docId)
    if (!result.ok) {
      return handleError(result)
    }
    return result
  }

  return {
    documents,
    loading,
    error,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    getDocumentStatus,
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useDocuments.js
git commit -m "feat(frontend): update documents for public read and admin-only write"
```

---

## Task 13: Update Frontend DocumentUpload Component

**Files:**
- Modify: `frontend/src/components/knowledge/DocumentUpload.vue`

- [ ] **Step 1: Update DocumentUpload for admin-only**

Modify `frontend/src/components/knowledge/DocumentUpload.vue`:

```vue
<script setup>
import { useDocuments } from '../../composables/useDocuments.js'
import { useAuth } from '../../composables/useAuth.js'
import { ElMessage } from 'element-plus'
import { UploadFilled, Lock } from '@element-plus/icons-vue'

const { uploadDocument } = useDocuments()
const { isAdmin, isAuthenticated } = useAuth()

async function handleUpload(options) {
  const result = await uploadDocument(options.file)
  if (result.ok) {
    ElMessage.success('文档上传成功')
  } else {
    ElMessage.error(`上传失败: ${result.data.detail || '未知错误'}`)
  }
}

function handleExceed() {
  ElMessage.warning('一次只能上传一个文件')
}
</script>

<template>
  <div style="padding: 16px;">
    <!-- Admin upload section -->
    <el-upload
      v-if="isAdmin"
      :auto-upload="true"
      :show-file-list="false"
      :limit="1"
      :on-exceed="handleExceed"
      :http-request="handleUpload"
      accept=".txt,.md,.pdf"
      drag
    >
      <el-icon style="font-size: 48px; color: #909399;"><UploadFilled /></el-icon>
      <div style="margin-top: 8px; color: #606266;">
        拖拽文件到此处或 <em style="color: #409EFF;">点击上传</em>
      </div>
      <template #tip>
        <div style="color: #909399; font-size: 12px; margin-top: 8px;">
          支持 .txt, .md, .pdf 文件，最大 50MB
        </div>
      </template>
    </el-upload>

    <!-- Non-admin message -->
    <div v-else style="text-align: center; padding: 32px; color: #909399;">
      <el-icon style="font-size: 32px; margin-bottom: 8px;"><Lock /></el-icon>
      <div>仅管理员可上传文档</div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/knowledge/DocumentUpload.vue
git commit -m "feat(frontend): show upload UI only for admin users"
```

---

## Task 14: Update Frontend DocumentList Component

**Files:**
- Modify: `frontend/src/components/knowledge/DocumentList.vue`

- [ ] **Step 1: Update DocumentList for conditional delete**

Modify `frontend/src/components/knowledge/DocumentList.vue`:

```vue
<script setup>
import { onMounted } from 'vue'
import { useDocuments } from '../../composables/useDocuments.js'
import { useAuth } from '../../composables/useAuth.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, View, Delete, Loading } from '@element-plus/icons-vue'

const { documents, loading, fetchDocuments, deleteDocument, getDocumentStatus } = useDocuments()
const { isAdmin } = useAuth()

const statusMap = {
  processing: { type: 'warning', text: '处理中' },
  completed: { type: 'success', text: '已完成' },
  failed: { type: 'danger', text: '失败' },
}

async function handleDelete(doc) {
  try {
    await ElMessageBox.confirm('确定删除此文档？', '确认删除', { type: 'warning' })
    const result = await deleteDocument(doc.id)
    if (result.ok) {
      ElMessage.success('删除成功')
    } else {
      ElMessage.error('删除失败')
    }
  } catch {
    // 用户取消
  }
}

async function handleViewStatus(doc) {
  const result = await getDocumentStatus(doc.id)
  if (result.ok) {
    const data = result.data
    ElMessage.success(`文档状态: ${data.status}, 分块数: ${data.chunk_count}`)
  } else {
    ElMessage.error('获取状态失败')
  }
}

onMounted(fetchDocuments)
</script>

<template>
  <div style="flex: 1; overflow-y: auto;">
    <div v-if="loading" style="padding: 20px; text-align: center;">
      <el-icon class="is-loading" style="font-size: 24px;"><Loading /></el-icon>
    </div>
    <div v-else-if="documents.length === 0" style="padding: 20px; text-align: center; color: #909399;">
      暂无文档
    </div>
    <div v-else>
      <div
        v-for="doc in documents"
        :key="doc.id"
        style="padding: 12px 16px; border-bottom: 1px solid #e4e7ed;"
      >
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="flex: 1; overflow: hidden;">
            <div style="font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <el-icon style="margin-right: 4px;"><Document /></el-icon>
              {{ doc.filename }}
            </div>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ new Date(doc.created_at).toLocaleString('zh-CN') }}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-tag :type="statusMap[doc.status]?.type || 'info'" size="small">
              {{ statusMap[doc.status]?.text || doc.status }}
            </el-tag>
            <el-button-group size="small">
              <el-tooltip content="查看状态" placement="top">
                <el-button @click="handleViewStatus(doc)" :icon="View" />
              </el-tooltip>
              <!-- Delete button only for admin -->
              <el-tooltip v-if="isAdmin" content="删除文档" placement="top">
                <el-button @click="handleDelete(doc)" :icon="Delete" type="danger" />
              </el-tooltip>
            </el-button-group>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/knowledge/DocumentList.vue
git commit -m "feat(frontend): show delete button only for admin users"
```

---

## Task 15: Create Database Migration

**Files:**
- Create: New Alembic migration file

- [ ] **Step 1: Create migration for role column**

Run: `uv run alembic revision -m "add_user_role_column"`
This creates a new migration file in `backend/alembic/versions/`.

- [ ] **Step 2: Edit migration file**

Edit the created migration file:

```python
"""add user role column

Revision ID: <generated>
Revises: <previous>
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '<generated>'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(20), nullable=False, server_default='user'))


def downgrade() -> None:
    op.drop_column('users', 'role')
```

- [ ] **Step 3: Run migration**

Run: `uv run alembic upgrade head`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/*.py
git commit -m "feat(db): add migration for user role column"
```

---

## Task 16: Run All Tests and Fix Issues

**Files:**
- Various test fixes

- [ ] **Step 1: Run all unit and contract tests**

Run: `uv run pytest backend/tests/unit backend/tests/contract -v`

- [ ] **Step 2: Fix any failing tests**

Review test output and fix any issues. Common issues:
- Tests may need to add `role` field when creating users
- Tests expecting old behavior need updates

- [ ] **Step 3: Commit fixes**

```bash
git add backend/tests/
git commit -m "fix(tests): update tests for role-based access control"
```

---

## Task 17: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add ADMIN_EMAILS to .env.example**

Add to `.env.example`:

```
# Admin configuration (comma-separated list of admin email addresses)
ADMIN_EMAILS=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add ADMIN_EMAILS to environment example"
```

---

## Task 18: Final Integration Test

**Files:**
- None (verification only)

- [ ] **Step 1: Run all tests**

Run: `uv run pytest backend/tests/unit backend/tests/contract -v`

Expected: All tests PASS

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`

Expected: Build succeeds

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete document access control implementation"
```
