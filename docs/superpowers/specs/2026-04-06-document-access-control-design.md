# Document System Access Control Design

**Date**: 2026-04-06  
**Status**: Approved

## Overview

Transform the document system from user-private to public-read with admin-only write access.

### Current State
- Any authenticated user can upload documents
- Each user only sees their own uploaded documents
- RAG retrieves documents regardless of ownership (no user filtering)
- No role/permission system exists

### Target State
- All documents public-readable (including guests)
- RAG retrieves all documents for all users
- Only admins can upload/modify/delete documents
- Role-based access control with `admin` and `user` roles
- Guest chat supported with temporary sessions

## Architecture Changes

### 1. Database & Domain

**User Model** (`backend/app/infra/postgres/models.py`):
```python
class User(Base):
    __tablename__ = "users"
    # existing fields...
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
```

**Domain Entity** (`backend/app/domain/entities.py`):
```python
@dataclass
class User:
    id: UserId
    email: str
    password_hash: str
    role: str  # "admin" or "user"
    created_at: datetime
```

**Migration**:
- Add `role` column with default `"user"`
- Existing users migrated to `"user"` role

### 2. Configuration

**Environment Variable**:
```
ADMIN_EMAILS=admin@example.com,another-admin@example.com
```

**Settings** (`backend/app/config/settings.py`):
```python
class Settings(BaseSettings):
    ADMIN_EMAILS: list[str] = Field(default_factory=list)
    
    @field_validator('ADMIN_EMAILS', mode='before')
    @classmethod
    def parse_admin_emails(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [email.strip() for email in v.split(',') if email.strip()]
        return v
```

### 3. Authentication & Authorization

**New Dependencies** (`backend/app/api/deps.py`):

```python
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_db_session),
    redis: RedisCache = Depends(get_redis_cache),
) -> dict | None:
    """Get current user if authenticated, else return None (for guest access)."""
    if credentials is None:
        return None
    # Same validation as get_current_user, return None on any failure

OptionalUser = Annotated[dict | None, Depends(get_optional_user)]

async def get_current_admin(
    current_user: CurrentUser,
) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user

CurrentAdmin = Annotated[dict, Depends(get_current_admin)]
```

**Auth Service Changes** (`backend/app/application/auth_service.py`):
```python
async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    hash_password_func: Callable,
    admin_emails: list[str],  # NEW
) -> User:
    role = "admin" if email in admin_emails else "user"
    # create user with role
```

**Updated CurrentUser Response**:
```python
return {"id": user.id, "email": user.email, "role": user.role}
```

### 4. Document API Changes

**Endpoint Permissions** (`backend/app/api/documents.py`):

| Endpoint | Current Auth | New Auth |
|----------|-------------|----------|
| `POST /upload` | `CurrentUser` | `CurrentAdmin` |
| `GET /` | `CurrentUser` | `OptionalUser` |
| `GET /{doc_id}` | `CurrentUser` + user filter | `OptionalUser` |
| `GET /{doc_id}/status` | `CurrentUser` + user filter | `OptionalUser` |
| `DELETE /{doc_id}` | `CurrentUser` + user filter | `CurrentAdmin` |

**Service Layer** (`backend/app/application/document_service.py`):

Remove user_id filtering, add public functions:

```python
async def get_all_documents(session: AsyncSession, limit: int, offset: int) -> list[Document]:
    """Get all documents (public access)."""
    stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def count_all_documents(session: AsyncSession) -> int:
    """Count all documents."""
    stmt = select(func.count()).select_from(Document)
    result = await session.execute(stmt)
    return result.scalar() or 0

async def get_document_by_id_public(session: AsyncSession, doc_id: str) -> Document | None:
    """Get document by ID without user filter."""
    stmt = select(Document).where(Document.id == doc_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def delete_document_by_id(session: AsyncSession, doc_id: str) -> bool:
    """Delete document by ID (admin only)."""
    stmt = select(Document).where(Document.id == doc_id)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        return False
    await session.delete(document)
    return True
```

### 5. Chat & RAG Changes

**Chat API** (`backend/app/api/chat.py`):
- Use `OptionalUser` for chat endpoints
- Generate temporary session ID for guests
- Store guest sessions in Redis with TTL (1 hour)

**Guest Chat Service** (`backend/app/application/chat_service.py`):
```python
async def ask_question_stream_guest(
    session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: LLMProvider,
    redis: RedisCache,
) -> AsyncGenerator[str, None]:
    """Stream chat response for guest users (no DB persistence)."""
    # Retrieve guest session from Redis if exists
    # Run RAG query (no user filtering)
    # Yield SSE events
    # Store updated context in Redis with TTL
```

**RAG Retrieval**: No changes needed - already retrieves all documents.

### 6. Frontend Changes

**Auth Composable** (`frontend/src/composables/useAuth.js`):
```javascript
const userRole = ref(null)
const isAdmin = computed(() => userRole.value === 'admin')
```

**Documents Composable** (`frontend/src/composables/useDocuments.js`):
- Remove authentication checks for `fetchDocuments()`
- Add admin check for `uploadDocument()` and `deleteDocument()`

**UI Components**:
- `DocumentUpload.vue`: Show only for admin users
- `DocumentList.vue`: Remove delete button for non-admin users
- `ChatPanel.vue`: Support guest mode with temporary session ID

### 7. Testing

**Unit Tests**:
- Admin registration when email in `ADMIN_EMAILS`
- Regular user registration
- `get_optional_user` returns `None` for guests
- `get_current_admin` raises 403 for non-admin

**Contract Tests**:
- Guest can list documents
- Guest can view document details
- Guest cannot upload (401)
- Regular user cannot upload (403)
- Admin can upload/delete

### 8. Error Responses

| Scenario | Status | Detail |
|----------|--------|--------|
| Guest tries upload | 401 | "Not authenticated" |
| Regular user tries upload | 403 | "Admin access required" |
| Non-admin tries delete | 403 | "Admin access required" |

## Implementation Order

1. Database migration (add `role` column)
2. Settings configuration (`ADMIN_EMAILS`)
3. Domain entity updates
4. Auth service changes (role assignment on register)
5. New dependencies (`OptionalUser`, `CurrentAdmin`)
6. Document service refactoring
7. Document API changes
8. Chat service changes (guest support)
9. Frontend updates
10. Tests

## Files to Modify

### Backend
- `backend/app/infra/postgres/models.py` - Add role field
- `backend/app/domain/entities.py` - Add role to User entity
- `backend/app/config/settings.py` - Add ADMIN_EMAILS
- `backend/app/api/deps.py` - Add OptionalUser, CurrentAdmin
- `backend/app/api/documents.py` - Update endpoint auth
- `backend/app/api/auth.py` - Pass admin_emails to register
- `backend/app/api/chat.py` - Support guest sessions
- `backend/app/application/auth_service.py` - Role assignment
- `backend/app/application/document_service.py` - Remove user filtering
- `backend/app/application/chat_service.py` - Guest chat support
- `backend/app/infra/redis/cache.py` - Guest session storage

### Frontend
- `frontend/src/composables/useAuth.js` - Add role tracking
- `frontend/src/composables/useDocuments.js` - Update auth logic
- `frontend/src/components/knowledge/DocumentUpload.vue` - Admin-only UI
- `frontend/src/components/knowledge/DocumentList.vue` - Remove delete for non-admin
- `frontend/src/components/ChatPanel.vue` - Guest mode support

### Migration
- New Alembic migration for `role` column

### Tests
- Update existing tests
- Add new tests for role-based access
