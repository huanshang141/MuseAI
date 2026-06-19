import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.tour_event_service import get_events_by_session
from app.application.hall_normalizer import hall_display_name, normalize_hall
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

REFLECTION_TOPIC_LABELS = {
    "craft": "器物工艺",
    "settlement": "聚落空间",
    "social": "社会组织",
    "spiritual": "精神文化",
    "life": "日常生活",
    "evidence": "证据推理",
}

PERSONA_REVIEW_ENTRY = {
    "A": ("evidence", "本次复盘先按证据链整理：实物、展签和遗迹位置优先于现成结论。"),
    "B": ("evidence", "本次复盘先按研学笔记整理：保留可回看、可继续追问的现场线索。"),
    "C": ("social", "本次复盘先按历史问题整理：半坡如何组织共同生活，是主要入口。"),
    "D": ("craft", "本次复盘先按器物细节整理：材料、器形、纹饰和使用痕迹是主要入口。"),
}

ASSUMPTION_REVIEW_HINTS = {
    "A": "初始问题偏向共同体：平等、协作和公共生活能否从遗存中看出来。",
    "B": "初始问题偏向日常生活：房屋、器具和食物怎样连成生活场景。",
    "C": "初始问题偏向社会组织：分工、规则和群体秩序从哪里显形。",
    "D": "初始问题偏向证据判断：先保留现场材料，再决定解释能走多远。",
}

REVIEW_TOPIC_LINES = {
    "craft": {
        "focus": "关注点集中在器物如何被制作和使用：陶器、骨器、石器不只是展品，也对应火候、器形、磨损和用途。",
        "evidence": "可回看{halls}中的器物与展签，把“怎么做、怎么用、留下什么痕迹”连成一条线。",
        "next": "继续追问同类器物在不同场景中的用途差异，区分哪些判断来自实物，哪些仍是推测。",
    },
    "settlement": {
        "focus": "关注点集中在聚落空间：房屋、壕沟、作坊和墓葬共同说明人群怎样住在一起。",
        "evidence": "可回看{halls}中的位置关系，重点看居住、生产、边界和公共空间如何相互支撑。",
        "next": "继续追问空间布局背后的规则：哪些区域属于日常生活，哪些可能承担保护、生产或仪式功能。",
    },
    "social": {
        "focus": "关注点集中在社会组织：协作、分工和公共规则没有直接写出，却能从器物、房屋和墓葬组合中推出来。",
        "evidence": "可回看{halls}里与工具、墓葬、公共空间相关的线索，比较不同材料之间是否互相印证。",
        "next": "继续追问半坡人的共同生活如何被组织起来，以及哪些证据足以支持这种判断。",
    },
    "spiritual": {
        "focus": "关注点集中在精神文化：纹饰、图案和象征让器物超出实用层面，留下审美与观念线索。",
        "evidence": "可回看{halls}中的人面、鱼纹、几何纹或相关图案，观察它们出现的位置和器物类型。",
        "next": "继续追问图案是装饰、身份标记还是仪式表达，避免只停留在“好看”的判断。",
    },
    "life": {
        "focus": "关注点集中在日常生活：吃什么、住哪里、用什么工具，都能落到具体展品和空间中。",
        "evidence": "可回看{halls}中的陶器、工具和房屋线索，把它们放回同一个生活场景里理解。",
        "next": "继续追问这些器物分别服务饮食、居住、劳动还是储藏，补齐生活场景的细节。",
    },
    "evidence": {
        "focus": "关注点集中在证据推理：重要的不是记住结论，而是区分直接可见的材料和合理推断。",
        "evidence": "可回看{halls}中的展品、展签和遗迹位置，检查每个判断的证据来源。",
        "next": "继续追问一个判断背后需要哪些证据，并标出仍不确定的部分。",
    },
}

INSUFFICIENT_REVIEW_LINES = {
    "focus": "有效互动还少，暂时不生成判断型总结。",
    "evidence": "目前只保留展厅到访和少量操作记录；继续提问或查看展品后，复盘线索会更清楚。",
    "next": "下一次可先选一个展厅或一件展品追问，例如“它有什么用途”“证据在哪里”。",
}

