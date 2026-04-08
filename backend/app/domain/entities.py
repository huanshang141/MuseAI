# backend/app/domain/entities.py
from dataclasses import dataclass
from datetime import datetime
from typing import List

from .exceptions import PromptVariableError
from .value_objects import DocumentId, JobId, SessionId, UserId, ExhibitId, TourPathId, ProfileId, Location


@dataclass
class User:
    id: UserId
    email: str
    password_hash: str
    created_at: datetime
    role: str = "user"


@dataclass
class ChatSession:
    id: SessionId
    user_id: UserId
    title: str
    created_at: datetime


@dataclass
class ChatMessage:
    id: str
    session_id: SessionId
    role: str
    content: str
    trace_id: str
    created_at: datetime


@dataclass
class Document:
    id: DocumentId
    user_id: UserId
    filename: str
    status: str
    created_at: datetime


@dataclass
class IngestionJob:
    id: JobId
    document_id: DocumentId
    status: str
    chunk_count: int
    created_at: datetime
    error: str | None = None

    def start(self) -> None:
        if self.status != "pending":
            raise ValueError("Can only start pending jobs")
        self.status = "processing"

    def complete(self, chunk_count: int) -> None:
        if self.status != "processing":
            raise ValueError("Can only complete processing jobs")
        self.status = "completed"
        self.chunk_count = chunk_count

    def fail(self, error: str) -> None:
        if self.status != "processing":
            raise ValueError("Can only fail processing jobs")
        self.status = "failed"
        self.error = error


@dataclass
class Exhibit:
    id: ExhibitId
    name: str
    description: str
    location: Location
    hall: str
    category: str
    era: str
    importance: int
    estimated_visit_time: int
    document_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class TourPath:
    id: TourPathId
    name: str
    description: str
    theme: str
    estimated_duration: int
    exhibit_ids: List[ExhibitId]
    is_active: bool
    created_by: UserId
    created_at: datetime
    updated_at: datetime


@dataclass
class VisitorProfile:
    id: ProfileId
    user_id: UserId
    interests: List[str]
    knowledge_level: str
    narrative_preference: str
    reflection_depth: str
    visited_exhibit_ids: List[ExhibitId]
    feedback_history: List[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class Prompt:
    id: str
    key: str
    name: str
    description: str | None
    category: str
    content: str
    variables: list[dict[str, str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    current_version: int = 1

    def render(self, variables: dict[str, str]) -> str:
        """Render the prompt template with provided variables."""
        try:
            return self.content.format(**variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise PromptVariableError(
                f"Missing required variable: {missing_var}"
            ) from e


@dataclass
class PromptVersion:
    id: str
    prompt_id: str
    version: int
    content: str
    changed_by: str | None
    change_reason: str | None
    created_at: datetime
