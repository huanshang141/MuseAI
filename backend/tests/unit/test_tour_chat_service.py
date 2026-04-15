from app.application.tour_chat_service import (
    ASSUMPTION_CONTEXTS,
    HALL_DESCRIPTIONS,
    PERSONA_PROMPTS,
    build_system_prompt,
)


def test_build_system_prompt_persona_a():
    prompt = build_system_prompt(persona="A", assumption="A")
    assert PERSONA_PROMPTS["A"] in prompt
    assert ASSUMPTION_CONTEXTS["A"] in prompt


def test_build_system_prompt_persona_b():
    prompt = build_system_prompt(persona="B", assumption="B")
    assert PERSONA_PROMPTS["B"] in prompt
    assert ASSUMPTION_CONTEXTS["B"] in prompt


def test_build_system_prompt_persona_c():
    prompt = build_system_prompt(persona="C", assumption="C")
    assert PERSONA_PROMPTS["C"] in prompt
    assert ASSUMPTION_CONTEXTS["C"] in prompt


def test_build_system_prompt_with_hall():
    prompt = build_system_prompt(persona="A", assumption="A", hall="relic-hall")
    assert HALL_DESCRIPTIONS["relic-hall"] in prompt


def test_build_system_prompt_with_unknown_hall():
    prompt = build_system_prompt(persona="A", assumption="A", hall="unknown-hall")
    assert "当前展厅" not in prompt


def test_build_system_prompt_with_exhibit_context():
    prompt = build_system_prompt(
        persona="A", assumption="A", exhibit_context="人面鱼纹盆，红陶制品"
    )
    assert "人面鱼纹盆，红陶制品" in prompt
    assert "当前展品信息" in prompt


def test_build_system_prompt_with_visited_exhibits():
    prompt = build_system_prompt(
        persona="A", assumption="A", visited_exhibits=["exhibit-1", "exhibit-2"]
    )
    assert "exhibit-1" in prompt
    assert "exhibit-2" in prompt
    assert "避免重复介绍" in prompt


def test_build_system_prompt_all_parts():
    prompt = build_system_prompt(
        persona="B",
        assumption="C",
        hall="site-hall",
        exhibit_context="半地穴式房屋",
        visited_exhibits=["exhibit-1"],
    )
    assert PERSONA_PROMPTS["B"] in prompt
    assert ASSUMPTION_CONTEXTS["C"] in prompt
    assert HALL_DESCRIPTIONS["site-hall"] in prompt
    assert "半地穴式房屋" in prompt
    assert "exhibit-1" in prompt


def test_build_system_prompt_default_persona():
    prompt = build_system_prompt(persona="X", assumption="A")
    assert PERSONA_PROMPTS["A"] in prompt


def test_persona_prompts_have_all_keys():
    assert set(PERSONA_PROMPTS.keys()) == {"A", "B", "C"}


def test_assumption_contexts_have_all_keys():
    assert set(ASSUMPTION_CONTEXTS.keys()) == {"A", "B", "C"}


def test_hall_descriptions_have_expected_slugs():
    assert "relic-hall" in HALL_DESCRIPTIONS
    assert "site-hall" in HALL_DESCRIPTIONS
