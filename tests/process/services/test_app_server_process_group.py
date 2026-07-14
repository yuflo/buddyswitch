"""App-server process-group lifecycle behavior."""

from __future__ import annotations

import importlib
import os
import tempfile
import time
from pathlib import Path

from runtime_kernel import process_identity
from tests.support.processes import ResourceLedger


APP_SERVER = importlib.import_module("app_server")


def test_stop_app_server_terminates_launch_group() -> None:
    script = (
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "from tests.support.processes import ResourceLedger\n"
        "child = ResourceLedger.from_environment().start_process("
        "[os.environ['BUDDYSWITCH_PYTHON'], '-c', 'import time; time.sleep(60)'], "
        "start_new_session=False)\n"
        "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')\n"
        "time.sleep(60)\n"
    )
    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        child_pid_file = root / "child.pid"
        leader = ResourceLedger.from_environment().start_process(
            [os.environ["BUDDYSWITCH_PYTHON"], "-c", script, str(child_pid_file)]
        )
        previous_grace = APP_SERVER.APP_SERVER_STOP_GRACE_SECONDS
        APP_SERVER.APP_SERVER_STOP_GRACE_SECONDS = 0.2
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not child_pid_file.exists():
                time.sleep(0.02)
            assert child_pid_file.exists()
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            child_identity = process_identity.start_identity(child_pid)
            assert child_identity is not None
            assert os.getpgid(child_pid) == os.getpgid(leader.pid)

            socket_path = root / "app-server.sock"
            pid_path = root / "app-server.pid"
            marker_path = root / "app-server.socket"
            log_path = root / "app-server.log"
            APP_SERVER.process_identity.write_record(pid_path, leader.pid)
            marker_path.write_text(f"{socket_path}\n", encoding="utf-8")
            socket_path.touch()

            payload = APP_SERVER.stop_app_server(
                socket_path,
                pid_path,
                marker_path,
                log_path,
            )

            assert payload["terminated"] is True
            leader.wait(timeout=2)
            recorded_child = process_identity.RecordedProcess(child_pid, child_identity)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and process_identity.is_running(recorded_child):
                time.sleep(0.02)
            assert not process_identity.is_running(recorded_child)
            assert not pid_path.exists()
            assert not marker_path.exists()
            assert not socket_path.exists()
        finally:
            APP_SERVER.APP_SERVER_STOP_GRACE_SECONDS = previous_grace
