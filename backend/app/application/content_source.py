# backend/app/application/content_source.py
"""Unified content source model for indexing."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentMetadata:
    """Metadata for content sources."""

    # Common fields
    name: str | None = None

    # Document-specific
    filename: str | None = None

    # Exhibit-specific
    category: str | None = None
    hall: str | None = None
    floor: int | None = None
    era: str | None = None
    importance: int | None = None
    location_x: float | None = None
    location_y: float | None = None

    # Allow additional fields
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {}
        if self.name is not None:
            result["name"] = self.name
        if self.filename is not None:
            result["filename"] = self.filename
        if self.category is not None:
            result["category"] = self.category
        if self.hall is not None:
            result["hall"] = self.hall
        if self.floor is not None:
            result["floor"] = self.floor
        if self.era is not None:
            result["era"] = self.era
        if self.importance is not None:
            result["importance"] = self.importance
        if self.location_x is not None:
            result["location_x"] = self.location_x
        if self.location_y is not None:
            result["location_y"] = self.location_y
        result.update(self.extra)
        return result


@dataclass
class ContentSource:
    """Unified content source for indexing.

    Represents any content that can be chunked and embedded for RAG retrieval.
    """

    source_id: str
    source_type: str  # "document" | "exhibit"
    content: str
    metadata: ContentMetadata = field(default_factory=ContentMetadata)

    def __post_init__(self) -> None:
        """Validate source_type."""
        valid_types = {"document", "exhibit"}
        if self.source_type not in valid_types:
            raise ValueError(f"source_type must be one of {valid_types}, got '{self.source_type}'")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
        }
