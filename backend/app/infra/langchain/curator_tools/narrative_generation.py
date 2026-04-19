import json
from typing import Any, ClassVar

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.ports.prompt_gateway import PromptGateway


class NarrativeGenerationInput(BaseModel):
    exhibit_name: str = Field(..., description="Name of the exhibit")
    exhibit_info: str = Field(..., description="Information about the exhibit")
    knowledge_level: str = Field(
        default="beginner", description="Target knowledge level (beginner/intermediate/expert)"
    )
    narrative_preference: str = Field(
        default="storytelling", description="Narrative style preference"
    )


class NarrativeGenerationTool(BaseTool):
    name: str = "narrative_generation"
    description: str = (
        "Generate engaging narrative content about an exhibit. "
        "Input should include exhibit_name, exhibit_info, knowledge_level "
        "(beginner/intermediate/expert), and narrative_preference."
    )

    llm: Any = Field(..., description="Language model for generation (BaseChatModel)")
    prompt_gateway: Any = Field(
        default=None, description="Prompt gateway for fetching prompts (PromptGateway protocol)"
    )

    LEVEL_PROMPTS_FALLBACK: ClassVar[dict[str, str]] = {
        "beginner": "Use simple language and avoid technical jargon. Focus on interesting stories and relatable concepts.",
        "intermediate": "Include some technical details and historical context. Balance accessibility with depth.",
        "expert": "Use professional terminology and academic language. Include detailed analysis and scholarly context.",
    }

    STYLE_PROMPTS_FALLBACK: ClassVar[dict[str, str]] = {
        "storytelling": "Tell this as an engaging story with vivid descriptions and emotional resonance.",
        "academic": "Present this in a formal, scholarly manner with precise terminology.",
        "interactive": "Create an interactive narrative that invites the visitor to imagine and explore.",
        "balanced": "Balance storytelling with factual information for an engaging yet informative narrative.",
    }

    TEMPLATE_FALLBACK: ClassVar[str] = """Please create a narrative about the following exhibit:

Exhibit: {exhibit_name}
Information: {exhibit_info}

Guidelines:
- {level_guidance}
- {style_guidance}
- Keep the narrative engaging and appropriate for a museum visit
- Length should be suitable for a 3-5 minute read

Please generate the narrative:"""

    async def _get_prompt_content(self, key: str) -> str | None:
        if self.prompt_gateway:
            return await self.prompt_gateway.get(key)
        return None

    async def _get_level_guidance(self, level: str) -> str:
        key = f"narrative_level_{level}"
        content = await self._get_prompt_content(key)
        if content:
            return content
        return self.LEVEL_PROMPTS_FALLBACK.get(level, self.LEVEL_PROMPTS_FALLBACK["beginner"])

    async def _get_style_guidance(self, style: str) -> str:
        key = f"narrative_style_{style}_en"
        content = await self._get_prompt_content(key)
        if content:
            return content
        return self.STYLE_PROMPTS_FALLBACK.get(style, self.STYLE_PROMPTS_FALLBACK["balanced"])

    async def _get_template(self) -> str:
        content = await self._get_prompt_content("narrative_generation_template")
        if content:
            return content
        return self.TEMPLATE_FALLBACK

    async def _arun(self, query: str) -> str:
        try:
            data = json.loads(query)
            input_data = NarrativeGenerationInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps({"error": f"Invalid input: {str(e)}"})

        try:
            level_guidance = await self._get_level_guidance(input_data.knowledge_level)
            style_guidance = await self._get_style_guidance(input_data.narrative_preference)
            template = await self._get_template()

            prompt = template.format(
                exhibit_name=input_data.exhibit_name,
                exhibit_info=input_data.exhibit_info,
                level_guidance=level_guidance,
                style_guidance=style_guidance,
            )

            response = await self.llm.ainvoke(prompt)
            narrative = response.content if hasattr(response, "content") else str(response)

            result = {
                "narrative": narrative,
                "style": input_data.narrative_preference,
                "target_level": input_data.knowledge_level,
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
