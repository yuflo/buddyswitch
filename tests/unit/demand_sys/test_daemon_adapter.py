"""Demand-owned daemon adapter tests."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

import daemon_contracts
from env.domain import demand_sys
from env.repos import runtime_files
from tests.support.runtime import RuntimeWorkspaceTestCase


class _Runtime:
    def __init__(self, *, result: Any = None, error: BaseException | None = None) -> None:
        self.result = (
            {"action": "start", "turn_id": "turn-demand-1"}
            if result is None
            else result
        )
        self.error = error
        self.inputs: list[str] = []

    def input_actor(self, text: str) -> Any:
        self.inputs.append(text)
        if self.error is not None:
            raise self.error
        return self.result


class DemandSysDaemonAdapterTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        actor_id = self._runtime_actor_id(role="pm", label="daemon-demand-owner")
        instance_root = self._instance_root(actor_id)
        workspace_dir = instance_root / "workspace"
        self.context = daemon_contracts.DaemonContext(
            instance_json=instance_root / "instance.json",
            instance_payload={},
            actor_id=actor_id,
            instance_root=instance_root,
            main_thread_id="thr-demand-main",
            role="pm",
            workspace_dir=workspace_dir,
            project_workspace_dir=self.runtime_root,
            socket_path=instance_root / "runtime" / "app-server.sock",
        )
        self.actor_target = {"actor_id": actor_id, "role_id": "pm"}

    def _adapter(self) -> Any:
        self.assertIsNotNone(
            importlib.util.find_spec("demand_sys_daemon_adapter"),
            "demand_sys_daemon_adapter must exist",
        )
        return importlib.import_module("demand_sys_daemon_adapter")

    def _capture(
        self,
        runtime: _Runtime,
        *,
        message_id: str = "msg-adapter-1",
    ) -> dict[str, Any]:
        return self._adapter().capture_inbound(
            self.context,
            runtime,
            intake_key=f"im.message.created:{message_id}",
            description="Support user data CSV export.",
            detail="Support user data CSV export.",
            source_refs=[{
                "type": "im.message.created",
                "ref": {
                    "message_id": message_id,
                    "conversation_id": "conv-adapter-1",
                    "event_id": "imev-adapter-1",
                },
            }],
        )

    def _demand_rows(self) -> list[dict[str, Any]]:
        return demand_sys.list_demands(self.actor_target, state="all")

    def _task_rows(self) -> list[Path]:
        return sorted((runtime_files.OBJECTS_ROOT / "task-sys" / "tasks").glob("*.json"))

    def test_capture_creates_one_pending_demand_and_requests_fixed_actor_input(self) -> None:
        runtime = _Runtime()

        receipt = self._capture(runtime)

        self.assertEqual(
            receipt,
            {
                "demand_id": receipt["demand_id"],
                "revision": 1,
                "capture_state_changed": True,
                "pending_count": 1,
                "attention_requested": True,
                "actor_input": {"action": "start", "turn_id": "turn-demand-1"},
            },
        )
        rows = self._demand_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], receipt["demand_id"])
        self.assertEqual(rows[0]["intake_key"], "im.message.created:msg-adapter-1")
        self.assertEqual(rows[0]["revision"], 1)
        self.assertEqual(rows[0]["checked_revision"], 0)
        self.assertEqual(
            rows[0]["source_refs"],
            [{
                "type": "im.message.created",
                "ref": {
                    "message_id": "msg-adapter-1",
                    "conversation_id": "conv-adapter-1",
                    "event_id": "imev-adapter-1",
                },
            }],
        )
        self.assertEqual(runtime.inputs, [self._adapter().DEMAND_CHECK_PROMPT])
        prompt = self._adapter().DEMAND_CHECK_PROMPT
        lowered_prompt = prompt.lower()
        self.assertIn("canonicalize", lowered_prompt)
        self.assertIn("revise, absorb, keep independent, or cancel", lowered_prompt)
        for forbidden in (
            "task_sys",
            "task sys",
            "task lifecycle",
            "task selection",
            "organization",
            "parent",
            "dependency",
            "duplicate",
            "supersede",
            "relation",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered_prompt)
        self.assertEqual(self._task_rows(), [])

    def test_same_intake_replay_after_input_failure_retries_attention_without_duplicate(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "input unavailable"):
            self._capture(_Runtime(error=RuntimeError("input unavailable")))
        pending = self._demand_rows()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["checked_revision"], 0)

        runtime = _Runtime(result={"action": "steer", "turn_id": "turn-retry-1"})
        receipt = self._capture(runtime)

        self.assertEqual(len(self._demand_rows()), 1)
        self.assertEqual(receipt["demand_id"], pending[0]["id"])
        self.assertFalse(receipt["capture_state_changed"])
        self.assertTrue(receipt["attention_requested"])
        self.assertEqual(
            receipt["actor_input"],
            {"action": "steer", "turn_id": "turn-retry-1"},
        )
        self.assertEqual(self._task_rows(), [])

    def test_checked_replay_does_not_request_actor_input(self) -> None:
        created = self._capture(_Runtime())
        demand_sys.complete_check(
            self.actor_target,
            [{"demand_id": created["demand_id"], "revision": created["revision"]}],
        )
        runtime = _Runtime()

        replay = self._capture(runtime)

        self.assertEqual(replay["demand_id"], created["demand_id"])
        self.assertFalse(replay["capture_state_changed"])
        self.assertEqual(replay["pending_count"], 0)
        self.assertFalse(replay["attention_requested"])
        self.assertIsNone(replay["actor_input"])
        self.assertEqual(runtime.inputs, [])
        self.assertEqual(self._task_rows(), [])

    def test_malformed_actor_input_result_leaves_canonical_demand_pending(self) -> None:
        cases = (
            ("non-object", []),
            ("bad-action", {"action": "queued", "turn_id": "turn-bad"}),
            ("missing-turn", {"action": "start", "turn_id": ""}),
        )
        for index, (name, result) in enumerate(cases, start=1):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    self._capture(
                        _Runtime(result=result),
                        message_id=f"msg-malformed-{index}",
                    )

        rows = self._demand_rows()
        self.assertEqual(len(rows), len(cases))
        self.assertTrue(all(row["revision"] > row["checked_revision"] for row in rows))
        self.assertEqual(self._task_rows(), [])
