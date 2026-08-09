import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)
from sqlalchemy import func, select

from app.api.deps import (
    LLMProviderDep,
    RagAgentDep,
    SessionDep,
    SessionMakerDep,
    TourChatRateLimitDep,
    TourReportRateLimitDep,
    TourSessionCreateRateLimitDep,
    TourSessionWriteRateLimitDep,
)
from app.application.hall_normalizer import (
    CANONICAL_HALL_SLUGS,
    is_temporary_hall,
    normalize_hall,
    normalize_halls,
    temporary_hall_description,
)
from app.application.tour_chat_service import (
    ask_stream_tour,
    bound_conversation_history,
    bound_grounding_history,
    grounding_subject,
    has_unresolved_deictic_comparison,
    is_hall_level_question,
)
from app.application.tour_event_service import get_events_by_session, record_events
from app.application.tour_report_service import (
    build_exploration_guidance,
    build_reflection_summary,
    clarification_question_keys,
    generate_report,
    get_report,
    is_clarification_event,
)
from app.application.tour_session_service import (
    SESSION_EXPIRY_HOURS,
    create_session,
    get_session,
    update_session,
    verify_session_token,
)
from app.application.tour_suggestion_service import (
    SUGGESTION_MAX_LENGTH,
    SUGGESTION_MIN_LENGTH,
)
from app.application.tour_suggestion_service import (
    derive_exhibit_suggestions as _derive_exhibit_suggestions,
)
from app.application.tour_suggestion_service import (
    quality_suggestions as _quality_suggestions,
)
from app.domain.exceptions import (
    TourSessionExpired,
    TourSessionNotFound,
    TourSessionStateConflict,
    TourSessionTokenMismatch,
)
from app.infra.postgres.models import Exhibit, Hall

router = APIRouter(prefix="/tour", tags=["tour"])

TourPersonaCode = Literal["default", "A", "B", "C", "D"]
TourAssumptionCode = Literal["A", "B", "C", "D"]
VISITED_HALL_EVENT_TYPES = {
    "exhibit_question",
    "exhibit_view",
}
MAX_SESSION_STATE_PATCH_BYTES = 2 * 1024 * 1024
TOUR_HALL_FOCUS_MAX_LENGTH = 120
TOUR_HALL_CARD_DESCRIPTION_MAX_LENGTH = 48
UNKNOWN_HALL_CARD_DESCRIPTION = "进入展厅查看当前展陈内容。"


class TourQuestionnaire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: Literal["default", "A", "B", "C", "D"] | None = None
    focus_id: str | None = Field(default=None, max_length=64)
    assumption: TourAssumptionCode | None = None
    rhythm_id: str | int | None = None
    intent_text: str | None = Field(default=None, max_length=500)
    preferred_hall_order: list[str] = Field(default_factory=list, max_length=9)

    @field_validator("rhythm_id")
    @classmethod
    def validate_rhythm_id(cls, value: str | int | None):
        if isinstance(value, str) and len(value) > 64:
            raise ValueError("rhythm_id exceeds 64 characters")
        return value


class TourQuestionnaireDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(default=1, ge=1, le=3)
    selectedFocusId: str | None = Field(default=None, max_length=64)
    selectedAssumptionId: str | None = Field(default=None, max_length=64)
    selectedRhythmId: str | None = Field(default=None, max_length=64)
    selectedPersonaName: str | None = Field(default=None, max_length=100)
    intentText: str = Field(default="", max_length=500)


class TourResumeExhibit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, max_length=100)
    name: str = Field(default="", max_length=255)
    hall: str = Field(default="", max_length=100)
    hallDisplay: str = Field(default="", max_length=255)
    era: str = Field(default="", max_length=100)
    category: str = Field(default="", max_length=100)
    objectKind: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class TourStylePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answerLength: Literal["brief", "balanced", "detailed"] = "balanced"
    depth: Literal["introductory", "standard", "deep"] = "standard"
    terminology: Literal["plain", "professional", "academic"] = "plain"
    enabled: bool = True


class TourTtsPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice: str = Field(default="冰糖", max_length=64)
    autoPlay: bool = False
    enabled: bool = True


class TourRouteStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=1, le=20)
    hallId: str = Field(max_length=100)
    hallSlug: str = Field(max_length=100)
    name: str = Field(max_length=255)
    short: str = Field(default="", max_length=20)
    highlights: list[str] = Field(default_factory=list, max_length=20)
    duration: str = Field(default="", max_length=100)
    estimatedMinutes: int = Field(default=0, ge=0, le=480)
    exhibitCount: int = Field(default=0, ge=0)
    exhibitCountKnown: bool = False
    reason: str = Field(default="", max_length=1000)
    focus: str = Field(default="", max_length=500)
    status: str = Field(default="upcoming", max_length=30)
    isVisited: bool = False
    isCurrent: bool = False


class TourRouteFloorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=100)
    short: str = Field(max_length=20)
    status: str = Field(default="upcoming", max_length=30)


class TourRoutePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[TourRouteStep] = Field(default_factory=list, max_length=9)
    floorItems: list[TourRouteFloorItem] = Field(default_factory=list, max_length=9)
    totalDesc: str = Field(default="", max_length=200)
    personaLabel: str = Field(default="", max_length=200)
    tagline: str = Field(default="", max_length=1000)
    stepsCount: int = Field(default=0, ge=0, le=9)
    routeSource: str = Field(default="fallback", max_length=50)
    routeSourceLabel: str = Field(default="", max_length=100)
    planSummary: str = Field(default="", max_length=2000)
    routeNotice: str = Field(default="", max_length=500)


class TourResumeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["onboarding", "opening", "touring", "completed"] | None = None
    interest_type: TourPersonaCode | None = None
    persona: TourPersonaCode | None = None
    persona_id: Literal["default", "A", "B", "C", "D"] | None = None
    assumption: TourAssumptionCode | None = None
    questionnaire: TourQuestionnaire | None = None
    questionnaire_draft: TourQuestionnaireDraft | None = None
    route_plan: TourRoutePlan | None = None
    current_page: str | None = Field(default=None, max_length=100)
    current_page_params: dict[str, str] | None = None
    current_hall: str | None = Field(default=None, max_length=100)
    current_hall_name: str | None = Field(default=None, max_length=255)
    current_exhibit_id: str | None = Field(default=None, max_length=100)
    current_exhibit: TourResumeExhibit | None = None
    current_scanned_exhibit_id: str | None = Field(default=None, max_length=100)
    current_scanned_exhibit_name: str | None = Field(default=None, max_length=255)
    last_scan_timestamp: int | None = Field(default=None, ge=0)
    visited_halls: list[str] = Field(default_factory=list, max_length=9)
    visited_exhibit_ids: list[str] = Field(default_factory=list, max_length=500)
    ai_conversation_count: int = Field(default=0, ge=0, le=10000)
    tour_started_at: datetime | None = None
    intent_text: str | None = Field(default=None, max_length=500)
    preferred_hall_order: list[str] = Field(default_factory=list, max_length=9)
    time_budget: str | int | None = None
    focus_id: str | None = Field(default=None, max_length=64)
    focus_title: str | None = Field(default=None, max_length=200)
    focus_prompt: str | None = Field(default=None, max_length=1000)
    assumption_text: str | None = Field(default=None, max_length=500)
    guide_mode_id: str | None = Field(default=None, max_length=64)
    guide_mode_title: str | None = Field(default=None, max_length=200)
    guide_mode_prompt: str | None = Field(default=None, max_length=1000)
    style_preferences: TourStylePreferences | None = None
    tts_preferences: TourTtsPreferences | None = None

    @field_validator("current_page_params")
    @classmethod
    def validate_page_params(cls, value: dict[str, str] | None):
        if value is not None and len(value) > 20:
            raise ValueError("current_page_params supports at most 20 entries")
        if value is not None and any(len(str(k)) > 100 or len(str(v)) > 500 for k, v in value.items()):
            raise ValueError("current_page_params entry is too long")
        return value


class TourHallChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class TourSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interest_type: TourPersonaCode
    persona: TourPersonaCode
    assumption: TourAssumptionCode
    guest_id: str | None = Field(default=None, max_length=64)
    questionnaire: TourQuestionnaire = Field(default_factory=TourQuestionnaire)
    resume_state: TourResumeState = Field(default_factory=TourResumeState)

    @model_validator(mode="after")
    def validate_persona_identity(self):
        if self.interest_type != self.persona:
            raise ValueError("interest_type must match persona")
        return self


class TourSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_hall: str | None = None
    current_exhibit_id: str | None = Field(default=None, max_length=36)
    status: Literal["onboarding", "opening", "touring", "completed"] | None = None
    interest_type: TourPersonaCode | None = None
    persona: TourPersonaCode | None = None
    assumption: TourAssumptionCode | None = None
    questionnaire: TourQuestionnaire | None = None
    resume_state: TourResumeState | None = None
    hall_chat_history: dict[str, list[TourHallChatMessage]] | None = None
    tour_started_at: datetime | None = None
    expected_state_version: int | None = Field(default=None, ge=1)

    @field_validator("hall_chat_history")
    @classmethod
    def validate_hall_count(
        cls, value: dict[str, list[TourHallChatMessage]] | None
    ) -> dict[str, list[TourHallChatMessage]] | None:
        if value is not None and len(value) > 9:
            raise ValueError("hall_chat_history supports at most 9 halls")
        if value is not None and any(len(messages) > 30 for messages in value.values()):
            raise ValueError("each hall supports at most 30 messages")
        return value


class TourEventItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal[
        "exhibit_view", "exhibit_question", "exhibit_deep_dive",
        "hall_enter", "hall_leave", "assistant_answer", "tour_start",
    ]
    exhibit_id: str | None = Field(default=None, max_length=36)
    hall: str | None = Field(default=None, max_length=100)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    metadata: dict[str, str | bool | None] | None = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(
        cls,
        value: dict[str, str | bool | None] | None,
    ) -> dict[str, str | bool] | None:
        if value is None:
            return None
        limits = {
            "started_at": 64,
            "client_event_id": 120,
            "question_client_event_id": 120,
            "exhibit_name": 255,
            "view_source": 64,
            "message": 2_000,
            "question": 2_000,
            "answer": 4_000,
            "trace_id": 120,
            "exhibit_kind": 100,
            "is_ceramic_question": 5,
        }
        unknown = set(value) - set(limits)
        if unknown:
            raise ValueError(
                f"unsupported event metadata keys: {', '.join(sorted(unknown))}"
            )
        cleaned: dict[str, str | bool] = {}
        for key, item in value.items():
            if item is None:
                continue
            if key == "is_ceramic_question":
                if not isinstance(item, bool):
                    raise ValueError("metadata.is_ceramic_question must be boolean")
                cleaned[key] = item
                continue
            if not isinstance(item, str):
                raise ValueError(f"metadata.{key} must be a string")
            if len(item) > limits[key]:
                raise ValueError(f"metadata.{key} is too long")
            cleaned[key] = item
        return cleaned

    @model_validator(mode="after")
    def validate_tour_start_metadata(self):
        if self.event_type == "tour_start":
            value = (self.metadata or {}).get("started_at")
            if not value:
                raise ValueError("tour_start metadata.started_at is required")
            try:
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("tour_start metadata.started_at must be ISO 8601") from exc
        return self


class TourEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TourEventItem] = Field(..., min_length=1, max_length=50)


class TourChatStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_length: Literal["brief", "balanced", "detailed"] | None = None
    depth: Literal["introductory", "standard", "deep"] | None = None
    terminology: Literal["plain", "professional", "academic"] | None = None


class TourChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=1000)


class TourChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]
    hall_id: str | None = Field(default=None, max_length=100)
    exhibit_id: str | None = Field(default=None, max_length=36)
    # Deprecated compatibility fields. They are accepted during the mini-program
    # migration but never used as museum facts or system-level instructions.
    exhibit_context: str | None = Field(default=None, max_length=1200)
    client_event_id: str | None = Field(default=None, max_length=120)
    style: TourChatStyle | None = None
    client_context: str | None = Field(default=None, max_length=1500)
    conversation_history: list[TourChatHistoryItem] | None = Field(default=None, max_length=30)
    tts: bool = False


class TourHallItem(BaseModel):
    slug: str
    name: str
    description: str
    short_description: str = Field(max_length=TOUR_HALL_CARD_DESCRIPTION_MAX_LENGTH)
    card_description: str = Field(max_length=TOUR_HALL_CARD_DESCRIPTION_MAX_LENGTH)
    exhibit_count: int
    estimated_duration_minutes: int
    highlights: list[str] = Field(default_factory=list, max_length=3)
    focus: str = Field(default="", max_length=TOUR_HALL_FOCUS_MAX_LENGTH)


class TourHallListResponse(BaseModel):
    halls: list[TourHallItem]


class TourSuggestionResponse(BaseModel):
    hall_id: str | None
    exhibit_id: str | None
    persona: TourPersonaCode
    suggestions: list[
        Annotated[
            str,
            StringConstraints(
                min_length=SUGGESTION_MIN_LENGTH,
                max_length=SUGGESTION_MAX_LENGTH,
            ),
        ]
    ]
    source: Literal["exhibit", "hall", "deterministic"]


SUGGESTION_PERSONAS = {"default", "A", "B", "C", "D"}


def _short_hall_focus(description: str | None) -> str:
    return str(description or "").strip()[:TOUR_HALL_FOCUS_MAX_LENGTH]


def _hall_card_description(hall: Hall) -> str:
    concise = re.sub(r"\s+", " ", str(hall.short_description or "")).strip()
    if concise:
        return concise[:TOUR_HALL_CARD_DESCRIPTION_MAX_LENGTH]

    slug = normalize_hall(hall.slug)
    if slug not in CANONICAL_HALL_SLUGS:
        return UNKNOWN_HALL_CARD_DESCRIPTION

    description = re.sub(r"\s+", " ", str(hall.description or "")).strip()
    if not description:
        return UNKNOWN_HALL_CARD_DESCRIPTION
    first_clause = re.split(r"[，。；！？]", description, maxsplit=1)[0].strip()
    return (first_clause or description)[:TOUR_HALL_CARD_DESCRIPTION_MAX_LENGTH]


