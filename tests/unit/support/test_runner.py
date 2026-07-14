from __future__ import annotations

from pathlib import Path

import pytest

from tests import runner


def test_focused_rejects_tests_root_directory() -> None:
    with pytest.raises(
        runner.RunnerUsageError,
        match="focused directory must be inside exactly one test tier",
    ):
        runner._validate_focused_targets(["tests"], None)


def test_run_command_cleans_resources_when_wait_is_interrupted(monkeypatch) -> None:
    events: list[str] = []

    class Process:
        def wait(self) -> int:
            events.append("wait")
            raise runner.RunnerSignal(15)

    class Ledger:
        def start_process(self, *_args, **_kwargs) -> Process:
            events.append("start")
            return Process()

        def cleanup(self):
            events.append("cleanup")
            return runner.CleanupReport()

    class Monitor:
        def __init__(self, _ledger) -> None:
            pass

        def start(self) -> None:
            events.append("monitor-start")

        def stop(self) -> None:
            events.append("monitor-stop")

    class Run:
        environ: dict[str, str] = {}

    monkeypatch.setattr(runner, "ResourceMonitor", Monitor)

    with pytest.raises(runner.RunnerSignal):
        runner._run_command(
            label="interrupted",
            command=["unused"],
            run=Run(),  # type: ignore[arg-type]
            ledger=Ledger(),  # type: ignore[arg-type]
        )

    assert events == ["start", "monitor-start", "wait", "monitor-stop", "cleanup"]


def test_shell_syntax_files_include_both_public_launchers() -> None:
    relative = {
        path.relative_to(runner.REPO_ROOT)
        for path in runner._shell_syntax_files()
    }

    assert Path("buddyswitch-test") in relative
    assert Path("buddyswitch-codex") in relative


def test_public_bootstrap_disables_runner_bytecode_residue() -> None:
    source = (runner.REPO_ROOT / "buddyswitch-test").read_text(encoding="utf-8")

    export = 'export PYTHONDONTWRITEBYTECODE="1"'
    assert export in source
    assert source.index(export) < source.index('exec "${BUDDYSWITCH_PYTHON}"')
