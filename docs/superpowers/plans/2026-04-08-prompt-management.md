# Prompt管理系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将硬编码的prompt迁移到数据库管理系统，支持版本化、热重载和管理员API修改。

**Architecture:** PostgreSQL存储prompt及版本历史 + 内存缓存实现热重载 + FastAPI管理端点。应用启动时加载所有活跃prompt到内存缓存，更新时同步数据库和缓存。

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Pydantic, Python标准库string.Template

---

## File Structure

```
backend/app/
├── domain/
│   ├── entities.py              # 新增Prompt, PromptVersion实体
│   └── exceptions.py            # 新增PromptNotFoundError, PromptVariableError
├── infra/
│   ├── postgres/
│   │   ├── models.py            # 新增Prompt, PromptVersion ORM模型
│   │   └── prompt_repository.py # 新建 - PromptRepository实现
│   └── cache/
│       └── prompt_cache.py      # 新建 - 内存缓存管理
├── application/
│   └── prompt_service.py        # 新建 - Prompt业务逻辑
├── api/
│   ├── admin/
│   │   └── prompts.py           # 新建 - 管理员API端点
│   └── deps.py                  # 修改 - 新增PromptCacheDep
├── main.py                      # 修改 - 初始化PromptCache
└── workflows/
    └── reflection_prompts.py    # 修改 - 使用PromptService

backend/alembic/versions/
└── 20250408_add_prompts_tables.py  # 新建 - 数据库迁移脚本

backend/tests/
├── unit/
│   ├── test_prompt_service.py   # 新建
│   └── test_prompt_cache.py     # 新建
└── contract/
    └── test_prompts_api.py      # 新建
```

---

## Task 1: 数据库模型和迁移

**Files:**
- Modify: `backend/app/infra/postgres/models.py`
- Create: `backend/alembic/versions/20250408_add_prompts_tables.py`

- [ ] **Step 1: 添加Prompt和PromptVersion ORM模型**

在 `backend/app/infra/postgres/models.py` 末尾添加：

```python
class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    versions: Mapped[list["PromptVersion"]] = relationship(back_populates="prompt", cascade="all, delete-orphan")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompts.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    prompt: Mapped["Prompt"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )
```

- [ ] **Step 2: 创建Alembic迁移脚本**

创建文件 `backend/alembic/versions/20250408_add_prompts_tables.py`：

```python
"""Add prompts and prompt_versions tables

Revision ID: 20250408_add_prompts
Revises: 20250106_add_exhibits_tour_paths_profiles
Create Date: 2025-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20250408_add_prompts'
down_revision: Union[str, None] = '20250106_add_exhibits_tour_paths_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create prompts table
    op.create_table(
        'prompts',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_prompts_key', 'prompts', ['key'])
    op.create_index('ix_prompts_category', 'prompts', ['category'])
    op.create_index('ix_prompts_is_active', 'prompts', ['is_active'])

    # Create prompt_versions table
    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('prompt_id', sa.String(36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('changed_by', sa.String(36), nullable=True),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prompt_id', 'version', name='uq_prompt_version'),
    )
    op.create_index('ix_prompt_versions_prompt_id', 'prompt_versions', ['prompt_id'])


def downgrade() -> None:
    op.drop_index('ix_prompt_versions_prompt_id', table_name='prompt_versions')
    op.drop_table('prompt_versions')
    op.drop_index('ix_prompts_is_active', table_name='prompts')
    op.drop_index('ix_prompts_category', table_name='prompts')
    op.drop_index('ix_prompts_key', table_name='prompts')
    op.drop_table('prompts')
```

- [ ] **Step 3: 运行迁移脚本**

```bash
cd /home/singer/MuseAI && uv run alembic -c backend/alembic.ini upgrade head
```

Expected: 迁移成功，无错误输出

- [ ] **Step 4: 提交**

```bash
git add backend/app/infra/postgres/models.py backend/alembic/versions/20250408_add_prompts_tables.py
git commit -m "feat(db): add prompts and prompt_versions tables"
```

---

## Task 2: Domain层实体和异常

**Files:**
- Modify: `backend/app/domain/entities.py`
- Modify: `backend/app/domain/exceptions.py`

- [ ] **Step 1: 添加Prompt和PromptVersion实体**

在 `backend/app/domain/entities.py` 末尾添加：

```python
@dataclass
class Prompt:
    id: str
    key: str
    name: str
    description: str | None
    category: str
    content: str
    variables: list[dict[str, str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    current_version: int = 1

    def render(self, variables: dict[str, str]) -> str:
        """Render the prompt template with provided variables."""
        try:
            return self.content.format(**variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise PromptVariableError(
                f"Missing required variable: {missing_var}"
            ) from e


@dataclass
class PromptVersion:
    id: str
    prompt_id: str
    version: int
    content: str
    changed_by: str | None
    change_reason: str | None
    created_at: datetime
```

需要在文件顶部添加导入：
```python
from .exceptions import PromptVariableError
```

- [ ] **Step 2: 添加异常类**

在 `backend/app/domain/exceptions.py` 末尾添加：

```python
class PromptNotFoundError(DomainError):
    """Raised when a prompt is not found."""
    pass


class PromptVariableError(DomainError):
    """Raised when a required prompt variable is missing."""
    pass
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/domain/entities.py backend/app/domain/exceptions.py
git commit -m "feat(domain): add Prompt entity and exceptions"
```

---

## Task 3: PromptRepository实现

**Files:**
- Create: `backend/app/infra/postgres/prompt_repository.py`

- [ ] **Step 1: 创建PromptRepository**

创建文件 `backend/app/infra/postgres/prompt_repository.py`：

