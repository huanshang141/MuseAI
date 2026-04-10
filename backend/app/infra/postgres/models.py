# backend/app/infra/postgres/models.py
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.value_objects import (
    DocumentId,
    ExhibitId,
    JobId,
    Location,
    ProfileId,
    PromptId,
    SessionId,
    TourPathId,
    UserId,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


    def to_entity(self):
        from app.domain.entities import User as UserEntity
        return UserEntity(
            id=UserId(self.id),
            email=self.email,
            password_hash=self.password_hash,
            created_at=self.created_at,
            role=self.role,
        )

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    profile: Mapped["VisitorProfile"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    created_tour_paths: Mapped[list["TourPath"]] = relationship(back_populates="creator")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


    def to_entity(self):
        from app.domain.entities import ChatSession as ChatSessionEntity
        return ChatSessionEntity(
            id=SessionId(self.id),
            user_id=UserId(self.user_id),
            title=self.title,
            created_at=self.created_at,
        )

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


    def to_entity(self):
        from app.domain.entities import ChatMessage as ChatMessageEntity
        return ChatMessageEntity(
            id=self.id,
            session_id=SessionId(self.session_id),
            role=self.role,
            content=self.content,
            trace_id=self.trace_id or "",
            created_at=self.created_at,
        )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


    def to_entity(self):
        from app.domain.entities import Document as DocumentEntity
        return DocumentEntity(
            id=DocumentId(self.id),
            user_id=UserId(self.user_id),
            filename=self.filename,
            status=self.status,
            created_at=self.created_at,
        )

    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    exhibits: Mapped[list["Exhibit"]] = relationship(back_populates="document")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


    def to_entity(self):
        from app.domain.entities import IngestionJob as IngestionJobEntity
        return IngestionJobEntity(
            id=JobId(self.id),
            document_id=DocumentId(self.document_id),
            status=self.status,
            chunk_count=self.chunk_count,
            created_at=self.created_at,
            error=self.error,
        )

    document: Mapped["Document"] = relationship(back_populates="ingestion_jobs")


class Exhibit(Base):
    __tablename__ = "exhibits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    hall: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    era: Mapped[str | None] = mapped_column(String(100), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, default=0)
    estimated_visit_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in minutes
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


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
    document: Mapped["Document"] = relationship(back_populates="exhibits")


class TourPath(Base):
    __tablename__ = "tour_paths"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    estimated_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in minutes
    exhibit_ids: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


    def to_entity(self):
        from app.domain.entities import TourPath as TourPathEntity
        return TourPathEntity(
            id=TourPathId(self.id),
            name=self.name,
            description=self.description or "",
            theme=self.theme or "",
            estimated_duration=self.estimated_duration or 0,
            exhibit_ids=[ExhibitId(eid) for eid in (self.exhibit_ids or [])],
            is_active=self.is_active,
            created_by=UserId(self.created_by) if self.created_by else UserId(""),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
    creator: Mapped["User"] = relationship(back_populates="created_tour_paths")


class VisitorProfile(Base):
    __tablename__ = "visitor_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    knowledge_level: Mapped[str] = mapped_column(String(20), default="beginner")  # beginner, intermediate, expert
    narrative_preference: Mapped[str] = mapped_column(String(20), default="balanced")  # concise, balanced, detailed
    reflection_depth: Mapped[int] = mapped_column(Integer, default=2)  # 1-5 scale
    visited_exhibit_ids: Mapped[list] = mapped_column(JSON, default=list)
    feedback_history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


    def to_entity(self):
        from app.domain.entities import VisitorProfile as VPEntity
        return VPEntity(
            id=ProfileId(self.id),
            user_id=UserId(self.user_id),
            interests=self.interests or [],
            knowledge_level=self.knowledge_level,
            narrative_preference=self.narrative_preference,
            reflection_depth=str(self.reflection_depth),
            visited_exhibit_ids=[ExhibitId(eid) for eid in (self.visited_exhibit_ids or [])],
            feedback_history=self.feedback_history or [],
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
    user: Mapped["User"] = relationship(back_populates="profile")


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


    def to_entity(self):
        from app.domain.entities import Prompt as PromptEntity
        return PromptEntity(
            id=PromptId(self.id),
            key=self.key,
            name=self.name,
            description=self.description,
            category=self.category,
            content=self.content,
            variables=self.variables or [],
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
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