async def _load_tour_halls(session: SessionDep) -> list[TourHallItem]:
    """Load active halls from persisted museum data without synthetic fallback."""
    stmt = (
        select(Hall)
        .where(
            Hall.slug.in_(CANONICAL_HALL_SLUGS),
            Hall.is_active.is_(True),
        )
        .order_by(Hall.display_order.asc(), Hall.created_at.asc())
    )
    result = await session.execute(stmt)
    hall_rows = list(result.scalars().all())

    if hall_rows:
        items: list[TourHallItem] = []
        for hall in hall_rows:
            card_description = _hall_card_description(hall)
            items.append(TourHallItem(
                slug=normalize_hall(hall.slug) or hall.slug,
                name=hall.name,
                description=hall.description or "",
                short_description=card_description,
                card_description=card_description,
                exhibit_count=0,
                estimated_duration_minutes=hall.estimated_duration_minutes,
                focus=_short_hall_focus(hall.description),
            ))
        return items

    return []


async def _load_hall_name_map(session: SessionDep) -> dict[str, str]:
    result = await session.execute(
        select(Hall.slug, Hall.name).where(
            Hall.slug.in_(CANONICAL_HALL_SLUGS),
            Hall.is_active.is_(True),
        )
    )
    return {
        normalized: str(name)
        for slug, name in result.all()
        if (normalized := normalize_hall(slug)) and str(name or "").strip()
    }


async def _verify_ownership(
    session_id: str,
    token: str | None,
    db_session,
):
    """Authorize a mini-program session exclusively by its guest token.

    A bearer token (including an administrator token) never grants access to a
    visitor session. This keeps admin authentication isolated from tour data.
    """
    if not token:
        raise HTTPException(status_code=403, detail="Session token required")
    try:
        return await verify_session_token(db_session, session_id, token)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    except TourSessionTokenMismatch:
        raise HTTPException(status_code=403, detail="Invalid session token") from None
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired") from None


def _format_session(tour_session) -> dict:
    eid = tour_session.current_exhibit_id
    uid = tour_session.user_id
    last_active_at = tour_session.last_active_at
    if last_active_at.tzinfo is None:
        last_active_at = last_active_at.replace(tzinfo=UTC)
    tour_started_at = tour_session.tour_started_at
    if tour_started_at is not None and tour_started_at.tzinfo is None:
        tour_started_at = tour_started_at.replace(tzinfo=UTC)
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
        "tour_started_at": tour_started_at.isoformat() if tour_started_at else None,
        "questionnaire": tour_session.questionnaire or {},
        "resume_state": tour_session.resume_state or {},
        "hall_chat_history": tour_session.hall_chat_history or {},
        "state_version": tour_session.state_version,
        "last_active_at": last_active_at.isoformat(),
        "expires_at": (
            last_active_at + timedelta(hours=SESSION_EXPIRY_HOURS)
        ).isoformat(),
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
) -> str | None:
    eid = str(exhibit_id or "").strip()
    if not eid or eid.startswith("local-") or eid.startswith("mock-"):
        return None

    exhibit = await session.get(Exhibit, eid)
    if exhibit is None or not exhibit.is_active:
        return None

    parts = [f"名称：{exhibit.name}"]
    hall_slug = normalize_hall(exhibit.hall)
    hall_row = await session.get(Hall, hall_slug) if hall_slug else None
    if (
        hall_slug not in CANONICAL_HALL_SLUGS
        or hall_row is None
        or not hall_row.is_active
    ):
        return None
    parts.append(f"展厅：{hall_row.name}")
    if exhibit.category:
        parts.append(f"类别：{exhibit.category}")
    if exhibit.era:
        parts.append(f"年代：{exhibit.era}")
    if exhibit.description:
        parts.append(f"简介：{str(exhibit.description).strip()[:600]}")
    return "\n".join(parts)[:1200]


def _compact_exhibit_match_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", normalized)


def _mentions_distinct_exhibit_names(
    message_key: str,
    mentions: list[tuple[Exhibit, str]],
) -> bool:
    """Detect separately written names, including one name nested in another."""
    spans_by_name = {
        name: [(match.start(), match.end()) for match in re.finditer(re.escape(name), message_key)]
        for _, name in mentions
    }
    for index, (_, first_name) in enumerate(mentions):
        for _, second_name in mentions[index + 1 :]:
            if first_name == second_name:
                continue
            if any(
                first_end <= second_start or second_end <= first_start
                for first_start, first_end in spans_by_name[first_name]
                for second_start, second_end in spans_by_name[second_name]
            ):
                return True
    return False


def _ambiguous_exhibit_message(subject: str, exhibits: list[Exhibit]) -> str:
    names = []
    for exhibit in exhibits:
        name = str(exhibit.name or "").strip()[:24]
        if name and name not in names:
            names.append(name)
        if len(names) >= 3:
            break
    choices = "、".join(f"“{name}”" for name in names)
    return (
        f"你提到的名称可能对应{choices}。"
        "请说完整名称，或点“搜展品”选择。"
    )


_SELECTED_EXHIBIT_REFERENCE_TOKEN = (
    r"(?:当前)?(?:它(?!们)|这个|那个|这件(?:展品|文物|器物)?|"
    r"那件(?:展品|文物|器物)?|该件(?:展品|文物|器物)?|"
    r"此件(?:展品|文物|器物)?)"
)
_SELECTED_EXHIBIT_COMPARISON_CONNECTOR = (
    r"(?:相较于|相对于|相比于|相比|对比|比较|还是|或者|以及|"
    r"和|与|跟|同|及|比|或|"
    r"vs|VS|、|，|,|/|&|\+|＋)"
)
_SELECTED_EXHIBIT_COMPARISON_REFERENCE_TAIL = (
    r"(?=\s*(?:$|[？?。！!,，；;]|有(?:什么|何|啥)(?:区别|不同)|"
    r"哪里不同|相比|比较|对比|哪个|哪一个|哪件|谁|分别|各自?|都|"
    r"是什么关系|有(?:什么|何|啥)关系|"
    r"(?:是|是否(?:是)?|是不是)同一(?:件|个)(?:展品|文物|器物)?|"
    r"更|较|比|呢|吗))"
)
_SELECTED_EXHIBIT_COMPARISON_REFERENCE_LEFT = re.compile(
    rf"{_SELECTED_EXHIBIT_REFERENCE_TOKEN}"
    rf"(?=\s*{_SELECTED_EXHIBIT_COMPARISON_CONNECTOR})"
)
_SELECTED_EXHIBIT_COMPARISON_REFERENCE_RIGHT = re.compile(
    rf"(?P<connector>{_SELECTED_EXHIBIT_COMPARISON_CONNECTOR})\s*"
    rf"{_SELECTED_EXHIBIT_REFERENCE_TOKEN}"
    rf"{_SELECTED_EXHIBIT_COMPARISON_REFERENCE_TAIL}"
)
_SELECTED_EXHIBIT_IDENTITY_REFERENCE_TOKEN = (
    r"(?:当前)?(?:它(?!们)|这个|那个|这件(?:展品|文物|器物)?|"
    r"那件(?:展品|文物|器物)?|该件(?:展品|文物|器物)?|"
    r"此件(?:展品|文物|器物)?|这|那)"
)
_SELECTED_EXHIBIT_IDENTITY_PREDICATE = (
    r"(?:到底)?(?:是不是叫|是否叫|是不是|是否是|不是|叫做|名叫|叫|是)"
)
_SELECTED_EXHIBIT_IDENTITY_REFERENCE_LEFT = re.compile(
    rf"{_SELECTED_EXHIBIT_IDENTITY_REFERENCE_TOKEN}"
    rf"(?=\s*{_SELECTED_EXHIBIT_IDENTITY_PREDICATE})"
)
_SELECTED_EXHIBIT_IDENTITY_REFERENCE_RIGHT = re.compile(
    rf"(?P<predicate>{_SELECTED_EXHIBIT_IDENTITY_PREDICATE})\s*"
    rf"{_SELECTED_EXHIBIT_IDENTITY_REFERENCE_TOKEN}"
    rf"(?=\s*(?:吗|呢|吧|[？?]|$))"
)
_UNRESOLVED_PLURAL_COMPARISON_REFERENCE = re.compile(
    rf"(?:它们|这些|那些|这(?:两|几)件|那(?:两|几)件|"
    rf"这两个|那两个)(?=\s*{_SELECTED_EXHIBIT_COMPARISON_CONNECTOR})"
    rf"|{_SELECTED_EXHIBIT_COMPARISON_CONNECTOR}\s*"
    rf"(?:它们|这些|那些|这(?:两|几)件|那(?:两|几)件|这两个|那两个)"
    rf"{_SELECTED_EXHIBIT_COMPARISON_REFERENCE_TAIL}"
)
_UNRESOLVED_PLURAL_COMPARISON_MESSAGE = (
    "我还不知道你说的“它们”指哪些展品。请说展品名称，或先点“搜展品”选择。"
)
_UNRESOLVED_DEICTIC_COMPARISON_MESSAGE = (
    "我还不知道你要比较的另一件展品。请说展品名称，或先点“搜展品”选择。"
)