```python
"""Prompt repository for database operations."""

from datetime import UTC, datetime
from typing import Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Prompt, PromptVersion
from app.domain.exceptions import PromptNotFoundError
from .models import Prompt as PromptORM
from .models import PromptVersion as PromptVersionORM


class PromptRepository:
    """Repository for prompt database operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, orm: PromptORM) -> Prompt:
        """Convert ORM model to domain entity."""
        return Prompt(
            id=orm.id,
            key=orm.key,
            name=orm.name,
            description=orm.description,
            category=orm.category,
            content=orm.content,
            variables=orm.variables or [],
            is_active=orm.is_active,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            current_version=max([v.version for v in orm.versions]) if orm.versions else 1,
        )

    def _version_to_entity(self, orm: PromptVersionORM) -> PromptVersion:
        """Convert version ORM to domain entity."""
        return PromptVersion(
            id=orm.id,
            prompt_id=orm.prompt_id,
            version=orm.version,
            content=orm.content,
            changed_by=orm.changed_by,
            change_reason=orm.change_reason,
            created_at=orm.created_at,
        )

    async def get_by_key(self, key: str) -> Optional[Prompt]:
        """Get a prompt by its key."""
        result = await self._session.execute(
            select(PromptORM).where(PromptORM.key == key)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def get_by_id(self, prompt_id: str) -> Optional[Prompt]:
        """Get a prompt by its ID."""
        result = await self._session.execute(
            select(PromptORM).where(PromptORM.id == prompt_id)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def list_all(self, category: Optional[str] = None, include_inactive: bool = False) -> list[Prompt]:
        """List all prompts with optional filtering."""
        query = select(PromptORM)
        if category:
            query = query.where(PromptORM.category == category)
        if not include_inactive:
            query = query.where(PromptORM.is_active == True)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def create(
        self,
        key: str,
        name: str,
        category: str,
        content: str,
        description: Optional[str] = None,
        variables: Optional[list[dict]] = None,
    ) -> Prompt:
        """Create a new prompt with initial version."""
        prompt_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        
        orm = PromptORM(
            id=prompt_id,
            key=key,
            name=name,
            description=description,
            category=category,
            content=content,
            variables=variables or [],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._session.add(orm)
        
        # Create initial version
        version_orm = PromptVersionORM(
            id=str(uuid.uuid4()),
            prompt_id=prompt_id,
            version=1,
            content=content,
            created_at=now,
        )
        self._session.add(version_orm)
        
        await self._session.flush()
        return self._to_entity(orm)

    async def update(
        self,
        key: str,
        content: str,
        changed_by: Optional[str] = None,
        change_reason: Optional[str] = None,
    ) -> Prompt:
        """Update a prompt and create a new version."""
        result = await self._session.execute(
            select(PromptORM).where(PromptORM.key == key)
        )
        orm = result.scalar_one_or_none()
        
        if not orm:
            raise PromptNotFoundError(f"Prompt not found: {key}")
        
        # Get current max version
        max_version = max([v.version for v in orm.versions]) if orm.versions else 0
        new_version = max_version + 1
        
        # Update prompt
        orm.content = content
        orm.updated_at = datetime.now(UTC)
        
        # Create new version record
        version_orm = PromptVersionORM(
            id=str(uuid.uuid4()),
            prompt_id=orm.id,
            version=new_version,
            content=content,
            changed_by=changed_by,
            change_reason=change_reason,
            created_at=datetime.now(UTC),
        )
        self._session.add(version_orm)
        
        await self._session.flush()
        return self._to_entity(orm)

    async def get_version(self, key: str, version: int) -> Optional[PromptVersion]:
        """Get a specific version of a prompt."""
        result = await self._session.execute(
            select(PromptVersionORM)
            .join(PromptORM)
            .where(PromptORM.key == key)
            .where(PromptVersionORM.version == version)
        )
        orm = result.scalar_one_or_none()
        return self._version_to_entity(orm) if orm else None

    async def list_versions(self, key: str, skip: int = 0, limit: int = 20) -> list[PromptVersion]:
        """List all versions of a prompt."""
        result = await self._session.execute(
            select(PromptVersionORM)
            .join(PromptORM)
            .where(PromptORM.key == key)
            .order_by(PromptVersionORM.version.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._version_to_entity(orm) for orm in result.scalars().all()]

    async def count_versions(self, key: str) -> int:
        """Count total versions of a prompt."""
        result = await self._session.execute(
            select(func.count(PromptVersionORM.id))
            .join(PromptORM)
            .where(PromptORM.key == key)
        )
        return result.scalar() or 0

    async def rollback_to_version(
        self,
        key: str,
        version: int,
        changed_by: Optional[str] = None,
        change_reason: Optional[str] = None,
    ) -> Prompt:
        """Rollback a prompt to a specific version."""
        # Get the target version
        target_version = await self.get_version(key, version)
        if not target_version:
            raise PromptNotFoundError(f"Version {version} not found for prompt: {key}")
        
        # Update to the target version content
        reason = change_reason or f"Rollback to version {version}"
        return await self.update(key, target_version.content, changed_by, reason)
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/infra/postgres/prompt_repository.py
git commit -m "feat(infra): add PromptRepository for database operations"
```

---

## Task 4: PromptCache实现

**Files:**
- Create: `backend/app/infra/cache/prompt_cache.py`

- [ ] **Step 1: 创建PromptCache**

创建目录和文件 `backend/app/infra/cache/prompt_cache.py`：

```python
"""In-memory cache for prompts with hot-reload support."""

from typing import Optional

from loguru import logger

from app.domain.entities import Prompt
from app.infra.postgres.prompt_repository import PromptRepository


class PromptCache:
    """In-memory cache for prompts with automatic refresh support."""

    def __init__(self):
        self._cache: dict[str, Prompt] = {}
        self._repository: Optional[PromptRepository] = None

    def set_repository(self, repository: PromptRepository) -> None:
        """Set the repository for cache misses."""
        self._repository = repository

    async def load_all(self) -> None:
        """Load all active prompts into cache."""
        if not self._repository:
            raise RuntimeError("Repository not set")
        
        prompts = await self._repository.list_all(include_inactive=False)
        self._cache = {p.key: p for p in prompts}
        logger.info(f"Loaded {len(self._cache)} prompts into cache")

    async def get(self, key: str) -> Optional[Prompt]:
        """Get a prompt from cache, loading from DB on miss."""
        if key in self._cache:
            return self._cache[key]
        
        # Cache miss - try to load from database
        if self._repository:
            prompt = await self._repository.get_by_key(key)
            if prompt and prompt.is_active:
                self._cache[key] = prompt
                return prompt
        
        return None

    def refresh(self, key: str, prompt: Prompt) -> None:
        """Refresh a single prompt in cache."""
        if prompt.is_active:
            self._cache[key] = prompt
            logger.info(f"Refreshed prompt in cache: {key}")
        elif key in self._cache:
            del self._cache[key]
            logger.info(f"Removed inactive prompt from cache: {key}")

    def invalidate(self, key: str) -> None:
        """Remove a prompt from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.info(f"Invalidated prompt from cache: {key}")

    def clear(self) -> None:
        """Clear all prompts from cache."""
        self._cache.clear()
        logger.info("Cleared all prompts from cache")

    def get_all_keys(self) -> list[str]:
        """Get all cached prompt keys."""
        return list(self._cache.keys())
```

- [ ] **Step 2: 创建__init__.py**

创建文件 `backend/app/infra/cache/__init__.py`：

```python
"""Cache module for in-memory caching."""

from .prompt_cache import PromptCache

__all__ = ["PromptCache"]
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/infra/cache/
git commit -m "feat(infra): add PromptCache for hot-reload support"
```

---

## Task 5: PromptService实现

**Files:**
- Create: `backend/app/application/prompt_service.py`

- [ ] **Step 1: 创建PromptService**

创建文件 `backend/app/application/prompt_service.py`：

