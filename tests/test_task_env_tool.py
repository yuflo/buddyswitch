#!/usr/bin/env python3
"""Task env.tool tests for task.current/propose/confirm behavior."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.domain import task_management  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TaskEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _taskbox_root(self, instance_root: Path, buddy: str) -> Path:
        return instance_root / "taskbox" / buddy

    def _taskbox_tasks_dir(self, instance_root: Path, buddy: str) -> Path:
        return self._taskbox_root(instance_root, buddy) / "tasks"

    def _history_file(self, instance_root: Path, buddy: str) -> Path:
        return self._taskbox_root(instance_root, buddy) / "history.md"

    def _task_file(self, instance_root: Path, buddy: str, task_id: str) -> Path:
        return self._taskbox_tasks_dir(instance_root, buddy) / f"{task_id}.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _make_instance_context(self, *, instance_id: str = "instance-a", buddy: str = "dev") -> dict[str, Any]:
        instance_id = self._runtime_instance_id(buddy=buddy, label=instance_id)
        instance_root = self._runtime_path(f"instances/{instance_id}")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        taskbox_root = self._taskbox_root(instance_root, buddy)
        (taskbox_root / "tasks").mkdir(parents=True, exist_ok=True)
        self._history_file(instance_root, buddy).write_text("", encoding="utf-8")
        instance_payload = {
            "instance_id": instance_id,
            "buddy": buddy,
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "browser_port": None,
            "updated_at": "2026-05-27T10:00:00+08:00",
        }
        instance_json = instance_root / "instance.json"
        self._write_json(instance_json, instance_payload)
        return {
            "instance_id": instance_id,
            "instance_root": instance_root,
            "instance_json": instance_json,
            "instance_payload": instance_payload,
            "buddy": buddy,
        }

    def _dispatch(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        instance_id = self._runtime_instance_id(buddy=buddy, label=instance_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-task-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": "task",
                "action": action,
                "args": args,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        payload: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
        return payload

    def _seed_taskbox_task(
        self,
        *,
        instance_root: Path,
        buddy: str,
        task_id: str,
        title: str,
        summary: str = "",
        body: str = "Seed task body.",
        status: str = "active",
        priority: str = "normal",
        track_id: str | None = None,
        refs: list[dict[str, object]] | None = None,
        created_at: str = "2026-05-27T09:00:00+08:00",
        updated_at: str = "2026-05-27T09:00:00+08:00",
        closed_at: str | None = None,
    ) -> None:
        if closed_at is None and status in {"done", "archived"}:
            closed_at = updated_at
        self._write_json(
            self._task_file(instance_root, buddy, task_id),
            {
                "id": task_id,
                "owner_buddy": buddy,
                "title": title,
                "summary": summary,
                "body": body,
                "status": status,
                "priority": priority,
                "track_id": track_id,
                "refs": refs or [],
                "created_at": created_at,
                "updated_at": updated_at,
                "closed_at": closed_at,
            },
        )

    def _json_field(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

    def _history_line(self, *, event: str, task_id: str, fields: dict[str, object] | None = None) -> str:
        parts = [f"{key}={self._json_field(value)}" for key, value in sorted((fields or {}).items())]
        suffix = f" {' '.join(parts)}" if parts else ""
        return f"- 2026-05-27T10:00:00+08:00 {event} {task_id}{suffix}"

    def _set_current_task(self, *, instance_root: Path, buddy: str, task_id: str) -> None:
        self._history_file(instance_root, buddy).write_text(
            self._history_line(event="task.create", task_id=task_id) + "\n",
            encoding="utf-8",
        )

    def _taskbox_snapshot(self, instance_root: Path, buddy: str) -> dict[str, object]:
        tasks_dir = self._taskbox_tasks_dir(instance_root, buddy)
        return {
            "history": self._history_file(instance_root, buddy).read_text(encoding="utf-8"),
            "tasks": {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(tasks_dir.glob("*.json"))
            },
        }

    def _start_task_args(self, title: str = "Clean runtime environment") -> dict[str, object]:
        return {
            "type": "start",
            "task": {
                "title": title,
                "summary": "Refine task input context.",
                "body": "Detailed body for the task.",
                "priority": "normal",
                "refs": [],
            },
            "reason": "User introduced a new task.",
            "evidence": "User asked to design task input context.",
        }

    def test_task_current_returns_canonical_snapshot_without_history_mutation(self) -> None:
        instance = self._make_instance_context(instance_id="instance-current", buddy="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-0001-alpha",
            title="Alpha",
            summary="Older task.",
        )
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-0002-beta",
            title="Beta",
            summary="Current task.",
            body="Detailed beta body.",
        )
        self._history_file(instance["instance_root"], "dev").write_text(
            "\n".join(
                [
                    self._history_line(event="task.create", task_id="task-0001-alpha"),
                    self._history_line(event="task.create", task_id="task-0002-beta"),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        before_history = self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8")
        expected = task_management.current_snapshot(
            active_buddy="dev",
            instance_json=instance["instance_json"],
            instance_payload=instance["instance_payload"],
        )

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-current",
            buddy="dev",
            action="current",
            args={},
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("action"), "task.current")
        self.assertIs(payload.get("state_changed"), False)
        self.assertEqual(payload.get("durability"), "none")
        self.assertEqual(payload["snapshot"]["current_task"]["id"], expected["current_task"]["id"])
        self.assertEqual(self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"), before_history)

    def test_task_propose_start_creates_current_task_with_body(self) -> None:
        instance = self._make_instance_context(instance_id="instance-start", buddy="dev")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-start",
            buddy="dev",
            action="propose",
            args=self._start_task_args(),
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("action"), "task.propose")
        self.assertIs(payload.get("state_changed"), True)
        task_id = str(payload["task"]["id"])
        self.assertEqual(task_id, "task-0001-clean-runtime-environment")
        stored = json.loads(self._task_file(instance["instance_root"], "dev", task_id).read_text(encoding="utf-8"))
        self.assertEqual(stored["body"], "Detailed body for the task.")
        self.assertEqual(stored["status"], "active")
        self.assertIn(f"task.create {task_id}", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

        current = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-start",
            buddy="dev",
            action="current",
            args={},
        )
        self.assertEqual(current["snapshot"]["current_task"]["id"], task_id)

    def test_task_propose_start_rejects_when_active_task_exists_without_mutation(self) -> None:
        instance = self._make_instance_context(instance_id="instance-start-reject", buddy="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-0001-active",
            title="Active",
        )
        self._set_current_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-active")
        before = self._taskbox_snapshot(instance["instance_root"], "dev")

        rejected = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-start-reject",
            buddy="dev",
            action="propose",
            args=self._start_task_args("Replacement task"),
        )

        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertIs(rejected.get("state_changed"), False)
        self.assertIn("task.propose(type=switch)", json.dumps(rejected, ensure_ascii=True))
        self.assertEqual(self._taskbox_snapshot(instance["instance_root"], "dev"), before)

    def test_task_propose_switch_creates_pending_confirmation_without_changing_current(self) -> None:
        instance = self._make_instance_context(instance_id="instance-switch", buddy="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0002-target", title="Target")
        self._set_current_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-switch",
            buddy="dev",
            action="propose",
            args={
                "type": "switch",
                "target": {"mode": "existing", "task_id": "task-0002-target"},
                "reason": "User asked to switch.",
                "evidence": "Switch to target.",
            },
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        pending = payload["snapshot"]["pending_confirmation"]
        self.assertEqual(pending["confirmation_id"], "confirm-0001")
        self.assertEqual(payload["snapshot"]["current_task"]["id"], "task-0001-current")
        self.assertIn("task.switch.requested task-0001-current", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

        current = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-switch",
            buddy="dev",
            action="current",
            args={},
        )
        self.assertEqual(current["snapshot"]["current_task"]["id"], "task-0001-current")
        self.assertEqual(current["snapshot"]["pending_confirmation"]["confirmation_id"], "confirm-0001")

    def test_task_propose_switch_to_new_target_defers_task_creation_until_confirm(self) -> None:
        instance = self._make_instance_context(instance_id="instance-switch-new", buddy="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._set_current_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-switch-new",
            buddy="dev",
            action="propose",
            args={
                "type": "switch",
                "target": {
                    "mode": "new",
                    "task": {
                        "title": "Next Task",
                        "summary": "Switch later.",
                        "body": "New task body.",
                        "priority": "high",
                        "refs": [],
                    },
                },
                "reason": "User asked for a different task.",
                "evidence": "Next task request.",
            },
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertEqual(payload["snapshot"]["pending_confirmation"]["target"]["mode"], "new")
        self.assertFalse(self._task_file(instance["instance_root"], "dev", "task-0002-next-task").exists())

    def test_task_confirm_accepts_existing_pending_switch(self) -> None:
        instance = self._make_instance_context(instance_id="instance-confirm-existing", buddy="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0002-target", title="Target")
        self._set_current_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current")
        proposed = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-confirm-existing",
            buddy="dev",
            action="propose",
            args={
                "type": "switch",
                "target": {"mode": "existing", "task_id": "task-0002-target"},
                "reason": "Switch.",
                "evidence": "Switch.",
            },
        )

        accepted = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-confirm-existing",
            buddy="dev",
            action="confirm",
            args={
                "confirmation_id": proposed["snapshot"]["pending_confirmation"]["confirmation_id"],
                "decision": "accept",
                "reason": "User confirmed.",
            },
        )

        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual(accepted["snapshot"]["current_task"]["id"], "task-0002-target")
        self.assertIsNone(accepted["snapshot"]["pending_confirmation"])
        self.assertIn("task.switch.confirmed task-0002-target", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_confirm_accepts_new_pending_switch_and_creates_target(self) -> None:
        instance = self._make_instance_context(instance_id="instance-confirm-new", buddy="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._set_current_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current")
        proposed = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-confirm-new",
            buddy="dev",
            action="propose",
            args={
                "type": "switch",
                "target": {
                    "mode": "new",
                    "task": {
                        "title": "Next Task",
                        "summary": "Switch later.",
                        "body": "New task body.",
                        "priority": "high",
                        "refs": [],
                    },
                },
                "reason": "Switch.",
                "evidence": "Switch.",
            },
        )

        accepted = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-confirm-new",
            buddy="dev",
            action="confirm",
            args={
                "confirmation_id": proposed["snapshot"]["pending_confirmation"]["confirmation_id"],
                "decision": "accept",
                "reason": "User confirmed.",
            },
        )

        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual(accepted["snapshot"]["current_task"]["id"], "task-0002-next-task")
        self.assertEqual(json.loads(self._task_file(instance["instance_root"], "dev", "task-0002-next-task").read_text(encoding="utf-8"))["body"], "New task body.")
        self.assertIsNone(accepted["snapshot"]["pending_confirmation"])
        self.assertIn("task.switch.confirmed task-0002-next-task", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_confirm_rejects_pending_switch_without_changing_current(self) -> None:
        instance = self._make_instance_context(instance_id="instance-confirm-reject", buddy="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._seed_taskbox_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0002-target", title="Target")
        self._set_current_task(instance_root=instance["instance_root"], buddy="dev", task_id="task-0001-current")
        proposed = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-confirm-reject",
            buddy="dev",
            action="propose",
            args={
                "type": "switch",
                "target": {"mode": "existing", "task_id": "task-0002-target"},
                "reason": "Switch.",
                "evidence": "Switch.",
            },
        )

        rejected = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-confirm-reject",
            buddy="dev",
            action="confirm",
            args={
                "confirmation_id": proposed["snapshot"]["pending_confirmation"]["confirmation_id"],
                "decision": "reject",
                "reason": "Stay focused.",
            },
        )

        self.assertTrue(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected["snapshot"]["current_task"]["id"], "task-0001-current")
        self.assertIsNone(rejected["snapshot"]["pending_confirmation"])
        self.assertIn("task.switch.rejected task-0001-current", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_propose_finish_and_block_update_current_task(self) -> None:
        finish_instance = self._make_instance_context(instance_id="instance-finish", buddy="dev")
        self._seed_taskbox_task(instance_root=finish_instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._set_current_task(instance_root=finish_instance["instance_root"], buddy="dev", task_id="task-0001-current")

        finished = self._dispatch(
            instance_json=finish_instance["instance_json"],
            instance_id="instance-finish",
            buddy="dev",
            action="propose",
            args={
                "type": "finish",
                "task_id": "task-0001-current",
                "reason": "Work is complete.",
                "evidence": "Focused tests pass.",
            },
        )
        self.assertTrue(finished.get("ok"), msg=finished)
        stored_finished = json.loads(self._task_file(finish_instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        self.assertEqual(stored_finished["status"], "done")
        self.assertIsNotNone(stored_finished["closed_at"])
        self.assertIn("task.close task-0001-current", self._history_file(finish_instance["instance_root"], "dev").read_text(encoding="utf-8"))

        block_instance = self._make_instance_context(instance_id="instance-block", buddy="dev")
        self._seed_taskbox_task(instance_root=block_instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._set_current_task(instance_root=block_instance["instance_root"], buddy="dev", task_id="task-0001-current")
        blocked = self._dispatch(
            instance_json=block_instance["instance_json"],
            instance_id="instance-block",
            buddy="dev",
            action="propose",
            args={
                "type": "block",
                "task_id": "task-0001-current",
                "reason": "External input needed.",
                "evidence": "User decision needed.",
            },
        )
        self.assertTrue(blocked.get("ok"), msg=blocked)
        stored_blocked = json.loads(self._task_file(block_instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        self.assertEqual(stored_blocked["status"], "blocked")
        self.assertIsNone(stored_blocked["closed_at"])
        self.assertIn("task.block task-0001-current", self._history_file(block_instance["instance_root"], "dev").read_text(encoding="utf-8"))

        before = self._taskbox_snapshot(block_instance["instance_root"], "dev")
        mismatch = self._dispatch(
            instance_json=block_instance["instance_json"],
            instance_id="instance-block",
            buddy="dev",
            action="propose",
            args={
                "type": "finish",
                "task_id": "task-9999-other",
                "reason": "Wrong task.",
                "evidence": "Wrong task.",
            },
        )
        self.assertFalse(mismatch.get("ok"), msg=mismatch)
        self.assertEqual(self._taskbox_snapshot(block_instance["instance_root"], "dev"), before)

    def test_invalid_payloads_do_not_mutate_task_docs_or_history(self) -> None:
        invalid_instance = self._make_instance_context(instance_id="instance-invalid", buddy="dev")
        self._seed_taskbox_task(
            instance_root=invalid_instance["instance_root"],
            buddy="dev",
            task_id="task-0001-current",
            title="Current",
        )
        self._set_current_task(instance_root=invalid_instance["instance_root"], buddy="dev", task_id="task-0001-current")

        cases = (
            ("propose", {"type": "unknown", "reason": "Bad.", "evidence": "Bad."}),
            ("propose", {"type": "start", "task": {"body": "Missing title."}, "reason": "Bad.", "evidence": "Bad."}),
            ("propose", {"type": "start", "task": {"title": "Missing body"}, "reason": "Bad.", "evidence": "Bad."}),
            ("propose", {"type": "switch", "reason": "Bad.", "evidence": "Bad."}),
            ("confirm", {"confirmation_id": "confirm-9999", "decision": "accept"}),
            ("propose", {**self._start_task_args("Visibility"), "visibility": "public"}),
            ("propose", {**self._start_task_args("Template"), "task": {"title": "Template", "body": "Body", "template": "note"}}),
            ("propose", {**self._start_task_args("Source refs"), "task": {"title": "Source refs", "body": "Body", "source_refs": []}}),
        )
        for action, args in cases:
            with self.subTest(action=action, args=args):
                before = self._taskbox_snapshot(invalid_instance["instance_root"], "dev")
                rejected = self._dispatch(
                    instance_json=invalid_instance["instance_json"],
                    instance_id="instance-invalid",
                    buddy="dev",
                    action=action,
                    args=args,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertIs(rejected.get("state_changed"), False, msg=rejected)
                self.assertEqual(self._taskbox_snapshot(invalid_instance["instance_root"], "dev"), before)

        mismatch_instance = self._make_instance_context(instance_id="instance-confirm-mismatch", buddy="dev")
        self._seed_taskbox_task(instance_root=mismatch_instance["instance_root"], buddy="dev", task_id="task-0001-current", title="Current")
        self._seed_taskbox_task(instance_root=mismatch_instance["instance_root"], buddy="dev", task_id="task-0002-target", title="Target")
        self._set_current_task(instance_root=mismatch_instance["instance_root"], buddy="dev", task_id="task-0001-current")
        proposed = self._dispatch(
            instance_json=mismatch_instance["instance_json"],
            instance_id="instance-confirm-mismatch",
            buddy="dev",
            action="propose",
            args={
                "type": "switch",
                "target": {"mode": "existing", "task_id": "task-0002-target"},
                "reason": "Switch.",
                "evidence": "Switch.",
            },
        )
        self.assertTrue(proposed.get("ok"), msg=proposed)
        before = self._taskbox_snapshot(mismatch_instance["instance_root"], "dev")
        mismatch = self._dispatch(
            instance_json=mismatch_instance["instance_json"],
            instance_id="instance-confirm-mismatch",
            buddy="dev",
            action="confirm",
            args={"confirmation_id": "confirm-9999", "decision": "accept"},
        )
        self.assertFalse(mismatch.get("ok"), msg=mismatch)
        self.assertIs(mismatch.get("state_changed"), False, msg=mismatch)
        self.assertEqual(self._taskbox_snapshot(mismatch_instance["instance_root"], "dev"), before)


if __name__ == "__main__":
    unittest.main()
