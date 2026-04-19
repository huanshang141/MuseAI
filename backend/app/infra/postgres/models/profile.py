from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects import ExhibitId, ProfileId, UserId
from app.infra.postgres.models.base import Base

if TYPE_CHECKING:
    from app.infra.postgres.models.user import User


class VisitorProfile(Base):
    __tablename__ = "visitor_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    knowledge_level: Mapped[str] = mapped_column(String(20), default="beginner")
    narrative_preference: Mapped[str] = mapped_column(String(20), default="balanced")
    reflection_depth: Mapped[int] = mapped_column(Integer, default=2)
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

    user: Mapped[User] = relationship(back_populates="profile")
