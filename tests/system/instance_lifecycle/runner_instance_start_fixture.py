from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

import app_server
import central_daemon_core
import daemon_core
import daemon_mailbox
from runtime_kernel import lifecycle, process_identity
from tests.support.paths import REPO_ROOT
from tests.support.processes import ResourceLedger
from tests.support.fake_codex import write_fake_codex
from tests.support.cli import write_executable


def _debug(run_root: Path, message: str) -> None:
    with (run_root / "instance-start-debug.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{time.monotonic():.6f} {message}\n")


def _write_fake_executables(fake_bin: Path) -> None:
    write_fake_codex(fake_bin / "codex")
    write_executable(fake_bin / "curl", "#!/bin/sh\nexit 22\n")
    write_executable(fake_bin / "fake-chrome", "#!/bin/sh\nexec sleep 60\n")


def _register_instance_resources(
    ledger: ResourceLedger,
    *,
    shared_root: Path,
    instance_root: Path,
    actor_id: str,
) -> None:
    instance_json = instance_root / "instance.json"
    runtime_dir = instance_root / "runtime"

    app_pid = app_server.pid_file(instance_root)
    app_marker = app_server.marker_file(instance_root)
    app_socket = app_server.effective_socket_path(actor_id, instance_root, app_marker)
    ledger.register_process_descriptor(
        pid_file=app_pid,
        cleanup_strategy="app_server_stop",
        cleanup_args={
            "socket_path": str(app_socket),
            "pid_file": str(app_pid),
            "marker_file": str(app_marker),
            "log_file": str(app_server.log_file(instance_root)),
        },
        command=["codex", "app-server"],
        owned_paths={
            "pid": app_pid,
            "pid_identity": process_identity.identity_file(app_pid),
            "socket": app_socket,
            "marker": app_marker,
        },
    )

    broker_pid = runtime_dir / "runtime-broker.pid"
    broker_marker = runtime_dir / "runtime-broker.socket"
    broker_paths = lifecycle.BrokerPaths(
        socket_path=lifecycle.resolve_socket_path(actor_id, instance_root, broker_marker),
        pid_file=broker_pid,
        marker_file=broker_marker,
        log_file=runtime_dir / "runtime-broker.log",
    )
    ledger.register_process_descriptor(
        pid_file=broker_pid,
        cleanup_strategy="runtime_broker_stop",
        cleanup_args={
            "socket_path": str(broker_paths.socket_path),
            "pid_file": str(broker_paths.pid_file),
            "marker_file": str(broker_paths.marker_file),
            "log_file": str(broker_paths.log_file),
        },
        command=["runtime-broker", "serve"],
        owned_paths={
            "pid": broker_pid,
            "pid_identity": process_identity.identity_file(broker_pid),
            "socket": broker_paths.socket_path,
            "marker": broker_marker,
        },
    )

    daemon_pid = daemon_core.daemon_pid_file(instance_root)
    ledger.register_process_descriptor(
        pid_file=daemon_pid,
        cleanup_strategy="instance_daemon_stop",
        cleanup_args={"instance_json": str(instance_json)},
        command=["instance-daemon", "run"],
        owned_paths={
            "pid": daemon_pid,
            "pid_identity": process_identity.identity_file(daemon_pid),
            "socket": daemon_mailbox.mailbox_socket_path(instance_root),
        },
    )

    ledger.register_cleanup_action(
        cleanup_strategy="browser_stop",
        cleanup_args={"instance_root": str(instance_root), "actor_id": actor_id},
    )
    for worktree in (
        shared_root / "project" / "workspace",
        instance_root / "workspace",
    ):
        ledger.register_cleanup_action(
            cleanup_strategy="git_worktree_remove",
            cleanup_args={"repo_root": str(REPO_ROOT), "worktree": str(worktree)},
        )


