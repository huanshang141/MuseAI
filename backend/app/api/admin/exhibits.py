"""Admin API endpoints for exhibit management."""

import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status
from loguru import logger
from pydantic import BaseModel

from app.api._shared_responses import ExhibitDeleteResponse as DeleteResponse
from app.api.deps import CurrentAdminUser, SessionDep
from app.application.content_source import ContentMetadata, ContentSource
from app.application.exhibit_service import ExhibitService
from app.application.unified_indexing_service import UnifiedIndexingService
from app.domain.exceptions import EntityNotFoundError
from app.infra.postgres.adapters import PostgresExhibitRepository

router = APIRouter(prefix="/admin/exhibits", tags=["admin-exhibits"])


class CreateExhibitRequest(BaseModel):
    name: str
    description: str
    location_x: float
    location_y: float
    floor: int = 1
    hall: str
    category: str
    era: str
    importance: int
    estimated_visit_time: int
    document_id: str


class ExhibitResponse(BaseModel):
    id: str
    name: str
    description: str
    location_x: float
    location_y: float
    floor: int
    hall: str
    category: str
    era: str
    importance: int
    estimated_visit_time: int
    document_id: str
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ExhibitListResponse(BaseModel):
    exhibits: list[ExhibitResponse]
    total: int
    skip: int
    limit: int


class UpdateExhibitRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    location_x: float | None = None
    location_y: float | None = None
    floor: int | None = None
    hall: str | None = None
    category: str | None = None
    era: str | None = None
    importance: int | None = None
    estimated_visit_time: int | None = None
    document_id: str | None = None
    is_active: bool | None = None


class ReindexResponse(BaseModel):
    status: str
    total: int
    indexed: int
    failed: int


def get_exhibit_service(session: SessionDep) -> ExhibitService:
    """Get exhibit service instance."""
    repository = PostgresExhibitRepository(session)
    return ExhibitService(repository)


