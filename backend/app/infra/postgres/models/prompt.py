from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.value_objects import PromptId
from app.infra.postgres.models.base import Base


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

    def to_entity(self):
        from app.domain.entities import PromptVersion as PromptVersionEntity

        return PromptVersionEntity(
            id=self.id,
            prompt_id=PromptId(self.prompt_id),
            version=self.version,
            content=self.content,
            changed_by=self.changed_by,
            change_reason=self.change_reason,
            created_at=self.created_at,
        )
