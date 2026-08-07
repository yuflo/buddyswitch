from __future__ import annotations

import json
from pathlib import Path

from buddyswitch.launcher import daemon_core
from buddyswitch.launcher import daemon_mailbox
import pytest
import buddyswitch.foundation.process_runtime.process_identity as process_identity


def test_instance_daemon_early_exit_removes_pid_identity_and_mailbox(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance_root = tmp_path / "instances" / "act-dev-daemon-failure"
    workspace = instance_root / "workspace"
    workspace.mkdir(parents=True)
    instance_json = instance_root / "instance.json"
    instance_json.write_text(
        json.dumps(
            {
                "actor_id": "act-dev-daemon-failure",
                "role": "dev",
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(workspace),
                "thread_id": "thr-daemon-failure",
                "app_server_socket": str(instance_root / "runtime" / "missing.sock"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(daemon_core, "DAEMON_READY_TIMEOUT_SECONDS", 2.0)
    monkeypatch.setattr(daemon_core, "DAEMON_READY_POLL_SECONDS", 0.02)

    with pytest.raises(RuntimeError, match="exited before ready"):
        daemon_core.start_daemon(instance_json)

    pid_path = daemon_core.daemon_pid_file(instance_root)
    assert not pid_path.exists()
    assert not process_identity.identity_file(pid_path).exists()
    assert not daemon_mailbox.mailbox_socket_path(instance_root).exists()