TOPIC_KEYWORDS = {
    "craft": [
        "陶", "器", "工艺", "纹", "材料", "制作", "烧制", "陶窑", "尖底瓶",
        "彩陶", "石器", "骨器", "工具", "器形", "用途", "痕迹", "磨损",
    ],
    "settlement": [
        "聚落", "房屋", "半地穴", "壕沟", "遗址", "空间", "布局", "作坊",
        "灶", "墓葬", "居住", "保护大厅", "地面圆形房屋",
    ],
    "social": [
        "社会", "组织", "分工", "规则", "共同体", "协作", "等级", "贫富",
        "身份", "公共", "权力", "资源", "秩序",
    ],
    "spiritual": [
        "精神", "信仰", "仪式", "审美", "象征", "人面", "鱼纹", "图案",
        "纹饰", "祭祀", "观念",
    ],
    "life": [
        "生活", "吃", "食物", "农业", "农耕", "居住", "日常", "生存",
        "采集", "狩猎", "儿童", "家庭",
    ],
    "evidence": [
        "证据", "推断", "不确定", "考古", "展签", "材料", "判断", "线索",
        "地层", "出土", "遗存",
    ],
}

HALL_TOPIC_WEIGHTS = {
    "basic-exhibition-hall": {"craft": 1, "life": 1, "evidence": 1},
    "site-protection-hall": {"settlement": 2, "social": 1, "evidence": 1},
    "kiln-hall": {"craft": 2, "evidence": 1},
    "prehistoric-workshop": {"craft": 1, "life": 1},
    "education-center": {"evidence": 2},
    "banpo-girl-sculpture": {"spiritual": 1, "social": 1},
    "peony-garden": {"life": 1},
}


RECORD_SUMMARY_MAX_CHARS = 260
RECORD_SUMMARY_MAX_PAIRS = 12
RECORD_SUMMARY_ANSWER_CHARS = 320
RECORD_SUMMARY_QUESTION_CHARS = 120

PERSONA_SUMMARY_NAMES = {
    "A": "考古研究员",
    "B": "研学记录员",
    "C": "历史追问者",
    "D": "器物研究员",
}


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
    return {
        "A": "archaeology",
        "B": "field_study",
        "C": "history_inquiry",
        "D": "artifact_study",
    }.get(persona, "archaeology")


def _format_review_halls(halls: list[str]) -> str:
    names: list[str] = []
    for hall in halls:
        name = hall_display_name(hall)
        if name and name not in names:
            names.append(name)
    if not names:
        return "相关展厅"
    return "、".join(names[:3])


