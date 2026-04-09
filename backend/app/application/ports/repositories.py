from typing import Any, Protocol

from app.domain.entities import (
    ChatMessage,
    ChatSession,
    Document,
    Exhibit,
    IngestionJob,
    User,
    VisitorProfile,
)
from app.domain.value_objects import ExhibitId, ProfileId, UserId


class UserRepositoryPort(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: str) -> User | None: ...

    async def add(self, user: User) -> None: ...


class DocumentRepositoryPort(Protocol):
    async def get_by_id(self, document_id: str) -> Document | None: ...

    async def get_by_user_id(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[Document]: ...

    async def get_all(self, limit: int = 20, offset: int = 0) -> list[Document]: ...

    async def count_all(self) -> int: ...

    async def count_by_user_id(self, user_id: str) -> int: ...

    async def create(
        self, filename: str, user_id: str
    ) -> tuple[Document, IngestionJob]: ...

    async def update_status(
        self,
        document_id: str,
        status: str,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> Document | None: ...

    async def delete(self, document_id: str) -> bool: ...

    async def get_ingestion_job_by_document(
        self, document_id: str
    ) -> IngestionJob | None: ...


class ExhibitRepositoryPort(Protocol):
    async def get_by_id(self, exhibit_id: ExhibitId) -> Exhibit | None: ...

    async def list_all(self, include_inactive: bool = False) -> list[Exhibit]: ...

    async def list_all_active(self) -> list[Exhibit]: ...

    async def list_by_category(
        self, category: str, include_inactive: bool = False
    ) -> list[Exhibit]: ...

    async def list_by_hall(
        self, hall: str, include_inactive: bool = False
    ) -> list[Exhibit]: ...

    async def list_with_filters(
        self,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
    ) -> list[Exhibit]: ...

    async def find_by_interests(
        self, interests: list[str], limit: int = 10
    ) -> list[Exhibit]: ...

    async def search_by_name(
        self,
        query: str,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Exhibit]: ...

    async def get_distinct_categories(self) -> list[str]: ...

    async def get_distinct_halls(self) -> list[str]: ...

    async def save(self, exhibit: Exhibit) -> Exhibit: ...

    async def delete(self, exhibit_id: ExhibitId) -> bool: ...


class VisitorProfileRepositoryPort(Protocol):
    async def get_by_id(self, profile_id: ProfileId) -> VisitorProfile | None: ...

    async def get_by_user_id(self, user_id: UserId) -> VisitorProfile | None: ...

    async def save(self, profile: VisitorProfile) -> VisitorProfile: ...

    async def update(self, profile: VisitorProfile) -> VisitorProfile: ...


class ChatSessionRepositoryPort(Protocol):
    async def create(self, title: str, user_id: str) -> ChatSession: ...

    async def get_by_id(self, session_id: str, user_id: str) -> ChatSession | None: ...

    async def get_by_user_id(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[ChatSession]: ...

    async def count_by_user_id(self, user_id: str) -> int: ...

    async def delete(self, session_id: str, user_id: str) -> bool: ...


class ChatMessageRepositoryPort(Protocol):
    async def add(
        self, session_id: str, role: str, content: str, trace_id: str | None = None
    ) -> ChatMessage: ...

    async def get_by_session(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessage]: ...

    async def count_by_session(self, session_id: str) -> int: ...


class LLMProviderPort(Protocol):
    async def generate(self, messages: list[dict[str, Any]]) -> Any: ...

    def generate_stream(self, messages: list[dict[str, Any]]) -> Any: ...


class CachePort(Protocol):
    async def get(self, key: str) -> Any: ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...


class CuratorAgentPort(Protocol):
    async def plan_tour(
        self, user_id: str, available_time: int, interests: list[str] | None = None
    ) -> dict[str, Any]: ...

    async def generate_narrative(
        self, user_id: str, exhibit_id: str
    ) -> dict[str, Any]: ...

    async def get_reflection_prompts(
        self, user_id: str, exhibit_id: str
    ) -> dict[str, Any]: ...


__all__ = [
    "UserRepositoryPort",
    "DocumentRepositoryPort",
    "ExhibitRepositoryPort",
    "VisitorProfileRepositoryPort",
    "ChatSessionRepositoryPort",
    "ChatMessageRepositoryPort",
    "LLMProviderPort",
    "CachePort",
    "CuratorAgentPort",
]
