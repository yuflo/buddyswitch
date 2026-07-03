#!/usr/bin/env python3
"""Tests for the shared-root central daemon service."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import threading
import unittest
from itertools import count
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CENTRAL_CORE_PATH = ROOT / "tools" / "launcher" / "central_daemon_core.py"
CENTRAL_CLI_PATH = ROOT / "tools" / "launcher" / "central_daemon.py"
DAEMON_CLIENT_PATH = ROOT / "scripts" / "env" / "tool_runtime" / "daemon_client.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            cli.subprocess.Popen = fake_popen
            cli.ping_central_daemon = fake_ping

            payload = cli.start_central_daemon(paths)

            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4321)
            self.assertEqual(payload["socket_path"], str(paths.socket_path))
            self.assertEqual(len(commands), 1)
            self.assertEqual(Path(commands[0][1]).resolve(), CENTRAL_CLI_PATH.resolve())
            self.assertEqual(commands[0][2:], ["serve", "--shared-root", str(paths.shared_root)])

    def test_start_daemon_registers_child_process_for_test_cleanup(self) -> None:
        cli = load_module(CENTRAL_CLI_PATH)
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)
            registry_path = Path(temp_root) / "processes.jsonl"
            original_popen = cli.subprocess.Popen
            original_ping = cli.ping_central_daemon
            previous_registry = os.environ.get("BUDDYSWITCH_TEST_PROCESS_REGISTRY")

            class FakeProcess:
                pid = 4321

                def poll(self) -> None:
                    return None

            def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
                del command, kwargs
                return FakeProcess()

            def fake_ping(*, socket_path: Path) -> dict[str, Any]:
                return {"ok": True, "pid": 4321, "socket_path": str(socket_path)}

            def restore_registry() -> None:
                if previous_registry is None:
                    os.environ.pop("BUDDYSWITCH_TEST_PROCESS_REGISTRY", None)
                else:
                    os.environ["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = previous_registry

            self.addCleanup(setattr, cli.subprocess, "Popen", original_popen)
            self.addCleanup(setattr, cli, "ping_central_daemon", original_ping)
            self.addCleanup(restore_registry)
            cli.subprocess.Popen = fake_popen
            cli.ping_central_daemon = fake_ping
            os.environ["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = str(registry_path)

            cli.start_central_daemon(paths)

            rows = [json.loads(line) for line in registry_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["kind"], "central_daemon")
            self.assertEqual(rows[0]["pid"], 4321)
            self.assertEqual(rows[0]["shared_root"], str(paths.shared_root))
            self.assertEqual(rows[0]["pid_file"], str(paths.pid_file))

    def test_stop_daemon_terminates_process_and_cleans_runtime_files(self) -> None:
        cli = load_module(CENTRAL_CLI_PATH)
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self._paths(temp_root)
            paths.pid_file.parent.mkdir(parents=True, exist_ok=True)
            paths.pid_file.write_text("4321\n", encoding="utf-8")
            paths.socket_path.write_text("", encoding="utf-8")
            terminated: list[int] = []
            original_terminate = cli.terminate_pid
            original_pid_is_live = cli.pid_is_live

            def fake_terminate(pid: int) -> bool:
                terminated.append(pid)
                return True

            self.addCleanup(setattr, cli, "terminate_pid", original_terminate)
            self.addCleanup(setattr, cli, "pid_is_live", original_pid_is_live)
            cli.terminate_pid = fake_terminate
            cli.pid_is_live = lambda pid: pid == 4321

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

    def test_registry_write_stops_when_test_runtime_cleanup_removed_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            service = self._service(temp_root)
            registry_path = Path(temp_root) / "processes.jsonl"
            previous_registry = os.environ.get("BUDDYSWITCH_TEST_PROCESS_REGISTRY")

            def restore_registry() -> None:
                if previous_registry is None:
                    os.environ.pop("BUDDYSWITCH_TEST_PROCESS_REGISTRY", None)
                else:
                    os.environ["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = previous_registry

            self.addCleanup(restore_registry)
            os.environ["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = str(registry_path)
            service.paths.run_dir.mkdir(parents=True, exist_ok=True)
            service.paths.pid_file.write_text("123\n", encoding="utf-8")
            service.paths.pid_file.unlink()

            result = service.dispatch(
                {
                    "request_id": "req-cleanup",
                    "method": "daemon.register",
                    "params": {
                        "identity_id": "act-dev-daemon",
                        "role_id": "dev",
                        "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": "/tmp/dev.sock"},
                    },
                }
            )

            self.assertFalse(result["ok"], msg=result)
            self.assertEqual(result["error"]["code"], "test_runtime_cleanup_in_progress")
            self.assertFalse(service.paths.registry_path.exists())

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


if __name__ == "__main__":
    unittest.main()
