"""Machine-enforced ownership boundaries for the Evidence capability."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

from tests.support.paths import REPO_ROOT


EVIDENCE_ROOT = Path("src/buddyswitch/modules/evidence")
EVIDENCE_TOOL_ROOT = EVIDENCE_ROOT / "private/adapters/tool"
EVIDENCE_ENTRYPOINT = EVIDENCE_ROOT / "entrypoints/browser_evidence.py"
EVIDENCE_PRODUCTION_FILES = (
    EVIDENCE_ROOT / "__init__.py",
    EVIDENCE_ROOT / "module.py",
    EVIDENCE_ROOT / "private/__init__.py",
    EVIDENCE_ROOT / "private/adapters/__init__.py",
    EVIDENCE_TOOL_ROOT / "__init__.py",
    EVIDENCE_TOOL_ROOT / "tool.py",
    EVIDENCE_TOOL_ROOT / "_impl.py",
    EVIDENCE_ROOT / "entrypoints/__init__.py",
    EVIDENCE_ENTRYPOINT,
)
RETIRED_PATHS = (
    Path("src/buddyswitch/env/tools/evidence"),
    Path("src/buddyswitch/runtime_support/browser_evidence.py"),
)
APPLICATION_ENTRYPOINT = Path(
    "src/buddyswitch/application/entrypoints/browser_evidence.py"
)
TOOL_CONTEXT = Path("src/buddyswitch/env/tool_runtime/context.py")
ALLOWED_EVIDENCE_IMPORT_PREFIXES = (
    "buddyswitch.env.tool_runtime",
    "buddyswitch.foundation.composition",
    "buddyswitch.modules.artifact.public",
    "buddyswitch.modules.evidence",
    "buddyswitch.runtime_kernel.client",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0:
                if module:
                    imports.add(module)
                continue
            package_parts = path.relative_to(
                REPO_ROOT / "src"
            ).parent.parts
            retained = len(package_parts) - (node.level - 1)
            if retained < 0:
                continue
            resolved = (*package_parts[:retained], *module.split("."))
            imports.add(".".join(part for part in resolved if part))
    return imports


def test_evidence_has_one_physical_owner_and_no_retired_live_path() -> None:
    assert [
        relative.as_posix()
        for relative in EVIDENCE_PRODUCTION_FILES
        if not (REPO_ROOT / relative).is_file()
    ] == []
    assert not (REPO_ROOT / EVIDENCE_ROOT / "public").exists()
    assert not (REPO_ROOT / EVIDENCE_ROOT / "tests").exists()
    for retired in RETIRED_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired


def test_evidence_is_one_passive_tool_contribution_selected_once() -> None:
    assert (REPO_ROOT / EVIDENCE_ROOT / "module.py").is_file()

    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import COMPONENTS
    from buddyswitch.env.tool_runtime import registry
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.modules.evidence.module import EVIDENCE

    assert isinstance(EVIDENCE, ModuleAssembly)
    assert EVIDENCE.name == "evidence"
    assert EVIDENCE.daemon_handlers == ()
    assert EVIDENCE.cli_commands == ()
    assert EVIDENCE.skills == ()
    assert EVIDENCE.cleanup == ()
    assert EVIDENCE.actor_console_sections == ()
    assert EVIDENCE.inbound_sources == ()
    assert len(EVIDENCE.tools) == 1
    registration = EVIDENCE.tools[0]
    assert registration.definition.id == "evidence"
    assert {action.name for action in registration.definition.actions} == {
        "approve_downgrade",
        "issue_browser",
    }
    assert callable(registration.invoke)

    assert sum(component is EVIDENCE for component in COMPONENTS) == 1
    application = build_application()
    assert [module.name for module in application.modules].count(
        "evidence"
    ) == 1
    assert [
        tool.definition.id for tool in application.tools
    ].count("evidence") == 1
    assert "evidence" not in registry.discover_tool_ids()
    assert [handler.name for handler in application.daemon_handlers] == [
        "demand_triage",
        "task_goal",
        "demand_orchestration",
    ]


def test_evidence_depends_only_on_artifact_public_and_generic_runtime() -> None:
    assert [
        relative.as_posix()
        for relative in EVIDENCE_PRODUCTION_FILES
        if not (REPO_ROOT / relative).is_file()
    ] == []

    violations: list[tuple[str, str]] = []
    evidence_imports: set[str] = set()
    for relative in EVIDENCE_PRODUCTION_FILES:
        path = REPO_ROOT / relative
        for imported in _imports(path):
            evidence_imports.add(imported)
            if imported.split(".", 1)[0] in sys.stdlib_module_names:
                continue
            if imported.startswith(ALLOWED_EVIDENCE_IMPORT_PREFIXES):
                continue
            violations.append((relative.as_posix(), imported))
    assert violations == []
    assert "buddyswitch.modules.artifact.public" in evidence_imports
    assert not [
        imported
        for imported in evidence_imports
        if imported.startswith("buddyswitch.modules.artifact.private")
        or "browser" in imported.lower()
    ]

    package_root = REPO_ROOT / "src/buddyswitch"
    evidence_root = REPO_ROOT / EVIDENCE_ROOT
    assert [
        (path.relative_to(REPO_ROOT).as_posix(), imported)
        for path in sorted(package_root.rglob("*.py"))
        if path != evidence_root and evidence_root not in path.parents
        for imported in _imports(path)
        if imported.startswith("buddyswitch.modules.evidence.private")
    ] == []


def test_stable_entrypoint_delegates_to_evidence_runtime_broker_entrypoint() -> None:
    assert (REPO_ROOT / EVIDENCE_ENTRYPOINT).is_file()
    assert (REPO_ROOT / APPLICATION_ENTRYPOINT).is_file()

    application_imports = _imports(REPO_ROOT / APPLICATION_ENTRYPOINT)
    assert (
        "buddyswitch.modules.evidence.entrypoints.browser_evidence"
        in application_imports
    )
    evidence_imports = _imports(REPO_ROOT / EVIDENCE_ENTRYPOINT)
    assert "buddyswitch.runtime_kernel.client" in evidence_imports
    assert not [
        imported
        for imported in application_imports | evidence_imports
        if imported.startswith("buddyswitch.runtime_support.browser_evidence")
    ]


def test_browser_host_retains_only_generic_status_surface() -> None:
    context_path = REPO_ROOT / TOOL_CONTEXT
    tree = ast.parse(
        context_path.read_text(encoding="utf-8"),
        filename=str(context_path),
    )
    browser_access = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BrowserAccess"
    )
    methods = {
        node.name
        for node in browser_access.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert methods == {"__init__", "status"}


def test_current_guidance_names_only_the_evidence_module_owner() -> None:
    readme = REPO_ROOT / "README.md"
    evidence_architecture = (
        REPO_ROOT / "docs/arch/evidence-capability-architecture.md"
    )
    assert evidence_architecture.is_file()
    assert "src/buddyswitch/modules/evidence/" in readme.read_text(
        encoding="utf-8"
    )
    assert "src/buddyswitch/modules/evidence/" in (
        evidence_architecture.read_text(encoding="utf-8")
    )

    guidance_paths = (
        readme,
        *sorted((REPO_ROOT / "docs/arch").glob("*.md")),
    )
    retired_tokens = (
        "src/buddyswitch/env/tools/evidence",
        "buddyswitch.env.tools.evidence",
        "src/buddyswitch/runtime_support/browser_evidence.py",
        "buddyswitch.runtime_support.browser_evidence",
    )
    assert [
        (path.relative_to(REPO_ROOT).as_posix(), retired)
        for path in guidance_paths
        for retired in retired_tokens
        if retired in path.read_text(encoding="utf-8")
    ] == []