def build_reflection_summary(
    tour_session,
    events: list,
    stats: dict | None = None,
    radar_scores: dict | None = None,
) -> dict[str, Any]:
    """Build report review cues from existing session/events without an LLM call."""
    stats = stats or {}
    radar_scores = radar_scores or {}
    persona = getattr(tour_session, "persona", None) or "A"
    assumption = getattr(tour_session, "assumption", None) or "D"
    initial_topic, entry_line = PERSONA_REVIEW_ENTRY.get(persona, PERSONA_REVIEW_ENTRY["A"])
    assumption_line = ASSUMPTION_REVIEW_HINTS.get(assumption, ASSUMPTION_REVIEW_HINTS["D"])

    question_count = 0
    deep_dive_count = 0
    scores: dict[str, float] = {key: 0.0 for key in REFLECTION_TOPIC_LABELS}
    signal_halls: list[str] = []

    for event in events or []:
        event_type = getattr(event, "event_type", "") or ""
        metadata = getattr(event, "metadata", None) or {}
        hall = normalize_hall(getattr(event, "hall", None)) or ""
        text = _reflection_event_text(event, metadata, hall)

        if event_type == "exhibit_question":
            question_count += 1
            weight = 3.0
        elif event_type == "exhibit_deep_dive":
            deep_dive_count += 1
            weight = 3.0
        elif event_type == "exhibit_view":
            weight = 1.0
        elif event_type in {"hall_enter", "hall_leave"}:
            weight = 0.0
        else:
            weight = 0.5

        if hall and event_type in {"exhibit_question", "exhibit_deep_dive", "exhibit_view"} and hall not in signal_halls:
            signal_halls.append(hall)

        for topic, topic_weight in HALL_TOPIC_WEIGHTS.get(hall, {}).items():
            scores[topic] += topic_weight * weight

        for topic in _match_reflection_topics(text):
            scores[topic] += weight

    total_signals = question_count + deep_dive_count
    if total_signals < 2:
        return {
            "initial_assumption": INSUFFICIENT_REVIEW_LINES["focus"],
            "observed_focus": INSUFFICIENT_REVIEW_LINES["evidence"],
            "change_summary": INSUFFICIENT_REVIEW_LINES["next"],
            "confidence": 0.35,
            "status": "insufficient",
            "initial_focus": REFLECTION_TOPIC_LABELS.get(initial_topic, initial_topic),
            "observed_focus_key": None,
        }

    top_topic = max(scores, key=scores.get)
    top_score = scores.get(top_topic, 0.0)
    total_score = sum(scores.values()) or 1.0
    observed_label = REFLECTION_TOPIC_LABELS.get(top_topic, top_topic)
    initial_label = REFLECTION_TOPIC_LABELS.get(initial_topic, initial_topic)
    hall_text = _format_review_halls(signal_halls)
    topic_lines = REVIEW_TOPIC_LINES.get(
        top_topic,
        {
            "focus": f"关注点集中在{observed_label}。",
            "evidence": "可回看{halls}中的相关展品、展签和遗迹位置。",
            "next": "继续追问这条线索背后的证据来源。",
        },
    )
    confidence = min(0.92, 0.5 + (top_score / total_score) * 0.3 + min(total_signals, 6) * 0.03)

    if top_score <= 0:
        initial_assumption = INSUFFICIENT_REVIEW_LINES["focus"]
        observed_focus = INSUFFICIENT_REVIEW_LINES["evidence"]
        change_summary = INSUFFICIENT_REVIEW_LINES["next"]
        status = "insufficient"
        confidence = 0.35
    elif top_topic == initial_topic:
        initial_assumption = f"{entry_line}{assumption_line}"
        observed_focus = topic_lines["evidence"].format(halls=hall_text)
        change_summary = topic_lines["next"].format(halls=hall_text)
        status = "stable"
    else:
        initial_assumption = topic_lines["focus"].format(halls=hall_text)
        observed_focus = topic_lines["evidence"].format(halls=hall_text)
        change_summary = (
            f"把{initial_label}的初始问题放到{observed_label}这条线索上继续核对："
            f"{topic_lines['next'].format(halls=hall_text)}"
        )
        status = "shifted"

    if radar_scores:
        strongest_radar = max(radar_scores, key=lambda key: radar_scores.get(key, 0))
        if strongest_radar == "ceramic_aesthetics" and top_topic != "craft":
            observed_focus += " 器物细节也可作为辅助线索保留。"
        elif strongest_radar == "life_experience" and top_topic != "life":
            observed_focus += " 日常生活场景也可作为辅助线索保留。"

    return {
        "initial_assumption": initial_assumption,
        "observed_focus": observed_focus,
        "change_summary": change_summary,
        "confidence": round(confidence, 2),
        "status": status,
        "initial_focus": initial_label,
        "observed_focus_key": top_topic if top_score > 0 else None,
    }


def _reflection_event_text(event, metadata: dict, hall: str) -> str:
    parts = [
        hall,
        str(metadata.get("question") or ""),
        str(metadata.get("message") or ""),
        str(metadata.get("exhibit_name") or ""),
        str(metadata.get("name") or ""),
    ]
    exhibit_id = getattr(event, "exhibit_id", None)
    if exhibit_id:
        parts.append(str(exhibit_id.value if hasattr(exhibit_id, "value") else exhibit_id))
    return " ".join(part for part in parts if part)


def _match_reflection_topics(text: str) -> set[str]:
    matched: set[str] = set()
    if not text:
        return matched
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            matched.add(topic)
    return matched


def _ensure_aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _event_metadata(event) -> dict:
    return getattr(event, "metadata", None) or {}