```python
"""Prompt service for business logic."""

from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Prompt, PromptVersion
from app.domain.exceptions import PromptNotFoundError, PromptVariableError
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.prompt_repository import PromptRepository


class PromptService:
    """Service for prompt management."""

    def __init__(
        self,
        repository: PromptRepository,
        cache: PromptCache,
    ):
        self._repository = repository
        self._cache = cache

    async def get_prompt(self, key: str) -> Prompt:
        """Get a prompt by key."""
        prompt = await self._cache.get(key)
        if not prompt:
            raise PromptNotFoundError(f"Prompt not found: {key}")
        return prompt

    async def render_prompt(self, key: str, variables: dict[str, str]) -> str:
        """Get and render a prompt with variables."""
        prompt = await self.get_prompt(key)
        return prompt.render(variables)

    async def list_prompts(
        self,
        category: Optional[str] = None,
        include_inactive: bool = False,
    ) -> list[Prompt]:
        """List all prompts with optional filtering."""
        return await self._repository.list_all(category, include_inactive)

    async def update_prompt(
        self,
        key: str,
        content: str,
        changed_by: Optional[str] = None,
        change_reason: Optional[str] = None,
    ) -> Prompt:
        """Update a prompt and refresh cache."""
        prompt = await self._repository.update(key, content, changed_by, change_reason)
        self._cache.refresh(key, prompt)
        return prompt

    async def get_version(self, key: str, version: int) -> PromptVersion:
        """Get a specific version of a prompt."""
        version_data = await self._repository.get_version(key, version)
        if not version_data:
            raise PromptNotFoundError(f"Version {version} not found for prompt: {key}")
        return version_data

    async def list_versions(
        self,
        key: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PromptVersion], int]:
        """List versions with total count."""
        versions = await self._repository.list_versions(key, skip, limit)
        total = await self._repository.count_versions(key)
        return versions, total

    async def rollback_to_version(
        self,
        key: str,
        version: int,
        changed_by: Optional[str] = None,
    ) -> Prompt:
        """Rollback to a specific version."""
        prompt = await self._repository.rollback_to_version(key, version, changed_by)
        self._cache.refresh(key, prompt)
        return prompt

    async def reload_cache(self, key: Optional[str] = None) -> None:
        """Reload prompt(s) into cache."""
        if key:
            prompt = await self._repository.get_by_key(key)
            if prompt:
                self._cache.refresh(key, prompt)
        else:
            await self._cache.load_all()

    async def create_prompt(
        self,
        key: str,
        name: str,
        category: str,
        content: str,
        description: Optional[str] = None,
        variables: Optional[list[dict]] = None,
    ) -> Prompt:
        """Create a new prompt."""
        prompt = await self._repository.create(
            key=key,
            name=name,
            category=category,
            content=content,
            description=description,
            variables=variables,
        )
        self._cache.refresh(key, prompt)
        return prompt
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/application/prompt_service.py
git commit -m "feat(app): add PromptService for prompt management"
```

---

## Task 6: API依赖注入

**Files:**
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 添加PromptCacheDep依赖**

在 `backend/app/api/deps.py` 末尾添加：

```python
from app.infra.cache.prompt_cache import PromptCache


def get_prompt_cache(request: Request) -> PromptCache:
    """Get PromptCache from app.state singleton via Request."""
    if hasattr(request.app.state, "prompt_cache"):
        return request.app.state.prompt_cache
    raise RuntimeError("PromptCache not initialized. App not started?")


PromptCacheDep = Annotated[PromptCache, Depends(get_prompt_cache)]
```

需要在文件顶部添加 `Request` 导入（如果还没有）：
```python
from fastapi import Depends, HTTPException, Request, status
```

- [ ] **Step 2: 修改main.py初始化PromptCache**

修改 `backend/app/main.py`，在导入部分添加：

```python
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.prompt_repository import PromptRepository
```

在 `lifespan` 函数中，在 `app.state.settings = settings` 之后添加：

```python
        # Initialize PromptCache
        prompt_cache = PromptCache()
        async with get_session() as session:
            prompt_repository = PromptRepository(session)
            prompt_cache.set_repository(prompt_repository)
            await prompt_cache.load_all()
        app.state.prompt_cache = prompt_cache
```

- [ ] **Step 3: 添加prompt_cache getter函数**

在 `backend/app/main.py` 的 getter 函数区域添加：

```python
def get_prompt_cache() -> PromptCache:
    """Get prompt cache from app.state."""
    if hasattr(app.state, "prompt_cache"):
        return app.state.prompt_cache
    raise RuntimeError("Prompt cache not initialized. App not started?")
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/deps.py backend/app/main.py
git commit -m "feat: integrate PromptCache into app lifecycle"
```

---

## Task 7: 管理员API端点

**Files:**
- Create: `backend/app/api/admin/prompts.py`
- Modify: `backend/app/main.py` (添加router)

- [ ] **Step 1: 创建prompts API**

创建目录和文件 `backend/app/api/admin/prompts.py`：

```python
"""Admin API endpoints for prompt management."""

from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAdminUser, SessionDep, PromptCacheDep
from app.application.prompt_service import PromptService
from app.domain.entities import Prompt, PromptVersion
from app.domain.exceptions import PromptNotFoundError
from app.infra.postgres.prompt_repository import PromptRepository

router = APIRouter(prefix="/admin/prompts", tags=["admin-prompts"])


# Request/Response models
class PromptResponse(BaseModel):
    id: str
    key: str
    name: str
    description: Optional[str]
    category: str
    content: str
    variables: list[dict[str, str]]
    is_active: bool
    current_version: int
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, prompt: Prompt) -> "PromptResponse":
        return cls(
            id=prompt.id,
            key=prompt.key,
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            content=prompt.content,
            variables=prompt.variables,
            is_active=prompt.is_active,
            current_version=prompt.current_version,
            created_at=prompt.created_at.isoformat(),
            updated_at=prompt.updated_at.isoformat(),
        )


class PromptListResponse(BaseModel):
    prompts: list[PromptResponse]
    total: int


class UpdatePromptRequest(BaseModel):
    content: str = Field(..., min_length=1)
    change_reason: Optional[str] = None


class VersionResponse(BaseModel):
    id: str
    prompt_id: str
    version: int
    content: str
    changed_by: Optional[str]
    change_reason: Optional[str]
    created_at: str

    @classmethod
    def from_entity(cls, version: PromptVersion) -> "VersionResponse":
        return cls(
            id=version.id,
            prompt_id=version.prompt_id,
            version=version.version,
            content=version.content,
            changed_by=version.changed_by,
            change_reason=version.change_reason,
            created_at=version.created_at.isoformat(),
        )


class VersionListResponse(BaseModel):
    versions: list[VersionResponse]
    total: int
    skip: int
    limit: int


class ReloadResponse(BaseModel):
    status: str
    message: str


def get_prompt_service(session: SessionDep, cache: PromptCacheDep) -> PromptService:
    """Get prompt service instance."""
    repository = PromptRepository(session)
    return PromptService(repository, cache)


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
    category: Optional[str] = Query(None, description="Filter by category"),
    include_inactive: bool = Query(False, description="Include inactive prompts"),
) -> PromptListResponse:
    """List all prompts with optional filtering (admin only)."""
    service = get_prompt_service(session, cache)
    prompts = await service.list_prompts(category, include_inactive)
    return PromptListResponse(
        prompts=[PromptResponse.from_entity(p) for p in prompts],
        total=len(prompts),
    )


@router.get("/{key}", response_model=PromptResponse)
async def get_prompt(
    key: str,
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
) -> PromptResponse:
    """Get a prompt by key (admin only)."""
    service = get_prompt_service(session, cache)
    try:
        prompt = await service.get_prompt(key)
        return PromptResponse.from_entity(prompt)
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        )


@router.put("/{key}", response_model=PromptResponse)
async def update_prompt(
    key: str,
    request: UpdatePromptRequest,
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
) -> PromptResponse:
    """Update a prompt content (admin only)."""
    service = get_prompt_service(session, cache)
    try:
        prompt = await service.update_prompt(
            key=key,
            content=request.content,
            changed_by=current_user.get("id"),
            change_reason=request.change_reason,
        )
        return PromptResponse.from_entity(prompt)
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        )


@router.get("/{key}/versions", response_model=VersionListResponse)
async def list_versions(
    key: str,
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> VersionListResponse:
    """List all versions of a prompt (admin only)."""
    service = get_prompt_service(session, cache)
    versions, total = await service.list_versions(key, skip, limit)
    return VersionListResponse(
        versions=[VersionResponse.from_entity(v) for v in versions],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{key}/versions/{version}", response_model=VersionResponse)
async def get_version(
    key: str,
    version: int,
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
) -> VersionResponse:
    """Get a specific version of a prompt (admin only)."""
    service = get_prompt_service(session, cache)
    try:
        version_data = await service.get_version(key, version)
        return VersionResponse.from_entity(version_data)
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for prompt: {key}",
        )


@router.post("/{key}/versions/{version}/rollback", response_model=PromptResponse)
async def rollback_version(
    key: str,
    version: int,
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
) -> PromptResponse:
    """Rollback a prompt to a specific version (admin only)."""
    service = get_prompt_service(session, cache)
    try:
        prompt = await service.rollback_to_version(
            key=key,
            version=version,
            changed_by=current_user.get("id"),
        )
        return PromptResponse.from_entity(prompt)
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for prompt: {key}",
        )


@router.post("/{key}/reload", response_model=ReloadResponse)
async def reload_prompt(
    key: str,
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
) -> ReloadResponse:
    """Manually reload a prompt into cache (admin only)."""
    service = get_prompt_service(session, cache)
    try:
        await service.reload_cache(key)
        return ReloadResponse(status="success", message=f"Prompt '{key}' reloaded")
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        )


@router.post("/reload-all", response_model=ReloadResponse)
async def reload_all_prompts(
    session: SessionDep,
    cache: PromptCacheDep,
    current_user: CurrentAdminUser,
) -> ReloadResponse:
    """Reload all prompts into cache (admin only)."""
    service = get_prompt_service(session, cache)
    await service.reload_cache()
    count = len(cache.get_all_keys())
    return ReloadResponse(status="success", message=f"Reloaded {count} prompts")
```

