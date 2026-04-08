"""Reflection prompts module for Digital Curation Agent.

This module provides reflection prompts for different knowledge levels,
categories, and narrative styles to guide user reflection on museum exhibits.

Prompts are loaded from the versioned PromptService (database-backed) with
fallback to hardcoded values for resilience.
"""

from enum import Enum
from typing import List

from loguru import logger


class KnowledgeLevel(Enum):
    """Knowledge level of the user."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class NarrativeStyle(Enum):
    """Narrative style for the reflection prompts."""

    STORYTELLING = "storytelling"
    ACADEMIC = "academic"
    INTERACTIVE = "interactive"


# Hardcoded fallback prompts (used when PromptService is unavailable)
BEGINNER_PROMPTS = [
    "这件文物让您联想到什么日常生活中的物品？",
    "这件文物最吸引您注意的是什么？",
    "这件文物让您想到了什么故事或传说？",
    "这件文物看起来像什么动物或植物？",
    "这件文物上有什么让您印象深刻的图案或颜色？",
]

INTERMEDIATE_PROMPTS = [
    "这件文物反映的社会结构对今天有什么启示？",
    "这件文物的制作工艺体现了当时怎样的技术水平？",
    "这件文物在当时的社会生活中扮演了什么角色？",
    "这件文物如何反映了当时的审美观念？",
    "这件文物与其他同类文物相比有什么独特之处？",
]

EXPERT_PROMPTS = [
    "现有的考古解读是否存在争议？您倾向于哪种观点？",
    "这件文物的断代依据是否充分？有哪些新的研究方法可以应用？",
    "这件文物的来源和流传过程是否清晰？",
    "这件文物在学术史上的地位如何？有哪些重要的研究成果？",
    "这件文物对于理解当时的文化交流有什么特殊价值？",
]

CATEGORY_REFLECTIONS = {
    "青铜器": [
        "这件青铜器的铸造工艺体现了当时怎样的技术水平？",
        "这件青铜器上的铭文或纹饰有什么特殊含义？",
        "这件青铜器的用途是什么？是礼器、兵器还是生活用具？",
        "这件青铜器的合金比例反映了当时怎样的冶金技术？",
        "这件青铜器与其他地区出土的青铜器有什么异同？",
    ],
    "书画": [
        "这幅作品的笔墨技法有什么独特之处？",
        "这幅作品的构图和意境如何体现了当时的审美追求？",
        "这幅作品的作者生平对其创作风格有什么影响？",
        "这幅作品的题跋和印章提供了哪些历史信息？",
        "这幅作品在书画史上的地位如何？",
    ],
    "陶瓷": [
        "这件陶瓷的釉色和纹饰有什么特点？",
        "这件陶瓷的烧制工艺体现了当时怎样的技术水平？",
        "这件陶瓷的产地和窑口对其价值有什么影响？",
        "这件陶瓷的造型设计反映了当时怎样的生活习俗？",
        "这件陶瓷与其他时期的陶瓷相比有什么演变关系？",
    ],
}

NARRATIVE_STYLE_PROMPTS = {
    NarrativeStyle.STORYTELLING: """请以讲故事的方式介绍这件文物，让内容生动有趣、富有感染力。
注重情节的展开和情感的传递，让听众仿佛置身于历史场景之中。
使用生动的语言和形象的比喻，让文物背后的故事活起来。""",
    NarrativeStyle.ACADEMIC: """请以学术研究的方式介绍这件文物，内容要严谨、准确、有据可查。
注重历史背景的考证和学术观点的引用，提供可靠的文献依据。
使用专业的术语和规范的表述，确保内容的学术价值和可信度。""",
    NarrativeStyle.INTERACTIVE: """请以互动问答的方式介绍这件文物，鼓励观众思考和参与。