def _event_dedupe_key(event, *parts: Any) -> str:
    metadata = _event_metadata(event)
    client_event_id = metadata.get("client_event_id")
    if client_event_id:
        return str(client_event_id)
    normalized_parts = [str(part or "").strip() for part in parts]
    return "|".join(normalized_parts)


def aggregate_stats(events: list, tour_session) -> dict:
    total_duration = 0.0
    started_at = _ensure_aware(tour_session.started_at)
    completed_at = _ensure_aware(tour_session.completed_at)
    if started_at and completed_at:
        total_duration = (completed_at - started_at).total_seconds() / 60.0
    elif started_at:
        total_duration = (datetime.now(UTC) - started_at).total_seconds() / 60.0

    exhibit_durations: dict[str, int] = {}
    hall_durations: dict[str, int] = {}
    answered_questions = 0
    fallback_questions = 0
    answered_ceramic_questions = 0
    fallback_ceramic_questions = 0
    viewed_exhibits: set[str] = set()
    seen_answered_questions: set[str] = set()
    seen_question_events: set[str] = set()
    seen_duration_events: set[str] = set()

    for event in events:
        metadata = _event_metadata(event)
        if event.event_type == "exhibit_view":
            eid = ""
            if event.exhibit_id:
                eid = event.exhibit_id.value if hasattr(event.exhibit_id, 'value') else str(event.exhibit_id)
            if not eid:
                exhibit_name = str(metadata.get("exhibit_name") or metadata.get("name") or "").strip()
                if exhibit_name:
                    eid = f"name:{exhibit_name}"
            if not eid:
                continue
            viewed_exhibits.add(eid)
            if event.duration_seconds:
                duration_key = _event_dedupe_key(
                    event,
                    event.event_type,
                    event.exhibit_id,
                    event.hall,
                    event.duration_seconds,
                )
                if duration_key not in seen_duration_events:
                    seen_duration_events.add(duration_key)
                    exhibit_durations[eid] = exhibit_durations.get(eid, 0) + event.duration_seconds
        elif event.event_type == "hall_leave" and event.hall and event.duration_seconds:
            duration_key = _event_dedupe_key(
                event,
                event.event_type,
                event.hall,
                event.duration_seconds,
            )
            if duration_key in seen_duration_events:
                continue
            seen_duration_events.add(duration_key)
            hall = normalize_hall(event.hall)
            if not hall:
                continue
            hall_durations[hall] = hall_durations.get(hall, 0) + event.duration_seconds
        elif event.event_type == "assistant_answer":
            question_text = metadata.get("question") or metadata.get("message") or ""
            question_key = _event_dedupe_key(
                event,
                event.event_type,
                normalize_hall(event.hall),
                question_text,
            )
            if question_key in seen_answered_questions:
                continue
            seen_answered_questions.add(question_key)
            answered_questions += 1
            if metadata.get("is_ceramic_question") or detect_ceramic_question(str(question_text)):
                answered_ceramic_questions += 1
        elif event.event_type == "exhibit_question":
            question_text = metadata.get("message") or metadata.get("question") or ""
            question_key = _event_dedupe_key(
                event,
                event.event_type,
                normalize_hall(event.hall),
                question_text,
            )
            if question_key in seen_question_events:
                continue
            seen_question_events.add(question_key)
            fallback_questions += 1
            if metadata.get("is_ceramic_question"):
                fallback_ceramic_questions += 1

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

    site_hall_minutes = hall_durations.get("site-protection-hall", 0) / 60.0
    total_questions = answered_questions if answered_questions else fallback_questions
    ceramic_questions = answered_ceramic_questions if answered_questions else fallback_ceramic_questions

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

    tour_session = await get_session(session, tour_session_id)
    events = await get_events_by_session(session, tour_session_id)

    stats = aggregate_stats(events, tour_session)
    radar_scores = calculate_radar_scores(stats)
    identity_tags = select_identity_tags(radar_scores)
    report_theme = get_report_theme(tour_session.persona)

    one_liner = existing.one_liner if existing is not None else _pick_one_liner(stats, tour_session.persona)
    record_summary = existing.record_summary if existing is not None else None
    previous_question_count = existing.total_questions if existing is not None else None
    should_refresh_record_summary = (
        existing is None
        or not record_summary
        or previous_question_count != stats["total_questions"]
    )

    # ── LLM enrichment (one-liner + record summary) ─────────────────────────────
    # Both are independent LLM calls; run them concurrently so report generation
    # pays one round-trip instead of two. The record summary is only attempted
    # when we captured answered Q&A — otherwise the API falls back to the keyword
    # template (no regression). Failures degrade to the non-LLM fallback per task.
    if llm_provider:
        qa_pairs = collect_qa_pairs(events) if should_refresh_record_summary else []
        tasks: dict[str, Any] = {}
        if existing is None:
            tasks["one_liner"] = _generate_one_liner_llm(llm_provider, tour_session.persona, stats)
        if qa_pairs:
            tasks["record_summary"] = generate_record_summary_llm(
                llm_provider, tour_session.persona, qa_pairs
            )
        if tasks:
            outcomes = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for key, outcome in zip(tasks.keys(), outcomes):
                if isinstance(outcome, Exception):
                    logger.warning(f"Failed to generate {key} via LLM, using fallback: {outcome}")
                    continue
                if key == "one_liner" and outcome:
                    one_liner = outcome
                elif key == "record_summary":
                    record_summary = outcome or None

    if existing is not None:
        existing.total_duration_minutes = stats["total_duration_minutes"]
        existing.most_viewed_exhibit_id = stats["most_viewed_exhibit_id"]
        existing.most_viewed_exhibit_duration = stats["most_viewed_exhibit_duration"]
        existing.longest_hall = stats["longest_hall"]
        existing.longest_hall_duration = stats["longest_hall_duration"]
        existing.total_questions = stats["total_questions"]
        existing.total_exhibits_viewed = stats["total_exhibits_viewed"]
        existing.ceramic_questions = stats["ceramic_questions"]
        existing.identity_tags = identity_tags
        existing.radar_scores = radar_scores
        existing.one_liner = one_liner
        existing.report_theme = report_theme
        existing.record_summary = record_summary
        await session.commit()
        await session.refresh(existing)
        return existing.to_entity()

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
        record_summary=record_summary,
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


