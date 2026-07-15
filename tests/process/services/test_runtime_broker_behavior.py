"""Tests for runtime broker request routing and identity checks."""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import unittest
import contextlib
import importlib
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from tests.support.paths import REPO_ROOT
from tests.support.cli import pid_alive, wait_until
from tests.support.fake_cdp import FakeCdpServer, write_fake_chrome
from tests.support.processes import ResourceLedger, run_process

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import runtime_kernel.broker as runtime_broker  # noqa: E402
import runtime_kernel.client as runtime_client  # noqa: E402
from runtime_kernel import process_identity  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
BROKER_V2_PROTOCOL = "buddyswitch-runtime-broker/v2"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


def port_accepts(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.2)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"missing required Runtime Broker V2 module: {name}") from exc


class RuntimeBrokerLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = _require_module("runtime_kernel.lifecycle")

    def _paths(self, root: Path):
        return self.lifecycle.BrokerPaths(
            socket_path=root / "runtime-broker.sock",
            pid_file=root / "runtime-broker.pid",
            marker_file=root / "runtime-broker.socket",
            log_file=root / "runtime-broker.log",
        )

    def test_start_broker_process_uses_configured_runtime_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            paths = self._paths(root)
            commands: list[list[str]] = []
            popen_kwargs: list[dict[str, object]] = []

            class FakeProcess:
                pid = 5432

            def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
                commands.append(command)
                popen_kwargs.append(kwargs)
                return FakeProcess()

            with patch.object(self.lifecycle.subprocess, "Popen", side_effect=fake_popen), patch.dict(
                os.environ,
                {"BUDDYSWITCH_PYTHON": "/configured/runtime/python"},
                clear=False,
            ):
                result = self.lifecycle.start_broker_process(
                    paths,
                    instance_json_path=root / "instance.json",
                    manifest_path=MANIFEST,
                )

            self.assertEqual(result["pid"], 5432)
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0][0], "/configured/runtime/python")
            self.assertEqual(Path(commands[0][1]).resolve(), (SCRIPTS / "runtime_kernel" / "broker.py").resolve())
            self.assertEqual(commands[0][2], "serve")
            self.assertEqual(len(popen_kwargs), 1)

    @staticmethod
    def _copy_runtime_fixture(workspace_dir: Path) -> None:
        runtime_surface = (
            "scripts/turn_runtime.py",
            "scripts/env_store.py",
            "scripts/env_legacy_store.py",
            "scripts/env",
            "scripts/env_profiles.py",
            "scripts/env_manifest.py",
            "scripts/browser_evidence.py",
            "scripts/runtime_kernel",
            "buddyswitch/manifest.toml",
            "buddyswitch/env-profiles",
            "framework/contracts",
        )
        for relative in runtime_surface:
            source = ROOT / relative
            target = workspace_dir / relative
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True, symlinks=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    @staticmethod
    def _write_instance_json(path: Path, *, workspace_dir: Path, actor_id: str = "act-pm-root", role: str = "pm") -> None:
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-13T00:00:00Z",
                    "updated_at": "2026-05-13T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _run_broker_cli(
        self,
        *,
        workspace_dir: Path,
        command: str,
        paths,
        instance_json: Path,
        manifest_path: Path,
        repo_root_path: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        broker_script = workspace_dir / "scripts" / "runtime_kernel" / "broker.py"
        broker_command = [
            os.environ["BUDDYSWITCH_PYTHON"],
            str(broker_script),
            command,
            "--socket",
            str(paths.socket_path),
            "--pid-file",
            str(paths.pid_file),
            "--marker-file",
            str(paths.marker_file),
            "--log-file",
            str(paths.log_file),
            "--instance-json",
            str(instance_json),
            "--manifest",
            str(manifest_path),
        ]
        if repo_root_path is not None:
            broker_command.extend(["--repo-root", str(repo_root_path)])
        if command == "ensure":
            ResourceLedger.from_environment().register_process_descriptor(
                pid_file=paths.pid_file,
                cleanup_strategy="runtime_broker_stop",
                cleanup_args={
                    "socket_path": str(paths.socket_path),
                    "pid_file": str(paths.pid_file),
                    "marker_file": str(paths.marker_file),
                    "log_file": str(paths.log_file),
                },
                command=broker_command,
                owned_paths={
                    "socket": paths.socket_path,
                    "pid": paths.pid_file,
                    "identity": process_identity.identity_file(paths.pid_file),
                    "marker": paths.marker_file,
                    "log": paths.log_file,
                },
            )
        completed = run_process(
            broker_command,
            cwd=workspace_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        payload: dict[str, object] = {}
        if completed.stdout.strip():
            decoded = json.loads(completed.stdout.strip())
            self.assertIsInstance(decoded, dict, msg=completed.stdout)
            payload = decoded
        return completed, payload

    def test_live_status_reports_workspace_root_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace_dir = Path(temp)
            (workspace_dir / "AGENTS.md").write_text(
                "# BuddySwitch Runtime Workspace\n",
                encoding="utf-8",
            )
            self._copy_runtime_fixture(workspace_dir)
            runtime_dir = workspace_dir / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            paths = self._paths(runtime_dir)
            instance_json = workspace_dir / "instance.json"
            self._write_instance_json(instance_json, workspace_dir=workspace_dir)
            manifest_path = workspace_dir / "buddyswitch" / "manifest.toml"

            ensure_completed, ensure_payload = self._run_broker_cli(
                workspace_dir=workspace_dir,
                command="ensure",
                paths=paths,
                instance_json=instance_json,
                manifest_path=manifest_path,
            )
            self.assertEqual(ensure_completed.returncode, 0, msg=ensure_completed.stderr)
            self.assertTrue(ensure_payload.get("ok"), msg=ensure_payload)
            try:
                status_completed, status_payload = self._run_broker_cli(
                    workspace_dir=workspace_dir,
                    command="status",
                    paths=paths,
                    instance_json=instance_json,
                    manifest_path=manifest_path,
                )
                self.assertEqual(status_completed.returncode, 0, msg=status_completed.stderr)
                self.assertTrue(status_payload.get("healthy"), msg=status_payload)
                self.assertIs(status_payload.get("runtime_workspace"), True)
                self.assertEqual(
                    Path(str(status_payload.get("env_store_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(status_payload.get("runtime_workspace_root"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(status_payload.get("runtime_state_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(status_payload.get("cwd"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
                ping = status_payload.get("ping")
                self.assertIsInstance(ping, dict, msg=status_payload)
                assert isinstance(ping, dict)
                self.assertIs(ping.get("runtime_workspace"), True)
                self.assertEqual(
                    Path(str(ping.get("env_store_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(ping.get("runtime_workspace_root"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(ping.get("runtime_state_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(ping.get("cwd"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
            finally:
                self._run_broker_cli(
                    workspace_dir=workspace_dir,
                    command="stop",
                    paths=paths,
                    instance_json=instance_json,
                    manifest_path=manifest_path,
                )

    def test_live_broker_message_needs_parent_rejects_without_parent_submit(self) -> None:
        protocol = _require_module("runtime_kernel.protocol")
        with tempfile.TemporaryDirectory() as temp:
            workspace_dir = Path(temp) / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            (workspace_dir / "AGENTS.md").write_text(
                "# BuddySwitch Runtime Workspace\n",
                encoding="utf-8",
            )
            self._copy_runtime_fixture(workspace_dir)
            self.assertFalse((workspace_dir / "tools").exists())
            runtime_dir = workspace_dir / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            paths = self._paths(runtime_dir)
            manifest_path = workspace_dir / "buddyswitch" / "manifest.toml"
            instance_json = workspace_dir / "instance.json"
            instance_json.write_text(
                json.dumps(
                    {
                        "actor_id": "act-pm-aaaaaaaaaaaa",
                        "role": "pm",
                        "status": "active",
                        "instance_root": str(workspace_dir),
                        "current_task_id": None,
                        "current_track_id": None,
                        "workspace_dir": str(workspace_dir),
                        "browser_port": None,
                        "created_at": "2026-06-04T00:00:00Z",
                        "updated_at": "2026-06-04T00:00:00Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            im_root = workspace_dir / "state" / "im"
            for child in ("conversations", "messages", "message_states"):
                (im_root / child).mkdir(parents=True, exist_ok=True)
            message_id = "msg-live-projected-root"
            conversation_id = "conv-live-projected-root"
            sender_identity = {"id": "act-dev-bbbbbbbbbbbb", "type": "actor"}
            target_identity = {"id": "act-pm-aaaaaaaaaaaa", "type": "actor"}
            state_path = im_root / "message_states" / f"{message_id}--act-pm-aaaaaaaaaaaa.json"
            (im_root / "conversations" / f"{conversation_id}.json").write_text(
                json.dumps(
                    {
                        "id": conversation_id,
                        "type": "direct",
                        "identity_ids": ["act-dev-bbbbbbbbbbbb", "act-pm-aaaaaaaaaaaa"],
                        "created_at": "2026-06-04T00:00:00Z",
                        "updated_at": "2026-06-04T00:00:00Z",
                        "last_message_id": message_id,
                        "last_sequence": 1,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (im_root / "messages" / f"{message_id}.json").write_text(
                json.dumps(
                    {
                        "id": message_id,
                        "conversation_id": conversation_id,
                        "sender_identity": sender_identity,
                        "target_identity": target_identity,
                        "content": "This changes the active parent-thread objective.",
                        "reply_to": None,
                        "created_at": "2026-06-04T00:00:00Z",
                        "sequence": 1,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "message_id": message_id,
                        "owner_identity_id": "act-pm-aaaaaaaaaaaa",
                        "disposition": "unseen",
                        "reason": None,
                        "processed_by": None,
                        "updated_at": "2026-06-04T00:00:00Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            fake_source_root = Path(temp) / "source-checkout"
            launcher_dir = fake_source_root / "tools" / "launcher"
            launcher_dir.mkdir(parents=True, exist_ok=True)
            (launcher_dir / "daemon_core.py").write_text(
                "raise AssertionError('old daemon_core parent submit path must not be imported')\n",
                encoding="utf-8",
            )

            ensure_completed, ensure_payload = self._run_broker_cli(
                workspace_dir=workspace_dir,
                command="ensure",
                paths=paths,
                instance_json=instance_json,
                manifest_path=manifest_path,
                repo_root_path=fake_source_root,
            )
            self.assertEqual(ensure_completed.returncode, 0, msg=ensure_completed.stderr)
            self.assertTrue(ensure_payload.get("ok"), msg=ensure_payload)
            try:
                request = {
                    "protocol": BROKER_V2_PROTOCOL,
                    "request_id": "req-live-needs-parent-projected-root",
                    "method": "env.tool",
                    "params": {
                        "actor_id": "act-pm-aaaaaaaaaaaa",
                        "active_role": "pm",
                        "tool": "message",
                        "action": "mark",
                        "args": {
                            "message_id": message_id,
                            "disposition": "needs_parent",
                            "reason": "This changes the active parent-thread objective.",
                        },
                    },
                    "deadline_ms": 35000,
                }
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(5.0)
                    sock.connect(str(paths.socket_path))
                    protocol.write_message(sock, request)
                    response = protocol.read_message(sock)

                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
                self.assertIn("task_sys.need_parent", (response.get("error") or {}).get("message", ""))
                stored = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(stored["disposition"], "unseen")
                self.assertIsNone(stored["reason"])
                parent_request_path = workspace_dir / "runtime" / "parent-request.json"
                self.assertFalse(parent_request_path.exists(), msg=parent_request_path)
            finally:
                self._run_broker_cli(
                    workspace_dir=workspace_dir,
                    command="stop",
                    paths=paths,
                    instance_json=instance_json,
                    manifest_path=manifest_path,
                    repo_root_path=fake_source_root,
                )

    def test_status_reports_unhealthy_when_pid_live_but_socket_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            process_identity.write_record(paths.pid_file, os.getpid())
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            status = self.lifecycle.broker_status(paths, expected_actor_id="act-pm-example", expected_active_role="pm")
        self.assertFalse(status["healthy"])
        self.assertEqual(status["error"]["code"], "E_RUNTIME_BROKER_STALE_SOCKET")

    def test_status_reports_unhealthy_when_marker_disagrees_with_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._paths(root)
            process_identity.write_record(paths.pid_file, os.getpid())
            paths.marker_file.write_text(str(root / "other.sock"), encoding="utf-8")
            status = self.lifecycle.broker_status(paths, expected_actor_id="act-pm-example", expected_active_role="pm")
        self.assertFalse(status["healthy"])
        self.assertEqual(status["socket_path"], str(paths.socket_path))
        self.assertEqual(status["marker_path"], str(paths.marker_file))

    def test_status_rejects_ping_from_source_checkout_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace_dir = Path(temp) / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            paths = self._paths(Path(temp))
            process_identity.write_record(paths.pid_file, os.getpid())
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "actor_id": "act-pm-example",
                        "active_role": "pm",
                        "pid": os.getpid(),
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": False,
                    },
                },
            ):
                status = self.lifecycle.broker_status(
                    paths,
                    expected_actor_id="act-pm-example",
                    expected_active_role="pm",
                    expected_workspace_root=workspace_dir,
                )
        self.assertFalse(status["healthy"])
        self.assertIn(status["error"]["code"], {"E_RUNTIME_BROKER_STALE_SOCKET", "E_RUNTIME_BROKER_PERMISSION"})
        self.assertRegex(status["error"]["message"], r"runtime root mismatch|runtime workspace marker is invalid")

    def test_status_reports_unhealthy_when_ping_result_missing_pid_or_socket_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            process_identity.write_record(paths.pid_file, os.getpid())
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "actor_id": "act-pm-example",
                        "active_role": "pm",
                    },
                },
            ):
                status = self.lifecycle.broker_status(
                    paths,
                    expected_actor_id="act-pm-example",
                    expected_active_role="pm",
                )
        self.assertFalse(status["healthy"])
        self.assertEqual(status["error"]["code"], "E_RUNTIME_BROKER_STALE_SOCKET")
        self.assertIn("missing pid", status["error"]["message"])

    def test_status_requires_successful_ping_before_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            process_identity.write_record(paths.pid_file, os.getpid())
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": False,
                    "error": {
                        "code": "E_RUNTIME_BROKER_UNAVAILABLE",
                        "message": "runtime broker ping unavailable",
                        "retriable": True,
                    },
                },
            ):
                status = self.lifecycle.broker_status(
                    paths,
                    expected_actor_id="act-pm-example",
                    expected_active_role="pm",
                )
        self.assertFalse(status["healthy"])
        self.assertEqual(status["error"]["code"], "E_RUNTIME_BROKER_UNAVAILABLE")

    def test_ensure_cleans_stale_pid_marker_and_socket_before_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text("999999\n", encoding="utf-8")
            paths.marker_file.write_text("/tmp/stale.sock", encoding="utf-8")
            paths.socket_path.write_text("not a socket", encoding="utf-8")
            events: list[str] = []

            def fake_start(*args, **kwargs):
                events.append("start")
                self.assertFalse(paths.pid_file.exists())
                self.assertFalse(paths.socket_path.exists())
                process_identity.write_record(paths.pid_file, os.getpid())
                return {"ok": True, "pid": os.getpid()}

            def fake_ping(*args, **kwargs):
                events.append("ping")
                return {
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "actor_id": "act-pm-example",
                        "active_role": "pm",
                        "pid": os.getpid(),
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": True,
                    },
                }

            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "start_broker_process",
                side_effect=fake_start,
            ), patch.object(self.lifecycle, "ping_broker", side_effect=fake_ping):
                result = self.lifecycle.ensure_broker(
                    paths,
                    instance_json_path=Path("instance.json"),
                    manifest_path=MANIFEST,
                    expected_actor_id="act-pm-example",
                    expected_active_role="pm",
                )
            self.assertTrue(result["ok"], msg=result)
            self.assertEqual(events, ["start", "ping", "ping"])
            self.assertEqual(paths.marker_file.read_text(encoding="utf-8"), str(paths.socket_path))
            self.assertTrue(result["status"]["healthy"], msg=result)

    def test_ensure_timeout_removes_stale_marker(self) -> None:
        started = ResourceLedger.from_environment().start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text("999999\n", encoding="utf-8")
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            paths.socket_path.write_text("stale socket", encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle, "start_broker_process", return_value={"ok": True, "pid": started.pid}
            ), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "actor_id": "act-pm-example",
                        "active_role": "pm",
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": True,
                    },
                },
            ):
                result = self.lifecycle.ensure_broker(
                    paths,
                    instance_json_path=Path("instance.json"),
                    manifest_path=MANIFEST,
                    expected_actor_id="act-pm-example",
                    expected_active_role="pm",
                    startup_timeout_seconds=0.05,
                )
        started.wait(timeout=2)
        self.assertFalse(result["ok"], msg=result)
        self.assertEqual(result["error"]["broker_status"]["log_file"], str(paths.log_file))
        self.assertEqual(result["error"]["broker_status"]["socket_path"], str(paths.socket_path))
        self.assertEqual(result["error"]["broker_status"]["pid_file"], str(paths.pid_file))
        self.assertFalse(paths.marker_file.exists())
        self.assertFalse(paths.socket_path.exists())
        self.assertIsNotNone(started.returncode)

    def test_ensure_stops_identity_valid_unhealthy_broker_before_repair(self) -> None:
        unhealthy = ResourceLedger.from_environment().start_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            process_identity.write_record(paths.pid_file, unhealthy.pid)

            def fail_start(*_args, **_kwargs):
                self.assertFalse(process_identity.is_running(
                    process_identity.RecordedProcess(
                        unhealthy.pid,
                        process_identity.start_identity(unhealthy.pid) or "stopped",
                    )
                ))
                return {"ok": False}

            with patch.object(
                self.lifecycle,
                "start_broker_process",
                side_effect=fail_start,
            ):
                result = self.lifecycle.ensure_broker(
                    paths,
                    instance_json_path=Path("instance.json"),
                    manifest_path=MANIFEST,
                    expected_actor_id="act-pm-example",
                    expected_active_role="pm",
                )

        unhealthy.wait(timeout=2)
        self.assertFalse(result["ok"], msg=result)
