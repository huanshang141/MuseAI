from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects import UserId
from app.infra.postgres.models.base import Base


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
    tour_sessions: Mapped[list["TourSessionModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
