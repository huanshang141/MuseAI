import uuid
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.sse_events import (
    sse_tour_audio_chunk,
    sse_tour_audio_end,
    sse_tour_audio_error,
    sse_tour_audio_start,
    sse_tour_event,
)
from app.infra.providers.tts.base import BaseTTSProvider
from app.application.tour_event_service import record_events
from app.application.tour_report_service import detect_ceramic_question
from app.application.tour_session_service import get_session
from app.observability.context import request_id_var

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


STYLE_LABELS = {
    "answer_length": {"brief": "简短", "balanced": "适中", "detailed": "详细"},
    "depth": {"introductory": "入门", "standard": "标准", "deep": "深入"},
    "terminology": {"plain": "通俗", "professional": "专业", "academic": "学术"},
}


def _build_style_prompt(style: Any) -> str | None:
    if style is None:
        return None
    style_dict = style if isinstance(style, dict) else style.model_dump(exclude_none=True)
    if not style_dict:
        return None
    lines = []
    label_map = {"answer_length": "回答长度", "depth": "讲解深浅", "terminology": "术语难度"}
    for key, label in label_map.items():
        raw = style_dict.get(key)
        if raw:
            mapped = STYLE_LABELS.get(key, {}).get(raw, raw)
            lines.append(f"{label}: {mapped}")
    return "\n".join(lines) if lines else None


async def ask_stream_tour(
    db_session: AsyncSession,
    session_maker: async_sessionmaker,
    tour_session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: Any,
    exhibit_id: str | None = None,
    exhibit_context: str | None = None,
    style: Any = None,
    degraded_services: set[str] | None = None,
    tts_provider: BaseTTSProvider | None = None,
    tts_service: Any = None,
    persona: str | None = None,
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

    style_prompt = _build_style_prompt(style)
    if style_prompt:
        system_prompt = f"[风格约束]\n{style_prompt}\n\n{system_prompt}"

    trace_id = str(uuid.uuid4())
    log = logger.bind(
        trace_id=trace_id,
        request_id=request_id_var.get(),
        tour_session_id=tour_session_id,
        exhibit_id=exhibit_id,
    )
    is_ceramic = detect_ceramic_question(message)

    full_content_parts: list[str] = []
    try:
        async for event, chunk in _stream_rag(rag_agent, llm_provider, message, system_prompt):
            if chunk is not None:
                full_content_parts.append(chunk)
            yield event
    except Exception as e:
        log.error("Tour chat RAG error: {}", e)
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

    # TTS audio events (after done)
    if tts_provider is not None and tts_service is not None:
        full_content = "".join(full_content_parts)
        tts_config = await tts_service.get_tour_tts_config(persona)
        yield sse_tour_audio_start(voice=tts_config.voice, format="pcm16")
        try:
            async for audio_chunk in tts_provider.synthesize_stream(full_content, tts_config):
                yield sse_tour_audio_chunk(audio_chunk)
            yield sse_tour_audio_end()
        except Exception as e:
            log.warning(f"TTS synthesis failed: {e}")
            yield sse_tour_audio_error("TTS_ERROR", "语音合成失败")

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
            log.error("Failed to record tour event after retries: {}", e)


async def _stream_rag(
    rag_agent: Any, llm_provider: Any, message: str, system_prompt: str
) -> AsyncGenerator[tuple[str, str | None], None]:
    result = await rag_agent.run(message, system_prompt=system_prompt)

    docs = (
        result.get("filtered_documents")
        or result.get("reranked_documents")
        or result.get("documents", [])
    )
    context = "\n\n".join(doc.page_content for doc in docs)

    prompt = None
    if hasattr(rag_agent, "prompt_gateway") and rag_agent.prompt_gateway:
        prompt = await rag_agent.prompt_gateway.render(
            "rag_answer_generation",
            {"context": context, "query": message},
        )

    if prompt is None:
        prompt = (
            f"{system_prompt}\n\n参考上下文：\n{context}\n\n"
            f"用户问题：{message}\n\n请基于以上信息回答："
        )

    messages = [{"role": "user", "content": prompt}]
    async for chunk in llm_provider.generate_stream(messages):
        yield sse_tour_event("chunk", data={"content": chunk}), chunk
