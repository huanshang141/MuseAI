# backend/tests/unit/test_domain_entities.py
import pytest
from datetime import datetime
from app.domain.entities import User, ChatSession, ChatMessage, Document, IngestionJob
from app.domain.value_objects import SessionId, DocumentId, UserId, JobId


def test_user_creation():
    user = User(
        id=UserId("user-123"),
        email="test@example.com",
        password_hash="hashed_password",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert user.id.value == "user-123"
    assert user.email == "test@example.com"


def test_chat_session_creation():
    session = ChatSession(
        id=SessionId("session-123"),
        user_id=UserId("user-123"),
        title="Test Session",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert session.id.value == "session-123"
    assert session.user_id.value == "user-123"


def test_chat_message_creation():
    message = ChatMessage(
        id="msg-123",
        session_id=SessionId("session-123"),
        role="user",
        content="Hello",
        trace_id="trace-123",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert message.role == "user"
    assert message.content == "Hello"


def test_document_creation():
    doc = Document(
        id=DocumentId("doc-123"),
        user_id=UserId("user-123"),
        filename="test.pdf",
        status="pending",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert doc.filename == "test.pdf"
    assert doc.status == "pending"


def test_ingestion_job_creation():
    job = IngestionJob(
        id=JobId("job-123"),
        document_id=DocumentId("doc-123"),
        status="pending",
        chunk_count=0,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert job.status == "pending"
    assert job.chunk_count == 0


def test_ingestion_job_status_transition():
    job = IngestionJob(
        id=JobId("job-123"),
        document_id=DocumentId("doc-123"),
        status="pending",
        chunk_count=0,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    job.start()
    assert job.status == "processing"
    job.complete(chunk_count=10)
    assert job.status == "completed"
    assert job.chunk_count == 10


def test_ingestion_job_failure():
    job = IngestionJob(
        id=JobId("job-123"),
        document_id=DocumentId("doc-123"),
        status="pending",
        chunk_count=0,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    job.start()
    job.fail(error="Something went wrong")
    assert job.status == "failed"
    assert job.error == "Something went wrong"
