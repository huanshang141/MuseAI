# backend/app/application/curator_service.py
import re
from typing import Any

from app.application.hall_normalizer import CANONICAL_HALLS, hall_display_name, normalize_hall
from app.application.ports.repositories import CuratorAgentPort
from app.domain.exceptions import EntityNotFoundError

from .exhibit_service import ExhibitService
from .profile_service import ProfileService


_PERSONA_ALIASES = {
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
    "default": "default",
    "student": "B",
    "historian": "C",
    "artifact": "D",
    "artisan": "D",
    "resident": "B",
    "community": "C",
}

_ROUTE_PROFILES = {
    "A": {
        "theme": "考古研究路线",
        "summary": "从代表性器物进入，再回到遗址和陶窑，用证据、遗迹和工艺流程建立可解释的半坡图景。",
        "steps": [
            {
                "hall_slug": "basic-exhibition-hall",
                "title": "先看核心证据",
                "reason": "基本陈列展厅集中呈现半坡代表性器物，适合先建立文物证据框架。",
                "focus": "关注器物形制、纹饰、出土背景与可支持的推断。",
                "questions": ["哪些细节能作为考古证据？", "器物差异能说明什么？"],
            },
            {
                "hall_slug": "site-protection-hall",
                "title": "回到遗址现场",
                "reason": "遗址保护大厅能把器物证据放回房屋、墓葬、作坊等空间关系中检验。",
                "focus": "观察地层、遗迹位置、居住结构和公共空间线索。",
                "questions": ["空间布局反映了怎样的社会组织？", "遗迹能验证哪些推断？"],
            },
            {
                "hall_slug": "kiln-hall",
                "title": "补上生产链条",
                "reason": "陶窑展厅能说明陶器不是孤立展品，而是材料、火候和流程共同作用的结果。",
                "focus": "观察制坯、干燥、入窑和烧成证据。",
                "questions": ["陶窑结构说明了什么技术能力？", "烧成痕迹能怎样被解读？"],
            },
            {
                "hall_slug": "prehistoric-workshop",
                "title": "用操作理解技术",
                "reason": "史前工坊能把考古证据转成可体验的技术问题，帮助理解制作难度。",
                "focus": "把观察到的器物特征和手作流程互相对应。",
                "questions": ["哪些步骤最考验经验？", "手作体验能帮助验证什么？"],
            },
        ],
    },
    "B": {
        "theme": "研学记录路线",
        "summary": "把参观拆成观察任务、记录点和复盘线索，方便形成可整理、可汇报的研学笔记。",
        "steps": [
            {
                "hall_slug": "basic-exhibition-hall",
                "title": "建立观察样本",
                "reason": "先看基本陈列，能快速获得器物、生活和生产方式的核心样本。",
                "focus": "记录展品名称、用途、材料和最能说明问题的细节。",
                "questions": ["我应该先记录哪些信息？", "这些展品分别说明什么？"],
            },
            {
                "hall_slug": "education-center",
                "title": "整理研学问题",
                "reason": "教研中心适合把看到的材料转化为问题清单和复盘框架。",
                "focus": "把观察点整理成证据链、问题链和小结。",
                "questions": ["怎样把观察整理成研学报告？", "哪些问题适合继续查证？"],
            },
            {
                "hall_slug": "prehistoric-workshop",
                "title": "用体验加深记录",
                "reason": "史前工坊能把抽象的技术和劳动转化为可感知的体验。",
                "focus": "记录动手环节、难点和与展品之间的对应关系。",
                "questions": ["体验能补充哪些书面记录？", "制作难点说明了什么？"],
            },
            {
                "hall_slug": "site-protection-hall",
                "title": "补充空间证据",
                "reason": "遗址空间能帮助研学记录从单件展品扩展到聚落生活。",
                "focus": "记录房屋、墓葬和公共空间的相互位置。",
                "questions": ["空间布局怎样进入笔记？", "遗址和器物如何互相印证？"],
            },
        ],
    },
    "C": {
        "theme": "历史追问路线",
        "summary": "从聚落空间出发，追问半坡人的社会组织、文明起源线索，以及这些问题与今天的关系。",
        "steps": [
            {
                "hall_slug": "site-protection-hall",
                "title": "从聚落提问",
                "reason": "遗址保护大厅展示房屋、墓葬、作坊等空间关系，适合追问社会如何组织。",
                "focus": "观察空间布局、公共生活和可能的分工线索。",
                "questions": ["聚落布局说明了怎样的共同生活？", "哪些遗迹能反映社会规则？"],
            },
            {
                "hall_slug": "basic-exhibition-hall",
                "title": "用器物补充社会图景",
                "reason": "基本陈列中的工具、陶器和装饰物能补充生活分工、审美和身份表达。",
                "focus": "比较不同器物背后的生活方式和社会含义。",
                "questions": ["器物差异反映了什么社会关系？", "审美和实用如何同时出现？"],
            },
            {
                "hall_slug": "banpo-girl-sculpture",
                "title": "连接人物想象",
                "reason": "半坡姑娘雕塑适合把考古材料与公众记忆连接起来，但仍要区分事实与想象。",
                "focus": "思考我们如何根据证据理解半坡人的形象。",
                "questions": ["公众形象如何影响历史理解？", "哪些想象需要证据约束？"],
            },
            {
                "hall_slug": "education-center",
                "title": "形成自己的追问",
                "reason": "最后把参观转化成问题：半坡为何重要，它和今天的公共生活有什么关系。",
                "focus": "整理文明起源、社会组织和现实关联三类问题。",
                "questions": ["半坡经验和今天有什么关系？", "我还想继续追问什么？"],
            },
        ],
    },
    "D": {
        "theme": "器物观察路线",
        "summary": "优先观察器形、材料、纹饰、工艺和使用痕迹，再用陶窑与工坊补足制作流程。",
        "steps": [
            {
                "hall_slug": "basic-exhibition-hall",
                "title": "先看器物成品",
                "reason": "基本陈列展厅集中呈现代表性器物，适合先观察形制、纹饰、材料和使用痕迹。",
                "focus": "比较器形、口沿、底部、纹饰和磨损位置。",
                "questions": ["这类器物主要用来做什么？", "纹饰和痕迹能说明什么？"],
            },
            {
                "hall_slug": "kiln-hall",
                "title": "理解烧制工艺",
                "reason": "陶窑展厅能解释陶器从泥料到成品的关键变化，补足工艺判断。",
                "focus": "观察制坯、干燥、火候、窑炉结构和烧成痕迹。",
                "questions": ["火候怎样影响陶器状态？", "陶窑结构体现了哪些经验？"],
            },
            {
                "hall_slug": "prehistoric-workshop",
                "title": "把观察转成操作问题",
                "reason": "史前工坊能帮助你用手作流程反推器物制作中的选择和难点。",
                "focus": "把材料处理、成型、修整和装饰步骤与展品细节对应。",
                "questions": ["哪一步最影响最终器形？", "手作痕迹可能保留在哪里？"],
            },
            {
                "hall_slug": "site-protection-hall",
                "title": "回到使用场景",
                "reason": "遗址现场能把器物放回房屋、灶台、作坊等生活场景，理解它们如何被使用。",
                "focus": "观察器物可能出现的位置与日常活动之间的关系。",
                "questions": ["器物在哪里被使用？", "使用场景能改变我们对器物的理解吗？"],
            },
        ],
    },
}
_ROUTE_PROFILES["default"] = {
    "theme": "AI 默认参观路线",
    "summary": "按普通游客第一次参观的节奏，先建立半坡遗址的整体印象，再进入遗址空间和陶器生产线索。",
    "steps": [
        {
            "hall_slug": "basic-exhibition-hall",
            "title": "先建立整体印象",
            "reason": "基本陈列展厅集中呈现半坡文化的核心展品和生活图景，适合作为首次参观入口。",
            "focus": "先看半坡人的生活、生产工具和代表性陶器，形成整体框架。",
            "questions": ["半坡遗址最重要的看点是什么？", "这些展品能说明怎样的生活？"],
        },
        {
            "hall_slug": "site-protection-hall",
            "title": "再走进遗址空间",
            "reason": "遗址保护大厅能把刚才看到的器物放回房屋、墓葬、壕沟和作坊的真实空间中。",
            "focus": "观察居住区、墓葬和公共设施的位置关系。",
            "questions": ["半坡人的村落怎样组织？", "遗址和展品怎样互相印证？"],
        },
        {
            "hall_slug": "kiln-hall",
            "title": "补上制陶线索",
            "reason": "陶窑展厅能解释陶器从泥料到成品的过程，让代表性陶器不只是孤立展品。",
            "focus": "理解制坯、干燥、入窑和烧成的基本流程。",
            "questions": ["陶器是怎样制作出来的？", "火候和窑炉结构有什么作用？"],
        },
        {
            "hall_slug": "prehistoric-workshop",
            "title": "用体验收束参观",
            "reason": "史前工坊适合把看到的工具、材料和工艺转化成可感知的体验。",
            "focus": "把手作体验和前面看到的器物、工具联系起来。",
            "questions": ["亲手体验能帮助理解什么？", "哪些技术最难掌握？"],
        },
    ],
}


