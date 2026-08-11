from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

import buddyswitch.foundation.app_server.runtime as app_server
from buddyswitch.foundation.browser_runtime import runtime as browser_runtime_manager
import pytest
import buddyswitch.foundation.process_runtime.process_identity as process_identity
from tests.support.python import executable_python_source
from tests.support.network import open_loopback_listener
from tests.support.cli import write_executable


def _write_executable(path: Path, source: str) -> None:
    write_executable(path, executable_python_source(source))


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_app_server_early_exit_removes_pid_identity_socket_and_marker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance_root = tmp_path / "instance"
    instance_root.mkdir()
    fake_codex = tmp_path / "fake-codex"
    _write_executable(fake_codex, "import time\ntime.sleep(60)\n")
    socket_path = app_server.effective_socket_path(
        "act-dev-app-failure",
        instance_root,
        app_server.marker_file(instance_root),
    )
    pid_path = app_server.pid_file(instance_root)
    real_popen = subprocess.Popen
    real_write_record = process_identity.write_record
    spawned_codex: list[subprocess.Popen[str]] = []

    def capture_codex_process(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        command = args[0] if args else kwargs["args"]
        if command[0] == str(fake_codex):
            spawned_codex.append(process)
        return process

    def record_identity_then_stop_child(
        record_path: Path,
        pid: int,
    ) -> process_identity.RecordedProcess:
        record = real_write_record(record_path, pid)
        assert record_path == pid_path
        assert len(spawned_codex) == 1
        process = spawned_codex[0]
        assert process.pid == pid
        assert process_identity.read_record(record_path) == record
        process.terminate()
        process.wait(timeout=2)
        return record

    monkeypatch.setattr(app_server.subprocess, "Popen", capture_codex_process)
    monkeypatch.setattr(
        app_server.process_identity,
        "write_record",
        record_identity_then_stop_child,
    )

    try:
        with pytest.raises(app_server.AppServerUnavailableError):
            app_server.ensure_app_server(
                "act-dev-app-failure",
                instance_root,
                str(fake_codex),
                startup_timeout_seconds=1.0,
            )
    finally:
        for process in spawned_codex:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)

    assert len(spawned_codex) == 1
    assert spawned_codex[0].poll() is not None
    assert not pid_path.exists()
    assert not process_identity.identity_file(pid_path).exists()
    assert not socket_path.exists()
    assert not app_server.marker_file(instance_root).exists()


def test_browser_not_ready_failure_reaps_process_and_removes_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance_root = tmp_path / "instance"
    instance_root.mkdir()
    (instance_root / "instance.json").write_text(
        json.dumps(
            {
                "actor_id": "act-dev-browser-failure",
                "role": "dev",
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(instance_root / "workspace"),
                "thread_id": "thr-browser-failure",
                "browser_port": None,
            }
        ),
        encoding="utf-8",
    )
    fake_chrome = tmp_path / "fake-chrome"
    _write_executable(
        fake_chrome,
        "\n".join(
            [
                "import signal, time",
                "signal.signal(signal.SIGTERM, lambda *_args: (_ for _ in ()).throw(SystemExit(0)))",
                "time.sleep(60)",
            ]
        )
        + "\n",
    )
    real_popen = subprocess.Popen
    spawned_chrome: list[subprocess.Popen[str]] = []

    def capture_chrome_process(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        command = args[0] if args else kwargs["args"]
        if command[0] == str(fake_chrome):
            spawned_chrome.append(process)
        return process

    monkeypatch.setattr(
        browser_runtime_manager.subprocess,
        "Popen",
        capture_chrome_process,
    )
    monkeypatch.setattr(browser_runtime_manager, "DEFAULT_READY_ATTEMPTS", 1)
    monkeypatch.setattr(browser_runtime_manager, "DEFAULT_READY_DELAY_SECONDS", 0.01)

    listener = open_loopback_listener()
    try:
        result = browser_runtime_manager.acquire(
            instance_root=instance_root,
            actor_id="act-dev-browser-failure",
            requested_port=int(listener.getsockname()[1]),
            chrome_bin=fake_chrome,
        )
    finally:
        listener.close()

    assert result["ok"] is False
    assert len(spawned_chrome) == 1
    pid = spawned_chrome[0].pid
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _pid_exists(pid):
        time.sleep(0.02)
    assert not _pid_exists(pid)
    pid_path = instance_root / "browser" / "chrome.pid"
    assert not pid_path.exists()
    assert not process_identity.identity_file(pid_path).exists()