提出引人深思的问题，引导观众主动探索和发现。
注重与观众的对话和交流，让参观体验更加生动和有意义。""",
}

REFLECTION_TEMPLATES = {
    KnowledgeLevel.BEGINNER: BEGINNER_PROMPTS,
    KnowledgeLevel.INTERMEDIATE: INTERMEDIATE_PROMPTS,
    KnowledgeLevel.EXPERT: EXPERT_PROMPTS,
}

# Mapping from KnowledgeLevel to prompt key
LEVEL_KEY_MAP = {
    KnowledgeLevel.BEGINNER: "reflection_beginner",
    KnowledgeLevel.INTERMEDIATE: "reflection_intermediate",
    KnowledgeLevel.EXPERT: "reflection_expert",
}

# Mapping from category to prompt key
CATEGORY_KEY_MAP = {
    "青铜器": "reflection_bronze",
    "书画": "reflection_painting",
    "陶瓷": "reflection_ceramic",
}

# Mapping from NarrativeStyle to prompt key
STYLE_KEY_MAP = {
    NarrativeStyle.STORYTELLING: "narrative_style_storytelling",
    NarrativeStyle.ACADEMIC: "narrative_style_academic",
    NarrativeStyle.INTERACTIVE: "narrative_style_interactive",
}


def _parse_multiline_prompts(content: str) -> List[str]:
    """Parse multi-line prompt content into a list of prompts.

    Args:
        content: Multi-line string with one prompt per line

    Returns:
        List of non-empty prompt strings
    """
    prompts = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line:
            prompts.append(line)
    return prompts


async def _get_prompt_content(key: str) -> str | None:
    """Fetch prompt content from PromptService.

    Args:
        key: Unique prompt key

    Returns:
        Prompt content if found, None otherwise
    """
    try:
        from app.application.prompt_service import PromptService
        from app.infra.postgres.database import get_session
        from app.infra.postgres.prompt_repository import PostgresPromptRepository
        from app.main import get_prompt_cache

        prompt_cache = get_prompt_cache()
        async with get_session() as session:
            repository = PostgresPromptRepository(session)
            service = PromptService(repository, prompt_cache)
            prompt = await service.get_prompt(key)
            return prompt.content if prompt else None
    except RuntimeError:
        # Prompt cache or database not initialized (e.g., during tests)
        logger.debug(f"PromptService unavailable for key '{key}', using fallback")
        return None
    except Exception as e:
        logger.warning(f"Failed to get prompt '{key}': {e}")
        return None


async def get_reflection_prompts(
    knowledge_level: KnowledgeLevel,
    reflection_depth: int = 3,
    category: str | None = None,
) -> List[str]:
    """Get reflection prompts based on knowledge level, depth, and category.

    Args:
        knowledge_level: The user's knowledge level (beginner, intermediate, expert)
        reflection_depth: Number of prompts to return (default 3, max 5)
        category: Optional category for category-specific prompts (e.g., "青铜器", "书画", "陶瓷")

    Returns:
        List of reflection prompt strings

    Raises:
        ValueError: If reflection_depth is less than 1 or greater than 5
    """
    if reflection_depth < 1:
        raise ValueError("reflection_depth must be at least 1")
    if reflection_depth > 5:
        raise ValueError("reflection_depth cannot exceed 5")

    prompts: List[str] = []

    # Add category-specific prompts if category is provided
    if category:
        # Try to get from PromptService first
        category_key = CATEGORY_KEY_MAP.get(category)
        if category_key:
            content = await _get_prompt_content(category_key)
            if content:
                prompts.extend(_parse_multiline_prompts(content))
            else:
                # Fallback to hardcoded
                prompts.extend(CATEGORY_REFLECTIONS.get(category, []))
        else:
            # Unknown category, use hardcoded fallback
            prompts.extend(CATEGORY_REFLECTIONS.get(category, []))

    # Add knowledge level prompts
    level_key = LEVEL_KEY_MAP.get(knowledge_level)
    if level_key:
        content = await _get_prompt_content(level_key)
        if content:
            prompts.extend(_parse_multiline_prompts(content))
        else:
            # Fallback to hardcoded
            prompts.extend(REFLECTION_TEMPLATES.get(knowledge_level, BEGINNER_PROMPTS))
    else:
        # Fallback to hardcoded
        prompts.extend(REFLECTION_TEMPLATES.get(knowledge_level, BEGINNER_PROMPTS))

    # Return the requested number of prompts
    return prompts[:reflection_depth]


async def get_narrative_style_prompt(style: NarrativeStyle) -> str:
    """Get the narrative style prompt for the given style.

    Args:
        style: The narrative style (storytelling, academic, interactive)

    Returns:
        The narrative style prompt string

    Raises:
        ValueError: If the style is not a valid NarrativeStyle
    """
    if not isinstance(style, NarrativeStyle):
        raise ValueError(f"Invalid narrative style: {style}")

    # Try to get from PromptService first
    style_key = STYLE_KEY_MAP.get(style)
    if style_key:
        content = await _get_prompt_content(style_key)
        if content:
            return content

    # Fallback to hardcoded
    return NARRATIVE_STYLE_PROMPTS.get(style, NARRATIVE_STYLE_PROMPTS[NarrativeStyle.STORYTELLING])


# Synchronous wrapper for backward compatibility
def get_reflection_prompts_sync(
    knowledge_level: KnowledgeLevel,
    reflection_depth: int = 3,
    category: str | None = None,
) -> List[str]:
    """Synchronous wrapper for backward compatibility.

    WARNING: This function uses hardcoded prompts only. For versioned prompts,
    use the async get_reflection_prompts() function instead.

    Args:
        knowledge_level: The user's knowledge level
        reflection_depth: Number of prompts to return
        category: Optional category for category-specific prompts

    Returns:
        List of reflection prompt strings
    """
    if reflection_depth < 1:
        raise ValueError("reflection_depth must be at least 1")
    if reflection_depth > 5:
        raise ValueError("reflection_depth cannot exceed 5")

    prompts: List[str] = []

    if category and category in CATEGORY_REFLECTIONS:
        prompts.extend(CATEGORY_REFLECTIONS[category])

    level_prompts = REFLECTION_TEMPLATES.get(knowledge_level, BEGINNER_PROMPTS)
    prompts.extend(level_prompts)

    return prompts[:reflection_depth]
