#!/usr/bin/env python3
"""Contract tests for the side-thread lifecycle owner."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from itertools import count
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_ROOT = ROOT / "tools" / "launcher"
LIFECYCLE_PATH = LAUNCHER_ROOT / "side_thread_lifecycle.py"
REGISTRY_PATH = LAUNCHER_ROOT / "side_thread_registry.py"
FAKE_CODEX_PATH = ROOT / "tests" / "helpers" / "fake_codex.py"
MODULE_COUNTER = count()


def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_registry() -> Any:
    return _load_module(REGISTRY_PATH, f"buddyswitch_side_thread_registry_{next(MODULE_COUNTER)}")


def load_lifecycle(app_server: types.ModuleType, registry: Any) -> Any:
    module_name = f"buddyswitch_side_thread_lifecycle_{next(MODULE_COUNTER)}"
    original_modules = {
        "app_server": sys.modules.get("app_server"),
        "side_thread_registry": sys.modules.get("side_thread_registry"),
    }
    original_path = list(sys.path)
    sys.modules["app_server"] = app_server
    sys.modules["side_thread_registry"] = registry
    sys.path.insert(0, str(LAUNCHER_ROOT))
    try:
        return _load_module(LIFECYCLE_PATH, module_name)
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        sys.path[:] = original_path


class FakeAppServer(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("app_server")
        self.calls: list[dict[str, Any]] = []
        self.thread_read_status: dict[str, object] = {"type": "active", "activeFlags": []}
        self.interrupt_error: Exception | None = None
        self.AppServerProtocolError = RuntimeError
        self.AppServerUnavailableError = RuntimeError

    def side_boundary_prompt_item(self) -> dict[str, object]:
        return {"type": "message", "role": "system", "content": [{"type": "input_text", "text": "side boundary"}]}

    def thread_fork(
        self,
        socket_path: Path,
        parent_thread_id: str,
        *,
        workspace_dir: Path,
        shared_project_workspace_dir: Path,
        permissions: str,
        model: str | None = None,
        model_reasoning_effort: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "helper": "thread_fork",
                "socket_path": socket_path,
                "parent_thread_id": parent_thread_id,
                "workspace_dir": workspace_dir,
                "shared_project_workspace_dir": shared_project_workspace_dir,
                "permissions": permissions,
                "model": model,
                "model_reasoning_effort": model_reasoning_effort,
            }
        )
        return {"thread": {"id": "thr-side-1"}}

    def thread_inject_items(self, socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, object]:
        self.calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
        return {"ok": True}

    def thread_read(self, socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
        self.calls.append({"helper": "thread_read", "socket_path": socket_path, "thread_id": thread_id, "include_turns": include_turns})
        return {"thread": {"id": thread_id, "status": self.thread_read_status}}

    def turn_start(self, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
        self.calls.append({"helper": "turn_start", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
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


for _name in ("side_start", "side_close", "input_turn", "active_turn_id", "thread_turns_list"):
    setattr(FakeAppServer, _name, FakeAppServer._forbidden)


class FakeCodexEphemeralBoundaryTests(unittest.TestCase):
    def test_thread_turns_list_rejects_ephemeral_side_thread(self) -> None:
        fake_codex = _load_module(FAKE_CODEX_PATH, f"buddyswitch_fake_codex_{next(MODULE_COUNTER)}")
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
        purpose: str = "daemon.side_triage",
        task_id: str | None = None,
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
        if task_id is not None:
            row["task_id"] = task_id
        payload["side_threads"] = [row]
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def test_start_side_thread_registers_lease_with_started_turn_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)

            result = self.lifecycle.start_side_thread(
                socket_path=self.socket_path,
                instance_json=instance_json,
                actor_id="act-dev-side",
                parent_thread_id="thr-main",
                text="Start side work",
                purpose="task_sys.side_frame",
                workspace_dir=self.workspace_dir,
                shared_project_workspace_dir=self.project_workspace_dir,
                permissions="buddyswitch-runtime",
                task_id="task-user-input-abc123",
            )

            self.assertEqual([call["helper"] for call in self.app_server.calls], ["thread_fork", "thread_inject_items", "turn_start"])
            self.assertEqual(result["action"], "start")
            self.assertEqual(result["purpose"], "task_sys.side_frame")
            self.assertEqual(result["parent_thread_id"], "thr-main")
            self.assertEqual(result["side_thread_id"], "thr-side-1")
            self.assertEqual(result["thread_action"], "start")
            self.assertEqual(result["turn_id"], "turn-side-started")
            self.assertEqual(result["lease_registered"], True)

            rows = self._payload(instance_json)["side_threads"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["thread_id"], "thr-side-1")
            self.assertEqual(rows[0]["parent_thread_id"], "thr-main")
            self.assertEqual(rows[0]["purpose"], "task_sys.side_frame")
            self.assertEqual(rows[0]["task_id"], "task-user-input-abc123")
            self.assertEqual(rows[0]["turn_id"], "turn-side-started")

    def test_start_side_thread_passes_model_and_effort_to_fork_without_registry_persistence(self) -> None:
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

            fork_call = self.app_server.calls[0]
            self.assertEqual(fork_call["helper"], "thread_fork")
            self.assertEqual(fork_call["model"], "gpt-5.4")
            self.assertEqual(fork_call["model_reasoning_effort"], "high")
            self.assertEqual(result["model_source"], "override")
            self.assertEqual(result["model"], "gpt-5.4")
            self.assertEqual(result["model_reasoning_effort_source"], "override")
            self.assertEqual(result["model_reasoning_effort"], "high")
            self.assertEqual(result["model_config_durability"], "thread_fork_only")

            row = self._payload(instance_json)["side_threads"][0]
            self.assertNotIn("model", row)
            self.assertNotIn("model_reasoning_effort", row)

    def test_start_side_thread_none_model_and_effort_mean_parent_inheritance(self) -> None:
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

            fork_call = self.app_server.calls[0]
            self.assertIsNone(fork_call["model"])
            self.assertIsNone(fork_call["model_reasoning_effort"])
            self.assertEqual(result["model_source"], "parent_thread")
            self.assertEqual(result["model_reasoning_effort_source"], "parent_thread")
            self.assertEqual(result["model_config_durability"], "thread_fork_only")
            self.assertNotIn("model", result)
            self.assertNotIn("model_reasoning_effort", result)

    def test_find_or_start_rejects_model_or_effort_when_existing_side_thread_would_be_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(temp_root)
            self._seed_side_thread(instance_json)

            with self.assertRaisesRegex(
                self.lifecycle.SideThreadLifecycleError,
                "only applies when starting a new side thread",
            ):
                self.lifecycle.find_or_start_side_thread(
                    socket_path=self.socket_path,
                    instance_json=instance_json,
                    actor_id="act-dev-side",
                    parent_thread_id="thr-main",
                    text="Follow up",
                    purpose="daemon.side_triage",
                    workspace_dir=self.workspace_dir,
                    shared_project_workspace_dir=self.project_workspace_dir,
                    permissions="buddyswitch-runtime",
                    model="gpt-5.4",
                )

            self.assertEqual(self.app_server.calls, [])

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


if __name__ == "__main__":
    unittest.main()