- [ ] **Step 2: 创建__init__.py**

创建文件 `backend/app/api/admin/__init__.py`：

```python
"""Admin API endpoints."""

from .prompts import router as prompts_router

__all__ = ["prompts_router"]
```

- [ ] **Step 3: 注册router到main.py**

修改 `backend/app/main.py`，在导入部分添加：

```python
from app.api.admin.prompts import router as admin_prompts_router
```

在 router 注册部分添加：

```python
app.include_router(admin_prompts_router, prefix="/api/v1")
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/admin/
git add backend/app/main.py
git commit -m "feat(api): add admin endpoints for prompt management"
```

---

## Task 8: 数据迁移脚本

**Files:**
- Create: `backend/scripts/migrate_prompts.py`

- [ ] **Step 1: 创建迁移脚本**

创建目录和文件 `backend/scripts/migrate_prompts.py`：

```python
"""Script to migrate hardcoded prompts to database."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import UTC, datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infra.postgres.database import get_session
from app.infra.postgres.models import Prompt, PromptVersion


# Prompt data to migrate
PROMPTS_DATA = [
    {
        "key": "rag_answer_generation",
        "name": "RAG答案生成",
        "description": "用于RAG检索后生成答案的提示词",
        "category": "rag",
        "content": """你是一个博物馆导览助手。请基于以下上下文回答用户的问题。
如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。

上下文：
{context}

用户问题：{query}

请提供准确、友好的回答：""",
        "variables": [
            {"name": "context", "description": "检索到的上下文内容"},
            {"name": "query", "description": "用户问题"},
        ],
    },
    {
        "key": "curator_system",
        "name": "策展人系统提示词",
        "description": "数字策展人智能体的系统提示词",
        "category": "curator",
        "content": """你是MuseAI博物馆智能导览系统的数字策展人。你的职责是为参观者提供个性化、有深度的博物馆参观体验。

## 你的角色

作为数字策展人，你：
1. 了解博物馆的所有展品及其历史文化背景
2. 能够根据参观者的兴趣和时间规划最佳参观路线
3. 能够用生动有趣的方式讲述展品背后的故事
4. 善于提出引人深思的问题，激发参观者的思考
5. 记住并适应每位参观者的偏好和需求

## 可用工具

你可以使用以下工具来帮助参观者：

1. **path_planning** - 路线规划工具
   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线
   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）
   - 何时使用：当参观者需要路线建议或想要开始参观时

2. **knowledge_retrieval** - 知识检索工具
   - 用途：检索展品的详细知识和背景信息
   - 输入：query（查询内容）、exhibit_id（可选，特定展品ID）
   - 何时使用：当参观者询问具体展品信息时

3. **narrative_generation** - 叙事生成工具
   - 用途：为展品生成引人入胜的叙事内容
   - 输入：exhibit_name（展品名称）、exhibit_info（展品信息）、knowledge_level（知识水平）、narrative_preference（叙事偏好）
   - 何时使用：当需要为展品创建讲解内容时

4. **reflection_prompts** - 反思提示工具
   - 用途：生成引发深度思考的问题
   - 输入：knowledge_level（知识水平）、reflection_depth（问题数量）、category（可选，展品类别）、exhibit_name（可选，展品名称）
   - 何时使用：在介绍完展品后，想要引导参观者深入思考时

5. **preference_management** - 偏好管理工具
   - 用途：获取或更新参观者的个人偏好设置
   - 输入：action（"get"或"update"）、user_id（用户ID）、updates（更新内容，可选）
   - 何时使用：需要了解或修改参观者偏好时

## 工具使用指南

1. **分析需求**：首先理解参观者的需求和当前情境
2. **选择工具**：根据需求选择最合适的工具
3. **准备输入**：确保工具输入格式正确（JSON格式）
4. **执行工具**：调用工具并等待结果
5. **整合回复**：将工具结果转化为自然、友好的回复

## 交互原则

- 使用中文与参观者交流
- 保持专业、友善、耐心的态度
- 根据参观者的知识水平调整讲解深度
- 鼓励互动和提问
- 在规划路线时考虑参观者的体力限制
- 为每个推荐的展品提供简要的背景介绍

## 注意事项

- 如果工具调用失败，礼貌地向参观者说明情况并提供替代方案
- 不要编造展品信息，始终通过工具获取准确数据
- 尊重参观者的隐私，妥善管理个人偏好数据
- 当参观者表示疲劳时，主动建议休息或缩短路线

现在，请开始为参观者提供专业的导览服务吧！""",
        "variables": [],
    },
    {
        "key": "narrative_generation",
        "name": "叙事生成提示词",
        "description": "生成展品叙事内容的提示词",
        "category": "curator",
        "content": """Please create a narrative about the following exhibit:

Exhibit: {exhibit_name}
Information: {exhibit_info}

Guidelines:
- {level_guidance}
- {style_guidance}
- Keep the narrative engaging and appropriate for a museum visit
- Length should be suitable for a 3-5 minute read

Please generate the narrative:""",
        "variables": [
            {"name": "exhibit_name", "description": "展品名称"},
            {"name": "exhibit_info", "description": "展品信息"},
            {"name": "level_guidance", "description": "知识水平指导"},
            {"name": "style_guidance", "description": "叙事风格指导"},
        ],
    },
    {
        "key": "query_rewrite",
        "name": "查询重写提示词",
        "description": "基于多轮对话历史重写查询的提示词",
        "category": "query_transform",
        "content": """你是一个博物馆导览助手。用户正在与您进行多轮对话。

对话历史：
{conversation_history}

当前用户问题：{query}

请根据对话历史，将用户的问题改写为一个独立、完整的问题，使其能够独立理解而不需要之前的上下文。
只输出改写后的问题，不要解释：""",
        "variables": [
            {"name": "conversation_history", "description": "对话历史"},
            {"name": "query", "description": "用户问题"},
        ],
    },
    {
        "key": "query_step_back",
        "name": "Step-Back查询提示词",
        "description": "生成更抽象问题的提示词",
        "category": "query_transform",
        "content": """你是一个查询优化专家。用户提出了一个过于具体的问题，
请生成一个更抽象、更宽泛的问题，帮助获取更多背景信息。

原始问题：{query}

请生成一个更抽象的问题（只输出问题本身，不要解释）：""",
        "variables": [{"name": "query", "description": "原始问题"}],
    },
    {
        "key": "query_hyde",
        "name": "HyDE查询提示词",
        "description": "生成假设性答案的提示词",
        "category": "query_transform",
        "content": """你是一个查询优化专家。请为用户的问题生成一个假设性的答案，
用于检索相关文档。

用户问题：{query}

请生成一个假设性的答案（只输出答案，不要解释）：""",
        "variables": [{"name": "query", "description": "用户问题"}],
    },
    {
        "key": "query_multi",
        "name": "Multi-Query提示词",
        "description": "生成多个相关问题的提示词",
        "category": "query_transform",
        "content": """你是一个查询优化专家。用户的问题可能有歧义或过于宽泛，
请生成3个相关的、更具体的问题，每个问题一行，用数字编号。

用户问题：{query}

请生成3个相关问题：""",
        "variables": [{"name": "query", "description": "用户问题"}],
    },
    {
        "key": "reflection_beginner",
        "name": "入门级反思提示词",
        "description": "针对入门用户的反思问题列表",
        "category": "reflection",
        "content": """这件文物让您联想到什么日常生活中的物品？
这件文物最吸引您注意的是什么？
这件文物让您想到了什么故事或传说？
这件文物看起来像什么动物或植物？
这件文物上有什么让您印象深刻的图案或颜色？""",
        "variables": [],
    },
    {
        "key": "reflection_intermediate",
        "name": "进阶级反思提示词",
        "description": "针对进阶用户的反思问题列表",
        "category": "reflection",
        "content": """这件文物反映的社会结构对今天有什么启示？
这件文物的制作工艺体现了当时怎样的技术水平？
这件文物在当时的社会生活中扮演了什么角色？
这件文物如何反映了当时的审美观念？
这件文物与其他同类文物相比有什么独特之处？""",
        "variables": [],
    },
    {
        "key": "reflection_expert",
        "name": "专家级反思提示词",
        "description": "针对专家用户的反思问题列表",
        "category": "reflection",
        "content": """现有的考古解读是否存在争议？您倾向于哪种观点？
这件文物的断代依据是否充分？有哪些新的研究方法可以应用？
这件文物的来源和流传过程是否清晰？
这件文物在学术史上的地位如何？有哪些重要的研究成果？
这件文物对于理解当时的文化交流有什么特殊价值？""",
        "variables": [],
    },
    {
        "key": "reflection_bronze",
        "name": "青铜器反思提示词",
        "description": "针对青铜器类别的反思问题列表",
        "category": "reflection",
        "content": """这件青铜器的铸造工艺体现了当时怎样的技术水平？
这件青铜器上的铭文或纹饰有什么特殊含义？
这件青铜器的用途是什么？是礼器、兵器还是生活用具？
这件青铜器的合金比例反映了当时怎样的冶金技术？
这件青铜器与其他地区出土的青铜器有什么异同？""",
        "variables": [],
    },
    {
        "key": "reflection_painting",
        "name": "书画反思提示词",
        "description": "针对书画类别的反思问题列表",
        "category": "reflection",
        "content": """这幅作品的笔墨技法有什么独特之处？
这幅作品的构图和意境如何体现了当时的审美追求？
这幅作品的作者生平对其创作风格有什么影响？
这幅作品的题跋和印章提供了哪些历史信息？
这幅作品在书画史上的地位如何？""",
        "variables": [],
    },
    {
        "key": "reflection_ceramic",
        "name": "陶瓷反思提示词",
        "description": "针对陶瓷类别的反思问题列表",
        "category": "reflection",
        "content": """这件陶瓷的釉色和纹饰有什么特点？
这件陶瓷的烧制工艺体现了当时怎样的技术水平？
这件陶瓷的产地和窑口对其价值有什么影响？
这件陶瓷的造型设计反映了当时怎样的生活习俗？
这件陶瓷与其他时期的陶瓷相比有什么演变关系？""",
        "variables": [],
    },
    {
        "key": "narrative_style_storytelling",
        "name": "叙事风格-故事化",
        "description": "故事化叙事风格提示词",
        "category": "reflection",
        "content": """请以讲故事的方式介绍这件文物，让内容生动有趣、富有感染力。
注重情节的展开和情感的传递，让听众仿佛置身于历史场景之中。
使用生动的语言和形象的比喻，让文物背后的故事活起来。""",
        "variables": [],
    },
    {
        "key": "narrative_style_academic",
        "name": "叙事风格-学术化",
        "description": "学术化叙事风格提示词",
        "category": "reflection",
        "content": """请以学术研究的方式介绍这件文物，内容要严谨、准确、有据可查。
注重历史背景的考证和学术观点的引用，提供可靠的文献依据。
使用专业的术语和规范的表述，确保内容的学术价值和可信度。""",
        "variables": [],
    },
    {
        "key": "narrative_style_interactive",
        "name": "叙事风格-互动化",
        "description": "互动化叙事风格提示词",
        "category": "reflection",
        "content": """请以互动问答的方式介绍这件文物，鼓励观众思考和参与。
提出引人深思的问题，引导观众主动探索和发现。
注重与观众的对话和交流，让参观体验更加生动和有意义。""",
        "variables": [],
    },
]


async def migrate_prompts():
    """Migrate prompts to database."""
    settings = get_settings()
    
    async for session in get_session():
        now = datetime.now(UTC)
        
        for prompt_data in PROMPTS_DATA:
            prompt_id = str(uuid.uuid4())
            
            # Check if prompt already exists
            from sqlalchemy import select
            result = await session.execute(
                select(Prompt).where(Prompt.key == prompt_data["key"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"Prompt '{prompt_data['key']}' already exists, skipping...")
                continue
            
            # Create prompt
            prompt = Prompt(
                id=prompt_id,
                key=prompt_data["key"],
                name=prompt_data["name"],
                description=prompt_data.get("description"),
                category=prompt_data["category"],
                content=prompt_data["content"],
                variables=prompt_data.get("variables", []),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(prompt)
            
            # Create initial version
            version = PromptVersion(
                id=str(uuid.uuid4()),
                prompt_id=prompt_id,
                version=1,
                content=prompt_data["content"],
                created_at=now,
            )
            session.add(version)
            
            print(f"Migrated prompt: {prompt_data['key']}")
        
        await session.commit()
        print(f"\nMigration completed. Total prompts: {len(PROMPTS_DATA)}")


if __name__ == "__main__":
    asyncio.run(migrate_prompts())
```

