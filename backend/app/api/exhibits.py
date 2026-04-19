# backend/app/api/exhibits.py
"""Public exhibits API - no authentication required for museum visitors."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.application.exhibit_service import ExhibitService
from app.infra.postgres.adapters import PostgresExhibitRepository

router = APIRouter(prefix="/exhibits", tags=["exhibits"])


# ============================================================================
# Response Models
# ============================================================================


class ExhibitListItem(BaseModel):
    """Simplified exhibit info for list views."""

    id: str
    name: str
    category: str
    hall: str
    floor: int
    era: str
    importance: int
    estimated_visit_time: int

    model_config = {"from_attributes": True}


class ExhibitDetail(BaseModel):
    """Detailed exhibit information."""

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

    model_config = {"from_attributes": True}


class ExhibitListResponse(BaseModel):
    """Paginated list of exhibits."""

    exhibits: list[ExhibitListItem]
    total: int
    skip: int
    limit: int


class CategoryStats(BaseModel):
    """Statistics for a category."""

    category: str
    count: int


class HallStats(BaseModel):
    """Statistics for a hall."""

    hall: str
    floor: int
    count: int


class ExhibitStatsResponse(BaseModel):
    """Overall exhibit statistics."""

    total_exhibits: int
    categories: list[CategoryStats]
    halls: list[HallStats]


# ============================================================================
# Dependencies
# ============================================================================


def get_exhibit_service(session: SessionDep) -> ExhibitService:
    """Get exhibit service instance."""
    repository = PostgresExhibitRepository(session)
    return ExhibitService(repository)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=ExhibitListResponse, summary="List exhibits (public)")
async def list_exhibits(
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    category: str | None = Query(None, description="Filter by category"),
    hall: str | None = Query(None, description="Filter by hall"),
    floor: int | None = Query(None, ge=1, description="Filter by floor"),
    search: str | None = Query(None, description="Search in name and description"),
) -> ExhibitListResponse:
    """List exhibits with pagination and filtering.

    This is a public endpoint - no authentication required.
    Only returns active exhibits.
    """
    service = get_exhibit_service(session)

    if search:
        exhibits = await service.search_exhibits(
            query=search,
            skip=skip,
            limit=limit,
            category=category,
            hall=hall,
            floor=floor,
        )
        # Get total count for search results
        all_exhibits = await service.search_exhibits(
            query=search,
            skip=0,
            limit=10000,
            category=category,
            hall=hall,
            floor=floor,
        )
        total = len(all_exhibits)
    else:
        exhibits = await service.list_exhibits(
            skip=skip,
            limit=limit,
            category=category,
            hall=hall,
            floor=floor,
        )
        # Get total count for pagination
        all_exhibits = await service.list_exhibits(skip=0, limit=10000, category=category, hall=hall, floor=floor)
        total = len(all_exhibits)

    return ExhibitListResponse(
        exhibits=[
            ExhibitListItem(
                id=e.id.value,
                name=e.name,
                category=e.category,
                hall=e.hall,
                floor=e.location.floor,
                era=e.era,
                importance=e.importance,
                estimated_visit_time=e.estimated_visit_time,
            )
            for e in exhibits
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=ExhibitStatsResponse, summary="Get exhibit statistics")
async def get_exhibit_stats(
    session: SessionDep,
) -> ExhibitStatsResponse:
    """Get exhibit statistics.

    Returns counts by category and hall.
    This is a public endpoint - no authentication required.
    """
    service = get_exhibit_service(session)

    all_exhibits = await service.list_all_active()

    # Calculate category stats
    category_counts: dict[str, int] = {}
    for e in all_exhibits:
        category_counts[e.category] = category_counts.get(e.category, 0) + 1

    # Calculate hall stats
    hall_counts: dict[tuple[str, int], int] = {}
    for e in all_exhibits:
        key = (e.hall, e.location.floor)
        hall_counts[key] = hall_counts.get(key, 0) + 1

    return ExhibitStatsResponse(
        total_exhibits=len(all_exhibits),
        categories=[
            CategoryStats(category=cat, count=count)
            for cat, count in sorted(category_counts.items())
        ],
        halls=[
            HallStats(hall=hall, floor=floor, count=count)
            for (hall, floor), count in sorted(hall_counts.items())
        ],
    )


@router.get("/categories/list", response_model=list[str], summary="List exhibit categories")
async def list_categories(
    session: SessionDep,
) -> list[str]:
    """Get all available exhibit categories.

    This is a public endpoint - no authentication required.
    """
    service = get_exhibit_service(session)
    return await service.get_all_categories()


@router.get("/halls/list", response_model=list[str], summary="List exhibit halls")
async def list_halls(
    session: SessionDep,
) -> list[str]:
    """Get all available exhibit halls.

    This is a public endpoint - no authentication required.
    """
    service = get_exhibit_service(session)
    return await service.get_all_halls()


@router.get("/{exhibit_id}", response_model=ExhibitDetail, summary="Get exhibit detail")
async def get_exhibit(
    session: SessionDep,
    exhibit_id: str,
) -> ExhibitDetail:
    """Get detailed information about a single exhibit.

    This is a public endpoint - no authentication required.
    Only returns active exhibits.
    """
    # Validate UUID format
    try:
        UUID(exhibit_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid exhibit ID format: {exhibit_id}",
        ) from None

    service = get_exhibit_service(session)

    exhibit = await service.get_exhibit(exhibit_id)

    if exhibit is None or not exhibit.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )

    return ExhibitDetail(
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
    )
