"""Machine-enforced ownership boundaries for the Context capability."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

from tests.support.paths import REPO_ROOT


CONTEXT_ROOT = Path("src/buddyswitch/modules/context")
CONTEXT_PRIVATE = CONTEXT_ROOT / "private"
CONTEXT_TOOL_ROOT = CONTEXT_PRIVATE / "adapters/tool"
CONTEXT_PRODUCTION_FILES = (
    CONTEXT_ROOT / "__init__.py",
    CONTEXT_ROOT / "module.py",
    CONTEXT_PRIVATE / "__init__.py",
    CONTEXT_PRIVATE / "adapters/__init__.py",
    CONTEXT_TOOL_ROOT / "__init__.py",
    CONTEXT_TOOL_ROOT / "tool.py",
    CONTEXT_TOOL_ROOT / "_impl.py",
)
RETIRED_PATHS = (
    Path("src/buddyswitch/env/tools/context"),
)
ALLOWED_CONTEXT_IMPORT_PREFIXES = (
    "buddyswitch.foundation.tool_runtime",
    "buddyswitch.foundation.composition",
    "buddyswitch.modules.artifact.public",
    "buddyswitch.modules.communication.public",
    "buddyswitch.modules.context",
    "buddyswitch.modules.task.public",
    "buddyswitch.modules.track.public",
    "buddyswitch.runtime_support.env_profiles",
    "buddyswitch.runtime_support.role_auth",
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
                imports.update(
                    f"{module}.{alias.name}" if module else alias.name
                    for alias in node.names
                )
                continue
            package_parts = path.relative_to(REPO_ROOT / "src").parent.parts
            retained = len(package_parts) - (node.level - 1)
            if retained < 0:
                continue
            resolved_module = ".".join(
                part
                for part in (*package_parts[:retained], *module.split("."))
                if part
            )
            imports.update(
                f"{resolved_module}.{alias.name}"
                if resolved_module
                else alias.name
                for alias in node.names
            )
    return imports


def test_context_has_one_physical_owner_and_no_retired_live_path() -> None:
    assert tuple(
        path.relative_to(REPO_ROOT)
        for path in sorted((REPO_ROOT / CONTEXT_ROOT).rglob("*.py"))
    ) == tuple(sorted(CONTEXT_PRODUCTION_FILES))
    assert {path.name for path in (REPO_ROOT / CONTEXT_ROOT).iterdir()} == {
        "__init__.py",
        "module.py",
        "private",
    }
    assert {path.name for path in (REPO_ROOT / CONTEXT_PRIVATE).iterdir()} == {
        "__init__.py",
        "adapters",
    }
    for retired in RETIRED_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired


def test_context_is_one_passive_tool_contribution_selected_once_and_last() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import (
        COMPONENTS,
        CONTEXT,
        DAEMON_HANDLER_ORDER,
    )
    from buddyswitch.foundation.tool_runtime import registry
    from buddyswitch.foundation.composition import ModuleAssembly

    assert isinstance(CONTEXT, ModuleAssembly)
    assert CONTEXT.name == "context"
    assert CONTEXT.daemon_handlers == ()
    assert CONTEXT.cli_commands == ()
    assert CONTEXT.skills == ()
    assert CONTEXT.cleanup == ()
    assert CONTEXT.actor_console_sections == ()
    assert CONTEXT.inbound_sources == ()
    assert CONTEXT.web_routes == ()
    assert CONTEXT.web_workers == ()
    assert len(CONTEXT.tools) == 1
    registration = CONTEXT.tools[0]
    assert registration.definition.id == "context"
    assert {action.name for action in registration.definition.actions} == {
        "get",
        "list_sources",
        "summarize",
    }
    assert callable(registration.invoke)

    assert [component.name for component in COMPONENTS] == [
        "demand",
        "task",
        "search",
        "artifact",
        "track",
        "evidence",
        "communication",
        "context",
    ]
    assert COMPONENTS[-1] is CONTEXT
    assert sum(component is CONTEXT for component in COMPONENTS) == 1

    application = build_application()
    assert application.modules[-1] is CONTEXT
    assert [module.name for module in application.modules].count("context") == 1
    assert [tool.definition.id for tool in application.tools].count("context") == 1
    assert DAEMON_HANDLER_ORDER == (
        "demand_triage",
        "task_goal",
        "demand_orchestration",
    )
    assert [handler.name for handler in application.daemon_handlers] == list(
        DAEMON_HANDLER_ORDER
    )


def test_context_private_depends_only_on_public_components_and_generic_runtime() -> None:
    context_imports: set[str] = set()
    violations: list[tuple[str, str]] = []
    for relative in CONTEXT_PRODUCTION_FILES:
        path = REPO_ROOT / relative
        for imported in _imports(path):
            context_imports.add(imported)
            if imported.split(".", 1)[0] in sys.stdlib_module_names:
                continue
            if imported.startswith(ALLOWED_CONTEXT_IMPORT_PREFIXES):
                continue
            violations.append((relative.as_posix(), imported))
    assert violations == []
    assert {
        "buddyswitch.modules.artifact.public",
        "buddyswitch.modules.communication.public",
        "buddyswitch.modules.task.public",
        "buddyswitch.modules.track.public",
    }.issubset(context_imports)
    assert not [
        imported
        for imported in context_imports
        if ".private" in imported
        and not imported.startswith("buddyswitch.modules.context.private")
    ]

    package_root = REPO_ROOT / "src/buddyswitch"
    context_root = REPO_ROOT / CONTEXT_ROOT
    context_private_consumers = [
        (path.relative_to(REPO_ROOT).as_posix(), imported)
        for path in sorted(package_root.rglob("*.py"))
        if path != context_root and context_root not in path.parents
        for imported in _imports(path)
        if imported.startswith("buddyswitch.modules.context.private")
    ]
    assert context_private_consumers == []

    context_module_consumers = [
        (path.relative_to(REPO_ROOT).as_posix(), imported)
        for path in sorted(package_root.rglob("*.py"))
        if path != context_root and context_root not in path.parents
        for imported in _imports(path)
        if imported.startswith("buddyswitch.modules.context")
    ]
    assert context_module_consumers == [
        (
            "src/buddyswitch/application/composition.py",
            "buddyswitch.modules.context.module.CONTEXT",
        )
    ]


def test_context_specific_shared_host_residue_is_absent() -> None:
    host_path = REPO_ROOT / "src/buddyswitch/foundation/tool_runtime/context.py"
    tree = ast.parse(host_path.read_text(encoding="utf-8"), filename=str(host_path))
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    assert "RuntimeObjectAccess" not in classes
    assert "RegistryCatalogAccess" not in classes

    tool_context = classes["ToolContext"]
    fields = {
        node.target.id
        for node in tool_context.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    methods = {
        node.name
        for node in tool_context.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "objects" not in fields
    assert "catalog" not in fields
    assert "runtime_policy_preview" not in methods


def test_current_guidance_names_only_the_context_module_owner() -> None:
    readme = REPO_ROOT / "README.md"
    architecture = REPO_ROOT / "docs/arch/context-capability-architecture.md"
    assert architecture.is_file()
    for path in (readme, architecture):
        assert "src/buddyswitch/modules/context/" in path.read_text(
            encoding="utf-8"
        )

    guidance_paths = (
        readme,
        *sorted((REPO_ROOT / "docs/arch").glob("*.md")),
    )
    retired_tokens = (
        "src/buddyswitch/env/tools/context",
        "buddyswitch.env.tools.context",
    )
    assert [
        (path.relative_to(REPO_ROOT).as_posix(), token)
        for path in guidance_paths
        for token in retired_tokens
        if token in path.read_text(encoding="utf-8")
    ] == []
