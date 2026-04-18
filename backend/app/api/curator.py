# backend/app/api/curator.py
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import OptionalUser, RateLimitDep, SessionDep
from app.application.curator_service import CuratorService
from app.application.error_handling import sanitize_error_message
from app.application.exhibit_service import ExhibitService
from app.application.profile_service import ProfileService
from app.domain.exceptions import EntityNotFoundError
from app.infra.langchain import create_curator_tools
from app.infra.langchain.curator_agent import CuratorAgent
from app.infra.postgres.adapters import PostgresExhibitRepository, PostgresVisitorProfileRepository

router = APIRouter(prefix="/curator", tags=["curator"])


class PlanTourRequest(BaseModel):
    available_time: int
    interests: list[str] | None = None


class PlanTourResponse(BaseModel):
    user_id: str
    available_time: int
    interests: list[str]
    visited_exhibit_ids: list[str]
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


async def get_curator_service(session: SessionDep, request: Request) -> CuratorService:
    """Get curator service instance with all dependencies."""
    # Create repositories
    profile_repository = PostgresVisitorProfileRepository(session)
    exhibit_repository = PostgresExhibitRepository(session)

    # Create services
    profile_service = ProfileService(profile_repository)
    exhibit_service = ExhibitService(exhibit_repository)

    # Get LLM from app state
    if not hasattr(request.app.state, "llm"):
        raise RuntimeError("LLM not initialized. App not started?")
    llm = request.app.state.llm

    # Get RAG agent from app state (for knowledge retrieval tool)
    rag_agent = getattr(request.app.state, "rag_agent", None)

    # Create tools
    tools = create_curator_tools(
        exhibit_repository=exhibit_repository,
        profile_repository=profile_repository,
        rag_agent=rag_agent,
        llm=llm,
    )

    # Create curator agent
    curator_agent = await CuratorAgent.create(
        llm=llm,
        tools=tools,
        session_id=str(uuid.uuid4()),
        verbose=False,
    )

    return CuratorService(
        curator_agent=curator_agent,
        profile_service=profile_service,
        exhibit_service=exhibit_service,
    )


def get_user_id(current_user: OptionalUser) -> str:
    """Get user ID from authenticated user or generate a guest ID."""
    if current_user:
        return current_user["id"]
    # Generate a temporary guest ID for anonymous users
    return f"guest-{uuid.uuid4()}"


@router.post("/plan-tour", response_model=PlanTourResponse)
async def plan_tour(
    session: SessionDep,
    request: PlanTourRequest,
    current_user: OptionalUser,
    http_request: Request,
    _: RateLimitDep,
) -> PlanTourResponse:
    """Plan a museum tour based on available time and interests.

    Supports both authenticated users and guests.
    Guests get a temporary profile that won't persist.
    """
    service = await get_curator_service(session, http_request)
    user_id = get_user_id(current_user)

    result = await service.plan_tour(
        user_id=user_id,
        available_time=request.available_time,
        interests=request.interests,
    )

    return PlanTourResponse(**result)


@router.post("/narrative", response_model=NarrativeResponse)
async def generate_narrative(
    session: SessionDep,
    request: NarrativeRequest,
    current_user: OptionalUser,
    http_request: Request,
    _: RateLimitDep,
) -> NarrativeResponse:
    """Generate narrative content for an exhibit.

    Supports both authenticated users and guests.
    """
    service = await get_curator_service(session, http_request)
    user_id = get_user_id(current_user)

    try:
        result = await service.generate_narrative(
            user_id=user_id,
            exhibit_id=request.exhibit_id,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=sanitize_error_message(e),
        ) from None

    return NarrativeResponse(**result)


@router.post("/reflection", response_model=ReflectionResponse)
async def get_reflection_prompts(
    session: SessionDep,
    request: ReflectionRequest,
    current_user: OptionalUser,
    http_request: Request,
    _: RateLimitDep,
) -> ReflectionResponse:
    """Get reflection prompts for an exhibit.

    Supports both authenticated users and guests.
    """
    service = await get_curator_service(session, http_request)
    user_id = get_user_id(current_user)

    try:
        result = await service.get_reflection_prompts(
            user_id=user_id,
            exhibit_id=request.exhibit_id,
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=sanitize_error_message(e),
        ) from None

    return ReflectionResponse(**result)