def _rewrite_selected_exhibit_comparison(
    message: str,
    selected_exhibit_name: str,
) -> str | None:
    """Resolve a comparison pronoun from the server-validated page selection."""
    name = str(selected_exhibit_name or "").strip()
    if not name:
        return None
    normalized = unicodedata.normalize("NFKC", str(message or ""))
    rewritten, replacements = _SELECTED_EXHIBIT_COMPARISON_REFERENCE_LEFT.subn(
        name,
        normalized,
        count=1,
    )
    if not replacements:
        rewritten, replacements = _SELECTED_EXHIBIT_COMPARISON_REFERENCE_RIGHT.subn(
            lambda match: f"{match.group('connector')}{name}",
            normalized,
            count=1,
        )
    return rewritten if replacements else None


def _rewrite_selected_exhibit_identity(
    message: str,
    selected_exhibit_name: str,
) -> str | None:
    """Resolve a server-validated page pronoun in an identity/name check."""
    name = str(selected_exhibit_name or "").strip()
    if not name:
        return None
    normalized = unicodedata.normalize("NFKC", str(message or ""))
    rewritten, replacements = _SELECTED_EXHIBIT_IDENTITY_REFERENCE_LEFT.subn(
        name,
        normalized,
        count=1,
    )
    if not replacements:
        rewritten, replacements = _SELECTED_EXHIBIT_IDENTITY_REFERENCE_RIGHT.subn(
            lambda match: f"{match.group('predicate')}{name}",
            normalized,
            count=1,
        )
    return rewritten if replacements else None


async def _resolve_message_exhibit(
    session,
    hall_id: str | None,
    message: str,
) -> tuple[Exhibit | None, str | None, str | None]:
    """Resolve only an explicit, unique current-hall name; never trust rank."""
    hall = normalize_hall(hall_id)
    if hall and has_unresolved_deictic_comparison(message):
        return None, _UNRESOLVED_DEICTIC_COMPARISON_MESSAGE, "unknown"
    subject = _compact_exhibit_match_text(grounding_subject(message))
    if not hall or len(subject) < 2 or is_hall_level_question(message):
        return None, None, None

    result = await session.execute(
        select(Exhibit)
        .where(
            Exhibit.hall == hall,
            Exhibit.is_active.is_(True),
        )
        .order_by(
            Exhibit.display_order.asc().nulls_last(),
            Exhibit.importance.desc(),
            Exhibit.created_at.asc(),
            Exhibit.id.asc(),
        )
    )
    exhibits = list(result.scalars().all())
    if not exhibits:
        return None, None, None

    message_key = _compact_exhibit_match_text(message)
    exact_mentions = [
        (exhibit, _compact_exhibit_match_text(exhibit.name))
        for exhibit in exhibits
        if _compact_exhibit_match_text(exhibit.name)
        and _compact_exhibit_match_text(exhibit.name) in message_key
    ]
    if exact_mentions:
        if _UNRESOLVED_PLURAL_COMPARISON_REFERENCE.search(message):
            return None, _UNRESOLVED_PLURAL_COMPARISON_MESSAGE, "unknown"
        if _mentions_distinct_exhibit_names(message_key, exact_mentions):
            # This is a comparison/multi-object question. Do not collapse it
            # onto the longest name; let the normal clear-question RAG path
            # answer with both explicitly named objects in the query.
            return None, None, "multi"
        longest = max(len(name) for _, name in exact_mentions)
        longest_matches = [
            exhibit for exhibit, name in exact_mentions if len(name) == longest
        ]
        longest_name = next(
            name for _, name in exact_mentions if len(name) == longest
        )
        names_are_nested = all(
            name in longest_name for _, name in exact_mentions
        )
        if len(longest_matches) == 1 and names_are_nested:
            return longest_matches[0], None, "single"
        if not names_are_nested:
            return None, None, "multi"
        return None, _ambiguous_exhibit_message(subject, longest_matches), "unknown"

    categories = {
        category
        for exhibit in exhibits
        if (category := _compact_exhibit_match_text(exhibit.category))
    }
    if subject in categories:
        return None, None, "unknown"

    partial_matches = [
        exhibit
        for exhibit in exhibits
        if subject in _compact_exhibit_match_text(exhibit.name)
    ]
    if len(partial_matches) == 1:
        return partial_matches[0], None, "single"
    if len(partial_matches) > 1:
        return None, _ambiguous_exhibit_message(subject, partial_matches), "unknown"
    return None, None, None


async def _resolve_chat_hall_context(session, hall_id: str | None) -> str | None:
    normalized = normalize_hall(hall_id)
    if not normalized:
        return None
    hall = await session.get(Hall, normalized)
    if hall is None or not hall.is_active or normalized not in CANONICAL_HALL_SLUGS:
        return None

    if is_temporary_hall(normalized):
        hall_name = hall.name
        count_stmt = select(func.count(Exhibit.id)).where(
            Exhibit.hall == normalized,
            Exhibit.is_active.is_(True),
        )
        active_count = int((await session.execute(count_stmt)).scalar_one() or 0)
        exhibit_stmt = (
            select(Exhibit)
            .where(
                Exhibit.hall == normalized,
                Exhibit.is_active.is_(True),
            )
            .order_by(
                Exhibit.display_order.asc().nulls_last(),
                Exhibit.importance.desc(),
                Exhibit.created_at.asc(),
                Exhibit.id.asc(),
            )
            .limit(6)
        )
        exhibits = list((await session.execute(exhibit_stmt)).scalars().all())
        dynamic_description = temporary_hall_description(
            hall.description,
            [item.name for item in exhibits],
            exhibit_count=active_count,
        )
        parts = [f"{hall_name}：{dynamic_description}"]
        for exhibit in exhibits:
            facts = [f"展品：{exhibit.name}"]
            if exhibit.category:
                facts.append(f"类别：{exhibit.category}")
            if exhibit.era:
                facts.append(f"年代：{exhibit.era}")
            if exhibit.description:
                facts.append(f"简介：{str(exhibit.description).strip()[:220]}")
            parts.append("；".join(facts))
        return "\n".join(parts)[:1000]

    return f"{hall.name}：{str(hall.description or '').strip()}"[:1000]


