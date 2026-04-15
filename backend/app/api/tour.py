from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import (
    LLMProviderDep,
    OptionalUser,
    RagAgentDep,
    SessionDep,
    SessionMakerDep,
)
from app.application.tour_chat_service import ask_stream_tour
from app.application.tour_event_service import get_events_by_session, record_events
from app.application.tour_report_service import generate_report, get_report
from app.application.tour_session_service import (
    create_session,
    find_active_session_by_user,
    get_session,
    update_session,
    verify_session_token,
)
from app.domain.exceptions import (
    TourSessionExpired,
    TourSessionNotFound,
    TourSessionTokenMismatch,
)
from app.infra.postgres.models import Exhibit

router = APIRouter(prefix="/tour", tags=["tour"])


class TourSessionCreate(BaseModel):
    interest_type: Literal["A", "B", "C"]
    persona: Literal["A", "B", "C"]
    assumption: Literal["A", "B", "C"]
    guest_id: str | None = None


class TourSessionUpdate(BaseModel):
    current_hall: str | None = None
    current_exhibit_id: str | None = None
    status: Literal["onboarding", "opening", "touring", "completed"] | None = None


class TourEventItem(BaseModel):
    event_type: Literal[
        "exhibit_view", "exhibit_question", "exhibit_deep_dive",
        "hall_enter", "hall_leave",
    ]
    exhibit_id: str | None = None
    hall: str | None = None
    duration_seconds: int | None = None
    metadata: dict | None = None


class TourEventBatch(BaseModel):
    events: list[TourEventItem] = Field(..., max_length=50)


class TourChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    exhibit_id: str | None = None


class TourHallItem(BaseModel):
    slug: str
    name: str
    description: str
    exhibit_count: int
    estimated_duration_minutes: int


class TourHallListResponse(BaseModel):
    halls: list[TourHallItem]


HALLS_DATA = [
    TourHallItem(
        slug="relic-hall",
        name="出土文物展厅",
        description=(
            "陈列半坡遗址出土的陶器、石器、骨器等文物，"
            "展示6000年前半坡人的生存技术和精神世界。"
        ),
        exhibit_count=0,
        estimated_duration_minutes=30,
    ),
    TourHallItem(
        slug="site-hall",
        name="遗址保护大厅",
        description=(
            "保留半坡遗址的居住区、制陶区和墓葬区原貌，"
            "展示圆形和方形半地穴式房屋结构。"
        ),
        exhibit_count=0,
        estimated_duration_minutes=25,
    ),
]


async def _verify_ownership(
    session_id: str,
    user: dict | None,
    token: str | None,
    db_session,
) -> None:
    if user:
        tour_session = await get_session(db_session, session_id)
        uid = (
            tour_session.user_id.value
            if hasattr(tour_session.user_id, "value")
            else tour_session.user_id
        )
        if tour_session.user_id and str(uid) != user["id"]:
            raise HTTPException(status_code=403, detail="Not your tour session") from None
    elif token:
        try:
            await verify_session_token(db_session, session_id, token)
        except TourSessionTokenMismatch:
            raise HTTPException(status_code=403, detail="Invalid session token") from None
    else:
        raise HTTPException(status_code=403, detail="Authentication required") from None


def _format_session(tour_session) -> dict:
    eid = tour_session.current_exhibit_id
    return {
        "id": (
            tour_session.id.value
            if hasattr(tour_session.id, "value")
            else tour_session.id
        ),
        "session_token": tour_session.session_token,
        "interest_type": tour_session.interest_type,
        "persona": tour_session.persona,
        "assumption": tour_session.assumption,
        "status": tour_session.status,
        "current_hall": tour_session.current_hall,
        "current_exhibit_id": (
            str(eid.value) if eid and hasattr(eid, "value") else eid
        ),
        "visited_halls": tour_session.visited_halls,
        "visited_exhibit_ids": tour_session.visited_exhibit_ids,
        "started_at": tour_session.started_at.isoformat(),
    }


def _format_report(report) -> dict:
    eid = report.most_viewed_exhibit_id
    return {
        "id": (
            report.id.value if hasattr(report.id, "value") else report.id
        ),
        "tour_session_id": (
            report.tour_session_id.value
            if hasattr(report.tour_session_id, "value")
            else report.tour_session_id
        ),
        "total_duration_minutes": report.total_duration_minutes,
        "most_viewed_exhibit_id": (
            str(eid.value) if eid and hasattr(eid, "value") else eid
        ),
        "most_viewed_exhibit_duration": report.most_viewed_exhibit_duration,
        "longest_hall": report.longest_hall,
        "longest_hall_duration": report.longest_hall_duration,
        "total_questions": report.total_questions,
        "total_exhibits_viewed": report.total_exhibits_viewed,
        "ceramic_questions": report.ceramic_questions,
        "identity_tags": report.identity_tags,
        "radar_scores": report.radar_scores,
        "one_liner": report.one_liner,
        "report_theme": report.report_theme,
        "created_at": report.created_at.isoformat(),
    }


