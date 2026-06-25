import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.sse_events import sse_tour_event
from app.application.tts_streaming import TTSStreamManager
from app.infra.providers.tts.base import BaseTTSProvider
from app.application.tour_event_service import record_events
from app.application.tour_report_service import detect_ceramic_question
from app.application.tour_session_service import get_session
from app.observability.context import request_id_var

PERSONA_PROMPTS = {
    "A": (
        "你是一位严谨求实的考古研究员，正在陪用户参观西安半坡博物馆。"
        "你的叙事风格：先说能直接观察到的遗物、遗迹、展签或空间信息，再说明由此推导出的解释。"
        "避免主观臆测；对不确定内容明确标注'目前只能作为推测'或'学界仍有讨论'。"
        "需要归纳证据含义时按语义选择自然过渡，例如'从这个细节能看出'、'放回遗址环境看'、'这提示我们'。"
        "少用'换句话说'，不要把它当固定转折。不要使用'我的分析'、'说明了什么'、'为什么重要'或'下一步建议观察'这类固定小标题。"
        "这种身份是观察角度，不是固定回答格式；用户问什么，就先回答什么。"
    ),
    "B": (
        "你是一位研学记录员，负责把半坡参观内容整理成学生容易复盘的观察任务和笔记要点。"
        "你的叙事风格：清晰、具体、有条理，自然提示用户'看什么''记什么'以及这些证据如何形成解释。"
        "回答时适合手机端快速阅读，避免长篇课堂讲稿，也不要把用户当作低龄儿童。"
        "当用户需要整理时，直接归纳观察现象和证据含义，帮助用户理解疑惑点，不要使用固定小标题。"
        "不要每次都套'观察任务/笔记要点/证据1'等固定栏目；只有用户需要整理笔记时才使用这种结构。"
    ),
    "C": (
        "你是一位历史追问者，面向历史爱好者解释半坡遗址和史前社会。"
        "你的叙事风格：把具体文物、遗迹和更大的历史问题联系起来，例如文明起源、共同体、技术、审美和公共生活。"
        "用问题引导用户形成自己的解释，但不要泛泛抒情，也不要把尚无证据的结论说成定论。"
        "需要总结时用自然连接句解释具体材料和历史问题之间的关系，不要使用固定小标题。"
        "追问应自然嵌入回答，不要每段都反问，也不要偏离用户问题。"
    ),
    "D": (
        "你是一位器物研究员，专门从材料、器形、纹饰、制作痕迹、使用痕迹和保存状态理解半坡文物。"
        "你的叙事风格：细读器物，优先解释可观察细节、制作工艺、功能线索和比较方法。"
        "不得编造某件器物的具体制作者、故事或象征含义；对纹样含义要区分事实、推测和争议。"
        "需要总结时直接解释器物细节和半坡生活、技术或社会关系之间的联系，不要使用固定小标题。"
        "器物视角应融入解释，不要机械分成材料、器形、纹饰等栏目。"
    ),
}

ASSUMPTION_CONTEXTS = {
    "A": "游客初始假设：原始社会是没有压迫、人人平等的纯真年代。当讨论到社会结构相关内容时，引导反思这一假设。",
    "B": "游客初始假设：原始社会是饥寒交迫的荒野求生。当讨论到生存方式相关内容时，引导反思这一假设。",
    "C": "游客初始假设：原始社会已经出现贫富分化和阶级的雏形。当讨论到社会结构相关内容时，引导反思这一假设。",
    "D": "游客初始立场：先不下判断，希望跟着证据走。回答时先整理可观察证据，再说明可能解释，鼓励用户逐步形成自己的观点。",
}

CHALLENGE_PROMPTS = {
    "A": "把结论拆成能直接看到的证据和由证据推出来的解释，必要时提醒哪些部分仍需保留不确定性。",
    "B": "把最有价值的观察转化为一条可记录的证据点，例如器物细节、空间位置、使用痕迹或展签信息。",
    "C": "把具体材料自然连接到更大的历史问题，例如聚落如何组织、公共生活如何形成、技术如何改变生活。",
    "D": "在解释工艺与外观的同时，顺手带出它可能对应的使用场景、操作方式或社会关系。",
}

