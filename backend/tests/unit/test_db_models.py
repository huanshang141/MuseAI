# backend/tests/unit/test_db_models.py
from app.infra.postgres.models import ChatMessage, ChatSession, Document, IngestionJob, User


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


def test_user_has_role_field():
    """Test that User model has role field that can be set to 'user'."""
    user = User(
        id="test-id",
        email="test@example.com",
        password_hash="hash",
        role="user",
    )
    assert hasattr(user, "role")
    assert user.role == "user"


def test_user_role_can_be_admin():
    """Test that User role can be set to 'admin'."""
    user = User(
        id="test-id",
        email="admin@example.com",
        password_hash="hash",
        role="admin",
    )
    assert user.role == "admin"


def test_user_role_field_exists():
    """Test that User model has role field defined."""
    from sqlalchemy import inspect
    mapper = inspect(User)
    role_column = mapper.columns.get("role")
    assert role_column is not None
    assert role_column.default is not None
    assert role_column.default.arg == "user"
