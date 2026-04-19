from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects import SessionId, UserId
from app.infra.postgres.models.base import Base

if TYPE_CHECKING:
    from app.infra.postgres.models.user import User


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

    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="session", cascade="all, delete-orphan")


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

    session: Mapped[ChatSession] = relationship(back_populates="messages")
