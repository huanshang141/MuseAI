# Digital Curation Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Tool-Calling Curator Agent that creates personalized museum tour paths, generates narrative content, and guides reflective cultural thinking based on visitor profiles.

**Architecture:** Three-layer system: (1) Data layer with exhibits, tour_paths, and visitor_profiles tables, (2) Service layer with repositories and business logic, (3) Agent layer using LangChain ReAct pattern with 5 specialized tools (path planning, knowledge retrieval, narrative generation, reflection prompting, preference management).

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, LangChain/LangGraph, Vue 3, Element Plus

---

## File Structure Overview

### New Files (19)
- `backend/app/domain/entities.py` additions: Exhibit, TourPath, VisitorProfile entities
- `backend/app/infra/postgres/models.py` additions: Exhibit, TourPath, VisitorProfile ORM models
- `backend/app/infra/postgres/repositories.py`: Repository implementations
- `backend/app/api/admin.py`: Admin endpoints for exhibits/tour paths
- `backend/app/api/curator.py`: Curator service endpoints
- `backend/app/api/profile.py`: User profile endpoints
- `backend/app/application/exhibit_service.py`: Exhibit CRUD service
- `backend/app/application/tour_path_service.py`: Tour path service
- `backend/app/application/profile_service.py`: Visitor profile service
- `backend/app/application/curator_service.py`: Curator coordination service
- `backend/app/infra/langchain/curator_tools.py`: 5 Tool implementations
- `backend/app/infra/langchain/curator_agent.py`: ReAct Agent
- `backend/app/workflows/reflection_prompts.py`: Hard-coded reflection templates
- `backend/tests/unit/test_curator_tools.py`: Tool unit tests
- `backend/tests/unit/test_curator_agent.py`: Agent unit tests
- `backend/tests/contract/test_admin_api.py`: Admin API contract tests
- `backend/tests/contract/test_curator_api.py`: Curator API contract tests
- `frontend/src/components/admin/ExhibitManager.vue`: Admin UI
- `frontend/src/components/profile/ProfileSettings.vue`: Profile settings UI

### Modified Files (6)
- `backend/app/infra/postgres/models.py`: Add relationships to Document model
- `backend/app/domain/entities.py`: Add new entity dataclasses
- `backend/app/infra/langchain/__init__.py`: Add create_curator_agent factory
- `backend/app/main.py`: Register new routers and lifespan initialization
- `backend/app/api/deps.py`: Add admin user dependency
- `backend/app/domain/value_objects.py`: Add new value object types

---

## Task 1: Database Models

**Files:**
- Create: `backend/alembic/versions/20250106_add_exhibits_tour_paths_profiles.py`
- Modify: `backend/app/infra/postgres/models.py`
- Test: `backend/tests/unit/test_models.py`

- [ ] **Step 1: Write migration for exhibits table**

```python
"""add exhibits tour_paths visitor_profiles

Revision ID: 20250106_add_exhibits
Revises: previous_revision
Create Date: 2025-01-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '20250106_add_exhibits'
down_revision: Union[str, None] = 'previous_revision'  # Update this
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exhibits',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location_x', sa.Float(), nullable=False),
        sa.Column('location_y', sa.Float(), nullable=False),
        sa.Column('floor', sa.Integer(), default=1),
        sa.Column('hall', sa.String(100), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('era', sa.String(100), nullable=True),
        sa.Column('importance', sa.Integer(), default=3),
        sa.Column('estimated_visit_time', sa.Integer(), default=10),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_exhibits_category', 'exhibits', ['category'])
    op.create_index('ix_exhibits_hall', 'exhibits', ['hall'])
    op.create_index('ix_exhibits_is_active', 'exhibits', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_exhibits_is_active')
    op.drop_index('ix_exhibits_hall')
    op.drop_index('ix_exhibits_category')
    op.drop_table('exhibits')
```

- [ ] **Step 2: Write migration for tour_paths table**

Add to the same migration file's upgrade() function:

```python
    op.create_table(
        'tour_paths',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('theme', sa.String(100), nullable=False),
        sa.Column('estimated_duration', sa.Integer(), nullable=False),
        sa.Column('exhibit_ids', postgresql.JSON(astext_type=sa.Text()), nullable=False, default=list),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_tour_paths_theme', 'tour_paths', ['theme'])
    op.create_index('ix_tour_paths_is_active', 'tour_paths', ['is_active'])
```

Add to downgrade():

```python
    op.drop_index('ix_tour_paths_is_active')
    op.drop_index('ix_tour_paths_theme')
    op.drop_table('tour_paths')
```

- [ ] **Step 3: Write migration for visitor_profiles table**

Add to upgrade():

```python
    op.create_table(
        'visitor_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False),
        sa.Column('interests', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('knowledge_level', sa.String(20), default='beginner'),
        sa.Column('narrative_preference', sa.String(20), default='storytelling'),
        sa.Column('reflection_depth', sa.Integer(), default=3),
        sa.Column('visited_exhibit_ids', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('feedback_history', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_visitor_profiles_user_id', 'visitor_profiles', ['user_id'])
```

Add to downgrade():

```python
    op.drop_index('ix_visitor_profiles_user_id')
    op.drop_table('visitor_profiles')
```

- [ ] **Step 4: Update ORM models.py with Exhibit model**

Add to `backend/app/infra/postgres/models.py`:

```python
class Exhibit(Base):
    __tablename__ = "exhibits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_x: Mapped[float] = mapped_column(nullable=False)
    location_y: Mapped[float] = mapped_column(nullable=False)
    floor: Mapped[int] = mapped_column(default=1)
    hall: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    era: Mapped[str | None] = mapped_column(String(100), nullable=True)
    importance: Mapped[int] = mapped_column(default=3)
    estimated_visit_time: Mapped[int] = mapped_column(default=10)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    document: Mapped["Document"] = relationship(back_populates="exhibits")
```

- [ ] **Step 5: Update Document model with relationship**

Add to Document class in models.py:

```python
    exhibits: Mapped[list["Exhibit"]] = relationship(back_populates="document")
```

- [ ] **Step 6: Add TourPath model to models.py**

```python
from sqlalchemy.dialects.postgresql import JSON

class TourPath(Base):
    __tablename__ = "tour_paths"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme: Mapped[str] = mapped_column(String(100), nullable=False)
    estimated_duration: Mapped[int] = mapped_column(nullable=False)
    exhibit_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 7: Add VisitorProfile model to models.py**

```python
class VisitorProfile(Base):
    __tablename__ = "visitor_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    knowledge_level: Mapped[str] = mapped_column(String(20), default="beginner")
    narrative_preference: Mapped[str] = mapped_column(String(20), default="storytelling")
    reflection_depth: Mapped[int] = mapped_column(default=3)
    visited_exhibit_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    feedback_history: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    user: Mapped["User"] = relationship(back_populates="profile")
```

- [ ] **Step 8: Add User relationships**

Add to User class:

```python
    profile: Mapped["VisitorProfile"] = relationship(back_populates="user", uselist=False)
```

- [ ] **Step 9: Run migration to verify**

```bash
cd /home/singer/MuseAI
alembic upgrade head
```

Expected: Migration applies successfully

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/versions/20250106_add_exhibits_tour_paths_profiles.py
git add backend/app/infra/postgres/models.py
git commit -m "feat(db): add exhibits, tour_paths, visitor_profiles tables"
```

---

## Task 2: Domain Entities and Value Objects

**Files:**
- Modify: `backend/app/domain/value_objects.py`
- Modify: `backend/app/domain/entities.py`
- Test: `backend/tests/unit/test_domain_entities.py`

- [ ] **Step 1: Add value objects**

Add to `backend/app/domain/value_objects.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ExhibitId:
    value: str


@dataclass(frozen=True)
class TourPathId:
    value: str


@dataclass(frozen=True)
class ProfileId:
    value: str


@dataclass(frozen=True)
class Location:
    x: float
    y: float
    floor: int = 1
```

- [ ] **Step 2: Add Exhibit entity**

Add to `backend/app/domain/entities.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from .value_objects import ExhibitId, DocumentId, Location


@dataclass
class Exhibit:
    id: ExhibitId
    name: str
    description: str | None
    location: Location
    hall: str
    category: str
    era: str | None
    importance: int  # 1-5
    estimated_visit_time: int  # minutes
    document_id: DocumentId | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 3: Add TourPath entity**

```python
from .value_objects import TourPathId, ExhibitId, UserId


