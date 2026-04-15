# 半坡博物馆 AI 导览游客流程 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的游客导览流程，包括引导问卷、3种身份导览、展厅选择、展品交互、游览报告。

**Architecture:** 独立导览模式，新增 `/tour` 路由，与现有聊天/策展人功能解耦。后端遵循 API→Application→Domain→Infrastructure 分层，前端使用 Composable + 组件化。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3, Element Plus, SSE, RAG (LangGraph)

**Spec:** `docs/superpowers/specs/2026-04-15-tour-visitor-flow-design.md`

---

## File Structure

### Backend - New Files

| File | Responsibility |
|------|---------------|
| `backend/app/domain/value_objects.py` | 新增 TourSessionId, TourEventId, TourReportId |
| `backend/app/domain/entities.py` | 新增 TourSession, TourEvent, TourReport 实体 |
| `backend/app/domain/exceptions.py` | 新增 TourSessionNotFound, TourSessionExpired |
| `backend/app/infra/postgres/models.py` | 新增 TourSessionModel, TourEventModel, TourReportModel ORM |
| `backend/alembic/versions/20260415_add_tour_tables.py` | 数据库迁移脚本 |
| `backend/app/application/tour_session_service.py` | 导览会话 CRUD + 状态管理 |
| `backend/app/application/tour_event_service.py` | 导览事件记录与查询 |
| `backend/app/application/tour_chat_service.py` | 导览专属 SSE 流式聊天 + 身份人设注入 |
| `backend/app/application/tour_report_service.py` | 游览报告生成（聚合 + 五型图 + 标签 + 一句话） |
| `backend/app/api/tour.py` | 导览 API 路由（10 个端点） |
| `backend/tests/unit/test_tour_entities.py` | 领域实体单元测试 |
| `backend/tests/unit/test_tour_report_service.py` | 报告服务单元测试（五型图、标签） |
| `backend/tests/contract/test_tour_api.py` | API 契约测试 |

### Backend - Modified Files

| File | Changes |
|------|---------|
| `backend/app/main.py` | 注册 tour_router |
| `backend/app/infra/postgres/models.py` | Exhibit 模型新增 display_order 字段 |

### Frontend - New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/composables/useTour.js` | 导览状态管理 Composable |
| `frontend/src/views/TourView.vue` | 导览主容器（状态机 + 全屏布局） |
| `frontend/src/components/tour/OnboardingQuiz.vue` | 引导问卷（3道选择题） |
| `frontend/src/components/tour/OpeningNarrative.vue` | 开场白展示 |
| `frontend/src/components/tour/HallSelect.vue` | 展厅选择 |
| `frontend/src/components/tour/ExhibitTour.vue` | 展厅导览+展品交互 |
| `frontend/src/components/tour/HallIntro.vue` | 展厅介绍 |
| `frontend/src/components/tour/ExhibitChat.vue` | 展品对话（SSE流式） |
| `frontend/src/components/tour/ExhibitNavigator.vue` | 深入/下一个导航 |
| `frontend/src/components/tour/TourReport.vue` | 游览报告 |
| `frontend/src/components/tour/TourStats.vue` | 游览统计 |
| `frontend/src/components/tour/IdentityTags.vue` | 身份标签 |
| `frontend/src/components/tour/RadarChart.vue` | 五型图（Canvas雷达图） |
| `frontend/src/components/tour/TourOneLiner.vue` | 游览一句话 |

### Frontend - Modified Files

| File | Changes |
|------|---------|
| `frontend/src/api/index.js` | 新增 tour API 命名空间 |
| `frontend/src/router/index.js` | 新增 /tour 路由 |
| `frontend/src/App.vue` | 导览模式下隐藏 Header/Sidebar |

---

## Chunk 1: Backend Domain Layer

### Task 1: 新增值对象

**Files:**
- Modify: `backend/app/domain/value_objects.py`

- [ ] **Step 1: 在 value_objects.py 末尾新增 3 个值对象**

```python
@dataclass(frozen=True)
class TourSessionId:
    value: str


@dataclass(frozen=True)
class TourEventId:
    value: str


@dataclass(frozen=True)
class TourReportId:
    value: str
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/domain/value_objects.py
git commit -m "feat(tour): add TourSessionId, TourEventId, TourReportId value objects"
```

### Task 2: 新增领域实体

**Files:**
- Modify: `backend/app/domain/entities.py`

- [ ] **Step 1: 更新 import，新增值对象引用**

在文件顶部的 import 中添加 `TourSessionId`, `TourEventId`, `TourReportId`：

```python
from .value_objects import DocumentId, ExhibitId, JobId, Location, ProfileId, PromptId, SessionId, TourEventId, TourPathId, TourReportId, TourSessionId, UserId
```

- [ ] **Step 2: 在文件末尾新增 3 个实体类**

```python
@dataclass
class TourSession:
    id: TourSessionId
    user_id: UserId | None
    guest_id: str | None
    session_token: str
    interest_type: str
    persona: str
    assumption: str
    current_hall: str | None
    current_exhibit_id: ExhibitId | None
    visited_halls: list[str]
    visited_exhibit_ids: list[str]
    status: str
    last_active_at: datetime
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    def start_tour(self) -> None:
        if self.status != "onboarding":
            raise ValueError("Can only start tour from onboarding status")
        self.status = "opening"

    def begin_touring(self) -> None:
        if self.status not in ("opening", "touring"):
            raise ValueError("Can only begin touring from opening or touring status")
        self.status = "touring"

    def complete(self) -> None:
        if self.status != "touring":
            raise ValueError("Can only complete from touring status")
        self.status = "completed"
        from datetime import UTC
        self.completed_at = datetime.now(UTC)

    def touch_active(self) -> None:
        from datetime import UTC
        self.last_active_at = datetime.now(UTC)


@dataclass
class TourEvent:
    id: TourEventId
    tour_session_id: TourSessionId
    event_type: str
    exhibit_id: ExhibitId | None
    hall: str | None
    duration_seconds: int | None
    metadata: dict | None
    created_at: datetime


@dataclass
class TourReport:
    id: TourReportId
    tour_session_id: TourSessionId
    total_duration_minutes: float
    most_viewed_exhibit_id: ExhibitId | None
    most_viewed_exhibit_duration: int | None
    longest_hall: str | None
    longest_hall_duration: int | None
    total_questions: int
    total_exhibits_viewed: int
    ceramic_questions: int
    identity_tags: list[str]
    radar_scores: dict
    one_liner: str
    report_theme: str
    created_at: datetime
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/domain/entities.py
git commit -m "feat(tour): add TourSession, TourEvent, TourReport domain entities"
```

### Task 3: 新增领域异常

**Files:**
- Modify: `backend/app/domain/exceptions.py`

- [ ] **Step 1: 在文件末尾新增导览相关异常**

```python
class TourSessionNotFound(DomainError):
    pass


class TourSessionExpired(DomainError):
    pass


class TourSessionTokenMismatch(DomainError):
    pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/domain/exceptions.py
git commit -m "feat(tour): add TourSession domain exceptions"
```

### Task 4: 领域实体单元测试

**Files:**
- Create: `backend/tests/unit/test_tour_entities.py`

- [ ] **Step 1: 编写 TourSession 状态转换测试**

```python
from datetime import UTC, datetime

import pytest

from app.domain.entities import TourSession
from app.domain.value_objects import TourSessionId, UserId


def _make_session(**overrides):
    defaults = dict(
        id=TourSessionId("test-id"),
        user_id=None,
        guest_id="guest-123",
        session_token="token-abc",
        interest_type="A",
        persona="A",
        assumption="A",
        current_hall=None,
        current_exhibit_id=None,
        visited_halls=[],
        visited_exhibit_ids=[],
        status="onboarding",
        last_active_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=None,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return TourSession(**defaults)


def test_start_tour_transitions_from_onboarding_to_opening():
    session = _make_session(status="onboarding")
    session.start_tour()
    assert session.status == "opening"


def test_start_tour_raises_from_non_onboarding():
    session = _make_session(status="touring")
    with pytest.raises(ValueError, match="Can only start tour from onboarding"):
        session.start_tour()


def test_begin_touring_transitions_from_opening():
    session = _make_session(status="opening")
    session.begin_touring()
    assert session.status == "touring"


def test_begin_touring_allows_from_touring():
    session = _make_session(status="touring")
    session.begin_touring()
    assert session.status == "touring"


def test_complete_transitions_from_touring():
    session = _make_session(status="touring")
    session.complete()
    assert session.status == "completed"
    assert session.completed_at is not None


def test_complete_raises_from_non_touring():
    session = _make_session(status="onboarding")
    with pytest.raises(ValueError, match="Can only complete from touring"):
        session.complete()


def test_touch_active_updates_last_active_at():
    session = _make_session()
    old_time = session.last_active_at
    session.touch_active()
    assert session.last_active_at >= old_time
```

- [ ] **Step 2: 运行测试验证通过**

Run: `uv run pytest backend/tests/unit/test_tour_entities.py -v`
Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_tour_entities.py
git commit -m "test(tour): add TourSession entity state transition tests"
```

---

## Chunk 2: Backend Infrastructure Layer

### Task 5: 新增 ORM 模型

**Files:**
- Modify: `backend/app/infra/postgres/models.py`

- [ ] **Step 1: 更新 import，新增值对象引用**

在文件顶部的 import 中添加 `TourEventId`, `TourReportId`, `TourSessionId`：

```python
from app.domain.value_objects import (
    DocumentId,
    ExhibitId,
    JobId,
    Location,
    ProfileId,
    PromptId,
    SessionId,
    TourEventId,
    TourPathId,
    TourReportId,
    TourSessionId,
    UserId,
)
```

- [ ] **Step 2: 在 Exhibit 模型中新增 display_order 字段**

在 Exhibit 类的 `is_active` 字段之后添加：

```python
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

更新 Exhibit.to_entity() 方法，添加 display_order 参数：

```python
    def to_entity(self):
        from app.domain.entities import Exhibit as ExhibitEntity
        return ExhibitEntity(
            id=ExhibitId(self.id),
            name=self.name,
            description=self.description or "",
            location=Location(x=self.location_x or 0.0, y=self.location_y or 0.0),
            hall=self.hall or "",
            category=self.category or "",
            era=self.era or "",
            importance=self.importance,
            estimated_visit_time=self.estimated_visit_time or 0,
            document_id=self.document_id or "",
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
```

注意：Exhibit 实体暂不添加 display_order 字段（YAGNI，仅在 ORM 层存储，服务层直接读取 ORM 模型）。

- [ ] **Step 3: 在文件末尾新增 3 个 ORM 模型**

