"""Tests for reflection prompts module."""

import pytest
from app.workflows.reflection_prompts import (
    BEGINNER_PROMPTS,
    CATEGORY_REFLECTIONS,
    EXPERT_PROMPTS,
    INTERMEDIATE_PROMPTS,
    KnowledgeLevel,
    NarrativeStyle,
    get_narrative_style_prompt,
    get_reflection_prompts,
)


class TestKnowledgeLevel:
    """Tests for KnowledgeLevel enum."""

    def test_beginner_value(self):
        assert KnowledgeLevel.BEGINNER.value == "beginner"

    def test_intermediate_value(self):
        assert KnowledgeLevel.INTERMEDIATE.value == "intermediate"

    def test_expert_value(self):
        assert KnowledgeLevel.EXPERT.value == "expert"


class TestNarrativeStyle:
    """Tests for NarrativeStyle enum."""

    def test_storytelling_value(self):
        assert NarrativeStyle.STORYTELLING.value == "storytelling"

    def test_academic_value(self):
        assert NarrativeStyle.ACADEMIC.value == "academic"

    def test_interactive_value(self):
        assert NarrativeStyle.INTERACTIVE.value == "interactive"


class TestGetReflectionPrompts:
    """Tests for get_reflection_prompts function."""

    def test_beginner_level_returns_correct_prompts(self):
        """Test that beginner level returns beginner prompts."""
        prompts = get_reflection_prompts(KnowledgeLevel.BEGINNER, reflection_depth=3)
        assert len(prompts) == 3
        # All returned prompts should be from BEGINNER_PROMPTS
        for prompt in prompts:
            assert prompt in BEGINNER_PROMPTS

    def test_beginner_level_default_depth(self):
        """Test that default depth is 3 for beginner level."""
        prompts = get_reflection_prompts(KnowledgeLevel.BEGINNER)
        assert len(prompts) == 3

    def test_expert_level_returns_correct_prompts(self):
        """Test that expert level returns expert prompts."""
        prompts = get_reflection_prompts(KnowledgeLevel.EXPERT, reflection_depth=3)
        assert len(prompts) == 3
        # All returned prompts should be from EXPERT_PROMPTS
        for prompt in prompts:
            assert prompt in EXPERT_PROMPTS

    def test_intermediate_level_returns_correct_prompts(self):
        """Test that intermediate level returns intermediate prompts."""
        prompts = get_reflection_prompts(KnowledgeLevel.INTERMEDIATE, reflection_depth=3)
        assert len(prompts) == 3
        # All returned prompts should be from INTERMEDIATE_PROMPTS
        for prompt in prompts:
            assert prompt in INTERMEDIATE_PROMPTS

    def test_with_bronze_category(self):
        """Test get_reflection_prompts with 青铜器 category."""
        prompts = get_reflection_prompts(
            KnowledgeLevel.BEGINNER,
            reflection_depth=3,
            category="青铜器",
        )
        assert len(prompts) == 3
        # First prompts should be from category
        for prompt in prompts:
            assert prompt in CATEGORY_REFLECTIONS["青铜器"] or prompt in BEGINNER_PROMPTS

    def test_with_painting_category(self):
        """Test get_reflection_prompts with 书画 category."""
        prompts = get_reflection_prompts(
            KnowledgeLevel.INTERMEDIATE,
            reflection_depth=3,
            category="书画",
        )
        assert len(prompts) == 3
        for prompt in prompts:
            assert prompt in CATEGORY_REFLECTIONS["书画"] or prompt in INTERMEDIATE_PROMPTS

    def test_with_ceramics_category(self):
        """Test get_reflection_prompts with 陶瓷 category."""
        prompts = get_reflection_prompts(
            KnowledgeLevel.EXPERT,
            reflection_depth=3,
            category="陶瓷",
        )
        assert len(prompts) == 3
        for prompt in prompts:
            assert prompt in CATEGORY_REFLECTIONS["陶瓷"] or prompt in EXPERT_PROMPTS

    def test_depth_limiting(self):
        """Test that reflection_depth limits the number of prompts returned."""
        # Test with depth 1
        prompts = get_reflection_prompts(KnowledgeLevel.BEGINNER, reflection_depth=1)
        assert len(prompts) == 1

        # Test with depth 5
        prompts = get_reflection_prompts(KnowledgeLevel.BEGINNER, reflection_depth=5)
        assert len(prompts) == 5

    def test_depth_limiting_with_category(self):
        """Test depth limiting when category is provided."""
        prompts = get_reflection_prompts(
            KnowledgeLevel.BEGINNER,
            reflection_depth=2,
            category="青铜器",
        )
        assert len(prompts) == 2

    def test_invalid_depth_zero_raises_error(self):
        """Test that depth of 0 raises ValueError."""
        with pytest.raises(ValueError, match="reflection_depth must be at least 1"):
            get_reflection_prompts(KnowledgeLevel.BEGINNER, reflection_depth=0)

    def test_invalid_depth_negative_raises_error(self):
        """Test that negative depth raises ValueError."""
        with pytest.raises(ValueError, match="reflection_depth must be at least 1"):
            get_reflection_prompts(KnowledgeLevel.BEGINNER, reflection_depth=-1)

    def test_invalid_depth_too_high_raises_error(self):
        """Test that depth greater than 5 raises ValueError."""
        with pytest.raises(ValueError, match="reflection_depth cannot exceed 5"):
            get_reflection_prompts(KnowledgeLevel.BEGINNER, reflection_depth=6)

    def test_unknown_category_ignores_category(self):
        """Test that unknown category is ignored and level prompts are returned."""
        prompts = get_reflection_prompts(
            KnowledgeLevel.BEGINNER,
            reflection_depth=3,
            category="未知类别",
        )
        assert len(prompts) == 3
        # Should only have beginner prompts since category doesn't exist
        for prompt in prompts:
            assert prompt in BEGINNER_PROMPTS