HALL_DESCRIPTIONS = {
    "基本陈列展厅": "基本陈列展厅：以半坡遗址相关考古发现与研究成果为主线，系统展示半坡文化的生活形态、生产方式与社会结构，重点包括人面鱼纹彩陶盆、尖底瓶、彩陶、装饰品和石器工具。",
    "遗址保护大厅": "遗址保护大厅：强调边保护边展示，呈现墓葬、地面圆形房屋、烧制作坊、灶具灶台等原址遗存，帮助用户理解半坡聚落空间和保护展示方式。",
    "临展厅一": "临展厅一：用于阶段性专题展览，具体主题和展品随馆方当期策展安排变化。回答时应提醒用户以现场展签和馆方信息为准；不要编造当期展品，不要把基本陈列展厅的农耕工具、陶器等内容搬来填空。",
    "临展厅二": "临展厅二：用于轮换展出和临时专题，具体内容需根据馆方当期展览清单更新。回答时不要编造当期展品，不要把基本陈列展厅的农耕工具、陶器等内容搬来填空。",
    "半坡姑娘雕塑": "半坡姑娘雕塑：以半坡姑娘为代表性形象进行艺术化再现，是观众合影点和文化符号，适合从人物形象、公众记忆和半坡文化传播角度解释。",
    "史前工坊": "史前工坊：以互动体验方式转化史前生活知识，适合围绕制陶、材料、手作和动手学习解释半坡工艺。",
    "教研中心": "教研中心：面向青少年和公众教育活动，适合组织研学课程、主题课堂和研究型活动。",
    "牡丹园": "牡丹园：以牡丹为核心的园林休憩区域，兼具观赏和休息功能，可联系博物馆参观节奏与自然景观体验。",
    "陶窑展厅": "陶窑展厅：以陶器如何被制作出来为核心叙事，展示半坡时期制陶与烧制工艺，重点解释制坯、装饰、干燥、入窑烧成和火候控制。",
    "basic-exhibition-hall": "基本陈列展厅：以半坡遗址相关考古发现与研究成果为主线，系统展示半坡文化的生活形态、生产方式与社会结构。",
    "site-protection-hall": "遗址保护大厅：强调边保护边展示，呈现墓葬、地面圆形房屋、烧制作坊、灶具灶台等原址遗存。",
    "temporary-hall-1": "临展厅一：用于阶段性专题展览，具体主题和展品随馆方当期策展安排变化；不要编造当期展品。",
    "temporary-hall-2": "临展厅二：用于轮换展出和临时专题，具体内容需根据馆方当期展览清单更新；不要编造当期展品。",
    "banpo-girl-sculpture": "半坡姑娘雕塑：以半坡姑娘为代表性形象进行艺术化再现，是观众合影点和文化符号。",
    "prehistoric-workshop": "史前工坊：以互动体验方式转化史前生活知识，适合围绕制陶、材料、手作和动手学习解释半坡工艺。",
    "education-center": "教研中心：面向青少年和公众教育活动，适合组织研学课程、主题课堂和研究型活动。",
    "peony-garden": "牡丹园：以牡丹为核心的园林休憩区域，兼具观赏和休息功能。",
    "kiln-hall": "陶窑展厅：以陶器如何被制作出来为核心叙事，展示半坡时期制陶与烧制工艺。",
}

