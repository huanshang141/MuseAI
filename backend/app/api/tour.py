import json
import re
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
from app.application.hall_normalizer import (
    canonical_hall_contract,
    hall_display_name,
    normalize_hall,
    normalize_halls,
)
from app.application.tour_report_service import build_reflection_summary, generate_report, get_report
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

TourPersonaCode = Literal["A", "B", "C", "D"]
TourAssumptionCode = Literal["A", "B", "C", "D"]
VISITED_HALL_EVENT_TYPES = {
    "exhibit_question",
    "exhibit_view",
}


class TourSessionCreate(BaseModel):
    interest_type: TourPersonaCode
    persona: TourPersonaCode
    assumption: TourAssumptionCode
    guest_id: str | None = None


class TourSessionUpdate(BaseModel):
    current_hall: str | None = None
    current_exhibit_id: str | None = None
    status: Literal["onboarding", "opening", "touring", "completed"] | None = None
    interest_type: TourPersonaCode | None = None
    persona: TourPersonaCode | None = None
    assumption: TourAssumptionCode | None = None


class TourEventItem(BaseModel):
    event_type: Literal[
        "exhibit_view", "exhibit_question", "exhibit_deep_dive",
        "hall_enter", "hall_leave", "assistant_answer",
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


class TourChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=1000)


class TourChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    exhibit_id: str | None = None
    exhibit_context: str | None = Field(default=None, max_length=1200)
    client_event_id: str | None = Field(default=None, max_length=120)
    style: TourChatStyle | None = None
    client_context: str | None = Field(default=None, max_length=1500)
    conversation_history: list[TourChatHistoryItem] | None = Field(default=None, max_length=8)
    tts: bool = False


class TourHallItem(BaseModel):
    slug: str
    name: str
    description: str
    exhibit_count: int
    estimated_duration_minutes: int


class TourHallListResponse(BaseModel):
    halls: list[TourHallItem]


DEFAULT_HALLS_DATA = [
    TourHallItem(
        slug="basic-exhibition-hall",
        name="基本陈列展厅",
        description="系统展示半坡文化的生活形态、生产方式与社会结构。",
        exhibit_count=0,
        estimated_duration_minutes=40,
    ),
    TourHallItem(
        slug="site-protection-hall",
        name="遗址保护大厅",
        description="强调原址呈现与保护展示，呈现墓葬、房屋、作坊和灶具灶台等遗存。",
        exhibit_count=0,
        estimated_duration_minutes=35,
    ),
    TourHallItem(
        slug="kiln-hall",
        name="陶窑展厅",
        description="展示半坡时期制陶与烧制工艺，解释从制坯到入窑烧成的流程。",
        exhibit_count=0,
        estimated_duration_minutes=25,
    ),
]


async def _load_tour_halls(session: SessionDep) -> list[TourHallItem]:
    """Load halls from unified hall settings, falling back to canonical defaults."""
    stmt = (
        select(Hall)
        .where(Hall.is_active.is_(True))
        .order_by(Hall.display_order.asc(), Hall.created_at.asc())
    )
    result = await session.execute(stmt)
    hall_rows = list(result.scalars().all())

    rows_by_slug = {}
    for hall in hall_rows:
        slug = normalize_hall(hall.slug)
        if slug and slug not in rows_by_slug:
            rows_by_slug[slug] = hall

    if not hall_rows and not canonical_hall_contract():
        return DEFAULT_HALLS_DATA

    halls: list[TourHallItem] = []
    for contract in canonical_hall_contract():
        slug = contract["slug"]
        backend = rows_by_slug.get(slug)
        if backend is not None and backend.is_active is False:
            continue
        halls.append(
            TourHallItem(
                slug=slug,
                name=hall_display_name(slug),
                description=(backend.description if backend else None) or contract.get("description") or "",
                exhibit_count=0,
                estimated_duration_minutes=(
                    backend.estimated_duration_minutes
                    if backend is not None
                    else contract["estimated_duration_minutes"]
                ),
            )
        )
    return halls


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
        "current_hall": normalize_hall(tour_session.current_hall),
        "current_exhibit_id": (
            str(eid.value) if eid and hasattr(eid, "value") else eid
        ),
        "visited_halls": normalize_halls(tour_session.visited_halls),
        "visited_exhibit_ids": tour_session.visited_exhibit_ids,
        "started_at": tour_session.started_at.isoformat(),
    }


