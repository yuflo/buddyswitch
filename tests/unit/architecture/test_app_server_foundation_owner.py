"""Stable ownership checks for the direct Foundation App Server."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
OWNER_ROOT = PACKAGE_ROOT / "foundation" / "app_server"
RUNTIME = OWNER_ROOT / "runtime.py"
SHELL = OWNER_ROOT / "shell" / "app_server.sh"
RETIRED_RUNTIME = PACKAGE_ROOT / "launcher" / "app_server.py"
RETIRED_SHELL = PACKAGE_ROOT / "launcher" / "shell" / "app_server.sh"
DIRECT_CONSUMERS = (
    PACKAGE_ROOT / "application" / "daemon_host.py",
    PACKAGE_ROOT / "application" / "entrypoints" / "app_server.py",
    PACKAGE_ROOT / "foundation" / "actor_runtime" / "session.py",
    PACKAGE_ROOT / "foundation" / "actor_runtime" / "side_thread_lifecycle.py",
    PACKAGE_ROOT
    / "modules"
    / "demand"
    / "private"
    / "adapters"
    / "daemon"
    / "demand_triage_handler.py",
    PACKAGE_ROOT / "modules" / "task" / "private" / "adapters" / "goal" / "handler.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def test_app_server_has_one_direct_foundation_owner_and_no_launcher_residue() -> None:
    assert {path.relative_to(OWNER_ROOT).as_posix() for path in OWNER_ROOT.rglob("*") if path.is_file()} == {
        "__init__.py",
        "runtime.py",
        "shell/app_server.sh",
    }
    package_tree = ast.parse((OWNER_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert len(package_tree.body) == 1
    package_docstring = package_tree.body[0]
    assert isinstance(package_docstring, ast.Expr)
    assert isinstance(package_docstring.value, ast.Constant)
    assert isinstance(package_docstring.value.value, str)
    assert not RETIRED_RUNTIME.exists()
    assert not RETIRED_SHELL.exists()

    for path in PACKAGE_ROOT.rglob("*.py"):
        assert "buddyswitch.launcher.app_server" not in _imports(path), path

    retired_tokens = (
        "buddyswitch.launcher.app_server",
        "launcher/app_server.py",
        "launcher/shell/app_server.sh",
    )
    for path in PACKAGE_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".sh"}:
            source = path.read_text(encoding="utf-8")
            assert not any(token in source for token in retired_tokens), path


def test_app_server_runtime_has_only_direct_process_runtime_dependencies() -> None:
    imports = _imports(RUNTIME)
    buddyswitch_imports = {name for name in imports if name.startswith("buddyswitch.")}
    assert buddyswitch_imports == {
        "buddyswitch.foundation.process_runtime.event_log",
        "buddyswitch.foundation.process_runtime.process_identity",
    }
    for name in imports - buddyswitch_imports:
        top_level = name.split(".", 1)[0]
        assert top_level == "__future__" or top_level in sys.stdlib_module_names, name


def test_every_live_host_imports_the_direct_foundation_runtime() -> None:
    for consumer in DIRECT_CONSUMERS:
        assert "buddyswitch.foundation.app_server.runtime" in _imports(consumer), consumer

    cli_source = (PACKAGE_ROOT / "foundation" / "cli_runtime" / "runtime.py").read_text(encoding="utf-8")
    host_source = (PACKAGE_ROOT / "foundation" / "host_control" / "shell" / "host_control.sh").read_text(
        encoding="utf-8"
    )
    assert 'PACKAGE_ROOT / "foundation" / "app_server" / "shell" / "app_server.sh"' in cli_source
    assert "../../app_server/shell/app_server.sh" in host_source
    assert 'SHELL_ROOT / "app_server.sh"' not in cli_source
    assert '${HOST_CONTROL_DIR}/app_server.sh' not in host_source


def test_app_server_shell_has_direct_package_data_ownership() -> None:
    document = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = document["tool"]["setuptools"]["package-data"]
    assert package_data["buddyswitch.foundation.app_server"] == ["shell/*.sh"]
