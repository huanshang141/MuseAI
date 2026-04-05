# backend/app/domain/entities.py
from dataclasses import dataclass
from datetime import datetime

from .value_objects import DocumentId, JobId, SessionId, UserId


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