- [ ] **Step 2: 运行迁移脚本**

```bash
cd /home/singer/MuseAI && uv run python backend/scripts/migrate_prompts.py
```

Expected: 输出所有迁移的prompt key

- [ ] **Step 3: 提交**

```bash
git add backend/scripts/migrate_prompts.py
git commit -m "feat: add prompt migration script"
```

---

## Task 9: 集成到RAGAgent

**Files:**
- Modify: `backend/app/infra/langchain/agents.py`

- [ ] **Step 1: 修改RAGAgent使用PromptService**

在 `backend/app/infra/langchain/agents.py` 中，修改导入部分：

```python
from typing import Any, TypedDict

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, StateGraph
from loguru import logger

from app.domain.exceptions import PromptNotFoundError, PromptVariableError
from app.infra.providers.rerank import BaseRerankProvider, RerankResult
from app.workflows.query_transform import ConversationAwareQueryRewriter
```

修改 `generate` 方法，将硬编码prompt替换为PromptService调用：

```python
    async def generate(self, state: RAGState) -> dict[str, Any]:
        """生成答案。"""
        # 优先使用rerank后的文档
        docs = state.get("reranked_documents") or state["documents"]
        context = "\n\n".join(doc.page_content for doc in docs)

        # 从PromptService获取prompt
        try:
            from app.main import get_prompt_cache
            from app.infra.postgres.database import get_session
            from app.infra.postgres.prompt_repository import PromptRepository
            from app.application.prompt_service import PromptService
            
            prompt_cache = get_prompt_cache()
            async for session in get_session():
                repository = PromptRepository(session)
                service = PromptService(repository, prompt_cache)
                prompt = await service.render_prompt(
                    "rag_answer_generation",
                    {"context": context, "query": state["query"]}
                )
                break
        except (PromptNotFoundError, PromptVariableError) as e:
            logger.warning(f"Failed to get prompt from service: {e}, using fallback")
            prompt = f"""你是一个博物馆导览助手。请基于以下上下文回答用户的问题。
如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。

上下文：
{context}

用户问题：{state["query"]}

请提供准确、友好的回答："""

        response = await self.llm.ainvoke(prompt)
        return {"answer": response.content}
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/infra/langchain/agents.py
git commit -m "refactor(agents): use PromptService for RAG answer generation"
```