@router.post("/sessions")
async def create_tour_session(
    body: TourSessionCreate,
    session: SessionDep,
    user: OptionalUser = None,
):
    user_id = user["id"] if user else None
    guest_id = body.guest_id if not user else None

    if user:
        existing = await find_active_session_by_user(session, user_id)
        if existing:
            return _format_session(existing)

    tour_session = await create_session(
        session,
        interest_type=body.interest_type,
        persona=body.persona,
        assumption=body.assumption,
        user_id=user_id,
        guest_id=guest_id,
    )
    return _format_session(tour_session)


@router.get("/sessions/{session_id}")
async def get_tour_session(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired") from None
    return _format_session(tour_session)


@router.patch("/sessions/{session_id}")
async def patch_tour_session(
    session_id: str,
    body: TourSessionUpdate,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        tour_session = await update_session(session, session_id, **updates)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired") from None
    return _format_session(tour_session)


@router.post("/sessions/{session_id}/events")
async def post_tour_events(
    session_id: str,
    body: TourEventBatch,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        events = await record_events(
            session, session_id, [e.model_dump() for e in body.events]
        )
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    return {"recorded": len(events)}


@router.get("/sessions/{session_id}/events")
async def list_tour_events(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        events = await get_events_by_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    return {
        "events": [
            {
                "id": (
                    e.id.value if hasattr(e.id, "value") else e.id
                ),
                "event_type": e.event_type,
                "exhibit_id": (
                    str(e.exhibit_id.value)
                    if e.exhibit_id and hasattr(e.exhibit_id, "value")
                    else e.exhibit_id
                ),
                "hall": e.hall,
                "duration_seconds": e.duration_seconds,
                "metadata": e.metadata,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }


@router.post("/sessions/{session_id}/complete-hall")
async def complete_hall(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None

    visited_halls = list(tour_session.visited_halls or [])
    if tour_session.current_hall and tour_session.current_hall not in visited_halls:
        visited_halls.append(tour_session.current_hall)

    all_halls = [h.slug for h in HALLS_DATA]
    all_visited = all(h in visited_halls for h in all_halls)

    new_status = "completed" if all_visited else "touring"
    updated = await update_session(
        session, session_id, visited_halls=visited_halls, status=new_status
    )

    return {
        "visited_halls": updated.visited_halls,
        "all_halls_visited": all_visited,
        "status": updated.status,
    }


@router.post("/sessions/{session_id}/report")
async def create_tour_report(
    session_id: str,
    session: SessionDep,
    llm_provider: LLMProviderDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)

    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None

    if tour_session.status != "completed":
        await update_session(session, session_id, status="completed")

    try:
        report = await generate_report(
            session, session_id, llm_provider=llm_provider
        )
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None

    return _format_report(report)


@router.get("/sessions/{session_id}/report")
async def get_tour_report(
    session_id: str,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    report = await get_report(session, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found") from None
    return _format_report(report)


@router.post("/sessions/{session_id}/chat/stream")
async def tour_chat_stream(
    session_id: str,
    body: TourChatRequest,
    request: Request,
    session: SessionDep,
    session_maker: SessionMakerDep,
    rag_agent: RagAgentDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)

    return StreamingResponse(
        ask_stream_tour(
            db_session=session,
            session_maker=session_maker,
            tour_session_id=session_id,
            message=body.message,
            rag_agent=rag_agent,
            exhibit_id=body.exhibit_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/halls")
async def list_tour_halls(
    session: SessionDep,
):
    hall_slugs = [h.slug for h in HALLS_DATA]
    stmt = (
        select(Exhibit.hall, func.count(Exhibit.id))
        .where(Exhibit.hall.in_(hall_slugs), Exhibit.is_active.is_(True))
        .group_by(Exhibit.hall)
    )
    result = await session.execute(stmt)
    counts = dict(result.all())

    halls = []
    for h in HALLS_DATA:
        halls.append(
            TourHallItem(
                slug=h.slug,
                name=h.name,
                description=h.description,
                exhibit_count=counts.get(h.slug, 0),
                estimated_duration_minutes=h.estimated_duration_minutes,
            )
        )
    return TourHallListResponse(halls=halls)
