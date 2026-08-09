"""Admin API endpoints for exhibit management."""

import uuid

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from loguru import logger
from pydantic import BaseModel, field_validator

from app.api._shared_responses import ExhibitDeleteResponse as DeleteResponse
from app.api.deps import CurrentAdminUser, SessionDep
from app.application.content_source import ContentMetadata, ContentSource
from app.application.exhibit_images import (
    ExhibitImageError,
    ExhibitImagePathError,
    ExhibitImageStorage,
    ExhibitImageTooLargeError,
    ExhibitImageTypeError,
    normalize_external_image_url,
    public_exhibit_image_url,
)
from app.application.exhibit_service import ExhibitService
from app.application.hall_normalizer import normalize_hall
from app.application.unified_indexing_service import UnifiedIndexingService
from app.config.settings import get_settings
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
    document_id: str | None = None
    image_url: str | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return normalize_external_image_url(value)


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
    document_id: str | None
    is_active: bool
    created_at: str
    updated_at: str
    image_url: str | None

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
    image_url: str | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return normalize_external_image_url(value)


class ExhibitImageResponse(BaseModel):
    image_url: str | None


class ReindexResponse(BaseModel):
    status: str
    total: int
    indexed: int
    failed: int


def get_exhibit_service(session: SessionDep) -> ExhibitService:
    """Get exhibit service instance."""
    repository = PostgresExhibitRepository(session)
    return ExhibitService(repository)


def get_exhibit_image_storage() -> ExhibitImageStorage:
    settings = get_settings()
    return ExhibitImageStorage(
        settings.EXHIBIT_IMAGE_DIR,
        max_bytes=settings.EXHIBIT_IMAGE_MAX_BYTES,
        max_pixels=settings.EXHIBIT_IMAGE_MAX_PIXELS,
    )


def _normalize_response_hall(value: str | None) -> str:
    return normalize_hall(value) or value or ""


def _to_exhibit_response(exhibit) -> ExhibitResponse:
    return ExhibitResponse(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        location_x=exhibit.location.x,
        location_y=exhibit.location.y,
        floor=exhibit.location.floor,
        hall=_normalize_response_hall(exhibit.hall),
        category=exhibit.category,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        document_id=exhibit.document_id,
        is_active=exhibit.is_active,
        created_at=exhibit.created_at.isoformat(),
        updated_at=exhibit.updated_at.isoformat(),
        image_url=public_exhibit_image_url(exhibit),
    )


def _validate_exhibit_uuid(exhibit_id: str) -> None:
    try:
        uuid.UUID(exhibit_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid exhibit ID format: {exhibit_id}",
        ) from None


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
        hall=_normalize_response_hall(request.hall),
        category=request.category,
        era=request.era,
        importance=request.importance,
        estimated_visit_time=request.estimated_visit_time,
        document_id=request.document_id,
        image_url=request.image_url,
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
                hall=_normalize_response_hall(exhibit.hall),
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

    return _to_exhibit_response(exhibit)


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
        hall=_normalize_response_hall(hall) if hall else None,
    )

    # Get total count for pagination
    all_exhibits = await service.list_exhibits(
        skip=0,
        limit=10000,
        category=category,
        hall=_normalize_response_hall(hall) if hall else None,
    )
    total = len(all_exhibits)

    return ExhibitListResponse(
        exhibits=[_to_exhibit_response(e) for e in exhibits],
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
    _validate_exhibit_uuid(exhibit_id)

    service = get_exhibit_service(session)

    try:
        update_values = dict(
            exhibit_id=exhibit_id,
            name=request.name,
            description=request.description,
            location_x=request.location_x,
            location_y=request.location_y,
            floor=request.floor,
            hall=_normalize_response_hall(request.hall) if request.hall is not None else None,
            category=request.category,
            era=request.era,
            importance=request.importance,
            estimated_visit_time=request.estimated_visit_time,
            document_id=request.document_id,
            is_active=request.is_active,
        )
        if "image_url" in request.model_fields_set:
            update_values["image_url"] = request.image_url
        exhibit = await service.update_exhibit(**update_values)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None

    # Changing only the display image has no effect on searchable exhibit
    # content, so avoid an unnecessary embedding/index rebuild.
    if not (request.model_fields_set - {"image_url"}):
        return _to_exhibit_response(exhibit)

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
                    hall=_normalize_response_hall(exhibit.hall),
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

    return _to_exhibit_response(exhibit)


@router.post(
    "/{exhibit_id}/image",
    response_model=ExhibitImageResponse,
    summary="Upload exhibit image (admin)",
)
async def upload_exhibit_image(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
    file: UploadFile = File(...),  # noqa: B008
) -> ExhibitImageResponse:
    """Replace an uploaded image after signature and decode-bound validation."""
    _validate_exhibit_uuid(exhibit_id)
    service = get_exhibit_service(session)
    exhibit = await service.get_exhibit(exhibit_id)
    if exhibit is None:
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    storage = get_exhibit_image_storage()
    old_path = exhibit.image_path
    new_path: str | None = None
    stored_committed = False
    try:
        new_path = await storage.store(exhibit_id, file)
        exhibit = await service.update_exhibit_image(exhibit_id, image_path=new_path)
        await session.commit()
        stored_committed = True
    except ExhibitImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from None
    except ExhibitImageTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from None
    except ExhibitImagePathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None
    except OSError as exc:
        await session.rollback()
        logger.exception("Failed to persist exhibit image for {}", exhibit_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store exhibit image",
        ) from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await file.close()
        if new_path and not stored_committed:
            try:
                await storage.delete(new_path)
            except (ExhibitImageError, OSError):
                logger.warning("Failed to clean unreferenced exhibit image for {}", exhibit_id)

    if old_path and old_path != new_path:
        try:
            await storage.delete(old_path)
        except (ExhibitImageError, OSError):
            logger.warning("Failed to remove replaced exhibit image for {}", exhibit_id)
    return ExhibitImageResponse(image_url=public_exhibit_image_url(exhibit))


@router.delete(
    "/{exhibit_id}/image",
    response_model=ExhibitImageResponse,
    summary="Delete exhibit image (admin)",
)
async def delete_exhibit_image(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
) -> ExhibitImageResponse:
    """Clear local and external image references, then remove the local file."""
    _validate_exhibit_uuid(exhibit_id)
    service = get_exhibit_service(session)
    exhibit = await service.get_exhibit(exhibit_id)
    if exhibit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    old_path = exhibit.image_path
    try:
        await service.update_exhibit_image(
            exhibit_id,
            image_url=None,
            image_path=None,
        )
        await session.commit()
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        ) from None

    if old_path:
        try:
            await get_exhibit_image_storage().delete(old_path)
        except (ExhibitImageError, OSError):
            logger.warning("Failed to remove deleted exhibit image for {}", exhibit_id)
    return ExhibitImageResponse(image_url=None)


@router.delete("/{exhibit_id}", response_model=DeleteResponse, summary="Delete exhibit (admin)")
async def delete_exhibit(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> DeleteResponse:
    """Delete an exhibit (admin only)."""
    service = get_exhibit_service(session)
    exhibit = await service.get_exhibit(exhibit_id)
    if exhibit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )
    old_image_path = exhibit.image_path

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

    # Commit the row deletion before removing its file. A failed database
    # commit therefore cannot leave a live row pointing at a missing image.
    await session.commit()

    if old_image_path:
        try:
            await get_exhibit_image_storage().delete(old_image_path)
        except (ExhibitImageError, OSError):
            logger.warning("Failed to remove image for deleted exhibit {}", exhibit_id)

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
                    hall=_normalize_response_hall(exhibit.hall),
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