```python
class TourSessionModel(Base):
    __tablename__ = "tour_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    guest_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    session_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    interest_type: Mapped[str] = mapped_column(String(1), nullable=False)
    persona: Mapped[str] = mapped_column(String(1), nullable=False)
    assumption: Mapped[str] = mapped_column(String(1), nullable=False)
    current_hall: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_exhibit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exhibits.id"), nullable=True)
    visited_halls: Mapped[list] = mapped_column(JSON, default=list)
    visited_exhibit_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="onboarding", nullable=False, index=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        sa.CheckConstraint("user_id IS NOT NULL OR guest_id IS NOT NULL", name="ck_tour_session_owner"),
    )

    def to_entity(self):
        from app.domain.entities import TourSession as TourSessionEntity
        return TourSessionEntity(
            id=TourSessionId(self.id),
            user_id=UserId(self.user_id) if self.user_id else None,
            guest_id=self.guest_id,
            session_token=self.session_token,
            interest_type=self.interest_type,
            persona=self.persona,
            assumption=self.assumption,
            current_hall=self.current_hall,
            current_exhibit_id=ExhibitId(self.current_exhibit_id) if self.current_exhibit_id else None,
            visited_halls=self.visited_halls or [],
            visited_exhibit_ids=self.visited_exhibit_ids or [],
            status=self.status,
            last_active_at=self.last_active_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            created_at=self.created_at,
        )

    user: Mapped["User | None"] = relationship(back_populates="tour_sessions")
    events: Mapped[list["TourEventModel"]] = relationship(back_populates="tour_session", cascade="all, delete-orphan")
    report: Mapped["TourReportModel | None"] = relationship(back_populates="tour_session", uselist=False, cascade="all, delete-orphan")


class TourEventModel(Base):
    __tablename__ = "tour_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tour_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("tour_sessions.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    exhibit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exhibits.id"), nullable=True)
    hall: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        sa.Index("ix_tour_events_session_type", "tour_session_id", "event_type"),
    )

    def to_entity(self):
        from app.domain.entities import TourEvent as TourEventEntity
        return TourEventEntity(
            id=TourEventId(self.id),
            tour_session_id=TourSessionId(self.tour_session_id),
            event_type=self.event_type,
            exhibit_id=ExhibitId(self.exhibit_id) if self.exhibit_id else None,
            hall=self.hall,
            duration_seconds=self.duration_seconds,
            metadata=self.metadata,
            created_at=self.created_at,
        )

    tour_session: Mapped["TourSessionModel"] = relationship(back_populates="events")


class TourReportModel(Base):
    __tablename__ = "tour_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tour_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("tour_sessions.id"), nullable=False, unique=True, index=True)
    total_duration_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    most_viewed_exhibit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exhibits.id"), nullable=True)
    most_viewed_exhibit_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    longest_hall: Mapped[str | None] = mapped_column(String(50), nullable=True)
    longest_hall_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    total_exhibits_viewed: Mapped[int] = mapped_column(Integer, nullable=False)
    ceramic_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    identity_tags: Mapped[list] = mapped_column(JSON, default=list)
    radar_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    one_liner: Mapped[str] = mapped_column(Text, nullable=False)
    report_theme: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def to_entity(self):
        from app.domain.entities import TourReport as TourReportEntity
        return TourReportEntity(
            id=TourReportId(self.id),
            tour_session_id=TourSessionId(self.tour_session_id),
            total_duration_minutes=self.total_duration_minutes,
            most_viewed_exhibit_id=ExhibitId(self.most_viewed_exhibit_id) if self.most_viewed_exhibit_id else None,
            most_viewed_exhibit_duration=self.most_viewed_exhibit_duration,
            longest_hall=self.longest_hall,
            longest_hall_duration=self.longest_hall_duration,
            total_questions=self.total_questions,
            total_exhibits_viewed=self.total_exhibits_viewed,
            ceramic_questions=self.ceramic_questions,
            identity_tags=self.identity_tags or [],
            radar_scores=self.radar_scores or {},
            one_liner=self.one_liner,
            report_theme=self.report_theme,
            created_at=self.created_at,
        )

    tour_session: Mapped["TourSessionModel"] = relationship(back_populates="report")
```

- [ ] **Step 4: 在 User 模型中添加 tour_sessions 关系**

在 User 类的 `created_tour_paths` 关系之后添加：

```python
    tour_sessions: Mapped[list["TourSessionModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

- [ ] **Step 5: 在文件顶部添加 sa import（用于 CheckConstraint 和 Index）**

确保 import 中有 `import sqlalchemy as sa`（如果没有，在 from sqlalchemy 行之后添加）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/infra/postgres/models.py
git commit -m "feat(tour): add TourSessionModel, TourEventModel, TourReportModel ORM models"
```

### Task 6: Alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/20260415_add_tour_tables.py`

- [ ] **Step 1: 编写迁移脚本**

```python
"""Add tour_sessions, tour_events, tour_reports tables and exhibit display_order

Revision ID: 20260415_add_tour_tables
Revises: 20250408_add_prompts
Create Date: 2026-04-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260415_add_tour_tables'
down_revision: str | None = '20250408_add_prompts'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'tour_sessions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('guest_id', sa.String(64), nullable=True),
        sa.Column('session_token', sa.String(64), nullable=False),
        sa.Column('interest_type', sa.String(1), nullable=False),
        sa.Column('persona', sa.String(1), nullable=False),
        sa.Column('assumption', sa.String(1), nullable=False),
        sa.Column('current_hall', sa.String(50), nullable=True),
        sa.Column('current_exhibit_id', sa.String(36), nullable=True),
        sa.Column('visited_halls', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('visited_exhibit_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['current_exhibit_id'], ['exhibits.id'], ondelete='SET NULL'),
        sa.CheckConstraint('user_id IS NOT NULL OR guest_id IS NOT NULL', name='ck_tour_session_owner'),
    )
    op.create_index('ix_tour_sessions_user_id', 'tour_sessions', ['user_id'])
    op.create_index('ix_tour_sessions_guest_id', 'tour_sessions', ['guest_id'])
    op.create_index('ix_tour_sessions_session_token', 'tour_sessions', ['session_token'])
    op.create_index('ix_tour_sessions_status', 'tour_sessions', ['status'])

    op.create_table(
        'tour_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tour_session_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('exhibit_id', sa.String(36), nullable=True),
        sa.Column('hall', sa.String(50), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tour_session_id'], ['tour_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exhibit_id'], ['exhibits.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_tour_events_session_type', 'tour_events', ['tour_session_id', 'event_type'])

    op.create_table(
        'tour_reports',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tour_session_id', sa.String(36), nullable=False),
        sa.Column('total_duration_minutes', sa.Float(), nullable=False),
        sa.Column('most_viewed_exhibit_id', sa.String(36), nullable=True),
        sa.Column('most_viewed_exhibit_duration', sa.Integer(), nullable=True),
        sa.Column('longest_hall', sa.String(50), nullable=True),
        sa.Column('longest_hall_duration', sa.Integer(), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('total_exhibits_viewed', sa.Integer(), nullable=False),
        sa.Column('ceramic_questions', sa.Integer(), nullable=False),
        sa.Column('identity_tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('radar_scores', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('one_liner', sa.Text(), nullable=False),
        sa.Column('report_theme', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tour_session_id'], ['tour_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['most_viewed_exhibit_id'], ['exhibits.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('tour_session_id'),
    )
    op.create_index('ix_tour_reports_session_id', 'tour_reports', ['tour_session_id'], unique=True)

    op.add_column('exhibits', sa.Column('display_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('exhibits', 'display_order')
    op.drop_index('ix_tour_reports_session_id', table_name='tour_reports')
    op.drop_table('tour_reports')
    op.drop_index('ix_tour_events_session_type', table_name='tour_events')
    op.drop_table('tour_events')
    op.drop_index('ix_tour_sessions_status', table_name='tour_sessions')
    op.drop_index('ix_tour_sessions_session_token', table_name='tour_sessions')
    op.drop_index('ix_tour_sessions_guest_id', table_name='tour_sessions')
    op.drop_index('ix_tour_sessions_user_id', table_name='tour_sessions')
    op.drop_table('tour_sessions')
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/versions/20260415_add_tour_tables.py
git commit -m "feat(tour): add Alembic migration for tour tables"
```

---

## Chunk 3: Backend Application Services

### Task 7: TourSessionService

**Files:**
- Create: `backend/app/application/tour_session_service.py`

- [ ] **Step 1: 编写 TourSessionService**

```python
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TourSession
from app.domain.exceptions import TourSessionExpired, TourSessionNotFound, TourSessionTokenMismatch
from app.domain.value_objects import TourSessionId
from app.infra.postgres.models import TourSessionModel


SESSION_EXPIRY_HOURS = 24


async def create_session(
    session: AsyncSession,
    interest_type: str,
    persona: str,
    assumption: str,
    user_id: str | None = None,
    guest_id: str | None = None,
) -> TourSession:
    session_id = str(uuid.uuid4())
    session_token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)

    model = TourSessionModel(
        id=session_id,
        user_id=user_id,
        guest_id=guest_id,
        session_token=session_token,
        interest_type=interest_type,
        persona=persona,
        assumption=assumption,
        current_hall=None,
        current_exhibit_id=None,
        visited_halls=[],
        visited_exhibit_ids=[],
        status="onboarding",
        last_active_at=now,
        started_at=now,
        completed_at=None,
        created_at=now,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def get_session(session: AsyncSession, session_id: str) -> TourSession:
    model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    _check_expiry(model)
    return model.to_entity()


async def get_session_model(session: AsyncSession, session_id: str) -> TourSessionModel:
    model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    _check_expiry(model)
    return model


async def update_session(
    session: AsyncSession,
    session_id: str,
    **updates,
) -> TourSession:
    model = await get_session_model(session, session_id)
    allowed_fields = {"current_hall", "current_exhibit_id", "status", "visited_halls", "visited_exhibit_ids"}
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(model, key, value)
    model.last_active_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def verify_session_token(session: AsyncSession, session_id: str, token: str) -> TourSession:
    model = await session.get(TourSessionModel, session_id)
    if model is None:
        raise TourSessionNotFound(f"Tour session {session_id} not found")
    if model.session_token != token:
        raise TourSessionTokenMismatch("Session token does not match")
    _check_expiry(model)
    model.last_active_at = datetime.now(UTC)
    await session.commit()
    return model.to_entity()


async def find_active_session_by_user(session: AsyncSession, user_id: str) -> TourSession | None:
    stmt = (
        select(TourSessionModel)
        .where(TourSessionModel.user_id == user_id, TourSessionModel.status != "completed")
        .order_by(TourSessionModel.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        return None
    _check_expiry(model)
    return model.to_entity()


async def find_active_session_by_guest(session: AsyncSession, guest_id: str) -> TourSession | None:
    stmt = (
        select(TourSessionModel)
        .where(TourSessionModel.guest_id == guest_id, TourSessionModel.status != "completed")
        .order_by(TourSessionModel.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        return None
    _check_expiry(model)
    return model.to_entity()


def _check_expiry(model: TourSessionModel) -> None:
    if model.last_active_at and datetime.now(UTC) - model.last_active_at > timedelta(hours=SESSION_EXPIRY_HOURS):
        raise TourSessionExpired(f"Tour session {model.id} has expired")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/application/tour_session_service.py
git commit -m "feat(tour): add TourSessionService for session CRUD and lifecycle"
```

### Task 8: TourEventService

**Files:**
- Create: `backend/app/application/tour_event_service.py`

- [ ] **Step 1: 编写 TourEventService**

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TourEvent
from app.domain.value_objects import TourEventId
from app.infra.postgres.models import TourEventModel


async def record_events(
    session: AsyncSession,
    tour_session_id: str,
    events: list[dict],
) -> list[TourEvent]:
    now = datetime.now(UTC)
    models = []
    for event_data in events:
        model = TourEventModel(
            id=str(uuid.uuid4()),
            tour_session_id=tour_session_id,
            event_type=event_data["event_type"],
            exhibit_id=event_data.get("exhibit_id"),
            hall=event_data.get("hall"),
            duration_seconds=event_data.get("duration_seconds"),
            metadata=event_data.get("metadata"),
            created_at=now,
        )
        session.add(model)
        models.append(model)
    await session.commit()
    for m in models:
        await session.refresh(m)
    return [m.to_entity() for m in models]


async def get_events_by_session(
    session: AsyncSession,
    tour_session_id: str,
) -> list[TourEvent]:
    stmt = (
        select(TourEventModel)
        .where(TourEventModel.tour_session_id == tour_session_id)
        .order_by(TourEventModel.created_at.asc())
    )
    result = await session.execute(stmt)
    return [model.to_entity() for model in result.scalars().all()]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/application/tour_event_service.py
git commit -m "feat(tour): add TourEventService for event recording and queries"
```

### Task 9: TourReportService（含五型图、标签逻辑）

**Files:**
- Create: `backend/app/application/tour_report_service.py`

- [ ] **Step 1: 编写 TourReportService**

```python
import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.tour_event_service import get_events_by_session
from app.application.tour_session_service import get_session
from app.domain.entities import TourReport
from app.domain.exceptions import TourSessionNotFound
from app.domain.value_objects import TourReportId
from app.infra.postgres.models import TourReportModel

CERAMIC_KEYWORDS = [
    "陶", "瓷", "盆", "罐", "瓶", "碗", "鼎", "甑", "釜", "纹",
    "彩陶", "人面鱼纹", "鱼纹", "几何纹", "绳纹", "尖底瓶",
    "红陶", "灰陶", "黑陶", "泥塑", "陶塑", "陶器", "瓷器",
    "素面", "刻划", "彩绘",
]

ONE_LINER_CANDIDATES = [
    "今天，我用AI唤醒了沉睡六千年的半坡先民",
    "我的博物馆向导来自公元前4000年",
    "没有文字的时代，他们把不朽的灵魂画在彩陶上",
    "凝视人面鱼纹盆的瞬间，六千年的风从浐河吹进了现实",
    "我们在泥土里寻找的不是瓦罐，而是六千年前祖宗的倒影",
    "半坡一日游达成：确认过了，如果回到6000年前，我的手艺只配负责吃",
    "懂了，六千年前的先民不内卷，每天研究怎么抓鱼和捏泥巴",
]

HARDCORE_TAGS = ["史前细节显微镜", "碎片重构大师", "冷酷无情的地层勘探机"]
FUN_TAGS = ["六千年前的干饭王", "母系氏族社交悍匪", "沉睡的部落大祭司"]
AESTHETIC_TAGS = ["史前第一眼光", "彩陶纹饰解码者", "被文物选中的人"]


