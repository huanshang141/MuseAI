"""Curator Tools module for Digital Curation Agent.

This module defines 5 LangChain tools for the curator agent:
1. PathPlanningTool - Plan optimal tour paths
2. KnowledgeRetrievalTool - Retrieve exhibit knowledge
3. NarrativeGenerationTool - Generate narrative content
4. ReflectionPromptTool - Generate reflection questions
5. PreferenceManagementTool - Manage user preferences
"""

import json
import math
from typing import Any, ClassVar

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from typing import TYPE_CHECKING

from app.domain.value_objects import ExhibitId, UserId
from loguru import logger

from app.workflows.reflection_prompts import (
    KnowledgeLevel,
    get_reflection_prompts,
)



if TYPE_CHECKING:
    from app.domain.repositories import ExhibitRepository, VisitorProfileRepository


class PathPlanningInput(BaseModel):
    """Input for path planning tool."""

    interests: list[str] = Field(..., description="List of user interests/categories")
    available_time: int = Field(..., description="Available time in minutes")
    current_location: dict[str, Any] = Field(
        ..., description="Current location with x, y, floor"
    )
    visited_exhibit_ids: list[str] = Field(
        default_factory=list, description="List of already visited exhibit IDs"
    )


class PathPlanningTool(BaseTool):
    """Tool for planning optimal tour paths through exhibits."""

    name: str = "path_planning"
    description: str = (
        "Plan an optimal tour path based on user interests, available time, and current location. "
        "Uses nearest neighbor TSP algorithm for path optimization. "
        "Input should include interests (list of categories), available_time (minutes), "
        "current_location (dict with x, y, floor), and optionally visited_exhibit_ids."
    )

    exhibit_repository: Any = Field(
        ..., description="Repository for exhibit data (ExhibitRepository protocol)"
    )

    def _calculate_distance(
        self, loc1: dict[str, Any], loc2: dict[str, Any]
    ) -> float:
        """Calculate Euclidean distance between two locations."""
        # If on different floors, add penalty
        floor_penalty = 0
        if loc1.get("floor", 1) != loc2.get("floor", 1):
            floor_penalty = 100  # Large penalty for changing floors

        dx = loc1.get("x", 0) - loc2.get("x", 0)
        dy = loc1.get("y", 0) - loc2.get("y", 0)
        return math.sqrt(dx * dx + dy * dy) + floor_penalty

    def _nearest_neighbor_tsp(
        self,
        start: dict[str, Any],
        exhibits: list[Any],
        visited_ids: set[str],
        max_time: int,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Solve TSP using nearest neighbor algorithm.

        Returns:
            Tuple of (path, estimated_duration, exhibit_count)
        """
        path = []
        current_location = start
        total_time = 0
        remaining_exhibits = [
            e for e in exhibits if e.id.value not in visited_ids
        ]
        visited_in_path = set()

        while remaining_exhibits and total_time < max_time:
            # Find nearest exhibit
            nearest = None
            nearest_dist = float("inf")
            nearest_idx = -1

            for idx, exhibit in enumerate(remaining_exhibits):
                exhibit_loc = {
                    "x": exhibit.location.x,
                    "y": exhibit.location.y,
                    "floor": exhibit.location.floor,
                }
                dist = self._calculate_distance(current_location, exhibit_loc)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = exhibit
                    nearest_idx = idx

            if nearest is None:
                break

            # Estimate travel time (1 unit = 1 minute walking) + visit time
            travel_time = max(1, int(nearest_dist / 10))  # Scale distance to minutes
            visit_time = nearest.estimated_visit_time or 5
            total_time_needed = travel_time + visit_time

            # Check if we have time
            if total_time + total_time_needed > max_time:
                break

            # Add to path
            path.append(
                {
                    "id": nearest.id.value,
                    "name": nearest.name,
                    "category": nearest.category,
                    "location": {
                        "x": nearest.location.x,
                        "y": nearest.location.y,
                        "floor": nearest.location.floor,
                    },
                    "estimated_visit_time": visit_time,
                }
            )
            total_time += total_time_needed
            visited_in_path.add(nearest.id.value)

            # Update current location
            current_location = {
                "x": nearest.location.x,
                "y": nearest.location.y,
                "floor": nearest.location.floor,
            }

            # Remove from remaining
            remaining_exhibits.pop(nearest_idx)

        return path, total_time, len(path)

    async def _arun(self, query: str) -> str:
        """Execute path planning asynchronously."""
        try:
            data = json.loads(query)
            input_data = PathPlanningInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps(
                {"error": f"Invalid input: {str(e)}"}
            )

        try:
            # Find exhibits matching interests
            exhibits = await self.exhibit_repository.find_by_interests(
                input_data.interests, limit=50
            )

            if not exhibits:
                return json.dumps(
                    {
                        "path": [],
                        "estimated_duration": 0,
                        "exhibit_count": 0,
                        "message": "No exhibits found matching your interests.",
                    }
                )

            # Plan path using nearest neighbor TSP
            visited_ids = set(input_data.visited_exhibit_ids)
            path, duration, count = self._nearest_neighbor_tsp(
                input_data.current_location,
                exhibits,
                visited_ids,
                input_data.available_time,
            )

            result = {
                "path": path,
                "estimated_duration": duration,
                "exhibit_count": count,
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        """Synchronous execution not supported."""
        raise NotImplementedError("This tool only supports async execution")


class KnowledgeRetrievalInput(BaseModel):
    """Input for knowledge retrieval tool."""

    query: str = Field(..., description="The query to search for")
    exhibit_id: str | None = Field(
        None, description="Optional specific exhibit ID to focus on"
    )


class KnowledgeRetrievalTool(BaseTool):
    """Tool for retrieving exhibit knowledge using RAG."""

    name: str = "knowledge_retrieval"
    description: str = (
        "Retrieve knowledge about exhibits using the RAG system. "
        "Input should include a query string and optionally an exhibit_id "
        "to focus the search on a specific exhibit."
    )

    rag_agent: Any = Field(..., description="RAG Agent instance for retrieval")

    async def _arun(self, query: str) -> str:
        """Execute knowledge retrieval asynchronously."""
        try:
            data = json.loads(query)
            input_data = KnowledgeRetrievalInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            # Try to use the raw query string
            input_data = KnowledgeRetrievalInput(query=query)

        try:
            # Enhance query with exhibit context if provided
            search_query = input_data.query
            if input_data.exhibit_id:
                search_query = f"{input_data.query} (exhibit: {input_data.exhibit_id})"

            # Use RAG agent to retrieve information
            result = await self.rag_agent.run(search_query)

            # Extract sources from retrieved documents
            sources = []
            docs = result.get("reranked_documents") or result.get("documents", [])
            for doc in docs:
                sources.append(
                    {
                        "content": doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content,
                        "metadata": doc.metadata,
                    }
                )

            response = {
                "answer": result.get("answer", "No answer found."),
                "sources": sources[:3],  # Limit to top 3 sources
                "retrieval_score": result.get("retrieval_score", 0.0),
            }
            return json.dumps(response, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        """Synchronous execution not supported."""
        raise NotImplementedError("This tool only supports async execution")


class NarrativeGenerationInput(BaseModel):
    """Input for narrative generation tool."""

    exhibit_name: str = Field(..., description="Name of the exhibit")
    exhibit_info: str = Field(..., description="Information about the exhibit")
    knowledge_level: str = Field(
        default="beginner", description="Target knowledge level (beginner/intermediate/expert)"
    )
    narrative_preference: str = Field(
        default="storytelling", description="Narrative style preference"
    )


class NarrativeGenerationTool(BaseTool):
    """Tool for generating narrative content about exhibits."""

    name: str = "narrative_generation"
    description: str = (
        "Generate engaging narrative content about an exhibit. "
        "Input should include exhibit_name, exhibit_info, knowledge_level "
        "(beginner/intermediate/expert), and narrative_preference."
    )

    llm: Any = Field(..., description="Language model for generation (BaseChatModel)")

    # Hardcoded fallback prompts (ClassVar to avoid Pydantic field interpretation)
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

    async def _get_level_guidance(self, level: str) -> str:
        """Get knowledge level guidance prompt.

        Args:
            level: Knowledge level (beginner/intermediate/expert)

        Returns:
            Level guidance prompt string
        """
        key = f"narrative_level_{level}"
        content = await self._get_prompt_content(key)
        if content:
            return content
        return self.LEVEL_PROMPTS_FALLBACK.get(level, self.LEVEL_PROMPTS_FALLBACK["beginner"])

    async def _get_style_guidance(self, style: str) -> str:
        """Get narrative style guidance prompt.

        Args:
            style: Narrative style (storytelling/academic/interactive/balanced)

        Returns:
            Style guidance prompt string
        """
        key = f"narrative_style_{style}_en"
        content = await self._get_prompt_content(key)
        if content:
            return content
        return self.STYLE_PROMPTS_FALLBACK.get(style, self.STYLE_PROMPTS_FALLBACK["balanced"])

    async def _get_template(self) -> str:
        """Get narrative generation template.

        Returns:
            Template string with placeholders
        """
        content = await self._get_prompt_content("narrative_generation_template")
        if content:
            return content
        return self.TEMPLATE_FALLBACK

    async def _arun(self, query: str) -> str:
        """Execute narrative generation asynchronously."""
        try:
            data = json.loads(query)
            input_data = NarrativeGenerationInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps({"error": f"Invalid input: {str(e)}"})

        try:
            # Get prompts from PromptService (with fallback to hardcoded)
            level_guidance = await self._get_level_guidance(input_data.knowledge_level)
            style_guidance = await self._get_style_guidance(input_data.narrative_preference)
            template = await self._get_template()

            # Render template with variables
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
        """Synchronous execution not supported."""
        raise NotImplementedError("This tool only supports async execution")


class ReflectionPromptInput(BaseModel):
    """Input for reflection prompt tool."""

    knowledge_level: str = Field(
        ..., description="User's knowledge level (beginner/intermediate/expert)"
    )
    reflection_depth: int = Field(default=3, description="Number of prompts to generate (1-5)")
    category: str | None = Field(None, description="Optional exhibit category")
    exhibit_name: str | None = Field(None, description="Optional exhibit name for context")


class ReflectionPromptTool(BaseTool):
    """Tool for generating reflection prompts about exhibits."""

    name: str = "reflection_prompts"
    description: str = (
        "Generate reflection prompts/questions to encourage deeper thinking about exhibits. "
        "Input should include knowledge_level (beginner/intermediate/expert), "
        "reflection_depth (1-5), and optionally category and exhibit_name."
    )

    async def _arun(self, query: str) -> str:
        """Execute reflection prompt generation asynchronously."""
        try:
            data = json.loads(query)
            input_data = ReflectionPromptInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps({"error": f"Invalid input: {str(e)}"})

        try:
            # Map string knowledge level to enum
            level_map = {
                "beginner": KnowledgeLevel.BEGINNER,
                "intermediate": KnowledgeLevel.INTERMEDIATE,
                "expert": KnowledgeLevel.EXPERT,
            }
            knowledge_level = level_map.get(
                input_data.knowledge_level.lower(), KnowledgeLevel.BEGINNER
            )

            # Get reflection prompts (now async, uses PromptService)
            questions = await get_reflection_prompts(
                knowledge_level=knowledge_level,
                reflection_depth=input_data.reflection_depth,
                category=input_data.category,
            )

            # Add exhibit context if provided
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
        """Synchronous execution not supported."""
        raise NotImplementedError("This tool only supports async execution")


class PreferenceManagementInput(BaseModel):
    """Input for preference management tool."""

    action: str = Field(
        ..., description="Action to perform: 'get' or 'update'"
    )
    user_id: str = Field(..., description="User ID")
    updates: dict[str, Any] | None = Field(
        None, description="Updates to apply (for update action)"
    )


class PreferenceManagementTool(BaseTool):
    """Tool for managing user preferences and profile."""

    name: str = "preference_management"
    description: str = (
        "Manage user preferences and profile information. "
        "Input should include action ('get' or 'update'), user_id, "
        "and optionally updates (dict with fields to update)."
    )

    profile_repository: Any = Field(
        ..., description="Repository for visitor profiles (VisitorProfileRepository protocol)"
    )

    async def _arun(self, query: str) -> str:
        """Execute preference management asynchronously."""
        try:
            data = json.loads(query)
            input_data = PreferenceManagementInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps({"error": f"Invalid input: {str(e)}"})

        try:
            user_id = UserId(input_data.user_id)

            if input_data.action == "get":
                # Get profile
                profile = await self.profile_repository.get_by_user_id(user_id)
                if profile:
                    result = {
                        "success": True,
                        "profile": {
                            "id": profile.id.value,
                            "user_id": profile.user_id.value,
                            "interests": profile.interests,
                            "knowledge_level": profile.knowledge_level,
                            "narrative_preference": profile.narrative_preference,
                            "reflection_depth": profile.reflection_depth,
                            "visited_exhibit_ids": [
                                eid.value for eid in profile.visited_exhibit_ids
                            ],
                        },
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Profile not found",
                    }

            elif input_data.action == "update":
                # Update profile
                if not input_data.updates:
                    return json.dumps(
                        {"success": False, "message": "No updates provided"}
                    )

                profile = await self.profile_repository.get_by_user_id(user_id)
                if not profile:
                    return json.dumps(
                        {"success": False, "message": "Profile not found"}
                    )

                # Apply updates
                updates = input_data.updates
                if "interests" in updates:
                    profile.interests = updates["interests"]
                if "knowledge_level" in updates:
                    profile.knowledge_level = updates["knowledge_level"]
                if "narrative_preference" in updates:
                    profile.narrative_preference = updates["narrative_preference"]
                if "reflection_depth" in updates:
                    profile.reflection_depth = str(updates["reflection_depth"])
                if "visited_exhibit_ids" in updates:
                    profile.visited_exhibit_ids = [
                        ExhibitId(eid) for eid in updates["visited_exhibit_ids"]
                    ]

                updated = await self.profile_repository.update(profile)
                result = {
                    "success": True,
                    "profile": {
                        "id": updated.id.value,
                        "user_id": updated.user_id.value,
                        "interests": updated.interests,
                        "knowledge_level": updated.knowledge_level,
                        "narrative_preference": updated.narrative_preference,
                        "reflection_depth": updated.reflection_depth,
                    },
                }

            else:
                result = {
                    "success": False,
                    "message": f"Unknown action: {input_data.action}",
                }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        """Synchronous execution not supported."""
        raise NotImplementedError("This tool only supports async execution")


def create_curator_tools(
    exhibit_repository: Any,
    profile_repository: Any,
    rag_agent: Any,
    llm: Any,
) -> list[BaseTool]:
    """Create curator tool set.

    Args:
        exhibit_repository: Repository for exhibit data
        profile_repository: Repository for visitor profiles
        rag_agent: RAG Agent instance for knowledge retrieval
        llm: Language model for narrative generation

    Returns:
        List of curator tools
    """
    return [
        PathPlanningTool(exhibit_repository=exhibit_repository),
        KnowledgeRetrievalTool(rag_agent=rag_agent),
        NarrativeGenerationTool(llm=llm),
        ReflectionPromptTool(),
        PreferenceManagementTool(profile_repository=profile_repository),
    ]