def _normalize_persona(interests: list[str] | None) -> str:
    if not interests:
        return "default"

    for raw in interests:
        text = str(raw or "").strip()
        if not text:
            continue
        match = re.search(
            r"(?:persona|personaId)\s*[:=]\s*(default|student|historian|artifact|artisan|resident|community|[A-Da-d])\b",
            text,
        )
        if match:
            token = match.group(1)
            return _PERSONA_ALIASES.get(token, _PERSONA_ALIASES.get(token.lower(), token.upper()))

    joined = " ".join(str(item) for item in interests)
    for alias, code in _PERSONA_ALIASES.items():
        if alias != "default" and alias in joined:
            return code
    return "default"


def _step_count_for_time(available_time: int) -> int:
    if available_time <= 35:
        return 2
    if available_time <= 75:
        return 3
    if available_time <= 120:
        return 4
    return 5


def _allocate_minutes(total_minutes: int, count: int) -> list[int]:
    count = max(1, count)
    base = max(10, total_minutes // count)
    minutes = [base for _ in range(count)]
    remainder = max(0, total_minutes - base * count)
    for idx in range(remainder):
        minutes[idx % count] += 1
    return minutes


def format_route_plan_text(route: dict[str, Any]) -> str:
    lines = [route["summary"]]
    for step in route["steps"]:
        lines.append(
            f"{step['order']}. {step['hall_name']}：{step['title']}。{step['focus']}"
        )
    return "\n".join(lines)


def _route_plan_text(route: dict[str, Any]) -> str:
    return format_route_plan_text(route)


def build_structured_route(
    available_time: int,
    interests: list[str] | None = None,
) -> dict[str, Any]:
    persona = _normalize_persona(interests)
    profile = _ROUTE_PROFILES.get(persona, _ROUTE_PROFILES["default"])
    step_count = min(len(profile["steps"]), _step_count_for_time(available_time))
    step_count = max(2, min(5, step_count))
    minutes = _allocate_minutes(max(available_time, 20), step_count)

    steps: list[dict[str, Any]] = []
    for idx, tpl in enumerate(profile["steps"][:step_count]):
        hall_slug = normalize_hall(tpl["hall_slug"])
        if hall_slug not in CANONICAL_HALLS:
            hall_slug = "basic-exhibition-hall"
        steps.append(
            {
                "order": idx + 1,
                "hall_slug": hall_slug,
                "hall_name": hall_display_name(hall_slug),
                "title": tpl["title"],
                "reason": tpl["reason"],
                "focus": tpl["focus"],
                "estimated_minutes": minutes[idx],
                "suggested_questions": list(tpl["questions"]),
            }
        )

    return {
        "source": "curator",
        "total_minutes": available_time,
        "theme": profile["theme"],
        "summary": profile["summary"],
        "steps": steps,
    }


class CuratorService:
    """策展人协调服务，整合展品、画像和策展智能体提供导览服务。"""

    def __init__(
        self,
        curator_agent: CuratorAgentPort,
        profile_service: ProfileService,
        exhibit_service: ExhibitService,
    ):
        self._curator_agent = curator_agent
        self._profile_service = profile_service
        self._exhibit_service = exhibit_service

    async def plan_tour(
        self,
        user_id: str,
        available_time: int,
        interests: list[str] | None = None,
    ) -> dict[str, Any]:
        """规划参观路线。

        Args:
            user_id: 用户ID
            available_time: 可用时间（分钟）
            interests: 兴趣标签列表（可选，默认使用用户画像中的兴趣）

        Returns:
            包含路线规划结果的字典
        """
        is_guest = user_id.startswith("guest-")
        if is_guest:
            tour_interests = interests or []
            visited_ids: list[str] = []
        else:
            # 获取或创建用户画像
            profile = await self._profile_service.get_or_create_profile(user_id)

            # 使用用户兴趣或传入的兴趣
            tour_interests = interests if interests is not None else profile.interests
            visited_ids = [eid.value for eid in profile.visited_exhibit_ids]

        route = build_structured_route(available_time, tour_interests)

        # 构建规划请求
        plan_request = f"""请为我规划一条博物馆参观路线。

可用时间：{available_time}分钟
兴趣标签：{', '.join(tour_interests) if tour_interests else '无特定偏好'}
已参观展品：{', '.join(visited_ids) if visited_ids else '无'}

请使用path_planning工具规划路线。"""

        if is_guest:
            result = {"output": _route_plan_text(route), "session_id": ""}
        else:
            # 调用策展智能体；结构化 route 已由规则生成，智能体失败也不影响接口可用。
            try:
                result = await self._curator_agent.run(
                    user_input=plan_request,
                    chat_history=[],
                )
            except Exception:
                result = {"output": _route_plan_text(route), "session_id": ""}

        return {
            "user_id": user_id,
            "available_time": available_time,
            "interests": tour_interests,
            "visited_exhibit_ids": visited_ids,
            "plan": result.get("output") or _route_plan_text(route),
            "route": route,
            "session_id": result.get("session_id", ""),
        }

    async def generate_narrative(
        self,
        user_id: str,
        exhibit_id: str,
    ) -> dict[str, Any]:
        """为展品生成叙事内容。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            包含叙事内容的字典

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        # 获取展品信息
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 获取用户画像
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 构建叙事生成请求
        narrative_request = f"""请为以下展品生成讲解内容：

展品名称：{exhibit.name}
展品描述：{exhibit.description}
展品年代：{exhibit.era}
展品类别：{exhibit.category}

用户知识水平：{profile.knowledge_level}
用户叙事偏好：{profile.narrative_preference}

请使用narrative_generation工具生成叙事内容。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=narrative_request,
            chat_history=[],
        )

        # 记录参观
        await self._profile_service.record_visit(user_id, exhibit_id)

        return {
            "user_id": user_id,
            "exhibit_id": exhibit_id,
            "exhibit_name": exhibit.name,
            "narrative": result.get("output", ""),
            "knowledge_level": profile.knowledge_level,
            "narrative_preference": profile.narrative_preference,
            "session_id": result.get("session_id", ""),
        }

    async def get_reflection_prompts(
        self,
        user_id: str,
        exhibit_id: str,
    ) -> dict[str, Any]:
        """获取展品的反思提示问题。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            包含反思提示的字典

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        # 获取展品信息
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 获取用户画像
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 构建反思提示请求
        reflection_request = f"""请为以下展品生成反思提示问题：

