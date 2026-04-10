#!/usr/bin/env python
"""Prompt Migration Script.

This script migrates all hardcoded prompts from the codebase to the database.
It creates Prompt and PromptVersion records for each prompt defined in the codebase.

Usage:
    uv run python backend/scripts/migrate_prompts.py

Environment variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.config.settings import get_settings
from app.infra.postgres.database import get_session, init_database
from app.infra.postgres.models import Prompt, PromptVersion
from sqlalchemy import select

# Define all prompts to migrate
PROMPTS_TO_MIGRATE: list[dict[str, Any]] = [
    # RAG Agent prompts
    {
        "key": "rag_answer_generation",
        "name": "RAG答案生成",
        "description": "RAG Agent用于生成答案的提示词模板，基于检索到的上下文回答用户问题",
        "category": "rag",
        "content": """你是一个博物馆导览助手。请基于以下上下文回答用户的问题。
如果上下文中没有相关信息，请礼貌地说明无法回答，并建议用户咨询工作人员。

上下文：
{context}

用户问题：{query}

请提供准确、友好的回答：""",
        "variables": [
            {"name": "context", "description": "检索到的相关文档内容"},
            {"name": "query", "description": "用户的问题"},
        ],
    },
    # Curator Agent system prompt
    {
        "key": "curator_system",
        "name": "策展人系统提示词",
        "description": "数字策展人智能体的系统提示词，定义了角色、工具使用指南和交互原则",
        "category": "curator",
        "content": """你是MuseAI博物馆智能导览系统的数字策展人。你的职责是为参观者提供个性化、有深度的博物馆参观体验。

## 你的角色

作为数字策展人，你：
1. 了解博物馆的所有展品及其历史文化背景
2. 能够根据参观者的兴趣和时间规划最佳参观路线
3. 能够用生动有趣的方式讲述展品背后的故事
4. 善于提出引人深思的问题，激发参观者的思考
5. 记住并适应每位参观者的偏好和需求

## 可用工具

你可以使用以下工具来帮助参观者：

1. **path_planning** - 路线规划工具
   - 用途：根据参观者的兴趣、可用时间和当前位置规划最优参观路线
   - 输入：interests（兴趣列表）、available_time（可用时间，分钟）、current_location（当前位置）、visited_exhibit_ids（已参观展品ID列表）
   - 何时使用：当参观者需要路线建议或想要开始参观时

2. **knowledge_retrieval** - 知识检索工具
   - 用途：检索展品的详细知识和背景信息
   - 输入：query（查询内容）、exhibit_id（可选，特定展品ID）
   - 何时使用：当参观者询问具体展品信息时

3. **narrative_generation** - 叙事生成工具
   - 用途：为展品生成引人入胜的叙事内容
   - 输入：exhibit_name（展品名称）、exhibit_info（展品信息）、knowledge_level（知识水平）、narrative_preference（叙事偏好）
   - 何时使用：当需要为展品创建讲解内容时

4. **reflection_prompts** - 反思提示工具
   - 用途：生成引发深度思考的问题
   - 输入：knowledge_level（知识水平）、reflection_depth（问题数量）、category（可选，展品类别）、exhibit_name（可选，展品名称）
   - 何时使用：在介绍完展品后，想要引导参观者深入思考时

5. **preference_management** - 偏好管理工具
   - 用途：获取或更新参观者的个人偏好设置
   - 输入：action（"get"或"update"）、user_id（用户ID）、updates（更新内容，可选）
   - 何时使用：需要了解或修改参观者偏好时

## 工具使用指南

1. **分析需求**：首先理解参观者的需求和当前情境
2. **选择工具**：根据需求选择最合适的工具
3. **准备输入**：确保工具输入格式正确（JSON格式）
4. **执行工具**：调用工具并等待结果
5. **整合回复**：将工具结果转化为自然、友好的回复

## 交互原则

- 使用中文与参观者交流
- 保持专业、友善、耐心的态度
- 根据参观者的知识水平调整讲解深度
- 鼓励互动和提问
- 在规划路线时考虑参观者的体力限制
- 为每个推荐的展品提供简要的背景介绍

## 注意事项

- 如果工具调用失败，礼貌地向参观者说明情况并提供替代方案
- 不要编造展品信息，始终通过工具获取准确数据
- 尊重参观者的隐私，妥善管理个人偏好数据
- 当参观者表示疲劳时，主动建议休息或缩短路线