def _clean_record_text(value: str | None) -> str:
    """Strip markdown/whitespace noise from recorded question/answer text."""
    text = str(value or "")
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _finish_summary_sentence(text: str) -> str:
    """Normalize summary ending to a complete Chinese sentence."""
    cleaned = text.strip().rstrip("，、；;：:,. ")
    if not cleaned:
        return ""
    if cleaned[-1] in "。！？":
        return cleaned
    return cleaned + "。"


def _trim_summary(text: str, max_chars: int = RECORD_SUMMARY_MAX_CHARS) -> str:
    """Keep the summary within the budget without cutting mid-sentence."""
    cleaned = _clean_record_text(text)
    if len(cleaned) <= max_chars:
        return _finish_summary_sentence(cleaned)
    window = cleaned[:max_chars]
    cut = max(window.rfind(sep) for sep in "。！？")
    if cut >= int(max_chars * 0.6):
        return _finish_summary_sentence(window[: cut + 1])
    return _finish_summary_sentence(window)


def collect_qa_pairs(events: list) -> list[dict[str, str]]:
    """Reconstruct ordered visitor↔guide Q&A pairs that actually have answers.

    The frontend records ``assistant_answer`` events carrying both the original
    question and the AI answer; bare ``exhibit_question`` events seed the entry so
    a later answer can attach to it. Only pairs with a non-empty answer are kept —
    a conversation with no answers has nothing to summarize.
    """
    entries: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for event in events or []:
        event_type = getattr(event, "event_type", None)
        if event_type not in {"assistant_answer", "exhibit_question"}:
            continue
        metadata = getattr(event, "metadata", None) or {}
        question = _clean_record_text(
            metadata.get("question") or metadata.get("message") or metadata.get("query")
        )
        if not question:
            continue
        hall = normalize_hall(getattr(event, "hall", None) or metadata.get("hall")) or ""
        key = f"{hall}|{question}"
        entry = entries.get(key)
        if entry is None:
            entry = {"hall": hall, "question": question, "answer": ""}
            entries[key] = entry
            order.append(key)
        if event_type == "assistant_answer":
            answer = _clean_record_text(metadata.get("answer"))
            if answer and not entry["answer"]:
                entry["answer"] = answer
    return [entries[key] for key in order if entries[key]["answer"]]


