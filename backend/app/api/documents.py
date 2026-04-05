from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep, RateLimitDep
from app.application.document_service import (
    create_document,
    delete_document,
    get_document_by_id,
    get_documents_by_user,
    get_ingestion_job_by_document,
)
from app.application.ingestion_service import IngestionService
from app.config.settings import get_settings
from app.infra.postgres.database import get_session, get_session_maker

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


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


def get_ingestion_service() -> IngestionService:
    from app.main import get_ingestion_service as _get_ingestion_service

    return _get_ingestion_service()


def get_es_client():
    from app.main import get_es_client as _get_es_client

    return _get_es_client()


def get_embeddings():
    from app.main import get_embeddings as _get_embeddings

    return _get_embeddings()


async def process_document_background(document_id: str, content: str, filename: str):
    from app.main import get_ingestion_service

    ingestion_service = get_ingestion_service()
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)

    async with get_session(session_maker) as session:
        try:
            await ingestion_service.process_document(
                session=session,
                document_id=document_id,
                content=content,
                source=filename,
            )
            await session.commit()
        except Exception as e:
            print(f"Failed to process document {document_id}: {e}")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    _: RateLimitDep,
    file: UploadFile = File(...),
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    document = await create_document(session, file.filename, file_size, current_user["id"])
    await session.commit()

    try:
        text_content = content.decode("utf-8")
        background_tasks.add_task(
            process_document_background,
            document.id,
            text_content,
            file.filename,
        )
    except UnicodeDecodeError:
        pass

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(session: SessionDep, current_user: CurrentUser) -> DocumentListResponse:
    documents = await get_documents_by_user(session, current_user["id"])
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(session: SessionDep, doc_id: str, current_user: CurrentUser) -> DocumentResponse:
    document = await get_document_by_id(session, doc_id, current_user["id"])
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.get("/{doc_id}/status", response_model=IngestionJobResponse)
async def get_document_status(session: SessionDep, doc_id: str, current_user: CurrentUser) -> IngestionJobResponse:
    document = await get_document_by_id(session, doc_id, current_user["id"])
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
async def delete_document_endpoint(session: SessionDep, doc_id: str, current_user: CurrentUser) -> DeleteResponse:
    success = await delete_document(session, doc_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return DeleteResponse(status="deleted", document_id=doc_id)