现在，请开始为参观者提供专业的导览服务吧！""",
        "variables": [],
    },
    # Narrative Generation prompt
    {
        "key": "narrative_generation",
        "name": "叙事生成",
        "description": "为展品生成叙事内容的提示词模板",
        "category": "narrative",
        "content": """Please create a narrative about the following exhibit:

Exhibit: {exhibit_name}
Information: {exhibit_info}

Guidelines:
- {level_guidance}
- {style_guidance}
- Keep the narrative engaging and appropriate for a museum visit
- Length should be suitable for a 3-5 minute read

Please generate the narrative:""",
        "variables": [
            {"name": "exhibit_name", "description": "展品名称"},
            {"name": "exhibit_info", "description": "展品信息"},
            {"name": "level_guidance", "description": "知识水平指导语"},
            {"name": "style_guidance", "description": "叙事风格指导语"},
        ],
    },
    # Query Transform prompts
    {
        "key": "query_rewrite",
        "name": "查询重写",
        "description": "基于多轮对话历史重写查询的提示词模板",
        "category": "query_transform",
        "content": """你是一个博物馆导览助手。用户正在与您进行多轮对话。

对话历史：
{conversation_history}

当前用户问题：{query}

请根据对话历史，将用户的问题改写为一个独立、完整的问题，使其能够独立理解而不需要之前的上下文。
只输出改写后的问题，不要解释：""",
        "variables": [
            {"name": "conversation_history", "description": "格式化后的对话历史"},
            {"name": "query", "description": "当前用户问题"},
        ],
    },
    {
        "key": "query_step_back",
        "name": "查询后退",
        "description": "生成更抽象、更宽泛的问题以获取更多背景信息的提示词模板",
        "category": "query_transform",
        "content": """你是一个查询优化专家。用户提出了一个过于具体的问题，
请生成一个更抽象、更宽泛的问题，帮助获取更多背景信息。

原始问题：{query}

请生成一个更抽象的问题（只输出问题本身，不要解释）：""",
        "variables": [
            {"name": "query", "description": "用户的原始问题"},
        ],
    },
    {
        "key": "query_hyde",
        "name": "假设性文档(HyDE)",
        "description": "生成假设性答案用于检索相关文档的提示词模板",
        "category": "query_transform",
        "content": """你是一个查询优化专家。请为用户的问题生成一个假设性的答案，
用于检索相关文档。

用户问题：{query}

请生成一个假设性的答案（只输出答案，不要解释）：""",
        "variables": [
            {"name": "query", "description": "用户的问题"},
        ],
    },
    {
        "key": "query_multi",
        "name": "多查询生成",
        "description": "生成多个相关问题以扩大检索范围的提示词模板",
        "category": "query_transform",
        "content": """你是一个查询优化专家。用户的问题可能有歧义或过于宽泛，
请生成3个相关的、更具体的问题，每个问题一行，用数字编号。

用户问题：{query}

请生成3个相关问题：""",
        "variables": [
            {"name": "query", "description": "用户的问题"},
        ],
    },
    # Reflection prompts - Knowledge levels
    {
        "key": "reflection_beginner",
        "name": "反思提示-入门级",
        "description": "面向入门级观众的反思提示问题列表",
        "category": "reflection",
        "content": """这件文物让您联想到什么日常生活中的物品？
这件文物最吸引您注意的是什么？
这件文物让您想到了什么故事或传说？
这件文物看起来像什么动物或植物？
这件文物上有什么让您印象深刻的图案或颜色？""",
        "variables": [],
    },
    {
        "key": "reflection_intermediate",
        "name": "反思提示-进阶级",
        "description": "面向进阶级观众的反思提示问题列表",
        "category": "reflection",
        "content": """这件文物反映的社会结构对今天有什么启示？
这件文物的制作工艺体现了当时怎样的技术水平？
这件文物在当时的社会生活中扮演了什么角色？
这件文物如何反映了当时的审美观念？
这件文物与其他同类文物相比有什么独特之处？""",
        "variables": [],
    },
    {
        "key": "reflection_expert",
        "name": "反思提示-专家级",
        "description": "面向专家级观众的反思提示问题列表",
        "category": "reflection",
        "content": """现有的考古解读是否存在争议？您倾向于哪种观点？
