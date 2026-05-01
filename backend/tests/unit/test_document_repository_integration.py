# backend/tests/integration/test_document_repository_integration.py
"""Integration tests for document repository with real database session.

These tests verify the actual behavior of the document repository
against a real database, replacing brittle source-inspection tests
with behavior-based tests.
"""

import uuid

import pytest
from app.application.document_service import (
    count_all_documents,
    create_document,
    delete_document_by_id,
    get_document_by_id_public,
)
from app.infra.postgres.adapters.document_repository import PostgresDocumentRepository
from app.infra.postgres.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
async def test_engine():
    """Create an async engine for testing with in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_engine):
    """Create an async session for testing."""
    async_session_factory = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session


class TestDocumentRepositoryIntegration:
    """Integration tests for document repository operations."""

    @pytest.mark.asyncio
    async def test_document_repo_roundtrip_with_real_session(self, test_db_session):
        """Test full roundtrip: create, fetch, verify document with real session."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user_id = str(uuid.uuid4())
        filename = "a.txt"

        # Create document through service layer
        doc = await create_document(doc_repo, filename, user_id)
        await test_db_session.commit()

        # Verify document was created with correct attributes
        assert doc is not None
        assert doc.id is not None
        assert doc.filename == filename
        assert doc.user_id == user_id
        assert doc.status == "pending"

        # Fetch the document by ID (public access, no user filter)
        fetched = await get_document_by_id_public(doc_repo, doc.id)

        assert fetched is not None
        assert fetched.id == doc.id
        assert fetched.filename == filename
        assert fetched.user_id == user_id

    @pytest.mark.asyncio
    async def test_document_create_creates_ingestion_job(self, test_db_session):
        """Test that creating a document also creates an ingestion job."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user_id = str(uuid.uuid4())
        filename = "test_document.pdf"

        # Create document
        doc, job = await doc_repo.create(filename, user_id)
        await test_db_session.commit()

        # Verify both document and job were created
        assert doc is not None
        assert job is not None
        assert job.document_id == doc.id
        assert job.status == "pending"
        assert job.chunk_count == 0

    @pytest.mark.asyncio
    async def test_document_update_status_updates_both_doc_and_job(self, test_db_session):
        """Test that updating document status also updates the ingestion job."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user_id = str(uuid.uuid4())
        filename = "status_test.txt"

        # Create document
        doc, job = await doc_repo.create(filename, user_id)
        await test_db_session.commit()

        # Update status
        updated_doc = await doc_repo.update_status(
            doc.id,
            status="completed",
            chunk_count=42
        )
        await test_db_session.commit()

        # Verify document status updated
        assert updated_doc is not None
        assert updated_doc.status == "completed"

        # Verify ingestion job also updated
        updated_job = await doc_repo.get_ingestion_job_by_document(doc.id)
        assert updated_job is not None
        assert updated_job.status == "completed"
        assert updated_job.chunk_count == 42

    @pytest.mark.asyncio
    async def test_document_delete_removes_from_database(self, test_db_session):
        """Test that deleting a document removes it from the database."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user_id = str(uuid.uuid4())
        filename = "delete_test.txt"

        # Create document
        doc, _ = await doc_repo.create(filename, user_id)
        await test_db_session.commit()

        # Verify it exists
        fetched = await doc_repo.get_by_id(doc.id)
        assert fetched is not None

        # Delete it
        deleted = await delete_document_by_id(doc_repo, doc.id)

        assert deleted is True

        # Verify it's gone
        fetched_after = await doc_repo.get_by_id(doc.id)
        assert fetched_after is None

    @pytest.mark.asyncio
    async def test_document_get_by_user_id_filters_correctly(self, test_db_session):
        """Test that documents can be filtered by user ID."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())

        # Create documents for different users
        doc1, _ = await doc_repo.create("user1_doc.txt", user1_id)
        doc2, _ = await doc_repo.create("user2_doc.txt", user2_id)
        doc3, _ = await doc_repo.create("user1_doc2.txt", user1_id)
        await test_db_session.commit()

        # Get documents for user1
        user1_docs = await doc_repo.get_by_user_id(user1_id)
        assert len(user1_docs) == 2
        filenames = [d.filename for d in user1_docs]
        assert "user1_doc.txt" in filenames
        assert "user1_doc2.txt" in filenames

        # Get documents for user2
        user2_docs = await doc_repo.get_by_user_id(user2_id)
        assert len(user2_docs) == 1
        assert user2_docs[0].filename == "user2_doc.txt"

    @pytest.mark.asyncio
    async def test_document_count_operations(self, test_db_session):
        """Test document counting operations."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())

        # Create some documents
        await doc_repo.create("doc1.txt", user1_id)
        await doc_repo.create("doc2.txt", user1_id)
        await doc_repo.create("doc3.txt", user2_id)
        await test_db_session.commit()

        # Count by user
        user1_count = await doc_repo.count_by_user_id(user1_id)
        assert user1_count == 2

        user2_count = await doc_repo.count_by_user_id(user2_id)
        assert user2_count == 1

        # Count all
        total_count = await count_all_documents(doc_repo)
        assert total_count == 3

    @pytest.mark.asyncio
    async def test_document_pagination(self, test_db_session):
        """Test document pagination with limit and offset."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        user_id = str(uuid.uuid4())

        # Create 5 documents
        for i in range(5):
            await doc_repo.create(f"doc_{i}.txt", user_id)
        await test_db_session.commit()

        # Get first page (limit 2, offset 0)
        page1 = await doc_repo.get_by_user_id(user_id, limit=2, offset=0)
        assert len(page1) == 2

        # Get second page (limit 2, offset 2)
        page2 = await doc_repo.get_by_user_id(user_id, limit=2, offset=2)
        assert len(page2) == 2

        # Get remaining (limit 2, offset 4)
        page3 = await doc_repo.get_by_user_id(user_id, limit=2, offset=4)
        assert len(page3) == 1

    @pytest.mark.asyncio
    async def test_document_nonexistent_returns_none(self, test_db_session):
        """Test that fetching a nonexistent document returns None."""
        doc_repo = PostgresDocumentRepository(test_db_session)

        # Try to fetch a document that doesn't exist
        fetched = await doc_repo.get_by_id(str(uuid.uuid4()))
        assert fetched is None

        # Try to get ingestion job for nonexistent document
        job = await doc_repo.get_ingestion_job_by_document(str(uuid.uuid4()))
        assert job is None