def detect_ceramic_question(message: str) -> bool:
    return any(kw in message for kw in CERAMIC_KEYWORDS)


def calculate_radar_scores(stats: dict) -> dict:
    total_minutes = stats.get("total_duration_minutes", 0)
    total_questions = stats.get("total_questions", 0)
    total_exhibits = stats.get("total_exhibits_viewed", 0)
    site_hall_minutes = stats.get("site_hall_duration_minutes", 0)
    ceramic_q = stats.get("ceramic_questions", 0)

    civilization = 3 if total_minutes > 60 else (2 if total_minutes >= 30 else 1)
    imagination = 3 if total_questions > 15 else (2 if total_questions >= 10 else 1)
    history = 3 if total_exhibits > 10 else (2 if total_exhibits >= 5 else 1)
    lifestyle = 3 if site_hall_minutes > 20 else (2 if site_hall_minutes >= 10 else 1)
    aesthetics = 3 if ceramic_q >= 3 else (2 if ceramic_q >= 1 else 1)

    return {
        "civilization_resonance": civilization,
        "imagination_breadth": imagination,
        "history_collection": history,
        "life_experience": lifestyle,
        "ceramic_aesthetics": aesthetics,
    }


def select_identity_tags(radar_scores: dict) -> list[str]:
    tags = []

    civ = radar_scores.get("civilization_resonance", 1)
    hist = radar_scores.get("history_collection", 1)
    img = radar_scores.get("imagination_breadth", 1)
    life = radar_scores.get("life_experience", 1)
    aes = radar_scores.get("ceramic_aesthetics", 1)

    if civ == 3:
        tags.append(HARDCORE_TAGS[2])
    elif hist == 3:
        tags.append(HARDCORE_TAGS[1])
    else:
        tags.append(HARDCORE_TAGS[0])

    if img == 3:
        tags.append(FUN_TAGS[1])
    elif life == 3:
        tags.append(FUN_TAGS[2])
    else:
        tags.append(FUN_TAGS[0])

    if aes == 3:
        tags.append(AESTHETIC_TAGS[1])
    elif civ == 3:
        tags.append(AESTHETIC_TAGS[2])
    else:
        tags.append(AESTHETIC_TAGS[0])

    return tags


def get_report_theme(persona: str) -> str:
    return {"A": "archaeology", "B": "village", "C": "homework"}.get(persona, "archaeology")


def aggregate_stats(events: list, tour_session) -> dict:
    total_duration = 0.0
    if tour_session.started_at and tour_session.completed_at:
        total_duration = (tour_session.completed_at - tour_session.started_at).total_seconds() / 60.0
    elif tour_session.started_at:
        total_duration = (datetime.now(UTC) - tour_session.started_at).total_seconds() / 60.0

    exhibit_durations: dict[str, int] = {}
    hall_durations: dict[str, int] = {}
    total_questions = 0
    ceramic_questions = 0
    viewed_exhibits: set[str] = set()

    for event in events:
        if event.event_type == "exhibit_view" and event.exhibit_id and event.duration_seconds:
            eid = event.exhibit_id.value if hasattr(event.exhibit_id, 'value') else str(event.exhibit_id)
            exhibit_durations[eid] = exhibit_durations.get(eid, 0) + event.duration_seconds
            viewed_exhibits.add(eid)
        elif event.event_type == "hall_leave" and event.hall and event.duration_seconds:
            hall_durations[event.hall] = hall_durations.get(event.hall, 0) + event.duration_seconds
        elif event.event_type == "exhibit_question":
            total_questions += 1
            meta = event.metadata or {}
            if meta.get("is_ceramic_question"):
                ceramic_questions += 1
        elif event.event_type == "exhibit_deep_dive":
            pass

    most_viewed_exhibit_id = None
    most_viewed_exhibit_duration = None
    if exhibit_durations:
        top_eid = max(exhibit_durations, key=exhibit_durations.get)
        most_viewed_exhibit_id = top_eid
        most_viewed_exhibit_duration = exhibit_durations[top_eid]

    longest_hall = None
    longest_hall_duration = None
    if hall_durations:
        top_hall = max(hall_durations, key=hall_durations.get)
        longest_hall = top_hall
        longest_hall_duration = hall_durations[top_hall]

    site_hall_minutes = hall_durations.get("site-hall", 0) / 60.0

    return {
        "total_duration_minutes": round(total_duration, 1),
        "most_viewed_exhibit_id": most_viewed_exhibit_id,
        "most_viewed_exhibit_duration": most_viewed_exhibit_duration,
        "longest_hall": longest_hall,
        "longest_hall_duration": longest_hall_duration,
        "total_questions": total_questions,
        "total_exhibits_viewed": len(viewed_exhibits),
        "ceramic_questions": ceramic_questions,
        "site_hall_duration_minutes": round(site_hall_minutes, 1),
    }


