# backend/app/api/curator.py
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, RateLimitDep, SessionDep
from app.application.curator_service import CuratorService
from app.application.exhibit_service import ExhibitService
from app.application.profile_service import ProfileService
from app.domain.exceptions import EntityNotFoundError
from app.infra.langchain.curator_agent import CuratorAgent
from app.infra.postgres.repositories import PostgresExhibitRepository, PostgresVisitorProfileRepository

router = APIRouter(prefix="/curator", tags=["curator"])


class PlanTourRequest(BaseModel):
    available_time: int
    interests: Optional[List[str]] = None


class PlanTourResponse(BaseModel):
    user_id: str
    available_time: int
    interests: List[str]
    visited_exhibit_ids: List[str]
    plan: str
    session_id: str


class NarrativeRequest(BaseModel):
    exhibit_id: str


class NarrativeResponse(BaseModel):
    user_id: str
    exhibit_id: str
    exhibit_name: str
    narrative: str
    knowledge_level: str
    narrative_preference: str
    session_id: str


class ReflectionRequest(BaseModel):
    exhibit_id: str


class ReflectionResponse(BaseModel):
    user_id: str
    exhibit_id: str
    exhibit_name: str
    reflection_prompts: str
    knowledge_level: str
    reflection_depth: str
    session_id: str


def get_curator_service(session: SessionDep) -> CuratorService:
    """Get curator service instance with all dependencies."""
    # Create repositories
    profile_repository = PostgresVisitorProfileRepository(session)
    exhibit_repository = PostgresExhibitRepository(session)

    # Create services
    profile_service = ProfileService(profile_repository)
    exhibit_service = ExhibitService(exhibit_repository)

    # Create curator agent (will use app state if available)
    curator_agent = CuratorAgent()

    return CuratorService(
        curator_agent=curator_agent,
        profile_service=profile_service,
        exhibit_service=exhibit_service,
    )


@router.post("/plan-tour", response_model=PlanTourResponse)
async def plan_tour(
    session: SessionDep,
    request: PlanTourRequest,
    current_user: CurrentUser,
    _: RateLimitDep,
) -> PlanTourResponse:
    """Plan a museum tour based on available time and interests."""
    service = get_curator_service(session)

    result = await service.plan_tour(
        user_id=current_user["id"],
        available_time=request.available_time,
        interests=request.interests,
    )

    return PlanTourResponse(**result)


@router.post("/narrative", response_model=NarrativeResponse)
async def generate_narrative(
    session: SessionDep,
    request: NarrativeRequest,
    current_user: CurrentUser,
    _: RateLimitDep,
) -> NarrativeResponse:
    """Generate narrative content for an exhibit."""
    service = get_curator_service(session)

    try:
        result = await service.generate_narrative(
            user_id=current_user["id"],
            exhibit_id=request.exhibit_id,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return NarrativeResponse(**result)


@router.post("/reflection", response_model=ReflectionResponse)
async def get_reflection_prompts(
    session: SessionDep,
    request: ReflectionRequest,
    current_user: CurrentUser,
    _: RateLimitDep,
) -> ReflectionResponse:
    """Get reflection prompts for an exhibit."""
    service = get_curator_service(session)

    try:
        result = await service.get_reflection_prompts(
            user_id=current_user["id"],
            exhibit_id=request.exhibit_id,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return ReflectionResponse(**result)