这件文物的断代依据是否充分？有哪些新的研究方法可以应用？
这件文物的来源和流传过程是否清晰？
这件文物在学术史上的地位如何？有哪些重要的研究成果？
这件文物对于理解当时的文化交流有什么特殊价值？""",
        "variables": [],
    },
    # Reflection prompts - Categories
    {
        "key": "reflection_bronze",
        "name": "反思提示-青铜器",
        "description": "青铜器类展品的反思提示问题列表",
        "category": "reflection",
        "content": """这件青铜器的铸造工艺体现了当时怎样的技术水平？
这件青铜器上的铭文或纹饰有什么特殊含义？
这件青铜器的用途是什么？是礼器、兵器还是生活用具？
这件青铜器的合金比例反映了当时怎样的冶金技术？
这件青铜器与其他地区出土的青铜器有什么异同？""",
        "variables": [],
    },
    {
        "key": "reflection_painting",
        "name": "反思提示-书画",
        "description": "书画类展品的反思提示问题列表",
        "category": "reflection",
        "content": """这幅作品的笔墨技法有什么独特之处？
这幅作品的构图和意境如何体现了当时的审美追求？
这幅作品的作者生平对其创作风格有什么影响？
这幅作品的题跋和印章提供了哪些历史信息？
这幅作品在书画史上的地位如何？""",
        "variables": [],
    },
    {
        "key": "reflection_ceramic",
        "name": "反思提示-陶瓷",
        "description": "陶瓷类展品的反思提示问题列表",
        "category": "reflection",
        "content": """这件陶瓷的釉色和纹饰有什么特点？
这件陶瓷的烧制工艺体现了当时怎样的技术水平？
这件陶瓷的产地和窑口对其价值有什么影响？
这件陶瓷的造型设计反映了当时怎样的生活习俗？
这件陶瓷与其他时期的陶瓷相比有什么演变关系？""",
        "variables": [],
    },
    # Narrative style prompts
    {
        "key": "narrative_style_storytelling",
        "name": "叙事风格-讲故事",
        "description": "讲故事式叙事风格的指导提示词",
        "category": "narrative_style",
        "content": """请以讲故事的方式介绍这件文物，让内容生动有趣、富有感染力。
注重情节的展开和情感的传递，让听众仿佛置身于历史场景之中。
使用生动的语言和形象的比喻，让文物背后的故事活起来。""",
        "variables": [],
    },
    {
        "key": "narrative_style_academic",
        "name": "叙事风格-学术",
        "description": "学术式叙事风格的指导提示词",
        "category": "narrative_style",
        "content": """请以学术研究的方式介绍这件文物，内容要严谨、准确、有据可查。
注重历史背景的考证和学术观点的引用，提供可靠的文献依据。
使用专业的术语和规范的表述，确保内容的学术价值和可信度。""",
        "variables": [],
    },
    {
        "key": "narrative_style_interactive",
        "name": "叙事风格-互动",
        "description": "互动式叙事风格的指导提示词",
        "category": "narrative_style",
        "content": """请以互动问答的方式介绍这件文物，鼓励观众思考和参与。
提出引人深思的问题，引导观众主动探索和发现。
注重与观众的对话和交流，让参观体验更加生动和有意义。""",
        "variables": [],
    },
    # Narrative generation - main prompt template
    {
        "key": "narrative_generation_template",
        "name": "叙事生成模板",
        "description": "叙事生成工具的主提示词模板，用于生成展品的叙事内容",
        "category": "narrative",
        "content": """Please create a narrative about the following exhibit:

Exhibit: {exhibit_name}
Information: {exhibit_info}

Guidelines:
- {level_guidance}
- {style_guidance}
- Keep the narrative engaging and appropriate for a museum visit
- Length should be suitable for a 3-5 minute read

