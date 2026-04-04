from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.postgres.database import get_session_maker, get_session
from app.application.document_service import (
    create_document,
    get_documents_by_user,
    get_document_by_id,
    get_ingestion_job_by_document,
    delete_document,
)
from app.config.settings import get_settings

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


async def get_db_session():
    settings = get_settings()
    session_maker = get_session_maker(settings.DATABASE_URL)
    async with get_session(session_maker) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(session: SessionDep, file: UploadFile = File(...)) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    document = await create_document(session, file.filename, file_size)

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(session: SessionDep) -> DocumentListResponse:
    documents = await get_documents_by_user(session)
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
async def get_document(session: SessionDep, doc_id: str) -> DocumentResponse:
    document = await get_document_by_id(session, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.get("/{doc_id}/status", response_model=IngestionJobResponse)
async def get_document_status(session: SessionDep, doc_id: str) -> IngestionJobResponse:
    document = await get_document_by_id(session, doc_id)
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
async def delete_document_endpoint(session: SessionDep, doc_id: str) -> DeleteResponse:
    success = await delete_document(session, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return DeleteResponse(status="deleted", document_id=doc_id)