class TestGetNarrativeStylePrompt:
    """Tests for get_narrative_style_prompt function."""

    def test_storytelling_style(self):
        """Test storytelling style prompt contains expected keywords."""
        prompt = get_narrative_style_prompt(NarrativeStyle.STORYTELLING)
        assert "讲故事" in prompt
        assert "感染力" in prompt

    def test_academic_style(self):
        """Test academic style prompt contains expected keywords."""
        prompt = get_narrative_style_prompt(NarrativeStyle.ACADEMIC)
        assert "学术" in prompt
        assert "严谨" in prompt

    def test_interactive_style(self):
        """Test interactive style prompt contains expected keywords."""
        prompt = get_narrative_style_prompt(NarrativeStyle.INTERACTIVE)
        assert "互动" in prompt or "问答" in prompt

    def test_invalid_style_raises_error(self):
        """Test that invalid style raises ValueError."""
        with pytest.raises(ValueError, match="Invalid narrative style"):
            get_narrative_style_prompt("invalid_style")

    def test_invalid_style_type_raises_error(self):
        """Test that non-enum style raises ValueError."""
        with pytest.raises(ValueError, match="Invalid narrative style"):
            get_narrative_style_prompt(123)


class TestPromptContent:
    """Tests to verify specific prompt content examples."""

    def test_beginner_example_prompt(self):
        """Test that beginner prompts include the expected example."""
        assert "这件文物让您联想到什么日常生活中的物品？" in BEGINNER_PROMPTS

    def test_intermediate_example_prompt(self):
        """Test that intermediate prompts include the expected example."""
        assert "这件文物反映的社会结构对今天有什么启示？" in INTERMEDIATE_PROMPTS

    def test_expert_example_prompt(self):
        """Test that expert prompts include the expected example."""
        assert "现有的考古解读是否存在争议？您倾向于哪种观点？" in EXPERT_PROMPTS

    def test_bronze_category_prompts(self):
        """Test that bronze category has expected prompts."""
        assert "青铜器" in CATEGORY_REFLECTIONS
        prompts = CATEGORY_REFLECTIONS["青铜器"]
        assert len(prompts) == 5
        assert "铸造工艺" in prompts[0]

    def test_painting_category_prompts(self):
        """Test that painting category has expected prompts."""
        assert "书画" in CATEGORY_REFLECTIONS
        prompts = CATEGORY_REFLECTIONS["书画"]
        assert len(prompts) == 5
        assert "笔墨技法" in prompts[0]

    def test_ceramics_category_prompts(self):
        """Test that ceramics category has expected prompts."""
        assert "陶瓷" in CATEGORY_REFLECTIONS
        prompts = CATEGORY_REFLECTIONS["陶瓷"]
        assert len(prompts) == 5
        assert "釉色" in prompts[0]
