import ast
import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"


def _get_module_imports(file_path: Path) -> list[str]:
    """Get module-level import targets from a Python file, excluding TYPE_CHECKING blocks."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return []

    imports = []
    type_checking_lines = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            for child in ast.walk(node):
                if isinstance(child, (ast.ImportFrom, ast.Import)):
                    if hasattr(child, "end_lineno") and child.end_lineno:
                        for ln in range(child.lineno, child.end_lineno + 1):
                            type_checking_lines.add(ln)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.lineno not in type_checking_lines:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

    return imports


def _scan_directory(directory: Path, exclude: set[str] | None = None) -> list[tuple[Path, list[str]]]:
    results = []
    exclude = exclude or set()
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            if f.endswith(".py"):
                path = Path(root) / f
                imports = _get_module_imports(path)
                if imports:
                    results.append((path, imports))
    return results


def test_application_services_use_domain_repositories():
    services_dir = APP_ROOT / "application"
    infra_imports = [
        "app.infra.postgres.repositories",
        "app.infra.langchain.curator_agent",
    ]
    for path, imports in _scan_directory(services_dir, exclude={"__pycache__", "ports"}):
        for imp in imports:
            for forbidden in infra_imports:
                assert forbidden not in imp, (
                    f"{path.relative_to(BACKEND_ROOT)} imports {imp} which violates hexagonal architecture. "
                    f"Application services should depend on domain/repository ports, not infrastructure."
                )


def test_exhibit_service_uses_port():
    path = APP_ROOT / "application" / "exhibit_service.py"
    if not path.exists():
        return
    imports = _get_module_imports(path)
    for imp in imports:
        assert "app.infra.postgres.repositories" not in imp, (
            "exhibit_service.py should import ExhibitRepository from app.domain.repositories, "
            "not PostgresExhibitRepository from app.infra"
        )


def test_profile_service_uses_port():
    path = APP_ROOT / "application" / "profile_service.py"
    if not path.exists():
        return
    imports = _get_module_imports(path)
    for imp in imports:
        assert "app.infra.postgres.repositories" not in imp, (
            "profile_service.py should import VisitorProfileRepository from app.domain.repositories, "
            "not PostgresVisitorProfileRepository from app.infra"
        )


def test_curator_service_uses_port():
    path = APP_ROOT / "application" / "curator_service.py"
    if not path.exists():
        return
    imports = _get_module_imports(path)
    for imp in imports:
        assert "app.infra.langchain.curator_agent" not in imp, (
            "curator_service.py should import CuratorAgentPort from app.application.ports.repositories, "
            "not CuratorAgent from app.infra.langchain"
        )


def test_auth_service_does_not_import_infra_modules():
    path = APP_ROOT / "application" / "auth_service.py"
    if not path.exists():
        return
    imports = _get_module_imports(path)
    for imp in imports:
        assert "app.infra" not in imp, (
            f"auth_service.py should not import from app.infra. Found: {imp}"
        )


def test_document_service_does_not_import_infra_modules():
    path = APP_ROOT / "application" / "document_service.py"
    if not path.exists():
        return
    imports = _get_module_imports(path)
    for imp in imports:
        assert "app.infra" not in imp, (
            f"document_service.py should not import from app.infra. Found: {imp}"
        )


def test_application_layer_has_repository_ports():
    ports_file = APP_ROOT / "application" / "ports" / "repositories.py"
    assert ports_file.exists(), "Repository ports file should exist"

    content = ports_file.read_text()
    required_ports = [
        "UserRepositoryPort",
        "DocumentRepositoryPort",
        "ExhibitRepositoryPort",
        "VisitorProfileRepositoryPort",
        "ChatSessionRepositoryPort",
        "ChatMessageRepositoryPort",
        "LLMProviderPort",
        "CachePort",
        "CuratorAgentPort",
    ]
    for port in required_ports:
        assert port in content, f"Repository port {port} should be defined in ports/repositories.py"


def test_infra_has_repository_adapters():
    adapters_dir = APP_ROOT / "infra" / "postgres" / "adapters"
    assert adapters_dir.exists(), "Adapters directory should exist"

    required_adapters = [
        "auth_repository.py",
        "document_repository.py",
    ]
    for adapter in required_adapters:
        assert (adapters_dir / adapter).exists(), f"Adapter {adapter} should exist"


def test_domain_layer_does_not_import_infra_modules():
    domain_dir = APP_ROOT / "domain"
    for path, imports in _scan_directory(domain_dir, exclude={"__pycache__"}):
        for imp in imports:
            assert "app.infra" not in imp, (
                f"Domain layer should not import from infrastructure. "
                f"{path.relative_to(BACKEND_ROOT)} imports {imp}"
            )


def test_domain_layer_does_not_import_sqlalchemy():
    domain_dir = APP_ROOT / "domain"
    for path, imports in _scan_directory(domain_dir, exclude={"__pycache__"}):
        for imp in imports:
            assert "sqlalchemy" not in imp, (
                f"Domain layer should not use SQLAlchemy directly. "
                f"{path.relative_to(BACKEND_ROOT)} imports {imp}"
            )


def test_chat_stream_service_uses_ports():
    path = APP_ROOT / "application" / "chat_stream_service.py"
    if not path.exists():
        return
    content = path.read_text()
    assert "LLMProviderPort" in content, "chat_stream_service should use LLMProviderPort"
    assert "CachePort" in content, "chat_stream_service should use CachePort"
    assert "from app.infra.providers.llm import LLMProvider" not in content, (
        "chat_stream_service should not import concrete LLMProvider"
    )
    assert "from app.infra.redis.cache import RedisCache" not in content, (
        "chat_stream_service should not import concrete RedisCache"
    )
