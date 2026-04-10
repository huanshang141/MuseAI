# backend/app/infra/postgres/adapters/document_repository.py
"""PostgreSQL adapter for document repository.

This adapter implements the DocumentRepositoryPort protocol using SQLAlchemy.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import Document, IngestionJob


class PostgresDocumentRepository:
    """PostgreSQL implementation of DocumentRepositoryPort."""

    def __init__(self, session: AsyncSession):
        """Initialize with async session.

        Args:
            session: SQLAlchemy async session for database operations.
        """
        self._session = session

    async def get_by_id(self, document_id: str) -> Document | None:
        """Retrieve a document by its ID.

        Args:
            document_id: The unique identifier of the document.

        Returns:
            The Document ORM instance if found, None otherwise.
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[Document]:
        """Retrieve documents for a specific user with pagination.

        Args:
            user_id: The user ID to filter by.
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            List of Document ORM instances.
        """
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self, limit: int = 20, offset: int = 0) -> list[Document]:
        """Retrieve all documents with pagination.

        Args:
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            List of Document ORM instances.
        """
        stmt = (
            select(Document)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        """Count total documents across all users.

        Returns:
            Total document count.
        """
        stmt = select(func.count()).select_from(Document)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_by_user_id(self, user_id: str) -> int:
        """Count documents for a specific user.

        Args:
            user_id: The user ID to count documents for.

        Returns:
            Document count for the user.
        """
        stmt = select(func.count()).select_from(Document).where(Document.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def create(
        self, filename: str, user_id: str
    ) -> tuple[Document, IngestionJob]:
        """Create a new document with associated ingestion job.

        Args:
            filename: Name of the file.
            user_id: ID of the user creating the document.

        Returns:
            Tuple of (document, ingestion_job) ORM instances.
        """
        doc_id = str(uuid.uuid4())
        document = Document(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            status="pending",
        )
        self._session.add(document)

        job_id = str(uuid.uuid4())
        ingestion_job = IngestionJob(
            id=job_id,
            document_id=doc_id,
            status="pending",
            chunk_count=0,
        )
        self._session.add(ingestion_job)

        await self._session.flush()
        await self._session.refresh(document)

        return document, ingestion_job

    async def update_status(
        self,
        document_id: str,
        status: str,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> Document | None:
        """Update document status and optionally error/chunk count.

        Args:
            document_id: ID of the document to update.
            status: New status value.
            error: Optional error message.
            chunk_count: Optional chunk count.

        Returns:
            Updated Document ORM instance, or None if not found.
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            return None
        document.status = status
        document.error = error

        job_stmt = select(IngestionJob).where(IngestionJob.document_id == document_id)
        job_result = await self._session.execute(job_stmt)
        ingestion_job = job_result.scalar_one_or_none()
        if ingestion_job is not None:
            ingestion_job.status = status
            ingestion_job.error = error
            if chunk_count is not None:
                ingestion_job.chunk_count = chunk_count

        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def delete(self, document_id: str) -> bool:
        """Delete a document by ID.

        Args:
            document_id: ID of the document to delete.

        Returns:
            True if deleted, False if not found.
        """
        document = await self.get_by_id(document_id)
        if document is None:
            return False
        await self._session.delete(document)
        await self._session.commit()
        return True

    async def get_ingestion_job_by_document(
        self, document_id: str
    ) -> IngestionJob | None:
        """Get ingestion job for a document.

        Args:
            document_id: ID of the document.

        Returns:
            IngestionJob ORM instance, or None if not found.
        """
        stmt = select(IngestionJob).where(IngestionJob.document_id == document_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
