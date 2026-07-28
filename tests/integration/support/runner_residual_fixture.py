from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from buddyswitch.runtime_kernel import process_identity
from tests.support.processes import ResourceLedger


def test_passing_test_with_failed_normal_cleanup_fails_runner() -> None:
    ledger = ResourceLedger.from_environment()
    run_root = Path(ledger.run_root)
    pid_path = run_root / "residual-detached.pid"
    ledger.register_process_descriptor(
        pid_file=pid_path,
        cleanup_strategy="central_daemon_stop",
        cleanup_args={},
        command=["residual-detached-service"],
        owned_paths={
            "pid": pid_path,
            "pid_identity": process_identity.identity_file(pid_path),
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
