import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.tour_event_service import get_events_by_session
from app.application.tour_session_service import get_session
from app.domain.entities import TourReport
from app.infra.postgres.models import TourReportModel

CERAMIC_KEYWORDS = [
    "陶", "瓷", "盆", "罐", "瓶", "碗", "鼎", "甑", "釜", "纹",
    "彩陶", "人面鱼纹", "鱼纹", "几何纹", "绳纹", "尖底瓶",
    "红陶", "灰陶", "黑陶", "泥塑", "陶塑", "陶器", "瓷器",
    "素面", "刻划", "彩绘",
]

ONE_LINER_CANDIDATES = [
    "今天，我用AI唤醒了沉睡六千年的半坡先民",
    "我的博物馆向导来自公元前4000年",
    "没有文字的时代，他们把不朽的灵魂画在彩陶上",
    "凝视人面鱼纹盆的瞬间，六千年的风从浐河吹进了现实",
    "我们在泥土里寻找的不是瓦罐，而是六千年前祖宗的倒影",
    "半坡一日游达成：确认过了，如果回到6000年前，我的手艺只配负责吃",
    "懂了，六千年前的先民不内卷，每天研究怎么抓鱼和捏泥巴",
]

HARDCORE_TAGS = ["史前细节显微镜", "碎片重构大师", "冷酷无情的地层勘探机"]
FUN_TAGS = ["六千年前的干饭王", "母系氏族社交悍匪", "沉睡的部落大祭司"]
AESTHETIC_TAGS = ["史前第一眼光", "彩陶纹饰解码者", "被文物选中的人"]


def detect_ceramic_question(message: str) -> bool:
    return any(kw in message for kw in CERAMIC_KEYWORDS)


def calculate_radar_scores(stats: dict) -> dict:
    total_minutes = stats.get("total_duration_minutes", 0)
    total_questions = stats.get("total_questions", 0)
    total_exhibits = stats.get("total_exhibits_viewed", 0)
    site_hall_minutes = stats.get("site_hall_duration_minutes", 0)
    ceramic_q = stats.get("ceramic_questions", 0)

    civilization = 3 if total_minutes > 60 else (2 if total_minutes >= 30 else 1)
    imagination = 3 if total_questions > 15 else (2 if total_questions >= 10 else 1)
    history = 3 if total_exhibits > 10 else (2 if total_exhibits >= 5 else 1)
    lifestyle = 3 if site_hall_minutes > 20 else (2 if site_hall_minutes >= 10 else 1)
    aesthetics = 3 if ceramic_q >= 3 else (2 if ceramic_q >= 1 else 1)

    return {
        "civilization_resonance": civilization,
        "imagination_breadth": imagination,
        "history_collection": history,
        "life_experience": lifestyle,
        "ceramic_aesthetics": aesthetics,
    }


def select_identity_tags(radar_scores: dict) -> list[str]:
    tags = []

    civ = radar_scores.get("civilization_resonance", 1)
    hist = radar_scores.get("history_collection", 1)
    img = radar_scores.get("imagination_breadth", 1)
    life = radar_scores.get("life_experience", 1)
    aes = radar_scores.get("ceramic_aesthetics", 1)

    if civ == 3:
        tags.append(HARDCORE_TAGS[2])
    elif hist == 3:
        tags.append(HARDCORE_TAGS[1])
    else:
        tags.append(HARDCORE_TAGS[0])

    if img == 3:
        tags.append(FUN_TAGS[1])
    elif life == 3:
        tags.append(FUN_TAGS[2])
    else:
        tags.append(FUN_TAGS[0])

    if aes == 3:
        tags.append(AESTHETIC_TAGS[1])
    elif civ == 3:
        tags.append(AESTHETIC_TAGS[2])
    else:
        tags.append(AESTHETIC_TAGS[0])

    return tags


def get_report_theme(persona: str) -> str:
    return {"A": "archaeology", "B": "village", "C": "homework"}.get(persona, "archaeology")


