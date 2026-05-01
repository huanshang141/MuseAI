import json
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
    re_onboard_session,
    update_session,
    verify_session_token,
)
from app.domain.exceptions import (
    TourSessionExpired,
    TourSessionNotFound,
    TourSessionTokenMismatch,
)
from app.infra.postgres.models import Exhibit, Hall

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
    interest_type: Literal["A", "B", "C"] | None = None
    persona: Literal["A", "B", "C"] | None = None
    assumption: Literal["A", "B", "C"] | None = None


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


class TourChatStyle(BaseModel):
    answer_length: str | None = None
    depth: str | None = None
    terminology: str | None = None


class TourChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    exhibit_id: str | None = None
    style: TourChatStyle | None = None
    tts: bool = False


class TourHallItem(BaseModel):
    slug: str
    name: str
    description: str
    exhibit_count: int
    estimated_duration_minutes: int


class TourHallListResponse(BaseModel):
    halls: list[TourHallItem]


LEGACY_HALLS_DATA = [
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


async def _load_tour_halls(session: SessionDep) -> list[TourHallItem]:
    """Load halls from unified hall settings, falling back to legacy defaults."""
    stmt = (
        select(Hall)
        .where(Hall.is_active.is_(True))
        .order_by(Hall.display_order.asc(), Hall.created_at.asc())
    )
    result = await session.execute(stmt)
    hall_rows = list(result.scalars().all())

    if not hall_rows:
        return LEGACY_HALLS_DATA

    return [
        TourHallItem(
            slug=hall.slug,
            name=hall.name,
            description=hall.description or "",
            exhibit_count=0,
            estimated_duration_minutes=hall.estimated_duration_minutes,
        )
        for hall in hall_rows
    ]


async def _verify_ownership(
    session_id: str,
    user: dict | None,
    token: str | None,
    db_session,
) -> None:
    if user:
        try:
            tour_session = await get_session(db_session, session_id)
        except TourSessionNotFound:
            raise HTTPException(status_code=404, detail="Tour session not found") from None
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
        except TourSessionNotFound:
            raise HTTPException(status_code=404, detail="Tour session not found") from None
        except TourSessionTokenMismatch:
            raise HTTPException(status_code=403, detail="Invalid session token") from None
    else:
        raise HTTPException(status_code=403, detail="Authentication required") from None


def _format_session(tour_session) -> dict:
    eid = tour_session.current_exhibit_id
    uid = tour_session.user_id
    return {
        "id": (
            tour_session.id.value
            if hasattr(tour_session.id, "value")
            else tour_session.id
        ),
        "user_id": (
            str(uid.value) if uid and hasattr(uid, "value") else uid
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


@router.post("/sessions", summary="Create tour session")
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
            if existing.status in ("onboarding", "opening"):
                updated = await re_onboard_session(
                    session,
                    existing.id.value,
                    interest_type=body.interest_type,
                    persona=body.persona,
                    assumption=body.assumption,
                )
                return _format_session(updated)
            updated = await update_session(
                session,
                existing.id.value,
                interest_type=body.interest_type,
                persona=body.persona,
                assumption=body.assumption,
            )
            return _format_session(updated)

    tour_session = await create_session(
        session,
        interest_type=body.interest_type,
        persona=body.persona,
        assumption=body.assumption,
        user_id=user_id,
        guest_id=guest_id,
    )
    return _format_session(tour_session)


@router.get("/sessions/{session_id}", summary="Get tour session")
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


@router.patch("/sessions/{session_id}", summary="Update tour session")
async def patch_tour_session(
    session_id: str,
    request: Request,
    session: SessionDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)
    raw = await request.body()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="Invalid JSON body") from None
    body = TourSessionUpdate.model_validate(data)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        tour_session = await update_session(session, session_id, **updates)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired") from None
    return _format_session(tour_session)


@router.post("/sessions/{session_id}/events", summary="Record tour events")
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


@router.get("/sessions/{session_id}/events", summary="List tour events")
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


@router.post("/sessions/{session_id}/complete-hall", summary="Complete hall visit")
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

    hall_configs = await _load_tour_halls(session)
    all_halls = [h.slug for h in hall_configs]
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


@router.post("/sessions/{session_id}/report", summary="Generate tour report")
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


@router.get("/sessions/{session_id}/report", summary="Get tour report")
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


@router.post("/sessions/{session_id}/chat/stream", summary="Stream tour chat (SSE)")
async def tour_chat_stream(
    session_id: str,
    body: TourChatRequest,
    request: Request,
    session: SessionDep,
    session_maker: SessionMakerDep,
    rag_agent: RagAgentDep,
    llm_provider: LLMProviderDep,
    user: OptionalUser = None,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, user, x_session_token, session)

    degraded = set()
    if hasattr(request.app.state, "degraded"):
        degraded = set(request.app.state.degraded)

    tts_provider = getattr(request.app.state, "tts_provider", None)
    tts_service = getattr(request.app.state, "tts_service", None)

    # Resolve persona for TTS config
    persona = None
    if body.tts:
        try:
            tour_session_obj = await get_session(session, session_id)
            persona = tour_session_obj.persona
        except (TourSessionNotFound, TourSessionExpired):
            pass  # Will fall back to session persona in ask_stream_tour

    return StreamingResponse(
        ask_stream_tour(
            db_session=session,
            session_maker=session_maker,
            tour_session_id=session_id,
            message=body.message,
            rag_agent=rag_agent,
            llm_provider=llm_provider,
            exhibit_id=body.exhibit_id,
            style=body.style,
            degraded_services=degraded,
            tts_provider=tts_provider if body.tts else None,
            tts_service=tts_service if body.tts else None,
            persona=persona,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/halls", summary="List tour halls")
async def list_tour_halls(
    session: SessionDep,
):
    hall_configs = await _load_tour_halls(session)
    hall_slugs = [h.slug for h in hall_configs]
    stmt = (
        select(Exhibit.hall, func.count(Exhibit.id))
        .where(Exhibit.hall.in_(hall_slugs), Exhibit.is_active.is_(True))
        .group_by(Exhibit.hall)
    )
    result = await session.execute(stmt)
    counts = dict(result.all())

    halls = []
    for h in hall_configs:
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
