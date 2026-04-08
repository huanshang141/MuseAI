import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.postgres.models import Document, IngestionJob


async def create_document(session: AsyncSession, filename: str, size: int, user_id: str) -> Document:
    doc_id = str(uuid.uuid4())
    document = Document(
        id=doc_id,
        user_id=user_id,
        filename=filename,
        status="pending",
    )
    session.add(document)

    job_id = str(uuid.uuid4())
    ingestion_job = IngestionJob(
        id=job_id,
        document_id=doc_id,
        status="pending",
        chunk_count=0,
    )
    session.add(ingestion_job)

    await session.flush()
    await session.refresh(document)

    return document


async def get_documents_by_user(
    session: AsyncSession, user_id: str, limit: int = 20, offset: int = 0
) -> list[Document]:
    """Get documents for a user with pagination."""
    stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_documents_by_user(session: AsyncSession, user_id: str) -> int:
    """Count total documents for a user."""
    stmt = select(func.count()).select_from(Document).where(Document.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_document_by_id(session: AsyncSession, doc_id: str, user_id: str) -> Document | None:
    stmt = select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_ingestion_job_by_document(session: AsyncSession, doc_id: str) -> IngestionJob | None:
    stmt = select(IngestionJob).where(IngestionJob.document_id == doc_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_document(session: AsyncSession, doc_id: str, user_id: str) -> bool:
    document = await get_document_by_id(session, doc_id, user_id)
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True


async def update_document_status(
    session: AsyncSession,
    doc_id: str,
    status: str,
    error: str | None = None,
    chunk_count: int | None = None,
) -> Document | None:
    """Update document status and optionally set error message.

    Also updates the associated IngestionJob if chunk_count is provided.
    """
    stmt = select(Document).where(Document.id == doc_id)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        return None
    document.status = status
    document.error = error
    await session.flush()
    await session.refresh(document)

    # Also update the IngestionJob
    job_stmt = select(IngestionJob).where(IngestionJob.document_id == doc_id)
    job_result = await session.execute(job_stmt)
    ingestion_job = job_result.scalar_one_or_none()
    if ingestion_job is not None:
        ingestion_job.status = status
        ingestion_job.error = error
        if chunk_count is not None:
            ingestion_job.chunk_count = chunk_count

    return document


async def get_all_documents(
    session: AsyncSession, limit: int = 20, offset: int = 0
) -> list[Document]:
    """Get all documents with pagination (admin access)."""
    stmt = (
        select(Document)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_all_documents(session: AsyncSession) -> int:
    """Count total documents across all users (admin access)."""
    stmt = select(func.count()).select_from(Document)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_document_by_id_public(session: AsyncSession, doc_id: str) -> Document | None:
    """Get document by ID without user filtering (admin access)."""
    stmt = select(Document).where(Document.id == doc_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_document_by_id(session: AsyncSession, doc_id: str) -> bool:
    """Delete document by ID without user filtering (admin access)."""
    document = await get_document_by_id_public(session, doc_id)
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