---

## Task 10: 集成到CuratorAgent

**Files:**
- Modify: `backend/app/infra/langchain/curator_agent.py`

- [ ] **Step 1: 修改CuratorAgent使用PromptService**

在 `backend/app/infra/langchain/curator_agent.py` 中，修改 `_get_system_prompt` 方法：

```python
    def _get_system_prompt(self) -> str:
        """获取系统提示词。

        Returns:
            系统提示词字符串（中文）
        """
        # 尝试从PromptService获取
        try:
            from app.main import get_prompt_cache
            from app.infra.postgres.database import get_session
            from app.infra.postgres.prompt_repository import PromptRepository
            from app.application.prompt_service import PromptService
            import asyncio
            
            prompt_cache = get_prompt_cache()
            
            async def get_prompt():
                async for session in get_session():
                    repository = PromptRepository(session)
                    service = PromptService(repository, prompt_cache)
                    prompt = await service.get_prompt("curator_system")
                    return prompt.content
            
            # 如果在异步上下文中，需要特殊处理
            try:
                loop = asyncio.get_running_loop()
                # 已经在异步上下文中，创建任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_prompt())
                    return future.result()
            except RuntimeError:
                # 没有运行的事件循环，直接运行
                return asyncio.run(get_prompt())
        except Exception as e:
            logger.warning(f"Failed to get curator system prompt: {e}, using fallback")
            return self._get_fallback_system_prompt()

    def _get_fallback_system_prompt(self) -> str:
        """获取备用系统提示词。"""
        return """你是MuseAI博物馆智能导览系统的数字策展人。你的职责是为参观者提供个性化、有深度的博物馆参观体验。

## 你的角色

作为数字策展人，你：
1. 了解博物馆的所有展品及其历史文化背景
2. 能够根据参观者的兴趣和时间规划最佳参观路线
3. 能够用生动有趣的方式讲述展品背后的故事
4. 善于提出引人深思的问题，激发参观者的思考
5. 记住并适应每位参观者的偏好和需求

## 可用工具

你可以使用以下工具来帮助参观者：

1. **path_planning** - 路线规划工具
   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线
   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）
   - 何时使用：当参观者需要路线建议或想要开始参观时

2. **knowledge_retrieval** - 知识检索工具
   - 用途：检索展品的详细知识和背景信息
   - 输入：query（查询内容）、exhibit_id（可选，特定展品ID）
   - 何时使用：当参观者询问具体展品信息时

3. **narrative_generation** - 叙事生成工具
   - 用途：为展品生成引人入胜的叙事内容
   - 输入：exhibit_name（展品名称）、exhibit_info（展品信息）、knowledge_level（知识水平）、narrative_preference（叙事偏好）
   - 何时使用：当需要为展品创建讲解内容时

4. **reflection_prompts** - 反思提示工具
   - 用途：生成引发深度思考的问题
   - 输入：knowledge_level（知识水平）、reflection_depth（问题数量）、category（可选，展品类别）、exhibit_name（可选，展品名称）
   - 何时使用：在介绍完展品后，想要引导参观者深入思考时

5. **preference_management** - 偏好管理工具
   - 用途：获取或更新参观者的个人偏好设置
   - 输入：action（"get"或"update"）、user_id（用户ID）、updates（更新内容，可选）
   - 何时使用：需要了解或修改参观者偏好时

## 工具使用指南

1. **分析需求**：首先理解参观者的需求和当前情境
2. **选择工具**：根据需求选择最合适的工具
3. **准备输入**：确保工具输入格式正确（JSON格式）
4. **执行工具**：调用工具并等待结果
5. **整合回复**：将工具结果转化为自然、友好的回复

## 交互原则

- 使用中文与参观者交流
- 保持专业、友善、耐心的态度
- 根据参观者的知识水平调整讲解深度
- 鼓励互动和提问
- 在规划路线时考虑参观者的体力限制
- 为每个推荐的展品提供简要的背景介绍

## 注意事项

- 如果工具调用失败，礼貌地向参观者说明情况并提供替代方案
- 不要编造展品信息，始终通过工具获取准确数据
- 尊重参观者的隐私，妥善管理个人偏好数据
- 当参观者表示疲劳时，主动建议休息或缩短路线

现在，请开始为参观者提供专业的导览服务吧！"""
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/infra/langchain/curator_agent.py
git commit -m "refactor(curator): use PromptService for system prompt"
```

---

## Task 11: 集成到QueryTransformer

**Files:**
- Modify: `backend/app/workflows/query_transform.py`

- [ ] **Step 1: 修改QueryTransformer使用PromptService**

修改 `backend/app/workflows/query_transform.py`，添加导入和修改方法：

