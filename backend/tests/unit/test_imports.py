"""Tests for ensuring API routers follow proper dependency and import patterns.

- No late imports from main.py inside functions.
- No module-level fallback singleton constructors; dependencies should be
  accessed through app.state via deps.py.
"""

import ast
import inspect


def test_documents_api_no_late_imports_from_main():
    """documents.py should not import from main.py inside functions."""
    from app.api import documents
    source = inspect.getsource(documents)
    tree = ast.parse(source)

    late_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    if child.module and "main" in child.module:
                        late_imports.append(f"{node.name}: from {child.module}")

    assert len(late_imports) == 0, f"Found late imports from main: {late_imports}"


def test_chat_api_no_late_imports_from_main():
    """chat.py should not import from main.py inside functions."""
    from app.api import chat
    source = inspect.getsource(chat)
    tree = ast.parse(source)

    late_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    if child.module and "main" in child.module:
                        late_imports.append(f"{node.name}: from {child.module}")

    assert len(late_imports) == 0, f"Found late imports from main: {late_imports}"


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
