"""Stable ownership checks for the direct Foundation CLI Runtime."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = ROOT / "src" / "buddyswitch"
OWNER_ROOT = PACKAGE_ROOT / "foundation" / "cli_runtime"
LAUNCHER_ROOT = PACKAGE_ROOT / "launcher"
APPLICATION_ASSEMBLY = PACKAGE_ROOT / "application" / "cli_runtime.py"
RETIRED_OWNERS = (
    LAUNCHER_ROOT / "cli.py",
    LAUNCHER_ROOT / "codex_config.py",
    LAUNCHER_ROOT / "shell" / "env.sh",
    LAUNCHER_ROOT / "shell" / "cleanup.sh",
    LAUNCHER_ROOT / "shell" / "browser_cockpit.sh",
)
RETIRED_PATH_TOKENS = tuple(
    path.relative_to(PACKAGE_ROOT).as_posix()
    for path in RETIRED_OWNERS
)
FORBIDDEN_OWNER_ROOTS = (
    "buddyswitch.application",
    "buddyswitch.launcher",
    "buddyswitch.modules",
    "buddyswitch.runtime_support",
    "buddyswitch/application",
    "buddyswitch/launcher",
    "buddyswitch/modules",
    "buddyswitch/runtime_support",
)
ZERO_CONSUMER_HELPERS = (
    "buddyswitch_browser_create_blank_page",
    "buddyswitch_browser_instance_endpoint_is_owned_active",
    "buddyswitch_browser_prepare_instance_ensure_port",
    "buddyswitch_browser_validate_env_or_default_port",
    "buddyswitch_cleanup_requests_execute",
    "buddyswitch_cleanup_trim_state_skeleton",
    "buddyswitch_require_env_profile",
    "buddyswitch_require_role_agents_template",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _assert_inert_package(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert len(tree.body) == 1
    statement = tree.body[0]
    assert isinstance(statement, ast.Expr)
    assert isinstance(statement.value, ast.Constant)
    assert isinstance(statement.value.value, str)


def test_cli_runtime_has_one_direct_owner_and_no_launcher_root() -> None:
    assert {
        path.relative_to(OWNER_ROOT).as_posix()
        for path in OWNER_ROOT.rglob("*")
        if path.is_file()
    } == {
        "__init__.py",
        "config.py",
        "contracts.py",
        "diagnostics.py",
        "runtime.py",
        "shell/browser_cockpit.sh",
        "shell/cleanup.sh",
        "shell/env.sh",
    }
    _assert_inert_package(OWNER_ROOT / "__init__.py")
    assert all(not path.exists() for path in RETIRED_OWNERS)
    assert not LAUNCHER_ROOT.exists()


def test_cli_runtime_embeds_no_upward_executable_root() -> None:
    for path in sorted(
        path
        for path in OWNER_ROOT.rglob("*")
        if path.is_file()
    ):
        source = path.read_text(encoding="utf-8")
        assert [root for root in FORBIDDEN_OWNER_ROOTS if root in source] == [], path


def test_cli_runtime_python_imports_only_direct_foundation_owners() -> None:
    for path in sorted(OWNER_ROOT.glob("*.py")):
        for imported in _imports(path):
            assert not any(
                imported == root or imported.startswith(f"{root}.")
                for root in FORBIDDEN_OWNER_ROOTS[:4]
            ), (path, imported)


def test_application_assembles_one_required_cli_runtime_input() -> None:
    source = APPLICATION_ASSEMBLY.read_text(encoding="utf-8")
    entrypoint = (
        PACKAGE_ROOT / "application" / "entrypoints" / "cli.py"
    ).read_text(encoding="utf-8")
    host_start = (
        PACKAGE_ROOT / "application" / "entrypoints" / "host_control_start.py"
    ).read_text(encoding="utf-8")
    assert "CliRuntimeApplicationInput(" in source
    assert "assemble_cli_runtime(application)" in entrypoint
    assert "application_input=application_input" in entrypoint
    assert "assemble_cli_runtime(application)" in host_start
    assert "resolve_role_browser_capability(" in host_start
    assert "application_environment(" in host_start
    assert "role_browser_capability=role_browser_capability" in host_start


def test_retired_owners_and_zero_consumer_helpers_are_absent() -> None:
    production_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE_ROOT.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".sh"}
    )
    assert [name for name in ZERO_CONSUMER_HELPERS if name in production_source] == []
    assert [path for path in RETIRED_PATH_TOKENS if path in production_source] == []
    retired_imports = {
        "buddyswitch.launcher.cli",
        "buddyswitch.launcher.codex_config",
    }
    for path in PACKAGE_ROOT.rglob("*.py"):
        assert _imports(path).isdisjoint(retired_imports), path


def test_cli_runtime_shells_have_owner_local_package_projection() -> None:
    package_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"
    ]["setuptools"]["package-data"]
    assert package_data["buddyswitch.foundation.cli_runtime"] == ["shell/*.sh"]