展品名称：{exhibit.name}
展品类别：{exhibit.category}

用户知识水平：{profile.knowledge_level}
反思深度：{profile.reflection_depth}

请使用reflection_prompts工具生成反思问题。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=reflection_request,
            chat_history=[],
        )

        return {
            "user_id": user_id,
            "exhibit_id": exhibit_id,
            "exhibit_name": exhibit.name,
            "reflection_prompts": result.get("output", ""),
            "knowledge_level": profile.knowledge_level,
            "reflection_depth": profile.reflection_depth,
            "session_id": result.get("session_id", ""),
        }

    async def chat(
        self,
        user_id: str,
        message: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """与策展人进行对话。

        Args:
            user_id: 用户ID
            message: 用户消息
            chat_history: 聊天历史（可选）

        Returns:
            包含回复内容的字典
        """
        # 获取用户画像以提供上下文
        profile = await self._profile_service.get_or_create_profile(user_id)

        # 构建系统上下文
        context = f"""当前用户信息：
- 知识水平：{profile.knowledge_level}
- 叙事偏好：{profile.narrative_preference}
- 兴趣标签：{', '.join(profile.interests) if profile.interests else '无'}
- 已参观展品数：{len(profile.visited_exhibit_ids)}

用户问题：{message}"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=context,
            chat_history=chat_history or [],
        )

        return {
            "user_id": user_id,
            "message": message,
            "response": result.get("output", ""),
            "session_id": result.get("session_id", ""),
            "error": result.get("error"),
        }

    async def get_exhibit_info(
        self,
        user_id: str,
        exhibit_id: str,
    ) -> dict[str, Any]:
        """获取展品详细信息（包含知识检索）。

        Args:
            user_id: 用户ID
            exhibit_id: 展品ID

        Returns:
            包含展品信息和相关知识的字典

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        # 获取展品信息
        exhibit = await self._exhibit_service.get_exhibit(exhibit_id)
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 获取用户画像
        await self._profile_service.get_or_create_profile(user_id)

        # 构建知识检索请求
        knowledge_request = f"""请检索以下展品的相关知识：

展品名称：{exhibit.name}
展品描述：{exhibit.description}
展品年代：{exhibit.era}
展品类别：{exhibit.category}

请使用knowledge_retrieval工具检索相关知识，exhibit_id为"{exhibit_id}"。"""

        # 调用策展智能体
        result = await self._curator_agent.run(
            user_input=knowledge_request,
            chat_history=[],
        )

        return {
            "user_id": user_id,
            "exhibit_id": exhibit_id,
            "exhibit": {
                "id": exhibit.id.value,
                "name": exhibit.name,
                "description": exhibit.description,
                "category": exhibit.category,
                "era": exhibit.era,
                "hall": exhibit.hall,
                "importance": exhibit.importance,
                "estimated_visit_time": exhibit.estimated_visit_time,
            },
            "knowledge": result.get("output", ""),
            "session_id": result.get("session_id", ""),
        }
