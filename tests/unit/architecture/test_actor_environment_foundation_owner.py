"""Stable ownership checks for Foundation Actor workspace publication."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
OWNER = PACKAGE_ROOT / "foundation" / "actor_runtime" / "environment.py"
ENTRYPOINT = PACKAGE_ROOT / "application" / "entrypoints" / "actor_build.py"
RETIRED_OWNER = PACKAGE_ROOT / "launcher" / "actor_environment.py"
LAUNCHER_ROOT = PACKAGE_ROOT / "launcher"
HOST_CONTROL_SHELL = PACKAGE_ROOT / "foundation" / "host_control" / "shell" / "host_control.sh"
HOST_CONTROL_START = PACKAGE_ROOT / "application" / "entrypoints" / "host_control_start.py"
RETIRED_MODULE = "buddyswitch.launcher.actor_environment"


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


def test_actor_environment_has_one_direct_foundation_owner() -> None:
    assert OWNER.is_file()
    assert not RETIRED_OWNER.exists()

    owner_imports = _imports(OWNER)
    forbidden_prefixes = (
        "buddyswitch.application",
        "buddyswitch.launcher",
        "buddyswitch.modules",
        "buddyswitch.runtime_support",
    )
    assert not [
        name for name in owner_imports if name.startswith(forbidden_prefixes)
    ]
    assert {
        name for name in owner_imports if name.startswith("buddyswitch.")
    } == {
        "buddyswitch.foundation.process_runtime.invocation",
        "buddyswitch.foundation.process_runtime.invocation.RuntimeIdentity",
        "buddyswitch.foundation.process_runtime.invocation.current_runtime_identity",
    }
    for name in owner_imports:
        if name.startswith("buddyswitch."):
            continue
        assert (
            name == "__future__"
            or name.split(".", 1)[0] in sys.stdlib_module_names
        )


def test_application_resolves_one_bootstrap_before_direct_publication() -> None:
    entrypoint_imports = _imports(ENTRYPOINT)
    assert "buddyswitch.foundation.actor_runtime.environment" in entrypoint_imports
    assert "buddyswitch.runtime_support.runtime_skills" in entrypoint_imports
    assert "buddyswitch.runtime_support.env_manifest" in entrypoint_imports
    assert RETIRED_MODULE not in entrypoint_imports

    runtime_skill_source = (
        PACKAGE_ROOT / "runtime_support" / "runtime_skills.py"
    ).read_text(encoding="utf-8")
    assert "resolve_runtime_skills" in runtime_skill_source
    assert "install_runtime_skills" not in runtime_skill_source
    assert "validate_runtime_skills" not in runtime_skill_source


def test_stable_host_control_build_boundary_is_application_supplied() -> None:
    host_source = HOST_CONTROL_SHELL.read_text(encoding="utf-8")
    start_source = HOST_CONTROL_START.read_text(encoding="utf-8")
    assert '"${BUDDYSWITCH_HOST_CONTROL_START_MODULE}" build' in host_source
    assert "resolve_actor_bootstrap" in start_source
    assert "buddyswitch.application" not in host_source
    assert "foundation.actor_runtime.environment" not in host_source


def test_retired_launcher_owner_import_and_reexport_are_absent() -> None:
    launcher_tree = ast.parse(
        (LAUNCHER_ROOT / "__init__.py").read_text(encoding="utf-8")
    )
    assert len(launcher_tree.body) == 1
    package_docstring = launcher_tree.body[0]
    assert isinstance(package_docstring, ast.Expr)
    assert isinstance(package_docstring.value, ast.Constant)
    assert isinstance(package_docstring.value.value, str)

    live_python = (
        *PACKAGE_ROOT.rglob("*.py"),
        *(REPO_ROOT / "tests" / "support").rglob("*.py"),
    )
    violations = {
        path.relative_to(REPO_ROOT).as_posix(): sorted(
            name
            for name in _imports(path)
            if name == RETIRED_MODULE or name.startswith(f"{RETIRED_MODULE}.")
        )
        for path in live_python
        if any(
            name == RETIRED_MODULE or name.startswith(f"{RETIRED_MODULE}.")
            for name in _imports(path)
        )
    }
    assert violations == {}
