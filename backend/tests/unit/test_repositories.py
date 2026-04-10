# backend/tests/unit/test_repositories.py
import uuid
from datetime import UTC, datetime

import pytest
from app.domain.entities import Exhibit, VisitorProfile
from app.domain.value_objects import (
    ExhibitId,
    Location,
    ProfileId,
    UserId,
)
from app.infra.postgres.models import Base
from app.infra.postgres.repositories import (
    PostgresExhibitRepository,
    PostgresVisitorProfileRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


# Use in-memory SQLite for testing
@pytest.fixture
async def async_session():
    """Create an async session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def sample_exhibit():
    """Create a sample exhibit entity."""
    now = datetime.now(UTC)
    return Exhibit(
        id=ExhibitId(str(uuid.uuid4())),
        name="Ancient Vase",
        description="A beautiful ancient vase from the Ming Dynasty.",
        location=Location(x=10.5, y=20.3, floor=2),
        hall="Hall A",
        category="Ceramics",
        era="Ming Dynasty",
        importance=5,
        estimated_visit_time=15,
        document_id=str(uuid.uuid4()),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_visitor_profile():
    """Create a sample visitor profile entity."""
    now = datetime.now(UTC)
    return VisitorProfile(
        id=ProfileId(str(uuid.uuid4())),
        user_id=UserId(str(uuid.uuid4())),
        interests=["Ceramics", "Paintings", "Sculptures"],
        knowledge_level="intermediate",
        narrative_preference="detailed",
        reflection_depth="3",
        visited_exhibit_ids=[ExhibitId(str(uuid.uuid4()))],
        feedback_history=["positive", "neutral"],
        created_at=now,
        updated_at=now,
    )


class TestPostgresExhibitRepository:
    """Tests for PostgresExhibitRepository."""

    async def test_save_new_exhibit(self, async_session, sample_exhibit):
        """Test saving a new exhibit."""
        repo = PostgresExhibitRepository(async_session)

        result = await repo.save(sample_exhibit)
        await async_session.commit()

        assert result.id == sample_exhibit.id
        assert result.name == sample_exhibit.name
        assert result.category == sample_exhibit.category

    async def test_get_by_id_existing(self, async_session, sample_exhibit):
        """Test getting an existing exhibit by ID."""
        repo = PostgresExhibitRepository(async_session)

        # First save the exhibit
        await repo.save(sample_exhibit)
        await async_session.commit()

        # Then retrieve it
        result = await repo.get_by_id(sample_exhibit.id)

        assert result is not None
        assert result.id == sample_exhibit.id
        assert result.name == sample_exhibit.name
        assert result.location.x == sample_exhibit.location.x
        assert result.location.y == sample_exhibit.location.y
        assert result.location.floor == sample_exhibit.location.floor

    async def test_get_by_id_nonexistent(self, async_session):
        """Test getting a non-existent exhibit."""
        repo = PostgresExhibitRepository(async_session)

        result = await repo.get_by_id(ExhibitId(str(uuid.uuid4())))

        assert result is None

    async def test_update_existing_exhibit(self, async_session, sample_exhibit):
        """Test updating an existing exhibit."""
        repo = PostgresExhibitRepository(async_session)

        # First save the exhibit
        await repo.save(sample_exhibit)
        await async_session.commit()

        # Modify the exhibit
        sample_exhibit.name = "Updated Vase Name"
        sample_exhibit.importance = 10

        # Save again (should update)
        result = await repo.save(sample_exhibit)
        await async_session.commit()

        assert result.name == "Updated Vase Name"
        assert result.importance == 10

        # Verify by fetching again
        fetched = await repo.get_by_id(sample_exhibit.id)
        assert fetched.name == "Updated Vase Name"

    async def test_list_all_active_only(self, async_session):
        """Test listing only active exhibits."""
        repo = PostgresExhibitRepository(async_session)
        now = datetime.now(UTC)

        # Create active exhibit
        active_exhibit = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name="Active Exhibit",
            description="An active exhibit",
            location=Location(x=1.0, y=2.0, floor=1),
            hall="Hall A",
            category="Test",
            era="Modern",
            importance=1,
            estimated_visit_time=5,
            document_id=str(uuid.uuid4()),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        # Create inactive exhibit
        inactive_exhibit = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name="Inactive Exhibit",
            description="An inactive exhibit",
            location=Location(x=3.0, y=4.0, floor=1),
            hall="Hall B",
            category="Test",
            era="Modern",
            importance=1,
            estimated_visit_time=5,
            document_id=str(uuid.uuid4()),
            is_active=False,
            created_at=now,
            updated_at=now,
        )

        await repo.save(active_exhibit)
        await repo.save(inactive_exhibit)
        await async_session.commit()

        # List only active
        results = await repo.list_all(include_inactive=False)
        assert len(results) == 1
        assert results[0].name == "Active Exhibit"

        # List all including inactive
        results = await repo.list_all(include_inactive=True)
        assert len(results) == 2

    async def test_list_by_category(self, async_session):
        """Test listing exhibits by category."""
        repo = PostgresExhibitRepository(async_session)
        now = datetime.now(UTC)

        # Create exhibits in different categories
        ceramics = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name="Ceramic Piece",
            description="A ceramic piece",
            location=Location(x=1.0, y=2.0, floor=1),
            hall="Hall A",
            category="Ceramics",
            era="Modern",
            importance=1,
            estimated_visit_time=5,
            document_id=str(uuid.uuid4()),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        painting = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name="Oil Painting",
            description="An oil painting",
            location=Location(x=3.0, y=4.0, floor=1),
            hall="Hall B",
            category="Paintings",
            era="Modern",
            importance=1,
            estimated_visit_time=5,
            document_id=str(uuid.uuid4()),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        await repo.save(ceramics)
        await repo.save(painting)
        await async_session.commit()

        results = await repo.list_by_category("Ceramics")
        assert len(results) == 1
        assert results[0].name == "Ceramic Piece"

    async def test_find_by_interests(self, async_session):
        """Test finding exhibits by interests (categories)."""
        repo = PostgresExhibitRepository(async_session)
        now = datetime.now(UTC)

        ceramics = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name="Ceramic Piece",
            description="A ceramic piece",
            location=Location(x=1.0, y=2.0, floor=1),
            hall="Hall A",
            category="Ceramics",
            era="Modern",
            importance=1,
            estimated_visit_time=5,
            document_id=str(uuid.uuid4()),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        await repo.save(ceramics)
        await async_session.commit()

        results = await repo.find_by_interests(["Ceramics", "Paintings"])
        assert len(results) == 1
        assert results[0].category == "Ceramics"

    async def test_delete_exhibit(self, async_session, sample_exhibit):
        """Test deleting an exhibit."""
        repo = PostgresExhibitRepository(async_session)

        await repo.save(sample_exhibit)
        await async_session.commit()

        # Verify it exists
        assert await repo.get_by_id(sample_exhibit.id) is not None

        # Delete it
        deleted = await repo.delete(sample_exhibit.id)
        await async_session.commit()

        assert deleted is True
        assert await repo.get_by_id(sample_exhibit.id) is None

    async def test_delete_nonexistent_exhibit(self, async_session):
        """Test deleting a non-existent exhibit."""
        repo = PostgresExhibitRepository(async_session)

        deleted = await repo.delete(ExhibitId(str(uuid.uuid4())))

        assert deleted is False


class TestPostgresVisitorProfileRepository:
    """Tests for PostgresVisitorProfileRepository."""

    async def test_save_new_profile(self, async_session, sample_visitor_profile):
        """Test saving a new visitor profile."""
        repo = PostgresVisitorProfileRepository(async_session)

        result = await repo.save(sample_visitor_profile)
        await async_session.commit()

        assert result.id == sample_visitor_profile.id
        assert result.user_id == sample_visitor_profile.user_id
        assert result.interests == sample_visitor_profile.interests
        assert result.knowledge_level == sample_visitor_profile.knowledge_level

    async def test_get_by_id_existing(self, async_session, sample_visitor_profile):
        """Test getting an existing profile by ID."""
        repo = PostgresVisitorProfileRepository(async_session)

        await repo.save(sample_visitor_profile)
        await async_session.commit()

        result = await repo.get_by_id(sample_visitor_profile.id)

        assert result is not None
        assert result.id == sample_visitor_profile.id
        assert result.knowledge_level == sample_visitor_profile.knowledge_level
        assert result.reflection_depth == sample_visitor_profile.reflection_depth

    async def test_get_by_user_id(self, async_session, sample_visitor_profile):
        """Test getting a profile by user ID."""
        repo = PostgresVisitorProfileRepository(async_session)

        await repo.save(sample_visitor_profile)
        await async_session.commit()

        result = await repo.get_by_user_id(sample_visitor_profile.user_id)

        assert result is not None
        assert result.id == sample_visitor_profile.id
        assert result.user_id == sample_visitor_profile.user_id

    async def test_get_by_user_id_nonexistent(self, async_session):
        """Test getting a non-existent profile by user ID."""
        repo = PostgresVisitorProfileRepository(async_session)

        result = await repo.get_by_user_id(UserId(str(uuid.uuid4())))

        assert result is None

    async def test_update_profile(self, async_session, sample_visitor_profile):
        """Test updating an existing profile."""
        repo = PostgresVisitorProfileRepository(async_session)

        # First save
        await repo.save(sample_visitor_profile)
        await async_session.commit()

        # Modify
        sample_visitor_profile.knowledge_level = "expert"
        sample_visitor_profile.interests.append("Photography")

        # Update
        result = await repo.update(sample_visitor_profile)
        await async_session.commit()

        assert result.knowledge_level == "expert"
        assert "Photography" in result.interests

        # Verify by fetching again
        fetched = await repo.get_by_id(sample_visitor_profile.id)
        assert fetched.knowledge_level == "expert"