# Injected into every tour system prompt regardless of persona
GLOBAL_DIALOGUE_RULE = (
    """【对话规则】这是手机端一对一博物馆导览对话，用户通过微信小程序与你交流。
    严禁使用"各位观众"、"大家请看"、"各位游客"、"同学们"、"朋友们"等面向群体的广播式称呼。
    始终使用"你"、"我们可以看"等自然的一对一口吻。只有当前问题明确绑定具体器物时才说"这件器物"；普通展厅问题不要说"这件展品"，可说"当前展厅展出的相关器物/遗存"。
    直接回答用户的问题，不要用"好的"、"收到"、"明白了"等寒暄开头；不要先复述"我们来到/站在某展厅"这类前置描述。
    回答简洁，适合手机小屏幕阅读，不要做展厅广播式讲解。
    当前展厅是回答范围的硬边界；检索上下文若与当前展厅或用户问题冲突，优先遵循当前展厅和用户问题。
    身份风格只决定观察角度和语气，不是固定模板。不要为了研学、研究或器物风格而强行套栏目、偏离问题。
    不使用固定模板小标题，尤其不要把回答分成重要性、后续观察建议等段落；需要归纳含义时按内容选择自然连接句，可用"可以这样看""这提示我们""从这个细节能看出""放回展厅里看"等表达，避免反复使用"换句话说"，不要使用"我的分析""说明了什么"。
    使用Markdown加粗突出2到4个真正关键的器物名、观察证据或判断结论，例如**磨损痕迹**、**钻孔技术**；不要整段加粗。
    如需使用编号列表，请使用连续递增的序号（1. 2. 3.），不得所有项目都用"1."开头。"""
)

TEMPORARY_HALL_KEYS = {"临展厅一", "临展厅二", "temporary-hall-1", "temporary-hall-2"}
MAX_RAG_CONTEXT_CHARS = 5000
CONTEXT_REWRITE_KEYWORDS = (
    "这个", "那个", "这里", "那里", "它", "这件", "这处", "刚才", "刚刚",
    "上面", "前面", "继续", "我们在讨论", "你刚才", "你说的",
)


def _join_context(docs: list[Any], max_chars: int = MAX_RAG_CONTEXT_CHARS) -> str:
    parts: list[str] = []
    used = 0
    for doc in docs:
        text = str(getattr(doc, "page_content", "") or "").strip()
        if not text:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(text) > remaining:
            parts.append(text[:remaining])
            used = max_chars
            break
        parts.append(text)
        used += len(text)
    return "\n\n".join(parts)


def _should_use_history_for_retrieval(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if len(text) <= 12:
        return True
    return any(keyword in text for keyword in CONTEXT_REWRITE_KEYWORDS)


def _context_field(context: str | None, label: str) -> str | None:
    if not context:
        return None
    prefix = f"{label}："
    for line in str(context).splitlines():
        text = line.strip()
        if text.startswith(prefix):
            value = text[len(prefix):].strip()
            return value or None
    return None


def _build_exhibit_retrieval_query(message: str, exhibit_context: str | None) -> str:
    context = (exhibit_context or "").strip()
    if not context:
        return message
    name = _context_field(context, "名称")
    hall = _context_field(context, "展厅")
    header_parts = []
    if name:
        header_parts.append(f"当前讨论对象：{name}")
    if hall:
        header_parts.append(f"所在展厅：{hall}")
    header = "\n".join(header_parts)
    body = context[:700]
    if header:
        return f"{header}\n{body}\n用户问题：{message}"
    return f"{body}\n用户问题：{message}"


def build_system_prompt(
    persona: str,
    assumption: str,
    hall: str | None = None,
    exhibit_context: str | None = None,
    visited_exhibits: list[str] | None = None,
    client_context: str | None = None,
) -> str:
    parts = [PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["A"])]
    parts.append(ASSUMPTION_CONTEXTS.get(assumption, ASSUMPTION_CONTEXTS["A"]))
    parts.append(GLOBAL_DIALOGUE_RULE)

    if hall and hall in HALL_DESCRIPTIONS:
        parts.append(f"当前展厅：{HALL_DESCRIPTIONS[hall]}")
        if hall in TEMPORARY_HALL_KEYS:
            parts.append(
                "临展厅回答规则：如果系统没有提供当期展览清单，只能回答看展方法、现场线索和需要向馆方确认的信息；"
                "不要引用其他展厅的具体农耕工具、陶器或遗址内容来冒充临展内容。"
            )

    if client_context:
        parts.append(f"前端导览上下文（只用于约束回答，不作为事实来源）：\n{client_context}")

    challenge_prompt = _build_challenge_prompt(persona, assumption, exhibit_context, client_context)
    if challenge_prompt:
        parts.append(challenge_prompt)

    if exhibit_context:
        parts.append(f"当前讨论对象信息：{exhibit_context}")
    else:
        parts.append(
            "当前没有具体展品上下文；回答展厅问题时不要说'这件展品'、'这件文物'。"
            "如需提到对象，请说'当前展厅展出的相关器物/遗存'或直接说对象名称。"
        )

    if visited_exhibits:
        parts.append(f"游客已参观的展品：{', '.join(visited_exhibits)}（避免重复介绍这些展品）")

    return "\n\n".join(parts)