def aggregate_stats(events: list, tour_session) -> dict:
    total_duration = 0.0
    if tour_session.started_at and tour_session.completed_at:
        total_duration = (tour_session.completed_at - tour_session.started_at).total_seconds() / 60.0
    elif tour_session.started_at:
        total_duration = (datetime.now(UTC) - tour_session.started_at).total_seconds() / 60.0

    exhibit_durations: dict[str, int] = {}
    hall_durations: dict[str, int] = {}
    total_questions = 0
    ceramic_questions = 0
    viewed_exhibits: set[str] = set()

    for event in events:
        if event.event_type == "exhibit_view" and event.exhibit_id and event.duration_seconds:
            eid = event.exhibit_id.value if hasattr(event.exhibit_id, 'value') else str(event.exhibit_id)
            exhibit_durations[eid] = exhibit_durations.get(eid, 0) + event.duration_seconds
            viewed_exhibits.add(eid)
        elif event.event_type == "hall_leave" and event.hall and event.duration_seconds:
            hall_durations[event.hall] = hall_durations.get(event.hall, 0) + event.duration_seconds
        elif event.event_type == "exhibit_question":
            total_questions += 1
            meta = event.metadata or {}
            if meta.get("is_ceramic_question"):
                ceramic_questions += 1

    most_viewed_exhibit_id = None
    most_viewed_exhibit_duration = None
    if exhibit_durations:
        top_eid = max(exhibit_durations, key=exhibit_durations.get)
        most_viewed_exhibit_id = top_eid
        most_viewed_exhibit_duration = exhibit_durations[top_eid]

    longest_hall = None
    longest_hall_duration = None
    if hall_durations:
        top_hall = max(hall_durations, key=hall_durations.get)
        longest_hall = top_hall
        longest_hall_duration = hall_durations[top_hall]

    site_hall_minutes = hall_durations.get("site-hall", 0) / 60.0

    return {
        "total_duration_minutes": round(total_duration, 1),
        "most_viewed_exhibit_id": most_viewed_exhibit_id,
        "most_viewed_exhibit_duration": most_viewed_exhibit_duration,
        "longest_hall": longest_hall,
        "longest_hall_duration": longest_hall_duration,
        "total_questions": total_questions,
        "total_exhibits_viewed": len(viewed_exhibits),
        "ceramic_questions": ceramic_questions,
        "site_hall_duration_minutes": round(site_hall_minutes, 1),
    }


async def generate_report(
    session: AsyncSession,
    tour_session_id: str,
    llm_provider: Any = None,
) -> TourReport:
    stmt = select(TourReportModel).where(TourReportModel.tour_session_id == tour_session_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        return existing.to_entity()

    tour_session = await get_session(session, tour_session_id)
    events = await get_events_by_session(session, tour_session_id)

    stats = aggregate_stats(events, tour_session)
    radar_scores = calculate_radar_scores(stats)
    identity_tags = select_identity_tags(radar_scores)
    report_theme = get_report_theme(tour_session.persona)

    one_liner = _pick_one_liner(stats, tour_session.persona)

    if llm_provider:
        try:
            one_liner = await _generate_one_liner_llm(llm_provider, tour_session.persona, stats)
        except Exception as e:
            logger.warning(f"Failed to generate one-liner via LLM, using fallback: {e}")

    report_id = str(uuid.uuid4())
    model = TourReportModel(
        id=report_id,
        tour_session_id=tour_session_id,
        total_duration_minutes=stats["total_duration_minutes"],
        most_viewed_exhibit_id=stats["most_viewed_exhibit_id"],
        most_viewed_exhibit_duration=stats["most_viewed_exhibit_duration"],
        longest_hall=stats["longest_hall"],
        longest_hall_duration=stats["longest_hall_duration"],
        total_questions=stats["total_questions"],
        total_exhibits_viewed=stats["total_exhibits_viewed"],
        ceramic_questions=stats["ceramic_questions"],
        identity_tags=identity_tags,
        radar_scores=radar_scores,
        one_liner=one_liner,
        report_theme=report_theme,
        created_at=datetime.now(UTC),
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model.to_entity()


async def get_report(session: AsyncSession, tour_session_id: str) -> TourReport | None:
    stmt = select(TourReportModel).where(TourReportModel.tour_session_id == tour_session_id)
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    return model.to_entity() if model else None


def _pick_one_liner(stats: dict, persona: str) -> str:
    import random
    return random.choice(ONE_LINER_CANDIDATES)


async def _generate_one_liner_llm(llm_provider: Any, persona: str, stats: dict) -> str:
    persona_names = {"A": "考古队长", "B": "半坡原住民", "C": "历史老师"}
    prompt = (
        f"根据以下游览数据，生成一句有感染力的'游览一句话'（15字以内），"
        f"风格要符合{persona_names.get(persona, '考古队长')}的身份：\n"
        f"- 游览时长：{stats.get('total_duration_minutes', 0):.0f}分钟\n"
        f"- 提问次数：{stats.get('total_questions', 0)}\n"
        f"- 参观展品数：{stats.get('total_exhibits_viewed', 0)}\n"
        f"只输出一句话，不要其他内容。"
    )
    result = await llm_provider.generate(prompt)
    return result.strip()[:50] if result else _pick_one_liner(stats, persona)
