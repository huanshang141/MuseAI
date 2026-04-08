from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel

from app.api.deps import CurrentAdmin, OptionalUser, RateLimitDep, SessionDep, UnifiedIndexingServiceDep
from app.application.content_source import ContentMetadata, ContentSource
from app.application.document_service import (
    count_all_documents,
    create_document,
    delete_document_by_id,
    get_all_documents,
    get_document_by_id_public,
    get_ingestion_job_by_document,
    update_document_status,
)
from app.application.unified_indexing_service import UnifiedIndexingService
from app.infra.postgres.adapters.document_repository import PostgresDocumentRepository
from app.infra.postgres.database import get_session, get_session_maker

router = APIRouter(prefix="/documents", tags=["documents"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


# ============================================================================
# Public Response Models (whitelisted fields for unauthenticated/guest access)
# ============================================================================


class PublicDocumentResponse(BaseModel):
    """Public document response with whitelisted fields only.

    This model formalizes the public document read contract, exposing only
    fields that are safe for unauthenticated/guest access.
    """

    id: str
    filename: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class PublicDocumentListResponse(BaseModel):
    """Public document list response with whitelisted fields."""

    documents: list[PublicDocumentResponse]
    total: int
    limit: int
    offset: int


class PublicIngestionJobResponse(BaseModel):
    """Public ingestion job response with whitelisted fields only.

    This model formalizes the public ingestion status read contract.
    """

    id: str
    document_id: str
    status: str
    chunk_count: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ============================================================================
# Admin/Full Response Models (include error field for operational needs)
# ============================================================================


class DocumentResponse(BaseModel):
    """Full document response including error field for admin/operational use."""

    id: str
    filename: str
    status: str
    error: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DeleteResponse(BaseModel):
    status: str
    document_id: str


class IngestionJobResponse(BaseModel):
    """Full ingestion job response including error field for admin/operational use."""

    id: str
    document_id: str
    status: str
    chunk_count: int
    error: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


MAX_FILE_SIZE = 50 * 1024 * 1024


async def process_document_background(
    document_id: str,
    content: str,
    filename: str,
    unified_indexing_service: UnifiedIndexingService,
):
    """Background task to process uploaded document."""
    from app.config.settings import get_settings

    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with get_session(session_maker) as session:
        try:
            doc_repo = PostgresDocumentRepository(session)
            # Update status to processing
            await update_document_status(doc_repo, document_id, "processing", None)
            await session.commit()

            # Use UnifiedIndexingService for indexing
            source = ContentSource(
                source_id=document_id,
                source_type="document",
                content=content,
                metadata=ContentMetadata(filename=filename),
            )
            chunk_count = await unified_indexing_service.index_source(source)

            # Update status to completed
            await update_document_status(doc_repo, document_id, "completed", None, chunk_count)
            await session.commit()

            logger.info(f"Document {document_id} indexed: {chunk_count} chunks")
        except Exception as e:
            logger.exception(f"Failed to process document {document_id}: {e}")
            doc_repo = PostgresDocumentRepository(session)
            await update_document_status(doc_repo, document_id, "failed", str(e))
            await session.commit()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_admin: CurrentAdmin,
    _: RateLimitDep,
    unified_indexing_service: UnifiedIndexingServiceDep,
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    doc_repo = PostgresDocumentRepository(session)
    document = await create_document(doc_repo, file.filename, current_admin["id"])
    await session.commit()

    try:
        text_content = content.decode("utf-8")
        background_tasks.add_task(
            process_document_background,
            document.id,
            text_content,
            file.filename,
            unified_indexing_service,
        )
    except UnicodeDecodeError:
        pass

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )


@router.get("", response_model=PublicDocumentListResponse)
async def list_documents(
    session: SessionDep,
    _: OptionalUser,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> PublicDocumentListResponse:
    """List all documents with public field whitelist.

    This endpoint is accessible to guests (unauthenticated) and authenticated users.
    Only whitelisted public fields are exposed in the response.
    """
    doc_repo = PostgresDocumentRepository(session)
    documents = await get_all_documents(doc_repo, limit=limit, offset=offset)
    total = await count_all_documents(doc_repo)
    return PublicDocumentListResponse(
        documents=[
            PublicDocumentResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{doc_id}", response_model=PublicDocumentResponse)
async def get_document(session: SessionDep, doc_id: str, _: OptionalUser) -> PublicDocumentResponse:
    """Get a single document with public field whitelist.

    This endpoint is accessible to guests (unauthenticated) and authenticated users.
    Only whitelisted public fields are exposed in the response.
    """
    doc_repo = PostgresDocumentRepository(session)
    document = await get_document_by_id_public(doc_repo, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return PublicDocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.get("/{doc_id}/status", response_model=PublicIngestionJobResponse)
async def get_document_status(
    session: SessionDep, doc_id: str, _: OptionalUser
) -> PublicIngestionJobResponse:
    """Get document ingestion status with public field whitelist.

    This endpoint is accessible to guests (unauthenticated) and authenticated users.
    Only whitelisted public fields are exposed in the response.
    """
    doc_repo = PostgresDocumentRepository(session)
    document = await get_document_by_id_public(doc_repo, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ingestion_job = await get_ingestion_job_by_document(doc_repo, doc_id)
    if ingestion_job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return PublicIngestionJobResponse(
        id=ingestion_job.id,
        document_id=ingestion_job.document_id,
        status=ingestion_job.status,
        chunk_count=ingestion_job.chunk_count,
        created_at=ingestion_job.created_at.isoformat(),
        updated_at=ingestion_job.updated_at.isoformat(),
    )


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document_endpoint(
    session: SessionDep,
    doc_id: str,
    current_admin: CurrentAdmin,
    unified_indexing_service: UnifiedIndexingServiceDep,
) -> DeleteResponse:
    doc_repo = PostgresDocumentRepository(session)
    success = await delete_document_by_id(doc_repo, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Elasticsearch
    try:
        await unified_indexing_service.delete_source(doc_id, source_type="document")
    except Exception as e:
        logger.error(f"Failed to delete document chunks from ES {doc_id}: {e}")

    return DeleteResponse(status="deleted", document_id=doc_id)
