from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects import ExhibitId, Location
from app.infra.postgres.models.base import Base


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
    estimated_visit_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
