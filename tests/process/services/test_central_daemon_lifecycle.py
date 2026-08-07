from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from buddyswitch.launcher import central_daemon
from buddyswitch.launcher import central_daemon_core
import buddyswitch.foundation.process_runtime.process_identity as process_identity
from tests.support.processes import ResourceLedger


def _wait_pid_gone(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            waited, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            waited = 0
        if waited == pid:
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.02)
    return False


def test_stop_refuses_stale_pid_identity_without_signalling_unrelated_process(
    tmp_path: Path,
) -> None:
    unrelated = ResourceLedger.from_environment().start_process(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    paths = central_daemon_core.central_daemon_paths(tmp_path / "shared")
    try:
        paths.run_dir.mkdir(parents=True)
        paths.pid_file.write_text(f"{unrelated.pid}\n", encoding="utf-8")
        paths.pid_identity_file.write_text("stale-start-identity\n", encoding="utf-8")

        result = central_daemon.stop_central_daemon(paths)

        assert unrelated.poll() is None
        assert result["terminated"] is False
        assert result["identity_mismatch"] is True
        assert not paths.pid_file.exists()
        assert not paths.pid_identity_file.exists()
    finally:
        if unrelated.poll() is None:
            os.killpg(os.getpgid(unrelated.pid), signal.SIGKILL)
        unrelated.wait(timeout=2)


def test_start_and_normal_stop_share_exact_identity_and_remove_runtime_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("BUDDYSWITCH_PYTHON", sys.executable)
    paths = central_daemon_core.central_daemon_paths(tmp_path / "shared")
    ledger = ResourceLedger.from_environment()
    ledger.register_process_descriptor(
        pid_file=paths.pid_file,
        cleanup_strategy="central_daemon_stop",
        cleanup_args={"shared_root": str(paths.shared_root)},
        command=["central-daemon", "serve"],
        owned_paths={
            "pid": paths.pid_file,
            "pid_identity": paths.pid_identity_file,
            "socket": paths.socket_path,
        },
    )
    pid = 0
    try:
        started = central_daemon.start_central_daemon(paths)
        pid = int(started["pid"])
        ledger.reconcile_descriptors()
        record = process_identity.read_record(paths.pid_file)
        assert record is not None
        assert record.pid == pid
        assert process_identity.matches(record)

        stopped = central_daemon.stop_central_daemon(paths)

        assert stopped["terminated"] is True
        assert stopped["identity_mismatch"] is False
        assert _wait_pid_gone(pid)
        assert not paths.pid_file.exists()
        assert not paths.pid_identity_file.exists()
        assert not paths.socket_path.exists()
    finally:
        if pid:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            _wait_pid_gone(pid, timeout=2.0)


def test_sigterm_service_uses_same_cleanup_owner_for_pid_identity_and_socket(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("BUDDYSWITCH_PYTHON", sys.executable)
    paths = central_daemon_core.central_daemon_paths(tmp_path / "shared")
    ledger = ResourceLedger.from_environment()
    ledger.register_process_descriptor(
        pid_file=paths.pid_file,
        cleanup_strategy="central_daemon_stop",
        cleanup_args={"shared_root": str(paths.shared_root)},
        command=["central-daemon", "serve"],
        owned_paths={
            "pid": paths.pid_file,
            "pid_identity": paths.pid_identity_file,
            "socket": paths.socket_path,
        },
    )
    started = central_daemon.start_central_daemon(paths)
    pid = int(started["pid"])
    ledger.reconcile_descriptors()
    try:
        os.kill(pid, signal.SIGTERM)

        assert _wait_pid_gone(pid)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and any(
            path.exists()
            for path in (paths.pid_file, paths.pid_identity_file, paths.socket_path)
        ):
            time.sleep(0.02)
        assert not paths.pid_file.exists()
        assert not paths.pid_identity_file.exists()
        assert not paths.socket_path.exists()
    finally:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        _wait_pid_gone(pid, timeout=2.0)
