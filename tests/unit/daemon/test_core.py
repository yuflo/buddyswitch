"""Tests for daemon core state, lifecycle, and run loop."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from unittest.mock import patch


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"
LAUNCHER = ROOT / "tools" / "launcher"

import daemon_contracts  # noqa: E402
import daemon_state  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402
from env.repos import runtime_files  # noqa: E402

DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
INSTANCE_DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
MODULE_COUNTER = count()
RUNTIME_ENV_KEYS = (
    "BUDDYSWITCH_SHARED_ROOT",
    "BUDDYSWITCH_STATE_ROOT",
    "BUDDYSWITCH_INSTANCE_ROOT",
    "BUDDYSWITCH_INSTANCE_JSON",
    "BUDDYSWITCH_WORKSPACE_DIR",
    "BUDDYSWITCH_ACTOR_ID",
    "BUDDYSWITCH_ROLE_ID",
)


def load_daemon_core() -> Any:
    if not DAEMON_CORE_PATH.exists():
        raise AssertionError(f"expected daemon core module to exist: {DAEMON_CORE_PATH}")
    return importlib.reload(importlib.import_module("daemon_core"))


class StopDaemonLoop(RuntimeError):
    pass


class DaemonCoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_runtime_env = {key: os.environ.get(key) for key in RUNTIME_ENV_KEYS}
        self.addCleanup(self._restore_runtime_env, self._saved_runtime_env)
        self.core = load_daemon_core()

    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.refresh_runtime_roots_from_env()


class DaemonCoreStateTests(DaemonCoreTestCase):
    def _instance_root(self, temp_root: str) -> Path:
        root = Path(temp_root) / "instances" / "act-dev-daed00000001"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_daemon_registration_projects_identity_route_and_registry_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps(
                    {
                        "actor_id": "act-dev-daed00000001",
                        "role": "dev",
                        "status": "active",
                        "instance_root": str(instance_root),
                        "workspace_dir": str(workspace_dir),
                        "thread_id": "thr-main",
                        "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            context = self.core.load_daemon_context(instance_json)
            identity_route = self.core.identity_route_for_context(context)
            calls: list[dict[str, Any]] = []
            original_register = self.core.daemon_client.register_actor

            def fake_register_actor(**kwargs: Any) -> dict[str, Any]:
                calls.append(kwargs)
                return {
                    "record": {
                        "identity_id": kwargs["identity_id"],
                        "role_id": kwargs["role_id"],
                        "endpoint": kwargs["endpoint"],
                    }
                }

            self.addCleanup(setattr, self.core.daemon_client, "register_actor", original_register)
            self.core.daemon_client.register_actor = fake_register_actor

            row = self.core.register_daemon_actor(context, identity_route)["record"]

            self.assertEqual(row["identity_id"], "act-dev-daed00000001")
            self.assertEqual(row["role_id"], "dev")
            self.assertEqual(row["endpoint"]["kind"], "daemon_mailbox_socket")
            self.assertEqual(row["endpoint"]["socket_path"], str(self.core.daemon_mailbox.mailbox_socket_path(context.instance_root)))
            self.assertEqual(calls[0]["heartbeat"], {"kind": "central_daemon_rpc"})
            self.assertEqual(calls[0]["socket_path"], self.core.central_daemon_socket_path(context))

    def test_daemon_reachability_client_uses_explicit_identity_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps(
                    {
                        "actor_id": "act-dev-daed00000001",
                        "role": "dev",
                        "status": "active",
                        "instance_root": str(instance_root),
                        "workspace_dir": str(workspace_dir),
                        "thread_id": "thr-main",
                        "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            context = self.core.load_daemon_context(instance_json)
            identity_route = self.core.identity_route_for_context(context)

            self.assertEqual(identity_route, {"identity_id": "act-dev-daed00000001", "role_id": "dev"})
            self.assertNotIn("to_role", self.core.register_daemon_actor.__code__.co_varnames)

    def test_application_command_composition_is_read_only_and_rejects_duplicates(self) -> None:
        context = object()
        first = lambda _params: {"source": "first"}
        second = lambda _params: {"source": "second"}

        commands = self.core.build_application_commands(
            context,
            [lambda _context: {"example.command": first}],
        )

        self.assertIs(commands["example.command"], first)
        with self.assertRaises(TypeError):
            commands["other.command"] = second
        with self.assertRaisesRegex(ValueError, "duplicate application command"):
            self.core.build_application_commands(
                context,
                [
                    lambda _context: {"example.command": first},
                    lambda _context: {"example.command": second},
                ],
            )

    def test_application_command_composition_rejects_invalid_factories_and_entries(self) -> None:
        context = object()
        with self.assertRaisesRegex(ValueError, "factories must be callable"):
            self.core.build_application_commands(context, [object()])
        with self.assertRaisesRegex(ValueError, "return a mapping"):
            self.core.build_application_commands(context, [lambda _context: []])
        with self.assertRaisesRegex(ValueError, "non-empty"):
            self.core.build_application_commands(context, [lambda _context: {"": lambda _params: {}}])
        with self.assertRaisesRegex(ValueError, "callable"):
            self.core.build_application_commands(context, [lambda _context: {"example.command": object()}])
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.core.build_application_commands(
                context,
                [lambda _context: {"mailbox.deliver": lambda _params: {}}],
            )

    def test_handler_reconciliation_is_optional_isolated_and_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps({
                    "actor_id": "act-dev-daed00000001",
                    "role": "dev",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace_dir),
                    "thread_id": "thr-main",
                    "app_server_socket": str(
                        instance_root / "runtime" / "app-server.sock"
                    ),
                }),
                encoding="utf-8",
            )
            context = self.core.load_daemon_context(instance_json)
            state = daemon_state.DaemonState.load(
                instance_root=instance_root,
                actor_id=context.actor_id,
                main_thread_id=context.main_thread_id,
            )
            state.register_handlers(["exploding", "healthy", "trigger-only"])
            calls: list[str] = []

            class Exploding:
                name = "exploding"

                def reconcile(self, context: object, state: object, runtime: object) -> object:
                    del context, state, runtime
                    calls.append(self.name)
                    raise RuntimeError("reconcile exploded")

            class Healthy:
                name = "healthy"

                def reconcile(self, context: object, state: object, runtime: object) -> object:
                    del context, state, runtime
                    calls.append(self.name)
                    return daemon_contracts.HandlerResult.handled()

            class TriggerOnly:
                name = "trigger-only"

            result = self.core.reconcile_handlers(
                context,
                state,
                object(),
                [Exploding(), Healthy(), TriggerOnly()],
            )

            self.assertEqual(calls, ["exploding", "healthy"])
            self.assertEqual(result["reconciled_count"], 1)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(
                [row["handler"] for row in result["handlers"]],
                ["exploding", "healthy"],
            )
            payload = json.loads(
                daemon_state.daemon_state_file(instance_root).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                payload["handlers"]["exploding"]["last_error"]["message"],
                "reconcile exploded",
            )
            self.assertEqual(
                payload["handlers"]["healthy"]["last_result"],
                "handled",
            )


class FakeBindingClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"thread": {"id": "thr-main"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


class DaemonCoreBindingTests(DaemonCoreTestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daed00000001"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "actor_id": "act-dev-daed00000001",
            "role": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {
            "instance_root": instance_root,
            "workspace_dir": workspace_dir,
            "instance_json": instance_json,
            "payload": payload,
        }

    def test_bind_main_thread_uses_thread_resume_for_current_instance_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient()

            self.core.bind_main_thread(context, client)

            self.assertEqual([request["method"] for request in client.requests], ["thread/resume"])
            params = client.requests[0]["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thr-main")
            self.assertEqual(params["cwd"], str(instance["workspace_dir"]))
            self.assertEqual(
                params["runtimeWorkspaceRoots"],
                [
                    str(instance["workspace_dir"]),
                    str(Path(temp_root) / "project" / "workspace"),
                ],
            )
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            self.assertEqual(params["excludeTurns"], True)

    def test_bind_main_thread_fails_on_wrong_resumed_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient(result={"thread": {"id": "thr-other"}})

            with self.assertRaises(self.core.app_server.AppServerProtocolError):
                self.core.bind_main_thread(context, client)

    def test_derive_daemon_runtime_env_projects_shared_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])

            env = self.core.derive_daemon_runtime_env(context)

            shared_root = Path(temp_root)
            self.assertEqual(
                env,
                {
                    "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                    "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
                    "BUDDYSWITCH_INSTANCE_ROOT": str(instance["instance_root"]),
                    "BUDDYSWITCH_INSTANCE_JSON": str(instance["instance_json"]),
                    "BUDDYSWITCH_WORKSPACE_DIR": str(instance["workspace_dir"]),
                    "BUDDYSWITCH_ACTOR_ID": "act-dev-daed00000001",
                    "BUDDYSWITCH_ROLE_ID": "dev",
                },
            )