def _validated_hall_chat_history(value: dict | None) -> dict[str, list[dict[str, str]]]:
    normalized: dict[str, list[dict[str, str]]] = {}
    for raw_hall, raw_messages in (value or {}).items():
        raw_hall_slug = str(raw_hall).strip()
        hall = normalize_hall(raw_hall_slug)
        if (
            not hall
            or raw_hall_slug != hall
            or hall not in CANONICAL_HALL_SLUGS
        ):
            raise HTTPException(
                status_code=422,
                detail="hall_chat_history keys must be canonical hall slugs",
            )
        messages = []
        for raw in list(raw_messages or [])[-30:]:
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump()
            role = str((raw or {}).get("role") or "")
            content = str((raw or {}).get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[:1000]})
        normalized[hall] = messages
    return normalized


def _normalized_questionnaire(
    value: TourQuestionnaire | dict | None,
    *,
    persona: TourPersonaCode,
    assumption: TourAssumptionCode,
) -> dict:
    if hasattr(value, "model_dump"):
        normalized = value.model_dump(mode="json", exclude_none=True)
    else:
        normalized = dict(value or {})
    raw_persona = normalized.get("persona_id")
    if raw_persona is not None and raw_persona != persona:
        raise HTTPException(
            status_code=422,
            detail="questionnaire.persona_id must match persona",
        )
    if normalized.get("assumption") not in {None, assumption}:
        raise HTTPException(
            status_code=422,
            detail="questionnaire.assumption must match assumption",
        )
    normalized["persona_id"] = raw_persona or persona
    normalized["assumption"] = assumption
    return normalized


def _normalized_resume_state(
    value: TourResumeState | dict | None,
    *,
    persona: TourPersonaCode,
    assumption: TourAssumptionCode,
) -> dict:
    if hasattr(value, "model_dump"):
        normalized = value.model_dump(mode="json", exclude_none=True)
    else:
        normalized = dict(value or {})
    if normalized.get("persona") not in {None, persona}:
        raise HTTPException(status_code=422, detail="resume_state.persona must match persona")
    raw_persona_id = normalized.get("persona_id")
    if raw_persona_id not in {None, persona}:
        raise HTTPException(status_code=422, detail="resume_state.persona_id must match persona")
    if normalized.get("assumption") not in {None, assumption}:
        raise HTTPException(status_code=422, detail="resume_state.assumption must match assumption")
    if normalized.get("questionnaire") is not None:
        normalized["questionnaire"] = _normalized_questionnaire(
            normalized["questionnaire"], persona=persona, assumption=assumption
        )
    return normalized


def _parsed_tour_started_at(value) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid tour_started_at") from exc
    if not isinstance(value, datetime):
        raise HTTPException(status_code=422, detail="Invalid tour_started_at")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def _validated_tour_started_at(value) -> datetime:
    value = _parsed_tour_started_at(value)
    now = datetime.now(UTC)
    if value < now - timedelta(hours=SESSION_EXPIRY_HOURS):
        raise HTTPException(status_code=422, detail="tour_started_at exceeds the 24-hour restoration window")
    if value > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="tour_started_at is in the future")
    return value


def _collect_visited_halls(tour_session=None, events=None) -> list[str]:
    candidates: list[str] = []
    clarification_keys = clarification_question_keys(events)
    for event in events or []:
        if is_clarification_event(event, clarification_keys):
            continue
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


def _build_report_highlights(report, _halls_visited: list[str]) -> list[str]:
    highlights: list[str] = []
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


def _build_record_summary_point(
    hall_text: str,
    question_text: str,
    answer_text: str,
) -> str:
    scope = f"在{hall_text}" if hall_text else "在本次参观中"
    questions = _compact_record_text(question_text, 150)
    answers = _compact_record_text(answer_text, 210)
    if answers:
        return _compact_record_text(
            f"{scope}，对话主题集中在：{questions}。现有记录中的关键结论包括：{answers}。",
            400,
        )
    return _compact_record_text(
        f"{scope}，对话主题集中在：{questions}。目前尚无完整回答可供提炼。",
        400,
    )


