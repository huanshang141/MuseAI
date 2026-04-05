# backend/tests/unit/test_api_no_late_imports.py

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