def _build_challenge_prompt(
    persona: str,
    assumption: str,
    exhibit_context: str | None,
    client_context: str | None,
) -> str | None:
    context = client_context or ""
    should_challenge = bool(exhibit_context) or "当前讨论对象" in context or "近期对话" in context
    if not should_challenge:
        return None

    challenge = CHALLENGE_PROMPTS.get(persona, CHALLENGE_PROMPTS["A"])
    assumption_hint = ASSUMPTION_CONTEXTS.get(assumption, ASSUMPTION_CONTEXTS["D"])
    return (
        "【反身性融入提示】这不是结尾模板，不要照抄下面的文字，不要在回答末尾固定追加问题。"
        "仅当用户进入展品深挖、连续追问，或当前问题确实需要归纳含义时，"
        "把这条线索自然融入回答中的一处解释里；优先使用陈述句、转折句或小结句，"
        "不要用突兀的反问结束。若用户只问事实定义或简单说明，直接回答事实即可。"
        f"可参考初始判断：{assumption_hint} "
        f"当前身份可融入的解释线索：{challenge}"
    )


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
    if lines:
        lines.append("这些是语气和详略偏好，不是固定格式；不要为了风格偏离用户问题。")
    return "\n".join(lines) if lines else None


async def ask_stream_tour(
    db_session: AsyncSession,
    session_maker: async_sessionmaker,
    tour_session_id: str,
    message: str,
    rag_agent: Any,
    llm_provider: Any,
    exhibit_id: str | None = None,
    client_event_id: str | None = None,
    exhibit_context: str | None = None,
    client_context: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    style: Any = None,
    degraded_services: set[str] | None = None,
    tts_provider: BaseTTSProvider | None = None,
    tts_service: Any = None,
    persona: str | None = None,
) -> AsyncGenerator[str, None]:
    # ── Perf: request entry ────────────────────────────────────────────────────
    t_total = time.perf_counter()
    trace_id = str(uuid.uuid4())  # moved before get_session so log can bind it early

    # ── Session load ───────────────────────────────────────────────────────────
    _t = time.perf_counter()
    tour_session = await get_session(db_session, tour_session_id)
    _session_ms = int((time.perf_counter() - _t) * 1000)

    if degraded_services and "elasticsearch" in degraded_services:
        yield sse_tour_event(
            "error",
            data={"code": "RAG_UNAVAILABLE", "message": "检索服务暂时不可用，请稍后再试"},
        )
        return

    # ── System prompt / style (sync, negligible) ───────────────────────────────
    visited_ids = tour_session.visited_exhibit_ids or []
    system_prompt = build_system_prompt(
        persona=tour_session.persona,
        assumption=tour_session.assumption,
        hall=tour_session.current_hall,
        exhibit_context=exhibit_context,
        visited_exhibits=visited_ids,
        client_context=client_context,
    )
    style_prompt = _build_style_prompt(style)
    if style_prompt:
        system_prompt = f"[风格约束]\n{style_prompt}\n\n{system_prompt}"

    # ── Bound logger (trace_id available from line 1 now) ──────────────────────
    log = logger.bind(
        trace_id=trace_id,
        request_id=request_id_var.get(),
        tour_session_id=tour_session_id,
        exhibit_id=exhibit_id,
    )
    is_ceramic = detect_ceramic_question(message)
    log.info(
        "[tour_chat] stream request persona={} hall={} exhibit={} message_chars={} history_items={}",
        tour_session.persona,
        tour_session.current_hall,
        exhibit_id or "",
        len(message or ""),
        len(conversation_history or []),
    )

    # Emit buffered perf marks
    log.bind(stage="session_loaded", duration_ms=_session_ms, ok=True, perf=True).info(
        "[perf] session_loaded  duration_ms={}ms", _session_ms
    )
    log.bind(stage="style_parsed", ok=True, perf=True).info("[perf] style_parsed")

    # ── TTS config ─────────────────────────────────────────────────────────────
    tts_config = None
    if tts_provider is not None and tts_service is not None:
        effective_persona = persona or tour_session.persona or "A"
        _t = time.perf_counter()
        try:
            tts_config = await tts_service.get_tour_tts_config(effective_persona)
            _tts_ms = int((time.perf_counter() - _t) * 1000)
            log.debug("TTS config resolved: voice={}, persona={}", tts_config.voice if tts_config else None, effective_persona)
            log.bind(stage="tts_config", duration_ms=_tts_ms, ok=True, perf=True).info(
                "[perf] tts_config  duration_ms={}ms", _tts_ms
            )
        except Exception as e:
            _tts_ms = int((time.perf_counter() - _t) * 1000)
            log.warning("Failed to resolve TTS config for persona {}: {}", effective_persona, e)
            log.bind(stage="tts_config", duration_ms=_tts_ms, ok=False, perf=True).warning(
                "[perf] tts_config  duration_ms={}ms  ok=False", _tts_ms
            )
    else:
        log.debug("TTS not configured: provider={}, service={}", tts_provider is not None, tts_service is not None)
        log.bind(stage="tts_config", skipped=True, perf=True).debug("[perf] tts_config  skipped=True")
    tts_mgr = TTSStreamManager(tts_provider, tts_config, schema="tour")
    log.debug("TTSStreamManager enabled={}", tts_mgr.enabled)

    # ── RAG + LLM streaming ────────────────────────────────────────────────────
    t_rag = time.perf_counter()
    _first_token = False
    full_content_parts: list[str] = []
    retrieval_query = _build_exhibit_retrieval_query(message, exhibit_context)
    try:
        async for event, chunk in _stream_rag(
            rag_agent, llm_provider, message, system_prompt,
            retrieval_query=retrieval_query if retrieval_query != message else None,
            conversation_history=conversation_history if _should_use_history_for_retrieval(message) else None,
            answer_history=conversation_history,
            perf_log=log, trace_id=trace_id,
        ):
            if chunk is not None:
                # First chunk = first token delivered to client
                if not _first_token:
                    _first_token = True
                    _ftl_ms = int((time.perf_counter() - t_rag) * 1000)
                    log.bind(stage="first_token", elapsed_ms=_ftl_ms, perf=True).info(
                        "[perf] first_token  elapsed_ms={}ms", _ftl_ms
                    )
                full_content_parts.append(chunk)
                async for audio_event in tts_mgr.feed(chunk):
                    yield audio_event
            yield event
    except Exception as e:
        _err_ms = int((time.perf_counter() - t_rag) * 1000)
        log.bind(stage="stream_error", elapsed_ms=_err_ms, ok=False, perf=True).error(
            "[perf] stream_error  elapsed_ms={}ms  error={}", _err_ms, e
        )
        log.error("Tour chat RAG error: {}", e)
        yield sse_tour_event(
            "error",
            data={"code": "llm_error", "message": "AI导览暂时不可用，请稍后再试"},
        )
        return

    _stream_ms = int((time.perf_counter() - t_rag) * 1000)
    log.bind(stage="stream_done", duration_ms=_stream_ms, ok=True, perf=True).info(
        "[perf] stream_done  duration_ms={}ms", _stream_ms
    )

    # Flush remaining TTS audio
    async for audio_event in tts_mgr.flush():
        yield audio_event

    yield sse_tour_event(
        "done",
        trace_id=trace_id,
        is_ceramic_question=is_ceramic,
    )

    _total_ms = int((time.perf_counter() - t_total) * 1000)
    log.bind(stage="total", duration_ms=_total_ms, ok=True, perf=True).info(
        "[perf] total  duration_ms={}ms", _total_ms
    )

    try:
        async with session_maker() as event_session:
            event_metadata = {"question": message, "is_ceramic_question": is_ceramic}
            if client_event_id:
                event_metadata["client_event_id"] = client_event_id
            exhibit_name = _context_field(exhibit_context, "名称")
            if exhibit_name:
                event_metadata["exhibit_name"] = exhibit_name
            await record_events(event_session, tour_session_id, [
                {
                    "event_type": "exhibit_question",
                    "exhibit_id": exhibit_id,
                    "hall": tour_session.current_hall,
                    "metadata": event_metadata,
                }
            ])
    except Exception as e:
        log.error("Failed to record tour event after retries: {}", e)


