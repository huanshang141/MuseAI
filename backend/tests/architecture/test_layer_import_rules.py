"""Architecture tests enforcing layer dependency direction.

Rules (from CLAUDE.md):
    domain     ← no imports of application/infra/api/workflows
    application ← no imports of api
    infra       ← no imports of application/api (except TYPE_CHECKING)
    workflows   ← currently undefined; will be absorbed into application/workflows/ by B2-6

Any violation MUST either be fixed OR added to KNOWN_VIOLATIONS with a
pointer to the batch that will resolve it.
"""
import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"

# Known violations pending remediation. Each entry is (source_file_relative_to_app, imported_module, resolving_batch).
# When the batch lands and removes the violation, delete the entry.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # B2-2: move PromptGateway/ConversationContextManager into application/ports/
    ("infra/langchain/agents.py", "app.application.prompt_gateway"),
    ("infra/langchain/__init__.py", "app.application.prompt_gateway"),
    ("infra/langchain/curator_agent.py", "app.application.prompt_gateway"),
    ("infra/langchain/curator_tools.py", "app.application.prompt_gateway"),
    ("infra/langchain/tools.py", "app.application.context_manager"),
    # B2-3: move rrf_fusion to domain/services/retrieval.py
    ("infra/langchain/retrievers.py", "app.application.retrieval"),
}


def _get_module_imports(file_path: Path) -> list[str]:
    """Return module-level import targets, skipping TYPE_CHECKING guarded blocks."""
    try:
        tree = ast.parse(file_path.read_text())
    except SyntaxError:
        return []

    type_checking_lines: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for child in ast.walk(node):
                if isinstance(child, (ast.ImportFrom, ast.Import)) and getattr(child, "end_lineno", None):
                    for ln in range(child.lineno, child.end_lineno + 1):
                        type_checking_lines.add(ln)

    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.lineno not in type_checking_lines:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


def _files_in(layer: str) -> list[Path]:
    return sorted(p for p in (APP_ROOT / layer).rglob("*.py") if "__pycache__" not in p.parts)


def _violations(layer: str, forbidden_prefixes: tuple[str, ...]) -> list[tuple[str, str]]:
    """Return a list of (relative_path_from_app, offending_import) tuples."""
    out: list[tuple[str, str]] = []
    for path in _files_in(layer):
        rel = str(path.relative_to(APP_ROOT))
        for imp in _get_module_imports(path):
            for prefix in forbidden_prefixes:
                if imp == prefix or imp.startswith(prefix + "."):
                    out.append((rel, imp))
    return out


def _assert_no_new_violations(layer: str, forbidden_prefixes: tuple[str, ...]) -> None:
    """Fail if the layer contains violations NOT in KNOWN_VIOLATIONS."""
    violations = _violations(layer, forbidden_prefixes)
    unexpected = [v for v in violations if v not in KNOWN_VIOLATIONS]

    if unexpected:
        formatted = "\n".join(f"  - {src} imports {imp}" for src, imp in unexpected)
        raise AssertionError(
            f"Layer '{layer}' has {len(unexpected)} unexpected import(s) of "
            f"forbidden prefixes {forbidden_prefixes}:\n{formatted}\n"
            f"Either remove the import (preferred) or, if tracked by an upcoming "
            f"batch, add the (source, import) tuple to KNOWN_VIOLATIONS in this file."
        )


# ---------- Rules ----------


def test_domain_imports_nothing_forbidden():
    """domain/ must be a pure layer — no imports from any higher layer."""
    _assert_no_new_violations(
        "domain",
        ("app.application", "app.infra", "app.api", "app.workflows"),
    )


def test_application_does_not_import_api():
    """application/ may use domain/infra ports but never calls routers."""
    _assert_no_new_violations("application", ("app.api",))


def test_infra_does_not_import_application_or_api():
    """infra/ implements ports defined in domain/application; never calls them at module load."""
    _assert_no_new_violations("infra", ("app.application", "app.api"))


def test_workflows_does_not_import_api():
    """workflows/ is a floating layer pending B2-6 absorption; for now forbid only api imports."""
    # After B2-6 moves everything into application/workflows/, this test will be deleted.
    if not (APP_ROOT / "workflows").exists():
        return  # Already absorbed.
    _assert_no_new_violations("workflows", ("app.api",))


# ---------- Allowlist hygiene ----------


def test_known_violations_still_exist():
    """Every entry in KNOWN_VIOLATIONS must actually exist. Stale entries mean a
    violation was fixed without removing the allowlist row — clean it up."""
    for src, imp in KNOWN_VIOLATIONS:
        path = APP_ROOT / src
        assert path.exists(), (
            f"KNOWN_VIOLATIONS references nonexistent file {src}. Remove the stale entry."
        )
        actual_imports = _get_module_imports(path)
        assert imp in actual_imports, (
            f"KNOWN_VIOLATIONS expects {src} to import {imp}, but it does not. "
            f"Remove the stale entry (violation was likely fixed by a batch)."
        )


# ---------- Positive assertions kept from the prior version ----------


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


def test_domain_layer_does_not_import_sqlalchemy():
    for path in _files_in("domain"):
        for imp in _get_module_imports(path):
            assert "sqlalchemy" not in imp, (
                f"Domain layer should not use SQLAlchemy directly. "
                f"{path.relative_to(BACKEND_ROOT)} imports {imp}"
            )
