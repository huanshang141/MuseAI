# backend/tests/unit/test_domain_entities.py
from datetime import datetime

import pytest
from app.domain.entities import (
    ChatMessage,
    ChatSession,
    Document,
    Exhibit,
    IngestionJob,
    Prompt,
    PromptVersion,
    TourPath,
    User,
    VisitorProfile,
)
from app.domain.exceptions import PromptVariableError
from app.domain.value_objects import (
    DocumentId,
    ExhibitId,
    JobId,
    Location,
    ProfileId,
    PromptId,
    SessionId,
    TourPathId,
    UserId,
)


def test_user_creation():
    user = User(
        id=UserId("user-123"),
        email="test@example.com",
        password_hash="hashed_password",
        role="user",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert user.id.value == "user-123"
    assert user.email == "test@example.com"
    assert user.role == "user"


def test_user_creation_with_admin_role():
    user = User(
        id=UserId("admin-123"),
        email="admin@example.com",
        password_hash="hashed_password",
        role="admin",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert user.role == "admin"


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


def test_exhibit_creation():
    exhibit = Exhibit(
        id=ExhibitId("exhibit-123"),
        name="Ancient Vase",
        description="A beautiful ancient vase from the Ming Dynasty",
        location=Location(x=10.5, y=20.3, floor=2),
        hall="Hall A",
        category="Ceramics",
        era="Ming Dynasty",
        importance=5,
        estimated_visit_time=15,
        document_id="doc-456",
        is_active=True,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert exhibit.id.value == "exhibit-123"
    assert exhibit.name == "Ancient Vase"
    assert exhibit.location.x == 10.5
    assert exhibit.location.y == 20.3
    assert exhibit.location.floor == 2
    assert exhibit.importance == 5


def test_tour_path_creation():
    tour = TourPath(
        id=TourPathId("tour-123"),
        name="Ancient China Tour",
        description="A tour through ancient Chinese artifacts",
        theme="Ancient History",
        estimated_duration=60,
        exhibit_ids=[ExhibitId("exhibit-123"), ExhibitId("exhibit-456")],
        is_active=True,
        created_by=UserId("user-123"),
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert tour.id.value == "tour-123"
    assert tour.name == "Ancient China Tour"
    assert len(tour.exhibit_ids) == 2
    assert tour.exhibit_ids[0].value == "exhibit-123"


def test_visitor_profile_creation():
    profile = VisitorProfile(
        id=ProfileId("profile-123"),
        user_id=UserId("user-123"),
        interests=["Ancient History", "Art", "Sculpture"],
        knowledge_level="intermediate",
        narrative_preference="storytelling",
        reflection_depth="deep",
        visited_exhibit_ids=[ExhibitId("exhibit-123")],
        feedback_history=["positive"],
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert profile.id.value == "profile-123"
    assert profile.user_id.value == "user-123"
    assert profile.knowledge_level == "intermediate"
    assert len(profile.interests) == 3
    assert "Ancient History" in profile.interests


def test_prompt_creation():
    prompt = Prompt(
        id=PromptId("prompt-123"),
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Hello {name}!",
        variables=[{"name": "name", "description": "User name"}],
        is_active=True,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
        current_version=1,
    )
    assert prompt.id.value == "prompt-123"
    assert prompt.key == "test_prompt"
    assert prompt.content == "Hello {name}!"
    assert prompt.is_active is True


def test_prompt_render_with_variables():
    prompt = Prompt(
        id=PromptId("prompt-123"),
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Hello {name}, you are {age} years old!",
        variables=[
            {"name": "name", "description": "User name"},
            {"name": "age", "description": "User age"},
        ],
        is_active=True,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    result = prompt.render({"name": "Alice", "age": "30"})
    assert result == "Hello Alice, you are 30 years old!"


def test_prompt_render_missing_variable_raises_error():
    prompt = Prompt(
        id=PromptId("prompt-123"),
        key="test_prompt",
        name="Test Prompt",
        description="A test prompt",
        category="test",
        content="Hello {name}, you are {age} years old!",
        variables=[
            {"name": "name", "description": "User name"},
            {"name": "age", "description": "User age"},
        ],
        is_active=True,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    with pytest.raises(PromptVariableError) as exc_info:
        prompt.render({"name": "Alice"})
    assert "age" in str(exc_info.value)


def test_prompt_version_creation():
    version = PromptVersion(
        id="version-123",
        prompt_id=PromptId("prompt-123"),
        version=1,
        content="Hello {name}!",
        changed_by="user-123",
        change_reason="Initial version",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assert version.id == "version-123"
    assert version.prompt_id.value == "prompt-123"
    assert version.version == 1
    assert version.changed_by == "user-123"