def _compact_chat_exhibit_context(value: str | None, max_len: int = 1200) -> str | None:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return None
    return text[:max_len]


async def _resolve_chat_exhibit_context(
    session,
    exhibit_id: str | None,
    provided_context: str | None,
) -> str | None:
    context = _compact_chat_exhibit_context(provided_context)
    if context:
        return context

    eid = str(exhibit_id or "").strip()
    if not eid or eid.startswith("local-") or eid.startswith("mock-"):
        return None

    exhibit = await session.get(Exhibit, eid)
    if exhibit is None:
        return None

    parts = [f"名称：{exhibit.name}"]
    hall_slug = normalize_hall(exhibit.hall)
    hall_name = hall_display_name(hall_slug) if hall_slug else None
    if hall_name or exhibit.hall:
        parts.append(f"展厅：{hall_name or exhibit.hall}")
    if exhibit.category:
        parts.append(f"类别：{exhibit.category}")
    if exhibit.era:
        parts.append(f"年代：{exhibit.era}")
    if exhibit.description:
        parts.append(f"简介：{str(exhibit.description).strip()[:600]}")
    return "\n".join(parts)[:1200]


def _collect_visited_halls(tour_session=None, events=None) -> list[str]:
    candidates: list[str] = []
    for event in events or []:
        event_type = getattr(event, "event_type", None)
        if event_type not in VISITED_HALL_EVENT_TYPES:
            continue
        hall = getattr(event, "hall", None)
        metadata = getattr(event, "metadata", None) or {}
        if hall:
            candidates.append(hall)
        for key in ("hall", "hall_slug", "hallSlug"):
            if metadata.get(key):
                candidates.append(metadata[key])
    return normalize_halls(candidates)


def _build_report_highlights(report, halls_visited: list[str]) -> list[str]:
    highlights: list[str] = []
    if halls_visited:
        highlights.append(f"本次共到访 {len(halls_visited)} 个展厅")
    if report.total_questions:
        highlights.append(f"共提出 {report.total_questions} 个导览问题")
    if report.total_exhibits_viewed:
        highlights.append(f"重点查看 {report.total_exhibits_viewed} 件展品")
    return highlights


