"""Unit tests for curator tools."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.domain.entities import Exhibit, VisitorProfile
from app.domain.value_objects import ExhibitId, Location, ProfileId, UserId
from app.infra.langchain.curator_tools import (
    KnowledgeRetrievalTool,
    NarrativeGenerationTool,
    PathPlanningTool,
    PreferenceManagementTool,
    ReflectionPromptTool,
    create_curator_tools,
)
from langchain_core.documents import Document


@pytest.fixture
def mock_exhibit_repository():
    """Create a mock exhibit repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_profile_repository():
    """Create a mock profile repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_rag_agent():
    """Create a mock RAG agent."""
    agent = AsyncMock()
    return agent


@pytest.fixture
def mock_llm():
    """Create a mock language model."""
    llm = AsyncMock()
    response = MagicMock()
    response.content = "This is a generated narrative about the exhibit."
    llm.ainvoke.return_value = response
    return llm


@pytest.fixture
def sample_exhibits():
    """Create sample exhibits for testing."""
    return [
        Exhibit(
            id=ExhibitId("exhibit-1"),
            name="Bronze Ding",
            description="Ancient bronze vessel",
            location=Location(x=0.0, y=0.0, floor=1),
            hall="Hall A",
            category="bronze",
            era="Shang Dynasty",
            importance=5,
            estimated_visit_time=10,
            document_id="doc-1",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Exhibit(
            id=ExhibitId("exhibit-2"),
            name="Ceramic Vase",
            description="Blue and white porcelain",
            location=Location(x=100.0, y=100.0, floor=1),
            hall="Hall B",
            category="ceramic",
            era="Ming Dynasty",
            importance=4,
            estimated_visit_time=8,
            document_id="doc-2",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Exhibit(
            id=ExhibitId("exhibit-3"),
            name="Ancient Painting",
            description="Landscape scroll",
            location=Location(x=50.0, y=50.0, floor=2),
            hall="Hall C",
            category="painting",
            era="Tang Dynasty",
            importance=5,
            estimated_visit_time=12,
            document_id="doc-3",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]


@pytest.fixture
def sample_profile():
    """Create a sample visitor profile for testing."""
    return VisitorProfile(
        id=ProfileId("profile-1"),
        user_id=UserId("user-1"),
        interests=["bronze", "ceramic"],
        knowledge_level="intermediate",
        narrative_preference="storytelling",
        reflection_depth="3",
        visited_exhibit_ids=[ExhibitId("exhibit-1")],
        feedback_history=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestPathPlanningTool:
    """Tests for PathPlanningTool."""

    @pytest.mark.asyncio
    async def test_path_planning_success(
        self, mock_exhibit_repository, sample_exhibits
    ):
        """Test successful path planning."""
        mock_exhibit_repository.find_by_interests.return_value = sample_exhibits

        tool = PathPlanningTool(exhibit_repository=mock_exhibit_repository)
        input_data = {
            "interests": ["bronze", "ceramic"],
            "available_time": 60,
            "current_location": {"x": 0.0, "y": 0.0, "floor": 1},
            "visited_exhibit_ids": [],
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert "error" not in result_data
        assert "path" in result_data
        assert "estimated_duration" in result_data
        assert "exhibit_count" in result_data
        assert result_data["exhibit_count"] > 0

    @pytest.mark.asyncio
    async def test_path_planning_no_exhibits(self, mock_exhibit_repository):
        """Test path planning with no matching exhibits."""
        mock_exhibit_repository.find_by_interests.return_value = []

        tool = PathPlanningTool(exhibit_repository=mock_exhibit_repository)
        input_data = {
            "interests": ["nonexistent"],
            "available_time": 60,
            "current_location": {"x": 0.0, "y": 0.0, "floor": 1},
            "visited_exhibit_ids": [],
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["exhibit_count"] == 0
        assert "message" in result_data

    @pytest.mark.asyncio
    async def test_path_planning_skips_visited(
        self, mock_exhibit_repository, sample_exhibits
    ):
        """Test that visited exhibits are skipped."""
        mock_exhibit_repository.find_by_interests.return_value = sample_exhibits

        tool = PathPlanningTool(exhibit_repository=mock_exhibit_repository)
        input_data = {
            "interests": ["bronze", "ceramic"],
            "available_time": 60,
            "current_location": {"x": 0.0, "y": 0.0, "floor": 1},
            "visited_exhibit_ids": ["exhibit-1"],  # Skip this one
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        path_ids = [p["id"] for p in result_data["path"]]
        assert "exhibit-1" not in path_ids

    @pytest.mark.asyncio
    async def test_path_planning_invalid_input(self, mock_exhibit_repository):
        """Test path planning with invalid input."""
        tool = PathPlanningTool(exhibit_repository=mock_exhibit_repository)

        result = await tool._arun("invalid json")
        result_data = json.loads(result)

        assert "error" in result_data

    def test_path_planning_sync_raises(self, mock_exhibit_repository):
        """Test that synchronous execution raises NotImplementedError."""
        tool = PathPlanningTool(exhibit_repository=mock_exhibit_repository)

        with pytest.raises(NotImplementedError):
            tool._run("{}")


class TestKnowledgeRetrievalTool:
    """Tests for KnowledgeRetrievalTool."""

    @pytest.mark.asyncio
    async def test_knowledge_retrieval_success(self, mock_rag_agent):
        """Test successful knowledge retrieval."""
        mock_rag_agent.run.return_value = {
            "answer": "This is the answer.",
            "documents": [
                Document(
                    page_content="Document content 1",
                    metadata={"source": "doc1"},
                ),
                Document(
                    page_content="Document content 2",
                    metadata={"source": "doc2"},
                ),
            ],
            "reranked_documents": [
                Document(
                    page_content="Document content 1",
                    metadata={"source": "doc1", "rerank_score": 0.9},
                ),
            ],
            "retrieval_score": 0.85,
        }

        tool = KnowledgeRetrievalTool(rag_agent=mock_rag_agent)
        input_data = {"query": "What is this artifact?", "exhibit_id": "exhibit-1"}

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert "error" not in result_data
        assert result_data["answer"] == "This is the answer."
        assert "sources" in result_data
        assert result_data["retrieval_score"] == 0.85

    @pytest.mark.asyncio
    async def test_knowledge_retrieval_raw_query(self, mock_rag_agent):
        """Test knowledge retrieval with raw string query."""
        mock_rag_agent.run.return_value = {
            "answer": "Answer from raw query.",
            "documents": [],
            "retrieval_score": 0.5,
        }

        tool = KnowledgeRetrievalTool(rag_agent=mock_rag_agent)

        result = await tool._arun("What is this?")
        result_data = json.loads(result)

        assert result_data["answer"] == "Answer from raw query."

    @pytest.mark.asyncio
    async def test_knowledge_retrieval_error(self, mock_rag_agent):
        """Test knowledge retrieval with error."""
        mock_rag_agent.run.side_effect = Exception("RAG error")

        tool = KnowledgeRetrievalTool(rag_agent=mock_rag_agent)
        input_data = {"query": "What is this?"}

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert "error" in result_data

    def test_knowledge_retrieval_sync_raises(self, mock_rag_agent):
        """Test that synchronous execution raises NotImplementedError."""
        tool = KnowledgeRetrievalTool(rag_agent=mock_rag_agent)

        with pytest.raises(NotImplementedError):
            tool._run("{}")


class TestNarrativeGenerationTool:
    """Tests for NarrativeGenerationTool."""

    @pytest.mark.asyncio
    async def test_narrative_generation_success(self, mock_llm):
        """Test successful narrative generation."""
        tool = NarrativeGenerationTool(llm=mock_llm)
        input_data = {
            "exhibit_name": "Bronze Ding",
            "exhibit_info": "An ancient bronze vessel from Shang Dynasty",
            "knowledge_level": "beginner",
            "narrative_preference": "storytelling",
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert "error" not in result_data
        assert "narrative" in result_data
        assert result_data["style"] == "storytelling"
        assert result_data["target_level"] == "beginner"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_narrative_generation_different_levels(self, mock_llm):
        """Test narrative generation with different knowledge levels."""
        tool = NarrativeGenerationTool(llm=mock_llm)

        for level in ["beginner", "intermediate", "expert"]:
            input_data = {
                "exhibit_name": "Artifact",
                "exhibit_info": "Some info",
                "knowledge_level": level,
                "narrative_preference": "academic",
            }

            result = await tool._arun(json.dumps(input_data))
            result_data = json.loads(result)

            assert result_data["target_level"] == level

    @pytest.mark.asyncio
    async def test_narrative_generation_invalid_input(self, mock_llm):
        """Test narrative generation with invalid input."""
        tool = NarrativeGenerationTool(llm=mock_llm)

        result = await tool._arun("invalid json")
        result_data = json.loads(result)

        assert "error" in result_data

    def test_narrative_generation_sync_raises(self, mock_llm):
        """Test that synchronous execution raises NotImplementedError."""
        tool = NarrativeGenerationTool(llm=mock_llm)

        with pytest.raises(NotImplementedError):
            tool._run("{}")


class TestReflectionPromptTool:
    """Tests for ReflectionPromptTool."""

    @pytest.mark.asyncio
    async def test_reflection_prompts_beginner(self):
        """Test reflection prompts for beginner level."""
        tool = ReflectionPromptTool()
        input_data = {
            "knowledge_level": "beginner",
            "reflection_depth": 3,
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert "error" not in result_data
        assert "questions" in result_data
        assert len(result_data["questions"]) == 3

    @pytest.mark.asyncio
    async def test_reflection_prompts_with_category(self):
        """Test reflection prompts with category."""
        tool = ReflectionPromptTool()
        input_data = {
            "knowledge_level": "intermediate",
            "reflection_depth": 2,
            "category": "青铜器",
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert len(result_data["questions"]) == 2

    @pytest.mark.asyncio
    async def test_reflection_prompts_with_exhibit_name(self):
        """Test reflection prompts with exhibit name substitution."""
        tool = ReflectionPromptTool()
        input_data = {
            "knowledge_level": "beginner",
            "reflection_depth": 1,
            "exhibit_name": "Special Bronze Vessel",
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        # Check that the exhibit name is substituted in questions
        for question in result_data["questions"]:
            assert "这件文物" not in question or "Special Bronze Vessel" in question

    @pytest.mark.asyncio
    async def test_reflection_prompts_invalid_input(self):
        """Test reflection prompts with invalid input."""
        tool = ReflectionPromptTool()

        result = await tool._arun("invalid json")
        result_data = json.loads(result)

        assert "error" in result_data

    def test_reflection_prompts_sync_raises(self):
        """Test that synchronous execution raises NotImplementedError."""
        tool = ReflectionPromptTool()

        with pytest.raises(NotImplementedError):
            tool._run("{}")


class TestPreferenceManagementTool:
    """Tests for PreferenceManagementTool."""

    @pytest.mark.asyncio
    async def test_get_profile_success(self, mock_profile_repository, sample_profile):
        """Test successful profile retrieval."""
        mock_profile_repository.get_by_user_id.return_value = sample_profile

        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)
        input_data = {"action": "get", "user_id": "user-1"}

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["success"] is True
        assert result_data["profile"]["user_id"] == "user-1"
        assert result_data["profile"]["knowledge_level"] == "intermediate"

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, mock_profile_repository):
        """Test profile retrieval when not found."""
        mock_profile_repository.get_by_user_id.return_value = None

        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)
        input_data = {"action": "get", "user_id": "nonexistent"}

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["success"] is False

    @pytest.mark.asyncio
    async def test_update_profile_success(self, mock_profile_repository, sample_profile):
        """Test successful profile update."""
        mock_profile_repository.get_by_user_id.return_value = sample_profile
        mock_profile_repository.update.return_value = sample_profile

        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)
        input_data = {
            "action": "update",
            "user_id": "user-1",
            "updates": {
                "knowledge_level": "expert",
                "interests": ["painting", "sculpture"],
            },
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["success"] is True
        mock_profile_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_profile_no_updates(self, mock_profile_repository, sample_profile):
        """Test profile update with no updates provided."""
        mock_profile_repository.get_by_user_id.return_value = sample_profile

        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)
        input_data = {"action": "update", "user_id": "user-1"}

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "No updates" in result_data["message"]

    @pytest.mark.asyncio
    async def test_update_profile_not_found(self, mock_profile_repository):
        """Test profile update when profile not found."""
        mock_profile_repository.get_by_user_id.return_value = None

        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)
        input_data = {
            "action": "update",
            "user_id": "nonexistent",
            "updates": {"knowledge_level": "expert"},
        }

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["success"] is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, mock_profile_repository):
        """Test with unknown action."""
        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)
        input_data = {"action": "unknown", "user_id": "user-1"}

        result = await tool._arun(json.dumps(input_data))
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "Unknown action" in result_data["message"]

    @pytest.mark.asyncio
    async def test_invalid_input(self, mock_profile_repository):
        """Test with invalid input."""
        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)

        result = await tool._arun("invalid json")
        result_data = json.loads(result)

        assert "error" in result_data

    def test_sync_raises(self, mock_profile_repository):
        """Test that synchronous execution raises NotImplementedError."""
        tool = PreferenceManagementTool(profile_repository=mock_profile_repository)

        with pytest.raises(NotImplementedError):
            tool._run("{}")


class TestCreateCuratorTools:
    """Tests for create_curator_tools function."""

    def test_create_curator_tools_returns_all_tools(
        self, mock_exhibit_repository, mock_profile_repository, mock_rag_agent, mock_llm
    ):
        """Test that create_curator_tools returns all 5 tools."""
        tools = create_curator_tools(
            exhibit_repository=mock_exhibit_repository,
            profile_repository=mock_profile_repository,
            rag_agent=mock_rag_agent,
            llm=mock_llm,
        )

        assert len(tools) == 5

        tool_names = {tool.name for tool in tools}
        expected_names = {
            "path_planning",
            "knowledge_retrieval",
            "narrative_generation",
            "reflection_prompts",
            "preference_management",
        }
        assert tool_names == expected_names

    def test_tool_types(
        self, mock_exhibit_repository, mock_profile_repository, mock_rag_agent, mock_llm
    ):
        """Test that each tool is of the correct type."""
        tools = create_curator_tools(
            exhibit_repository=mock_exhibit_repository,
            profile_repository=mock_profile_repository,
            rag_agent=mock_rag_agent,
            llm=mock_llm,
        )

        tool_map = {tool.name: tool for tool in tools}

        assert isinstance(tool_map["path_planning"], PathPlanningTool)
        assert isinstance(tool_map["knowledge_retrieval"], KnowledgeRetrievalTool)
        assert isinstance(tool_map["narrative_generation"], NarrativeGenerationTool)
        assert isinstance(tool_map["reflection_prompts"], ReflectionPromptTool)
        assert isinstance(tool_map["preference_management"], PreferenceManagementTool)