Please generate the narrative:""",
        "variables": [
            {"name": "exhibit_name", "description": "展品名称"},
            {"name": "exhibit_info", "description": "展品信息"},
            {"name": "level_guidance", "description": "知识水平指导语"},
            {"name": "style_guidance", "description": "叙事风格指导语"},
        ],
    },
    # Knowledge level guidance prompts
    {
        "key": "narrative_level_beginner",
        "name": "叙事知识水平-入门",
        "description": "面向入门级观众的叙事指导语",
        "category": "narrative_level",
        "content": "Use simple language and avoid technical jargon. Focus on interesting stories and relatable concepts.",
        "variables": [],
    },
    {
        "key": "narrative_level_intermediate",
        "name": "叙事知识水平-进阶",
        "description": "面向进阶级观众的叙事指导语",
        "category": "narrative_level",
        "content": "Include some technical details and historical context. Balance accessibility with depth.",
        "variables": [],
    },
    {
        "key": "narrative_level_expert",
        "name": "叙事知识水平-专家",
        "description": "面向专家级观众的叙事指导语",
        "category": "narrative_level",
        "content": "Use professional terminology and academic language. Include detailed analysis and scholarly context.",
        "variables": [],
    },
    # Narrative style guidance (English version for curator tools)
    {
        "key": "narrative_style_storytelling_en",
        "name": "叙事风格指导-讲故事",
        "description": "讲故事式叙事风格的英文指导语",
        "category": "narrative_style",
        "content": "Tell this as an engaging story with vivid descriptions and emotional resonance.",
        "variables": [],
    },
    {
        "key": "narrative_style_academic_en",
        "name": "叙事风格指导-学术",
        "description": "学术式叙事风格的英文指导语",
        "category": "narrative_style",
        "content": "Present this in a formal, scholarly manner with precise terminology.",
        "variables": [],
    },
    {
        "key": "narrative_style_interactive_en",
        "name": "叙事风格指导-互动",
        "description": "互动式叙事风格的英文指导语",
        "category": "narrative_style",
        "content": "Create an interactive narrative that invites the visitor to imagine and explore.",
        "variables": [],
    },
    {
        "key": "narrative_style_balanced_en",
        "name": "叙事风格指导-平衡",
        "description": "平衡式叙事风格的英文指导语",
        "category": "narrative_style",
        "content": "Balance storytelling with factual information for an engaging yet informative narrative.",
        "variables": [],
    },
]


async def migrate_prompts() -> None:
    """Migrate all prompts to the database."""
    settings = get_settings()

    # Initialize database
    await init_database(settings.DATABASE_URL)

    migrated_count = 0
    skipped_count = 0
    updated_count = 0

    async with get_session() as session:
        for prompt_data in PROMPTS_TO_MIGRATE:
            # Check if prompt already exists
            result = await session.execute(
                select(Prompt).where(Prompt.key == prompt_data["key"])
            )
            existing_prompt = result.scalar_one_or_none()

            if existing_prompt:
                # Check if content has changed
                if existing_prompt.content == prompt_data["content"]:
                    print(f"[SKIP] Prompt '{prompt_data['key']}' already exists with same content")
                    skipped_count += 1
                    continue

                # Update existing prompt and create new version
                existing_prompt.name = prompt_data["name"]
                existing_prompt.description = prompt_data["description"]
                existing_prompt.category = prompt_data["category"]
                existing_prompt.content = prompt_data["content"]
                existing_prompt.variables = prompt_data["variables"]
                existing_prompt.updated_at = datetime.now(UTC)

                # Get next version number
                version_result = await session.execute(
                    select(PromptVersion)
                    .where(PromptVersion.prompt_id == existing_prompt.id)
                    .order_by(PromptVersion.version.desc())
                    .limit(1)
                )
                last_version = version_result.scalar_one_or_none()
                next_version = (last_version.version + 1) if last_version else 1

                # Create new version
                version = PromptVersion(
                    id=str(uuid.uuid4()),
                    prompt_id=existing_prompt.id,
                    version=next_version,
                    content=prompt_data["content"],
                    changed_by="migration_script",
                    change_reason="Content updated during migration",
                )
                session.add(version)

                print(f"[UPDATE] Prompt '{prompt_data['key']}' updated (version {next_version})")
                updated_count += 1
            else:
                # Create new prompt
                prompt_id = str(uuid.uuid4())
                prompt = Prompt(
                    id=prompt_id,
                    key=prompt_data["key"],
                    name=prompt_data["name"],
                    description=prompt_data["description"],
                    category=prompt_data["category"],
                    content=prompt_data["content"],
                    variables=prompt_data["variables"],
                    is_active=True,
                )
                session.add(prompt)

                # Create initial version
                version = PromptVersion(
                    id=str(uuid.uuid4()),
                    prompt_id=prompt_id,
                    version=1,
                    content=prompt_data["content"],
                    changed_by="migration_script",
                    change_reason="Initial migration",
                )
                session.add(version)

                print(f"[CREATE] Prompt '{prompt_data['key']}' created")
                migrated_count += 1

        # Commit all changes
        await session.commit()

    print("\n" + "=" * 50)
    print("Migration Summary:")
    print(f"  Created: {migrated_count}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total:   {len(PROMPTS_TO_MIGRATE)}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(migrate_prompts())
