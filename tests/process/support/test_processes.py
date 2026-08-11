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


def test_run_process_timeout_keeps_post_kill_pipe_drain_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PipeOwningDescendantProcess:
        pid = 4242
        returncode = -9

        def __init__(self) -> None:
            self.communicate_timeouts: list[float | None] = []

        def communicate(
            self,
            input: str | bytes | None = None,
            timeout: float | None = None,
        ) -> tuple[str, str]:
            del input
            self.communicate_timeouts.append(timeout)
            if len(self.communicate_timeouts) == 1:
                raise subprocess.TimeoutExpired(
                    ["pipe-owning-descendant"],
                    timeout,
                    output="before timeout",
                    stderr="before timeout error",
                )
            assert timeout is not None, "post-kill pipe drain must remain bounded"
            return "after kill", "after kill error"

    class Ledger:
        def __init__(self, process: PipeOwningDescendantProcess) -> None:
            self.process = process
            self.reconciled = False

        def start_process(self, *args: object, **kwargs: object) -> PipeOwningDescendantProcess:
            del args, kwargs
            return self.process

        def reconcile_descriptors(self) -> None:
            self.reconciled = True

    process = PipeOwningDescendantProcess()
    ledger = Ledger(process)
    monkeypatch.setattr(
        "tests.support.processes.ResourceLedger.from_environment",
        lambda: ledger,
    )
    monkeypatch.setattr("tests.support.processes.os.killpg", lambda *_args: None)

    with pytest.raises(subprocess.TimeoutExpired) as raised:
        run_process(
            ["pipe-owning-descendant"],
            text=True,
            capture_output=True,
            timeout=0.01,
        )

    assert raised.value.stdout == "after kill"
    assert raised.value.stderr == "after kill error"
    assert process.communicate_timeouts[0] == 0.01
    assert process.communicate_timeouts[1] is not None
    assert ledger.reconciled is True


def test_start_process_can_join_its_owner_process_group() -> None:
    process = ResourceLedger.from_environment().start_process(
        [sys.executable, "-c", "pass"],
        start_new_session=False,
    )

    assert os.getpgid(process.pid) == os.getpgrp()
    assert process.wait(timeout=2) == 0