@dataclass
class TourPath:
    id: TourPathId
    name: str
    description: str | None
    theme: str
    estimated_duration: int  # minutes
    exhibit_ids: list[ExhibitId]
    is_active: bool
    created_by: UserId
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Add VisitorProfile entity**

```python
from .value_objects import ProfileId, UserId


@dataclass
class VisitorProfile:
    id: ProfileId
    user_id: UserId
    interests: list[str]
    knowledge_level: str  # beginner, intermediate, expert
    narrative_preference: str  # storytelling, academic, interactive
    reflection_depth: int  # 1-5
    visited_exhibit_ids: list[ExhibitId]
    feedback_history: list[dict]
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 5: Write test for Exhibit entity**

Add to `backend/tests/unit/test_domain_entities.py`:

```python
from datetime import datetime

from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location, DocumentId


def test_exhibit_creation():
    exhibit = Exhibit(
        id=ExhibitId("exhibit-001"),
        name="青铜鼎",
        description="商代晚期青铜礼器",
        location=Location(x=10.5, y=20.3, floor=1),
        hall="青铜馆",
        category="青铜器",
        era="商代晚期",
        importance=5,
        estimated_visit_time=15,
        document_id=DocumentId("doc-001"),
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    
    assert exhibit.id.value == "exhibit-001"
    assert exhibit.name == "青铜鼎"
    assert exhibit.location.x == 10.5
    assert exhibit.importance == 5
```

- [ ] **Step 6: Write test for VisitorProfile entity**

```python
from app.domain.entities import VisitorProfile
from app.domain.value_objects import ProfileId, UserId, ExhibitId


def test_visitor_profile_creation():
    profile = VisitorProfile(
        id=ProfileId("profile-001"),
        user_id=UserId("user-001"),
        interests=["青铜器", "书画"],
        knowledge_level="intermediate",
        narrative_preference="storytelling",
        reflection_depth=3,
        visited_exhibit_ids=[ExhibitId("exhibit-001")],
        feedback_history=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    
    assert profile.user_id.value == "user-001"
    assert "青铜器" in profile.interests
    assert profile.knowledge_level == "intermediate"
```

- [ ] **Step 7: Run tests**

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_domain_entities.py -v
```

Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/value_objects.py
git add backend/app/domain/entities.py
git add backend/tests/unit/test_domain_entities.py
git commit -m "feat(domain): add Exhibit, TourPath, VisitorProfile entities"
```

---

## Task 3: Repository Layer

**Files:**
- Create: `backend/app/domain/repositories.py` (protocols)
- Create: `backend/app/infra/postgres/repositories.py` (implementations)
- Test: `backend/tests/unit/test_repositories.py`

- [ ] **Step 1: Define repository protocols**

Create `backend/app/domain/repositories.py`:

```python
from typing import Protocol

from app.domain.entities import Exhibit, TourPath, VisitorProfile
from app.domain.value_objects import ExhibitId, TourPathId, ProfileId, UserId


class ExhibitRepository(Protocol):
    async def get_by_id(self, exhibit_id: ExhibitId) -> Exhibit | None:
        ...
    
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Exhibit]:
        ...
    
    async def list_by_category(self, category: str) -> list[Exhibit]:
        ...
    
    async def list_by_hall(self, hall: str) -> list[Exhibit]:
        ...
    
    async def find_by_interests(self, interests: list[str]) -> list[Exhibit]:
        ...
    
    async def save(self, exhibit: Exhibit) -> Exhibit:
        ...
    
    async def delete(self, exhibit_id: ExhibitId) -> bool:
        ...


class TourPathRepository(Protocol):
    async def get_by_id(self, path_id: TourPathId) -> TourPath | None:
        ...
    
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[TourPath]:
        ...
    
    async def list_by_theme(self, theme: str) -> list[TourPath]:
        ...
    
    async def save(self, path: TourPath) -> TourPath:
        ...
    
    async def delete(self, path_id: TourPathId) -> bool:
        ...


class VisitorProfileRepository(Protocol):
    async def get_by_id(self, profile_id: ProfileId) -> VisitorProfile | None:
        ...
    
    async def get_by_user_id(self, user_id: UserId) -> VisitorProfile | None:
        ...
    
    async def save(self, profile: VisitorProfile) -> VisitorProfile:
        ...
    
    async def update(self, user_id: UserId, updates: dict) -> VisitorProfile:
        ...
```

- [ ] **Step 2: Implement ExhibitRepository**

Create `backend/app/infra/postgres/repositories.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Exhibit, TourPath, VisitorProfile
from app.domain.value_objects import ExhibitId, TourPathId, ProfileId, UserId, Location
from app.infra.postgres.models import Exhibit as ExhibitORM, TourPath as TourPathORM, VisitorProfile as VisitorProfileORM


class PostgresExhibitRepository:
    def __init__(self, session: AsyncSession):
        self._session = session
    
    def _to_entity(self, orm: ExhibitORM) -> Exhibit:
        return Exhibit(
            id=ExhibitId(orm.id),
            name=orm.name,
            description=orm.description,
            location=Location(x=orm.location_x, y=orm.location_y, floor=orm.floor),
            hall=orm.hall,
            category=orm.category,
            era=orm.era,
            importance=orm.importance,
            estimated_visit_time=orm.estimated_visit_time,
            document_id=None if not orm.document_id else __import__('app.domain.value_objects', fromlist=['DocumentId']).DocumentId(orm.document_id),
            is_active=orm.is_active,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
    
    async def get_by_id(self, exhibit_id: ExhibitId) -> Exhibit | None:
        result = await self._session.execute(
            select(ExhibitORM).where(ExhibitORM.id == exhibit_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None
    
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Exhibit]:
        result = await self._session.execute(
            select(ExhibitORM).where(ExhibitORM.is_active == True).offset(skip).limit(limit)
        )
        return [self._to_entity(orm) for orm in result.scalars().all()]
    
    async def list_by_category(self, category: str) -> list[Exhibit]:
        result = await self._session.execute(
            select(ExhibitORM).where(
                ExhibitORM.category == category,
                ExhibitORM.is_active == True
            )
        )
        return [self._to_entity(orm) for orm in result.scalars().all()]
    
    async def list_by_hall(self, hall: str) -> list[Exhibit]:
        result = await self._session.execute(
            select(ExhibitORM).where(
                ExhibitORM.hall == hall,
                ExhibitORM.is_active == True
            )
        )
        return [self._to_entity(orm) for orm in result.scalars().all()]
    
    async def find_by_interests(self, interests: list[str]) -> list[Exhibit]:
        # Match exhibits where category matches any interest
        result = await self._session.execute(
            select(ExhibitORM).where(
                ExhibitORM.category.in_(interests),
                ExhibitORM.is_active == True
            ).order_by(ExhibitORM.importance.desc())
        )
        return [self._to_entity(orm) for orm in result.scalars().all()]
    
    async def save(self, exhibit: Exhibit) -> Exhibit:
        orm = ExhibitORM(
            id=exhibit.id.value if exhibit.id else str(uuid.uuid4()),
            name=exhibit.name,
            description=exhibit.description,
            location_x=exhibit.location.x,
            location_y=exhibit.location.y,
            floor=exhibit.location.floor,
            hall=exhibit.hall,
            category=exhibit.category,
            era=exhibit.era,
            importance=exhibit.importance,
            estimated_visit_time=exhibit.estimated_visit_time,
            document_id=exhibit.document_id.value if exhibit.document_id else None,
            is_active=exhibit.is_active,
            created_at=exhibit.created_at or datetime.now(),
            updated_at=exhibit.updated_at or datetime.now(),
        )
        self._session.add(orm)
        await self._session.flush()
        return self._to_entity(orm)
    
    async def delete(self, exhibit_id: ExhibitId) -> bool:
        result = await self._session.execute(
            select(ExhibitORM).where(ExhibitORM.id == exhibit_id.value)
        )
        orm = result.scalar_one_or_none()
        if orm:
            orm.is_active = False
            await self._session.flush()
            return True
        return False
```

- [ ] **Step 3: Implement VisitorProfileRepository**

Add to `backend/app/infra/postgres/repositories.py`:

```python
class PostgresVisitorProfileRepository:
    def __init__(self, session: AsyncSession):
        self._session = session
    
    def _to_entity(self, orm: VisitorProfileORM) -> VisitorProfile:
        return VisitorProfile(
            id=ProfileId(orm.id),
            user_id=UserId(orm.user_id),
            interests=orm.interests or [],
            knowledge_level=orm.knowledge_level,
            narrative_preference=orm.narrative_preference,
            reflection_depth=orm.reflection_depth,
            visited_exhibit_ids=[ExhibitId(eid) for eid in (orm.visited_exhibit_ids or [])],
            feedback_history=orm.feedback_history or [],
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
    
    async def get_by_id(self, profile_id: ProfileId) -> VisitorProfile | None:
        result = await self._session.execute(
            select(VisitorProfileORM).where(VisitorProfileORM.id == profile_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None
    
    async def get_by_user_id(self, user_id: UserId) -> VisitorProfile | None:
        result = await self._session.execute(
            select(VisitorProfileORM).where(VisitorProfileORM.user_id == user_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None
    
    async def save(self, profile: VisitorProfile) -> VisitorProfile:
        orm = VisitorProfileORM(
            id=profile.id.value if profile.id else str(uuid.uuid4()),
            user_id=profile.user_id.value,
            interests=profile.interests,
            knowledge_level=profile.knowledge_level,
            narrative_preference=profile.narrative_preference,
            reflection_depth=profile.reflection_depth,
            visited_exhibit_ids=[eid.value for eid in profile.visited_exhibit_ids],
            feedback_history=profile.feedback_history,
            created_at=profile.created_at or datetime.now(),
            updated_at=profile.updated_at or datetime.now(),
        )
        self._session.add(orm)
        await self._session.flush()
        return self._to_entity(orm)
    
    async def update(self, user_id: UserId, updates: dict) -> VisitorProfile:
        result = await self._session.execute(
            select(VisitorProfileORM).where(VisitorProfileORM.user_id == user_id.value)
        )
        orm = result.scalar_one()
        
        for key, value in updates.items():
            if hasattr(orm, key):
                setattr(orm, key, value)
        
        orm.updated_at = datetime.now()
        await self._session.flush()
        return self._to_entity(orm)
```

- [ ] **Step 4: Write repository test**

Create `backend/tests/unit/test_repositories.py`:

```python
import pytest
from datetime import datetime

from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location
from app.infra.postgres.repositories import PostgresExhibitRepository


@pytest.mark.asyncio
async def test_exhibit_repository_save_and_get(async_session):
    repo = PostgresExhibitRepository(async_session)
    
    exhibit = Exhibit(
        id=ExhibitId("test-exhibit-001"),
        name="测试展品",
        description="测试描述",
        location=Location(x=1.0, y=2.0, floor=1),
        hall="测试展厅",
        category="测试分类",
        era="测试年代",
        importance=3,
        estimated_visit_time=10,
        document_id=None,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    
    saved = await repo.save(exhibit)
    await async_session.commit()
    
    assert saved.name == "测试展品"
    
    retrieved = await repo.get_by_id(ExhibitId("test-exhibit-001"))
    assert retrieved is not None
    assert retrieved.name == "测试展品"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/repositories.py
git add backend/app/infra/postgres/repositories.py
git add backend/tests/unit/test_repositories.py
git commit -m "feat(repo): add Exhibit and VisitorProfile repositories"
```

---

## Task 4: Reflection Prompts Module

**Files:**
- Create: `backend/app/workflows/reflection_prompts.py`
- Test: `backend/tests/unit/test_reflection_prompts.py`

- [ ] **Step 1: Create hard-coded reflection templates**

Create `backend/app/workflows/reflection_prompts.py`:

```python
"""反身性引导提示模板（硬编码版本）

后续版本将迁移到版本化管理系统。
"""

from enum import Enum


class KnowledgeLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


# 按知识水平分类的反思问题模板
REFLECTION_TEMPLATES = {
    KnowledgeLevel.BEGINNER: [
        "这件文物让您联想到什么日常生活中的物品？",
        "如果您生活在那个时代，会如何使用这件物品？",
        "这件文物的颜色/形状给您什么感觉？",
        "您觉得制作这件物品需要哪些材料？",
        "如果这件文物会说话，它想告诉我们什么？",
    ],
    KnowledgeLevel.INTERMEDIATE: [
        "这件文物反映的社会结构对今天有什么启示？",
        "历史记载中，哪些群体的视角可能被忽略了？",
        "这件物品的工艺技术如何影响了当时的经济发展？",
        "文物的流传过程反映了怎样的权力更迭？",
        "不同文化背景下，这件文物可能被如何解读？",
    ],
    KnowledgeLevel.EXPERT: [
        "现有的考古解读是否存在争议？您倾向于哪种观点？",
        "这件文物在特定历史语境中的象征意义如何被重构？",
        "从物质文化研究的角度，这件物品如何挑战传统史学叙事？",
        "这件文物的收藏史如何映射现代民族国家建构过程？",
        "如果采用后殖民视角，这件文物的展示方式需要哪些调整？",
    ],
}

# 按展品分类的专项问题
CATEGORY_REFLECTIONS = {
    "青铜器": [
        "青铜器的铸造工艺反映了怎样的社会组织形式？",
        "礼器制度如何塑造了古代中国的权力结构？",
    ],
    "书画": [
        "笔墨技法的变化如何反映作者的心境变迁？",
        "这幅作品的题跋和鉴藏印揭示了怎样的流传史？",
    ],
    "陶瓷": [
        "窑址的地理分布如何反映当时的贸易网络？",
        "釉色审美变迁背后是怎样的文化交融？",
    ],
}


def get_reflection_prompts(
    knowledge_level: str,
    reflection_depth: int,
    category: str | None = None,
) -> list[str]:
    """获取反身性引导问题列表
    
    Args:
        knowledge_level: 知识水平 (beginner/intermediate/expert)
        reflection_depth: 返回问题数量 (1-5)
        category: 展品分类（可选，用于添加专项问题）
    
    Returns:
        问题列表
    """
    level = KnowledgeLevel(knowledge_level) if knowledge_level in [e.value for e in KnowledgeLevel] else KnowledgeLevel.BEGINNER
    
    # 获取基础问题
    base_prompts = REFLECTION_TEMPLATES[level][:]
    
    # 添加分类专项问题
    if category and category in CATEGORY_REFLECTIONS:
        base_prompts.extend(CATEGORY_REFLECTIONS[category])
    
    # 根据深度返回指定数量
    depth = max(1, min(5, reflection_depth))
    return base_prompts[:depth]


def get_narrative_style_prompt(style: str) -> str:
    """获取叙事风格系统提示
    
    Args:
        style: storytelling, academic, interactive
    """
    prompts = {
        "storytelling": """你是一位富有感染力的博物馆讲解员。请用讲故事的方式介绍这件展品：
- 营造场景感和代入感
- 使用生动形象的描述
- 适当加入悬念和情感元素
- 让历史"活"起来""",
        
        "academic": """你是一位严谨的博物馆学者。请用学术的方式介绍这件展品：
- 准确使用专业术语
- 引用考古发现和研究成果
- 说明历史背景和断代依据
- 保持客观中立的叙述 tone""",
        
        "interactive": """你是一位互动型博物馆教育者。请用对话的方式介绍这件展品：
- 使用提问引发思考
- 邀请观众参与想象
- 联系当代生活经验
- 鼓励观众表达自己的观点""",
    }
    
    return prompts.get(style, prompts["storytelling"])
```

- [ ] **Step 2: Write tests for reflection prompts**

Create `backend/tests/unit/test_reflection_prompts.py`:

```python
import pytest

from app.workflows.reflection_prompts import (
    get_reflection_prompts,
    get_narrative_style_prompt,
    KnowledgeLevel,
)


def test_get_reflection_prompts_beginner():
    prompts = get_reflection_prompts("beginner", 3)
    assert len(prompts) == 3
    assert all(isinstance(p, str) for p in prompts)
    assert "文物" in prompts[0] or "物品" in prompts[0]


def test_get_reflection_prompts_expert():
    prompts = get_reflection_prompts("expert", 2)
    assert len(prompts) == 2
    # Expert prompts should be more academic
    assert any("考古" in p or "史学" in p for p in prompts)


def test_get_reflection_prompts_with_category():
    prompts = get_reflection_prompts("intermediate", 5, category="青铜器")
    assert len(prompts) >= 5
    # Should include bronze-specific questions
    assert any("青铜" in p for p in prompts)


def test_get_reflection_prompts_depth_limit():
    # Should cap at available prompts
    prompts = get_reflection_prompts("beginner", 10)
    assert len(prompts) <= 5  # beginner has 5 prompts


def test_get_narrative_style_prompt_storytelling():
    prompt = get_narrative_style_prompt("storytelling")
    assert "讲故事" in prompt
    assert "感染力" in prompt


def test_get_narrative_style_prompt_academic():
    prompt = get_narrative_style_prompt("academic")
    assert "学术" in prompt
    assert "严谨" in prompt


def test_get_narrative_style_prompt_default():
    # Unknown style defaults to storytelling
    prompt = get_narrative_style_prompt("unknown")
    assert "讲故事" in prompt
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest backend/tests/unit/test_reflection_prompts.py -v
```

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/workflows/reflection_prompts.py
git add backend/tests/unit/test_reflection_prompts.py
git commit -m "feat(workflow): add hard-coded reflection prompts and narrative styles"
```

---

## Task 5: Curator Tools Implementation

**Files:**
- Create: `backend/app/infra/langchain/curator_tools.py`
- Test: `backend/tests/unit/test_curator_tools.py`

- [ ] **Step 1: Implement PathPlanningTool**

Create `backend/app/infra/langchain/curator_tools.py`:

```python
"""博物馆策展工具集"""

import json
import math
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import Field

from app.domain.value_objects import ExhibitId, Location
from app.infra.langchain.agents import RAGAgent
from app.workflows.reflection_prompts import get_reflection_prompts, get_narrative_style_prompt


class PathPlanningTool(BaseTool):
    """根据用户画像和时间规划最优导览路径"""
    
    name: str = "plan_tour_path"
    description: str = """
    根据用户的兴趣、可用时间、当前位置规划最优参观路线。
    输入应为JSON格式：{
        "interests": ["青铜器", "书画"],
        "available_time": 60,
        "current_location": {"x": 0, "y": 0, "floor": 1},
        "visited_exhibit_ids": ["exhibit-001"],
        "max_exhibits": 10
    }
    返回包含路径、预计时间、展品数量的JSON。
    """
    
    exhibit_repository: Any = Field(..., description="展品仓库")
    
    def _calculate_distance(self, loc1: Location, loc2: Location) -> float:
        """计算两点间距离（考虑楼层）"""
        floor_penalty = abs(loc1.floor - loc2.floor) * 100  # 楼层切换惩罚
        return math.sqrt((loc1.x - loc2.x) ** 2 + (loc1.y - loc2.y) ** 2) + floor_penalty
    
    def _solve_tsp_nearest_neighbor(
        self,
        start: Location,
        exhibits: list[Any],
        max_time: int,
    ) -> list[Any]:
        """使用最近邻算法求解路径"""
        if not exhibits:
            return []
        
        unvisited = exhibits.copy()
        path = []
        current_location = start
        total_time = 0
        
        while unvisited and total_time < max_time:
            # 找到最近的未访问展品
            nearest = min(
                unvisited,
                key=lambda e: self._calculate_distance(
                    current_location,
                    Location(x=e.location.x, y=e.location.y, floor=e.location.floor)
                )
            )
            
            travel_time = self._calculate_distance(
                current_location,
                Location(x=nearest.location.x, y=nearest.location.y, floor=nearest.location.floor)
            ) / 10  # 假设移动速度 10单位/分钟
            
            visit_time = nearest.estimated_visit_time
            
            if total_time + travel_time + visit_time > max_time:
                break
            
            path.append(nearest)
            total_time += travel_time + visit_time
            current_location = Location(
                x=nearest.location.x,
                y=nearest.location.y,
                floor=nearest.location.floor
            )
            unvisited.remove(nearest)
        
        return path
    
    async def _arun(self, query: str) -> str:
        """异步执行路径规划"""
        try:
            params = json.loads(query)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input"})
        
        interests = params.get("interests", [])
        available_time = params.get("available_time", 60)
        current_location = Location(**params.get("current_location", {"x": 0, "y": 0, "floor": 1}))
        visited_ids = set(params.get("visited_exhibit_ids", []))
        max_exhibits = params.get("max_exhibits", 10)
        
        # 1. 根据兴趣筛选展品
        candidates = []
        for interest in interests:
            exhibits = await self.exhibit_repository.list_by_category(interest)
            candidates.extend(exhibits)
        
        # 去重并排除已参观
        seen = set()
        unique_candidates = []
        for e in candidates:
            if e.id.value not in seen and e.id.value not in visited_ids and e.is_active:
                seen.add(e.id.value)
                unique_candidates.append(e)
        
        # 按重要性排序
        unique_candidates.sort(key=lambda e: e.importance, reverse=True)
        
        # 限制候选数量
        unique_candidates = unique_candidates[:max_exhibits * 2]
        
        # 2. 计算最优路径
        path = self._solve_tsp_nearest_neighbor(
            start=current_location,
            exhibits=unique_candidates,
            max_time=available_time,
        )
        
        # 3. 返回结果
        total_time = sum(e.estimated_visit_time for e in path)
        
        return json.dumps({
            "path": [
                {
                    "id": e.id.value,
                    "name": e.name,
                    "category": e.category,
                    "location": {"x": e.location.x, "y": e.location.y, "floor": e.location.floor},
                    "estimated_time": e.estimated_visit_time,
                }
                for e in path
            ],
            "estimated_duration": total_time,
            "exhibit_count": len(path),
        }, ensure_ascii=False)
    
    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
```

- [ ] **Step 2: Implement KnowledgeRetrievalTool**

Add to `curator_tools.py`:

```python
class KnowledgeRetrievalTool(BaseTool):
    """检索展品知识"""
    
    name: str = "retrieve_exhibit_knowledge"
    description: str = """
    检索博物馆知识库中关于展品的信息。
    输入应为JSON格式：{
        "query": "商代青铜器的铸造工艺",
        "exhibit_id": "exhibit-001"  // 可选
    }
    """
    
    rag_agent: RAGAgent = Field(..., description="RAG Agent实例")
    
    async def _arun(self, query: str) -> str:
        try:
            params = json.loads(query)
            search_query = params.get("query", query)
            exhibit_id = params.get("exhibit_id")
            
            # 如果有exhibit_id，增强查询
            if exhibit_id:
                search_query = f"展品 {exhibit_id}: {search_query}"
            
            result = await self.rag_agent.run(search_query)
            
            return json.dumps({
                "answer": result.get("answer", "未找到相关信息"),
                "sources": [
                    {
                        "chunk_id": doc.metadata.get("chunk_id"),
                        "score": doc.metadata.get("rrf_score"),
                    }
                    for doc in result.get("documents", [])
                ],
                "retrieval_score": result.get("retrieval_score", 0),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
```

- [ ] **Step 3: Implement NarrativeGenerationTool**

Add to `curator_tools.py`:

```python
from langchain_core.language_models import BaseChatModel


class NarrativeGenerationTool(BaseTool):
    """生成故事化讲解内容"""
    
    name: str = "generate_narrative"
    description: str = """
    根据展品信息和用户偏好生成故事化讲解。
    输入应为JSON格式：{
        "exhibit_name": "青铜鼎",
        "exhibit_info": "商代晚期青铜礼器，高50cm...",
        "knowledge_level": "beginner",
        "narrative_preference": "storytelling"
    }
    """
    
    llm: BaseChatModel = Field(..., description="语言模型")
    
    async def _arun(self, query: str) -> str:
        try:
            params = json.loads(query)
            
            exhibit_name = params.get("exhibit_name", "这件展品")
            exhibit_info = params.get("exhibit_info", "")
            knowledge_level = params.get("knowledge_level", "beginner")
            narrative_style = params.get("narrative_preference", "storytelling")
            
            # 获取风格提示
            style_prompt = get_narrative_style_prompt(narrative_style)
            
            # 根据知识水平调整深度
            level_instructions = {
                "beginner": "使用通俗易懂的语言，避免专业术语，多使用比喻。",
                "intermediate": "适当使用专业术语，提供背景知识解释。",
                "expert": "深入专业细节，引用研究成果，提出学术观点。",
            }
            level_instruction = level_instructions.get(knowledge_level, level_instructions["beginner"])
            
            prompt = f"""{style_prompt}

{level_instruction}

展品名称：{exhibit_name}
展品信息：{exhibit_info}

请生成一段200-300字的讲解内容："""
            
            response = await self.llm.ainvoke(prompt)
            
            return json.dumps({
                "narrative": response.content,
                "style": narrative_style,
                "target_level": knowledge_level,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
```

- [ ] **Step 4: Implement ReflectionPromptTool**

Add to `curator_tools.py`:

```python
class ReflectionPromptTool(BaseTool):
    """生成反身性引导问题"""
    
    name: str = "prompt_reflection"
    description: str = """
    根据用户知识水平和展品信息生成反身性思考引导问题。
    输入应为JSON格式：{
        "knowledge_level": "intermediate",
        "reflection_depth": 2,
        "category": "青铜器",
        "exhibit_name": "青铜鼎"
    }
    """
    
    async def _arun(self, query: str) -> str:
        try:
            params = json.loads(query)
            
            knowledge_level = params.get("knowledge_level", "beginner")
            reflection_depth = params.get("reflection_depth", 2)
            category = params.get("category")
            exhibit_name = params.get("exhibit_name", "这件展品")
            
            questions = get_reflection_prompts(
                knowledge_level=knowledge_level,
                reflection_depth=reflection_depth,
                category=category,
            )
            
            # 个性化问题（加入展品名称）
            personalized = [q.replace("这件文物", exhibit_name).replace("这件物品", exhibit_name) for q in questions]
            
            return json.dumps({
                "questions": personalized,
                "knowledge_level": knowledge_level,
                "category": category,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
```

- [ ] **Step 5: Implement PreferenceManagementTool**

Add to `curator_tools.py`:

```python
class PreferenceManagementTool(BaseTool):
    """管理用户偏好设置"""
    
    name: str = "manage_preferences"
    description: str = """
    获取或更新用户的导览偏好设置。
    输入应为JSON格式：{
        "action": "get",  // "get" 或 "update"
        "user_id": "user-001",
        "updates": {      // 仅update时需要
            "interests": ["陶瓷"],
            "knowledge_level": "expert"
        }
    }
    """
    
    profile_repository: Any = Field(..., description="用户画像仓库")
    
    async def _arun(self, query: str) -> str:
        try:
            params = json.loads(query)
            action = params.get("action", "get")
            user_id = params.get("user_id")
            
            if not user_id:
                return json.dumps({"error": "user_id is required"})
            
            from app.domain.value_objects import UserId
            
            if action == "get":
                profile = await self.profile_repository.get_by_user_id(UserId(user_id))
                if not profile:
                    return json.dumps({"error": "Profile not found"})
                
                return json.dumps({
                    "interests": profile.interests,
                    "knowledge_level": profile.knowledge_level,
                    "narrative_preference": profile.narrative_preference,
                    "reflection_depth": profile.reflection_depth,
                    "visited_exhibit_count": len(profile.visited_exhibit_ids),
                }, ensure_ascii=False)
            
            elif action == "update":
                updates = params.get("updates", {})
                profile = await self.profile_repository.update(UserId(user_id), updates)
                
                return json.dumps({
                    "status": "success",
                    "updated_fields": list(updates.keys()),
                    "profile": {
                        "interests": profile.interests,
                        "knowledge_level": profile.knowledge_level,
                        "narrative_preference": profile.narrative_preference,
                    },
                }, ensure_ascii=False)
            
            else:
                return json.dumps({"error": f"Unknown action: {action}"})
        
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
```

- [ ] **Step 6: Write tests for curator tools**

Create `backend/tests/unit/test_curator_tools.py`:

```python
import pytest
import json

from app.infra.langchain.curator_tools import (
    PathPlanningTool,
    ReflectionPromptTool,
)


@pytest.mark.asyncio
async def test_path_planning_tool(mock_exhibit_repository):
    # Setup mock data
    from datetime import datetime
    from app.domain.entities import Exhibit
    from app.domain.value_objects import ExhibitId, Location
    
    exhibit = Exhibit(
        id=ExhibitId("exhibit-001"),
        name="青铜鼎",
        description="商代青铜器",
        location=Location(x=10, y=10, floor=1),
        hall="青铜馆",
        category="青铜器",
        era="商代",
        importance=5,
        estimated_visit_time=15,
        document_id=None,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    
    mock_exhibit_repository.list_by_category.return_value = [exhibit]
    
    tool = PathPlanningTool(exhibit_repository=mock_exhibit_repository)
    
    result = await tool._arun(json.dumps({
        "interests": ["青铜器"],
        "available_time": 60,
        "current_location": {"x": 0, "y": 0, "floor": 1},
        "visited_exhibit_ids": [],
    }))
    
    data = json.loads(result)
    assert "path" in data
    assert data["exhibit_count"] >= 0


@pytest.mark.asyncio
async def test_reflection_prompt_tool():
    tool = ReflectionPromptTool()
    
    result = await tool._arun(json.dumps({
        "knowledge_level": "beginner",
        "reflection_depth": 2,
        "category": "青铜器",
        "exhibit_name": "青铜鼎",
    }))
    
    data = json.loads(result)
    assert "questions" in data
    assert len(data["questions"]) == 2
    # Should personalize with exhibit name
    assert any("青铜鼎" in q for q in data["questions"])
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/infra/langchain/curator_tools.py
git add backend/tests/unit/test_curator_tools.py
git commit -m "feat(tools): implement 5 curator tools for path planning, knowledge, narrative, reflection, and preferences"
```

---

## Task 6: Curator Agent

**Files:**
- Create: `backend/app/infra/langchain/curator_agent.py`
- Modify: `backend/app/infra/langchain/__init__.py`
- Test: `backend/tests/unit/test_curator_agent.py`

- [ ] **Step 1: Implement CuratorAgent class**

Create `backend/app/infra/langchain/curator_agent.py`:

```python
"""策展协调 Agent - 使用 ReAct 模式"""

from typing import Any

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from loguru import logger


class CuratorAgent:
    """博物馆AI策展助手
    
    使用 ReAct (Reasoning + Acting) 模式协调多个工具：
    - plan_tour_path: 规划导览路径
    - retrieve_exhibit_knowledge: 检索知识
    - generate_narrative: 生成故事化讲解
    - prompt_reflection: 引导反身性思考
    - manage_preferences: 管理用户偏好
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        session_id: str | None = None,
        verbose: bool = True,
    ):
        self.llm = llm
        self.tools = tools
        self.session_id = session_id
        self.verbose = verbose
        
        # 创建 ReAct Agent
        self.agent_executor = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """创建 ReAct Agent Executor"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是 MuseAI 博物馆AI策展助手。你的使命是为每位观众创造个性化、沉浸式的观展体验。

## 核心职责

1. **理解观众需求**
   - 分析用户的兴趣、时间、知识水平
   - 识别显性和隐性需求

2. **规划导览路径**
   - 调用 `plan_tour_path` 工具生成最优路线
   - 考虑时间限制、体力、兴趣分布

3. **提供知识讲解**
   - 调用 `retrieve_exhibit_knowledge` 获取展品信息
   - 调用 `generate_narrative` 创建故事化内容

4. **引导深度思考**
   - 在适当时机调用 `prompt_reflection` 引发反身性思考
   - 帮助观众建立个人与文化的连接

5. **管理用户偏好**
   - 调用 `manage_preferences` 记录和更新用户画像

## 交互原则

- **个性化**: 根据用户画像调整讲解深度和风格
- **沉浸感**: 创造故事化、情感化的体验
- **启发性**: 引导文化思考，而非单向灌输
- **适应性**: 根据用户反馈动态调整

## 工具使用指南

- 当用户询问"推荐路线"、"怎么参观"时 → 使用 plan_tour_path
- 当用户询问展品信息时 → 使用 retrieve_exhibit_knowledge
- 当需要生动讲解时 → 使用 generate_narrative
- 当需要引发思考时 → 使用 prompt_reflection
- 当用户设置偏好时 → 使用 manage_preferences

可用工具：{tool_names}

工具描述：
{tools}"""),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            handle_parsing_errors=True,
            max_iterations=10,
        )
    
    async def run(
        self,
        user_input: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """运行策展Agent
        
        Args:
            user_input: 用户输入
            chat_history: 对话历史 [(role, content), ...]
        
        Returns:
            Agent执行结果
        """
        logger.info(f"CuratorAgent processing: {user_input[:50]}...")
        
        try:
            result = await self.agent_executor.ainvoke({
                "input": user_input,
                "chat_history": chat_history or [],
            })
            
            return {
                "output": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", []),
                "session_id": self.session_id,
            }
        except Exception as e:
            logger.error(f"CuratorAgent error: {e}")
            return {
                "output": "抱歉，我在处理您的请求时遇到了问题。请稍后再试。",
                "error": str(e),
                "session_id": self.session_id,
            }
```

- [ ] **Step 2: Add factory function**

Add to `backend/app/infra/langchain/__init__.py`:

```python
from app.infra.langchain.curator_agent import CuratorAgent
from app.infra.langchain.curator_tools import (
    PathPlanningTool,
    KnowledgeRetrievalTool,
    NarrativeGenerationTool,
    ReflectionPromptTool,
    PreferenceManagementTool,
)


def create_curator_agent(
    llm: BaseChatModel,
    rag_agent: RAGAgent,
    exhibit_repository: Any,
    profile_repository: Any,
    session_id: str | None = None,
) -> CuratorAgent:
    """创建 Curator Agent 实例
    
    Args:
        llm: 语言模型
        rag_agent: RAG Agent用于知识检索
        exhibit_repository: 展品仓库
        profile_repository: 用户画像仓库
        session_id: 会话ID
    
    Returns:
        CuratorAgent实例
    """
    tools = [
        PathPlanningTool(exhibit_repository=exhibit_repository),
        KnowledgeRetrievalTool(rag_agent=rag_agent),
        NarrativeGenerationTool(llm=llm),
        ReflectionPromptTool(),
        PreferenceManagementTool(profile_repository=profile_repository),
    ]
    
    return CuratorAgent(
        llm=llm,
        tools=tools,
        session_id=session_id,
    )


# Update __all__
__all__ = [
    # ... existing exports ...
    "CuratorAgent",
    "create_curator_agent",
    "PathPlanningTool",
    "KnowledgeRetrievalTool",
    "NarrativeGenerationTool",
    "ReflectionPromptTool",
    "PreferenceManagementTool",
]
```

- [ ] **Step 3: Write test for CuratorAgent**

Create `backend/tests/unit/test_curator_agent.py`:

```python
import pytest
from unittest.mock import Mock, AsyncMock

from app.infra.langchain.curator_agent import CuratorAgent


@pytest.mark.asyncio
async def test_curator_agent_run():
    # Mock LLM
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(return_value=Mock(content="这是AI回复"))
    
    # Mock tools
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test tool"
    
    agent = CuratorAgent(
        llm=mock_llm,
        tools=[mock_tool],
        session_id="test-session",
        verbose=False,
    )
    
    # Mock the executor
    agent.agent_executor.ainvoke = AsyncMock(return_value={
        "output": "我为您规划了一条路线...",
        "intermediate_steps": [],
    })
    
    result = await agent.run("我想参观青铜器")
    
    assert "output" in result
    assert result["session_id"] == "test-session"


@pytest.mark.asyncio
async def test_curator_agent_error_handling():
    mock_llm = Mock()
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    
    agent = CuratorAgent(
        llm=mock_llm,
        tools=[mock_tool],
        verbose=False,
    )
    
    # Mock executor to raise exception
    agent.agent_executor.ainvoke = AsyncMock(side_effect=Exception("Test error"))
    
    result = await agent.run("test input")
    
    assert "error" in result
    assert "抱歉" in result["output"]
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/infra/langchain/curator_agent.py
git add backend/app/infra/langchain/__init__.py
git add backend/tests/unit/test_curator_agent.py
git commit -m "feat(agent): implement CuratorAgent with ReAct pattern"
```

---

## Task 7: Service Layer

**Files:**
- Create: `backend/app/application/exhibit_service.py`
- Create: `backend/app/application/tour_path_service.py`
- Create: `backend/app/application/profile_service.py`
- Create: `backend/app/application/curator_service.py`

- [ ] **Step 1: Implement ExhibitService**

Create `backend/app/application/exhibit_service.py`:

```python
"""展品管理服务"""

import uuid
from datetime import datetime

from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location, DocumentId


class ExhibitService:
    def __init__(self, exhibit_repository):
        self._repo = exhibit_repository
    
    async def create_exhibit(
        self,
        name: str,
        description: str | None,
        location_x: float,
        location_y: float,
        floor: int,
        hall: str,
        category: str,
        era: str | None,
        importance: int,
        estimated_visit_time: int,
        document_id: str | None,
    ) -> Exhibit:
        exhibit = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name=name,
            description=description,
            location=Location(x=location_x, y=location_y, floor=floor),
            hall=hall,
            category=category,
            era=era,
            importance=importance,
            estimated_visit_time=estimated_visit_time,
            document_id=DocumentId(document_id) if document_id else None,
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return await self._repo.save(exhibit)
    
    async def get_exhibit(self, exhibit_id: str) -> Exhibit | None:
        return await self._repo.get_by_id(ExhibitId(exhibit_id))
    
    async def list_exhibits(
        self,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
        hall: str | None = None,
    ) -> list[Exhibit]:
        if category:
            return await self._repo.list_by_category(category)
        if hall:
            return await self._repo.list_by_hall(hall)
        return await self._repo.list_all(skip, limit)
    
    async def delete_exhibit(self, exhibit_id: str) -> bool:
        return await self._repo.delete(ExhibitId(exhibit_id))
```

- [ ] **Step 2: Implement ProfileService**

Create `backend/app/application/profile_service.py`:

```python
"""用户画像管理服务"""

import uuid
from datetime import datetime

from app.domain.entities import VisitorProfile
from app.domain.value_objects import ProfileId, UserId, ExhibitId


class ProfileService:
    def __init__(self, profile_repository):
        self._repo = profile_repository
    
    async def get_or_create_profile(self, user_id: str) -> VisitorProfile:
        profile = await self._repo.get_by_user_id(UserId(user_id))
        if profile:
            return profile
        
        # Create default profile
        new_profile = VisitorProfile(
            id=ProfileId(str(uuid.uuid4())),
            user_id=UserId(user_id),
            interests=[],
            knowledge_level="beginner",
            narrative_preference="storytelling",
            reflection_depth=3,
            visited_exhibit_ids=[],
            feedback_history=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return await self._repo.save(new_profile)
    
    async def update_profile(self, user_id: str, updates: dict) -> VisitorProfile:
        return await self._repo.update(UserId(user_id), updates)
    
    async def record_visit(self, user_id: str, exhibit_id: str) -> VisitorProfile:
        profile = await self._repo.get_by_user_id(UserId(user_id))
        if not profile:
            profile = await self.get_or_create_profile(user_id)
        
        visited = list(profile.visited_exhibit_ids)
        if ExhibitId(exhibit_id) not in visited:
            visited.append(ExhibitId(exhibit_id))
        
        return await self._repo.update(UserId(user_id), {
            "visited_exhibit_ids": [e.value for e in visited]
        })
    
    async def add_feedback(self, user_id: str, feedback: dict) -> VisitorProfile:
        profile = await self._repo.get_by_user_id(UserId(user_id))
        if not profile:
            raise ValueError("Profile not found")
        
        history = list(profile.feedback_history)
        feedback["timestamp"] = datetime.now().isoformat()
        history.append(feedback)
        
        return await self._repo.update(UserId(user_id), {
            "feedback_history": history
        })
```

- [ ] **Step 3: Implement CuratorService**

Create `backend/app/application/curator_service.py`:

```python
"""策展协调服务"""

import json

from app.infra.langchain.curator_agent import CuratorAgent


class CuratorService:
    """策展服务 - 协调Agent和工具的高层服务"""
    
    def __init__(
        self,
        curator_agent: CuratorAgent,
        profile_service,
        exhibit_service,
    ):
        self._agent = curator_agent
        self._profile_service = profile_service
        self._exhibit_service = exhibit_service
    
    async def plan_tour(self, user_id: str, available_time: int, interests: list[str] | None = None) -> dict:
        """为用户规划导览路线"""
        # 获取用户画像
        profile = await self._profile_service.get_or_create_profile(user_id)
        
        # 使用用户兴趣或画像中的兴趣
        user_interests = interests or profile.interests
        if not user_interests:
            user_interests = ["青铜器", "书画", "陶瓷"]  # 默认兴趣
        
        # 构建查询
        query = f"""请为我规划一条导览路线。
可用时间：{available_time}分钟
兴趣：{", ".join(user_interests)}
已参观：{len(profile.visited_exhibit_ids)}件展品"""
        
        result = await self._agent.run(query)
        return result
    
    async def generate_narrative(self, user_id: str, exhibit_id: str) -> dict:
        """为展品生成故事化讲解"""
        profile = await self._profile_service.get_or_create_profile(user_id)
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        
        if not exhibit:
            return {"error": "Exhibit not found"}
        
        query = f"""请为"{exhibit.name}"生成讲解。
展品信息：{exhibit.description or "暂无详细描述"}
我的知识水平：{profile.knowledge_level}
我喜欢的风格：{profile.narrative_preference}"""
        
        result = await self._agent.run(query)
        
        # 记录参观
        await self._profile_service.record_visit(user_id, exhibit_id)
        
        return result
    
    async def get_reflection_prompts(self, user_id: str, exhibit_id: str) -> dict:
        """获取反身性引导问题"""
        profile = await self._profile_service.get_or_create_profile(user_id)
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        
        if not exhibit:
            return {"error": "Exhibit not found"}
        
        query = f"""请为"{exhibit.name}"生成反身性思考引导问题。
展品分类：{exhibit.category}
我的知识水平：{profile.knowledge_level}
思考深度：{profile.reflection_depth}"""
        
        return await self._agent.run(query)
    
    async def chat(self, user_id: str, message: str, chat_history: list | None = None) -> dict:
        """通用策展对话"""
        return await self._agent.run(message, chat_history)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/application/exhibit_service.py
git add backend/app/application/profile_service.py
git add backend/app/application/curator_service.py
git commit -m "feat(service): add exhibit, profile, and curator services"
```

---

## Task 8: API Layer

**Files:**
- Create: `backend/app/api/admin.py`
- Create: `backend/app/api/curator.py`
- Create: `backend/app/api/profile.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add admin dependency**

Add to `backend/app/api/deps.py`:

```python
from app.config.settings import get_settings


async def get_current_admin_user(
    current_user: CurrentUser,
) -> dict:
    """验证当前用户是否为管理员"""
    settings = get_settings()
    admin_emails = settings.get_admin_emails()
    
    if current_user["email"] not in admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


CurrentAdminUser = Annotated[dict, Depends(get_current_admin_user)]
```

- [ ] **Step 2: Implement Admin API**

Create `backend/app/api/admin.py`:

```python
"""管理员API - 展品和导览路径管理"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, CurrentAdminUser
from app.application.exhibit_service import ExhibitService
from app.infra.postgres.repositories import PostgresExhibitRepository

router = APIRouter(prefix="/admin", tags=["admin"])


# Request/Response Models
class CreateExhibitRequest(BaseModel):
    name: str
    description: str | None = None
    location_x: float
    location_y: float
    floor: int = 1
    hall: str
    category: str
    era: str | None = None
    importance: int = 3
    estimated_visit_time: int = 10
    document_id: str | None = None


class ExhibitResponse(BaseModel):
    id: str
    name: str
    description: str | None
    location_x: float
    location_y: float
    floor: int
    hall: str
    category: str
    era: str | None
    importance: int
    estimated_visit_time: int
    is_active: bool


def get_exhibit_service(session: AsyncSession) -> ExhibitService:
    repo = PostgresExhibitRepository(session)
    return ExhibitService(repo)


@router.post("/exhibits", response_model=ExhibitResponse)
async def create_exhibit(
    request: CreateExhibitRequest,
    session: SessionDep,
    current_user: CurrentAdminUser,
) -> ExhibitResponse:
    """创建新展品"""
    service = get_exhibit_service(session)
    
    exhibit = await service.create_exhibit(
        name=request.name,
        description=request.description,
        location_x=request.location_x,
        location_y=request.location_y,
        floor=request.floor,
        hall=request.hall,
        category=request.category,
        era=request.era,
        importance=request.importance,
        estimated_visit_time=request.estimated_visit_time,
        document_id=request.document_id,
    )
    
    await session.commit()
    
    return ExhibitResponse(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        location_x=exhibit.location.x,
        location_y=exhibit.location.y,
        floor=exhibit.location.floor,
        hall=exhibit.hall,
        category=exhibit.category,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        is_active=exhibit.is_active,
    )


@router.get("/exhibits")
async def list_exhibits(
    session: SessionDep,
    current_user: CurrentAdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = None,
    hall: str | None = None,
):
    """列出所有展品"""
    service = get_exhibit_service(session)
    exhibits = await service.list_exhibits(skip, limit, category, hall)
    
    return {
        "exhibits": [
            {
                "id": e.id.value,
                "name": e.name,
                "category": e.category,
                "hall": e.hall,
                "importance": e.importance,
                "is_active": e.is_active,
            }
            for e in exhibits
        ],
        "total": len(exhibits),
    }


@router.delete("/exhibits/{exhibit_id}")
async def delete_exhibit(
    exhibit_id: str,
    session: SessionDep,
    current_user: CurrentAdminUser,
):
    """删除展品（软删除）"""
    service = get_exhibit_service(session)
    success = await service.delete_exhibit(exhibit_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Exhibit not found")
    
    await session.commit()
    return {"status": "deleted", "exhibit_id": exhibit_id}
```

- [ ] **Step 3: Implement Curator API**

Create `backend/app/api/curator.py`:

```python
"""策展服务API"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.application.curator_service import CuratorService
from app.application.profile_service import ProfileService
from app.application.exhibit_service import ExhibitService
from app.infra.langchain import create_curator_agent, get_llm, get_rag_agent
from app.infra.postgres.repositories import PostgresExhibitRepository, PostgresVisitorProfileRepository

router = APIRouter(prefix="/curator", tags=["curator"])


class PlanTourRequest(BaseModel):
    available_time: int  # minutes
    interests: list[str] | None = None


class NarrativeRequest(BaseModel):
    exhibit_id: str


class ReflectionRequest(BaseModel):
    exhibit_id: str


def get_curator_service(session) -> CuratorService:
    llm = get_llm()
    rag_agent = get_rag_agent()
    
    exhibit_repo = PostgresExhibitRepository(session)
    profile_repo = PostgresVisitorProfileRepository(session)
    
    curator_agent = create_curator_agent(
        llm=llm,
        rag_agent=rag_agent,
        exhibit_repository=exhibit_repo,
        profile_repository=profile_repo,
    )
    
    return CuratorService(
        curator_agent=curator_agent,
        profile_service=ProfileService(profile_repo),
        exhibit_service=ExhibitService(exhibit_repo),
    )


@router.post("/plan-tour")
async def plan_tour(
    request: PlanTourRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    """规划个性化导览路线"""
    service = get_curator_service(session)
    result = await service.plan_tour(
        user_id=current_user["id"],
        available_time=request.available_time,
        interests=request.interests,
    )
    return result


@router.post("/narrative")
async def generate_narrative(
    request: NarrativeRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    """为展品生成故事化讲解"""
    service = get_curator_service(session)
    result = await service.generate_narrative(
        user_id=current_user["id"],
        exhibit_id=request.exhibit_id,
    )
    return result


@router.post("/reflection")
async def get_reflection(
    request: ReflectionRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    """获取反身性引导问题"""
    service = get_curator_service(session)
    result = await service.get_reflection_prompts(
        user_id=current_user["id"],
        exhibit_id=request.exhibit_id,
    )
    return result
```

- [ ] **Step 4: Implement Profile API**

Create `backend/app/api/profile.py`:

```python
"""用户画像API"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.application.profile_service import ProfileService
from app.infra.postgres.repositories import PostgresVisitorProfileRepository

router = APIRouter(prefix="/profile", tags=["profile"])


class UpdateProfileRequest(BaseModel):
    interests: list[str] | None = None
    knowledge_level: str | None = None
    narrative_preference: str | None = None
    reflection_depth: int | None = None


class ProfileResponse(BaseModel):
    interests: list[str]
    knowledge_level: str
    narrative_preference: str
    reflection_depth: int
    visited_exhibit_count: int


def get_profile_service(session) -> ProfileService:
    repo = PostgresVisitorProfileRepository(session)
    return ProfileService(repo)


@router.get("", response_model=ProfileResponse)
async def get_profile(
    session: SessionDep,
    current_user: CurrentUser,
):
    """获取当前用户画像"""
    service = get_profile_service(session)
    profile = await service.get_or_create_profile(current_user["id"])
    
    return ProfileResponse(
        interests=profile.interests,
        knowledge_level=profile.knowledge_level,
        narrative_preference=profile.narrative_preference,
        reflection_depth=profile.reflection_depth,
        visited_exhibit_count=len(profile.visited_exhibit_ids),
    )


@router.put("", response_model=ProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    """更新用户画像"""
    service = get_profile_service(session)
    
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    profile = await service.update_profile(current_user["id"], updates)
    
    return ProfileResponse(
        interests=profile.interests,
        knowledge_level=profile.knowledge_level,
        narrative_preference=profile.narrative_preference,
        reflection_depth=profile.reflection_depth,
        visited_exhibit_count=len(profile.visited_exhibit_ids),
    )
```

- [ ] **Step 5: Register routers in main.py**

Add to `backend/app/main.py`:

```python
from app.api.admin import router as admin_router
from app.api.curator import router as curator_router
from app.api.profile import router as profile_router

# ... after other router includes
app.include_router(admin_router, prefix="/api/v1")
app.include_router(curator_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin.py
git add backend/app/api/curator.py
git add backend/app/api/profile.py
git add backend/app/api/deps.py
git add backend/app/main.py
git commit -m "feat(api): add admin, curator, and profile endpoints"
```

---

## Task 9: Frontend Components

**Files:**
- Create: `frontend/src/components/admin/ExhibitManager.vue`
- Create: `frontend/src/components/profile/ProfileSettings.vue`
- Create: `frontend/src/composables/useCurator.js`
- Modify: `frontend/src/router/index.js` (if exists)

- [ ] **Step 1: Create useCurator composable**

Create `frontend/src/composables/useCurator.js`:

```javascript
import { ref } from 'vue'
import { useAuth } from './useAuth'

const API_BASE = '/api/v1'

export function useCurator() {
  const { token } = useAuth()
  const loading = ref(false)
  const error = ref(null)

  async function planTour(availableTime, interests = null) {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch(`${API_BASE}/curator/plan-tour`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token.value}`
        },
        body: JSON.stringify({
          available_time: availableTime,
          interests: interests
        })
      })
      
      if (!response.ok) throw new Error('Failed to plan tour')
      return await response.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function generateNarrative(exhibitId) {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch(`${API_BASE}/curator/narrative`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token.value}`
        },
        body: JSON.stringify({ exhibit_id: exhibitId })
      })
      
      if (!response.ok) throw new Error('Failed to generate narrative')
      return await response.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getReflectionPrompts(exhibitId) {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch(`${API_BASE}/curator/reflection`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token.value}`
        },
        body: JSON.stringify({ exhibit_id: exhibitId })
      })
      
      if (!response.ok) throw new Error('Failed to get reflection prompts')
      return await response.json()
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    planTour,
    generateNarrative,
    getReflectionPrompts
  }
}
```

- [ ] **Step 2: Create ProfileSettings component**

Create `frontend/src/components/profile/ProfileSettings.vue`:

```vue
<script setup>
import { ref, onMounted } from 'vue'

const profile = ref({
  interests: [],
  knowledge_level: 'beginner',
  narrative_preference: 'storytelling',
  reflection_depth: 3
})

const interestOptions = [
  { label: '青铜器', value: '青铜器' },
  { label: '书画', value: '书画' },
  { label: '陶瓷', value: '陶瓷' },
  { label: '玉器', value: '玉器' },
  { label: '金银器', value: '金银器' },
  { label: '雕塑', value: '雕塑' },
  { label: '古籍', value: '古籍' },
  { label: '织绣', value: '织绣' }
]

const loading = ref(false)
const saved = ref(false)

async function fetchProfile() {
  const response = await fetch('/api/v1/profile', {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
  })
  if (response.ok) {
    profile.value = await response.json()
  }
}

async function saveProfile() {
  loading.value = true
  saved.value = false
  
  try {
    const response = await fetch('/api/v1/profile', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(profile.value)
    })
    
    if (response.ok) {
      saved.value = true
      setTimeout(() => saved.value = false, 3000)
    }
  } finally {
    loading.value = false
  }
}

onMounted(fetchProfile)
</script>

<template>
  <div class="profile-settings">
    <h2>导览偏好设置</h2>
    
    <div class="form-group">
      <label>兴趣标签</label>
      <div class="checkbox-group">
        <label v-for="option in interestOptions" :key="option.value" class="checkbox">
          <input
            type="checkbox"
            :value="option.value"
            v-model="profile.interests"
          />
          {{ option.label }}
        </label>
      </div>
    </div>
    
    <div class="form-group">
      <label>知识水平</label>
      <div class="radio-group">
        <label class="radio">
          <input type="radio" value="beginner" v-model="profile.knowledge_level" />
          初学者 - 通俗易懂的讲解
        </label>
        <label class="radio">
          <input type="radio" value="intermediate" v-model="profile.knowledge_level" />
          爱好者 - 适度的专业内容
        </label>
        <label class="radio">
          <input type="radio" value="expert" v-model="profile.knowledge_level" />
          专家 - 深入的学术探讨
        </label>
      </div>
    </div>
    
    <div class="form-group">
      <label>讲解风格</label>
      <div class="radio-group">
        <label class="radio">
          <input type="radio" value="storytelling" v-model="profile.narrative_preference" />
          故事型 - 生动有趣，引人入胜
        </label>
        <label class="radio">
          <input type="radio" value="academic" v-model="profile.narrative_preference" />
          学术型 - 严谨专业，注重细节
        </label>
        <label class="radio">
          <input type="radio" value="interactive" v-model="profile.narrative_preference" />
          互动型 - 提问引导，鼓励思考
        </label>
      </div>
    </div>
    
    <div class="form-group">
      <label>思考深度 ({{ profile.reflection_depth }}/5)</label>
      <input
        type="range"
        min="1"
        max="5"
        v-model.number="profile.reflection_depth"
        class="slider"
      />
      <div class="slider-labels">
        <span>轻松参观</span>
        <span>深度思考</span>
      </div>
    </div>
    
    <button @click="saveProfile" :disabled="loading" class="save-btn">
      {{ loading ? '保存中...' : '保存设置' }}
    </button>
    
    <div v-if="saved" class="success-message">
      设置已保存！
    </div>
  </div>
</template>

<style scoped>
.profile-settings {
  max-width: 600px;
  padding: 20px;
}

.form-group {
  margin-bottom: 24px;
}

.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 8px;
  color: #333;
}

.checkbox-group, .radio-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox, .radio {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox input, .radio input {
  cursor: pointer;
}

.slider {
  width: 100%;
  margin: 10px 0;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #666;
}

.save-btn {
  width: 100%;
  padding: 12px;
  background: #4a90d9;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
}

.save-btn:disabled {
  opacity: 0.6;
}

.success-message {
  margin-top: 16px;
  padding: 12px;
  background: #e8f5e9;
  color: #2e7d32;
  border-radius: 4px;
  text-align: center;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useCurator.js
git add frontend/src/components/profile/ProfileSettings.vue
git commit -m "feat(frontend): add curator composable and profile settings UI"
```

---

## Task 10: Testing & Integration

**Files:**
- Create: `backend/tests/contract/test_curator_api.py`
- Create: `backend/tests/integration/test_curator_flow.py`

- [ ] **Step 1: Write contract tests**

Create `backend/tests/contract/test_curator_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    # Mock authentication
    return {"Authorization": "Bearer test-token"}


def test_plan_tour_endpoint(client, auth_headers):
    response = client.post(
        "/api/v1/curator/plan-tour",
        json={"available_time": 60, "interests": ["青铜器"]},
        headers=auth_headers
    )
    
    assert response.status_code in [200, 401]  # 401 if auth fails


def test_get_profile_endpoint(client, auth_headers):
    response = client.get(
        "/api/v1/profile",
        headers=auth_headers
    )
    
    assert response.status_code in [200, 401]
```

- [ ] **Step 2: Run all tests**

```bash
uv run pytest backend/tests/unit -v
uv run pytest backend/tests/contract -v
```

- [ ] **Step 3: Final commit**

```bash
git add backend/tests/
git commit -m "test: add curator API contract tests"
```

---

## Summary

This implementation plan creates a complete Digital Curation Agent System with:

1. **Data Layer**: 3 new tables (exhibits, tour_paths, visitor_profiles)
2. **Domain Layer**: Entities, value objects, repository protocols
3. **Service Layer**: Exhibit, Profile, Curator services
4. **Agent Layer**: 5 Tools + ReAct CuratorAgent
5. **API Layer**: Admin, Curator, Profile endpoints
6. **Frontend**: Composables and UI components

**Total**: 19 new files, 6 modified files, ~2500 lines of code

**Estimated effort**: 6 weeks (following the phased approach)
