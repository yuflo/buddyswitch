from __future__ import annotations

import json
import os
from pathlib import Path
import time

from buddyswitch.launcher import app_server
from buddyswitch.launcher import browser_runtime_manager
import pytest
from buddyswitch.runtime_kernel import process_identity
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
) -> None:
    instance_root = tmp_path / "instance"
    instance_root.mkdir()
    fake_codex = tmp_path / "fake-codex"
    _write_executable(fake_codex, "import sys\nraise SystemExit(7)\n")
    socket_path = app_server.effective_socket_path(
        "act-dev-app-failure",
        instance_root,
        app_server.marker_file(instance_root),
    )

    with pytest.raises(app_server.AppServerUnavailableError):
        app_server.ensure_app_server(
            "act-dev-app-failure",
            instance_root,
            str(fake_codex),
            startup_timeout_seconds=1.0,
        )

    pid_path = app_server.pid_file(instance_root)
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
    child_pid_file = tmp_path / "fake-chrome.pid"
    fake_chrome = tmp_path / "fake-chrome"
    _write_executable(
        fake_chrome,
        "\n".join(
            [
                "import os, signal, time",
                "from pathlib import Path",
                f"Path({str(child_pid_file)!r}).write_text(str(os.getpid()), encoding='utf-8')",
                "signal.signal(signal.SIGTERM, lambda *_args: (_ for _ in ()).throw(SystemExit(0)))",
                "time.sleep(60)",
            ]
        )
        + "\n",
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
    pid = int(child_pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _pid_exists(pid):
        time.sleep(0.02)
    assert not _pid_exists(pid)
    pid_path = instance_root / "browser" / "chrome.pid"
    assert not pid_path.exists()
    assert not process_identity.identity_file(pid_path).exists()