async def generate_report(
    session: AsyncSession,
    tour_session_id: str,
    llm_provider: Any = None,
) -> TourReport:
    existing = await session.get(TourReportModel, tour_session_id)
    if existing is None:
        stmt = select(TourReportModel).where(TourReportModel.tour_session_id == tour_session_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

    if existing is not None:
        return existing.to_entity()

    tour_session = await get_session(session, tour_session_id)
    events = await get_events_by_session(session, tour_session_id)

    stats = aggregate_stats(events, tour_session)
    radar_scores = calculate_radar_scores(stats)
    identity_tags = select_identity_tags(radar_scores)
    report_theme = get_report_theme(tour_session.persona)

    one_liner = _pick_one_liner(stats, tour_session.persona)

    if llm_provider:
        try:
            one_liner = await _generate_one_liner_llm(llm_provider, tour_session.persona, stats)
        except Exception as e:
            logger.warning(f"Failed to generate one-liner via LLM, using fallback: {e}")

    report_id = str(uuid.uuid4())
    model = TourReportModel(
        id=report_id,
        tour_session_id=tour_session_id,
        total_duration_minutes=stats["total_duration_minutes"],
        most_viewed_exhibit_id=stats["most_viewed_exhibit_id"],
        most_viewed_exhibit_duration=stats["most_viewed_exhibit_duration"],
        longest_hall=stats["longest_hall"],
        longest_hall_duration=stats["longest_hall_duration"],
        total_questions=stats["total_questions"],
        total_exhibits_viewed=stats["total_exhibits_viewed"],
        ceramic_questions=stats["ceramic_questions"],
        identity_tags=identity_tags,
        radar_scores=radar_scores,
        one_liner=one_liner,
        report_theme=report_theme,
        created_at=datetime.now(UTC),
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def get_report(session: AsyncSession, tour_session_id: str) -> TourReport | None:
    stmt = select(TourReportModel).where(TourReportModel.tour_session_id == tour_session_id)
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    return model.to_entity() if model else None


def _pick_one_liner(stats: dict, persona: str) -> str:
    import random
    return random.choice(ONE_LINER_CANDIDATES)


async def _generate_one_liner_llm(llm_provider: Any, persona: str, stats: dict) -> str:
    persona_names = {"A": "考古队长", "B": "半坡原住民", "C": "历史老师"}
    prompt = (
        f"根据以下游览数据，生成一句有感染力的'游览一句话'（15字以内），"
        f"风格要符合{persona_names.get(persona, '考古队长')}的身份：\n"
        f"- 游览时长：{stats.get('total_duration_minutes', 0):.0f}分钟\n"
        f"- 提问次数：{stats.get('total_questions', 0)}\n"
        f"- 参观展品数：{stats.get('total_exhibits_viewed', 0)}\n"
        f"只输出一句话，不要其他内容。"
    )
    result = await llm_provider.generate(prompt)
    return result.strip()[:50] if result else _pick_one_liner(stats, persona)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/application/tour_report_service.py
git commit -m "feat(tour): add TourReportService with radar scores, identity tags, one-liner"
```

### Task 10: TourReportService 单元测试

**Files:**
- Create: `backend/tests/unit/test_tour_report_service.py`

- [ ] **Step 1: 编写五型图和标签计算测试**

```python
from app.application.tour_report_service import (
    calculate_radar_scores,
    detect_ceramic_question,
    select_identity_tags,
    get_report_theme,
)


def test_detect_ceramic_question_true():
    assert detect_ceramic_question("这个人面鱼纹盆是做什么的？") is True
    assert detect_ceramic_question("彩陶是怎么烧制的") is True
    assert detect_ceramic_question("尖底瓶的用途") is True


def test_detect_ceramic_question_false():
    assert detect_ceramic_question("半坡人的房屋是怎么建的？") is False
    assert detect_ceramic_question("谁是首领？") is False


def test_radar_scores_all_B():
    stats = {
        "total_duration_minutes": 10,
        "total_questions": 3,
        "total_exhibits_viewed": 2,
        "site_hall_duration_minutes": 5,
        "ceramic_questions": 0,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 1
    assert scores["imagination_breadth"] == 1
    assert scores["history_collection"] == 1
    assert scores["life_experience"] == 1
    assert scores["ceramic_aesthetics"] == 1


def test_radar_scores_all_A():
    stats = {
        "total_duration_minutes": 45,
        "total_questions": 12,
        "total_exhibits_viewed": 7,
        "site_hall_duration_minutes": 15,
        "ceramic_questions": 1,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 2
    assert scores["imagination_breadth"] == 2
    assert scores["history_collection"] == 2
    assert scores["life_experience"] == 2
    assert scores["ceramic_aesthetics"] == 2


def test_radar_scores_all_S():
    stats = {
        "total_duration_minutes": 90,
        "total_questions": 20,
        "total_exhibits_viewed": 15,
        "site_hall_duration_minutes": 30,
        "ceramic_questions": 5,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 3
    assert scores["imagination_breadth"] == 3
    assert scores["history_collection"] == 3
    assert scores["life_experience"] == 3
    assert scores["ceramic_aesthetics"] == 3


def test_select_identity_tags_default():
    scores = {
        "civilization_resonance": 1,
        "imagination_breadth": 1,
        "life_experience": 1,
        "ceramic_aesthetics": 1,
    }
    tags = select_identity_tags(scores)
    assert tags == ["史前细节显微镜", "六千年前的干饭王", "史前第一眼光"]


def test_select_identity_tags_all_S():
    scores = {
        "civilization_resonance": 3,
        "imagination_breadth": 3,
        "life_experience": 3,
        "ceramic_aesthetics": 3,
    }
    tags = select_identity_tags(scores)
    assert tags[0] == "冷酷无情的地层勘探机"
    assert tags[1] == "母系氏族社交悍匪"
    assert tags[2] == "彩陶纹饰解码者"


def test_get_report_theme():
    assert get_report_theme("A") == "archaeology"
    assert get_report_theme("B") == "village"
    assert get_report_theme("C") == "homework"
```

- [ ] **Step 2: 运行测试验证通过**

Run: `uv run pytest backend/tests/unit/test_tour_report_service.py -v`
Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_tour_report_service.py
git commit -m "test(tour): add TourReportService unit tests for radar scores and tags"
```

### Task 11: TourChatService

**Files:**
- Create: `backend/app/application/tour_chat_service.py`

- [ ] **Step 1: 编写 TourChatService**

```python
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.tour_event_service import record_events
from app.application.tour_report_service import detect_ceramic_question
from app.application.tour_session_service import get_session, get_session_model, update_session
from app.domain.entities import TourSession


PERSONA_PROMPTS = {
    "A": (
        "你是一位严谨求实的考古队长，正在带领游客勘探西安半坡博物馆。"
        "你的叙事风格：引用硬核发掘数据和学术推论，用'我们''数据表明''地层学证据'等措辞。"
        "避免主观臆测，对不确定的内容标注'学术界尚有争议'。"
        "在推荐下一个展品时，强调工艺承接关系和地层演化顺序。"
    ),
    "B": (
        "你是一位穿越来的半坡村原住民，正在带远道而来的朋友参观你曾经生活的村落。"
        "你的叙事风格：以村民视角第一人称叙述，增强沉浸感，用'我''阿妈''我们部落''当年'等措辞。"
        "把展柜里的文物描述成你曾经使用或见过的日常用品。"
        "在推荐下一个展品时，用生活化的语言描述它的用途和故事。"
    ),
    "C": (
        "你是一位爱提问的历史老师，正在带领学生进行半坡博物馆的沉浸式游学。"
        "你的叙事风格：多提供不同观点并引导思考，用'同学们''想一想''你觉得呢'等措辞。"
        "每个知识点后抛出启发性问题。"
        "在推荐下一个展品时，设置悬念和对比思考任务。"
    ),
}

ASSUMPTION_CONTEXTS = {
    "A": "游客初始假设：原始社会是没有压迫、人人平等的纯真年代。当讨论到社会结构相关内容时，引导反思这一假设。",
    "B": "游客初始假设：原始社会是饥寒交迫的荒野求生。当讨论到生存方式相关内容时，引导反思这一假设。",
    "C": "游客初始假设：原始社会已经出现贫富分化和阶级的雏形。当讨论到社会结构相关内容时，引导反思这一假设。",
}

HALL_DESCRIPTIONS = {
    "relic-hall": "出土文物展厅：陈列半坡遗址出土的陶器、石器、骨器等文物，展示6000年前半坡人的生存技术和精神世界。",
    "site-hall": "遗址保护大厅：保留半坡遗址的居住区、制陶区和墓葬区原貌，展示圆形和方形半地穴式房屋结构。",
}


def build_system_prompt(
    persona: str,
    assumption: str,
    hall: str | None = None,
    exhibit_context: str | None = None,
    visited_exhibits: list[str] | None = None,
) -> str:
    parts = [PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["A"])]
    parts.append(ASSUMPTION_CONTEXTS.get(assumption, ASSUMPTION_CONTEXTS["A"]))

    if hall and hall in HALL_DESCRIPTIONS:
        parts.append(f"当前展厅：{HALL_DESCRIPTIONS[hall]}")

    if exhibit_context:
        parts.append(f"当前展品信息：{exhibit_context}")

    if visited_exhibits:
        parts.append(f"游客已参观的展品：{', '.join(visited_exhibits)}（避免重复介绍这些展品）")

    return "\n\n".join(parts)


async def ask_stream_tour(
    db_session: AsyncSession,
    session_maker: async_sessionmaker,
    tour_session_id: str,
    message: str,
    rag_agent: Any,
    exhibit_id: str | None = None,
    exhibit_context: str | None = None,
) -> AsyncGenerator[str, None]:
    tour_session = await get_session(db_session, tour_session_id)

    visited_ids = tour_session.visited_exhibit_ids or []
    system_prompt = build_system_prompt(
        persona=tour_session.persona,
        assumption=tour_session.assumption,
        hall=tour_session.current_hall,
        exhibit_context=exhibit_context,
        visited_exhibits=visited_ids,
    )

    trace_id = str(uuid.uuid4())
    is_ceramic = detect_ceramic_question(message)

    try:
        async for event in _stream_rag(rag_agent, message, system_prompt):
            yield event
    except Exception as e:
        logger.error(f"Tour chat RAG error: {e}")
        error_data = json.dumps({"event": "error", "data": {"code": "llm_error", "message": "AI导览暂时不可用，请稍后再试"}})
        yield f"data: {error_data}\n\n"

    done_data = {
        "event": "done",
        "trace_id": trace_id,
        "is_ceramic_question": is_ceramic,
    }
    yield f"data: {json.dumps(done_data)}\n\n"

    try:
        async with session_maker() as event_session:
            await record_events(event_session, tour_session_id, [
                {
                    "event_type": "exhibit_question",
                    "exhibit_id": exhibit_id,
                    "hall": tour_session.current_hall,
                    "metadata": {"question": message, "is_ceramic_question": is_ceramic},
                }
            ])
    except Exception as e:
        logger.warning(f"Failed to record tour event: {e}")


async def _stream_rag(rag_agent: Any, message: str, system_prompt: str) -> AsyncGenerator[str, None]:
    result = await rag_agent.run(message, system_prompt=system_prompt)
    answer = result.get("answer", "")

    chunk_data = json.dumps({"event": "chunk", "data": {"content": answer}})
    yield f"data: {chunk_data}\n\n"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/application/tour_chat_service.py
git commit -m "feat(tour): add TourChatService with persona prompts and SSE streaming"
```

---

## Chunk 4: Backend API Layer

### Task 12: 导览 API 路由

**Files:**
- Create: `backend/app/api/tour.py`

- [ ] **Step 1: 编写导览 API 路由**

```python
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal

from app.api.deps import (
    LLMProviderDep,
    OptionalUser,
    RagAgentDep,
    RedisCacheDep,
    SessionDep,
    SessionMakerDep,
)
from app.application.tour_chat_service import ask_stream_tour
from app.application.tour_event_service import get_events_by_session, record_events
from app.application.tour_report_service import generate_report, get_report
from app.application.tour_session_service import (
    create_session,
    find_active_session_by_guest,
    find_active_session_by_user,
    get_session,
    update_session,
    verify_session_token,
)
from app.domain.exceptions import TourSessionExpired, TourSessionNotFound, TourSessionTokenMismatch

router = APIRouter(prefix="/tour", tags=["tour"])

SSE_HEARTBEAT_INTERVAL = 15


class TourSessionCreate(BaseModel):
    interest_type: Literal["A", "B", "C"]
    persona: Literal["A", "B", "C"]
    assumption: Literal["A", "B", "C"]
    guest_id: str | None = None


class TourSessionUpdate(BaseModel):
    current_hall: str | None = None
    current_exhibit_id: str | None = None
    status: Literal["onboarding", "opening", "touring", "completed"] | None = None


class TourEventItem(BaseModel):
    event_type: Literal["exhibit_view", "exhibit_question", "exhibit_deep_dive", "hall_enter", "hall_leave"]
    exhibit_id: str | None = None
    hall: str | None = None
    duration_seconds: int | None = None
    metadata: dict | None = None


class TourEventBatch(BaseModel):
    events: list[TourEventItem] = Field(..., max_length=50)


class TourChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    exhibit_id: str | None = None


class TourHallItem(BaseModel):
    slug: str
    name: str
    description: str
    exhibit_count: int
    estimated_duration_minutes: int


class TourHallListResponse(BaseModel):
    halls: list[TourHallItem]


HALLS_DATA = [
    TourHallItem(
        slug="relic-hall",
        name="出土文物展厅",
        description="陈列半坡遗址出土的陶器、石器、骨器等文物，展示6000年前半坡人的生存技术和精神世界。",
        exhibit_count=0,
        estimated_duration_minutes=30,
    ),
    TourHallItem(
        slug="site-hall",
        name="遗址保护大厅",
        description="保留半坡遗址的居住区、制陶区和墓葬区原貌，展示圆形和方形半地穴式房屋结构。",
        exhibit_count=0,
        estimated_duration_minutes=25,
    ),
]


async def _verify_ownership(session_id: str, user: dict | None, token: str | None, db_session) -> None:
    if user:
        tour_session = await get_session(db_session, session_id)
        if tour_session.user_id and str(tour_session.user_id.value if hasattr(tour_session.user_id, 'value') else tour_session.user_id) != user["id"]:
            raise HTTPException(status_code=403, detail="Not your tour session")
    elif token:
        try:
            await verify_session_token(db_session, session_id, token)
        except TourSessionTokenMismatch:
            raise HTTPException(status_code=403, detail="Invalid session token")
    else:
        raise HTTPException(status_code=403, detail="Authentication required")


@router.post("/sessions")
async def create_tour_session(
    body: TourSessionCreate,
    session: SessionDep,
    user: OptionalUser = None,
):
    user_id = user["id"] if user else None
    guest_id = body.guest_id if not user else None

    if user:
        existing = await find_active_session_by_user(session, user_id)
        if existing:
            return {
                "id": existing.id.value if hasattr(existing.id, 'value') else existing.id,
                "session_token": existing.session_token,
                "interest_type": existing.interest_type,
                "persona": existing.persona,
                "assumption": existing.assumption,
                "status": existing.status,
                "current_hall": existing.current_hall,
                "current_exhibit_id": str(existing.current_exhibit_id.value) if existing.current_exhibit_id and hasattr(existing.current_exhibit_id, 'value') else existing.current_exhibit_id,
                "visited_halls": existing.visited_halls,
                "visited_exhibit_ids": existing.visited_exhibit_ids,
                "started_at": existing.started_at.isoformat(),
            }

    tour_session = await create_session(
        session,
        interest_type=body.interest_type,
        persona=body.persona,
        assumption=body.assumption,
        user_id=user_id,
        guest_id=guest_id,
    )
    return {
        "id": tour_session.id.value if hasattr(tour_session.id, 'value') else tour_session.id,
        "session_token": tour_session.session_token,
        "interest_type": tour_session.interest_type,
        "persona": tour_session.persona,
        "assumption": tour_session.assumption,
        "status": tour_session.status,
        "current_hall": tour_session.current_hall,
        "current_exhibit_id": str(tour_session.current_exhibit_id.value) if tour_session.current_exhibit_id and hasattr(tour_session.current_exhibit_id, 'value') else tour_session.current_exhibit_id,
        "visited_halls": tour_session.visited_halls,
        "visited_exhibit_ids": tour_session.visited_exhibit_ids,
        "started_at": tour_session.started_at.isoformat(),
    }


@router.get("/sessions/{session_id}")
async def get_tour_session(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired")

    return {
        "id": tour_session.id.value if hasattr(tour_session.id, 'value') else tour_session.id,
        "interest_type": tour_session.interest_type,
        "persona": tour_session.persona,
        "assumption": tour_session.assumption,
        "status": tour_session.status,
        "current_hall": tour_session.current_hall,
        "current_exhibit_id": str(tour_session.current_exhibit_id.value) if tour_session.current_exhibit_id and hasattr(tour_session.current_exhibit_id, 'value') else tour_session.current_exhibit_id,
        "visited_halls": tour_session.visited_halls,
        "visited_exhibit_ids": tour_session.visited_exhibit_ids,
        "started_at": tour_session.started_at.isoformat(),
    }


@router.patch("/sessions/{session_id}")
async def patch_tour_session(
    session_id: str,
    body: TourSessionUpdate,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        tour_session = await update_session(session, session_id, **updates)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired")

    return {
        "id": tour_session.id.value if hasattr(tour_session.id, 'value') else tour_session.id,
        "status": tour_session.status,
        "current_hall": tour_session.current_hall,
        "current_exhibit_id": str(tour_session.current_exhibit_id.value) if tour_session.current_exhibit_id and hasattr(tour_session.current_exhibit_id, 'value') else tour_session.current_exhibit_id,
        "visited_halls": tour_session.visited_halls,
        "visited_exhibit_ids": tour_session.visited_exhibit_ids,
    }


@router.post("/sessions/{session_id}/events")
async def post_tour_events(
    session_id: str,
    body: TourEventBatch,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        events = await record_events(session, session_id, [e.model_dump() for e in body.events])
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")
    return {"recorded": len(events)}


@router.get("/sessions/{session_id}/events")
async def list_tour_events(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        events = await get_events_by_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")
    return {
        "events": [
            {
                "id": e.id.value if hasattr(e.id, 'value') else e.id,
                "event_type": e.event_type,
                "exhibit_id": str(e.exhibit_id.value) if e.exhibit_id and hasattr(e.exhibit_id, 'value') else e.exhibit_id,
                "hall": e.hall,
                "duration_seconds": e.duration_seconds,
                "metadata": e.metadata,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }


@router.post("/sessions/{session_id}/complete-hall")
async def complete_hall(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")

    visited_halls = list(tour_session.visited_halls or [])
    if tour_session.current_hall and tour_session.current_hall not in visited_halls:
        visited_halls.append(tour_session.current_hall)

    all_halls = [h.slug for h in HALLS_DATA]
    all_visited = all(h in visited_halls for h in all_halls)

    new_status = "completed" if all_visited else "touring"
    updated = await update_session(session, session_id, visited_halls=visited_halls, status=new_status)

    return {
        "visited_halls": updated.visited_halls,
        "all_halls_visited": all_visited,
        "status": updated.status,
    }


@router.post("/sessions/{session_id}/report")
async def create_tour_report(
    session_id: str,
    session: SessionDep,
    llm_provider: LLMProviderDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)

    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")

    if tour_session.status != "completed":
        await update_session(session, session_id, status="completed")

    try:
        report = await generate_report(session, session_id, llm_provider=llm_provider)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found")

    return _format_report(report)


@router.get("/sessions/{session_id}/report")
async def get_tour_report(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    report = await get_report(session, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _format_report(report)


@router.post("/sessions/{session_id}/chat/stream")
async def tour_chat_stream(
    session_id: str,
    body: TourChatRequest,
    request: Request,
    session: SessionDep,
    session_maker: SessionMakerDep,
    rag_agent: RagAgentDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)

    return StreamingResponse(
        ask_stream_tour(
            db_session=session,
            session_maker=session_maker,
            tour_session_id=session_id,
            message=body.message,
            rag_agent=rag_agent,
            exhibit_id=body.exhibit_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/halls")
async def list_tour_halls(
    session: SessionDep,
):
    from sqlalchemy import select, func
    from app.infra.postgres.models import Exhibit

    hall_slugs = [h.slug for h in HALLS_DATA]
    stmt = (
        select(Exhibit.hall, func.count(Exhibit.id))
        .where(Exhibit.hall.in_(hall_slugs), Exhibit.is_active == True)
        .group_by(Exhibit.hall)
    )
    result = await session.execute(stmt)
    counts = dict(result.all())

    halls = []
    for h in HALLS_DATA:
        halls.append(TourHallItem(
            slug=h.slug,
            name=h.name,
            description=h.description,
            exhibit_count=counts.get(h.slug, 0),
            estimated_duration_minutes=h.estimated_duration_minutes,
        ))
    return TourHallListResponse(halls=halls)


def _format_report(report) -> dict:
    return {
        "id": report.id.value if hasattr(report.id, 'value') else report.id,
        "tour_session_id": report.tour_session_id.value if hasattr(report.tour_session_id, 'value') else report.tour_session_id,
        "total_duration_minutes": report.total_duration_minutes,
        "most_viewed_exhibit_id": str(report.most_viewed_exhibit_id.value) if report.most_viewed_exhibit_id and hasattr(report.most_viewed_exhibit_id, 'value') else report.most_viewed_exhibit_id,
        "most_viewed_exhibit_duration": report.most_viewed_exhibit_duration,
        "longest_hall": report.longest_hall,
        "longest_hall_duration": report.longest_hall_duration,
        "total_questions": report.total_questions,
        "total_exhibits_viewed": report.total_exhibits_viewed,
        "ceramic_questions": report.ceramic_questions,
        "identity_tags": report.identity_tags,
        "radar_scores": report.radar_scores,
        "one_liner": report.one_liner,
        "report_theme": report.report_theme,
        "created_at": report.created_at.isoformat(),
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/tour.py
git commit -m "feat(tour): add tour API router with 10 endpoints"
```

### Task 13: 注册路由到 main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 添加 tour router import 和注册**

在 import 区添加：
```python
from app.api.tour import router as tour_router
```

在路由注册区添加：
```python
app.include_router(tour_router, prefix="/api/v1")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(tour): register tour router in main.py"
```

### Task 14: 运行 lint 和类型检查

- [ ] **Step 1: 运行 ruff 检查**

Run: `uv run ruff check backend/app/domain/ backend/app/application/tour_*.py backend/app/api/tour.py backend/tests/unit/test_tour_*.py`
Expected: 无错误（或修复后无错误）

- [ ] **Step 2: 运行 mypy 检查**

Run: `uv run mypy backend/app/domain/ backend/app/application/tour_*.py backend/app/api/tour.py --ignore-missing-imports`
Expected: 无错误（或修复后无错误）

- [ ] **Step 3: 运行全部单元测试**

Run: `uv run pytest backend/tests/unit/test_tour_entities.py backend/tests/unit/test_tour_report_service.py -v`
Expected: All passed

---

## Chunk 5: Frontend API & Composable

### Task 15: 前端 API 层 - tour 命名空间

**Files:**
- Modify: `frontend/src/api/index.js`

- [ ] **Step 1: 在 api 对象中添加 tour 命名空间**

在 `profile` 命名空间之后添加：

```javascript
  tour: {
    createSession: (data) => request('/tour/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    getSession: (id, token) => request(`/tour/sessions/${id}`, {
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    updateSession: (id, data, token) => request(`/tour/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    recordEvents: (id, events, token) => request(`/tour/sessions/${id}/events`, {
      method: 'POST',
      body: JSON.stringify({ events }),
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    getEvents: (id, token) => request(`/tour/sessions/${id}/events`, {
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    completeHall: (id, token) => request(`/tour/sessions/${id}/complete-hall`, {
      method: 'POST',
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    generateReport: (id, token) => request(`/tour/sessions/${id}/report`, {
      method: 'POST',
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    getReport: (id, token) => request(`/tour/sessions/${id}/report`, {
      headers: token ? { 'X-Session-Token': token } : {},
    }),
    chatStream: async function* (id, message, token, exhibitId = null) {
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['X-Session-Token'] = token
      const body = { message }
      if (exhibitId) body.exhibit_id = exhibitId

      const response = await fetch(`${BASE_URL}/tour/sessions/${id}/chat/stream`, {
        method: 'POST',
        credentials: 'include',
        headers,
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') return
            try {
              yield JSON.parse(data)
            } catch {
              warn('Parse error:', data)
            }
          }
        }
      }
    },
    getHalls: () => request('/tour/halls'),
  },
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/index.js
git commit -m "feat(tour): add tour API namespace with all endpoints"
```

### Task 16: useTour.js Composable

**Files:**
- Create: `frontend/src/composables/useTour.js`

- [ ] **Step 1: 编写 useTour composable**

```javascript
import { ref, computed } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'
import { log, error as logError } from '../utils/logger.js'

const tourSession = ref(null)
const sessionToken = ref(null)
const tourStep = ref('onboarding')
const currentHall = ref(null)
const currentExhibit = ref(null)
const hallExhibits = ref([])
const exhibitIndex = ref(0)
const streamingContent = ref('')
const suggestedActions = ref(null)
const chatMessages = ref([])
const loading = ref({ session: false, chat: false, report: false })
const error = ref(null)
const tourReport = ref(null)
const halls = ref([])

let eventBuffer = []
let eventFlushTimer = null
let exhibitStartTime = null

const EVENT_FLUSH_INTERVAL = 30000

const STORAGE_KEY_SESSION = 'tour_session_id'
const STORAGE_KEY_TOKEN = 'tour_session_token'
const STORAGE_KEY_EVENTS = 'tour_pending_events'

function _getToken() {
  return sessionToken.value || null
}

function _persistSession() {
  if (tourSession.value) {
    localStorage.setItem(STORAGE_KEY_SESSION, tourSession.value.id)
    localStorage.setItem(STORAGE_KEY_TOKEN, sessionToken.value || '')
  }
}

function _persistEvents() {
  localStorage.setItem(STORAGE_KEY_EVENTS, JSON.stringify(eventBuffer))
}

function _loadPersistedEvents() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_EVENTS)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

export function useTour() {
  const { isAuthenticated, user } = useAuth()

  async function createTourSession(interestType, persona, assumption) {
    loading.value.session = true
    error.value = null
    const guestId = isAuthenticated.value ? null : `guest-${crypto.randomUUID()}`
    const result = await api.tour.createSession({
      interest_type: interestType,
      persona,
      assumption,
      guest_id: guestId,
    })
    loading.value.session = false

    if (!result.ok) {
      error.value = result.data?.detail || '创建导览会话失败'
      return null
    }

    tourSession.value = result.data
    sessionToken.value = result.data.session_token
    _persistSession()
    return result.data
  }

  async function restoreSession() {
    const storedId = localStorage.getItem(STORAGE_KEY_SESSION)
    const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN)
    if (!storedId) return false

    const result = await api.tour.getSession(storedId, storedToken)
    if (!result.ok) {
      localStorage.removeItem(STORAGE_KEY_SESSION)
      localStorage.removeItem(STORAGE_KEY_TOKEN)
      return false
    }

    tourSession.value = result.data
    sessionToken.value = storedToken

    if (result.data.status === 'completed') {
      tourStep.value = 'report'
    } else if (result.data.status === 'touring') {
      tourStep.value = 'tour'
      currentHall.value = result.data.current_hall
    } else if (result.data.status === 'opening') {
      tourStep.value = 'opening'
    }
    return true
  }

  async function fetchHalls() {
    const result = await api.tour.getHalls()
    if (result.ok) {
      halls.value = result.data.halls || []
    }
    return halls.value
  }

  async function selectHall(hallSlug) {
    currentHall.value = hallSlug
    const token = _getToken()
    await api.tour.updateSession(tourSession.value.id, {
      current_hall: hallSlug,
      status: 'touring',
    }, token)
    _persistSession()
  }

  async function enterExhibit(exhibit) {
    if (currentExhibit.value && exhibitStartTime) {
      const duration = Math.floor((Date.now() - exhibitStartTime) / 1000)
      bufferEvent('exhibit_view', {
        exhibit_id: currentExhibit.value.id,
        duration_seconds: duration,
      })
    }
    currentExhibit.value = exhibit
    exhibitStartTime = Date.now()
    chatMessages.value = []
    streamingContent.value = ''
    suggestedActions.value = null

    const token = _getToken()
    await api.tour.updateSession(tourSession.value.id, {
      current_exhibit_id: exhibit.id,
    }, token)
  }

  async function sendTourMessage(message) {
    if (!tourSession.value) return
    loading.value.chat = true
    chatMessages.value.push({ role: 'user', content: message })
    streamingContent.value = ''
    suggestedActions.value = null

    const token = _getToken()
    try {
      for await (const event of api.tour.chatStream(
        tourSession.value.id,
        message,
        token,
        currentExhibit.value?.id,
      )) {
        if (event.event === 'chunk' && event.data?.content) {
          streamingContent.value += event.data.content
        } else if (event.event === 'done') {
          chatMessages.value.push({ role: 'assistant', content: streamingContent.value })
          streamingContent.value = ''
          if (event.is_ceramic_question !== undefined || event.suggested_actions) {
            suggestedActions.value = event.suggested_actions || {}
            suggestedActions.value.is_ceramic_question = event.is_ceramic_question || false
          }
        } else if (event.event === 'error') {
          error.value = event.data?.message || 'AI导览暂时不可用'
        }
      }
    } catch (e) {
      logError('Tour chat stream error:', e)
      error.value = '连接中断，请重试'
    }
    loading.value.chat = false
  }

  function bufferEvent(eventType, metadata = {}) {
    eventBuffer.push({
      event_type: eventType,
      exhibit_id: currentExhibit.value?.id || metadata.exhibit_id,
      hall: currentHall.value,
      duration_seconds: metadata.duration_seconds,
      metadata,
    })
    _persistEvents()
    if (!eventFlushTimer) {
      eventFlushTimer = setInterval(flushEvents, EVENT_FLUSH_INTERVAL)
    }
  }

  async function flushEvents() {
    if (eventBuffer.length === 0 || !tourSession.value) return
    const events = [...eventBuffer]
    eventBuffer = []
    _persistEvents()

    const token = _getToken()
    const result = await api.tour.recordEvents(tourSession.value.id, events, token)
    if (!result.ok) {
      eventBuffer = [...events, ...eventBuffer]
      _persistEvents()
    }
  }

  async function completeHall() {
    if (!tourSession.value) return
    await flushEvents()

    const token = _getToken()
    const result = await api.tour.completeHall(tourSession.value.id, token)
    if (result.ok) {
      if (result.data.all_halls_visited) {
        tourStep.value = 'report'
      } else {
        tourStep.value = 'hall-select'
        currentHall.value = null
        currentExhibit.value = null
      }
    }
    return result
  }

  async function generateReport() {
    if (!tourSession.value) return
    loading.value.report = true
    const token = _getToken()
    const result = await api.tour.generateReport(tourSession.value.id, token)
    loading.value.report = false
    if (result.ok) {
      tourReport.value = result.data
    } else {
      error.value = result.data?.detail || '报告生成失败'
    }
    return result
  }

  function resetTour() {
    tourSession.value = null
    sessionToken.value = null
    tourStep.value = 'onboarding'
    currentHall.value = null
    currentExhibit.value = null
    hallExhibits.value = []
    exhibitIndex.value = 0
    streamingContent.value = ''
    suggestedActions.value = null
    chatMessages.value = []
    tourReport.value = null
    error.value = null
    eventBuffer = []
    exhibitStartTime = null
    localStorage.removeItem(STORAGE_KEY_SESSION)
    localStorage.removeItem(STORAGE_KEY_TOKEN)
    localStorage.removeItem(STORAGE_KEY_EVENTS)
    if (eventFlushTimer) {
      clearInterval(eventFlushTimer)
      eventFlushTimer = null
    }
  }

  function setupBeforeUnload() {
    window.addEventListener('beforeunload', () => {
      if (eventBuffer.length > 0 && tourSession.value) {
        const token = _getToken()
        navigator.sendBeacon(
          `/api/v1/tour/sessions/${tourSession.value.id}/events`,
          JSON.stringify({ events: eventBuffer }),
        )
      }
    })
  }

  const personaLabel = computed(() => {
    const map = { A: '考古队长', B: '半坡原住民', C: '历史老师' }
    return map[tourSession.value?.persona] || ''
  })

  const reportThemeTitle = computed(() => {
    const map = { A: '你的半坡考古报告', B: '半坡一日穿越体验', C: '半坡游学荣誉证书' }
    return map[tourSession.value?.persona] || ''
  })

  return {
    tourSession,
    sessionToken,
    tourStep,
    currentHall,
    currentExhibit,
    hallExhibits,
    exhibitIndex,
    streamingContent,
    suggestedActions,
    chatMessages,
    loading,
    error,
    tourReport,
    halls,
    personaLabel,
    reportThemeTitle,
    createTourSession,
    restoreSession,
    fetchHalls,
    selectHall,
    enterExhibit,
    sendTourMessage,
    bufferEvent,
    flushEvents,
    completeHall,
    generateReport,
    resetTour,
    setupBeforeUnload,
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/composables/useTour.js
git commit -m "feat(tour): add useTour composable with full state management"
```

### Task 17: 新增 /tour 路由

**Files:**
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 在路由配置中添加 /tour 路由**

在现有路由列表中添加：

```javascript
  {
    path: '/tour',
    name: 'tour',
    component: () => import('../views/TourView.vue'),
    meta: { requiresAuth: false }
  },
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/router/index.js
git commit -m "feat(tour): add /tour route"
```

---

## Chunk 6: Frontend Components - Onboarding & Hall Selection

### Task 18: TourView 主容器

**Files:**
- Create: `frontend/src/views/TourView.vue`

- [ ] **Step 1: 编写 TourView.vue**

全屏沉浸式布局，根据 tourStep 渲染子组件，隐藏 Header/Sidebar。

```vue
<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useTour } from '../composables/useTour.js'
import OnboardingQuiz from '../components/tour/OnboardingQuiz.vue'
import OpeningNarrative from '../components/tour/OpeningNarrative.vue'
import HallSelect from '../components/tour/HallSelect.vue'
import ExhibitTour from '../components/tour/ExhibitTour.vue'
import TourReport from '../components/tour/TourReport.vue'

const {
  tourStep,
  tourSession,
  resetTour,
  restoreSession,
  setupBeforeUnload,
} = useTour()

onMounted(async () => {
  document.body.classList.add('tour-mode')
  setupBeforeUnload()
  const restored = await restoreSession()
  if (!restored) {
    tourStep.value = 'onboarding'
  }
})

onUnmounted(() => {
  document.body.classList.remove('tour-mode')
})
</script>

<template>
  <div class="tour-container">
    <div v-if="tourStep !== 'onboarding' && tourStep !== 'report'" class="tour-header">
      <div class="tour-header-left">
        <span class="tour-logo">🏛️ 半坡AI导览</span>
      </div>
      <div class="tour-header-right">
        <el-button text @click="resetTour">退出导览</el-button>
      </div>
    </div>

    <div class="tour-content">
      <OnboardingQuiz v-if="tourStep === 'onboarding'" />
      <OpeningNarrative v-else-if="tourStep === 'opening'" />
      <HallSelect v-else-if="tourStep === 'hall-select'" />
      <ExhibitTour v-else-if="tourStep === 'tour'" />
      <TourReport v-else-if="tourStep === 'report'" />
    </div>
  </div>
</template>

<style scoped>
.tour-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  color: #e0e0e0;
  overflow: hidden;
}

.tour-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tour-logo {
  font-size: 18px;
  font-weight: 600;
}

.tour-content {
  flex: 1;
  overflow-y: auto;
}
</style>

<style>
body.tour-mode .app-header,
body.tour-mode .app-sidebar {
  display: none !important;
}
body.tour-mode .app-main {
  margin: 0 !important;
  padding: 0 !important;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/TourView.vue
git commit -m "feat(tour): add TourView main container with step-based rendering"
```

### Task 19: OnboardingQuiz 引导问卷

**Files:**
- Create: `frontend/src/components/tour/OnboardingQuiz.vue`

- [ ] **Step 1: 编写 OnboardingQuiz.vue**

3 道选择题逐题展示，半坡主题视觉设计。

```vue
<script setup>
import { ref } from 'vue'
import { useTour } from '../../composables/useTour.js'

const { createTourSession, tourStep } = useTour()

const currentQuestion = ref(0)
const answers = ref({ interest_type: null, persona: null, assumption: null })
const loading = ref(false)

const questions = [
  {
    key: 'interest_type',
    title: '如果你穿越回了6000年前的半坡，你第一件想搞清楚的事是？',
    options: [
      { value: 'A', label: '半坡人平时吃什么？房屋如何构建？', desc: '生存与技术' },
      { value: 'B', label: '陶器上那些诡异的人面鱼纹到底象征着什么？', desc: '符号与艺术' },
      { value: 'C', label: '谁是首领？打来的猎物怎么分？', desc: '社会与权力' },
    ],
  },
  {
    key: 'persona',
    title: '接下来的半个小时，你希望陪你逛展的AI导览员是什么人设？',
    options: [
      { value: 'A', label: '严谨求实的考古队长', desc: '硬核发掘数据与学术推论' },
      { value: 'B', label: '穿越来的半坡原住民', desc: '村民视角的第一人称沉浸' },
      { value: 'C', label: '爱提问的历史老师', desc: '多观点引导思考' },
    ],
  },
  {
    key: 'assumption',
    title: '凭直觉，你认为6000年前的原始社会更接近哪种状态？',
    options: [
      { value: 'A', label: '没有压迫，人人平等的纯真年代', desc: '' },
      { value: 'B', label: '饥寒交迫的荒野求生', desc: '' },
      { value: 'C', label: '已经出现贫富分化和阶级的雏形', desc: '' },
    ],
  },
]

async function selectOption(value) {
  const q = questions[currentQuestion.value]
  answers.value[q.key] = value

  if (currentQuestion.value < questions.length - 1) {
    currentQuestion.value++
  } else {
    loading.value = true
    const session = await createTourSession(
      answers.value.interest_type,
      answers.value.persona,
      answers.value.assumption,
    )
    loading.value = false
    if (session) {
      tourStep.value = 'opening'
    }
  }
}
</script>

<template>
  <div class="onboarding">
    <div class="onboarding-inner">
      <div class="progress">
        <span v-for="i in 3" :key="i" class="dot" :class="{ active: i <= currentQuestion + 1, done: i < currentQuestion + 1 }" />
      </div>

      <transition name="fade" mode="out-in">
        <div :key="currentQuestion" class="question-card">
          <h2 class="question-title">{{ questions[currentQuestion].title }}</h2>
          <div class="options">
            <div
              v-for="opt in questions[currentQuestion].options"
              :key="opt.value"
              class="option-card"
              @click="selectOption(opt.value)"
            >
              <span class="option-letter">{{ opt.value }}</span>
              <div class="option-content">
                <span class="option-label">{{ opt.label }}</span>
                <span v-if="opt.desc" class="option-desc">{{ opt.desc }}</span>
              </div>
            </div>
          </div>
        </div>
      </transition>

      <div v-if="loading" class="loading-overlay">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>正在为你准备专属导览...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.onboarding {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.onboarding-inner {
  max-width: 640px;
  width: 100%;
}

.progress {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 40px;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  transition: all 0.3s;
}

.dot.active {
  background: #d4a574;
}

.dot.done {
  background: #8fbc8f;
}

.question-card {
  text-align: center;
}

.question-title {
  font-size: 22px;
  line-height: 1.6;
  margin-bottom: 32px;
  color: #f0e6d3;
}

.options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.option-card:hover {
  background: rgba(212, 165, 116, 0.15);
  border-color: #d4a574;
  transform: translateX(4px);
}

.option-letter {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(212, 165, 116, 0.2);
  color: #d4a574;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
}

.option-content {
  display: flex;
  flex-direction: column;
  text-align: left;
}

.option-label {
  font-size: 16px;
  line-height: 1.5;
}

.option-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(26, 26, 46, 0.9);
  z-index: 100;
  color: #d4a574;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/tour/OnboardingQuiz.vue
git commit -m "feat(tour): add OnboardingQuiz component with 3-step questions"
```

### Task 20: OpeningNarrative 开场白

**Files:**
- Create: `frontend/src/components/tour/OpeningNarrative.vue`

- [ ] **Step 1: 编写 OpeningNarrative.vue**

```vue
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useTour } from '../../composables/useTour.js'

const { tourSession, tourStep, fetchHalls } = useTour()

const displayedText = ref('')
const isTyping = ref(true)

const openingTexts = {
  A: '你好，我是本次带你勘探的考古队长。你现在站立的地方，不仅是西安半坡博物馆，更是中国第一座史前遗址博物馆。收起那些走马观花的游览心思吧，在我们脚下，是一座距今6000多年的母系氏族繁荣期村落。从1953年春天在浐河岸边发现它开始，老一辈考古人在这里进行了五次大规模的科学发掘，揭露面积整整达到1万平方米。直到今天，馆内依然保留着未发掘的探方。带好你的求知欲，跟紧我的脚步，我们马上进入这片国家一级遗址的核心区，用文物和地层数据说话。',
  B: '哎呀，稀客稀客！欢迎来到我的家——浐河边的半坡村。听说你们现在管这里叫"国家AAAA级景区"？哈哈，太客气了。对我来说，这里就是我们部落六千年前生息繁衍的地方。那时候，可是我们女人当家作主的母系氏族哦！我刚刚看了你们的历书，说是从1953年起，你们花了整整四年时间，扒开了这1万平方米的泥土，把我当年用过的陶罐和住过的房子都挖出来了。走吧，远道而来的朋友，去看看我现在被装在玻璃柜里的"家"，我讲给你听当年的故事。',
  C: '各位同学，欢迎来到西安半坡博物馆！导览开始前，老师先考考大家：你们知道中国"第一座"史前遗址博物馆是哪里吗？没错，就是我们脚下！请大家闭上眼睛想象一下，如果把时间往前推六千年，回到那个繁荣的母系氏族社会，生活在浐河岸边的先民们，每天都在忙些什么呢？自1958年建馆以来，这里展出了1万平方米的真实发掘现场。但在咱们今天的游览中，老师希望大家不仅要看那些已经出土的丰富遗存，更要留意那些"未发掘"的神秘区域。准备好开启今天的历史寻宝了吗？我们出发！',
}

const fullText = computed(() => openingTexts[tourSession.value?.persona] || openingTexts.A)

onMounted(() => {
  let index = 0
  const timer = setInterval(() => {
    if (index < fullText.value.length) {
      displayedText.value += fullText.value[index]
      index++
    } else {
      isTyping.value = false
      clearInterval(timer)
    }
  }, 30)
})

async function startExplore() {
  await fetchHalls()
  tourStep.value = 'hall-select'
}
</script>

<template>
  <div class="opening">
    <div class="opening-inner">
      <div class="persona-badge">
        {{ tourSession?.persona === 'A' ? '⛏️ 考古队长' : tourSession?.persona === 'B' ? '🏠 半坡原住民' : '📚 历史老师' }}
      </div>
      <div class="narrative-text">
        {{ displayedText }}
        <span v-if="isTyping" class="cursor">|</span>
      </div>
      <el-button
        v-if="!isTyping"
        type="primary"
        size="large"
        class="start-btn"
        @click="startExplore"
      >
        开始探索 →
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.opening {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.opening-inner {
  max-width: 640px;
  width: 100%;
  text-align: center;
}

.persona-badge {
  display: inline-block;
  padding: 8px 24px;
  background: rgba(212, 165, 116, 0.15);
  border: 1px solid rgba(212, 165, 116, 0.3);
  border-radius: 20px;
  color: #d4a574;
  font-size: 16px;
  margin-bottom: 32px;
}

.narrative-text {
  font-size: 17px;
  line-height: 2;
  text-align: left;
  color: #f0e6d3;
  white-space: pre-wrap;
}

.cursor {
  animation: blink 0.8s infinite;
  color: #d4a574;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.start-btn {
  margin-top: 40px;
  padding: 14px 48px;
  font-size: 18px;
  border-radius: 24px;
  background: #d4a574;
  border-color: #d4a574;
}

.start-btn:hover {
  background: #c49564;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/tour/OpeningNarrative.vue
git commit -m "feat(tour): add OpeningNarrative with typewriter effect"
```

### Task 21: HallSelect 展厅选择

**Files:**
- Create: `frontend/src/components/tour/HallSelect.vue`

- [ ] **Step 1: 编写 HallSelect.vue**

```vue
<script setup>
import { useTour } from '../../composables/useTour.js'

const { halls, selectHall, tourStep, tourSession } = useTour()

const hallIcons = {
  'relic-hall': '🏺',
  'site-hall': '🏚️',
}

async function onHallSelect(hallSlug) {
  await selectHall(hallSlug)
  tourStep.value = 'tour'
}
</script>

<template>
  <div class="hall-select">
    <div class="hall-select-inner">
      <h2 class="title">选择你想先参观的展厅</h2>
      <p class="subtitle">每个展厅都有独特的展品和故事等你发现</p>

      <div class="hall-cards">
        <div
          v-for="hall in halls"
          :key="hall.slug"
          class="hall-card"
          @click="onHallSelect(hall.slug)"
        >
          <div class="hall-icon">{{ hallIcons[hall.slug] || '🏛️' }}</div>
          <h3 class="hall-name">{{ hall.name }}</h3>
          <p class="hall-desc">{{ hall.description }}</p>
          <div class="hall-meta">
            <span>{{ hall.exhibit_count }} 件展品</span>
            <span>约 {{ hall.estimated_duration_minutes }} 分钟</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hall-select {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.hall-select-inner {
  max-width: 800px;
  width: 100%;
  text-align: center;
}

.title {
  font-size: 24px;
  color: #f0e6d3;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 40px;
}

.hall-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.hall-card {
  padding: 32px 24px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.hall-card:hover {
  background: rgba(212, 165, 116, 0.12);
  border-color: #d4a574;
  transform: translateY(-4px);
}

.hall-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.hall-name {
  font-size: 20px;
  color: #f0e6d3;
  margin-bottom: 12px;
}

.hall-desc {
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 16px;
}

.hall-meta {
  display: flex;
  justify-content: center;
  gap: 16px;
  font-size: 13px;
  color: #d4a574;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/tour/HallSelect.vue
git commit -m "feat(tour): add HallSelect component with hall cards"
```

---

## Chunk 7: Frontend Components - Exhibit Tour

### Task 22: ExhibitTour 展厅导览核心

**Files:**
- Create: `frontend/src/components/tour/ExhibitTour.vue`

- [ ] **Step 1: 编写 ExhibitTour.vue**

```vue
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useTour } from '../../composables/useTour.js'
import { api } from '../../api/index.js'
import HallIntro from './HallIntro.vue'
import ExhibitChat from './ExhibitChat.vue'
import ExhibitNavigator from './ExhibitNavigator.vue'

const {
  tourSession,
  currentHall,
  currentExhibit,
  hallExhibits,
  exhibitIndex,
  enterExhibit,
  completeHall,
  tourStep,
  bufferEvent,
  flushEvents,
} = useTour()

const subStep = ref('hall-intro')
const exhibits = ref([])
const loadingExhibits = ref(false)

const hallNames = {
  'relic-hall': '出土文物展厅',
  'site-hall': '遗址保护大厅',
}

const currentHallName = computed(() => hallNames[currentHall.value] || currentHall.value)

const hasNextExhibit = computed(() => {
  return exhibitIndex.value < exhibits.value.length - 1
})

const nextExhibit = computed(() => {
  if (hasNextExhibit.value) {
    return exhibits.value[exhibitIndex.value + 1]
  }
  return null
})

onMounted(async () => {
  loadingExhibits.value = true
  const result = await api.exhibits.list({ hall: currentHall.value, sort: 'display_order', is_active: 'true' })
  loadingExhibits.value = false
  if (result.ok) {
    exhibits.value = result.data.exhibits || result.data || []
  }
})

function onHallIntroDone() {
  if (exhibits.value.length > 0) {
    enterExhibit(exhibits.value[0])
    subStep.value = 'exhibit-chat'
    bufferEvent('hall_enter', { hall: currentHall.value })
  }
}

async function onNextExhibit() {
  if (hasNextExhibit.value) {
    const next = exhibits.value[exhibitIndex.value + 1]
    await enterExhibit(next)
    exhibitIndex.value++
    subStep.value = 'exhibit-chat'
  } else {
    await onHallComplete()
  }
}

async function onDeepDive() {
  bufferEvent('exhibit_deep_dive', {
    exhibit_id: currentExhibit.value?.id,
  })
}

async function onHallComplete() {
  await completeHall()
}
</script>

<template>
  <div class="exhibit-tour">
    <div class="tour-header-bar">
      <span class="hall-name">{{ currentHallName }}</span>
      <span class="exhibit-progress">{{ exhibitIndex + 1 }} / {{ exhibits.length }}</span>
    </div>

    <div v-if="loadingExhibits" class="loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载展品中...</span>
    </div>

    <template v-else>
      <HallIntro
        v-if="subStep === 'hall-intro'"
        :hall="currentHall"
        :hall-name="currentHallName"
        @done="onHallIntroDone"
      />

      <template v-if="subStep === 'exhibit-chat'">
        <ExhibitChat
          :exhibit="currentExhibit"
          @deep-dive="onDeepDive"
        />
        <ExhibitNavigator
          :has-next="hasNextExhibit"
          :next-exhibit="nextExhibit"
          :is-last="exhibitIndex >= exhibits.length - 1"
          @next="onNextExhibit"
          @complete="onHallComplete"
          @deep-dive="onDeepDive"
        />
      </template>
    </template>
  </div>
</template>

<style scoped>
.exhibit-tour {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tour-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.hall-name {
  font-size: 16px;
  font-weight: 600;
  color: #d4a574;
}

.exhibit-progress {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px;
  color: rgba(255, 255, 255, 0.5);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/tour/ExhibitTour.vue
git commit -m "feat(tour): add ExhibitTour component with hall intro and exhibit navigation"
```

### Task 23: HallIntro, ExhibitChat, ExhibitNavigator

**Files:**
- Create: `frontend/src/components/tour/HallIntro.vue`
- Create: `frontend/src/components/tour/ExhibitChat.vue`
- Create: `frontend/src/components/tour/ExhibitNavigator.vue`

- [ ] **Step 1: 编写 HallIntro.vue**

展厅介绍组件，展示当前展厅的介绍文字，通过 SSE 调用 LLM 生成。

```vue
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useTour } from '../../composables/useTour.js'

const props = defineProps({
  hall: String,
  hallName: String,
})

const emit = defineEmits(['done'])

const { tourSession, sendTourMessage, streamingContent, chatMessages, loading } = useTour()

const introText = ref('')
const isGenerating = ref(false)

const hallIntroPrompts = {
  A: `请以考古队长的身份，为游客介绍${props.hallName}。简要说明这个展厅的主题和重点观察方向，3-4句话即可。`,
  B: `请以半坡原住民的身份，为远道而来的朋友介绍${props.hallName}。用第一人称，2-3句话即可。`,
  C: `请以历史老师的身份，为同学们介绍${props.hallName}。抛出一个引人思考的问题，2-3句话即可。`,
}

onMounted(async () => {
  isGenerating.value = true
  await sendTourMessage(hallIntroPrompts[tourSession.value?.persona || 'A'])
  isGenerating.value = false
})

function continueTour() {
  emit('done')
}
</script>

<template>
  <div class="hall-intro">
    <h2 class="hall-title">{{ hallName }}</h2>
    <div class="intro-content">
      <template v-if="chatMessages.length > 0">
        <p v-for="msg in chatMessages.filter(m => m.role === 'assistant')" :key="msg.content" class="intro-text">
          {{ msg.content }}
        </p>
      </template>
      <p v-if="loading.chat" class="intro-text typing">
        {{ streamingContent }}<span class="cursor">|</span>
      </p>
    </div>
    <el-button
      v-if="!loading.chat && chatMessages.length > 0"
      type="primary"
      @click="continueTour"
    >
      开始参观 →
    </el-button>
  </div>
</template>

<style scoped>
.hall-intro {
  padding: 40px 24px;
  text-align: center;
  max-width: 640px;
  margin: 0 auto;
}

.hall-title {
  font-size: 24px;
  color: #d4a574;
  margin-bottom: 24px;
}

.intro-content {
  margin-bottom: 32px;
}

.intro-text {
  font-size: 16px;
  line-height: 2;
  color: #f0e6d3;
  text-align: left;
  white-space: pre-wrap;
}

.cursor {
  animation: blink 0.8s infinite;
  color: #d4a574;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
```

- [ ] **Step 2: 编写 ExhibitChat.vue**

展品对话组件，SSE 流式聊天。

```vue
<script setup>
import { ref, watch } from 'vue'
import { useTour } from '../../composables/useTour.js'

const props = defineProps({
  exhibit: Object,
})

const emit = defineEmits(['deep-dive'])

const {
  sendTourMessage,
  streamingContent,
  chatMessages,
  loading,
  suggestedActions,
  currentExhibit,
} = useTour()

const inputMessage = ref('')

async function sendMessage() {
  if (!inputMessage.value.trim() || loading.value.chat) return
  const msg = inputMessage.value.trim()
  inputMessage.value = ''
  await sendTourMessage(msg)
}

function handleDeepDive() {
  emit('deep-dive')
}
</script>

<template>
  <div class="exhibit-chat">
    <div v-if="exhibit" class="exhibit-header">
      <h3 class="exhibit-name">{{ exhibit.name }}</h3>
      <p v-if="exhibit.description" class="exhibit-desc">{{ exhibit.description }}</p>
    </div>

    <div class="messages">
      <div v-for="(msg, i) in chatMessages" :key="i" class="message" :class="msg.role">
        <span class="msg-content">{{ msg.content }}</span>
      </div>
      <div v-if="loading.chat && streamingContent" class="message assistant">
        <span class="msg-content">{{ streamingContent }}<span class="cursor">|</span></span>
      </div>
    </div>

    <div v-if="suggestedActions && !loading.chat" class="suggestions">
      <div v-if="suggestedActions.deep_dive_prompt" class="suggestion-card" @click="handleDeepDive">
        💡 {{ suggestedActions.deep_dive_prompt }}
      </div>
    </div>

    <div class="input-area">
      <el-input
        v-model="inputMessage"
        placeholder="向导览员提问..."
        @keyup.enter="sendMessage"
        :disabled="loading.chat"
      >
        <template #append>
          <el-button @click="sendMessage" :loading="loading.chat">发送</el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<style scoped>
.exhibit-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.exhibit-header {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.exhibit-name {
  font-size: 18px;
  color: #f0e6d3;
  margin-bottom: 4px;
}

.exhibit-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.6;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.message.user {
  align-self: flex-end;
  background: rgba(212, 165, 116, 0.2);
  color: #f0e6d3;
}

.message.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.06);
  color: #e0e0e0;
}

.cursor {
  animation: blink 0.8s infinite;
  color: #d4a574;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.suggestions {
  padding: 8px 24px;
}

.suggestion-card {
  padding: 12px 16px;
  background: rgba(212, 165, 116, 0.1);
  border: 1px solid rgba(212, 165, 116, 0.2);
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #d4a574;
  transition: background 0.2s;
}

.suggestion-card:hover {
  background: rgba(212, 165, 116, 0.2);
}

.input-area {
  padding: 12px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
```

- [ ] **Step 3: 编写 ExhibitNavigator.vue**

深入/下一个展品导航组件。

```vue
<script setup>
const props = defineProps({
  hasNext: Boolean,
  nextExhibit: Object,
  isLast: Boolean,
})

const emit = defineEmits(['next', 'complete', 'deep-dive'])
</script>

<template>
  <div class="navigator">
    <el-button @click="emit('deep-dive')" text class="nav-btn deep-dive">
      💡 继续深入了解
    </el-button>

    <el-button
      v-if="hasNext"
      @click="emit('next')"
      type="primary"
      class="nav-btn next-btn"
    >
      下一个展品 → {{ nextExhibit?.name || '' }}
    </el-button>

    <el-button
      v-if="isLast"
      @click="emit('complete')"
      type="success"
      class="nav-btn complete-btn"
    >
      完成本展厅 ✓
    </el-button>
  </div>
</template>

<style scoped>
.navigator {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 12px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
}

.nav-btn {
  border-radius: 20px;
}

.deep-dive {
  color: #d4a574;
}

.next-btn {
  background: #d4a574;
  border-color: #d4a574;
}

.complete-btn {
  background: #8fbc8f;
  border-color: #8fbc8f;
}
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/tour/HallIntro.vue frontend/src/components/tour/ExhibitChat.vue frontend/src/components/tour/ExhibitNavigator.vue
git commit -m "feat(tour): add HallIntro, ExhibitChat, ExhibitNavigator components"
```

---

## Chunk 8: Frontend Components - Tour Report

### Task 24: TourReport 游览报告

**Files:**
- Create: `frontend/src/components/tour/TourReport.vue`
- Create: `frontend/src/components/tour/TourStats.vue`
- Create: `frontend/src/components/tour/IdentityTags.vue`
- Create: `frontend/src/components/tour/RadarChart.vue`
- Create: `frontend/src/components/tour/TourOneLiner.vue`

- [ ] **Step 1: 编写 TourReport.vue**

```vue
<script setup>
import { onMounted } from 'vue'
import { useTour } from '../../composables/useTour.js'
import TourStats from './TourStats.vue'
import IdentityTags from './IdentityTags.vue'
import RadarChart from './RadarChart.vue'
import TourOneLiner from './TourOneLiner.vue'

const { tourReport, generateReport, tourSession, reportThemeTitle, loading } = useTour()

onMounted(async () => {
  if (!tourReport.value) {
    await generateReport()
  }
})
</script>

<template>
  <div class="tour-report" :class="`theme-${tourSession?.persona || 'A'}`">
    <div v-if="loading.report" class="loading">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span>正在生成你的专属报告...</span>
    </div>

    <template v-if="tourReport">
      <div class="report-header">
        <h1 class="report-title">{{ reportThemeTitle }}</h1>
      </div>

      <TourStats :report="tourReport" :persona="tourSession?.persona" />
      <IdentityTags :tags="tourReport.identity_tags" />
      <RadarChart :scores="tourReport.radar_scores" />
      <TourOneLiner :text="tourReport.one_liner" />

      <div class="qr-placeholder">
        <p>扫码分享你的导览报告</p>
        <div class="qr-box">QR</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tour-report {
  max-width: 640px;
  margin: 0 auto;
  padding: 40px 24px;
  min-height: 100%;
}

.theme-A { background: linear-gradient(180deg, #1a1a2e 0%, #2d1f0e 100%); }
.theme-B { background: linear-gradient(180deg, #1a1a2e 0%, #1e2d1a 100%); }
.theme-C { background: linear-gradient(180deg, #1a1a2e 0%, #1a1e2d 100%); }

.report-header {
  text-align: center;
  margin-bottom: 32px;
}

.report-title {
  font-size: 28px;
  color: #d4a574;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 80px 0;
  color: #d4a574;
}

.qr-placeholder {
  text-align: center;
  margin-top: 40px;
  padding: 24px;
  color: rgba(255, 255, 255, 0.5);
}

.qr-box {
  width: 120px;
  height: 120px;
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 12px auto 0;
  font-size: 24px;
  color: rgba(255, 255, 255, 0.3);
}
</style>
```

- [ ] **Step 2: 编写 TourStats.vue**

```vue
<script setup>
const props = defineProps({
  report: Object,
  persona: String,
})

const statTexts = {
  A: {
    duration: (min) => `本次实地勘探总耗时 ${Math.floor(min / 60)}小时${Math.floor(min % 60)}分。`,
    exhibit: (name, dur) => `你的目光在 ${name} 前锁定了最久，完成了深度的数据采集。`,
    hall: (name, dur) => `${name} 是你今日的核心作业区块，长达 ${dur} 分钟的驻足，证明了你对地层学有着极度敏锐的嗅觉。`,
  },
  B: {
    duration: (min) => `这次串门你一共逛了 ${Math.floor(min / 60)}小时${Math.floor(min % 60)}分。`,
    exhibit: (name) => `全村那么多宝贝，你偏偏对着 ${name} 挪不开眼，是不是想起了当年阿妈用它的样子？`,
    hall: (name, dur) => `你在 ${name} 待了足足 ${dur} 分钟，一定是闻到了那股熟悉的泥土味吧。`,
  },
  C: {
    duration: (min) => `本次沉浸式游学共计 ${Math.floor(min / 60)}小时${Math.floor(min % 60)}分。`,
    exhibit: (name) => `面对众多的史前谜题，你将"最佳观察奖"颁给了 ${name}。`,
    hall: (name, dur) => `在 ${name} 的 ${dur} 分钟里，你展现出了远超常人的求知欲。`,
  },
}
</script>

<template>
  <div class="tour-stats">
    <div class="stat-item">
      <p class="stat-text">{{ (statTexts[persona || 'A'])?.duration?.(report?.total_duration_minutes || 0) }}</p>
    </div>
    <div v-if="report?.most_viewed_exhibit_id" class="stat-item">
      <p class="stat-text">{{ (statTexts[persona || 'A'])?.exhibit?.(report.most_viewed_exhibit_id, report.most_viewed_exhibit_duration) }}</p>
    </div>
    <div v-if="report?.longest_hall" class="stat-item">
      <p class="stat-text">{{ (statTexts[persona || 'A'])?.hall?.(report.longest_hall, Math.floor((report.longest_hall_duration || 0) / 60)) }}</p>
    </div>
  </div>
</template>

<style scoped>
.tour-stats {
  margin-bottom: 32px;
}

.stat-item {
  padding: 16px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  margin-bottom: 12px;
}

.stat-text {
  font-size: 15px;
  line-height: 1.8;
  color: #f0e6d3;
}
</style>
```

- [ ] **Step 3: 编写 IdentityTags.vue**

```vue
<script setup>
const props = defineProps({
  tags: Array,
})

const tagColors = ['#d4a574', '#8fbc8f', '#6fa8dc']
</script>

<template>
  <div class="identity-tags">
    <h3 class="section-title">你的身份标签</h3>
    <div class="tags">
      <div v-for="(tag, i) in (tags || [])" :key="tag" class="tag-card" :style="{ borderColor: tagColors[i % 3] }">
        <span class="tag-text" :style="{ color: tagColors[i % 3] }">{{ tag }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-tags {
  margin-bottom: 32px;
}

.section-title {
  font-size: 18px;
  color: #f0e6d3;
  margin-bottom: 16px;
}

.tags {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.tag-card {
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid;
  border-radius: 12px;
}

.tag-text {
  font-size: 15px;
  font-weight: 600;
}
</style>
```

- [ ] **Step 4: 编写 RadarChart.vue**

Canvas 雷达图，5 个维度。

```vue
<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  scores: Object,
})

const canvasRef = ref(null)

const dimensions = [
  { key: 'civilization_resonance', label: '文明共鸣度' },
  { key: 'imagination_breadth', label: '脑洞广度' },
  { key: 'history_collection', label: '历史碎片' },
  { key: 'life_experience', label: '生活体验' },
  { key: 'ceramic_aesthetics', label: '彩陶审美' },
]

function drawChart() {
  const canvas = canvasRef.value
  if (!canvas || !props.scores) return

  const ctx = canvas.getContext('2d')
  const w = canvas.width = canvas.offsetWidth * 2
  const h = canvas.height = canvas.offsetHeight * 2
  ctx.scale(2, 2)
  const cw = canvas.offsetWidth
  const ch = canvas.offsetHeight
  const cx = cw / 2
  const cy = ch / 2
  const maxR = Math.min(cx, cy) - 40

  ctx.clearRect(0, 0, cw, ch)

  const n = dimensions.length
  const angleStep = (Math.PI * 2) / n

  for (let level = 1; level <= 3; level++) {
    const r = (maxR * level) / 3
    ctx.beginPath()
    for (let i = 0; i <= n; i++) {
      const angle = i * angleStep - Math.PI / 2
      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)'
    ctx.stroke()
  }

  for (let i = 0; i < n; i++) {
    const angle = i * angleStep - Math.PI / 2
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(cx + maxR * Math.cos(angle), cy + maxR * Math.sin(angle))
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)'
    ctx.stroke()

    const labelR = maxR + 20
    const lx = cx + labelR * Math.cos(angle)
    const ly = cy + labelR * Math.sin(angle)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
    ctx.font = '12px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(dimensions[i].label, lx, ly)
  }

  ctx.beginPath()
  for (let i = 0; i <= n; i++) {
    const idx = i % n
    const score = props.scores[dimensions[idx].key] || 1
    const r = (maxR * score) / 3
    const angle = idx * angleStep - Math.PI / 2
    const x = cx + r * Math.cos(angle)
    const y = cy + r * Math.sin(angle)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.fillStyle = 'rgba(212, 165, 116, 0.2)'
  ctx.fill()
  ctx.strokeStyle = '#d4a574'
  ctx.lineWidth = 2
  ctx.stroke()

  for (let i = 0; i < n; i++) {
    const score = props.scores[dimensions[i].key] || 1
    const r = (maxR * score) / 3
    const angle = i * angleStep - Math.PI / 2
    const x = cx + r * Math.cos(angle)
    const y = cy + r * Math.sin(angle)
    ctx.beginPath()
    ctx.arc(x, y, 4, 0, Math.PI * 2)
    ctx.fillStyle = '#d4a574'
    ctx.fill()
  }
}

onMounted(drawChart)
watch(() => props.scores, drawChart, { deep: true })
</script>

<template>
  <div class="radar-chart">
    <h3 class="section-title">游览五型图</h3>
    <canvas ref="canvasRef" class="chart-canvas" />
    <div class="level-legend">
      <span>B级</span><span>A级</span><span>S级</span>
    </div>
  </div>
</template>

<style scoped>
.radar-chart {
  margin-bottom: 32px;
  text-align: center;
}

.section-title {
  font-size: 18px;
  color: #f0e6d3;
  margin-bottom: 16px;
}

.chart-canvas {
  width: 300px;
  height: 300px;
  margin: 0 auto;
  display: block;
}

.level-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
```

- [ ] **Step 5: 编写 TourOneLiner.vue**

```vue
<script setup>
const props = defineProps({
  text: String,
})
</script>

<template>
  <div class="one-liner">
    <p class="liner-text">"{{ text }}"</p>
  </div>
</template>

<style scoped>
.one-liner {
  text-align: center;
  padding: 32px 16px;
  margin-bottom: 24px;
}

.liner-text {
  font-size: 20px;
  font-weight: 600;
  color: #d4a574;
  line-height: 1.6;
  font-style: italic;
}
</style>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/tour/TourReport.vue frontend/src/components/tour/TourStats.vue frontend/src/components/tour/IdentityTags.vue frontend/src/components/tour/RadarChart.vue frontend/src/components/tour/TourOneLiner.vue
git commit -m "feat(tour): add TourReport, TourStats, IdentityTags, RadarChart, TourOneLiner components"
```

---

## Chunk 9: Integration & Verification

### Task 25: App.vue 适配导览模式

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 在 App.vue 中检测 /tour 路由，隐藏 Header/Sidebar**

在 App.vue 的 template 中，为 Header 和 Sidebar 添加 v-if 判断：

```vue
<app-header v-if="!$route.path.startsWith('/tour')" />
<app-sidebar v-if="!$route.path.startsWith('/tour')" />
```

同时为主内容区添加条件样式：

```vue
<div class="app-main" :class="{ 'tour-mode': $route.path.startsWith('/tour') }">
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(tour): hide header/sidebar in tour mode"
```

### Task 26: 运行 lint 和测试

- [ ] **Step 1: 后端 ruff 检查**

Run: `uv run ruff check backend/`
Expected: 无错误

- [ ] **Step 2: 后端 mypy 检查**

Run: `uv run mypy backend/ --ignore-missing-imports`
Expected: 无严重错误

- [ ] **Step 3: 后端单元测试**

Run: `uv run pytest backend/tests/unit/ -v`
Expected: All passed

- [ ] **Step 4: 前端构建检查**

Run: `cd frontend && npm run build`
Expected: 构建成功

### Task 27: 创建新分支并合并

- [ ] **Step 1: 创建 feature 分支**

```bash
git checkout -b feature/tour-visitor-flow
```

- [ ] **Step 2: 将所有 commit 合并到新分支**

所有之前的 commit 已在 main 分支上，需要将它们移到 feature 分支。如果之前已经在 main 上开发，使用：

```bash
git log --oneline -20  # 查看最近的 commit
```

确认所有 tour 相关 commit 都在当前分支上。

- [ ] **Step 3: 最终 commit 汇总**

```bash
git log --oneline feature/tour-visitor-flow --not main
```

Expected: 看到所有 tour 相关的 commit

---

## 验收标准

- [ ] 后端：所有 `/api/v1/tour/*` 端点可正常响应
- [ ] 后端：TourSession 状态转换逻辑正确（onboarding→opening→touring→completed）
- [ ] 后端：五型图计算和身份标签选择逻辑正确
- [ ] 后端：SSE 流式聊天可正常工作，身份人设注入生效
- [ ] 后端：游览报告生成幂等
- [ ] 前端：`/tour` 路由可正常访问，全屏沉浸式布局
- [ ] 前端：3 道引导问卷可逐题完成
- [ ] 前端：开场白打字机效果正常
- [ ] 前端：展厅选择和展品交互流程完整
- [ ] 前端：游览报告展示正确（统计、标签、五型图、一句话）
- [ ] 测试：所有单元测试通过
- [ ] 代码：ruff 和 mypy 检查通过