@router.post("", response_model=ExhibitResponse, status_code=status.HTTP_201_CREATED, summary="Create exhibit (admin)")
async def create_exhibit(
    session: SessionDep,
    request: CreateExhibitRequest,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ExhibitResponse:
    """Create a new exhibit (admin only)."""
    service = get_exhibit_service(session)

    exhibit = await service.create_exhibit(
        name=request.name,
        description=request.description,
        location_x=request.location_x,
        location_y=request.location_y,
        floor=request.floor,
        hall=request.hall,
        category=request.category,
        era=request.era,
        importance=request.importance,
        estimated_visit_time=request.estimated_visit_time,
        document_id=request.document_id,
    )

    # Index the exhibit to Elasticsearch
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        indexing_service = UnifiedIndexingService(es_client, embeddings)

        # Create ContentSource for the exhibit
        content_source = ContentSource(
            source_id=exhibit.id.value,
            source_type="exhibit",
            content=exhibit.description,
            metadata=ContentMetadata(
                name=exhibit.name,
                category=exhibit.category,
                hall=exhibit.hall,
                floor=exhibit.location.floor,
                era=exhibit.era,
                importance=exhibit.importance,
                location_x=exhibit.location.x,
                location_y=exhibit.location.y,
            ),
        )
        await indexing_service.index_source(content_source)
    except Exception as e:
        logger.error(f"Failed to index exhibit {exhibit.id.value}: {e}")

    return ExhibitResponse(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        location_x=exhibit.location.x,
        location_y=exhibit.location.y,
        floor=exhibit.location.floor,
        hall=exhibit.hall,
        category=exhibit.category,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        document_id=exhibit.document_id,
        is_active=exhibit.is_active,
        created_at=exhibit.created_at.isoformat(),
        updated_at=exhibit.updated_at.isoformat(),
    )


@router.get("", response_model=ExhibitListResponse, summary="List exhibits (admin)")
async def list_exhibits(
    session: SessionDep,
    current_user: CurrentAdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: str | None = None,
    hall: str | None = None,
) -> ExhibitListResponse:
    """List all exhibits with optional filtering (admin only)."""
    service = get_exhibit_service(session)

    exhibits = await service.list_exhibits(
        skip=skip,
        limit=limit,
        category=category,
        hall=hall,
    )

    # Get total count for pagination
    all_exhibits = await service.list_exhibits(skip=0, limit=10000, category=category, hall=hall)
    total = len(all_exhibits)

    return ExhibitListResponse(
        exhibits=[
            ExhibitResponse(
                id=e.id.value,
                name=e.name,
                description=e.description,
                location_x=e.location.x,
                location_y=e.location.y,
                floor=e.location.floor,
                hall=e.hall,
                category=e.category,
                era=e.era,
                importance=e.importance,
                estimated_visit_time=e.estimated_visit_time,
                document_id=e.document_id,
                is_active=e.is_active,
                created_at=e.created_at.isoformat(),
                updated_at=e.updated_at.isoformat(),
            )
            for e in exhibits
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.put("/{exhibit_id}", response_model=ExhibitResponse, summary="Update exhibit (admin)")
async def update_exhibit(
    session: SessionDep,
    exhibit_id: str,
    request: UpdateExhibitRequest,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ExhibitResponse:
    """Update an exhibit (admin only)."""
    # Validate UUID format
    try:
        uuid.UUID(exhibit_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid exhibit ID format: {exhibit_id}",
        ) from None

    service = get_exhibit_service(session)

    try:
        exhibit = await service.update_exhibit(
            exhibit_id=exhibit_id,
            name=request.name,
            description=request.description,
            location_x=request.location_x,
            location_y=request.location_y,
            floor=request.floor,
            hall=request.hall,
            category=request.category,
            era=request.era,
            importance=request.importance,
            estimated_visit_time=request.estimated_visit_time,
            document_id=request.document_id,
            is_active=request.is_active,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None

    # Update Elasticsearch index based on is_active status
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        indexing_service = UnifiedIndexingService(es_client, embeddings)

        if exhibit.is_active:
            # Reindex the exhibit
            content_source = ContentSource(
                source_id=exhibit.id.value,
                source_type="exhibit",
                content=exhibit.description,
                metadata=ContentMetadata(
                    name=exhibit.name,
                    category=exhibit.category,
                    hall=exhibit.hall,
                    floor=exhibit.location.floor,
                    era=exhibit.era,
                    importance=exhibit.importance,
                    location_x=exhibit.location.x,
                    location_y=exhibit.location.y,
                ),
            )
            await indexing_service.index_source(content_source)
        else:
            # Remove from index
            await indexing_service.delete_source(exhibit.id.value, source_type="exhibit")
    except Exception as e:
        logger.error(f"Failed to update exhibit index {exhibit.id.value}: {e}")

    return ExhibitResponse(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        location_x=exhibit.location.x,
        location_y=exhibit.location.y,
        floor=exhibit.location.floor,
        hall=exhibit.hall,
        category=exhibit.category,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        document_id=exhibit.document_id,
        is_active=exhibit.is_active,
        created_at=exhibit.created_at.isoformat(),
        updated_at=exhibit.updated_at.isoformat(),
    )


@router.delete("/{exhibit_id}", response_model=DeleteResponse, summary="Delete exhibit (admin)")
async def delete_exhibit(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> DeleteResponse:
    """Delete an exhibit (admin only)."""
    service = get_exhibit_service(session)

    try:
        success = await service.delete_exhibit(exhibit_id)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    # Remove from Elasticsearch index
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        indexing_service = UnifiedIndexingService(es_client, embeddings)
        await indexing_service.delete_source(exhibit_id, source_type="exhibit")
    except Exception as e:
        logger.error(f"Failed to delete exhibit index {exhibit_id}: {e}")

    return DeleteResponse(status="deleted", exhibit_id=exhibit_id)


@router.post("/reindex", response_model=ReindexResponse, summary="Reindex all exhibits")
async def reindex_all_exhibits(
    session: SessionDep,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ReindexResponse:
    """Reindex all active exhibits to Elasticsearch (admin only)."""
    # Get all active exhibits
    service = get_exhibit_service(session)
    exhibits = await service.list_all_active()

    # Get es_client and embeddings from app.state
    if not hasattr(http_request.app.state, "es_client"):
        raise RuntimeError("Elasticsearch client not initialized. App not started?")
    if not hasattr(http_request.app.state, "embeddings"):
        raise RuntimeError("Embeddings not initialized. App not started?")

    es_client = http_request.app.state.es_client
    embeddings = http_request.app.state.embeddings

    # Use UnifiedIndexingService to reindex
    indexing_service = UnifiedIndexingService(es_client, embeddings)

    total = len(exhibits)
    indexed = 0
    failed = 0

    for exhibit in exhibits:
        try:
            content_source = ContentSource(
                source_id=exhibit.id.value,
                source_type="exhibit",
                content=exhibit.description,
                metadata=ContentMetadata(
                    name=exhibit.name,
                    category=exhibit.category,
                    hall=exhibit.hall,
                    floor=exhibit.location.floor,
                    era=exhibit.era,
                    importance=exhibit.importance,
                    location_x=exhibit.location.x,
                    location_y=exhibit.location.y,
                ),
            )
            await indexing_service.index_source(content_source)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to reindex exhibit {exhibit.id.value}: {e}")
            failed += 1

    return ReindexResponse(
        status="completed",
        total=total,
        indexed=indexed,
        failed=failed,
    )
