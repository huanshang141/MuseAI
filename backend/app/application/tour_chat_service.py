import uuid
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.sse_events import sse_tour_event
from app.application.tour_event_service import record_events
from app.application.tour_report_service import detect_ceramic_question
from app.application.tour_session_service import get_session

PERSONA_PROMPTS = {
    "A": (
        "你是一位严谨求实的考古队长，正在带领游客勘探西安半坡博物馆。"
        "你的叙事风格：引用硬核发掘数据和学术推论，用'我们''数据表明''地层学证据'等措辞。"
        "避免主观臆测，对不确定的内容标注'学术界尚有争议'。"
        "在推荐下一个展品时，强调工艺承接关系和地层演化顺序。"
    ),
    "B": (
        "你是一位穿越来的半坡村原住民，正在带远道而来的朋友参观你曾经生活的村落。"
        "你的叙事风格：以村民视角第一人称叙述，增强沉浸感，用'我''阿妈''我们部落''当年'等措辞。"
        "把展柜里的文物描述成你曾经使用或见过的日常用品。"
        "在推荐下一个展品时，用生活化的语言描述它的用途和故事。"
    ),
    "C": (
        "你是一位爱提问的历史老师，正在带领学生进行半坡博物馆的沉浸式游学。"
        "你的叙事风格：多提供不同观点并引导思考，用'同学们''想一想''你觉得呢'等措辞。"
        "每个知识点后抛出启发性问题。"
        "在推荐下一个展品时，设置悬念和对比思考任务。"
    ),
}

ASSUMPTION_CONTEXTS = {
    "A": "游客初始假设：原始社会是没有压迫、人人平等的纯真年代。当讨论到社会结构相关内容时，引导反思这一假设。",
    "B": "游客初始假设：原始社会是饥寒交迫的荒野求生。当讨论到生存方式相关内容时，引导反思这一假设。",
    "C": "游客初始假设：原始社会已经出现贫富分化和阶级的雏形。当讨论到社会结构相关内容时，引导反思这一假设。",
}

HALL_DESCRIPTIONS = {
    "relic-hall": "出土文物展厅：陈列半坡遗址出土的陶器、石器、骨器等文物，展示6000年前半坡人的生存技术和精神世界。",
    "site-hall": "遗址保护大厅：保留半坡遗址的居住区、制陶区和墓葬区原貌，展示圆形和方形半地穴式房屋结构。",
}


def build_system_prompt(
    persona: str,
    assumption: str,
    hall: str | None = None,
    exhibit_context: str | None = None,
    visited_exhibits: list[str] | None = None,
) -> str:
    parts = [PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["A"])]
    parts.append(ASSUMPTION_CONTEXTS.get(assumption, ASSUMPTION_CONTEXTS["A"]))

    if hall and hall in HALL_DESCRIPTIONS:
        parts.append(f"当前展厅：{HALL_DESCRIPTIONS[hall]}")

    if exhibit_context:
        parts.append(f"当前展品信息：{exhibit_context}")

    if visited_exhibits:
        parts.append(f"游客已参观的展品：{', '.join(visited_exhibits)}（避免重复介绍这些展品）")

    return "\n\n".join(parts)


async def ask_stream_tour(
    db_session: AsyncSession,
    session_maker: async_sessionmaker,
    tour_session_id: str,
    message: str,
    rag_agent: Any,
    exhibit_id: str | None = None,
    exhibit_context: str | None = None,
    degraded_services: set[str] | None = None,
) -> AsyncGenerator[str, None]:
    tour_session = await get_session(db_session, tour_session_id)

    if degraded_services and "elasticsearch" in degraded_services:
        yield sse_tour_event(
            "error",
            data={"code": "RAG_UNAVAILABLE", "message": "检索服务暂时不可用，请稍后再试"},
        )
        return

    visited_ids = tour_session.visited_exhibit_ids or []
    system_prompt = build_system_prompt(
        persona=tour_session.persona,
        assumption=tour_session.assumption,
        hall=tour_session.current_hall,
        exhibit_context=exhibit_context,
        visited_exhibits=visited_ids,
    )

    trace_id = str(uuid.uuid4())
    is_ceramic = detect_ceramic_question(message)

    try:
        async for event in _stream_rag(rag_agent, message, system_prompt):
            yield event
    except Exception as e:
        logger.error(f"Tour chat RAG error: {e}")
        yield sse_tour_event(
            "error",
            data={"code": "llm_error", "message": "AI导览暂时不可用，请稍后再试"},
        )
        return

    yield sse_tour_event(
        "done",
        trace_id=trace_id,
        is_ceramic_question=is_ceramic,
    )

    try:
        async with session_maker() as event_session:
            await record_events(event_session, tour_session_id, [
                {
                    "event_type": "exhibit_question",
                    "exhibit_id": exhibit_id,
                    "hall": tour_session.current_hall,
                    "metadata": {"question": message, "is_ceramic_question": is_ceramic},
                }
            ])
    except Exception as e:
        logger.warning(f"Failed to record tour event: {e}")


async def _stream_rag(rag_agent: Any, message: str, system_prompt: str) -> AsyncGenerator[str, None]:
    result = await rag_agent.run(message, system_prompt=system_prompt)
    answer = result.get("answer", "")

    yield sse_tour_event("chunk", data={"content": answer})
