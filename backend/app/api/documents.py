import os
import tempfile

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel

from app.api.deps import CurrentAdmin, OptionalUser, RateLimitDep, SessionDep, UnifiedIndexingServiceDep
from app.application.content_source import ContentMetadata, ContentSource
from app.application.document_service import (
    SANITIZED_ERROR_MESSAGE,
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


class PublicDocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class PublicDocumentListResponse(BaseModel):
    documents: list[PublicDocumentResponse]
    total: int
    limit: int
    offset: int


class PublicIngestionJobResponse(BaseModel):
    id: str
    document_id: str
    status: str
    chunk_count: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
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
    id: str
    document_id: str
    status: str
    chunk_count: int
    error: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 64 * 1024

ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
ALLOWED_CONTENT_TYPES = frozenset({
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",
})
MAGIC_SNIFF_BYTES = 8192


def validate_upload_metadata(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=415,
            detail=f"File extension not allowed. Accepted: {sorted(ALLOWED_EXTENSIONS)}",
        )

    ct = (file.content_type or "").lower()
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Content-type not allowed: {ct}",
        )


def validate_upload_content(temp_path: str) -> None:
    with open(temp_path, "rb") as f:
        head = f.read(MAGIC_SNIFF_BYTES)

    if b"\x00" in head:
        raise HTTPException(
            status_code=415,
            detail="File content appears binary (null bytes detected)",
        )

    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=415,
            detail="File content is not valid UTF-8 text",
        ) from e


async def stream_to_temp_file(file: UploadFile, max_size: int) -> tuple[str, int]:
    """Stream upload file to a temporary file with size validation.

    Reads the file in chunks, accumulating size and writing to disk.
    Raises HTTPException if the file exceeds max_size.

    Returns:
        Tuple of (temp_file_path, total_bytes_written).
    """
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix="museai_upload_")
    os.close(tmp_fd)

    total_size = 0
    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    os.unlink(tmp_path)
                    raise HTTPException(status_code=413, detail="File too large (max 50MB)")
                await f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return tmp_path, total_size


async def process_document_background(
    document_id: str,
    temp_file_path: str,
    filename: str,
    unified_indexing_service: UnifiedIndexingService,
):
    """Background task to process uploaded document from temp file."""
    from app.config.settings import get_settings

    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with get_session(session_maker) as session:
        try:
            doc_repo = PostgresDocumentRepository(session)
            await update_document_status(doc_repo, document_id, "processing", None)
            await session.commit()

            try:
                async with aiofiles.open(temp_file_path, encoding="utf-8") as f:
                    content = await f.read()

                source = ContentSource(
                    source_id=document_id,
                    source_type="document",
                    content=content,
                    metadata=ContentMetadata(filename=filename),
                )
                chunk_count = await unified_indexing_service.index_source(source)

                await update_document_status(doc_repo, document_id, "completed", None, chunk_count)
                await session.commit()

                logger.info(f"Document {document_id} indexed: {chunk_count} chunks")
            except UnicodeDecodeError:
                logger.warning(f"Document {document_id} is not valid UTF-8, marking as failed")
                await update_document_status(doc_repo, document_id, "failed", SANITIZED_ERROR_MESSAGE)
                await session.commit()
        except Exception as e:
            logger.exception(f"Failed to process document {document_id}: {e}")
            try:
                doc_repo = PostgresDocumentRepository(session)
                await update_document_status(doc_repo, document_id, "failed", SANITIZED_ERROR_MESSAGE)
                await session.commit()
            except Exception:
                logger.exception(f"Failed to update document {document_id} status to failed")
        finally:
            try:
                os.unlink(temp_file_path)
            except OSError:
                logger.warning(f"Failed to delete temp file {temp_file_path}")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_admin: CurrentAdmin,
    _: RateLimitDep,
    unified_indexing_service: UnifiedIndexingServiceDep,
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    validate_upload_metadata(file)

    tmp_path, file_size = await stream_to_temp_file(file, MAX_FILE_SIZE)

    try:
        validate_upload_content(tmp_path)
    except HTTPException:
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

    try:
        await unified_indexing_service.delete_source(doc_id, source_type="document")
    except Exception as e:
        logger.error(f"Failed to delete document chunks from ES {doc_id}: {e}")

    return DeleteResponse(status="deleted", document_id=doc_id)