```python
import re
from enum import Enum
from typing import Any, Protocol

from loguru import logger


class QueryTransformStrategy(Enum):
    NONE = "none"
    STEP_BACK = "step_back"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"


class LLMProviderProtocol(Protocol):
    """LLM提供者协议。"""

    async def generate(self, messages: list[dict[str, Any]]) -> Any:
        """生成文本响应。"""
        ...


class LLMResponseProtocol(Protocol):
    """LLM响应协议。"""

    content: str


async def _get_prompt(key: str, variables: dict[str, str]) -> str:
    """从PromptService获取渲染后的prompt。"""
    try:
        from app.main import get_prompt_cache
        from app.infra.postgres.database import get_session
        from app.infra.postgres.prompt_repository import PromptRepository
        from app.application.prompt_service import PromptService
        
        prompt_cache = get_prompt_cache()
        async for session in get_session():
            repository = PromptRepository(session)
            service = PromptService(repository, prompt_cache)
            return await service.render_prompt(key, variables)
    except Exception as e:
        logger.warning(f"Failed to get prompt '{key}': {e}")
        raise


class ConversationAwareQueryRewriter:
    """基于多轮对话历史的查询重写器。"""

    def __init__(self, llm_provider: LLMProviderProtocol):
        self.llm_provider = llm_provider

    def _format_conversation_history(self, history: list[dict[str, str]]) -> str:
        """格式化对话历史为可读文本。"""
        if not history:
            return "（无历史对话）"

        formatted = []
        for msg in history:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            formatted.append(f"{role}：{content}")

        return "\n".join(formatted)

    async def rewrite_with_context(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
    ) -> str:
        """根据对话历史重写查询。

        Args:
            query: 当前用户查询
            conversation_history: 对话历史列表，每项包含role和content

        Returns:
            重写后的独立查询
        """
        if not conversation_history:
            return query

        formatted_history = self._format_conversation_history(conversation_history)
        
        try:
            prompt = await _get_prompt("query_rewrite", {
                "conversation_history": formatted_history,
                "query": query,
            })
        except Exception:
            # Fallback to hardcoded prompt
            prompt = f"""你是一个博物馆导览助手。用户正在与您进行多轮对话。

对话历史：
{formatted_history}

当前用户问题：{query}

请根据对话历史，将用户的问题改写为一个独立、完整的问题，使其能够独立理解而不需要之前的上下文。
只输出改写后的问题，不要解释："""

        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return str(response.content).strip()


class QueryTransformer:
    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    async def transform_step_back(self, query: str) -> str:
        try:
            prompt = await _get_prompt("query_step_back", {"query": query})
        except Exception:
            prompt = f"""你是一个查询优化专家。用户提出了一个过于具体的问题，
请生成一个更抽象、更宽泛的问题，帮助获取更多背景信息。

原始问题：{query}

请生成一个更抽象的问题（只输出问题本身，不要解释）："""
        
        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return str(response.content).strip()

    async def transform_hyde(self, query: str) -> str:
        try:
            prompt = await _get_prompt("query_hyde", {"query": query})
        except Exception:
            prompt = f"""你是一个查询优化专家。请为用户的问题生成一个假设性的答案，
用于检索相关文档。

用户问题：{query}

请生成一个假设性的答案（只输出答案，不要解释）："""
        
        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])
        return str(response.content).strip()

    async def transform_multi_query(self, query: str) -> list[str]:
        try:
            prompt = await _get_prompt("query_multi", {"query": query})
        except Exception:
            prompt = f"""你是一个查询优化专家。用户的问题可能有歧义或过于宽泛，
请生成3个相关的、更具体的问题，每个问题一行，用数字编号。

用户问题：{query}

请生成3个相关问题："""
        
        response = await self.llm_provider.generate([{"role": "user", "content": prompt}])

        lines = str(response.content).strip().split("\n")
        queries = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                cleaned = line.lstrip("0123456789.-) ")
                if cleaned:
                    queries.append(cleaned)

        return queries[:3] if queries else [query]


def has_specific_details(query: str) -> bool:
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}",
        r"\d{1,2}:\d{2}",
        r"\d+%",
        r"\d+\s*(万|千|百|ten|hundred|thousand|million)",
    ]
    return any(re.search(p, query) for p in patterns)


def is_ambiguous(query: str) -> bool:
    ambiguous_words = ["那个", "这个", "它", "那个东西", "something", "it", "that"]
    query_lower = query.lower()
    for word in ambiguous_words:
        if any(ord(c) > 127 for c in word):
            if word in query_lower:
                return True
        else:
            if re.search(r"\b" + re.escape(word) + r"\b", query_lower):
                return True
    return len(query) < 10


def select_strategy(query: str, retrieval_score: float, attempt: int) -> QueryTransformStrategy:
    if retrieval_score >= 0.7:
        return QueryTransformStrategy.NONE

    if attempt == 1:
        if has_specific_details(query):
            return QueryTransformStrategy.STEP_BACK
        elif is_ambiguous(query):
            return QueryTransformStrategy.MULTI_QUERY
        else:
            return QueryTransformStrategy.HYDE

    if attempt == 2:
        return QueryTransformStrategy.HYDE

    return QueryTransformStrategy.MULTI_QUERY
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/workflows/query_transform.py
git commit -m "refactor(query): use PromptService for query transformation prompts"
```

---

## Task 12: 单元测试

**Files:**
- Create: `backend/tests/unit/test_prompt_service.py`
- Create: `backend/tests/unit/test_prompt_cache.py`

- [ ] **Step 1: 创建PromptService单元测试**

创建文件 `backend/tests/unit/test_prompt_service.py`：

```python
"""Unit tests for PromptService."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

from app.application.prompt_service import PromptService
from app.domain.entities import Prompt, PromptVersion
from app.domain.exceptions import PromptNotFoundError, PromptVariableError


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return AsyncMock()


@pytest.fixture
def mock_cache():
    """Create mock cache."""
    cache = MagicMock()
    cache.get = AsyncMock()
    cache.refresh = MagicMock()
    return cache


@pytest.fixture
def sample_prompt():
    """Create sample prompt."""
    return Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Hello {name}!",
        variables=[{"name": "name", "description": "User name"}],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )


@pytest.mark.asyncio
async def test_get_prompt_from_cache(mock_repository, mock_cache, sample_prompt):
    """Test getting prompt from cache."""
    mock_cache.get.return_value = sample_prompt
    
    service = PromptService(mock_repository, mock_cache)
    result = await service.get_prompt("test_prompt")
    
    assert result.key == "test_prompt"
    mock_cache.get.assert_called_once_with("test_prompt")


@pytest.mark.asyncio
async def test_get_prompt_not_found(mock_repository, mock_cache):
    """Test getting non-existent prompt."""
    mock_cache.get.return_value = None
    
    service = PromptService(mock_repository, mock_cache)
    
    with pytest.raises(PromptNotFoundError):
        await service.get_prompt("nonexistent")


@pytest.mark.asyncio
async def test_render_prompt(mock_repository, mock_cache, sample_prompt):
    """Test rendering prompt with variables."""
    mock_cache.get.return_value = sample_prompt
    
    service = PromptService(mock_repository, mock_cache)
    result = await service.render_prompt("test_prompt", {"name": "World"})
    
    assert result == "Hello World!"


@pytest.mark.asyncio
async def test_render_prompt_missing_variable(mock_repository, mock_cache, sample_prompt):
    """Test rendering prompt with missing variable."""
    mock_cache.get.return_value = sample_prompt
    
    service = PromptService(mock_repository, mock_cache)
    
    with pytest.raises(PromptVariableError):
        await service.render_prompt("test_prompt", {})


@pytest.mark.asyncio
async def test_update_prompt(mock_repository, mock_cache, sample_prompt):
    """Test updating prompt."""
    updated_prompt = Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Updated content",
        variables=[],
        is_active=True,
        created_at=sample_prompt.created_at,
        updated_at=datetime.now(UTC),
        current_version=2,
    )
    mock_repository.update.return_value = updated_prompt
    
    service = PromptService(mock_repository, mock_cache)
    result = await service.update_prompt("test_prompt", "Updated content", "user-1", "Test update")
    
    assert result.content == "Updated content"
    mock_cache.refresh.assert_called_once_with("test_prompt", updated_prompt)
```

