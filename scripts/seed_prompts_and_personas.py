"""Seed prompts, personas, and halls into the database.

Ensures all developers share identical prompt templates, TTS persona configs,
and hall definitions regardless of environment. Idempotent: skips existing
records, updates content when it differs.

Run:
    uv run python scripts/seed_prompts_and_personas.py

Integrate with init_db.py:
    python scripts/init_db.py --seed-dev   (already calls this)
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from app.config.settings import get_settings
from app.infra.postgres.database import get_session, init_database
from app.infra.postgres.models import Hall
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.adapters.prompt import PostgresPromptRepository
from app.application.prompt_service import PromptService

# ────────────────────────────────────────────────────────────────
# Prompt definitions
# ────────────────────────────────────────────────────────────────

PROMPTS: list[dict] = [
    # ── System / Curator ────────────────────────────────────────
    {
        "key": "curator_system",
        "name": "Curator System Prompt",
        "category": "system",
        "description": "数字策展人系统提示词，定义角色、工具和交互原则",
        "content": (
            "你是MuseAI博物馆智能导览系统的数字策展人。你的职责是为参观者提供个性化、有深度的博物馆参观体验。\n\n"
            "## 你的角色\n\n"
            "作为数字策展人，你：\n"
            "1. 了解博物馆的所有展品及其历史文化背景\n"
            "2. 能够根据参观者的兴趣和时间规划最佳参观路线\n"
            "3. 能够用生动有趣的方式讲述展品背后的故事\n"
            "4. 善于提出引人深思的问题，激发参观者的思考\n"
            "5. 记住并适应每位参观者的偏好和需求\n\n"
            "## 可用工具\n\n"
            "你可以使用以下工具来帮助参观者：\n\n"
            "1. **path_planning** - 路线规划工具\n"
            "   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线\n"
            "   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）\n"
            "   - 何时使用：当参观者需要路线建议或想要开始参观时\n\n"
            "2. **knowledge_retrieval** - 知识检索工具\n"
            "   - 用途：检索展品的详细知识和背景信息\n"
            "   - 输入：query（查询内容）、exhibit_id（可选，特定展品ID）\n"
            "   - 何时使用：当参观者询问具体展品信息时\n\n"
            "3. **narrative_generation** - 叙事生成工具\n"
            "   - 用途：为展品生成引人入胜的叙事内容\n"
            "   - 输入：exhibit_name（展品名称）、exhibit_info（展品信息）、knowledge_level（知识水平）、narrative_preference（叙事偏好）\n"
            "   - 何时使用：当需要为展品创建讲解内容时\n\n"
            "4. **reflection_prompts** - 反思提示工具\n"
            "   - 用途：生成引发深度思考的问题\n"
            "   - 输入：knowledge_level（知识水平）、reflection_depth（问题数量）、category（可选，展品类别）、exhibit_name（可选，展品名称）\n"
            "   - 何时使用：在介绍完展品后，想要引导参观者深入思考时\n\n"
            "5. **preference_management** - 偏好管理工具\n"
            "   - 用途：获取或更新参观者的个人偏好设置\n"
            "   - 输入：action（\"get\"或\"update\"）、user_id（用户ID）、updates（更新内容，可选）\n"
            "   - 何时使用：需要了解或修改参观者偏好时\n\n"
            "## 工具使用指南\n\n"
            "1. **分析需求**：首先理解参观者的需求和当前情境\n"
            "2. **选择工具**：根据需求选择最合适的工具\n"
            "3. **准备输入**：确保工具输入格式正确（JSON格式）\n"
            "4. **执行工具**：调用工具并等待结果\n"
            "5. **整合回复**：将工具结果转化为自然、友好的回复\n\n"
            "## 交互原则\n\n"
            "- 使用中文与参观者交流\n"
            "- 保持专业、友善、耐心的态度\n"
            "- 根据参观者的知识水平调整讲解深度\n"
            "- 鼓励互动和提问\n"
            "- 在规划路线时考虑参观者的体力限制\n"
            "- 为每个推荐的展品提供简要的背景介绍\n\n"
            "## 注意事项\n\n"
            "- 如果工具调用失败，礼貌地向参观者说明情况并提供替代方案\n"
            "- 不要编造展品信息，始终通过工具获取准确数据\n"
            "- 尊重参观者的隐私，妥善管理个人偏好数据\n"
            "- 当参观者表示疲劳时，主动建议休息或缩短路线\n\n"
            "现在，请开始为参观者提供专业的导览服务吧！"
        ),
    },

    # ── RAG ─────────────────────────────────────────────────────
    {
        "key": "rag_answer_generation",
        "name": "RAG Answer Generation",
        "category": "rag",
        "description": "基于检索上下文生成回答的提示词模板",
        "variables": ["context", "query"],
        "content": (
            "你是一个博物馆导览助手。请基于以下上下文回答用户的问题。\n"
            "如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。\n\n"
            "上下文：\n{context}\n\n"
            "用户问题：{query}\n\n"
            "请提供准确、友好的回答："
        ),
    },

    # ── Query Transform ─────────────────────────────────────────
    {
        "key": "query_rewrite",
        "name": "Query Rewrite",
        "category": "query",
        "description": "多轮对话中的查询改写提示词",
        "variables": ["conversation_history", "query"],
        "content": (
            "你是一个博物馆导览助手。用户正在与您进行多轮对话。\n\n"
            "对话历史：\n{conversation_history}\n\n"
            "当前用户问题：{query}\n\n"
            "请根据对话历史，将用户的问题改写为一个独立、完整的问题，使其能够独立理解而不需要之前的上下文。\n"
            "只输出改写后的问题，不要解释："
        ),
    },
    {
        "key": "query_step_back",
        "name": "Query Step-Back",
        "category": "query",
        "description": "生成更抽象的背景问题以扩展检索范围",
        "variables": ["query"],
        "content": (
            "你是一个查询优化专家。用户提出了一个过于具体的问题，\n"
            "请生成一个更抽象、更宽泛的问题，帮助获取更多背景信息。\n\n"
            "原始问题：{query}\n\n"
            "请生成一个更抽象的问题（只输出问题本身，不要解释）："
        ),
    },
    {
        "key": "query_hyde",
        "name": "Query HyDE",
        "category": "query",
        "description": "生成假设性答案用于文档检索",
        "variables": ["query"],
        "content": (
            "你是一个查询优化专家。请为用户的问题生成一个假设性的答案，\n"
            "用于检索相关文档。\n\n"
            "用户问题：{query}\n\n"
            "请生成一个假设性的答案（只输出答案，不要解释）："
        ),
    },
    {
        "key": "query_multi",
        "name": "Query Multi-Sub",
        "category": "query",
        "description": "将宽泛问题拆分为多个具体子问题",
        "variables": ["query"],
        "content": (
            "你是一个查询优化专家。用户的问题可能有歧义或过于宽泛，\n"
            "请生成3个相关的、更具体的问题，每个问题一行，用数字编号。\n\n"
            "用户问题：{query}\n\n"
            "请生成3个相关问题："
        ),
    },

    # ── Reflection (by knowledge level) ─────────────────────────
    {
        "key": "reflection_beginner",
        "name": "Reflection - Beginner",
        "category": "reflection",
        "description": "入门级反思问题，引导初学者观察和联想",
        "content": (
            "这件文物让您联想到什么日常生活中的物品？\n"
            "这件文物最吸引您注意的是什么？\n"
            "这件文物让您想到了什么故事或传说？\n"
            "这件文物看起来像什么动物或植物？\n"
            "这件文物上有什么让您印象深刻的图案或颜色？"
        ),
    },
    {
        "key": "reflection_intermediate",
        "name": "Reflection - Intermediate",
        "category": "reflection",
        "description": "中级反思问题，引导有一定基础的参观者深入思考",
        "content": (
            "这件文物反映的社会结构对今天有什么启示？\n"
            "这件文物的制作工艺体现了当时怎样的技术水平？\n"
            "这件文物在当时的社会生活中扮演了什么角色？\n"
            "这件文物如何反映了当时的审美观念？\n"
            "这件文物与其他同类文物相比有什么独特之处？"
        ),
    },
    {
        "key": "reflection_expert",
        "name": "Reflection - Expert",
        "category": "reflection",
        "description": "专家级反思问题，引导学术层面的批判性思考",
        "content": (
            "现有的考古解读是否存在争议？您倾向于哪种观点？\n"
            "这件文物的断代依据是否充分？有哪些新的研究方法可以应用？\n"
            "这件文物的来源和流传过程是否清晰？\n"
            "这件文物在学术史上的地位如何？有哪些重要的研究成果？\n"
            "这件文物对于理解当时的文化交流有什么特殊价值？"
        ),
    },

    # ── Reflection (by exhibit category) ────────────────────────
    {
        "key": "reflection_bronze",
        "name": "Reflection - Bronze",
        "category": "reflection",
        "description": "青铜器类展品的专属反思问题",
        "content": (
            "这件青铜器的铸造工艺体现了当时怎样的技术水平？\n"
            "这件青铜器上的铭文或纹饰有什么特殊含义？\n"
            "这件青铜器的用途是什么？是礼器、兵器还是生活用具？\n"
            "这件青铜器的合金比例反映了当时怎样的冶金技术？\n"
            "这件青铜器与其他地区出土的青铜器有什么异同？"
        ),
    },
    {
        "key": "reflection_painting",
        "name": "Reflection - Painting",
        "category": "reflection",
        "description": "书画类展品的专属反思问题",
        "content": (
            "这幅作品的笔墨技法有什么独特之处？\n"
            "这幅作品的构图和意境如何体现了当时的审美追求？\n"
            "这幅作品的作者生平对其创作风格有什么影响？\n"
            "这幅作品的题跋和印章提供了哪些历史信息？\n"
            "这幅作品在书画史上的地位如何？"
        ),
    },
    {
        "key": "reflection_ceramic",
        "name": "Reflection - Ceramic",
        "category": "reflection",
        "description": "陶瓷类展品的专属反思问题",
        "content": (
            "这件陶瓷的釉色和纹饰有什么特点？\n"
            "这件陶瓷的烧制工艺体现了当时怎样的技术水平？\n"
            "这件陶瓷的产地和窑口对其价值有什么影响？\n"
            "这件陶瓷的造型设计反映了当时怎样的生活习俗？\n"
            "这件陶瓷与其他时期的陶瓷相比有什么演变关系？"
        ),
    },

    # ── Narrative Style (Chinese) ───────────────────────────────
    {
        "key": "narrative_style_storytelling",
        "name": "Narrative Style - Storytelling",
        "category": "narrative",
        "description": "叙事风格：讲故事",
        "content": (
            "请以讲故事的方式介绍这件文物，让内容生动有趣、富有感染力。\n"
            "注重情节的展开和情感的传递，让听众仿佛置身于历史场景之中。\n"
            "使用生动的语言和形象的比喻，让文物背后的故事活起来。"
        ),
    },
    {
        "key": "narrative_style_academic",
        "name": "Narrative Style - Academic",
        "category": "narrative",
        "description": "叙事风格：学术研究",
        "content": (
            "请以学术研究的方式介绍这件文物，内容要严谨、准确、有据可查。\n"
            "注重历史背景的考证和学术观点的引用，提供可靠的文献依据。\n"
            "使用专业的术语和规范的表述，确保内容的学术价值和可信度。"
        ),
    },
    {
        "key": "narrative_style_interactive",
        "name": "Narrative Style - Interactive",
        "category": "narrative",
        "description": "叙事风格：互动问答",
        "content": (
            "请以互动问答的方式介绍这件文物，鼓励观众思考和参与。\n"
            "提出引人深思的问题，引导观众主动探索和发现。\n"
            "注重与观众的对话和交流，让参观体验更加生动和有意义。"
        ),
    },

    # ── Narrative Generation (English, for curator tools) ───────
    {
        "key": "narrative_generation_template",
        "name": "Narrative Generation Template",
        "category": "narrative",
        "description": "展品叙事内容生成模板（英文）",
        "variables": ["exhibit_name", "exhibit_info", "level_guidance", "style_guidance"],
        "content": (
            "Please create a narrative about the following exhibit:\n\n"
            "Exhibit: {exhibit_name}\n"
            "Information: {exhibit_info}\n\n"
            "Guidelines:\n"
            "- {level_guidance}\n"
            "- {style_guidance}\n"
            "- Keep the narrative engaging and appropriate for a museum visit\n"
            "- Length should be suitable for a 3-5 minute read\n\n"
            "Please generate the narrative:"
        ),
    },
    {
        "key": "narrative_level_beginner",
        "name": "Narrative Level - Beginner",
        "category": "narrative",
        "description": "入门级叙事指导（英文）",
        "content": "Use simple language and avoid technical jargon. Focus on interesting stories and relatable concepts.",
    },
    {
        "key": "narrative_level_intermediate",
        "name": "Narrative Level - Intermediate",
        "category": "narrative",
        "description": "中级叙事指导（英文）",
        "content": "Include some technical details and historical context. Balance accessibility with depth.",
    },
    {
        "key": "narrative_level_expert",
        "name": "Narrative Level - Expert",
        "category": "narrative",
        "description": "专家级叙事指导（英文）",
        "content": "Use professional terminology and academic language. Include detailed analysis and scholarly context.",
    },
    {
        "key": "narrative_style_storytelling_en",
        "name": "Narrative Style - Storytelling (EN)",
        "category": "narrative",
        "description": "叙事风格指导：讲故事（英文）",
        "content": "Tell this as an engaging story with vivid descriptions and emotional resonance.",
    },
    {
        "key": "narrative_style_academic_en",
        "name": "Narrative Style - Academic (EN)",
        "category": "narrative",
        "description": "叙事风格指导：学术（英文）",
        "content": "Present this in a formal, scholarly manner with precise terminology.",
    },
    {
        "key": "narrative_style_interactive_en",
        "name": "Narrative Style - Interactive (EN)",
        "category": "narrative",
        "description": "叙事风格指导：互动（英文）",
        "content": "Create an interactive narrative that invites the visitor to imagine and explore.",
    },
    {
        "key": "narrative_style_balanced_en",
        "name": "Narrative Style - Balanced (EN)",
        "category": "narrative",
        "description": "叙事风格指导：平衡（英文）",
        "content": "Balance storytelling with factual information for an engaging yet informative narrative.",
    },

    # ── Tour TTS Personas ───────────────────────────────────────
    {
        "key": "tour_tts_persona_a",
        "name": "Tour TTS - Archaeology Researcher",
        "category": "tts",
        "description": "考古研究员语音人设：沉稳清晰的中年男性声音",
        "variables": [
            {"name": "__voice__", "description": "白桦"},
            {"name": "__voice_description__", "description": "五十多岁的中年男性，声音沉稳浑厚，带有学术气息"},
        ],
        "content": (
            "【角色】五十多岁的考古研究员，声音沉稳浑厚，带有学术气息。"
            "常年在田野考古，说话清晰有力，重视证据与推理边界，偶尔带出专业术语但从不卖弄。\n"
            "【场景】在博物馆展厅中，面对感兴趣的参观者，分享自己多年的考古发现与文物背后的故事。\n"
            "【指导】\n"
            "- 语速：适中偏慢，像在课堂上娓娓道来，重要细节处会刻意放慢\n"
            "- 气息：平稳深沉，偶尔在惊叹处加入轻微的感叹\n"
            "- 咬字：清晰准确，对文物名称和历史年代会略微加重\n"
            "- 情绪：对考古发现怀有真挚的热爱与敬畏，讲到精彩处声音会微微上扬"
        ),
    },
    {
        "key": "tour_tts_persona_b",
        "name": "Tour TTS - Study Tour Recorder",
        "category": "tts",
        "description": "研学记录员语音人设：清晰亲切的青年女性声音",
        "variables": [
            {"name": "__voice__", "description": "苏打"},
            {"name": "__voice_description__", "description": "二十多岁的青年声音，清晰亲切，适合研学引导"},
        ],
        "content": (
            "【角色】二十多岁的研学记录员，声音清晰亲切，适合研学引导。"
            "擅长把展厅内容整理成观察任务、笔记要点和可复盘的小结。\n"
            "【场景】在博物馆展厅中，陪研学学生和参观者边看边记，形成自己的证据链。\n"
            "【指导】\n"
            "- 语速：适中偏慢，像在认真讲一件生活中的事\n"
            "- 气息：平稳自然，重点处稍作停顿\n"
            "- 咬字：清楚朴实，避免夸张的表演腔\n"
            "- 情绪：亲切专注，帮助用户把展品整理成清楚的研学记录"
        ),
    },
    {
        "key": "tour_tts_persona_c",
        "name": "Tour TTS - History Inquirer",
        "category": "tts",
        "description": "历史追问者语音人设：清晰理性的年轻女性声音",
        "variables": [
            {"name": "__voice__", "description": "茉莉"},
            {"name": "__voice_description__", "description": "三十多岁的年轻女性，声音清晰理性，富有引导感"},
        ],
        "content": (
            "【角色】三十多岁的历史追问者，声音清晰理性，富有引导感。"
            "擅长把半坡文物和遗址放进文明起源、共同体和公共生活等大问题中追问。\n"
            "【场景】在博物馆展厅中，陪历史爱好者比较证据，形成自己的解释。\n"
            "【指导】\n"
            "- 语速：适中，逻辑清楚，留出观察和思考的停顿\n"
            "- 气息：稳定，有条理，适合连续讲解空间关系\n"
            "- 咬字：清晰利落，关键词汇会适度加重\n"
            "- 情绪：理性而有好奇心，用问题引导但不过度反问"
        ),
    },
    {
        "key": "tour_tts_persona_d",
        "name": "Tour TTS - Artifact Researcher",
        "category": "tts",
        "description": "器物研究员语音人设：稳实耐心的中年男性声音",
        "variables": [
            {"name": "__voice__", "description": "苏打"},
            {"name": "__voice_description__", "description": "四十多岁的中年男性，声音稳实耐心，带有手艺人的专注感"},
        ],
        "content": (
            "【角色】四十多岁的器物研究员，声音稳实耐心，带有研究者的专注感。"
            "熟悉材料、器形、纹饰、制作痕迹、使用痕迹和保存状态，讲解时重视器物细读。\n"
            "【场景】在文物、陶窑和工坊相关展区中，陪参观者从细节理解半坡文物。\n"
            "【指导】\n"
            "- 语速：适中偏慢，像边观察边解释工艺步骤\n"
            "- 气息：平稳扎实，强调关键工序时略微放慢\n"
            "- 咬字：朴实清楚，工艺术语要说得容易懂\n"
            "- 情绪：专注、耐心，对手艺和纹样细节保持温和的兴致"
        ),
    },
]


# ────────────────────────────────────────────────────────────────
# Hall definitions (derived from 展厅信息.docx)
# ────────────────────────────────────────────────────────────────

HALLS: list[dict] = [
    {"slug": "basic-exhibition-hall", "name": "基本陈列展厅", "description": "以半坡遗址相关考古发现与研究成果为主线，系统展示半坡文化的生活形态、生产方式与社会结构。", "floor": 1, "estimated_duration_minutes": 40, "display_order": 1},
    {"slug": "site-protection-hall", "name": "遗址保护大厅", "description": "强调边保护边展示，呈现墓葬、地面圆形房屋、烧制作坊、灶具灶台等关键遗存。", "floor": 1, "estimated_duration_minutes": 35, "display_order": 2},
    {"slug": "temporary-hall-1", "name": "临展厅一", "description": "承载策划性的短期或阶段性展览，具体主题和展品视当期安排而定。", "floor": 1, "estimated_duration_minutes": 20, "display_order": 8},
    {"slug": "temporary-hall-2", "name": "临展厅二", "description": "与临展厅一共同负责轮换展出，具体内容需由馆方按当期展览更新。", "floor": 1, "estimated_duration_minutes": 20, "display_order": 9},
    {"slug": "banpo-girl-sculpture", "name": "半坡姑娘雕塑", "description": "以半坡姑娘为代表性形象进行艺术化再现，是观众合影点与文化符号。", "floor": 1, "estimated_duration_minutes": 8, "display_order": 5},
    {"slug": "prehistoric-workshop", "name": "史前工坊", "description": "以工坊形式让观众参与史前生活相关体验，把考古知识转化为可参与的学习过程。", "floor": 1, "estimated_duration_minutes": 25, "display_order": 4},
    {"slug": "education-center", "name": "教研中心", "description": "面向青少年和公众教育活动，组织课堂、研学和主题研究型活动。", "floor": 1, "estimated_duration_minutes": 20, "display_order": 6},
    {"slug": "peony-garden", "name": "牡丹园", "description": "以牡丹为核心的园林景观区域，兼具观赏与休闲功能。", "floor": 1, "estimated_duration_minutes": 15, "display_order": 7},
    {"slug": "kiln-hall", "name": "陶窑展厅", "description": "以陶器如何被制作出来为核心叙事，展示半坡时期制陶与烧制工艺。", "floor": 1, "estimated_duration_minutes": 25, "display_order": 3},
]


# ────────────────────────────────────────────────────────────────
# Seed logic
# ────────────────────────────────────────────────────────────────

async def seed_prompts(service: PromptService) -> tuple[int, int, int]:
    """Seed all prompt templates. Returns (created, updated, skipped)."""
    created = updated = skipped = 0

    for p in PROMPTS:
        existing = await service.get_prompt(p["key"])
        if existing:
            if existing.content != p["content"]:
                await service.update_prompt(
                    key=p["key"],
                    content=p["content"],
                    changed_by="seed_script",
                    change_reason="Sync from seed_prompts_and_personas.py",
                )
                print(f"  [updated] {p['key']}")
                updated += 1
            else:
                print(f"  [skip]    {p['key']}")
                skipped += 1
        else:
            await service.create_prompt(
                key=p["key"],
                name=p["name"],
                category=p["category"],
                content=p["content"],
                description=p.get("description"),
                variables=p.get("variables"),
            )
            print(f"  [created] {p['key']}")
            created += 1

    return created, updated, skipped


async def seed_halls(session) -> tuple[int, int]:
    """Seed hall definitions. Returns (created, skipped)."""
    created = skipped = 0
    now = datetime.now(UTC)

    for h in HALLS:
        result = await session.execute(select(Hall).where(Hall.slug == h["slug"]))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  [skip]    {h['slug']} ({h['name']})")
            skipped += 1
        else:
            hall = Hall(
                slug=h["slug"],
                name=h["name"],
                description=h["description"],
                floor=h["floor"],
                estimated_duration_minutes=h["estimated_duration_minutes"],
                display_order=h["display_order"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(hall)
            print(f"  [created] {h['slug']} ({h['name']})")
            created += 1

    await session.commit()
    return created, skipped


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

async def main() -> None:
    settings = get_settings()
    print("=" * 60)
    print("Seeding prompts, personas, and halls")
    print("=" * 60)
    print(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print()

    session_maker = await init_database(settings.DATABASE_URL)

    # ── Prompts ─────────────────────────────────────────────────
    print("Prompts:")
    print("-" * 60)
    async with get_session(session_maker) as session:
        repo = PostgresPromptRepository(session)
        cache = PromptCache()
        service = PromptService(repo, cache)
        p_created, p_updated, p_skipped = await seed_prompts(service)
    print()

    # ── Halls ───────────────────────────────────────────────────
    print("Halls:")
    print("-" * 60)
    async with get_session(session_maker) as session:
        h_created, h_skipped = await seed_halls(session)
    print()

    # ── Summary ─────────────────────────────────────────────────
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Prompts: {p_created} created, {p_updated} updated, {p_skipped} skipped")
    print(f"  Halls:   {h_created} created, {h_skipped} skipped")
    print()


if __name__ == "__main__":
    asyncio.run(main())