def _build_summary_prompt(persona: str, qa_pairs: list[dict[str, str]]) -> str:
    persona_name = PERSONA_SUMMARY_NAMES.get(persona, "考古研究员")
    lines: list[str] = []
    for index, pair in enumerate(qa_pairs[:RECORD_SUMMARY_MAX_PAIRS], 1):
        hall = hall_display_name(pair["hall"]) if pair["hall"] else ""
        prefix = f"（{hall}）" if hall else ""
        question = pair["question"][:RECORD_SUMMARY_QUESTION_CHARS]
        answer = pair["answer"][:RECORD_SUMMARY_ANSWER_CHARS]
        lines.append(f"{index}. {prefix}游客问：{question}\n   导览答：{answer}")
    transcript = "\n".join(lines)
    return (
        "你正在为一次西安半坡博物馆的AI导览生成「记录摘要」。\n"
        "以下是本次游客与AI导览员的真实问答记录（按时间顺序）：\n\n"
        f"{transcript}\n\n"
        f"请以{persona_name}的视角，把上面这段真实对话提炼成一段连贯的中文「记录摘要」，要求：\n"
        "1. 必须基于上面真实问答的具体内容，准确写出游客实际关心的问题，"
        "以及对话中得到的关键信息或结论；不要套用与本次对话无关的通用说辞，也不要编造未提到的展品。\n"
        "2. 用第二人称「你」称呼游客，像在帮游客复盘这次参观。\n"
        "3. 输出一段完整的话，建议120到220字，最多260字；宁可概括，不要堆叠全部展品名称、"
        "痕迹和细节。\n"
        "4. 用2到3个短句完成，句末只能用句号、问号或感叹号，不要用分号收尾。\n"
        "5. 不要写标题、列表、编号或Markdown符号，只输出摘要正文本身，不要任何前后缀、引号或解释。"
    )


async def generate_record_summary_llm(
    llm_provider: Any,
    persona: str,
    qa_pairs: list[dict[str, str]],
) -> str:
    """Summarize the real tour conversation into a concise record summary."""
    prompt = _build_summary_prompt(persona, qa_pairs)
    messages = [{"role": "user", "content": prompt}]
    model = getattr(llm_provider, "report_model", None)
    if getattr(llm_provider, "supports_model_override", False) is True and model:
        result = await llm_provider.generate(messages, model=model)
    else:
        result = await llm_provider.generate(messages)
    content = getattr(result, "content", result)
    return _trim_summary(str(content or ""))


async def _generate_one_liner_llm(llm_provider: Any, persona: str, stats: dict) -> str:
    persona_names = {
        "A": "考古研究员",
        "B": "研学记录员",
        "C": "历史追问者",
        "D": "器物研究员",
    }
    prompt = (
        f"根据以下游览数据，生成一句有感染力的'游览一句话'（15字以内），"
        f"风格要符合{persona_names.get(persona, '考古研究员')}的身份：\n"
        f"- 游览时长：{stats.get('total_duration_minutes', 0):.0f}分钟\n"
        f"- 提问次数：{stats.get('total_questions', 0)}\n"
        f"- 参观展品数：{stats.get('total_exhibits_viewed', 0)}\n"
        f"只输出一句话，不要其他内容。"
    )
    messages = [{"role": "user", "content": prompt}]
    model = getattr(llm_provider, "report_model", None)
    if getattr(llm_provider, "supports_model_override", False) is True and model:
        result = await llm_provider.generate(messages, model=model)
    else:
        result = await llm_provider.generate(messages)
    content = getattr(result, "content", result)
    return str(content).strip()[:50] if content else _pick_one_liner(stats, persona)
