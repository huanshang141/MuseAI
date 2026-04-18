"""Tests to enforce no runtime imports from app.main in deep modules.

Deep modules (infra, workflows, application) should not import from app.main
at runtime. Instead, dependencies should be injected through constructors.
"""

import ast
from pathlib import Path


def find_runtime_imports_from_main(directory: str) -> list[dict]:
    """Find all runtime imports from app.main in a directory.

    This includes both module-level and function-level imports.
    TYPE_CHECKING block imports are excluded as they are type-only.

    Args:
        directory: Directory to scan (relative to project root).

    Returns:
        List of violations with file path and import statement.
    """
    violations = []
    project_root = Path(__file__).parent.parent.parent.parent
    target_dir = project_root / directory

    if not target_dir.exists():
        return violations

    for file_path in target_dir.rglob("*.py"):
        # Skip __pycache__ directories
        if "__pycache__" in str(file_path):
            continue

        relative_path = file_path.relative_to(project_root)

        with open(file_path, encoding="utf-8") as f:
            try:
                source = f.read()
                tree = ast.parse(source)
            except SyntaxError:
                continue

        # Track nodes that are in TYPE_CHECKING blocks
        type_checking_nodes: set[int] = set()

        def find_type_checking_nodes(
            node: ast.AST,
            in_type_checking: bool = False,
            _tc_nodes: set[int] = type_checking_nodes,
        ) -> None:
            """Recursively find all nodes inside TYPE_CHECKING blocks."""
            is_type_checking = in_type_checking
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    is_type_checking = True
                elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
                    is_type_checking = True

            if is_type_checking:
                _tc_nodes.add(id(node))

            for child in ast.iter_child_nodes(node):
                find_type_checking_nodes(child, is_type_checking, _tc_nodes)

        find_type_checking_nodes(tree)

        # Find all ImportFrom nodes that import from app.main
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "app.main" and id(node) not in type_checking_nodes:
                    for alias in node.names:
                        violations.append({
                            "file": str(relative_path),
                            "import": f"from app.main import {alias.name}",
                            "line": node.lineno,
                        })

    return violations


def test_no_runtime_import_from_main_outside_main_module():
    """Test that deep modules do not import from app.main at runtime.

    Deep modules like workflows and infra should receive dependencies
    through constructor injection rather than importing from app.main.
    This includes both module-level and function-level imports.
    """
    violations = []

    # Check infra layer (excluding main.py itself)
    violations.extend(find_runtime_imports_from_main("backend/app/infra"))

    # Check workflows layer
    violations.extend(find_runtime_imports_from_main("backend/app/workflows"))

    # Check application layer
    violations.extend(find_runtime_imports_from_main("backend/app/application"))

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}:{v['line']}: {v['import']}"
            for v in violations
        )
        raise AssertionError(
            "Deep modules should not import from app.main at runtime.\n"
            "Use dependency injection through constructors instead.\n"
            f"Found {len(violations)} violations:\n{violation_details}"
        )
