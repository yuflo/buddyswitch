from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from buddyswitch.runtime_kernel import process_identity
from tests.support.processes import ResourceLedger


def test_failure_leaves_cleanup_to_runner() -> None:
    ledger = ResourceLedger.from_environment()
    run_root = Path(ledger.run_root)
    pid_path = run_root / "failure-detached.pid"
    socket_path = run_root / "failure-detached.sock"
    ledger.register_process_descriptor(
        pid_file=pid_path,
        cleanup_strategy="terminate_owned_pgid",
        cleanup_args={},
        command=["failure-detached-service"],
        owned_paths={
            "pid": pid_path,
            "pid_identity": process_identity.identity_file(pid_path),
            "socket": socket_path,
        },
    )
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    process_identity.write_record(pid_path, child.pid)
    socket_path.write_text("owned\n", encoding="utf-8")
    raise AssertionError("intentional runner cleanup failure fixture")