def _build_report_record_notes(
    events=None,
    persona: str | None = None,
    hall_name_map: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    answered_entries: list[dict[str, str]] = []
    question_entries: list[dict[str, str]] = []
    seen_answer_ids: set[str] = set()
    clarification_keys = clarification_question_keys(events)
    for event in events or []:
        event_type = getattr(event, "event_type", None)
        if event_type not in {"assistant_answer", "exhibit_question"}:
            continue
        metadata = getattr(event, "metadata", None) or {}
        if is_clarification_event(event, clarification_keys):
            continue
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
        hall_name = (
            (hall_name_map or {}).get(entry["hall"])
            if entry["hall"]
            else ""
        )
        if hall_name and hall_name not in hall_names:
            hall_names.append(hall_name)
    hall_text = "、".join(hall_names)
    questions_text = "”“".join(entry["question"] for entry in entries)
    answer_text = " ".join(entry["answer"] for entry in entries if entry["answer"])
    point = _build_record_summary_point(hall_text, questions_text, answer_text)
    return [{"question": "游览记录摘要", "point": point}]


def _format_report(
    report,
    tour_session=None,
    events=None,
    hall_name_map: dict[str, str] | None = None,
) -> dict:
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
            hall_name_map=hall_name_map,
        )
        if tour_session is not None
        else None
    )
    exploration_guidance = (
        build_exploration_guidance(
            tour_session,
            events or [],
            reflection=reflection,
            hall_name_map=hall_name_map,
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
        record_notes = _build_report_record_notes(
            events,
            getattr(tour_session, "persona", None),
            hall_name_map,
        )
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
        "exploration_guidance": exploration_guidance,
        "created_at": report.created_at.isoformat(),
    }


@router.post("/sessions", summary="Create tour session")
async def create_tour_session(
    body: TourSessionCreate,
    _create_rate_limit: TourSessionCreateRateLimitDep,
    session: SessionDep,
):
    guest_id = (body.guest_id or "").strip()[:64] or f"miniapp-{uuid.uuid4()}"
    questionnaire = _normalized_questionnaire(
        body.questionnaire, persona=body.persona, assumption=body.assumption
    )
    resume_state = _normalized_resume_state(
        body.resume_state, persona=body.persona, assumption=body.assumption
    )
    tour_started_at = (
        _validated_tour_started_at(body.resume_state.tour_started_at)
        if body.resume_state.tour_started_at is not None
        else None
    )
    tour_session = await create_session(
        session,
        interest_type=body.interest_type,
        persona=body.persona,
        assumption=body.assumption,
        user_id=None,
        guest_id=guest_id,
        questionnaire=questionnaire,
        resume_state=resume_state,
        tour_started_at=tour_started_at,
    )
    return _format_session(tour_session)


@router.get("/sessions/{session_id}", summary="Get tour session")
async def get_tour_session(
    session_id: str,
    session: SessionDep,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, x_session_token, session)
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
    _write_rate_limit: TourSessionWriteRateLimitDep,
    session: SessionDep,
    x_session_token: str | None = Header(None),
):
    owned_session = await _verify_ownership(session_id, x_session_token, session)
    raw = await request.body()
    if len(raw) > MAX_SESSION_STATE_PATCH_BYTES:
        raise HTTPException(status_code=413, detail="Session state patch is too large")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="Invalid JSON body") from None
    try:
        body = TourSessionUpdate.model_validate(data)
    except PydanticValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from None
    body_data = body.model_dump(mode="json")
    updates = {k: body_data[k] for k in body.model_fields_set}
    expected_state_version = updates.pop("expected_state_version", None)
    if "persona" in updates or "interest_type" in updates:
        requested_persona = updates.get("persona", updates.get("interest_type"))
        if requested_persona is None:
            raise HTTPException(status_code=422, detail="persona cannot be null")
        if (
            "persona" in updates
            and "interest_type" in updates
            and updates["persona"] != updates["interest_type"]
        ):
            raise HTTPException(status_code=422, detail="interest_type must match persona")
        if requested_persona not in {owned_session.persona, owned_session.interest_type}:
            raise HTTPException(
                status_code=422,
                detail="persona is immutable; create a new tour session",
            )
        updates["persona"] = requested_persona
        updates["interest_type"] = requested_persona
    if "assumption" in updates and updates["assumption"] is None:
        raise HTTPException(status_code=422, detail="assumption cannot be null")
    effective_persona = updates.get("persona", owned_session.persona)
    effective_assumption = updates.get("assumption", owned_session.assumption)
    if {"persona", "assumption", "questionnaire"} & updates.keys():
        updates["questionnaire"] = _normalized_questionnaire(
            updates.get("questionnaire", owned_session.questionnaire),
            persona=effective_persona,
            assumption=effective_assumption,
        )
    if "resume_state" in updates:
        updates["resume_state"] = _normalized_resume_state(
            updates["resume_state"],
            persona=effective_persona,
            assumption=effective_assumption,
        )
    valid_halls: set[str] | None = None
    if "current_hall" in updates and updates["current_hall"] is not None:
        updates["current_hall"] = normalize_hall(updates["current_hall"])
        valid_halls = {
            slug
            for h in await _load_tour_halls(session)
            if (slug := normalize_hall(h.slug))
        }
        if not updates["current_hall"] or updates["current_hall"] not in valid_halls:
            raise HTTPException(status_code=422, detail="Unknown current_hall")
    effective_exhibit_id = updates.get(
        "current_exhibit_id", owned_session.current_exhibit_id
    )
    if hasattr(effective_exhibit_id, "value"):
        effective_exhibit_id = effective_exhibit_id.value
    effective_exhibit_id = str(effective_exhibit_id or "").strip()
    if effective_exhibit_id:
        if valid_halls is None:
            valid_halls = {
                slug
                for h in await _load_tour_halls(session)
                if (slug := normalize_hall(h.slug))
            }
        exhibit = await session.get(Exhibit, effective_exhibit_id)
        if exhibit is None or not exhibit.is_active:
            raise HTTPException(
                status_code=422,
                detail="Unknown or inactive current_exhibit_id",
            )
        exhibit_hall = normalize_hall(exhibit.hall)
        if exhibit_hall not in valid_halls:
            raise HTTPException(
                status_code=422,
                detail="current_exhibit_id is outside an active tour hall",
            )
        effective_hall = normalize_hall(
            updates.get("current_hall", owned_session.current_hall)
        )
        if effective_hall and exhibit_hall != effective_hall:
            raise HTTPException(
                status_code=422,
                detail="current_exhibit_id does not belong to current_hall",
            )
    if "hall_chat_history" in updates:
        updates["hall_chat_history"] = _validated_hall_chat_history(
            updates["hall_chat_history"]
        )
    if "tour_started_at" in updates and updates["tour_started_at"] is not None:
        if owned_session.tour_started_at is not None:
            requested_start = _parsed_tour_started_at(updates["tour_started_at"])
            current_start = owned_session.tour_started_at
            if current_start.tzinfo is None:
                current_start = current_start.replace(tzinfo=UTC)
            if abs((requested_start - current_start).total_seconds()) > 1:
                raise HTTPException(status_code=409, detail="tour_started_at is immutable")
            updates.pop("tour_started_at")
        else:
            updates["tour_started_at"] = _validated_tour_started_at(
                updates["tour_started_at"]
            )
    try:
        tour_session = await update_session(
            session,
            session_id,
            expected_state_version=expected_state_version,
            **updates,
        )
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None
    except TourSessionExpired:
        raise HTTPException(status_code=410, detail="Tour session expired") from None
    except TourSessionStateConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STATE_VERSION_CONFLICT",
                "message": str(exc),
                "expected_state_version": exc.expected_state_version,
                "current_state_version": exc.current_state_version,
            },
        ) from None
    return _format_session(tour_session)


@router.post("/sessions/{session_id}/events", summary="Record tour events")
async def post_tour_events(
    session_id: str,
    body: TourEventBatch,
    _write_rate_limit: TourSessionWriteRateLimitDep,
    session: SessionDep,
    x_session_token: str | None = Header(None),
):
    tour_session = await _verify_ownership(session_id, x_session_token, session)
    payload_events = [e.model_dump() for e in body.events]
    valid_halls = {
        normalize_hall(hall.slug)
        for hall in await _load_tour_halls(session)
        if normalize_hall(hall.slug)
    }
    exhibit_ids = {
        str(event.get("exhibit_id") or "").strip()
        for event in payload_events
        if event.get("exhibit_id")
    }
    if any(
        exhibit_id.startswith(("local-", "mock-"))
        for exhibit_id in exhibit_ids
    ):
        raise HTTPException(status_code=422, detail="Local exhibit IDs cannot be recorded")
    exhibit_by_id: dict[str, Exhibit] = {}
    if exhibit_ids:
        result = await session.execute(
            select(Exhibit).where(Exhibit.id.in_(exhibit_ids))
        )
        exhibit_by_id = {str(exhibit.id): exhibit for exhibit in result.scalars().all()}

    for event in payload_events:
        if event.get("hall"):
            event["hall"] = normalize_hall(event["hall"])
            if not event["hall"] or event["hall"] not in valid_halls:
                raise HTTPException(status_code=422, detail="Unknown event hall")
        exhibit_id = str(event.get("exhibit_id") or "").strip()
        if not exhibit_id:
            continue
        exhibit = exhibit_by_id.get(exhibit_id)
        if exhibit is None or not exhibit.is_active:
            raise HTTPException(status_code=422, detail="Unknown or inactive event exhibit_id")
        exhibit_hall = normalize_hall(exhibit.hall)
        if exhibit_hall not in valid_halls:
            raise HTTPException(
                status_code=422,
                detail="event exhibit_id is outside an active tour hall",
            )
        if event.get("hall") and exhibit_hall != event["hall"]:
            raise HTTPException(
                status_code=422,
                detail="event exhibit_id does not belong to event hall",
            )
        if not event.get("hall"):
            event["hall"] = exhibit_hall
    if any(event["event_type"] == "tour_start" for event in payload_events):
        if tour_session.tour_started_at is None:
            start_event = next(
                event for event in payload_events if event["event_type"] == "tour_start"
            )
            start_at = _validated_tour_started_at(
                (start_event.get("metadata") or {}).get("started_at")
            )
            await update_session(
                session,
                session_id,
                tour_started_at=start_at,
                status="touring",
            )
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
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, x_session_token, session)
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
    _write_rate_limit: TourSessionWriteRateLimitDep,
    session: SessionDep,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, x_session_token, session)
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
    all_visited = bool(all_halls) and all(h in visited_halls for h in all_halls)

    new_status = "touring"
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
    _report_rate_limit: TourReportRateLimitDep,
    session: SessionDep,
    llm_provider: LLMProviderDep,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, x_session_token, session)

    try:
        tour_session = await get_session(session, session_id)
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None

    hall_name_map = await _load_hall_name_map(session)
    try:
        report = await generate_report(
            session,
            session_id,
            hall_name_map=hall_name_map,
            llm_provider=llm_provider,
        )
    except TourSessionNotFound:
        raise HTTPException(status_code=404, detail="Tour session not found") from None

    events = await get_events_by_session(session, session_id)
    return _format_report(
        report,
        tour_session=tour_session,
        events=events,
        hall_name_map=hall_name_map,
    )