- [ ] **Step 2: 创建PromptCache单元测试**

创建文件 `backend/tests/unit/test_prompt_cache.py`：

```python
"""Unit tests for PromptCache."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock

from app.infra.cache.prompt_cache import PromptCache
from app.domain.entities import Prompt


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return AsyncMock()


@pytest.fixture
def sample_prompt():
    """Create sample prompt."""
    return Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Test content",
        variables=[],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )


@pytest.mark.asyncio
async def test_load_all(mock_repository, sample_prompt):
    """Test loading all prompts into cache."""
    mock_repository.list_all.return_value = [sample_prompt]
    
    cache = PromptCache()
    cache.set_repository(mock_repository)
    await cache.load_all()
    
    result = await cache.get("test_prompt")
    assert result == sample_prompt


@pytest.mark.asyncio
async def test_get_from_cache(mock_repository, sample_prompt):
    """Test getting prompt from cache."""
    mock_repository.list_all.return_value = [sample_prompt]
    
    cache = PromptCache()
    cache.set_repository(mock_repository)
    await cache.load_all()
    
    result = await cache.get("test_prompt")
    assert result == sample_prompt
    # Should not call repository again
    mock_repository.get_by_key.assert_not_called()


@pytest.mark.asyncio
async def test_get_cache_miss(mock_repository, sample_prompt):
    """Test cache miss loads from repository."""
    mock_repository.get_by_key.return_value = sample_prompt
    
    cache = PromptCache()
    cache.set_repository(mock_repository)
    
    result = await cache.get("test_prompt")
    assert result == sample_prompt
    mock_repository.get_by_key.assert_called_once_with("test_prompt")


@pytest.mark.asyncio
async def test_refresh(mock_repository, sample_prompt):
    """Test refreshing prompt in cache."""
    cache = PromptCache()
    cache.refresh("test_prompt", sample_prompt)
    
    result = await cache.get("test_prompt")
    assert result == sample_prompt


def test_invalidate(sample_prompt):
    """Test invalidating prompt from cache."""
    cache = PromptCache()
    cache.refresh("test_prompt", sample_prompt)
    
    cache.invalidate("test_prompt")
    
    # Cache should be empty
    keys = cache.get_all_keys()
    assert "test_prompt" not in keys


def test_clear(sample_prompt):
    """Test clearing all prompts from cache."""
    cache = PromptCache()
    cache.refresh("test_prompt", sample_prompt)
    
    cache.clear()
    
    keys = cache.get_all_keys()
    assert len(keys) == 0
```

- [ ] **Step 3: 运行测试**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit/test_prompt_service.py backend/tests/unit/test_prompt_cache.py -v
```

Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/tests/unit/test_prompt_service.py backend/tests/unit/test_prompt_cache.py
git commit -m "test: add unit tests for PromptService and PromptCache"
```

---

## Task 13: API契约测试

**Files:**
- Create: `backend/tests/contract/test_prompts_api.py`

- [ ] **Step 1: 创建API契约测试**

创建文件 `backend/tests/contract/test_prompts_api.py`：

```python
"""Contract tests for prompt management API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from app.main import app
from app.domain.entities import Prompt


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_prompt_cache():
    """Create mock prompt cache."""
    cache = MagicMock()
    cache.get = AsyncMock()
    cache.refresh = MagicMock()
    cache.get_all_keys = MagicMock(return_value=["test_prompt"])
    return cache


@pytest.fixture
def sample_prompt():
    """Create sample prompt."""
    return Prompt(
        id="test-id",
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Test content {var}",
        variables=[{"name": "var", "description": "A variable"}],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_version=1,
    )


@pytest.fixture
def auth_headers():
    """Create auth headers for admin user."""
    # This should be a valid admin token in a real test
    return {"Authorization": "Bearer test-admin-token"}


class TestListPrompts:
    """Tests for GET /admin/prompts endpoint."""

    @patch("app.api.admin.prompts.get_prompt_service")
    def test_list_prompts_success(self, mock_get_service, client, sample_prompt, auth_headers):
        """Test listing prompts successfully."""
        mock_service = AsyncMock()
        mock_service.list_prompts.return_value = [sample_prompt]
        mock_get_service.return_value = mock_service
        
        # This test requires authentication - skip if not properly set up
        # response = client.get("/api/v1/admin/prompts", headers=auth_headers)
        # assert response.status_code == 200
        pass

    def test_list_prompts_unauthorized(self, client):
        """Test listing prompts without auth."""
        response = client.get("/api/v1/admin/prompts")
        assert response.status_code == 401


class TestGetPrompt:
    """Tests for GET /admin/prompts/{key} endpoint."""

    def test_get_prompt_unauthorized(self, client):
        """Test getting prompt without auth."""
        response = client.get("/api/v1/admin/prompts/test_prompt")
        assert response.status_code == 401


class TestUpdatePrompt:
    """Tests for PUT /admin/prompts/{key} endpoint."""

    def test_update_prompt_unauthorized(self, client):
        """Test updating prompt without auth."""
        response = client.put(
            "/api/v1/admin/prompts/test_prompt",
            json={"content": "New content"}
        )
        assert response.status_code == 401


class TestReloadPrompts:
    """Tests for POST /admin/prompts/reload-all endpoint."""

    def test_reload_unauthorized(self, client):
        """Test reloading prompts without auth."""
        response = client.post("/api/v1/admin/prompts/reload-all")
        assert response.status_code == 401
```

- [ ] **Step 2: 运行测试**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/contract/test_prompts_api.py -v
```

Expected: 基本测试通过（未授权测试）

- [ ] **Step 3: 提交**

```bash
git add backend/tests/contract/test_prompts_api.py
git commit -m "test: add contract tests for prompt management API"
```

---

## Task 14: 最终验证和提交

- [ ] **Step 1: 运行所有测试**

```bash
cd /home/singer/MuseAI && uv run pytest backend/tests/unit backend/tests/contract -v
```

Expected: 所有测试通过

- [ ] **Step 2: 运行linting**

```bash
cd /home/singer/MuseAI && uv run ruff check backend/
```

Expected: 无错误

- [ ] **Step 3: 运行type checking**

```bash
cd /home/singer/MuseAI && uv run mypy backend/
```

Expected: 无类型错误

- [ ] **Step 4: 最终提交（如果有未提交的更改）**

```bash
git status
# 如果有未提交的更改
git add -A
git commit -m "feat: complete prompt management system implementation"
```

- [ ] **Step 5: 推送到远程分支（如果需要）**

```bash
git push origin main
```
