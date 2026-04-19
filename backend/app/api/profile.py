# backend/app/api/profile.py

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, RateLimitDep, SessionDep
from app.application.error_handling import sanitize_error_message
from app.application.profile_service import ProfileService
from app.domain.exceptions import EntityNotFoundError
from app.infra.postgres.adapters import PostgresVisitorProfileRepository

router = APIRouter(prefix="/profile", tags=["profile"])


class UpdateProfileRequest(BaseModel):
    interests: list[str] | None = None
    knowledge_level: str | None = None
    narrative_preference: str | None = None
    reflection_depth: str | None = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    interests: list[str]
    knowledge_level: str
    narrative_preference: str
    reflection_depth: str
    visited_exhibit_ids: list[str]
    feedback_history: list[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


def get_profile_service(session: SessionDep) -> ProfileService:
    """Get profile service instance."""
    repository = PostgresVisitorProfileRepository(session)
    return ProfileService(repository)


@router.get("", response_model=ProfileResponse, summary="Get visitor profile")
async def get_profile(
    session: SessionDep,
    current_user: CurrentUser,
) -> ProfileResponse:
    """Get current user's profile."""
    service = get_profile_service(session)

    # Get or create profile
    profile = await service.get_or_create_profile(current_user["id"])

    return ProfileResponse(
        id=profile.id.value,
        user_id=profile.user_id.value,
        interests=profile.interests,
        knowledge_level=profile.knowledge_level,
        narrative_preference=profile.narrative_preference,
        reflection_depth=profile.reflection_depth,
        visited_exhibit_ids=[eid.value for eid in profile.visited_exhibit_ids],
        feedback_history=profile.feedback_history,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )


@router.put("", response_model=ProfileResponse, summary="Update visitor profile")
async def update_profile(
    session: SessionDep,
    request: UpdateProfileRequest,
    current_user: CurrentUser,
    _: RateLimitDep,
) -> ProfileResponse:
    """Update current user's profile."""
    service = get_profile_service(session)

    try:
        profile = await service.update_profile(
            user_id=current_user["id"],
            interests=request.interests,
            knowledge_level=request.knowledge_level,
            narrative_preference=request.narrative_preference,
            reflection_depth=request.reflection_depth,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=sanitize_error_message(e),
        ) from None

    return ProfileResponse(
        id=profile.id.value,
        user_id=profile.user_id.value,
        interests=profile.interests,
        knowledge_level=profile.knowledge_level,
        narrative_preference=profile.narrative_preference,
        reflection_depth=profile.reflection_depth,
        visited_exhibit_ids=[eid.value for eid in profile.visited_exhibit_ids],
        feedback_history=profile.feedback_history,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )
