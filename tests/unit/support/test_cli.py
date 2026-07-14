from __future__ import annotations

import stat
import subprocess

from tests.support.cli import parse_json_stdout, wait_until, write_executable


def test_write_executable_sets_owner_execute_bit(tmp_path) -> None:
    path = write_executable(tmp_path / "tool", "#!/bin/sh\nexit 0\n")

    assert path.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
    assert path.stat().st_mode & stat.S_IXUSR


def test_wait_until_uses_monotonic_polling() -> None:
    attempts = 0

    def ready() -> bool:
        nonlocal attempts
        attempts += 1
        return attempts == 3

    assert wait_until(ready, timeout=0.2, interval=0.001)
    assert attempts == 3


def test_parse_json_stdout_validates_exit_and_object_shape() -> None:
    completed = subprocess.CompletedProcess(["tool"], 0, '{"ok": true}\n', "")

    assert parse_json_stdout(completed) == {"ok": True}