async def _stream_rag(
    rag_agent: Any,
    llm_provider: Any,
    message: str,
    system_prompt: str,
    retrieval_query: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    answer_history: list[dict[str, str]] | None = None,
    perf_log: Any = None,
    trace_id: str | None = None,
) -> AsyncGenerator[tuple[str, str | None], None]:
    # ── RAG pipeline (rewrite → retrieve → merge → rerank → filter → evaluate) ──
    # skip_generate=True: generate node is a no-op, we stream via llm_provider below.
    _t = time.perf_counter()
    query_for_retrieval = retrieval_query or message
    result = await rag_agent.run(
        query_for_retrieval,
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        trace_id=trace_id,
        skip_generate=True,
    )
    _rag_ms = int((time.perf_counter() - _t) * 1000)
    if perf_log is not None:
        perf_log.bind(stage="rag_pipeline", duration_ms=_rag_ms, ok=True, perf=True).info(
            "[perf] rag_pipeline  duration_ms={}ms", _rag_ms
        )

    docs = (
        result.get("filtered_documents")
        or result.get("reranked_documents")
        or result.get("documents", [])
    )
    if perf_log is not None:
        perf_log.info("[tour_chat] rag result docs={}", len(docs))
    context = _join_context(docs)

    # ── Prompt assembly ────────────────────────────────────────────────────────
    _t = time.perf_counter()
    prompt = None
    if hasattr(rag_agent, "prompt_gateway") and rag_agent.prompt_gateway:
        rendered_prompt = await rag_agent.prompt_gateway.render(
            "rag_answer_generation",
            {"context": context, "query": message},
        )
        if rendered_prompt is not None:
            prompt = f"{system_prompt}\n\n[检索回答任务]\n{rendered_prompt}"
    if prompt is None:
        prompt = (
            f"{system_prompt}\n\n参考上下文：\n{context}\n\n"
            f"用户问题：{message}\n\n"
            "请先判断参考上下文是否与当前展厅和用户问题匹配；若不匹配，不要硬套参考上下文。"
            "请基于以上信息回答："
        )
    if prompt.startswith(system_prompt):
        prompt = prompt[len(system_prompt):].lstrip()
    _prompt_ms = int((time.perf_counter() - _t) * 1000)
    if perf_log is not None:
        perf_log.bind(stage="prompt_build", duration_ms=_prompt_ms, ok=True, perf=True).info(
            "[perf] prompt_build  duration_ms={}ms", _prompt_ms
        )

    # ── LLM streaming (2nd LLM call — see ai_latency_diagnostics.md §4) ───────
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in (answer_history or conversation_history or [])[-6:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content[:800]})
    messages.append({"role": "user", "content": prompt})
    if perf_log is not None:
        perf_log.bind(stage="llm_stream_start", perf=True).info("[perf] llm_stream_start")
    _t = time.perf_counter()
    model = getattr(llm_provider, "tour_model", None)
    if getattr(llm_provider, "supports_model_override", False) is True and model:
        stream = llm_provider.generate_stream(messages, model=model)
    else:
        stream = llm_provider.generate_stream(messages)
    async for chunk in stream:
        yield sse_tour_event("chunk", data={"content": chunk}), chunk
    _llm_ms = int((time.perf_counter() - _t) * 1000)
    if perf_log is not None:
        perf_log.bind(stage="llm_stream", duration_ms=_llm_ms, ok=True, perf=True).info(
            "[perf] llm_stream  duration_ms={}ms", _llm_ms
        )
