from __future__ import annotations

import os
from pathlib import Path
import json
import signal
import socket
import subprocess
import sys
import time

import pytest

from runtime_kernel import process_identity
from tests.support.environment import RunEnvironment
from tests.support.paths import REPO_ROOT
from tests.support.processes import (
    CleanupReport,
    ResourceLedger,
    ResourceMonitor,
    SystemLock,
    process_start_identity,
    run_process,
)


def _public_runner_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def test_run_environment_isolates_host_paths_outside_repository(monkeypatch) -> None:
    monkeypatch.setenv("BUDDYSWITCH_HOME", "/host/must-not-leak")
    monkeypatch.setenv("BUDDYSWITCH_INSTANCE_ROOT", "/host/instance-must-not-leak")
    monkeypatch.setenv("BUDDYSWITCH_PYTHON", sys.executable)
    run = RunEnvironment.create()
    try:
        assert run.root.parent != REPO_ROOT
        assert not run.root.is_relative_to(REPO_ROOT)
        assert run.ledger_path == run.root / "owned-resources.jsonl"
        assert run.ledger_path.is_file()
        assert run.run_id

        expected = {
            "HOME": run.root / "home",
            "CODEX_HOME": run.root / "codex-home",
            "XDG_CACHE_HOME": run.root / "xdg" / "cache",
            "XDG_CONFIG_HOME": run.root / "xdg" / "config",
            "XDG_DATA_HOME": run.root / "xdg" / "data",
            "XDG_STATE_HOME": run.root / "xdg" / "state",
            "TMPDIR": run.root / "tmp",
            "BUDDYSWITCH_STATE_ROOT": run.root / "state",
            "BUDDYSWITCH_SHARED_ROOT": run.root / "shared",
            "BUDDYSWITCH_TEST_RUN_ROOT": run.root,
            "BUDDYSWITCH_TEST_RESOURCE_LEDGER": run.ledger_path,
        }
        for name, path in expected.items():
            assert run.environ[name] == str(path)
            assert path == run.root or path.is_relative_to(run.root)
        assert run.environ["BUDDYSWITCH_TEST_RUN_ID"] == run.run_id
        assert run.environ["BUDDYSWITCH_TEST_RUNNER_PID"] == str(os.getpid())
        assert "BUDDYSWITCH_HOME" not in run.environ
        assert "BUDDYSWITCH_INSTANCE_ROOT" not in run.environ
        assert run.environ["BUDDYSWITCH_PYTHON"] == sys.executable
    finally:
        run.cleanup()

    assert not run.root.exists()


def test_run_environment_leaves_space_for_unix_socket_paths() -> None:
    run = RunEnvironment.create()
    try:
        representative_socket = run.root / "tmp" / "tmpabcdefgh" / "app-server.sock"
        assert len(os.fsencode(representative_socket)) < 100
    finally:
        run.cleanup()


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin identity precision")
def test_process_identity_uses_darwin_kernel_start_timestamp() -> None:
    process = ResourceLedger.from_environment().start_process(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        identity = process_start_identity(process.pid)

        assert identity is not None
        assert identity.startswith("darwin:")
        seconds, microseconds = identity.removeprefix("darwin:").split(":")
        assert seconds.isdigit()
        assert microseconds.isdigit()
    finally:
        process.terminate()
        process.wait(timeout=2)


def test_ledger_records_exact_process_identity_and_cleans_only_owned_resources() -> None:
    run = RunEnvironment.create()
    sibling = run.root.parent / f"{run.root.name}-not-owned"
    sibling.mkdir()
    process: subprocess.Popen[str] | None = None
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        owned_path = run.root / "owned" / "service.sock"
        owned_path.parent.mkdir()
        owned_path.write_text("owned\n", encoding="utf-8")
        ledger.register_path(owned_path, path_type="socket")
        process = ledger.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        records = ledger.records()
        process_record = next(record for record in records if record["kind"] == "process")
        assert process_record["pid"] == process.pid
        assert process_record["pgid"] == os.getpgid(process.pid)
        assert process_record["start_identity"] == process_start_identity(process.pid)
        assert process_record["cleanup_strategy"] == "terminate_owned_pgid"
        assert process_record["command"] == [
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
        ]

        report = ledger.cleanup(term_timeout=1.0, kill_timeout=1.0)
        process.wait(timeout=2)
        assert report.residuals == []
        assert process.pid in report.terminated_pids
        assert not owned_path.exists()
        assert sibling.is_dir()
    finally:
        if process is not None and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=2)
        sibling.rmdir()
        if run.root.exists():
            run.cleanup()


