from __future__ import annotations

import subprocess
import sys
import time

import buddyswitch.foundation.process_runtime.process_identity as process_identity
from tests.support.processes import ResourceLedger


def test_wait_with_detached_owned_service() -> None:
    ledger = ResourceLedger.from_environment()
    pid_path = ledger.run_root / "detached-service.pid"
    ledger.register_process_descriptor(
        pid_file=pid_path,
        cleanup_strategy="terminate_owned_pgid",
        cleanup_args={},
        command=["runner-signal-detached-service"],
        owned_paths={
            "pid": pid_path,
            "pid_identity": process_identity.identity_file(pid_path),
        },
    )
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    process_identity.write_record(pid_path, child.pid)
    time.sleep(60)
