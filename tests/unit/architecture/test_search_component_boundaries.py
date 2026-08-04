"""Machine-enforced ownership boundaries for the Search capability."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

from tests.support.paths import REPO_ROOT


SEARCH_ROOT = Path("src/buddyswitch/modules/search")
SEARCH_TOOL_ROOT = SEARCH_ROOT / "private/adapters/tool"
SEARCH_TEST_ROOT = SEARCH_ROOT / "tests/integration"
SEARCH_PRODUCTION_FILES = (
    SEARCH_ROOT / "__init__.py",
    SEARCH_ROOT / "module.py",
    SEARCH_ROOT / "private/__init__.py",
    SEARCH_ROOT / "private/adapters/__init__.py",
    SEARCH_TOOL_ROOT / "__init__.py",
    SEARCH_TOOL_ROOT / "tool.py",
    SEARCH_TOOL_ROOT / "_impl.py",
)
SEARCH_TEST_FILES = (
    SEARCH_ROOT / "tests/__init__.py",
    SEARCH_TEST_ROOT / "__init__.py",
    SEARCH_TEST_ROOT / "test_search.py",
    SEARCH_TEST_ROOT / "test_response_search.py",
)
RETIRED_PATHS = (
    Path("src/buddyswitch/env/tools/search"),
    Path("tests/integration/env_tool/test_search.py"),
    Path("tests/integration/env_tool/test_response_search.py"),
)
APPLICATION_COMPOSITION = Path("src/buddyswitch/application/composition.py")
TOOL_CONTEXT = Path("src/buddyswitch/foundation/tool_runtime/context.py")
ALLOWED_SEARCH_IMPORT_PREFIXES = (
    "buddyswitch.foundation.tool_runtime",
    "buddyswitch.foundation.composition",
    "buddyswitch.modules.search.private.adapters.tool",
    "buddyswitch.runtime_support.env_profiles",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            imported.update(
                f"{module}.{alias.name}" if module else alias.name
                for alias in node.names
            )
    return imported


def test_search_has_one_physical_owner_and_no_retired_live_path() -> None:
    expected = (*SEARCH_PRODUCTION_FILES, *SEARCH_TEST_FILES)
    assert [
        relative.as_posix()
        for relative in expected
        if not (REPO_ROOT / relative).is_file()
    ] == []
    assert not (REPO_ROOT / SEARCH_ROOT / "public.py").exists()
    for retired in RETIRED_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired


def test_search_is_one_passive_tool_contribution_selected_once() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import COMPONENTS
    from buddyswitch.foundation.tool_runtime import registry
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.modules.search.module import SEARCH

    assert isinstance(SEARCH, ModuleAssembly)
    assert SEARCH.name == "search"
    assert SEARCH.daemon_handlers == ()
    assert SEARCH.cli_commands == ()
    assert SEARCH.skills == ()
    assert SEARCH.cleanup == ()
    assert SEARCH.actor_console_sections == ()
    assert len(SEARCH.tools) == 1
    registration = SEARCH.tools[0]
    assert registration.definition.id == "search"
    assert {action.name for action in registration.definition.actions} == {
        "request",
        "status",
    }
    assert callable(registration.invoke)

    assert sum(component is SEARCH for component in COMPONENTS) == 1
    assert [component.name for component in COMPONENTS].count("search") == 1
    application = build_application()
    assert [module.name for module in application.modules].count("search") == 1
    assert [
        tool.definition.id
        for tool in application.tools
    ].count("search") == 1
    assert [handler.name for handler in application.daemon_handlers] == [
        "demand_triage",
        "task_goal",
        "demand_orchestration",
    ]


def test_search_source_imports_only_owned_and_public_foundation_surfaces() -> None:
    violations: list[tuple[str, str]] = []
    for relative in SEARCH_PRODUCTION_FILES:
        path = REPO_ROOT / relative
        for imported in _imports(path):
            if imported.split(".", 1)[0] in sys.stdlib_module_names:
                continue
            if imported.startswith(ALLOWED_SEARCH_IMPORT_PREFIXES):
                continue
            violations.append((relative.as_posix(), imported))
    assert violations == []


def test_generic_hosts_import_no_search_private_module() -> None:
    violations: list[tuple[str, str]] = []
    package_root = REPO_ROOT / "src/buddyswitch"
    search_root = REPO_ROOT / SEARCH_ROOT
    for path in sorted(package_root.rglob("*.py")):
        if path == search_root or search_root in path.parents:
            continue
        for imported in _imports(path):
            if imported.startswith("buddyswitch.modules.search.private"):
                violations.append(
                    (path.relative_to(REPO_ROOT).as_posix(), imported)
                )
    assert violations == []


def test_current_guidance_does_not_teach_the_retired_search_path() -> None:
    guidance_paths = (
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs/arch").glob("*.md")),
    )
    retired_tokens = (
        "src/buddyswitch/env/tools/search",
        "buddyswitch.env.tools.search",
    )
    violations = [
        (path.relative_to(REPO_ROOT).as_posix(), retired)
        for path in guidance_paths
        for retired in retired_tokens
        if retired in path.read_text(encoding="utf-8")
    ]
    assert violations == []