def test_public_instance_start_resources_survive_until_runner_signal() -> None:
    ledger = ResourceLedger.from_environment()
    run_root = ledger.run_root
    shared_root = Path(os.environ["BUDDYSWITCH_SHARED_ROOT"])
    _debug(run_root, f"fixture-start shared_root={shared_root}")
    home = Path(os.environ["HOME"])
    auth_dir = home / ".codex"
    auth_dir.mkdir(parents=True, exist_ok=True)
    (auth_dir / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "apikey",
                "openai_api_key": "test-key",
                "tokens": None,
                "last_refresh": None,
                "agent_identity": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    fake_bin = run_root / "fake-bin"
    _write_fake_executables(fake_bin)
    _debug(run_root, "fake-executables-ready")

    central_paths = central_daemon_core.central_daemon_paths(shared_root)
    ledger.register_process_descriptor(
        pid_file=central_paths.pid_file,
        cleanup_strategy="central_daemon_stop",
        cleanup_args={"shared_root": str(shared_root)},
        command=["central-daemon", "serve"],
        owned_paths={
            "pid": central_paths.pid_file,
            "pid_identity": central_paths.pid_identity_file,
            "socket": central_paths.socket_path,
        },
    )
    _debug(run_root, "central-descriptor-registered")

    env = dict(os.environ)
    env.pop("CODEX_HOME", None)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
    env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(run_root / "browser-ready.flag")
    env["BUDDYSWITCH_TEST_CAPTURE"] = str(run_root / "instance-start-capture.json")
    env["BUDDYSWITCH_TEST_CALLS"] = str(run_root / "instance-start-calls.jsonl")
    launcher_stdout = (run_root / "instance-start-launcher.stdout").open(
        "w", encoding="utf-8"
    )
    launcher_stderr = (run_root / "instance-start-launcher.stderr").open(
        "w", encoding="utf-8"
    )
    try:
        launcher = ledger.start_process(
            [str(REPO_ROOT / "buddyswitch-codex"), "instance", "start", "--role", "pm"],
            cwd=REPO_ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=launcher_stdout,
            stderr=launcher_stderr,
            text=True,
        )
    finally:
        launcher_stdout.close()
        launcher_stderr.close()
    _debug(run_root, f"launcher-started pid={launcher.pid}")

    deadline = time.monotonic() + 30.0
    instance_root: Path | None = None
    actor_id = ""
    while time.monotonic() < deadline:
        instances = sorted((shared_root / "instances").glob("act-pm-*"))
        if instances and (instances[0] / "instance.json").exists():
            instance_root = instances[0]
            actor_id = instance_root.name
            break
        if launcher.poll() is not None:
            stdout = (run_root / "instance-start-launcher.stdout").read_text(
                encoding="utf-8"
            )
            stderr = (run_root / "instance-start-launcher.stderr").read_text(
                encoding="utf-8"
            )
            raise AssertionError(
                f"public instance start exited early: {launcher.returncode}"
                f"\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        time.sleep(0.02)
    assert instance_root is not None
    _debug(run_root, f"instance-discovered actor_id={actor_id}")
    _register_instance_resources(
        ledger,
        shared_root=shared_root,
        instance_root=instance_root,
        actor_id=actor_id,
    )
    _debug(run_root, "instance-descriptors-registered")

    required_pid_files = {
        "central": central_paths.pid_file,
        "app_server": app_server.pid_file(instance_root),
        "runtime_broker": instance_root / "runtime" / "runtime-broker.pid",
        "instance_daemon": daemon_core.daemon_pid_file(instance_root),
    }
    captured: dict[str, int] = {}
    while time.monotonic() < deadline:
        ledger.reconcile_descriptors()
        process_records = {
            int(record["pid"])
            for record in ledger.records()
            if record.get("kind") == "process"
        }
        captured = {}
        for name, pid_file in required_pid_files.items():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                break
            if pid not in process_records:
                break
            captured[name] = pid
        if len(captured) == len(required_pid_files):
            _debug(run_root, f"all-processes-captured pids={captured}")
            break
        if launcher.poll() is not None and launcher.returncode != 0:
            stdout = (run_root / "instance-start-launcher.stdout").read_text(
                encoding="utf-8"
            )
            stderr = (run_root / "instance-start-launcher.stderr").read_text(
                encoding="utf-8"
            )
            raise AssertionError(
                f"public instance start failed: {launcher.returncode}"
                f"\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        time.sleep(0.02)
    assert len(captured) == len(required_pid_files), captured
    (run_root / "instance-start-ready.json").write_text(
        json.dumps(
            {
                "actor_id": actor_id,
                "instance_root": str(instance_root),
                "pids": captured,
                "worktrees": [
                    str(shared_root / "project" / "workspace"),
                    str(instance_root / "workspace"),
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _debug(run_root, "ready-written")
    time.sleep(60)
