import sys
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel

from app.api.deps import CurrentAdmin, OptionalUser, RateLimitDep, SessionDep
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
from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import create_embeddings
from app.infra.postgres.database import get_session, get_session_maker

router = APIRouter(prefix="/documents", tags=["documents"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


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


def _get_app_state_attr(attr_name: str) -> Any:
    """Get attribute from app.state if available, without late import."""
    main_module = sys.modules.get("app.main")
    if main_module and hasattr(main_module, "app"):
        app = main_module.app
        if hasattr(app.state, attr_name):
            return getattr(app.state, attr_name)
    return None


# Dependency functions - check app.state first for mocks/singletons
def get_unified_indexing_service() -> UnifiedIndexingService:
    """Get unified indexing service from app.state or create fallback."""
    # Check app.state first (for production and mocked tests)
    service = _get_app_state_attr("unified_indexing_service")
    if service is not None:
        return service

    # Fallback: create from settings (used in standalone mode)
    settings = get_settings()
    es_client = ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )
    embeddings = create_embeddings(settings)
    return UnifiedIndexingService(es_client=es_client, embeddings=embeddings)


def get_es_client() -> ElasticsearchClient:
    """Get ES client from app.state or create fallback."""
    client = _get_app_state_attr("es_client")
    if client is not None:
        return client

    settings = get_settings()
    return ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )


def get_embeddings() -> Any:
    """Get embeddings from app.state or create fallback."""
    emb = _get_app_state_attr("embeddings")
    if emb is not None:
        return emb

    settings = get_settings()
    return create_embeddings(settings)


async def process_document_background(
    document_id: str,
    content: str,
    filename: str,
    unified_indexing_service: UnifiedIndexingService,
):
    """Background task to process uploaded document."""
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with get_session(session_maker) as session:
        try:
            # Update status to processing
            await update_document_status(session, document_id, "processing", None)
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
            await update_document_status(session, document_id, "completed", None, chunk_count)
            await session.commit()

            logger.info(f"Document {document_id} indexed: {chunk_count} chunks")
        except Exception as e:
            logger.exception(f"Failed to process document {document_id}: {e}")
            await update_document_status(session, document_id, "failed", str(e))
            await session.commit()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_admin: CurrentAdmin,
    _: RateLimitDep,
    unified_indexing_service: UnifiedIndexingService = Depends(get_unified_indexing_service),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    document = await create_document(session, file.filename, file_size, current_admin["id"])
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


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: SessionDep,
    _: OptionalUser,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> DocumentListResponse:
    documents = await get_all_documents(session, limit=limit, offset=offset)
    total = await count_all_documents(session)
    return DocumentListResponse(
        documents=[
            DocumentResponse(
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


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(session: SessionDep, doc_id: str, _: OptionalUser) -> DocumentResponse:
    document = await get_document_by_id_public(session, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error=document.error,
        created_at=document.created_at.isoformat(),
    )


@router.get("/{doc_id}/status", response_model=IngestionJobResponse)
async def get_document_status(session: SessionDep, doc_id: str, _: OptionalUser) -> IngestionJobResponse:
    document = await get_document_by_id_public(session, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ingestion_job = await get_ingestion_job_by_document(session, doc_id)
    if ingestion_job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return IngestionJobResponse(
        id=ingestion_job.id,
        document_id=ingestion_job.document_id,
        status=ingestion_job.status,
        chunk_count=ingestion_job.chunk_count,
        error=ingestion_job.error,
        created_at=ingestion_job.created_at.isoformat(),
        updated_at=ingestion_job.updated_at.isoformat(),
    )


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document_endpoint(
    session: SessionDep,
    doc_id: str,
    current_admin: CurrentAdmin,
) -> DeleteResponse:
    success = await delete_document_by_id(session, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Elasticsearch
    try:
        indexing_service = get_unified_indexing_service()
        await indexing_service.delete_source(doc_id, source_type="document")
    except Exception as e:
        logger.error(f"Failed to delete document chunks from ES {doc_id}: {e}")

    return DeleteResponse(status="deleted", document_id=doc_id)
