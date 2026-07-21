from __future__ import annotations

import argparse
from collections.abc import Sequence
import importlib.metadata
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

from tests.support.environment import RunEnvironment
from tests.support.paths import LAUNCHER_ROOT, REPO_ROOT, SCRIPTS_ROOT
from tests.support.processes import (
    CleanupReport,
    ResourceLedger,
    ResourceMonitor,
    SystemLock,
)


class RunnerUsageError(ValueError):
    pass


class RunnerSignal(BaseException):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def _preflight() -> None:
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError(
            f"BuddySwitch tests require Python 3.13; got {sys.version_info.major}.{sys.version_info.minor}"
        )
    try:
        pytest_version = importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "pytest is missing; install requirements-test.txt with BUDDYSWITCH_PYTHON"
        ) from exc
    if pytest_version != "9.0.3":
        raise RuntimeError(
            f"BuddySwitch tests require pytest 9.0.3; got {pytest_version}"
        )
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node is missing from PATH")
    completed = subprocess.run(
        [node, "-e", 'require("node:test")'],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Node does not provide node:test: {completed.stderr.strip()}")


def _target_file(target: str) -> Path:
    raw_path = target.split("::", 1)[0]
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve(strict=False)


def _validate_focused_targets(
    targets: Sequence[str], node_name_pattern: str | None
) -> tuple[list[str], list[str], bool]:
    if not targets:
        raise RunnerUsageError("focused requires at least one explicit target")
    python_targets: list[str] = []
    javascript_targets: list[str] = []
    needs_system_lock = False
    tests_root = (REPO_ROOT / "tests").resolve(strict=True)
    system_root = (tests_root / "system").resolve(strict=False)
    tier_roots = {
        tier: (tests_root / tier).resolve(strict=True)
        for tier in ("unit", "integration", "process", "system")
    }
    for target in targets:
        path = _target_file(target)
        if not path.exists():
            raise RunnerUsageError(f"focused target does not exist: {target}")
        if path != tests_root and not path.is_relative_to(tests_root):
            raise RunnerUsageError(f"focused target must be under tests/: {target}")
        matching_tiers = [
            tier for tier, root in tier_roots.items() if path == root or path.is_relative_to(root)
        ]
        if len(matching_tiers) != 1:
            raise RunnerUsageError(
                f"focused directory must be inside exactly one test tier: {target}"
            )
        if path == system_root or path.is_relative_to(system_root):
            needs_system_lock = True
        if path.is_dir() or path.suffix == ".py":
            python_targets.append(target)
        elif path.name.endswith(".test.js"):
            if "::" in target:
                raise RunnerUsageError(
                    "JavaScript case selection uses --node-name-pattern, not :: nodeids"
                )
            javascript_targets.append(target)
        else:
            raise RunnerUsageError(
                f"focused target must be a Python file/nodeid, directory, or *.test.js: {target}"
            )
    if node_name_pattern is not None and (
        len(javascript_targets) != 1 or python_targets
    ):
        raise RunnerUsageError(
            "--node-name-pattern requires exactly one JavaScript file and no Python targets"
        )
    return python_targets, javascript_targets, needs_system_lock


def _print_command(label: str, command: Sequence[str]) -> None:
    print(f"[{label}] {shlex.join(command)}", flush=True)


def _report_cleanup(report: CleanupReport) -> bool:
    for pid in report.identity_mismatches:
        print(f"cleanup: refused PID with changed start identity: {pid}", flush=True)
    for residual in report.residuals:
        print(f"cleanup residual: {residual}", file=sys.stderr, flush=True)
    return not report.residuals


def _run_command(
    *,
    label: str,
    command: Sequence[str],
    run: RunEnvironment,
    ledger: ResourceLedger,
) -> int:
    _print_command(label, command)
    started = time.monotonic()
    process = ledger.start_process(
        command,
        cwd=REPO_ROOT,
        env=run.environ,
        stdin=None,
        stdout=None,
        stderr=None,
    )
    monitor = ResourceMonitor(ledger)
    monitor.start()
    try:
        try:
            returncode = process.wait()
        finally:
            monitor.stop()
    finally:
        clean = _report_cleanup(ledger.cleanup())
    duration = time.monotonic() - started
    status = "passed" if returncode == 0 and clean else "failed"
    print(f"[{label}] {status} in {duration:.2f}s", flush=True)
    if returncode != 0:
        return returncode
    return 0 if clean else 1


def _pytest_command(
    targets: Sequence[str], *, durations: int | None = None
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--import-mode=importlib",
        *targets,
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    if durations is not None:
        command.append(f"--durations={durations}")
    return command


def _node_command(targets: Sequence[str], node_name_pattern: str | None) -> list[str]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node disappeared after preflight")
    command = [node, "--test"]
    if node_name_pattern is not None:
        command.append(f"--test-name-pattern={node_name_pattern}")
    command.extend(targets)
    return command


def _shell_syntax_files() -> list[Path]:
    files = [REPO_ROOT / "buddyswitch-test", REPO_ROOT / "buddyswitch-codex"]
    files.extend(sorted((REPO_ROOT / "tools").rglob("*.sh")))
    files.extend(sorted((REPO_ROOT / "scripts").rglob("*.sh")))
    return files


def _run_focused(
    args: argparse.Namespace,
    run: RunEnvironment,
    ledger: ResourceLedger,
) -> int:
    python_targets, javascript_targets, needs_system_lock = _validate_focused_targets(
        args.targets, args.node_name_pattern
    )
    lock: SystemLock | None = None
    if needs_system_lock:
        lock = SystemLock.for_repo(REPO_ROOT)
        lock.acquire(timeout=2.0)
    try:
        if python_targets:
            returncode = _run_command(
                label="focused-python",
                command=_pytest_command(python_targets),
                run=run,
                ledger=ledger,
            )
            if returncode != 0:
                return returncode
        if javascript_targets:
            return _run_command(
                label="focused-javascript",
                command=_node_command(javascript_targets, args.node_name_pattern),
                run=run,
                ledger=ledger,
            )
        return 0
    finally:
        if lock is not None:
            lock.release()


def _run_full(run: RunEnvironment, ledger: ResourceLedger) -> int:
    phases: list[tuple[str, list[str], bool]] = []
    for tier in ("unit", "integration", "process", "system"):
        tier_path = REPO_ROOT / "tests" / tier
        if not tier_path.is_dir():
            raise RuntimeError(f"final test tier is missing: tests/{tier}")
        relative = tier_path.relative_to(REPO_ROOT).as_posix()
        phases.append((tier, _pytest_command([relative], durations=25), tier == "system"))
        if tier == "unit":
            javascript = [
                path.relative_to(REPO_ROOT).as_posix()
                for path in sorted(tier_path.rglob("*.test.js"))
            ]
            if javascript:
                phases.append(("unit-javascript", _node_command(javascript, None), False))
    for label, command, locked in phases:
        lock: SystemLock | None = None
        if locked:
            lock = SystemLock.for_repo(REPO_ROOT)
            lock.acquire(timeout=2.0)
        try:
            returncode = _run_command(
                label=label,
                command=command,
                run=run,
                ledger=ledger,
            )
        finally:
            if lock is not None:
                lock.release()
        if returncode != 0:
            return returncode

    shell_command = ["bash", "-n", *(str(path) for path in _shell_syntax_files())]
    returncode = _run_command(
        label="shell-syntax",
        command=shell_command,
        run=run,
        ledger=ledger,
    )
    if returncode != 0:
        return returncode
    return _run_command(
        label="diff-check",
        command=["git", "diff", "--check"],
        run=run,
        ledger=ledger,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddyswitch-test")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    focused = subparsers.add_parser("focused")
    focused.add_argument("targets", nargs="*")
    focused.add_argument("--node-name-pattern")
    subparsers.add_parser("full")
    return parser


def _signal_handler(signum: int, _frame: object) -> None:
    raise RunnerSignal(signum)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _preflight()
    except RuntimeError as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return 2
    args = _build_parser().parse_args(argv)
    run = RunEnvironment.create()
    ledger = ResourceLedger(run.ledger_path, run.root)
    print(f"run id: {run.run_id}", flush=True)
    print(f"run root: {run.root}", flush=True)
    old_sigint = signal.signal(signal.SIGINT, _signal_handler)
    old_sigterm = signal.signal(signal.SIGTERM, _signal_handler)
    returncode = 1
    try:
        if args.mode == "focused":
            returncode = _run_focused(args, run, ledger)
        else:
            returncode = _run_full(run, ledger)
    except RunnerUsageError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        returncode = 2
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        returncode = 2
    except RunnerSignal as exc:
        print(f"received signal {exc.signum}; cleaning owned resources", file=sys.stderr, flush=True)
        returncode = 128 + exc.signum
    finally:
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
        cleanup_ok = _report_cleanup(ledger.cleanup())
        try:
            run.cleanup()
        except OSError as exc:
            print(f"cleanup residual: run root {run.root}: {exc}", file=sys.stderr, flush=True)
            cleanup_ok = False
        if not cleanup_ok and returncode == 0:
            returncode = 1
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
