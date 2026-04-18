# backend/app/domain/entities.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .exceptions import PromptVariableError
from .value_objects import (
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


@dataclass
class User:
    id: UserId
    email: str
    password_hash: str
    created_at: datetime
    role: str = "user"


@dataclass
class ChatSession:
    def add_message(self, message: "ChatMessage") -> None:
        pass

    def close(self) -> None:
        pass

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
    def update_status(self, status: str, error: str | None = None) -> None:
        self.status = status
        self.error = error

    id: DocumentId
    user_id: UserId
    filename: str
    status: str
    created_at: datetime
    error: str | None = None


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
    def update_details(
        self,
        name: str | None = None,
        description: str | None = None,
        hall: str | None = None,
        category: str | None = None,
        era: str | None = None,
        importance: int | None = None,
        estimated_visit_time: int | None = None,
        document_id: str | None = None,
    ) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if hall is not None:
            self.hall = hall
        if category is not None:
            self.category = category
        if era is not None:
            self.era = era
        if importance is not None:
            self.importance = importance
        if estimated_visit_time is not None:
            self.estimated_visit_time = estimated_visit_time
        if document_id is not None:
            self.document_id = document_id

    def deactivate(self) -> None:
        self.is_active = False

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
    exhibit_ids: list[ExhibitId]
    is_active: bool
    created_by: UserId
    created_at: datetime
    updated_at: datetime


@dataclass
class VisitorProfile:
    def update_preferences(
        self,
        interests: list[str] | None = None,
        knowledge_level: str | None = None,
        narrative_preference: str | None = None,
        reflection_depth: str | None = None,
    ) -> None:
        if interests is not None:
            self.interests = interests
        if knowledge_level is not None:
            self.knowledge_level = knowledge_level
        if narrative_preference is not None:
            self.narrative_preference = narrative_preference
        if reflection_depth is not None:
            self.reflection_depth = reflection_depth

    id: ProfileId
    user_id: UserId
    interests: list[str]
    knowledge_level: str
    narrative_preference: str
    reflection_depth: str
    visited_exhibit_ids: list[ExhibitId]
    feedback_history: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class Prompt:
    id: PromptId
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
    prompt_id: PromptId
    version: int
    content: str
    changed_by: str | None
    change_reason: str | None
    created_at: datetime


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
    metadata: dict[str, Any] | None
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
    radar_scores: dict[str, Any]
    one_liner: str
    report_theme: str
    created_at: datetime
