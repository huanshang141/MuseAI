from typing import Any

from langchain_core.tools import BaseTool

from app.application.ports.prompt_gateway import PromptGateway
from app.application.workflows.reflection_prompts import ReflectionPromptService
from app.infra.langchain.curator_tools.knowledge_retrieval import KnowledgeRetrievalTool
from app.infra.langchain.curator_tools.narrative_generation import NarrativeGenerationTool
from app.infra.langchain.curator_tools.path_planning import PathPlanningTool
from app.infra.langchain.curator_tools.preference_management import PreferenceManagementTool
from app.infra.langchain.curator_tools.reflection_prompt import ReflectionPromptTool

__all__ = [
    "PathPlanningTool",
    "KnowledgeRetrievalTool",
    "NarrativeGenerationTool",
    "ReflectionPromptTool",
    "PreferenceManagementTool",
    "create_curator_tools",
]


def create_curator_tools(
    exhibit_repository: Any,
    profile_repository: Any,
    rag_agent: Any,
    llm: Any,
    prompt_gateway: PromptGateway | None = None,
    reflection_service: ReflectionPromptService | None = None,
) -> list[BaseTool]:
    return [
        PathPlanningTool(exhibit_repository=exhibit_repository),
        KnowledgeRetrievalTool(rag_agent=rag_agent),
        NarrativeGenerationTool(llm=llm, prompt_gateway=prompt_gateway),
        ReflectionPromptTool(reflection_service=reflection_service),
        PreferenceManagementTool(profile_repository=profile_repository),
    ]
