"""Public test support surface for fake Codex."""

from __future__ import annotations

import os
from pathlib import Path
import shlex

from tests.support.python import PYTHON
from tests.support.cli import write_executable
from tests.support.paths import LAUNCHER_ROOT, REPO_ROOT, SCRIPTS_ROOT

from .rpc import handle_rpc_message

_RUNNER_ROOT = os.environ.get("BUDDYSWITCH_TEST_RUN_ROOT")


def main(argv: list[str]) -> int:
    from .main import main as execute

    return execute(argv)


def executable_source() -> str:
    run_root = _RUNNER_ROOT
    if not run_root:
        raise RuntimeError("fake Codex requires the BuddySwitch test runner")
    python_path = os.pathsep.join(
        str(path) for path in (REPO_ROOT, SCRIPTS_ROOT, LAUNCHER_ROOT)
    )
    return (
        "#!/bin/sh\n"
        f"export PYTHONPATH={shlex.quote(python_path)}\n"
        "export PYTHONDONTWRITEBYTECODE=1\n"
        f"export BUDDYSWITCH_TEST_RUN_ROOT={shlex.quote(run_root)}\n"
        f"exec {shlex.quote(PYTHON)} -B -m tests.support.fake_codex.main \"$@\"\n"
    )


def write_fake_codex(path: Path) -> Path:
    return write_executable(path, executable_source())


__all__ = ["executable_source", "handle_rpc_message", "main", "write_fake_codex"]
