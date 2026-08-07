from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from buddyswitch.launcher import app_server
from buddyswitch.foundation.browser_runtime import runtime as browser_runtime_manager
from buddyswitch.launcher import daemon_core
import buddyswitch.foundation.process_runtime.process_identity as process_identity
from buddyswitch.runtime_kernel import lifecycle
from tests.support.processes import ResourceLedger


def _unrelated_process() -> subprocess.Popen[str]:
    return ResourceLedger.from_environment().start_process(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _write_stale_record(pid_file: Path, pid: int) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{pid}\n", encoding="utf-8")
    process_identity.identity_file(pid_file).write_text(
        json.dumps({"pid": pid, "start_identity": "stale-start-identity"}) + "\n",
        encoding="utf-8",
    )


def _kill_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    process.wait(timeout=2)


def test_app_server_stop_refuses_stale_pid_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    unrelated = _unrelated_process()
    instance_root = tmp_path / "instance"
    socket_path = app_server.default_socket_path(instance_root)
    pid_path = app_server.pid_file(instance_root)
    marker_path = app_server.marker_file(instance_root)
    log_path = app_server.log_file(instance_root)
    _write_stale_record(pid_path, unrelated.pid)
    real_kill = os.kill
    real_killpg = os.killpg
    attempted_signals: list[int] = []

    def guarded_kill(pid: int, signum: int) -> None:
        if signum == 0:
            real_kill(pid, signum)
            return
        attempted_signals.append(signum)

    def guarded_killpg(pgid: int, signum: int) -> None:
        if signum == 0:
            real_killpg(pgid, signum)
            return
        attempted_signals.append(signum)

    monkeypatch.setattr(app_server.os, "kill", guarded_kill)
    monkeypatch.setattr(app_server.os, "killpg", guarded_killpg)
    try:
        result = app_server.stop_app_server(
            socket_path,
            pid_path,
            marker_path,
            log_path,
        )
        monkeypatch.undo()

        assert attempted_signals == []
        assert unrelated.poll() is None
        assert result["terminated"] is False
        assert result["identity_mismatch"] is True
        assert not pid_path.exists()
        assert not process_identity.identity_file(pid_path).exists()
    finally:
        monkeypatch.undo()
        _kill_process(unrelated)


def test_runtime_broker_stop_refuses_stale_pid_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    unrelated = _unrelated_process()
    paths = lifecycle.BrokerPaths(
        socket_path=tmp_path / "runtime-broker.sock",
        pid_file=tmp_path / "runtime-broker.pid",
        marker_file=tmp_path / "runtime-broker.socket",
        log_file=tmp_path / "runtime-broker.log",
    )
    _write_stale_record(paths.pid_file, unrelated.pid)
    real_kill = os.kill
    attempted_signals: list[int] = []

    def guarded_kill(pid: int, signum: int) -> None:
        if signum == 0:
            real_kill(pid, signum)
            return
        attempted_signals.append(signum)

    monkeypatch.setattr(lifecycle.os, "kill", guarded_kill)
    try:
        result = lifecycle.stop_broker(paths)
        monkeypatch.undo()

        assert attempted_signals == []
        assert unrelated.poll() is None
        assert result["stopped"] is False
        assert result["identity_mismatch"] is True
        assert not paths.pid_file.exists()
        assert not process_identity.identity_file(paths.pid_file).exists()
    finally:
        monkeypatch.undo()
        _kill_process(unrelated)


def test_instance_daemon_stop_refuses_stale_pid_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    unrelated = _unrelated_process()
    instance_root = tmp_path / "instances" / "act-dev-stale000001"
    workspace_dir = instance_root / "workspace"
    workspace_dir.mkdir(parents=True)
    instance_json = instance_root / "instance.json"
    instance_json.write_text(
        json.dumps(
            {
                "actor_id": "act-dev-stale000001",
                "role": "dev",
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(workspace_dir),
                "thread_id": "thr-stale",
                "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
            }
        ),
        encoding="utf-8",
    )
    pid_path = daemon_core.daemon_pid_file(instance_root)
    _write_stale_record(pid_path, unrelated.pid)
    real_kill = os.kill
    attempted_signals: list[int] = []

    def guarded_kill(pid: int, signum: int) -> None:
        if signum == 0:
            real_kill(pid, signum)
            return
        attempted_signals.append(signum)

    monkeypatch.setattr(daemon_core.os, "kill", guarded_kill)
    try:
        result = daemon_core.stop_daemon(instance_json)
        monkeypatch.undo()

        assert attempted_signals == []
        assert unrelated.poll() is None
        assert result["terminated"] is False
        assert result["identity_mismatch"] is True
        assert not pid_path.exists()
        assert not process_identity.identity_file(pid_path).exists()
    finally:
        monkeypatch.undo()
        _kill_process(unrelated)


def test_browser_stop_refuses_stale_pid_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance_root = tmp_path / "instances" / "act-dev-browser-stale"
    profile_dir = instance_root / "browser" / "profile"
    profile_dir.mkdir(parents=True)
    instance_json = instance_root / "instance.json"
    instance_json.write_text(
        json.dumps(
            {
                "actor_id": "act-dev-browser-stale",
                "role": "dev",
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(instance_root / "workspace"),
                "thread_id": "thr-browser-stale",
                "browser_port": None,
            }
        ),
        encoding="utf-8",
    )
    unrelated = ResourceLedger.from_environment().start_process(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            f"--user-data-dir={profile_dir}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    pid_file = instance_root / "browser" / "chrome.pid"
    _write_stale_record(pid_file, unrelated.pid)
    real_kill = os.kill
    real_killpg = os.killpg
    attempted_signals: list[int] = []

    def guarded_kill(pid: int, signum: int) -> None:
        if signum == 0:
            real_kill(pid, signum)
            return
        attempted_signals.append(signum)

    def guarded_killpg(pgid: int, signum: int) -> None:
        if signum == 0:
            real_killpg(pgid, signum)
            return
        attempted_signals.append(signum)

    monkeypatch.setattr(browser_runtime_manager.os, "kill", guarded_kill)
    monkeypatch.setattr(browser_runtime_manager.os, "killpg", guarded_killpg)
    try:
        result = browser_runtime_manager.stop(
            instance_root=instance_root,
            actor_id="act-dev-browser-stale",
        )
        monkeypatch.undo()

        assert attempted_signals == []
        assert unrelated.poll() is None
        assert result["ok"] is True
        assert result["ownership"] == "stale_state"
        assert not pid_file.exists()
        assert not process_identity.identity_file(pid_file).exists()
    finally:
        monkeypatch.undo()
        _kill_process(unrelated)
