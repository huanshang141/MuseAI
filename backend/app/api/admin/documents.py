"""Admin compatibility endpoints for knowledge base management."""

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentAdmin, RateLimitDep, SessionDep, UnifiedIndexingServiceDep
from app.api.documents import (
    MAX_FILE_SIZE,
    process_document_background,
    stream_to_temp_file,
    validate_upload_content,
    validate_upload_metadata,
)
from app.application.document_service import (
    count_all_documents,
    create_document,
    delete_document_by_id,
    get_all_documents,
    get_document_by_id_public,
    get_ingestion_job_by_document,
)
from app.infra.postgres.adapters.document_repository import PostgresDocumentRepository

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class AdminDocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    error: str | None = None
    created_at: str


class AdminDocumentListResponse(BaseModel):
    documents: list[AdminDocumentResponse]
    total: int
    limit: int
    offset: int


class AdminIngestionJobResponse(BaseModel):
    id: str
    document_id: str
    status: str
    chunk_count: int
    error: str | None
    created_at: str
    updated_at: str


class AdminDocumentDeleteResponse(BaseModel):
    status: str
    document_id: str


@router.get("", response_model=AdminDocumentListResponse, summary="List documents (admin)")
async def list_documents_admin(
    session: SessionDep,
    current_admin: CurrentAdmin,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> AdminDocumentListResponse:
    doc_repo = PostgresDocumentRepository(session)
    documents = await get_all_documents(doc_repo, limit=limit, offset=offset)
    total = await count_all_documents(doc_repo)

    return AdminDocumentListResponse(
        documents=[
            AdminDocumentResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                error=doc.error,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{doc_id}", response_model=AdminDocumentResponse, summary="Get document detail (admin)")
async def get_document_admin(
    session: SessionDep,
    doc_id: str,
    current_admin: CurrentAdmin,
) -> AdminDocumentResponse:
    doc_repo = PostgresDocumentRepository(session)
    document = await get_document_by_id_public(doc_repo, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return AdminDocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )


@router.get("/{doc_id}/status", response_model=AdminIngestionJobResponse, summary="Get document status (admin)")
async def get_document_status_admin(
    session: SessionDep,
    doc_id: str,
    current_admin: CurrentAdmin,
) -> AdminIngestionJobResponse:
    doc_repo = PostgresDocumentRepository(session)
    document = await get_document_by_id_public(doc_repo, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ingestion_job = await get_ingestion_job_by_document(doc_repo, doc_id)
    if ingestion_job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return AdminIngestionJobResponse(
        id=ingestion_job.id,
        document_id=ingestion_job.document_id,
        status=ingestion_job.status,
        chunk_count=ingestion_job.chunk_count,
        error=ingestion_job.error,
        created_at=ingestion_job.created_at.isoformat(),
        updated_at=ingestion_job.updated_at.isoformat(),
    )


@router.post("/upload", response_model=AdminDocumentResponse, summary="Upload document (admin)")
async def upload_document_admin(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_admin: CurrentAdmin,
    _: RateLimitDep,
    unified_indexing_service: UnifiedIndexingServiceDep,
    file: UploadFile = File(...),  # noqa: B008
) -> AdminDocumentResponse:
    validate_upload_metadata(file)

    tmp_path, _ = await stream_to_temp_file(file, MAX_FILE_SIZE)

    try:
        validate_upload_content(tmp_path)
    except HTTPException:
        import os

        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    doc_repo = PostgresDocumentRepository(session)
    document = await create_document(doc_repo, file.filename, current_admin["id"])
    await session.commit()

    background_tasks.add_task(
        process_document_background,
        document.id,
        tmp_path,
        file.filename,
        unified_indexing_service,
    )

    return AdminDocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )


@router.delete("/{doc_id}", response_model=AdminDocumentDeleteResponse, summary="Delete document (admin)")
async def delete_document_admin(
    session: SessionDep,
    doc_id: str,
    current_admin: CurrentAdmin,
    unified_indexing_service: UnifiedIndexingServiceDep,
) -> AdminDocumentDeleteResponse:
    doc_repo = PostgresDocumentRepository(session)
    success = await delete_document_by_id(doc_repo, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        await unified_indexing_service.delete_source(doc_id, source_type="document")
    except Exception:
        # Keep parity with existing behavior: DB delete succeeded regardless of ES status.
        pass

    return AdminDocumentDeleteResponse(status="deleted", document_id=doc_id)
