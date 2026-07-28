"""Tests for the shared-root central daemon service."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import threading
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
CENTRAL_CORE_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "central_daemon_core.py"
CENTRAL_CLI_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "central_daemon.py"
DAEMON_CLIENT_PATH = ROOT / "src" / "buddyswitch" / "env" / "tool_runtime" / "daemon_client.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = (
        "buddyswitch.env.tool_runtime.daemon_client"
        if path == DAEMON_CLIENT_PATH
        else f"buddyswitch.launcher.{path.stem}"
    )
    return importlib.reload(importlib.import_module(module_name))


class CentralDaemonServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = load_module(CENTRAL_CORE_PATH)
        self.client = load_module(DAEMON_CLIENT_PATH)

    def _paths(self, temp_root: str) -> Any:
        return self.core.central_daemon_paths(Path(temp_root))

    def _service(self, temp_root: str) -> Any:
        return self.core.CentralDaemonService(paths=self._paths(temp_root), now=lambda: "2026-05-30T00:00:00Z")

    def _register(self, service: Any, *, role: str = "dev", actor_id: str = "act-dev-daemon", status: str = "online") -> dict[str, Any]:
        return service.handle(
            "daemon.register",
            {
                "identity_id": actor_id,
                "role_id": role,
                "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": f"/tmp/{actor_id}.sock"},
                "heartbeat": {"kind": "central_daemon_rpc", "interval_seconds": 5},
                "status": status,
            },
        )

    def test_central_daemon_lifecycle_paths_are_shared_root_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)

            self.assertEqual(paths.shared_root, Path(temp_root).resolve(strict=False))
            expected_socket = self.client.central_daemon_socket_path_for_shared_root(paths.shared_root)
            self.assertEqual(paths.socket_path, expected_socket)
            self.assertEqual(paths.pid_file, paths.shared_root / "run" / "central-daemon" / "central-daemon.pid")
            self.assertEqual(paths.log_file, paths.shared_root / "run" / "central-daemon" / "central-daemon.log")
            self.assertEqual(paths.registry_path, paths.shared_root / "state" / "runtime" / "central-daemon" / "registry.json")

    def test_start_daemon_spawns_independent_process_and_status_reads_ready(self) -> None:
        cli = load_module(CENTRAL_CLI_PATH)
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)
            commands: list[list[str]] = []
            original_popen = cli.subprocess.Popen
            original_ping = cli.ping_central_daemon
            original_start_identity = cli.process_identity.start_identity

            class FakeProcess:
                pid = 4321

                def poll(self) -> None:
                    return None

            def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
                commands.append(command)
                self.assertTrue(kwargs.get("start_new_session"))
                return FakeProcess()

            def fake_ping(*, socket_path: Path) -> dict[str, Any]:
                self.assertEqual(socket_path, paths.socket_path)
                return {"ok": True, "pid": 4321, "socket_path": str(socket_path)}

            self.addCleanup(setattr, cli.subprocess, "Popen", original_popen)
            self.addCleanup(setattr, cli, "ping_central_daemon", original_ping)
            self.addCleanup(
                setattr,
                cli.process_identity,
                "start_identity",
                original_start_identity,
            )
            cli.subprocess.Popen = fake_popen
            cli.ping_central_daemon = fake_ping
            cli.process_identity.start_identity = lambda pid: f"test:{pid}"

            with patch.dict(os.environ, {"BUDDYSWITCH_PYTHON": "/configured/runtime/python"}, clear=False):
                payload = cli.start_central_daemon(paths)

            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4321)
            self.assertEqual(payload["socket_path"], str(paths.socket_path))
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0][0], cli.sys.executable)
            self.assertEqual(
                commands[0][1:],
                [
                    "-m",
                    "buddyswitch.application.entrypoints.central_daemon",
                    "serve",
                    "--shared-root",
                    str(paths.shared_root),
                ],
            )

    def test_ping_uses_identity_reachability_protocol(self) -> None:
        cli = load_module(CENTRAL_CLI_PATH)
        original_request = cli.daemon_client.request_central_daemon
        original_check = cli.daemon_client.check_reachability
        calls: list[dict[str, Any]] = []

        def fake_request(method: str, params: dict[str, Any], *, socket_path: Path) -> dict[str, Any]:
            calls.append({"kind": "request", "method": method, "params": params, "socket_path": socket_path})
            if method == "daemon.ping":
                return {"ok": True, "pid": 1111, "socket_path": str(socket_path)}
            raise AssertionError(f"unexpected central daemon method: {method}")

        def fake_check_reachability(*, target_identity_id: str, socket_path: Path) -> dict[str, Any]:
            calls.append(
                {
                    "kind": "reachability",
                    "target_identity_id": target_identity_id,
                    "socket_path": socket_path,
                }
            )
            return {
                "reachability_status": "never_registered",
                "target_identity_id": "act-central-daemon-probe",
                "record": None,
            }

        self.addCleanup(setattr, cli.daemon_client, "request_central_daemon", original_request)
        self.addCleanup(setattr, cli.daemon_client, "check_reachability", original_check)
        cli.daemon_client.request_central_daemon = fake_request
        cli.daemon_client.check_reachability = fake_check_reachability

        payload = cli.ping_central_daemon(socket_path=Path("/tmp/central.sock"))

        self.assertTrue(payload["identity_reachability_protocol"])
        self.assertEqual(
            calls,
            [
                {"kind": "request", "method": "daemon.ping", "params": {}, "socket_path": Path("/tmp/central.sock")},
                {
                    "kind": "reachability",
                    "target_identity_id": "act-central-daemon-probe",
                    "socket_path": Path("/tmp/central.sock"),
                },
            ],
        )
        self.assertNotIn("target_" + "actor_address", repr(calls))

    def test_central_daemon_readiness_has_no_actor_address_contract(self) -> None:
        text = CENTRAL_CLI_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "PROBE_" + "ACTOR_ADDRESS",
            "target_" + "actor_address",
            "actor_" + "address_protocol",
            "actor-address " + "protocol",
        ):
            self.assertNotIn(forbidden, text)

    def test_start_daemon_restarts_live_process_without_identity_reachability_protocol(self) -> None:
        cli = load_module(CENTRAL_CLI_PATH)
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)
            paths.pid_file.parent.mkdir(parents=True, exist_ok=True)
            commands: list[list[str]] = []
            terminated: list[int] = []
            original_popen = cli.subprocess.Popen
            original_ping = cli.ping_central_daemon
            original_start_identity = cli.process_identity.start_identity
            original_matches = cli.process_identity.matches
            original_terminate = cli.terminate_record
            original_cleanup = cli.cleanup_runtime_files
            cli.process_identity.start_identity = lambda pid: f"test:{pid}"
            cli.process_identity.matches = (
                lambda record: record.start_identity == f"test:{record.pid}"
            )
            cli.process_identity.write_record(paths.pid_file, 1111)

            class FakeProcess:
                pid = 2222

                def poll(self) -> None:
                    return None

            def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
                del kwargs
                commands.append(command)
                return FakeProcess()

            def fake_ping(*, socket_path: Path) -> dict[str, Any]:
                self.assertEqual(socket_path, paths.socket_path)
                if not commands:
                    raise RuntimeError("central daemon does not support identity reachability protocol")
                return {
                    "ok": True,
                    "pid": 2222,
                    "socket_path": str(socket_path),
                    "identity_reachability_protocol": True,
                }

            def fake_terminate(record: object) -> bool:
                terminated.append(record.pid)
                return True

            self.addCleanup(setattr, cli.subprocess, "Popen", original_popen)
            self.addCleanup(setattr, cli, "ping_central_daemon", original_ping)
            self.addCleanup(setattr, cli.process_identity, "start_identity", original_start_identity)
            self.addCleanup(setattr, cli.process_identity, "matches", original_matches)
            self.addCleanup(setattr, cli, "terminate_record", original_terminate)
            self.addCleanup(setattr, cli, "cleanup_runtime_files", original_cleanup)
            cli.subprocess.Popen = fake_popen
            cli.ping_central_daemon = fake_ping
            cli.terminate_record = fake_terminate
            cli.cleanup_runtime_files = lambda _paths: None

            payload = cli.start_central_daemon(paths)

            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 2222)
            self.assertEqual(payload["ping"]["identity_reachability_protocol"], True)
            self.assertEqual(terminated, [1111])
            self.assertEqual(len(commands), 1)

    def test_stop_daemon_terminates_process_and_cleans_runtime_files(self) -> None:
        cli = load_module(CENTRAL_CLI_PATH)
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)
            paths.pid_file.parent.mkdir(parents=True, exist_ok=True)
            paths.socket_path.write_text("", encoding="utf-8")
            terminated: list[int] = []
            original_start_identity = cli.process_identity.start_identity
            original_matches = cli.process_identity.matches
            original_is_running = cli.process_identity.is_running
            original_terminate = cli.terminate_record
            cli.process_identity.start_identity = lambda pid: f"test:{pid}"
            cli.process_identity.matches = (
                lambda record: record.start_identity == f"test:{record.pid}"
            )
            cli.process_identity.is_running = cli.process_identity.matches
            cli.process_identity.write_record(paths.pid_file, 4321)

            def fake_terminate(record: object) -> bool:
                terminated.append(record.pid)
                return True

            self.addCleanup(setattr, cli.process_identity, "start_identity", original_start_identity)
            self.addCleanup(setattr, cli.process_identity, "matches", original_matches)
            self.addCleanup(setattr, cli.process_identity, "is_running", original_is_running)
            self.addCleanup(setattr, cli, "terminate_record", original_terminate)
            cli.terminate_record = fake_terminate

            payload = cli.stop_central_daemon(paths)

            self.assertTrue(payload["ok"])
            self.assertEqual(terminated, [4321])
            self.assertFalse(paths.pid_file.exists())
            self.assertFalse(paths.socket_path.exists())

    def test_socket_server_ping_round_trip_closes_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)
            service = self._service(temp_root)
            server = self.core.CentralDaemonSocketServer(service=service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.request_central_daemon("daemon.ping", {}, socket_path=paths.socket_path)
            server.close()
            thread.join(timeout=2)

            self.assertEqual(result["ok"], True)
            self.assertEqual(result["socket_path"], str(paths.socket_path))
            self.assertFalse(thread.is_alive())
            self.assertFalse(paths.socket_path.exists())

    def test_register_projects_identity_and_presence_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)

            result = self._register(service)

            row = result["record"]
            self.assertEqual(row["identity_id"], "act-dev-daemon")
            self.assertEqual(row["identity"], {"id": "act-dev-daemon", "type": "actor"})
            self.assertEqual(row["role_id"], "dev")
            self.assertEqual(row["status"], "online")
            self.assertIn("endpoint", row)
            self.assertIn("heartbeat", row)
            self.assertIn("last_seen_at", row)
            self.assertNotIn("role", row)
            self.assertNotIn("daemon_role", row)
            self.assertNotIn("target_role_instance", row)
            self.assertNotIn("actor_address", row)

            saved = json.loads(service.paths.registry_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["actors"], [row])

    def test_register_rejects_presence_fields_as_identity_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)

            result = service.dispatch(
                {
                    "request_id": "req-bad-address",
                    "method": "daemon.register",
                    "params": {
                        "identity_id": {"id": "act-dev-daemon", "status": "online"},
                        "role_id": "dev",
                        "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": "/tmp/dev.sock"},
                    },
                }
            )

            self.assertFalse(result["ok"], msg=result)
            self.assertEqual(result["error"]["code"], "invalid_identity_id")

    def test_unregister_marks_registered_offline_instead_of_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            self._register(service)

            result = service.handle(
                "daemon.unregister",
                {"identity_id": "act-dev-daemon", "role_id": "dev"},
            )

            self.assertEqual(result["record"]["status"], "registered_offline")
            registry = service.handle("daemon.registry", {})
            self.assertEqual(len(registry["actors"]), 1)
            self.assertEqual(registry["actors"][0]["status"], "registered_offline")

    def test_heartbeat_restores_online_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            self._register(service)
            service.handle("daemon.unregister", {"identity_id": "act-dev-daemon", "role_id": "dev"})

            result = service.handle("daemon.heartbeat", {"identity_id": "act-dev-daemon"})

            self.assertEqual(result["record"]["status"], "online")
            self.assertEqual(result["record"]["last_seen_at"], "2026-05-30T00:00:00Z")

    def test_actor_directory_list_online_returns_only_online_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            self._register(service, role="dev", actor_id="act-dev-daemon")
            self._register(service, role="design", actor_id="act-design-daemon")
            service.handle("daemon.unregister", {"identity_id": "act-design-daemon", "role_id": "design"})

            result = service.handle("actor_directory.list_online", {})

            self.assertEqual(
                [(row["identity_id"], row["role_id"]) for row in result["actors"]],
                [("act-dev-daemon", "dev")],
            )

    def test_actor_directory_list_online_filters_by_role_without_resolving_message_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            self._register(service, role="dev", actor_id="act-dev-daemon")
            self._register(service, role="pm", actor_id="act-pm-daemon")

            result = service.handle("actor_directory.list_online", {"role_id": "dev"})

            self.assertEqual(len(result["actors"]), 1)
            self.assertEqual(result["actors"][0]["role_id"], "dev")

    def test_reachability_distinguishes_online_offline_never_registered_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            self._register(service, role="dev", actor_id="act-dev-daemon")
            self._register(service, role="design", actor_id="act-design-daemon")
            service.handle("daemon.unregister", {"identity_id": "act-design-daemon", "role_id": "design"})

            online = service.handle("actor.check_reachability", {"target_identity_id": "act-dev-daemon"})
            offline = service.handle("actor.check_reachability", {"target_identity_id": "act-design-daemon"})
            missing = service.handle("actor.check_reachability", {"target_identity_id": "act-pm-daemon"})
            invalid = service.handle("actor.check_reachability", {"target_identity_id": "dev-daemon"})

            self.assertEqual(online["reachability_status"], "online")
            self.assertEqual(offline["reachability_status"], "registered_offline")
            self.assertEqual(missing["reachability_status"], "never_registered")
            self.assertEqual(invalid["reachability_status"], "invalid_identity_id")

    def test_reachability_has_no_ambiguous_online_actor_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            self._register(service, role="dev", actor_id="act-dev-one")
            self._register(service, role="dev", actor_id="act-dev-two")

            first = service.handle("actor.check_reachability", {"target_identity_id": "act-dev-one"})
            second = service.handle("actor.check_reachability", {"target_identity_id": "act-dev-two"})

            self.assertEqual(first["reachability_status"], "online")
            self.assertEqual(second["reachability_status"], "online")
            self.assertNotIn("ambiguous_online_actor", json.dumps([first, second], ensure_ascii=True))
