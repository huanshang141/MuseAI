import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.postgres.models import Document, IngestionJob

MOCK_USER_ID = "user-001"


async def create_document(session: AsyncSession, filename: str, size: int) -> Document:
    doc_id = str(uuid.uuid4())
    document = Document(
        id=doc_id,
        user_id=MOCK_USER_ID,
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


async def get_documents_by_user(session: AsyncSession) -> list[Document]:
    stmt = select(Document).where(Document.user_id == MOCK_USER_ID).order_by(Document.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_document_by_id(session: AsyncSession, doc_id: str) -> Document | None:
    stmt = select(Document).where(Document.id == doc_id, Document.user_id == MOCK_USER_ID)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_ingestion_job_by_document(session: AsyncSession, doc_id: str) -> IngestionJob | None:
    stmt = select(IngestionJob).where(IngestionJob.document_id == doc_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_document(session: AsyncSession, doc_id: str) -> bool:
    document = await get_document_by_id(session, doc_id)
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
