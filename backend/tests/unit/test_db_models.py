# backend/tests/unit/test_db_models.py
from app.infra.postgres.models import User, ChatSession, ChatMessage, Document, IngestionJob


def test_user_model():
    user = User(
        id="user-123",
        email="test@example.com",
        password_hash="hashed"
    )
    assert user.id == "user-123"
    assert user.email == "test@example.com"


def test_chat_session_model():
    session = ChatSession(
        id="session-123",
        user_id="user-123",
        title="Test Session"
    )
    assert session.user_id == "user-123"
    assert session.title == "Test Session"


def test_chat_message_model():
    msg = ChatMessage(
        id="msg-123",
        session_id="session-123",
        role="user",
        content="Hello",
        trace_id="trace-123"
    )
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_document_model():
    doc = Document(
        id="doc-123",
        user_id="user-123",
        filename="test.pdf",
        status="pending"
    )
    assert doc.filename == "test.pdf"
    assert doc.status == "pending"


def test_ingestion_job_model():
    job = IngestionJob(
        id="job-123",
        document_id="doc-123",
        status="pending",
        chunk_count=0
    )
    assert job.document_id == "doc-123"
    assert job.status == "pending"
