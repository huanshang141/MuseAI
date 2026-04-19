from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects import (
    ExhibitId,
    TourEventId,
    TourPathId,
    TourReportId,
    TourSessionId,
    UserId,
)
from app.infra.postgres.models.base import Base

if TYPE_CHECKING:
    from app.infra.postgres.models.user import User


class TourPath(Base):
    __tablename__ = "tour_paths"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    estimated_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    creator: Mapped[User] = relationship(back_populates="created_tour_paths")


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

    user: Mapped[User | None] = relationship(back_populates="tour_sessions")
    events: Mapped[list[TourEventModel]] = relationship(back_populates="tour_session", cascade="all, delete-orphan")
    report: Mapped[TourReportModel | None] = relationship(
        back_populates="tour_session", uselist=False, cascade="all, delete-orphan"
    )


class TourEventModel(Base):
    __tablename__ = "tour_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tour_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("tour_sessions.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    exhibit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exhibits.id"), nullable=True)
    hall: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
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
            metadata=self.event_meta,
            created_at=self.created_at,
        )

    tour_session: Mapped[TourSessionModel] = relationship(back_populates="events")


class TourReportModel(Base):
    __tablename__ = "tour_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tour_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tour_sessions.id"), nullable=False, unique=True, index=True
    )
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

    tour_session: Mapped[TourSessionModel] = relationship(back_populates="report")
