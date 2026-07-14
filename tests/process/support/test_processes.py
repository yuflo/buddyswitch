from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.support.processes import ResourceLedger, run_process


def test_run_process_captures_output_and_registers_exact_child() -> None:
    completed = run_process(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
        input="owned child",
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout == "OWNED CHILD\n"
    records = ResourceLedger.from_environment().records()
    record = next(
        record
        for record in reversed(records)
        if record.get("kind") == "process"
        and record.get("command") == [
            sys.executable,
            "-c",
            "import sys; print(sys.stdin.read().upper())",
        ]
    )
    assert record["pid"] > 0
    assert record["pgid"] > 0
    assert record["start_identity"]


def test_run_process_honors_check() -> None:
    with pytest.raises(subprocess.CalledProcessError) as raised:
        run_process(
            [sys.executable, "-c", "raise SystemExit(7)"],
            text=True,
            capture_output=True,
            check=True,
        )

    assert raised.value.returncode == 7


def test_start_process_can_join_its_owner_process_group() -> None:
    process = ResourceLedger.from_environment().start_process(
        [sys.executable, "-c", "pass"],
        start_new_session=False,
    )

    assert os.getpgid(process.pid) == os.getpgrp()
    assert process.wait(timeout=2) == 0
