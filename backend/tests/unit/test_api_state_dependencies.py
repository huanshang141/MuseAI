"""Tests for ensuring API routers don't have fallback singleton constructors.

This enforces the architectural pattern where all dependencies should be
accessed through app.state via deps.py, not through module-level fallbacks.
"""

import inspect


def test_chat_router_has_no_module_level_fallback_singletons():
    """Ensure chat.py doesn't have module-level fallback singleton patterns."""
    from app.api import chat

    src = inspect.getsource(chat)

    # These patterns indicate fallback singleton construction that should be removed
    assert "_rag_agent" not in src, "chat.py should not have module-level _rag_agent singleton"
    assert "_llm_provider" not in src, "chat.py should not have module-level _llm_provider singleton"
    assert "_get_app_state_attr" not in src, "chat.py should not have _get_app_state_attr fallback helper"


def test_documents_router_has_no_module_level_fallback_singletons():
    """Ensure documents.py doesn't have module-level fallback singleton patterns."""
    from app.api import documents

    src = inspect.getsource(documents)

    # These patterns indicate fallback singleton construction that should be removed
    assert "_get_app_state_attr" not in src, "documents.py should not have _get_app_state_attr fallback helper"

    # Check for fallback creation patterns in dependency functions
    # The dependency functions should only check app.state, not create fallbacks
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if "def get_unified_indexing_service" in line or "def get_es_client" in line or "def get_embeddings" in line:
            # Look ahead to check if there's a fallback creation pattern
            remaining = "\n".join(lines[i:])
            # Check for fallback patterns like creating ES client or embeddings directly
            assert "ElasticsearchClient(" not in remaining or "# Fallback" not in remaining, (
                "Dependency function should not have fallback construction"
            )


def test_rag_agent_dependency_in_deps():
    """Ensure get_rag_agent dependency is available in deps.py."""
    from app.api import deps

    # The deps module should have the get_rag_agent function
    assert hasattr(deps, "get_rag_agent"), "deps.py should have get_rag_agent function"


def test_llm_provider_dependency_in_deps():
    """Ensure get_llm_provider dependency is available in deps.py."""
    from app.api import deps

    # The deps module should have the get_llm_provider function
    assert hasattr(deps, "get_llm_provider"), "deps.py should have get_llm_provider function"
