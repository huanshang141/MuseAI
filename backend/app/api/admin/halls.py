"""Admin API endpoints for hall settings management."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentAdminUser, SessionDep
from app.infra.postgres.models import Hall

router = APIRouter(prefix="/admin/halls", tags=["admin-halls"])


class HallCreateRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    floor: int | None = Field(default=None, ge=1, le=10)
    estimated_duration_minutes: int = Field(default=0, ge=0, le=480)
    display_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class HallUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    floor: int | None = Field(default=None, ge=1, le=10)
    estimated_duration_minutes: int | None = Field(default=None, ge=0, le=480)
    display_order: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None


class HallResponse(BaseModel):
    slug: str
    name: str
    description: str | None
    floor: int | None
    estimated_duration_minutes: int
    display_order: int
    is_active: bool
    created_at: str
    updated_at: str


class HallListResponse(BaseModel):
    halls: list[HallResponse]
    total: int


class HallDeleteResponse(BaseModel):
    status: str
    slug: str


def _to_response(hall: Hall) -> HallResponse:
    return HallResponse(
        slug=hall.slug,
        name=hall.name,
        description=hall.description,
        floor=hall.floor,
        estimated_duration_minutes=hall.estimated_duration_minutes,
        display_order=hall.display_order,
        is_active=hall.is_active,
        created_at=hall.created_at.isoformat(),
        updated_at=hall.updated_at.isoformat(),
    )


def _normalize_slug(slug: str) -> str:
    normalized = slug.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Slug cannot be empty")
    return normalized


@router.get("", response_model=HallListResponse, summary="List halls (admin)")
async def list_halls(
    session: SessionDep,
    current_user: CurrentAdminUser,
    include_inactive: bool = Query(True),
) -> HallListResponse:
    stmt = select(Hall)
    if not include_inactive:
        stmt = stmt.where(Hall.is_active.is_(True))
    stmt = stmt.order_by(Hall.display_order.asc(), Hall.created_at.asc())

    result = await session.execute(stmt)
    halls = list(result.scalars().all())

    return HallListResponse(halls=[_to_response(h) for h in halls], total=len(halls))


@router.post("", response_model=HallResponse, status_code=status.HTTP_201_CREATED, summary="Create hall (admin)")
async def create_hall(
    session: SessionDep,
    request: HallCreateRequest,
    current_user: CurrentAdminUser,
) -> HallResponse:
    slug = _normalize_slug(request.slug)

    existing = await session.get(Hall, slug)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Hall already exists: {slug}")

    hall = Hall(
        slug=slug,
        name=request.name.strip(),
        description=request.description,
        floor=request.floor,
        estimated_duration_minutes=request.estimated_duration_minutes,
        display_order=request.display_order,
        is_active=request.is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(hall)
    await session.commit()
    await session.refresh(hall)

    return _to_response(hall)


@router.put("/{slug}", response_model=HallResponse, summary="Update hall (admin)")
async def update_hall(
    session: SessionDep,
    slug: str,
    request: HallUpdateRequest,
    current_user: CurrentAdminUser,
) -> HallResponse:
    normalized_slug = _normalize_slug(slug)
    hall = await session.get(Hall, normalized_slug)
    if hall is None:
        raise HTTPException(status_code=404, detail=f"Hall not found: {normalized_slug}")

    if request.name is not None:
        hall.name = request.name.strip()
    if request.description is not None:
        hall.description = request.description
    if request.floor is not None:
        hall.floor = request.floor
    if request.estimated_duration_minutes is not None:
        hall.estimated_duration_minutes = request.estimated_duration_minutes
    if request.display_order is not None:
        hall.display_order = request.display_order
    if request.is_active is not None:
        hall.is_active = request.is_active

    hall.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(hall)

    return _to_response(hall)


@router.delete("/{slug}", response_model=HallDeleteResponse, summary="Delete hall (admin)")
async def delete_hall(
    session: SessionDep,
    slug: str,
    current_user: CurrentAdminUser,
) -> HallDeleteResponse:
    normalized_slug = _normalize_slug(slug)
    hall = await session.get(Hall, normalized_slug)
    if hall is None:
        raise HTTPException(status_code=404, detail=f"Hall not found: {normalized_slug}")

    await session.delete(hall)
    await session.commit()

    return HallDeleteResponse(status="deleted", slug=normalized_slug)
