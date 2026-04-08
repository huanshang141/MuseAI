# backend/tests/architecture/test_layer_import_rules.py
"""Tests to enforce layered architecture boundaries.

The application layer should not directly import from the infrastructure layer.
Instead, it should depend on ports (protocols) that are implemented by adapters.
"""

import ast
from pathlib import Path


def get_module_level_imports(file_path: Path) -> list[str]:
    """Extract module-level import statements from a Python file.

    This function only extracts imports that are at the top level of the module,
    excluding:
    - Imports inside TYPE_CHECKING blocks
    - Imports inside functions (lazy/optional imports)
    - Imports inside classes

    Args:
        file_path: Path to the Python file to analyze.

    Returns:
        List of fully qualified import names.
    """
    imports = []

    with open(file_path, encoding="utf-8") as f:
        try:
            source = f.read()
            tree = ast.parse(source)
        except SyntaxError:
            return imports

    # Track if we're in a TYPE_CHECKING block
    in_type_checking = False

    # Only process top-level statements (not inside functions/classes)
    for node in tree.body:
        # Check for TYPE_CHECKING if block
        if isinstance(node, ast.If):
            # Check if condition is TYPE_CHECKING
            is_type_checking = False
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                is_type_checking = True
            elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
                is_type_checking = True

            if is_type_checking:
                # Skip imports inside TYPE_CHECKING block
                continue

        # Process import statements at module level
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
                for alias in node.names:
                    imports.append(f"{node.module}.{alias.name}")

    return imports


def scan_imports(directory: str, forbidden_prefix: str, specific_files: list[str] | None = None) -> list[dict]:
    """Scan all Python files in a directory for forbidden imports.

    Only checks module-level imports, excluding:
    - Imports inside TYPE_CHECKING blocks
    - Imports inside functions

    Args:
        directory: Directory to scan (relative to project root).
        forbidden_prefix: Import prefix that is not allowed.
        specific_files: Optional list of specific files to check (relative to directory).

    Returns:
        List of violations with file path and import statement.
    """
    violations = []
    project_root = Path(__file__).parent.parent.parent.parent
    target_dir = project_root / directory

    if not target_dir.exists():
        return violations

    if specific_files:
        file_paths = [target_dir / f for f in specific_files]
    else:
        file_paths = list(target_dir.rglob("*.py"))

    for file_path in file_paths:
        # Skip __pycache__ directories
        if "__pycache__" in str(file_path):
            continue

        relative_path = file_path.relative_to(project_root)
        imports = get_module_level_imports(file_path)

        for imp in imports:
            # Check if import starts with forbidden prefix
            # Handle both "app.infra" and "from app.infra import X"
            if imp.startswith(forbidden_prefix) or f"app.{forbidden_prefix}" in imp:
                violations.append({
                    "file": str(relative_path),
                    "import": imp,
                })

    return violations


def test_auth_service_does_not_import_infra_modules():
    """Test that auth_service does not import from infrastructure layer at module level.

    This enforces the hexagonal architecture pattern for the auth service.
    """
    violations = scan_imports(
        "backend/app/application",
        forbidden_prefix="app.infra",
        specific_files=["auth_service.py"],
    )

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}: imports '{v['import']}'"
            for v in violations
        )
        assert False, (
            f"auth_service.py should not import from infrastructure layer at module level.\n"
            f"Found {len(violations)} violations:\n{violation_details}\n"
            f"Use repository ports (Protocol) instead, or move imports inside functions for optional dependencies."
        )


def test_document_service_does_not_import_infra_modules():
    """Test that document_service does not import from infrastructure layer at module level.

    This enforces the hexagonal architecture pattern for the document service.
    """
    violations = scan_imports(
        "backend/app/application",
        forbidden_prefix="app.infra",
        specific_files=["document_service.py"],
    )

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}: imports '{v['import']}'"
            for v in violations
        )
        assert False, (
            f"document_service.py should not import from infrastructure layer at module level.\n"
            f"Found {len(violations)} violations:\n{violation_details}\n"
            f"Use repository ports (Protocol) instead, or move imports inside functions for optional dependencies."
        )


def test_application_layer_has_repository_ports():
    """Test that repository ports are defined for architecture compliance."""
    project_root = Path(__file__).parent.parent.parent.parent
    ports_file = project_root / "backend/app/application/ports/repositories.py"

    assert ports_file.exists(), "Repository ports file should exist"

    # Check that the file contains the expected port protocols
    content = ports_file.read_text()
    assert "UserRepositoryPort" in content, "UserRepositoryPort should be defined"
    assert "DocumentRepositoryPort" in content, "DocumentRepositoryPort should be defined"


def test_infra_has_repository_adapters():
    """Test that repository adapters are defined in the infrastructure layer."""
    project_root = Path(__file__).parent.parent.parent.parent
    adapters_dir = project_root / "backend/app/infra/postgres/adapters"

    assert adapters_dir.exists(), "Adapters directory should exist"

    auth_repo = adapters_dir / "auth_repository.py"
    doc_repo = adapters_dir / "document_repository.py"

    assert auth_repo.exists(), "auth_repository.py adapter should exist"
    assert doc_repo.exists(), "document_repository.py adapter should exist"


def test_domain_layer_does_not_import_infra_modules():
    """Test that domain layer does not import from infrastructure layer.

    The domain layer should be completely independent of infrastructure concerns.
    """
    violations = scan_imports("backend/app/domain", forbidden_prefix="app.infra")

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}: imports '{v['import']}'"
            for v in violations
        )
        assert False, (
            f"Domain layer should not import from infrastructure layer.\n"
            f"Found {len(violations)} violations:\n{violation_details}"
        )


def test_domain_layer_does_not_import_sqlalchemy():
    """Test that domain layer does not import SQLAlchemy.

    The domain layer should use pure Python dataclasses, not ORM models.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    domain_dir = project_root / "backend/app/domain"

    violations = []

    for file_path in domain_dir.rglob("*.py"):
        if "__pycache__" in str(file_path):
            continue

        relative_path = file_path.relative_to(project_root)
        imports = get_module_level_imports(file_path)

        for imp in imports:
            if imp.startswith("sqlalchemy"):
                violations.append({
                    "file": str(relative_path),
                    "import": imp,
                })

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}: imports '{v['import']}'"
            for v in violations
        )
        assert False, (
            f"Domain layer should not import SQLAlchemy.\n"
            f"Found {len(violations)} violations:\n{violation_details}"
        )
