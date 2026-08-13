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
    assert source.index(export) < source.index(
        'exec "${RUNTIME_DIR}/venv/bin/python" -m tests.runner'
    )
    assert "PYTHONPATH" in source
    assert "src/buddyswitch" not in source


def test_pytest_command_isolates_duplicate_test_module_basenames() -> None:
    command = runner._pytest_command(["tests/unit"])

    assert "--import-mode=importlib" in command


def test_local_test_tiers_discover_module_and_role_owners_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for owner in ("modules/search", "roles/market"):
        for tier in ("unit", "contract", "integration"):
            (tmp_path / "src" / "buddyswitch" / owner / "tests" / tier).mkdir(
                parents=True
            )

    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)

    roots = runner._local_test_tier_roots()

    assert {
        tier: tuple(path.relative_to(tmp_path).as_posix() for path in paths)
        for tier, paths in roots.items()
    } == {
        "unit": (
            "src/buddyswitch/modules/search/tests/unit",
            "src/buddyswitch/roles/market/tests/unit",
        ),
        "contract": (
            "src/buddyswitch/modules/search/tests/contract",
            "src/buddyswitch/roles/market/tests/contract",
        ),
        "integration": (
            "src/buddyswitch/modules/search/tests/integration",
            "src/buddyswitch/roles/market/tests/integration",
        ),
    }


def test_local_test_tiers_exclude_parent_and_role_process_system_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    role_tests = tmp_path / "src" / "buddyswitch" / "roles" / "market" / "tests"
    for tier in ("unit", "contract", "integration", "process", "system"):
        (role_tests / tier).mkdir(parents=True)

    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)

    roots = runner._local_test_tier_roots()
    discovered = {path for paths in roots.values() for path in paths}

    assert role_tests.resolve() not in discovered
    assert (role_tests / "process").resolve() not in discovered
    assert (role_tests / "system").resolve() not in discovered


def test_current_role_local_tiers_are_discovered_exactly_once() -> None:
    roots = runner._local_test_tier_roots()
    discovered = tuple(path for paths in roots.values() for path in paths)
    role_tests_root = runner.REPO_ROOT / "src" / "buddyswitch" / "roles"
    expected = {
        path.resolve(strict=True)
        for tier in ("unit", "contract", "integration")
        for path in role_tests_root.glob(f"*/tests/{tier}")
        if path.is_dir()
    }

    assert expected
    assert set(discovered) >= expected
    assert len(discovered) == len(set(discovered))