def test_cleanup_removes_owned_unix_socket_path() -> None:
    run = RunEnvironment.create()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        socket_path = run.root / "owned.sock"
        listener.bind(str(socket_path))
        listener.close()
        ledger.register_path(socket_path, path_type="socket")

        report = ledger.cleanup()

        assert report.residuals == []
        assert not socket_path.exists()
    finally:
        listener.close()
        if run.root.exists():
            run.cleanup()


def test_cleanup_refuses_stale_process_identity_without_signalling_live_process() -> None:
    run = RunEnvironment.create()
    unrelated = ResourceLedger.from_environment().start_process(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        ledger.register_process(
            pid=unrelated.pid,
            pgid=os.getpgid(unrelated.pid),
            start_identity=process_start_identity(unrelated.pid) + "-stale",
            command=["unrelated"],
            cleanup_strategy="terminate_owned_pgid",
            cleanup_args={},
        )

        report = ledger.cleanup(term_timeout=0.1, kill_timeout=0.1)

        assert unrelated.poll() is None
        assert report.identity_mismatches == [unrelated.pid]
        assert report.residuals == []
    finally:
        if unrelated.poll() is None:
            os.killpg(os.getpgid(unrelated.pid), signal.SIGKILL)
        unrelated.wait(timeout=2)
        run.cleanup()


def test_targeted_cleanup_refuses_process_missing_from_exact_ledger() -> None:
    owner_run = RunEnvironment.create()
    other_run = RunEnvironment.create()
    process: subprocess.Popen[str] | None = None
    try:
        owner = ResourceLedger(owner_run.ledger_path, owner_run.root)
        other = ResourceLedger(other_run.ledger_path, other_run.root)
        process = owner.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        identity = process_start_identity(process.pid)
        assert identity is not None

        refused = other.cleanup_registered_process(process.pid)

        assert refused.residuals == [
            f"refused process missing from exact ledger: pid={process.pid}"
        ]
        assert process_start_identity(process.pid) == identity

        cleaned = owner.cleanup_registered_process(process.pid)
        process.wait(timeout=2)
        assert cleaned.residuals == []
        assert cleaned.identity_mismatches == []
        assert process.pid in cleaned.terminated_pids
    finally:
        if process is not None and process.poll() is None:
            ResourceLedger(owner_run.ledger_path, owner_run.root).cleanup()
            process.wait(timeout=2)
        if owner_run.root.exists():
            owner_run.cleanup()
        if other_run.root.exists():
            other_run.cleanup()


def test_serialized_ledger_cleans_detached_service_after_owner_is_killed() -> None:
    run = RunEnvironment.create()
    owner: subprocess.Popen[str] | None = None
    detached_pid = 0
    try:
        pid_path = run.root / "detached.pid"
        owner_code = "\n".join(
            [
                "import subprocess, sys, time",
                "from pathlib import Path",
                "from tests.support.processes import ResourceLedger",
                "ledger = ResourceLedger(Path(sys.argv[1]), Path(sys.argv[2]))",
                "child = ledger.start_process([sys.executable, '-c', 'import time; time.sleep(60)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
                "Path(sys.argv[3]).write_text(str(child.pid), encoding='utf-8')",
                "time.sleep(60)",
            ]
        )
        owner = ResourceLedger.from_environment().start_process(
            [
                sys.executable,
                "-c",
                owner_code,
                str(run.ledger_path),
                str(run.root),
                str(pid_path),
            ],
            cwd=REPO_ROOT,
            env=run.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not pid_path.exists():
            time.sleep(0.02)
        assert pid_path.exists()
        detached_pid = int(pid_path.read_text(encoding="utf-8"))

        owner.terminate()
        owner.wait(timeout=2)
        report = ResourceLedger(run.ledger_path, run.root).cleanup(
            term_timeout=1.0,
            kill_timeout=1.0,
        )

        assert report.residuals == []
        assert detached_pid in report.terminated_pids
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                os.kill(detached_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            pytest.fail(f"detached PID {detached_pid} was not reaped")
    finally:
        if owner is not None and owner.poll() is None:
            os.killpg(os.getpgid(owner.pid), signal.SIGKILL)
            owner.wait(timeout=2)
        if detached_pid:
            try:
                os.kill(detached_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if run.root.exists():
            run.cleanup()


def test_descriptor_reconciliation_captures_replacement_process_identity() -> None:
    run = RunEnvironment.create()
    first: subprocess.Popen[str] | None = None
    replacement: subprocess.Popen[str] | None = None
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        pid_file = run.root / "replaceable-service.pid"
        descriptor_id = ledger.register_process_descriptor(
            pid_file=pid_file,
            cleanup_strategy="terminate_owned_pgid",
            cleanup_args={},
            command=[sys.executable, "replaceable-service"],
            owned_paths={"pid": pid_file},
        )

        first = ledger.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        from runtime_kernel import process_identity

        process_identity.write_record(pid_file, first.pid)
        ledger.reconcile_descriptors()
        first.terminate()
        first.wait(timeout=2)

        replacement = ledger.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        process_identity.write_record(pid_file, replacement.pid)
        ledger.reconcile_descriptors()

        captured = [
            int(record["pid"])
            for record in ledger.records()
            if record.get("kind") == "process"
            and record.get("descriptor_id") == descriptor_id
        ]
        assert captured == [first.pid, replacement.pid]
    finally:
        if run.root.exists():
            ResourceLedger(run.ledger_path, run.root).cleanup()
            run.cleanup()


def test_descriptor_reconciliation_refuses_mismatched_identity_record() -> None:
    from runtime_kernel import process_identity

    run = RunEnvironment.create()
    unrelated: subprocess.Popen[str] | None = None
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        pid_file = run.root / "stale-service.pid"
        descriptor_id = ledger.register_process_descriptor(
            pid_file=pid_file,
            cleanup_strategy="terminate_owned_pgid",
            cleanup_args={},
            command=["stale-service"],
            owned_paths={"pid": pid_file},
        )
        unrelated = ledger.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid_file.write_text(f"{unrelated.pid}\n", encoding="utf-8")
        process_identity.identity_file(pid_file).write_text(
            json.dumps(
                {
                    "pid": unrelated.pid,
                    "start_identity": "stale-start-identity",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        ledger.reconcile_descriptors()

        captured = [
            record
            for record in ledger.records()
            if record.get("kind") == "process"
            and record.get("descriptor_id") == descriptor_id
        ]
        assert captured == []
        assert unrelated.poll() is None
    finally:
        if run.root.exists():
            ResourceLedger(run.ledger_path, run.root).cleanup()
            run.cleanup()


def test_cleanup_refuses_changed_process_group(monkeypatch) -> None:
    run = RunEnvironment.create()
    process: subprocess.Popen[str] | None = None
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        process = ledger.start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        record = next(
            record for record in ledger.records() if record.get("kind") == "process"
        )
        record["pgid"] = int(record["pgid"]) + 1
        attempted: list[tuple[int, int]] = []
        monkeypatch.setattr(
            os,
            "killpg",
            lambda pgid, signum: attempted.append((pgid, signum)),
        )

        report = CleanupReport()
        ledger._cleanup_process(
            record,
            report,
            term_timeout=0.1,
            kill_timeout=0.1,
        )

        assert attempted == []
        assert report.residuals == [
            f"refused changed process group for PID {process.pid}: "
            f"recorded={record['pgid']} current={os.getpgid(process.pid)}"
        ]
        assert process.poll() is None
    finally:
        monkeypatch.undo()
        if process is not None and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=2)
        if run.root.exists():
            run.cleanup()


def test_cleanup_escalates_from_term_to_kill_and_reaps_owned_child() -> None:
    run = RunEnvironment.create()
    process: subprocess.Popen[str] | None = None
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        process = ledger.start_process(
            [
                sys.executable,
                "-c",
                "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.05)

        report = ledger.cleanup(term_timeout=0.1, kill_timeout=1.0)
        process.wait(timeout=2)

        assert process.pid in report.terminated_pids
        assert process.pid in report.killed_pids
        assert report.residuals == []
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=2)
        run.cleanup()


def test_monitor_persists_descriptor_identity_before_owner_process_exits() -> None:
    run = RunEnvironment.create()
    child: subprocess.Popen[str] | None = None
    monitor: ResourceMonitor | None = None
    try:
        ledger = ResourceLedger(run.ledger_path, run.root)
        pid_path = run.root / "service" / "daemon.pid"
        socket_path = run.root / "service" / "daemon.sock"
        descriptor_id = ledger.register_process_descriptor(
            pid_file=pid_path,
            cleanup_strategy="terminate_owned_pgid",
            cleanup_args={},
            command=["detached-service"],
            owned_paths={
                "pid": pid_path,
                "pid_identity": process_identity.identity_file(pid_path),
                "socket": socket_path,
            },
        )
        monitor = ResourceMonitor(ledger, poll_interval=0.01)
        monitor.start()
        child = ResourceLedger.from_environment().start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        pid_path.parent.mkdir(parents=True)
        process_identity.write_record(pid_path, child.pid)

        deadline = time.monotonic() + 2.0
        process_record: dict[str, object] | None = None
        while time.monotonic() < deadline:
            process_record = next(
                (
                    record
                    for record in ledger.records()
                    if record.get("descriptor_id") == descriptor_id
                    and record.get("kind") == "process"
                ),
                None,
            )
            if process_record is not None:
                break
            time.sleep(0.01)

        assert process_record is not None
        assert process_record["pid"] == child.pid
        assert process_record["pgid"] == os.getpgid(child.pid)
        assert process_record["start_identity"] == process_start_identity(child.pid)
        assert process_record["cleanup_strategy"] == "terminate_owned_pgid"

        monitor.stop()
        monitor = None
        report = ledger.cleanup(term_timeout=1.0, kill_timeout=1.0)
        child.wait(timeout=2)
        assert report.residuals == []
        assert not pid_path.exists()
        assert not socket_path.exists()
    finally:
        if monitor is not None:
            monitor.stop()
        if child is not None and child.poll() is None:
            os.killpg(os.getpgid(child.pid), signal.SIGKILL)
            child.wait(timeout=2)
        if run.root.exists():
            run.cleanup()


def test_serialized_central_daemon_strategy_runs_normal_stop_before_group_fallback(
    monkeypatch,
) -> None:
    import central_daemon
    import central_daemon_core

    run = RunEnvironment.create()
    pid = 0
    try:
        monkeypatch.setenv("BUDDYSWITCH_PYTHON", sys.executable)
        ledger = ResourceLedger(run.ledger_path, run.root)
        paths = central_daemon_core.central_daemon_paths(run.root / "shared")
        ledger.register_process_descriptor(
            pid_file=paths.pid_file,
            cleanup_strategy="central_daemon_stop",
            cleanup_args={"shared_root": str(paths.shared_root)},
            command=["central-daemon"],
            owned_paths={
                "pid": paths.pid_file,
                "pid_identity": paths.pid_identity_file,
                "socket": paths.socket_path,
            },
        )
        started = central_daemon.start_central_daemon(paths)
        pid = int(started["pid"])
        ledger.reconcile_descriptors()

        report = ledger.cleanup(term_timeout=1.0, kill_timeout=1.0)

        assert report.residuals == []
        assert pid not in report.terminated_pids
        assert not paths.pid_file.exists()
        assert not paths.pid_identity_file.exists()
        assert not paths.socket_path.exists()
    finally:
        if pid:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        if run.root.exists():
            run.cleanup()


def test_common_dir_lock_is_shared_by_two_git_worktrees() -> None:
    run = RunEnvironment.create()
    waiter: subprocess.Popen[str] | None = None
    repo = run.root / "lock-source"
    worktree = run.root / "lock-worktree"
    holder: SystemLock | None = None
    try:
        run_process(["git", "init", "-q", str(repo)], check=True)
        run_process(
            ["git", "-C", str(repo), "config", "user.email", "tests@buddyswitch.local"],
            check=True,
        )
        run_process(
            ["git", "-C", str(repo), "config", "user.name", "BuddySwitch Tests"],
            check=True,
        )
        (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        run_process(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        run_process(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
        run_process(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), "HEAD"],
            stdout=subprocess.DEVNULL,
            check=True,
        )

        holder = SystemLock.for_repo(repo)
        holder.acquire(timeout=0.2)
        inode = holder.path.stat().st_ino
        ready_path = run.root / "waiter-opened"
        acquired_path = run.root / "waiter-acquired"
        waiter_code = "\n".join(
            [
                "import sys",
                "from pathlib import Path",
                "from tests.support.processes import SystemLock",
                "lock = SystemLock.for_repo(Path(sys.argv[1]))",
                "Path(sys.argv[2]).write_text('opened', encoding='utf-8')",
                "lock.acquire(timeout=5.0)",
                "Path(sys.argv[3]).write_text(str(lock.path.stat().st_ino), encoding='utf-8')",
                "lock.release()",
            ]
        )
        waiter = ResourceLedger.from_environment().start_process(
            [
                sys.executable,
                "-c",
                waiter_code,
                str(worktree),
                str(ready_path),
                str(acquired_path),
            ],
            cwd=worktree,
            env=run.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not ready_path.exists():
            time.sleep(0.02)
        assert ready_path.exists()
        assert not acquired_path.exists()

        holder.release()
        waiter.wait(timeout=5)

        assert waiter.returncode == 0
        assert int(acquired_path.read_text(encoding="utf-8")) == inode
        assert holder.path.exists()
        assert holder.path.stat().st_ino == inode
    finally:
        if holder is not None:
            holder.release()
        if waiter is not None and waiter.poll() is None:
            os.killpg(os.getpgid(waiter.pid), signal.SIGKILL)
            waiter.wait(timeout=2)
        if worktree.exists():
            run_process(
                ["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        run.cleanup()


def test_serialized_cleanup_action_removes_exact_git_worktree() -> None:
    run = RunEnvironment.create()
    repo = run.root / "source-repo"
    worktree = run.root / "owned-worktree"
    try:
        run_process(["git", "init", "-q", str(repo)], check=True)
        run_process(
            ["git", "-C", str(repo), "config", "user.email", "tests@buddyswitch.local"],
            check=True,
        )
        run_process(
            ["git", "-C", str(repo), "config", "user.name", "BuddySwitch Tests"],
            check=True,
        )
        (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        run_process(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        run_process(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
        run_process(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), "HEAD"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        ledger = ResourceLedger(run.ledger_path, run.root)
        ledger.register_cleanup_action(
            cleanup_strategy="git_worktree_remove",
            cleanup_args={"repo_root": str(repo), "worktree": str(worktree)},
        )

        report = ledger.cleanup()

        assert report.residuals == []
        assert not worktree.exists()
        listed = run_process(
            ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        assert str(worktree) not in listed
    finally:
        if worktree.exists():
            run_process(
                ["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        run.cleanup()


def test_focused_runner_executes_only_the_explicit_python_nodeid() -> None:
    target = (
        "tests/unit/launcher/test_cli_contract.py::CliContractTests::"
        "test_success_envelope_has_stable_machine_keys"
    )

    completed = run_process(
        [str(REPO_ROOT / "buddyswitch-test"), "focused", target],
        cwd=REPO_ROOT,
        env=_public_runner_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stdout
    assert target in completed.stdout
    assert "1 passed" in completed.stdout
    assert "test_failure_envelope_has_stable_error_keys" not in completed.stdout


def test_invalid_focused_target_still_cleans_created_run_context() -> None:
    completed = run_process(
        [
            str(REPO_ROOT / "buddyswitch-test"),
            "focused",
            "tests/does-not-exist.py",
        ],
        cwd=REPO_ROOT,
        env=_public_runner_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=15,
    )

    assert completed.returncode == 2
    assert "focused target does not exist" in completed.stdout
    root_line = next(
        line for line in completed.stdout.splitlines() if line.startswith("run root: ")
    )
    run_root = Path(root_line.removeprefix("run root: "))
    assert not run_root.exists()


def _runner_process_result(target: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    completed = run_process(
        [str(REPO_ROOT / "buddyswitch-test"), "focused", target],
        cwd=REPO_ROOT,
        env=_public_runner_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=15,
    )
    root_line = next(
        line for line in completed.stdout.splitlines() if line.startswith("run root: ")
    )
    return completed, Path(root_line.removeprefix("run root: "))


def test_failed_pytest_still_cleans_detached_service_and_run_root() -> None:
    completed, run_root = _runner_process_result(
        "tests/integration/support/runner_failure_fixture.py"
    )

    assert completed.returncode == 1, completed.stdout
    assert "intentional runner cleanup failure fixture" in completed.stdout
    assert not run_root.exists()


def test_cleanup_strategy_residual_fails_otherwise_passing_runner() -> None:
    completed, run_root = _runner_process_result(
        "tests/integration/support/runner_residual_fixture.py"
    )

    assert completed.returncode == 1, completed.stdout
    assert "1 passed" in completed.stdout
    assert "cleanup residual:" in completed.stdout
    assert "central_daemon_stop" in completed.stdout
    assert not run_root.exists()


def test_focused_javascript_name_pattern_executes_only_matching_case() -> None:
    target = "tests/unit/web/markdown_renderer.test.js"
    completed = run_process(
        [
            str(REPO_ROOT / "buddyswitch-test"),
            "focused",
            target,
            "--node-name-pattern",
            "^renders CommonMark headings and paragraphs$",
        ],
        cwd=REPO_ROOT,
        env=_public_runner_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stdout
    assert "renders CommonMark headings and paragraphs" in completed.stdout
    assert "pass 1" in completed.stdout
    assert "fail 0" in completed.stdout
    assert "sanitizer is always invoked before returning html" not in completed.stdout


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_runner_cleans_pytest_child_detached_service_and_run_paths(
    signum: int,
) -> None:
    runner = ResourceLedger.from_environment().start_process(
        [
            str(REPO_ROOT / "buddyswitch-test"),
            "focused",
            "tests/integration/support/runner_signal_fixture.py",
        ],
        cwd=REPO_ROOT,
        env=_public_runner_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    assert runner.stdout is not None
    output_lines: list[str] = []
    run_root: Path | None = None
    detached_pid = 0
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and run_root is None:
            line = runner.stdout.readline()
            if line:
                output_lines.append(line)
                if line.startswith("run root: "):
                    run_root = Path(line.removeprefix("run root: ").strip())
            if runner.poll() is not None:
                break
        assert run_root is not None, "".join(output_lines)
        pid_path = run_root / "detached-service.pid"
        while time.monotonic() < deadline and not pid_path.exists():
            if runner.poll() is not None:
                break
            time.sleep(0.02)
        if pid_path.exists():
            detached_pid = int(pid_path.read_text(encoding="utf-8"))
        assert detached_pid > 0, "".join(output_lines)
        ledger_path = run_root / "owned-resources.jsonl"
        captured = False
        while time.monotonic() < deadline:
            captured = any(
                json.loads(line).get("kind") == "process"
                and json.loads(line).get("pid") == detached_pid
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            if captured:
                break
            time.sleep(0.02)
        assert captured, ledger_path.read_text(encoding="utf-8")

        os.kill(runner.pid, signum)
        remaining, _ = runner.communicate(timeout=10)
        output_lines.append(remaining)

        assert runner.returncode == 128 + signum, "".join(output_lines)
        assert "received signal" in "".join(output_lines)
        assert not run_root.exists()
        with pytest.raises(ProcessLookupError):
            os.kill(detached_pid, 0)
    finally:
        if runner.poll() is None:
            runner.terminate()
            try:
                runner.wait(timeout=5)
            except subprocess.TimeoutExpired:
                runner.kill()
                runner.wait(timeout=2)
        if detached_pid:
            try:
                os.kill(detached_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_sigterm_runner_cleans_public_instance_start_detached_services_and_worktrees() -> None:
    runner = ResourceLedger.from_environment().start_process(
        [
            str(REPO_ROOT / "buddyswitch-test"),
            "focused",
            "tests/system/instance_lifecycle/runner_instance_start_fixture.py",
        ],
        cwd=REPO_ROOT,
        env=_public_runner_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert runner.stdout is not None
    output: list[str] = []
    run_root: Path | None = None
    ready: dict[str, object] | None = None
    try:
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline and run_root is None:
            line = runner.stdout.readline()
            if line:
                output.append(line)
                if line.startswith("run root: "):
                    run_root = Path(line.removeprefix("run root: ").strip())
            if runner.poll() is not None:
                break
        assert run_root is not None, "".join(output)
        ready_path = run_root / "instance-start-ready.json"
        while time.monotonic() < deadline and not ready_path.exists():
            if runner.poll() is not None:
                break
            time.sleep(0.05)
        if ready_path.exists():
            ready = json.loads(ready_path.read_text(encoding="utf-8"))
        if ready is None:
            diagnostics = []
            for name in (
                "instance-start-debug.log",
                "instance-start-launcher.stdout",
                "instance-start-launcher.stderr",
            ):
                path = run_root / name
                if path.exists():
                    diagnostics.append(f"\n--- {name} ---\n{path.read_text(encoding='utf-8')}")
            if runner.poll() is not None:
                remaining, _ = runner.communicate()
                output.append(remaining)
            pytest_output = "".join(output)
            raise AssertionError(pytest_output + "".join(diagnostics))
        pids = dict(ready["pids"])
        assert set(pids) == {
            "central",
            "app_server",
            "runtime_broker",
            "instance_daemon",
        }
        assert Path(str(ready["browser_ttl_config"])).read_text(encoding="utf-8") == ready["browser_ttl_config_text"]

        os.kill(runner.pid, signal.SIGTERM)
        remaining, _ = runner.communicate(timeout=20)
        output.append(remaining)

        assert runner.returncode == 128 + signal.SIGTERM, "".join(output)
        assert not run_root.exists()
        for pid in pids.values():
            with pytest.raises(ProcessLookupError):
                os.kill(int(pid), 0)
        worktree_listing = run_process(
            ["git", "-C", str(REPO_ROOT), "worktree", "list", "--porcelain"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        for worktree in ready["worktrees"]:
            assert str(worktree) not in worktree_listing
    finally:
        if runner.poll() is None:
            runner.terminate()
            try:
                runner.wait(timeout=10)
            except subprocess.TimeoutExpired:
                runner.kill()
                runner.wait(timeout=2)