def _compact_record_text(value: str | None, max_len: int = 90) -> str:
    text = str(value or "")
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[*_`#>-]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text


def _append_unique(items: list[str], value: str) -> None:
    text = str(value or "").strip()
    if text and text not in items:
        items.append(text)


def _record_focus_phrases(question_text: str, answer_text: str, topic: str) -> list[str]:
    text = f"{question_text} {answer_text}"
    phrases: list[str] = []
    if re.search(r"石器|骨器|工具|用途", text):
        _append_unique(phrases, "石器骨器用途")
    if re.search(r"文物|类型|展示|展厅", text):
        _append_unique(phrases, "文物类型")
    if re.search(r"动手|体验|技术|制作|步骤", text):
        _append_unique(phrases, "动手体验与技术理解")
    if re.search(r"陶|彩陶|陶器|器形|纹饰|工艺|烧制", text):
        _append_unique(phrases, "器物工艺")
    if re.search(r"房屋|聚落|遗址|壕沟|布局|半地穴", text):
        _append_unique(phrases, "聚落空间")
    if re.search(r"人面|鱼纹|图案|信仰|仪式|观念", text):
        _append_unique(phrases, "图案与观念")
    if re.search(r"生活|先民|日常|生产|定居", text):
        _append_unique(phrases, "半坡生活方式")
    if not phrases:
        _append_unique(phrases, topic or "证据线索")
    return phrases[:4]


def _record_knowledge_phrases(answer_text: str, topic: str) -> list[str]:
    phrases: list[str] = []
    if re.search(r"石器|骨器|工具", answer_text):
        _append_unique(phrases, "石器、骨器和工具可对应加工、制作与生产分工")
    if re.search(r"陶|彩陶|陶器|器形|纹饰|烧制", answer_text):
        _append_unique(phrases, "陶器可从器形、纹饰和制作痕迹理解用途")
    if re.search(r"房屋|聚落|遗址|壕沟|半地穴|布局", answer_text):
        _append_unique(phrases, "房屋、壕沟等遗迹能说明聚落布局")
    if re.search(r"人面|鱼纹|图案|信仰|仪式|观念", answer_text):
        _append_unique(phrases, "人面鱼纹等图案关联审美、仪式与观念")
    if re.search(r"动手|体验|技术|制作|步骤|材料", answer_text):
        _append_unique(phrases, "动手体验能把材料、步骤和工具关系具体化")
    if re.search(r"生活|定居|生产|日常|先民", answer_text):
        _append_unique(phrases, "出土文物反映定居、生产和日常生活方式")
    if not phrases:
        _append_unique(phrases, f"{topic or '证据线索'}需要回到展品、展签和遗迹位置核对")
    return phrases[:3]


def _append_summary_sentence(parts: list[str], sentence: str, max_len: int = 400) -> None:
    if sentence and len("".join(parts) + sentence) <= max_len:
        parts.append(sentence)


def _join_record_phrases(phrases: list[str]) -> str:
    clean = [phrase for phrase in phrases if phrase]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]}和{clean[1]}"
    return "、".join(clean[:-1]) + f"和{clean[-1]}"


def _build_record_summary_point(
    hall_text: str,
    question_text: str,
    answer_text: str,
    topic: str,
) -> str:
    focus_phrases = _record_focus_phrases(question_text, answer_text, topic)
    knowledge_phrases = _record_knowledge_phrases(answer_text, topic)
    subject = f"{hall_text}这段记录" if hall_text and hall_text != "半坡遗址" else "这次参观"
    focus_text = _join_record_phrases(focus_phrases)
    knowledge_text = _join_record_phrases(knowledge_phrases)
    parts: list[str] = []
    _append_summary_sentence(parts, f"{subject}主要留下这些线索：{knowledge_text}。")
    _append_summary_sentence(parts, f"提问中的{focus_text}，可在展柜、展签和遗迹位置继续核对。")
    return "".join(parts)


def _record_point_from_answer(answer: str | None) -> str:
    text = _compact_record_text(answer, 400)
    if not text:
        return "这条问题已经留下线索，后续可回到对应展厅核对可见证据。"
    sentences = [
        item.strip()
        for item in re.split(r"[。！？；]", text)
        if item.strip()
    ]
    markers = ("说明", "反映", "表明", "意味着", "可以看出", "证据", "关键")
    for sentence in sentences:
        if any(marker in sentence for marker in markers):
            return _compact_record_text(sentence, 110)
    return _compact_record_text(sentences[0] if sentences else text, 110)


def _infer_record_topic(text: str) -> str:
    if any(keyword in text for keyword in ("陶", "器", "工艺", "纹", "材料", "石器", "骨器", "工具", "用途")):
        return "器物工艺"
    if any(keyword in text for keyword in ("聚落", "房屋", "半地穴", "壕沟", "遗址", "空间", "布局", "墓葬")):
        return "聚落空间"
    if any(keyword in text for keyword in ("社会", "组织", "分工", "共同体", "协作", "规则", "公共")):
        return "社会组织"
    if any(keyword in text for keyword in ("生活", "食物", "农业", "居住", "日常", "生产")):
        return "日常生活"
    return "证据线索"


def _persona_record_frame(persona: str | None) -> tuple[str, str]:
    frames = {
        "A": ("考古研究员", "这段记录更像一份考古观察：它把问题压回到可核对的遗迹、材料和推断边界上，也提醒后续回到展厅时继续区分直接证据与合理解释。"),
        "B": ("研学记录员", "这段记录更像一份研学笔记：它把展厅见闻整理成后续还能复盘的学习线索，也帮助你把“看过什么”转成“为什么这样判断”。"),
        "C": ("历史追问者", "这段记录更像一次历史追问：它把展厅内容和半坡社会、共同生活的问题连接起来，也保留了继续追问制度、分工和日常秩序的入口。"),
        "D": ("器物研究员", "这段记录更像一份器物观察：它从材料、器形、用途和工艺痕迹进入半坡生活，也把器物细节和生产、使用场景联系起来。"),
    }
    return frames.get(persona or "A", frames["A"])


def _build_report_record_notes(events=None, persona: str | None = None) -> list[dict[str, str]]:
    answered_entries: list[dict[str, str]] = []
    question_entries: list[dict[str, str]] = []
    seen_answer_ids: set[str] = set()
    for event in events or []:
        event_type = getattr(event, "event_type", None)
        if event_type not in {"assistant_answer", "exhibit_question"}:
            continue
        metadata = getattr(event, "metadata", None) or {}
        hall = normalize_hall(
            getattr(event, "hall", None)
            or metadata.get("hall")
            or metadata.get("hall_slug")
            or metadata.get("hallSlug")
        )
        question = (
            metadata.get("question")
            or metadata.get("message")
            or metadata.get("query")
            or ""
        )
        if not question:
            continue
        compact_question = _compact_record_text(question, 54)
        if not compact_question:
            continue
        entry = {
            "hall": hall or "",
            "question": compact_question,
            "answer": "",
        }
        if event_type == "assistant_answer" and metadata.get("answer"):
            client_event_id = str(
                metadata.get("question_client_event_id")
                or metadata.get("client_event_id")
                or ""
            ).strip()
            if client_event_id:
                if client_event_id in seen_answer_ids:
                    continue
                seen_answer_ids.add(client_event_id)
            entry["answer"] = _compact_record_text(metadata.get("answer"), 400)
            answered_entries.append(entry)
        elif event_type == "exhibit_question":
            question_entries.append(entry)

    entries = answered_entries or question_entries
    if not entries:
        return []

    hall_names = []
    for entry in entries:
        hall_name = hall_display_name(entry["hall"]) if entry["hall"] else ""
        if hall_name and hall_name not in hall_names:
            hall_names.append(hall_name)
    hall_text = "、".join(hall_names) if hall_names else "半坡遗址"
    questions_text = "”“".join(entry["question"] for entry in entries)
    answer_text = " ".join(entry["answer"] for entry in entries if entry["answer"])
    topic = _infer_record_topic(" ".join([questions_text, answer_text]))
    point = _build_record_summary_point(hall_text, questions_text, answer_text, topic)
    return [{"question": "游览记录摘要", "point": point}]


def _format_report(report, tour_session=None, events=None) -> dict:
    eid = report.most_viewed_exhibit_id
    halls_visited = _collect_visited_halls(tour_session, events)
    report_stats = {
        "total_duration_minutes": report.total_duration_minutes,
        "most_viewed_exhibit_duration": report.most_viewed_exhibit_duration,
        "longest_hall_duration": report.longest_hall_duration,
        "total_questions": report.total_questions,
        "total_exhibits_viewed": report.total_exhibits_viewed,
        "ceramic_questions": report.ceramic_questions,
    }
    reflection = (
        build_reflection_summary(
            tour_session,
            events or [],
            stats=report_stats,
            radar_scores=report.radar_scores,
        )
        if tour_session is not None
        else None
    )
    record_summary = getattr(report, "record_summary", None)
    if record_summary:
        record_notes = [{
            "question": "游览记录摘要",
            "point": _compact_record_text(record_summary, 400),
        }]
    else:
        record_notes = _build_report_record_notes(events, getattr(tour_session, "persona", None))
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
        "longest_hall": normalize_hall(report.longest_hall),
        "longest_hall_duration": report.longest_hall_duration,
        "total_questions": report.total_questions,
        "total_exhibits_viewed": report.total_exhibits_viewed,
        "ceramic_questions": report.ceramic_questions,
        "halls_visited": halls_visited,
        "identity_tags": report.identity_tags,
        "radar_scores": report.radar_scores,
        "one_liner": report.one_liner,
        "report_theme": report.report_theme,
        "record_summary": record_summary,
        "highlights": _build_report_highlights(report, halls_visited),
        "record_notes": record_notes,
        "reflection": reflection,
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
    body_data = body.model_dump()
    updates = {k: body_data[k] for k in body.model_fields_set}
    if "current_hall" in updates and updates["current_hall"] is not None:
        updates["current_hall"] = normalize_hall(updates["current_hall"])
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
    payload_events = [e.model_dump() for e in body.events]
    for event in payload_events:
        if event.get("hall"):
            event["hall"] = normalize_hall(event["hall"])
    try:
        events = await record_events(
            session, session_id, payload_events
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
                "hall": normalize_hall(e.hall),
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

    visited_halls = normalize_halls(tour_session.visited_halls)
    current_hall = normalize_hall(tour_session.current_hall)
    if current_hall and current_hall not in visited_halls:
        visited_halls.append(current_hall)

    hall_configs = await _load_tour_halls(session)
    all_halls = [normalize_hall(h.slug) for h in hall_configs if normalize_hall(h.slug)]
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

    events = await get_events_by_session(session, session_id)
    return _format_report(report, tour_session=tour_session, events=events)


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
    try:
        tour_session = await get_session(session, session_id)
        events = await get_events_by_session(session, session_id)
    except TourSessionNotFound:
        tour_session = None
        events = []
    return _format_report(report, tour_session=tour_session, events=events)


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

    exhibit_context = await _resolve_chat_exhibit_context(
        session,
        body.exhibit_id,
        body.exhibit_context,
    )

    return StreamingResponse(
        ask_stream_tour(
            db_session=session,
            session_maker=session_maker,
            tour_session_id=session_id,
            message=body.message,
            rag_agent=rag_agent,
            llm_provider=llm_provider,
            exhibit_id=body.exhibit_id,
            exhibit_context=exhibit_context,
            client_event_id=body.client_event_id,
            client_context=body.client_context,
            conversation_history=[
                item.model_dump() for item in body.conversation_history
            ] if body.conversation_history else None,
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
    hall_slugs = [normalize_hall(h.slug) for h in hall_configs if normalize_hall(h.slug)]
    stmt = (
        select(Exhibit.hall, func.count(Exhibit.id))
        .where(Exhibit.hall.in_(hall_slugs), Exhibit.is_active.is_(True))
        .group_by(Exhibit.hall)
    )
    result = await session.execute(stmt)
    counts = {}
    for hall, count in result.all():
        slug = normalize_hall(hall) or hall
        counts[slug] = counts.get(slug, 0) + count

    halls = []
    seen = set()
    for h in hall_configs:
        slug = normalize_hall(h.slug) or h.slug
        if slug in seen:
            continue
        seen.add(slug)
        halls.append(
            TourHallItem(
                slug=slug,
                name=hall_display_name(slug),
                description=h.description,
                exhibit_count=counts.get(slug, 0),
                estimated_duration_minutes=h.estimated_duration_minutes,
            )
        )
    return TourHallListResponse(halls=halls)
