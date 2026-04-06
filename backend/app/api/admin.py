# backend/app/api/admin.py
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentAdminUser, SessionDep
from app.application.exhibit_service import ExhibitService
from app.domain.exceptions import EntityNotFoundError
from app.infra.postgres.repositories import PostgresExhibitRepository

router = APIRouter(prefix="/admin", tags=["admin"])


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


class DeleteResponse(BaseModel):
    status: str
    exhibit_id: str


def get_exhibit_service(session: SessionDep) -> ExhibitService:
    """Get exhibit service instance."""
    repository = PostgresExhibitRepository(session)
    return ExhibitService(repository)


@router.post("/exhibits", response_model=ExhibitResponse, status_code=status.HTTP_201_CREATED)
async def create_exhibit(
    session: SessionDep,
    request: CreateExhibitRequest,
    current_user: CurrentAdminUser,
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


@router.get("/exhibits", response_model=ExhibitListResponse)
async def list_exhibits(
    session: SessionDep,
    current_user: CurrentAdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    hall: Optional[str] = None,
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


@router.delete("/exhibits/{exhibit_id}", response_model=DeleteResponse)
async def delete_exhibit(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
) -> DeleteResponse:
    """Delete an exhibit (admin only)."""
    service = get_exhibit_service(session)

    try:
        success = await service.delete_exhibit(exhibit_id)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    return DeleteResponse(status="deleted", exhibit_id=exhibit_id)
