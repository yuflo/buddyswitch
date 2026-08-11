"""Stable ownership checks for the converged Foundation Daemon."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPO_ROOT / "src" / "buddyswitch"
FOUNDATION_DAEMON = SOURCE_ROOT / "foundation" / "daemon"
LAUNCHER = SOURCE_ROOT / "launcher"

FOUNDATION_DAEMON_FILES = {
    "central_process.py",
    "central_service.py",
    "client.py",
    "contracts.py",
    "inbound.py",
    "instance.py",
    "instance_process.py",
    "mailbox.py",
    "runtime.py",
    "state.py",
    "triggers.py",
}

RETIRED_LAUNCHER_FILES = {
    "central_daemon.py",
    "central_daemon_core.py",
    "daemon_contracts.py",
    "daemon_core.py",
    "daemon_mailbox.py",
    "daemon_runtime.py",
    "daemon_state.py",
    "daemon_triggers.py",
    "instance_daemon.py",
    "notification_center.py",
    "runtime_event_log.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_daemon_has_one_foundation_owner_without_launcher_back_edges() -> None:
    actual_files = {
        path.name for path in FOUNDATION_DAEMON.glob("*.py") if path.name != "__init__.py"
    }
    assert actual_files == FOUNDATION_DAEMON_FILES
    assert not any((LAUNCHER / name).exists() for name in RETIRED_LAUNCHER_FILES)
    assert (SOURCE_ROOT / "foundation" / "process_runtime" / "event_log.py").is_file()

    for path in FOUNDATION_DAEMON.glob("*.py"):
        imports = _imports(path)
        assert not any(name.startswith("buddyswitch.launcher") for name in imports)
        assert not any(name.startswith("buddyswitch.application") for name in imports)

    entrypoint_imports = _imports(
        SOURCE_ROOT / "application" / "entrypoints" / "instance_daemon.py"
    )
    assert "buddyswitch.application.daemon" in entrypoint_imports
    assert "buddyswitch.foundation.daemon" in entrypoint_imports
