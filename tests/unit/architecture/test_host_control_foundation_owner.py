from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "buddyswitch"

FINAL_FILES = (
    SRC / "foundation" / "host_control" / "__init__.py",
    SRC / "foundation" / "host_control" / "runtime.py",
    SRC / "foundation" / "host_control" / "state.py",
    SRC / "foundation" / "host_control" / "shell" / "host_control.sh",
    SRC / "foundation" / "host_control" / "shell" / "environment.sh",
    SRC / "foundation" / "host_control" / "shell" / "services.sh",
    SRC / "foundation" / "host_control" / "shell" / "daemon.sh",
    SRC / "foundation" / "host_control" / "shell" / "runtime_broker.sh",
    SRC / "foundation" / "process_runtime" / "runtime_lock.py",
    SRC / "application" / "host_control.py",
    SRC / "application" / "entrypoints" / "host_control_start.py",
)
RETIRED_FILES = (
    SRC / "launcher" / "host_control.py",
    SRC / "launcher" / "runtime_lock.py",
    SRC / "launcher" / "shell" / "host_control.sh",
    SRC / "launcher" / "shell" / "daemon.sh",
    SRC / "launcher" / "shell" / "runtime_broker.sh",
)
FORBIDDEN_FOUNDATION_ROOTS = {
    "buddyswitch.application",
    "buddyswitch.launcher",
    "buddyswitch.modules",
    "buddyswitch.runtime_support",
}
FORBIDDEN_FOUNDATION_SHELL_ROOTS = (
    "buddyswitch.application",
    "buddyswitch.launcher",
    "buddyswitch.modules",
    "buddyswitch.runtime_support",
    "application/",
    "launcher/",
    "modules/",
    "runtime_support/",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_host_control_has_one_direct_foundation_owner_and_process_lock() -> None:
    assert all(path.is_file() for path in FINAL_FILES)
    assert all(not path.exists() for path in RETIRED_FILES)

    foundation_python = tuple((SRC / "foundation" / "host_control").rglob("*.py"))
    foundation_python += (SRC / "foundation" / "process_runtime" / "runtime_lock.py",)
    for path in foundation_python:
        for imported in _imports(path):
            assert not any(
                imported == root or imported.startswith(f"{root}.")
                for root in FORBIDDEN_FOUNDATION_ROOTS
            ), f"{path.relative_to(ROOT)} imports {imported}"


def test_every_host_control_shell_is_free_of_upward_implementation_dependencies() -> None:
    shell_root = SRC / "foundation" / "host_control" / "shell"
    shell_files = tuple(sorted(shell_root.rglob("*.sh")))
    assert shell_files
    assert shell_root / "host_control.sh" in shell_files
    for shell in shell_files:
        source = shell.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_FOUNDATION_SHELL_ROOTS:
            assert forbidden not in source, (
                f"{shell.relative_to(ROOT)} contains upward dependency {forbidden}"
            )


def test_application_assembles_one_host_control_for_generic_cli_and_web() -> None:
    cli_source = (SRC / "application" / "entrypoints" / "cli.py").read_text(encoding="utf-8")
    web_source = (SRC / "application" / "entrypoints" / "web.py").read_text(encoding="utf-8")
    for source in (cli_source, web_source):
        assert "assemble_host_control" in source
        assert "host_control=" in source

    generic_cli = (SRC / "launcher" / "cli.py").read_text(encoding="utf-8")
    generic_web = (SRC / "foundation" / "web_runtime" / "runtime.py").read_text(encoding="utf-8")
    for source in (generic_cli, generic_web):
        assert "HostControl()" not in source
        assert "launcher import host_control" not in source
        assert "launcher.host_control" not in source


def test_retired_host_control_and_lock_imports_are_absent_from_production() -> None:
    retired_modules = {
        "buddyswitch.launcher.host_control",
        "buddyswitch.launcher.runtime_lock",
    }
    for path in SRC.rglob("*.py"):
        for imported in _imports(path):
            assert imported not in retired_modules
        source = path.read_text(encoding="utf-8")
        assert "from buddyswitch.launcher import host_control" not in source
        assert "from buddyswitch.launcher import runtime_lock" not in source


def test_global_lifecycle_lock_and_broker_private_lock_remain_distinct() -> None:
    global_lock = (
        SRC / "foundation" / "process_runtime" / "runtime_lock.py"
    ).read_text(encoding="utf-8")
    broker_lock = (
        SRC / "foundation" / "runtime_broker" / "coordinator.py"
    ).read_text(encoding="utf-8")
    assert 'Path(shared_root) / "run" / "locks"' in global_lock
    assert 'workspace_root / ".runtime" / "locks" / "runtime.lock"' in broker_lock
