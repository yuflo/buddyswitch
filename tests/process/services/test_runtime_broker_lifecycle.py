from __future__ import annotations

import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

import buddyswitch.foundation.process_runtime.process_identity as process_identity
from buddyswitch.foundation.runtime_broker import lifecycle
from tests.support.paths import REPO_ROOT
from tests.support.processes import ResourceLedger, run_process


def _paths(root: Path) -> lifecycle.BrokerPaths:
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return lifecycle.BrokerPaths(
        socket_path=Path(os.path.realpath("/tmp"))
        / f"buddyswitch-runtime-broker-lifecycle-{digest}.sock",
        pid_file=root / "runtime-broker.pid",
        marker_file=root / "runtime-broker.socket",
        log_file=root / "runtime-broker.log",
    )


def _command(paths: lifecycle.BrokerPaths, root: Path) -> list[str]:
    return [
        os.environ["BUDDYSWITCH_PYTHON"],
        "-m",
        "buddyswitch.application.entrypoints.runtime_broker",
        "serve",
        "--socket",
        str(paths.socket_path),
        "--pid-file",
        str(paths.pid_file),
        "--marker-file",
        str(paths.marker_file),
        "--log-file",
        str(paths.log_file),
        "--instance-json",
        str(root / "instance.json"),
    ]


def _wait_ready(paths: lifecycle.BrokerPaths, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if paths.socket_path.exists() and process_identity.read_record(paths.pid_file):
            return
        if process.poll() is not None:
            raise AssertionError(f"broker exited before ready: {process.returncode}")
        time.sleep(0.02)
    raise AssertionError("broker did not become ready")


def test_broker_command_uses_only_installed_module_and_explicit_state_paths(
    tmp_path: Path,
) -> None:
    command = _command(_paths(tmp_path), tmp_path)

    assert command[:3] == [
        sys.executable,
        "-m",
        "buddyswitch.application.entrypoints.runtime_broker",
    ]
    assert "--repo-root" not in command
    assert not [argument for argument in command if argument.endswith(".py")]
    assert "--manifest" not in command


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_broker_signal_finally_removes_pid_identity_socket_and_marker(
    tmp_path: Path,
    signum: int,
) -> None:
    paths = _paths(tmp_path)
    process = ResourceLedger.from_environment().start_process(
        _command(paths, tmp_path),
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        _wait_ready(paths, process)
        paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")

        process.send_signal(signum)
        process.wait(timeout=5)

        assert process.returncode == 0
        assert not paths.pid_file.exists()
        assert not process_identity.identity_file(paths.pid_file).exists()
        assert not paths.socket_path.exists()
        assert not paths.marker_file.exists()
    finally:
        if process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=2)
        paths.socket_path.unlink(missing_ok=True)


def test_broker_start_failure_removes_partially_created_socket_and_identity(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    paths.pid_file.mkdir(parents=True)

    completed = run_process(
        _command(paths, tmp_path),
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 1
    assert not paths.socket_path.exists()
    assert not process_identity.identity_file(paths.pid_file).exists()
    paths.socket_path.unlink(missing_ok=True)
