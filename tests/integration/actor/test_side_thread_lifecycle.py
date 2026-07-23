"""Contract tests for the side-thread lifecycle owner."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from itertools import count
from pathlib import Path
from typing import Any, Callable


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
LAUNCHER_ROOT = ROOT / "tools" / "launcher"
LIFECYCLE_PATH = LAUNCHER_ROOT / "side_thread_lifecycle.py"
REGISTRY_PATH = LAUNCHER_ROOT / "side_thread_registry.py"
MODULE_COUNTER = count()


def _load_module(path: Path, module_name: str) -> Any:
    del module_name
    return importlib.reload(importlib.import_module(path.stem))


def load_registry() -> Any:
    return _load_module(REGISTRY_PATH, f"buddyswitch_side_thread_registry_{next(MODULE_COUNTER)}")


def load_lifecycle(app_server: types.ModuleType, registry: Any) -> Any:
    module_name = f"buddyswitch_side_thread_lifecycle_{next(MODULE_COUNTER)}"
    original_modules = {
        "app_server": sys.modules.get("app_server"),
        "side_thread_registry": sys.modules.get("side_thread_registry"),
    }
    sys.modules["app_server"] = app_server
    sys.modules["side_thread_registry"] = registry
    try:
        return _load_module(LIFECYCLE_PATH, module_name)
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class FakeAppServer(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("app_server")
        self.SIDE_DEVELOPER_INSTRUCTIONS = "isolated side instructions"
        self.calls: list[dict[str, Any]] = []
        self.thread_read_status: dict[str, object] = {"type": "active", "activeFlags": []}
        self.thread_read_error: Exception | None = None
        self.interrupt_error: Exception | None = None
        self.before_turn_start: Callable[[], None] | None = None
        self.AppServerProtocolError = RuntimeError
        self.AppServerUnavailableError = RuntimeError

    def thread_start(
        self,
        socket_path: Path,
        workspace_dir: Path,
        shared_project_workspace_dir: Path,
        permissions: str,
        *,
        developer_instructions: str | None = None,
        ephemeral: bool | None = None,
        model: str | None = None,
        model_reasoning_effort: str | None = None,
        config_overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "helper": "thread_start",
                "socket_path": socket_path,
                "workspace_dir": workspace_dir,
                "shared_project_workspace_dir": shared_project_workspace_dir,
                "permissions": permissions,
                "developer_instructions": developer_instructions,
                "ephemeral": ephemeral,
                "model": model,
                "model_reasoning_effort": model_reasoning_effort,
                "config_overrides": config_overrides,
            }
        )
        return {"thread": {"id": "thr-side-1"}}

    def thread_read(self, socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
        self.calls.append({"helper": "thread_read", "socket_path": socket_path, "thread_id": thread_id, "include_turns": include_turns})
        if self.thread_read_error is not None:
            raise self.thread_read_error
        return {"thread": {"id": thread_id, "status": self.thread_read_status}}

    def turn_start(
        self,
        socket_path: Path,
        thread_id: str,
        text: str,
        permissions: str,
        *,
        output_schema: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append({
            "helper": "turn_start",
            "socket_path": socket_path,
            "thread_id": thread_id,
            "text": text,
            "permissions": permissions,
            "output_schema": output_schema,
        })
        if self.before_turn_start is not None:
            self.before_turn_start()
        return {"action": "start", "turn": {"id": "turn-side-started"}, "turn_id": "turn-side-started"}

    def turn_steer(self, socket_path: Path, thread_id: str, turn_id: str, text: str) -> dict[str, object]:
        self.calls.append({"helper": "turn_steer", "socket_path": socket_path, "thread_id": thread_id, "turn_id": turn_id, "text": text})
        return {"turn_id": f"{turn_id}-updated", "expected_turn_id": turn_id}

    def turn_interrupt(self, socket_path: Path, thread_id: str, turn_id: str) -> dict[str, object]:
        self.calls.append({"helper": "turn_interrupt", "socket_path": socket_path, "thread_id": thread_id, "turn_id": turn_id})
        if self.interrupt_error is not None:
            raise self.interrupt_error
        return {"ok": True, "turn_id": turn_id}

    def _forbidden(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
        raise AssertionError("side_thread_lifecycle must not use old turn-discovery or composite app-server helpers")


for _name in (
    "side_start",
    "side_close",
    "input_turn",
    "active_turn_id",
    "thread_turns_list",
    "thread_fork",
    "thread_inject_items",
    "side_boundary_prompt_item",
):
    setattr(FakeAppServer, _name, FakeAppServer._forbidden)


class FakeCodexEphemeralBoundaryTests(unittest.TestCase):
    def test_thread_turns_list_rejects_ephemeral_side_thread(self) -> None:
        fake_codex = importlib.reload(importlib.import_module("tests.support.fake_codex"))
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "app-server-state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "thread_id": "thr-main",
                        "threads": {
                            "thr-main": {
                                "status": {"type": "idle"},
                                "turns": [],
                                "injected_items": [],
                            },
                            "thr-side-1": {
                                "status": {"type": "active", "activeFlags": []},
                                "turns": [{"id": "turn-side-1", "status": "inProgress"}],
                                "injected_items": [],
                                "ephemeral": True,
                            },
                        },
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            previous = os.environ.get("BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE")
            os.environ["BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE"] = str(state_path)
            try:
                response = fake_codex.handle_rpc_message(
                    {
                        "id": 1,
                        "method": "thread/turns/list",
                        "params": {"threadId": "thr-side-1"},
                    },
                    {"actor_id": "act-dev-side"},
                )
            finally:
                if previous is None:
                    os.environ.pop("BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE", None)
                else:
                    os.environ["BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE"] = previous

        self.assertIsInstance(response, dict)
        error = response.get("error") if isinstance(response, dict) else None
        self.assertIsInstance(error, dict)
        self.assertEqual(error["code"], -32600)
        self.assertIn("ephemeral thread thr-side-1", error["message"])


class SideThreadLifecycleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry()
        self.app_server = FakeAppServer()
        self.lifecycle = load_lifecycle(self.app_server, self.registry)
        self.socket_path = Path("/tmp/buddyswitch-test-app.sock")
        self.workspace_dir = Path("/tmp/buddyswitch-workspace")
        self.project_workspace_dir = Path("/tmp/buddyswitch-project-workspace")

    def _instance_json(self, temp_root: str, *, actor_id: str = "act-dev-side") -> Path:
        instance_root = Path(temp_root) / "instances" / actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "dev",
                    "thread_id": "thr-main",
                    "side_threads": [],
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _payload(self, instance_json: Path) -> dict[str, Any]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def _seed_side_thread(
        self,
        instance_json: Path,
        *,
        side_thread_id: str = "thr-side-1",
        turn_id: str = "turn-side-active",
        purpose: str = "host_control.side",
    ) -> None:
        payload = self._payload(instance_json)
        row: dict[str, object] = {
            "thread_id": side_thread_id,
            "parent_thread_id": "thr-main",
            "status": "open",
            "purpose": purpose,
            "turn_id": turn_id,
            "created_at": "2026-07-02T00:00:00Z",
            "updated_at": "2026-07-02T00:00:00Z",
        }
        payload["side_threads"] = [row]
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def test_start_side_thread_registers_lease_with_started_turn_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            def assert_starting_lease_is_visible() -> None:
                rows = self._payload(instance_json)["side_threads"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["thread_id"], "thr-side-1")
                self.assertEqual(rows[0]["turn_kind"], "starting")
                self.assertNotIn("turn_id", rows[0])

            self.app_server.before_turn_start = assert_starting_lease_is_visible

            result = self.lifecycle.start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Start side work",
                purpose="demand-triage",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
                output_schema={
                    "type": "object",
                    "required": ["decision"],
                    "properties": {"decision": {"type": "string"}},
                },
            )

            self.assertEqual(
                [call["helper"] for call in self.app_server.calls],
                ["thread_start", "turn_start", "thread_read"],
            )
            self.assertEqual(self.app_server.calls[0]["developer_instructions"], "isolated side instructions")
            self.assertIs(self.app_server.calls[0]["ephemeral"], True)
            self.assertEqual(
                self.app_server.calls[1]["output_schema"],
                {
                    "type": "object",
                    "required": ["decision"],
                    "properties": {"decision": {"type": "string"}},
                },
            )
            self.assertEqual(result["action"], "start")
            self.assertEqual(result["purpose"], "demand-triage")
            self.assertEqual(result["parent_thread_id"], "thr-main")
            self.assertEqual(result["side_thread_id"], "thr-side-1")
            self.assertEqual(result["thread_action"], "start")
            self.assertEqual(result["turn_id"], "turn-side-started")
            self.assertEqual(result["thread_status"], "active")
            self.assertEqual(result["lease_registered"], True)

            rows = self._payload(instance_json)["side_threads"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["thread_id"], "thr-side-1")
            self.assertEqual(rows[0]["parent_thread_id"], "thr-main")
            self.assertEqual(rows[0]["purpose"], "demand-triage")
            self.assertEqual(rows[0]["turn_id"], "turn-side-started")
            self.assertEqual(rows[0]["turn_kind"], "work")

    def test_start_side_thread_passes_model_and_effort_to_isolated_thread_without_registry_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            result = self.lifecycle.start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Start side work",
                purpose="host_control.side",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
                model="gpt-5.4",
                model_reasoning_effort="high",
            )

            start_call = self.app_server.calls[0]
            self.assertEqual(start_call["helper"], "thread_start")
            self.assertEqual(start_call["model"], "gpt-5.4")
            self.assertEqual(start_call["model_reasoning_effort"], "high")
            self.assertEqual(result["model"], "gpt-5.4")
            self.assertEqual(result["model_reasoning_effort"], "high")

            row = self._payload(instance_json)["side_threads"][0]
            self.assertNotIn("model", row)
            self.assertNotIn("model_reasoning_effort", row)

    def test_start_side_thread_registers_hashed_capability_before_turn_and_forwards_thread_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            config_overrides = {
                "mcp_servers.buddyswitch-env.enabled_tools": [
                    "demand_sys__list",
                    "demand_sys__get",
                ],
                "mcp_servers.buddyswitch-demand-triage": {
                    "command": "/usr/bin/python3",
                    "env": {
                        "BUDDYSWITCH_DEMAND_TRIAGE_CAPABILITY": "raw-secret",
                    },
                },
            }

            def assert_capability_lease_is_visible() -> None:
                row = self._payload(instance_json)["side_threads"][0]
                self.assertEqual(row["capability_hash"], "sha256:abc123")
                self.assertEqual(row["capability_state"], "open")
                self.assertEqual(
                    row["binding"],
                    {
                        "source_key": "im.message.created:msg-1",
                        "attempt_id": "attempt-1",
                    },
                )
                self.assertNotIn("raw-secret", json.dumps(row, sort_keys=True))

            self.app_server.before_turn_start = assert_capability_lease_is_visible

            self.lifecycle.start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Resolve Demand ingress.",
                purpose="demand-triage",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
                config_overrides=config_overrides,
                capability_hash="sha256:abc123",
                binding={
                    "source_key": "im.message.created:msg-1",
                    "attempt_id": "attempt-1",
                },
            )

            self.assertEqual(
                self.app_server.calls[0]["config_overrides"],
                config_overrides,
            )
            persisted = instance_json.read_text(encoding="utf-8")
            self.assertNotIn("raw-secret", persisted)

    def test_start_side_thread_accepts_lease_consumed_before_turn_start_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            def consume_starting_lease() -> None:
                removed = self.registry.unregister_side_thread(
                    instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    side_thread_id="thr-side-1",
                )
                self.assertTrue(removed)

            self.app_server.before_turn_start = consume_starting_lease

            result = self.lifecycle.start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Finish immediately",
                purpose="demand-triage",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
            )

            self.assertEqual(result["turn_id"], "turn-side-started")
            self.assertEqual(result["thread_status"], "consumed")
            self.assertFalse(result["lease_registered"])
            self.assertTrue(result["lease_consumed"])
            self.assertEqual(self._payload(instance_json)["side_threads"], [])

    def test_start_side_thread_interrupts_known_turn_before_retryable_setup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.app_server.thread_read_error = RuntimeError("thread/read failed after turn start")

            with self.assertRaisesRegex(
                self.lifecycle.SideThreadLifecycleError,
                "thread/read failed after turn start",
            ) as raised:
                self.lifecycle.start_side_thread(
                    socket_path=self.socket_path,
                    instance_json=instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    text="Start side work",
                    purpose="demand-triage",
                    workspace_dir=self.workspace_dir,
                    shared_project_workspace_dir=self.project_workspace_dir,
                    permissions="buddyswitch-runtime",
                )

            self.assertTrue(raised.exception.retryable)
            self.assertEqual(
                [call["helper"] for call in self.app_server.calls],
                ["thread_start", "turn_start", "thread_read", "turn_interrupt"],
            )
            self.assertEqual(self.app_server.calls[-1]["thread_id"], "thr-side-1")
            self.assertEqual(self.app_server.calls[-1]["turn_id"], "turn-side-started")
            self.assertEqual(
                raised.exception.cleanup,
                {
                    "turn_interrupt_attempted": True,
                    "turn_interrupt_ok": True,
                    "lease_unregistered": True,
                },
            )
            self.assertEqual(self._payload(instance_json)["side_threads"], [])

    def test_start_side_thread_setup_failure_is_not_retryable_when_exact_turn_cannot_be_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self.app_server.thread_read_error = RuntimeError("thread/read failed after turn start")
            self.app_server.interrupt_error = RuntimeError("turn interrupt failed")

            with self.assertRaises(self.lifecycle.SideThreadLifecycleError) as raised:
                self.lifecycle.start_side_thread(
                    socket_path=self.socket_path,
                    instance_json=instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    text="Start side work",
                    purpose="demand-triage",
                    workspace_dir=self.workspace_dir,
                    shared_project_workspace_dir=self.project_workspace_dir,
                    permissions="buddyswitch-runtime",
                )

            self.assertFalse(raised.exception.retryable)
            self.assertTrue(raised.exception.cleanup["turn_interrupt_attempted"])
            self.assertFalse(raised.exception.cleanup["turn_interrupt_ok"])
            self.assertEqual(raised.exception.cleanup["turn_interrupt_error"], "turn interrupt failed")
            self.assertTrue(raised.exception.cleanup["lease_unregistered"])
            self.assertEqual(self._payload(instance_json)["side_threads"], [])

    def test_start_side_thread_none_model_and_effort_use_app_server_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            result = self.lifecycle.start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Start side work",
                purpose="host_control.side",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
            )

            start_call = self.app_server.calls[0]
            self.assertIsNone(start_call["model"])
            self.assertIsNone(start_call["model_reasoning_effort"])
            self.assertNotIn("model", result)
            self.assertNotIn("model_reasoning_effort", result)

    def test_send_to_active_side_thread_steers_stored_turn_without_turn_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self._seed_side_thread(instance_json)

            result = self.lifecycle.send_to_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                text="Continue side work",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual([call["helper"] for call in self.app_server.calls], ["thread_read", "turn_steer"])
            self.assertEqual(self.app_server.calls[1]["turn_id"], "turn-side-active")
            self.assertEqual(result["action"], "send")
            self.assertEqual(result["thread_action"], "steer")
            self.assertEqual(result["side_thread_id"], "thr-side-1")
            self.assertEqual(result["turn_id"], "turn-side-active-updated")
            self.assertEqual(result["expected_turn_id"], "turn-side-active")
            rows = self._payload(instance_json)["side_threads"]
            self.assertEqual(rows[0]["turn_id"], "turn-side-active-updated")

    def test_send_to_idle_side_thread_starts_turn_and_updates_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self._seed_side_thread(instance_json, turn_id="turn-side-old")
            self.app_server.thread_read_status = {"type": "idle"}

            result = self.lifecycle.send_to_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                text="Restart side work",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual([call["helper"] for call in self.app_server.calls], ["thread_read", "turn_start"])
            self.assertEqual(result["action"], "send")
            self.assertEqual(result["thread_action"], "start")
            self.assertEqual(result["turn_id"], "turn-side-started")
            rows = self._payload(instance_json)["side_threads"]
            self.assertEqual(rows[0]["turn_id"], "turn-side-started")

    def test_send_marks_external_submit_as_uncertain_when_lease_persistence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self._seed_side_thread(instance_json, turn_id="turn-side-old")
            self.app_server.thread_read_status = {"type": "idle"}
            original_update = self.registry.update_side_thread

            def fail_update(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("lease persistence failed")

            self.addCleanup(setattr, self.registry, "update_side_thread", original_update)
            self.registry.update_side_thread = fail_update

            with self.assertRaisesRegex(
                self.lifecycle.SideThreadLifecycleError,
                "lease persistence failed",
            ) as raised:
                self.lifecycle.send_to_side_thread(
                    socket_path=self.socket_path,
                    instance_json=instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    side_thread_id="thr-side-1",
                    text="Run Progress Check",
                    permissions="buddyswitch-runtime",
                    turn_kind="progress_check",
                )

            self.assertTrue(raised.exception.input_submitted)
            self.assertEqual(
                [call["helper"] for call in self.app_server.calls],
                ["thread_read", "turn_start"],
            )

    def test_cleanup_unregisters_lease_even_when_known_turn_interrupt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self._seed_side_thread(instance_json, turn_id="turn-side-active")
            self.app_server.interrupt_error = RuntimeError("turn already gone")

            result = self.lifecycle.cleanup_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
            )

            self.assertEqual([call["helper"] for call in self.app_server.calls], ["turn_interrupt"])
            self.assertEqual(self.app_server.calls[0]["turn_id"], "turn-side-active")
            self.assertEqual(result["action"], "cleanup")
            self.assertEqual(result["side_thread_id"], "thr-side-1")
            self.assertEqual(result["turn_id"], "turn-side-active")
            self.assertEqual(result["turn_interrupt_attempted"], True)
            self.assertEqual(result["turn_interrupt_ok"], False)
            self.assertEqual(result["turn_interrupt_error"], "turn already gone")
            self.assertEqual(result["lease_unregistered"], True)
            self.assertEqual(self._payload(instance_json)["side_threads"], [])