@router.get("/sessions/{session_id}/report", summary="Get tour report")
async def get_tour_report(
    session_id: str,
    _report_rate_limit: TourReportRateLimitDep,
    session: SessionDep,
    llm_provider: LLMProviderDep,
    x_session_token: str | None = Header(None),
):
    await _verify_ownership(session_id, x_session_token, session)
    report = await get_report(session, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found") from None
    hall_name_map = await _load_hall_name_map(session)
    report = await generate_report(
        session,
        session_id,
        hall_name_map=hall_name_map,
        llm_provider=llm_provider,
    )
    try:
        tour_session = await get_session(session, session_id)
        events = await get_events_by_session(session, session_id)
    except TourSessionNotFound:
        tour_session = None
        events = []
    return _format_report(
        report,
        tour_session=tour_session,
        events=events,
        hall_name_map=hall_name_map,
    )


@router.post("/sessions/{session_id}/chat/stream", summary="Stream tour chat (SSE)")
async def tour_chat_stream(
    session_id: str,
    body: TourChatRequest,
    request: Request,
    _chat_rate_limit: TourChatRateLimitDep,
    session: SessionDep,
    session_maker: SessionMakerDep,
    rag_agent: RagAgentDep,
    llm_provider: LLMProviderDep,
    x_session_token: str | None = Header(None),
):
    tour_session = await _verify_ownership(session_id, x_session_token, session)

    degraded = set()
    if hasattr(request.app.state, "degraded"):
        degraded = set(request.app.state.degraded)

    tts_provider = getattr(request.app.state, "tts_provider", None)
    tts_service = getattr(request.app.state, "tts_service", None)

    # Resolve persona for TTS config
    persona = None
    if body.tts:
        try:
            persona = tour_session.persona
        except (TourSessionNotFound, TourSessionExpired):
            pass  # Will fall back to session persona in ask_stream_tour

    requested_hall = normalize_hall(body.hall_id)
    trusted_hall = normalize_hall(tour_session.current_hall)
    valid_halls = {
        slug
        for hall in await _load_tour_halls(session)
        if (slug := normalize_hall(hall.slug))
    }
    exhibit_row = None
    requested_exhibit_id = str(body.exhibit_id or "").strip()
    if requested_exhibit_id and not requested_exhibit_id.startswith(("local-", "mock-")):
        exhibit_row = await session.get(Exhibit, requested_exhibit_id)
        if exhibit_row is None or not exhibit_row.is_active:
            raise HTTPException(status_code=422, detail="Unknown exhibit_id")
        exhibit_hall = normalize_hall(exhibit_row.hall)
        if exhibit_hall not in valid_halls:
            raise HTTPException(status_code=422, detail="Unknown exhibit_id")
        if requested_hall and requested_hall != exhibit_hall:
            raise HTTPException(status_code=422, detail="exhibit_id does not belong to hall_id")
        requested_hall = exhibit_hall

    effective_hall = requested_hall or trusted_hall
    if effective_hall and effective_hall not in valid_halls:
        raise HTTPException(status_code=422, detail="Unknown hall_id")

    selected_exhibit_row = exhibit_row
    turn_exhibit_row = selected_exhibit_row
    clarification_message = None
    subject_scope_hint = "single" if selected_exhibit_row is not None else None
    resolved_message = None
    (
        message_exhibit_row,
        message_clarification,
        message_subject_scope,
    ) = await _resolve_message_exhibit(
        session,
        effective_hall,
        body.message,
    )
    if message_subject_scope is not None:
        selected_comparison = None
        selected_identity = None
        if (
            selected_exhibit_row is not None
            and message_exhibit_row is not None
            and message_exhibit_row.id != selected_exhibit_row.id
        ):
            selected_comparison = _rewrite_selected_exhibit_comparison(
                body.message,
                selected_exhibit_row.name,
            )
            if not selected_comparison:
                selected_identity = _rewrite_selected_exhibit_identity(
                    body.message,
                    selected_exhibit_row.name,
                )
        if selected_comparison:
            # The page selection identifies the pronoun and the typed name
            # identifies the other object.  Use an explicit trusted query for
            # this turn, but do not turn either object into a single binding.
            turn_exhibit_row = None
            clarification_message = None
            subject_scope_hint = "multi"
            resolved_message = selected_comparison
        elif selected_identity:
            # "Is this A actually B?" is about the page-selected object A.
            # Keep A as the single turn binding and use B only in the resolved
            # question; otherwise the explicit B name would silently replace A.
            turn_exhibit_row = selected_exhibit_row
            clarification_message = None
            subject_scope_hint = "single"
            resolved_message = selected_identity
        else:
            turn_exhibit_row = message_exhibit_row
            clarification_message = message_clarification
            subject_scope_hint = message_subject_scope

    session_updates: dict[str, str | None] = {}
    if requested_hall:
        if requested_hall != trusted_hall:
            session_updates["current_hall"] = requested_hall
            # A hall switch without a trusted exhibit must not retain the
            # previous hall's foreign key.
            session_updates["current_exhibit_id"] = (
                selected_exhibit_row.id
                if requested_exhibit_id and selected_exhibit_row is not None
                else None
            )
        elif requested_exhibit_id and selected_exhibit_row is not None:
            session_updates["current_exhibit_id"] = selected_exhibit_row.id
        elif requested_exhibit_id:
            session_updates["current_exhibit_id"] = None
        session_updates["status"] = "touring"

    if session_updates:
        tour_session = await update_session(
            session,
            session_id,
            **session_updates,
        )
    trusted_exhibit_id = turn_exhibit_row.id if turn_exhibit_row is not None else None
    exhibit_context = await _resolve_chat_exhibit_context(
        session,
        trusted_exhibit_id,
    )
    hall_context = await _resolve_chat_hall_context(
        session, tour_session.current_hall
    )
    current_hall_key = normalize_hall(tour_session.current_hall) or ""
    raw_trusted_history = (tour_session.trusted_hall_chat_history or {}).get(
        current_hall_key, []
    )
    conversation_history = bound_conversation_history(raw_trusted_history)
    grounding_history = bound_grounding_history(raw_trusted_history)
    # Client-restored/display history is intentionally excluded from model
    # inference. Only completed server-persisted turns may ground follow-ups or
    # enter the prompt/retrieval rewrite history.

    # The dependency-scoped session otherwise remains checked out for the full
    # SSE lifetime.  Everything the stream needs is now a detached snapshot;
    # later trusted-data checks use their own short-lived sessions.
    await session.commit()

    return StreamingResponse(
        ask_stream_tour(
            db_session=None,
            session_maker=session_maker,
            tour_session_id=session_id,
            message=body.message,
            rag_agent=rag_agent,
            llm_provider=llm_provider,
            exhibit_id=trusted_exhibit_id,
            exhibit_context=exhibit_context,
            hall_context=hall_context,
            subject_scope_hint=subject_scope_hint,
            resolved_message=resolved_message,
            client_event_id=body.client_event_id,
            client_context=None,
            conversation_history=conversation_history or None,
            grounding_history=grounding_history or None,
            style=body.style,
            degraded_services=degraded,
            tts_provider=tts_provider if body.tts else None,
            tts_service=tts_service if body.tts else None,
            persona=persona,
            tour_session=tour_session,
            clarification_message=clarification_message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions/{session_id}/suggestions",
    response_model=TourSuggestionResponse,
    summary="Get deterministic data-driven suggestions",
)
async def get_tour_suggestions(
    session_id: str,
    session: SessionDep,
    x_session_token: str | None = Header(None),
    hall_id: str | None = None,
    exhibit_id: str | None = None,
):
    tour_session = await _verify_ownership(session_id, x_session_token, session)
    persona = tour_session.persona if tour_session.persona in SUGGESTION_PERSONAS else "default"

    normalized_hall = normalize_hall(hall_id or tour_session.current_hall)
    valid_halls = {
        normalize_hall(hall.slug)
        for hall in await _load_tour_halls(session)
        if normalize_hall(hall.slug)
    }
    if hall_id and normalized_hall not in valid_halls:
        raise HTTPException(status_code=422, detail="Unknown hall_id")
    if normalized_hall not in valid_halls:
        normalized_hall = None
    normalized_exhibit_id = str(exhibit_id or "").strip() or None
    suggestions: list[str] = []
    source: Literal["exhibit", "hall", "deterministic"] = "deterministic"

    if normalized_exhibit_id and not normalized_exhibit_id.startswith(("local-", "mock-")):
        exhibit = await session.get(Exhibit, normalized_exhibit_id)
        exhibit_hall = normalize_hall(exhibit.hall) if exhibit is not None else None
        if (
            exhibit is None
            or not exhibit.is_active
            or exhibit_hall not in valid_halls
        ):
            raise HTTPException(status_code=422, detail="Unknown exhibit_id")
        if normalized_hall and exhibit_hall != normalized_hall:
            raise HTTPException(
                status_code=422,
                detail="exhibit_id does not belong to hall_id",
            )
        suggestions = _quality_suggestions(exhibit.suggested_questions)
        if not suggestions:
            suggestions = _derive_exhibit_suggestions(
                exhibit.name,
                exhibit.description,
                exhibit.category,
            )
        if suggestions:
            source = "exhibit"
        normalized_hall = exhibit_hall

    if not suggestions and normalized_hall:
        if not is_temporary_hall(normalized_hall):
            hall = await session.get(Hall, normalized_hall)
            if hall is not None and hall.is_active:
                suggestions = _quality_suggestions(hall.suggested_questions)
                if suggestions:
                    source = "hall"

        if not suggestions:
            exhibit_stmt = (
                select(
                    Exhibit.name,
                    Exhibit.description,
                    Exhibit.category,
                    Exhibit.suggested_questions,
                )
                .where(
                    Exhibit.hall == normalized_hall,
                    Exhibit.is_active.is_(True),
                )
                .order_by(
                    Exhibit.display_order.asc().nulls_last(),
                    Exhibit.importance.desc(),
                    Exhibit.created_at.asc(),
                    Exhibit.id.asc(),
                )
            )
            active_exhibits = list((await session.execute(exhibit_stmt)).all())
            seen_questions: set[str] = set()
            for name, description, category, raw_questions in active_exhibits:
                exhibit_questions = _quality_suggestions(raw_questions)
                if not exhibit_questions:
                    exhibit_questions = _derive_exhibit_suggestions(
                        name,
                        description,
                        category,
                    )
                for question in exhibit_questions:
                    if question not in seen_questions:
                        seen_questions.add(question)
                        suggestions.append(question)
                    if len(suggestions) >= 6:
                        break
                if len(suggestions) >= 6:
                    break
            if suggestions:
                source = "exhibit"

    return TourSuggestionResponse(
        hall_id=normalized_hall,
        exhibit_id=normalized_exhibit_id,
        persona=persona,
        suggestions=suggestions,
        source=source,
    )


@router.get("/halls", summary="List tour halls")
async def list_tour_halls(
    session: SessionDep,
):
    hall_configs = await _load_tour_halls(session)
    hall_slugs = [normalize_hall(h.slug) for h in hall_configs if normalize_hall(h.slug)]
    if not hall_slugs:
        return TourHallListResponse(halls=[])

    stmt = (
        select(Exhibit.hall, Exhibit.name)
        .where(Exhibit.hall.in_(hall_slugs), Exhibit.is_active.is_(True))
        .order_by(
            Exhibit.hall.asc(),
            Exhibit.display_order.asc().nulls_last(),
            Exhibit.importance.desc(),
            Exhibit.created_at.asc(),
            Exhibit.id.asc(),
        )
    )
    result = await session.execute(stmt)
    counts: dict[str, int] = {}
    highlights: dict[str, list[str]] = {}
    for hall, exhibit_name in result.all():
        slug = normalize_hall(hall) or hall
        counts[slug] = counts.get(slug, 0) + 1
        hall_highlights = highlights.setdefault(slug, [])
        name = str(exhibit_name or "").strip()
        if name and len(hall_highlights) < 3:
            hall_highlights.append(name)

    halls = []
    seen = set()
    for h in hall_configs:
        slug = normalize_hall(h.slug) or h.slug
        if slug in seen:
            continue
        seen.add(slug)
        description = h.description
        if is_temporary_hall(slug):
            description = temporary_hall_description(
                h.description,
                highlights.get(slug, []),
                exhibit_count=counts.get(slug, 0),
            )
        halls.append(
            TourHallItem(
                slug=slug,
                name=h.name,
                description=description,
                short_description=h.short_description,
                card_description=h.card_description,
                exhibit_count=counts.get(slug, 0),
                estimated_duration_minutes=h.estimated_duration_minutes,
                highlights=highlights.get(slug, []),
                focus=_short_hall_focus(description),
            )
        )
    return TourHallListResponse(halls=halls)
