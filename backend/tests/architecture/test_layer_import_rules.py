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
KNOWN_VIOLATIONS: set[tuple[str, str]] = set()


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


def _violations(
    layer: str,
    forbidden_prefixes: tuple[str, ...],
    allowed_prefixes: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    """Return a list of (relative_path_from_app, offending_import) tuples."""
    out: list[tuple[str, str]] = []
    for path in _files_in(layer):
        rel = str(path.relative_to(APP_ROOT))
        for imp in _get_module_imports(path):
            for prefix in forbidden_prefixes:
                if imp == prefix or imp.startswith(prefix + "."):
                    if any(imp == ap or imp.startswith(ap + ".") for ap in allowed_prefixes):
                        continue
                    out.append((rel, imp))
    return out


def _assert_no_new_violations(
    layer: str,
    forbidden_prefixes: tuple[str, ...],
    allowed_prefixes: tuple[str, ...] = (),
) -> None:
    """Fail if the layer contains violations NOT in KNOWN_VIOLATIONS."""
    violations = _violations(layer, forbidden_prefixes, allowed_prefixes)
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
    """infra/ implements ports defined in application/ports/; never calls application services or api directly."""
    _assert_no_new_violations("infra", ("app.application", "app.api"), allowed_prefixes=("app.application.ports",))


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


def test_postgres_adapters_consolidated():
    """infra/postgres/ adapters must be consolidated into infra/postgres/adapters/.

    After B2-4, infra/postgres/repositories.py and
    infra/postgres/prompt_repository.py are deleted; their classes
    live in infra/postgres/adapters/.
    """
    old_repos = APP_ROOT / "infra" / "postgres" / "repositories.py"
    old_prompt = APP_ROOT / "infra" / "postgres" / "prompt_repository.py"
    assert not old_repos.exists(), (
        "infra/postgres/repositories.py should be deleted (ARCH-P2-01). "
        "Move contents to infra/postgres/adapters/."
    )
    assert not old_prompt.exists(), (
        "infra/postgres/prompt_repository.py should be deleted (ARCH-P2-01). "
        "Move contents to infra/postgres/adapters/."
    )

    adapters_dir = APP_ROOT / "infra" / "postgres" / "adapters"
    assert adapters_dir.is_dir(), "infra/postgres/adapters/ must be a directory"

    adapter_files = list(adapters_dir.glob("*.py"))
    adapter_names = [f.name for f in adapter_files if f.name != "__init__.py"]
    assert len(adapter_names) >= 2, (
        "infra/postgres/adapters/ must contain at least 2 adapter modules "
        "(exhibit, profile, prompt, etc.)"
    )


def test_rrf_fusion_lives_in_domain_services():
    """rrf_fusion is a pure algorithm and must live in domain/services/retrieval.py.

    After B2-3, application/retrieval.py is deleted and the function
    is in domain/services/retrieval.py. Infra must not import from
    application/retrieval.
    """
    old_location = APP_ROOT / "application" / "retrieval.py"
    assert not old_location.exists(), (
        "application/retrieval.py should be deleted (ARCH-P1-03). "
        "rrf_fusion must live in domain/services/retrieval.py."
    )

    new_location = APP_ROOT / "domain" / "services" / "retrieval.py"
    assert new_location.exists(), (
        "domain/services/retrieval.py must exist with rrf_fusion function."
    )

    content = new_location.read_text()
    assert "rrf_fusion" in content, (
        "domain/services/retrieval.py must define rrf_fusion function."
    )


def test_context_manager_port_exists_in_ports():
    """ConversationContextManagerPort must exist in application/ports/context_manager.py.

    After B2-2b, infra/langchain/tools.py imports the Port from
    application/ports/ instead of the concrete ConversationContextManager
    from application/context_manager.py.
    """
    port_file = APP_ROOT / "application" / "ports" / "context_manager.py"
    assert port_file.exists(), (
        "application/ports/context_manager.py must exist with "
        "ConversationContextManagerPort Protocol."
    )

    content = port_file.read_text()
    assert "ConversationContextManagerPort" in content, (
        "application/ports/context_manager.py must define "
        "ConversationContextManagerPort Protocol."
    )


def test_prompt_gateway_lives_in_ports():
    """PromptGateway Protocol must live in application/ports/prompt_gateway.py.

    After B2-2a, application/prompt_gateway.py is deleted and the Protocol
    is in application/ports/prompt_gateway.py. Infra and workflows must
    import from the ports location, not from application root.
    """
    old_location = APP_ROOT / "application" / "prompt_gateway.py"
    assert not old_location.exists(), (
        "application/prompt_gateway.py should be deleted (ARCH-P1-01). "
        "PromptGateway Protocol must live in application/ports/prompt_gateway.py."
    )

    new_location = APP_ROOT / "application" / "ports" / "prompt_gateway.py"
    assert new_location.exists(), (
        "application/ports/prompt_gateway.py must exist with the PromptGateway Protocol."
    )

    content = new_location.read_text()
    assert "class PromptGateway" in content, (
        "application/ports/prompt_gateway.py must define the PromptGateway Protocol."
    )


def test_application_does_not_import_domain_repositories():
    """application/ must use application/ports/repositories.py, not domain/repositories.py.

    The dual-Port surface (domain/repositories.py + application/ports/repositories.py)
    violates ARCH-P1-02. After B2-1, domain/repositories.py is deleted and all
    application services must import from the canonical ports location.
    """
    domain_repos = APP_ROOT / "domain" / "repositories.py"
    assert not domain_repos.exists(), (
        "domain/repositories.py should be deleted (ARCH-P1-02). "
        "All repository ports must live in application/ports/repositories.py."
    )

    for path in _files_in("application"):
        rel = str(path.relative_to(APP_ROOT))
        for imp in _get_module_imports(path):
            assert imp != "app.domain.repositories" and not imp.startswith("app.domain.repositories."), (
                f"{rel} imports {imp} from domain/repositories.py. "
                f"Use application/ports/repositories.py instead (ARCH-P1-02)."
            )


def test_domain_layer_does_not_import_sqlalchemy():
    for path in _files_in("domain"):
        for imp in _get_module_imports(path):
            assert "sqlalchemy" not in imp, (
                f"Domain layer should not use SQLAlchemy directly. "
                f"{path.relative_to(BACKEND_ROOT)} imports {imp}"
            )
