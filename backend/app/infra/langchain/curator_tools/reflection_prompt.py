import json
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.application.workflows.reflection_prompts import (
    KnowledgeLevel,
    ReflectionPromptService,
)


class ReflectionPromptInput(BaseModel):
    knowledge_level: str = Field(
        ..., description="User's knowledge level (beginner/intermediate/expert)"
    )
    reflection_depth: int = Field(default=3, description="Number of prompts to generate (1-5)")
    category: str | None = Field(None, description="Optional exhibit category")
    exhibit_name: str | None = Field(None, description="Optional exhibit name for context")


class ReflectionPromptTool(BaseTool):
    name: str = "reflection_prompts"
    description: str = (
        "Generate reflection prompts/questions to encourage deeper thinking about exhibits. "
        "Input should include knowledge_level (beginner/intermediate/expert), "
        "reflection_depth (1-5), and optionally category and exhibit_name."
    )

    reflection_service: Any = Field(
        default=None,
        description="ReflectionPromptService instance for prompt generation",
    )

    async def _arun(self, query: str) -> str:
        try:
            data = json.loads(query)
            input_data = ReflectionPromptInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps({"error": f"Invalid input: {str(e)}"})

        try:
            level_map = {
                "beginner": KnowledgeLevel.BEGINNER,
                "intermediate": KnowledgeLevel.INTERMEDIATE,
                "expert": KnowledgeLevel.EXPERT,
            }
            knowledge_level = level_map.get(
                input_data.knowledge_level.lower(), KnowledgeLevel.BEGINNER
            )

            if self.reflection_service:
                questions = await self.reflection_service.get_reflection_prompts(
                    knowledge_level=knowledge_level,
                    reflection_depth=input_data.reflection_depth,
                    category=input_data.category,
                )
            else:
                from app.application.workflows.reflection_prompts import get_reflection_prompts_sync

                questions = get_reflection_prompts_sync(
                    knowledge_level=knowledge_level,
                    reflection_depth=input_data.reflection_depth,
                    category=input_data.category,
                )

            if input_data.exhibit_name:
                questions = [
                    q.replace("这件文物", f"{input_data.exhibit_name}")
                    .replace("这件青铜器", f"{input_data.exhibit_name}")
                    .replace("这幅作品", f"{input_data.exhibit_name}")
                    .replace("这件陶瓷", f"{input_data.exhibit_name}")
                    for q in questions
                ]

            result = {"questions": questions}
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
