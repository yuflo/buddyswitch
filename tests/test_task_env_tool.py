#!/usr/bin/env python3
"""Task env.tool tests for actor Task Management System behavior."""

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
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TaskEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _taskbox_root(self, instance_root: Path, role: str) -> Path:
        return instance_root / "taskbox" / role

    def _taskbox_tasks_dir(self, instance_root: Path, role: str) -> Path:
        return self._taskbox_root(instance_root, role) / "tasks"

    def _history_file(self, instance_root: Path, role: str) -> Path:
        return self._taskbox_root(instance_root, role) / "history.md"

    def _task_file(self, instance_root: Path, role: str, task_id: str) -> Path:
        return self._taskbox_tasks_dir(instance_root, role) / f"{task_id}.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _make_instance_context(self, *, actor_id: str = "instance-a", role: str = "dev") -> dict[str, Any]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self._runtime_path(f"instances/{actor_id}")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        taskbox_root = self._taskbox_root(instance_root, role)
        (taskbox_root / "tasks").mkdir(parents=True, exist_ok=True)
        self._history_file(instance_root, role).write_text("", encoding="utf-8")
        instance_payload = {
            "actor_id": actor_id,
            "role": role,
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "browser_port": None,
            "updated_at": "2026-06-06T10:00:00+08:00",
        }
        instance_json = instance_root / "instance.json"
        self._write_json(instance_json, instance_payload)
        return {
            "actor_id": actor_id,
            "instance_root": instance_root,
            "instance_json": instance_json,
            "instance_payload": instance_payload,
            "role": role,
        }

    def _actor_payload(self, *, instance_root: Path, role: str) -> dict[str, str]:
        return {"actor_id": instance_root.name, "role_id": role}

    def _dispatch(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        role: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-task-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": actor_id,
                "active_role": role,
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
        role: str,
        task_id: str,
        title: str,
        summary: str = "",
        body: str = "Seed task body.",
        status: str = "captured",
        priority: str = "normal",
        origin: dict[str, object] | None = None,
        refs: list[dict[str, object]] | None = None,
        progress_summary: str = "",
        created_at: str = "2026-06-06T09:00:00+08:00",
        updated_at: str = "2026-06-06T09:00:00+08:00",
        closed_at: str | None = None,
    ) -> None:
        if closed_at is None and status in {"done", "archived"}:
            closed_at = updated_at
        self._write_json(
            self._task_file(instance_root, role, task_id),
            {
                "id": task_id,
                "owner_actor": self._actor_payload(instance_root=instance_root, role=role),
                "title": title,
                "summary": summary,
                "body": body,
                "status": status,
                "priority": priority,
                "origin": origin or {"type": "manual"},
                "refs": refs or [],
                "progress_summary": progress_summary,
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
        return f"- 2026-06-06T10:00:00+08:00 {event} {task_id}{suffix}"

    def _set_current_task(self, *, instance_root: Path, role: str, task_id: str) -> None:
        self._history_file(instance_root, role).write_text(
            self._history_line(event="task.selected", task_id=task_id, fields={"reason": "seed current"}) + "\n",
            encoding="utf-8",
        )

    def _taskbox_snapshot(self, instance_root: Path, role: str) -> dict[str, object]:
        tasks_dir = self._taskbox_tasks_dir(instance_root, role)
        return {
            "history": self._history_file(instance_root, role).read_text(encoding="utf-8"),
            "tasks": {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(tasks_dir.glob("*.json"))
            },
        }

    def _task_payload(self, title: str = "Clean runtime environment") -> dict[str, object]:
        return {
            "title": title,
            "summary": "Refine task input context.",
            "body": "Detailed body for the task.",
            "priority": "normal",
            "origin": {"type": "user_input", "id": "turn-1"},
            "refs": [{"type": "track", "id": "track-alpha", "label": "Alpha"}],
        }

    def test_task_current_returns_task_view_model_without_mutation(self) -> None:
        instance = self._make_instance_context(actor_id="instance-current", role="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            role="dev",
            task_id="task-0001-alpha",
            title="Alpha",
            status="active",
            summary="Current task.",
            progress_summary="Investigating task context.",
        )
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            role="dev",
            task_id="task-0002-beta",
            title="Beta",
            status="captured",
            summary="Shelf task.",
        )
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-alpha")
        before = self._taskbox_snapshot(instance["instance_root"], "dev")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-current",
            role="dev",
            action="current",
            args={},
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("action"), "task.current")
        self.assertIs(payload.get("state_changed"), False)
        self.assertEqual(payload.get("durability"), "none")
        view = payload["view"]
        self.assertEqual(view["current_anchor"]["id"], "task-0001-alpha")
        self.assertEqual(view["task_state"], "active")
        self.assertEqual([row["id"] for row in view["shelf"]], ["task-0002-beta"])
        self.assertIn("capture", view["available_actions"])
        self.assertIn("checkout", view["available_actions"])
        self.assertEqual(view["checkout_cue"]["choices"], ["continue", "finish", "block"])
        self.assertEqual(self._taskbox_snapshot(instance["instance_root"], "dev"), before)

    def test_task_capture_creates_shelf_task_without_changing_current(self) -> None:
        instance = self._make_instance_context(actor_id="instance-capture", role="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            role="dev",
            task_id="task-0001-current",
            title="Current",
            status="active",
        )
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-capture",
            role="dev",
            action="capture",
            args={
                "task": self._task_payload("Captured Follow Up"),
                "reason": "User introduced related work for later.",
                "evidence": "User asked to remember the follow-up.",
            },
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("action"), "task.capture")
        self.assertIs(payload.get("state_changed"), True)
        task_id = str(payload["task"]["id"])
        self.assertEqual(task_id, "task-0002-captured-follow-up")
        stored = json.loads(self._task_file(instance["instance_root"], "dev", task_id).read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "captured")
        self.assertEqual(stored["origin"], {"type": "user_input", "id": "turn-1"})
        self.assertEqual(payload["view"]["current_anchor"]["id"], "task-0001-current")
        self.assertIn(task_id, [row["id"] for row in payload["view"]["shelf"]])
        self.assertIn(f"task.captured {task_id}", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_select_only_selects_captured_task_when_no_active_anchor_exists(self) -> None:
        instance = self._make_instance_context(actor_id="instance-select", role="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            role="dev",
            task_id="task-0001-captured",
            title="Captured",
            status="captured",
        )

        selected = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-select",
            role="dev",
            action="select",
            args={"task_id": "task-0001-captured", "reason": "Resume shelf work."},
        )

        self.assertTrue(selected.get("ok"), msg=selected)
        self.assertEqual(selected["view"]["current_anchor"]["id"], "task-0001-captured")
        stored = json.loads(self._task_file(instance["instance_root"], "dev", "task-0001-captured").read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "active")
        self.assertIn("task.selected task-0001-captured", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            role="dev",
            task_id="task-0002-other",
            title="Other",
            status="captured",
        )
        before = self._taskbox_snapshot(instance["instance_root"], "dev")
        rejected = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-select",
            role="dev",
            action="select",
            args={"task_id": "task-0002-other", "reason": "Cannot skip switch."},
        )

        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertIs(rejected.get("state_changed"), False)
        self.assertIn("active current anchor", str(rejected.get("why_blocked")))
        self.assertEqual(self._taskbox_snapshot(instance["instance_root"], "dev"), before)

        blocked_instance = self._make_instance_context(actor_id="instance-select-blocked", role="dev")
        self._seed_taskbox_task(
            instance_root=blocked_instance["instance_root"],
            role="dev",
            task_id="task-0001-blocked",
            title="Blocked",
            status="blocked",
        )
        resumed = self._dispatch(
            instance_json=blocked_instance["instance_json"],
            actor_id="instance-select-blocked",
            role="dev",
            action="select",
            args={"task_id": "task-0001-blocked", "reason": "Blocker cleared."},
        )
        self.assertTrue(resumed.get("ok"), msg=resumed)
        self.assertEqual(resumed["view"]["current_anchor"]["id"], "task-0001-blocked")
        stored_resumed = json.loads(self._task_file(blocked_instance["instance_root"], "dev", "task-0001-blocked").read_text(encoding="utf-8"))
        self.assertEqual(stored_resumed["status"], "active")

    def test_task_switch_request_and_confirm_accept_change_current_anchor(self) -> None:
        instance = self._make_instance_context(actor_id="instance-switch", role="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0002-target", title="Target", status="captured")
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current")

        requested = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-switch",
            role="dev",
            action="switch_request",
            args={
                "target": {"mode": "existing", "task_id": "task-0002-target"},
                "reason": "User asked to switch.",
                "evidence": "Switch to target.",
            },
        )

        self.assertTrue(requested.get("ok"), msg=requested)
        self.assertEqual(requested["view"]["current_anchor"]["id"], "task-0001-current")
        self.assertEqual(requested["view"]["pending_switch"]["confirmation_id"], "confirm-0001")
        self.assertIn("task.switch.requested task-0001-current", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

        accepted = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-switch",
            role="dev",
            action="switch_confirm",
            args={
                "confirmation_id": "confirm-0001",
                "decision": "accept",
                "reason": "User confirmed.",
            },
        )

        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual(accepted["view"]["current_anchor"]["id"], "task-0002-target")
        self.assertIsNone(accepted["view"]["pending_switch"])
        current = json.loads(self._task_file(instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        target = json.loads(self._task_file(instance["instance_root"], "dev", "task-0002-target").read_text(encoding="utf-8"))
        self.assertEqual(current["status"], "captured")
        self.assertEqual(target["status"], "active")
        self.assertIn("task.switch.confirmed task-0002-target", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_switch_request_to_new_target_defers_creation_until_confirm(self) -> None:
        instance = self._make_instance_context(actor_id="instance-switch-new", role="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current")

        requested = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-switch-new",
            role="dev",
            action="switch_request",
            args={
                "target": {"mode": "new", "task": self._task_payload("Next Task")},
                "reason": "User asked for a different task.",
                "evidence": "Next task request.",
            },
        )

        self.assertTrue(requested.get("ok"), msg=requested)
        self.assertFalse(self._task_file(instance["instance_root"], "dev", "task-0002-next-task").exists())

        accepted = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-switch-new",
            role="dev",
            action="switch_confirm",
            args={"confirmation_id": "confirm-0001", "decision": "accept", "reason": "Confirmed."},
        )

        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual(accepted["view"]["current_anchor"]["id"], "task-0002-next-task")
        self.assertTrue(self._task_file(instance["instance_root"], "dev", "task-0002-next-task").exists())
        self.assertIn("task-0002-next-task", accepted.get("created_ids", []))

    def test_task_switch_confirm_reject_keeps_current_anchor(self) -> None:
        instance = self._make_instance_context(actor_id="instance-switch-reject", role="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0002-target", title="Target", status="captured")
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current")
        requested = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-switch-reject",
            role="dev",
            action="switch_request",
            args={"target": {"mode": "existing", "task_id": "task-0002-target"}, "reason": "Switch.", "evidence": "Switch."},
        )
        self.assertTrue(requested.get("ok"), msg=requested)

        rejected = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-switch-reject",
            role="dev",
            action="switch_confirm",
            args={"confirmation_id": "confirm-0001", "decision": "reject", "reason": "Stay focused."},
        )

        self.assertTrue(rejected.get("ok"), msg=rejected)
        self.assertIs(rejected.get("state_changed"), True)
        self.assertEqual(rejected["view"]["current_anchor"]["id"], "task-0001-current")
        self.assertIsNone(rejected["view"]["pending_switch"])
        self.assertIn("task.switch.rejected task-0001-current", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_progress_appends_evidence_refs_and_updates_current_task(self) -> None:
        instance = self._make_instance_context(actor_id="instance-progress", role="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-progress",
            role="dev",
            action="progress",
            args={
                "task_id": "task-0001-current",
                "summary": "Implemented task tests.",
                "evidence": "Focused tests cover progress.",
                "refs": [{"type": "artifact", "id": "art-1", "label": "Evidence"}],
            },
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        stored = json.loads(self._task_file(instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        self.assertEqual(stored["progress_summary"], "Implemented task tests.")
        self.assertEqual(stored["refs"], [{"type": "artifact", "id": "art-1", "label": "Evidence"}])
        self.assertIn("task.progress.appended task-0001-current", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))
        self.assertIn("Focused tests cover progress.", json.dumps(payload["view"]["recent_evidence"], ensure_ascii=True))

    def test_task_checkout_continue_finish_and_block_follow_evidence_rules(self) -> None:
        continue_instance = self._make_instance_context(actor_id="instance-continue", role="dev")
        self._seed_taskbox_task(instance_root=continue_instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._set_current_task(instance_root=continue_instance["instance_root"], role="dev", task_id="task-0001-current")
        continued = self._dispatch(
            instance_json=continue_instance["instance_json"],
            actor_id="instance-continue",
            role="dev",
            action="checkout",
            args={"task_id": "task-0001-current", "next": "continue", "summary": "Continue tomorrow."},
        )
        self.assertTrue(continued.get("ok"), msg=continued)
        stored_continue = json.loads(self._task_file(continue_instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        self.assertEqual(stored_continue["status"], "active")
        self.assertIsNone(stored_continue["closed_at"])
        self.assertIn("task.checkout.continued task-0001-current", self._history_file(continue_instance["instance_root"], "dev").read_text(encoding="utf-8"))

        finish_instance = self._make_instance_context(actor_id="instance-finish", role="dev")
        self._seed_taskbox_task(instance_root=finish_instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._set_current_task(instance_root=finish_instance["instance_root"], role="dev", task_id="task-0001-current")
        before_finish = self._taskbox_snapshot(finish_instance["instance_root"], "dev")
        missing_evidence = self._dispatch(
            instance_json=finish_instance["instance_json"],
            actor_id="instance-finish",
            role="dev",
            action="checkout",
            args={"task_id": "task-0001-current", "next": "finish"},
        )
        self.assertFalse(missing_evidence.get("ok"), msg=missing_evidence)
        self.assertEqual(self._taskbox_snapshot(finish_instance["instance_root"], "dev"), before_finish)

        finished = self._dispatch(
            instance_json=finish_instance["instance_json"],
            actor_id="instance-finish",
            role="dev",
            action="checkout",
            args={"task_id": "task-0001-current", "next": "finish", "evidence": "Focused tests pass."},
        )
        self.assertTrue(finished.get("ok"), msg=finished)
        stored_finished = json.loads(self._task_file(finish_instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        self.assertEqual(stored_finished["status"], "done")
        self.assertIsNotNone(stored_finished["closed_at"])
        self.assertIsNone(finished["view"]["current_anchor"])
        self.assertIn("task.finished task-0001-current", self._history_file(finish_instance["instance_root"], "dev").read_text(encoding="utf-8"))

        block_instance = self._make_instance_context(actor_id="instance-block", role="dev")
        self._seed_taskbox_task(instance_root=block_instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._set_current_task(instance_root=block_instance["instance_root"], role="dev", task_id="task-0001-current")
        blocked = self._dispatch(
            instance_json=block_instance["instance_json"],
            actor_id="instance-block",
            role="dev",
            action="checkout",
            args={"task_id": "task-0001-current", "next": "block", "reason": "Waiting for user decision."},
        )
        self.assertTrue(blocked.get("ok"), msg=blocked)
        stored_blocked = json.loads(self._task_file(block_instance["instance_root"], "dev", "task-0001-current").read_text(encoding="utf-8"))
        self.assertEqual(stored_blocked["status"], "blocked")
        self.assertIsNone(stored_blocked["closed_at"])
        self.assertIsNone(blocked["view"]["current_anchor"])
        self.assertIn("task.blocked task-0001-current", self._history_file(block_instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_task_review_reads_shelf_and_blocked_work_without_mutation(self) -> None:
        instance = self._make_instance_context(actor_id="instance-review", role="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-captured", title="Captured", status="captured")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0002-blocked", title="Blocked", status="blocked")
        before = self._taskbox_snapshot(instance["instance_root"], "dev")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            actor_id="instance-review",
            role="dev",
            action="review",
            args={},
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIs(payload.get("state_changed"), False)
        self.assertEqual([row["id"] for row in payload["view"]["shelf"]], ["task-0001-captured"])
        self.assertIn("task-0002-blocked", json.dumps(payload["view"]["warnings"], ensure_ascii=True))
        self.assertEqual(self._taskbox_snapshot(instance["instance_root"], "dev"), before)

    def test_invalid_payloads_do_not_mutate_task_docs_or_history(self) -> None:
        instance = self._make_instance_context(actor_id="instance-invalid", role="dev")
        self._seed_taskbox_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current", title="Current", status="active")
        self._set_current_task(instance_root=instance["instance_root"], role="dev", task_id="task-0001-current")

        cases = (
            ("capture", {"task": {"body": "Missing title."}}),
            ("capture", {"task": {"title": "Visibility", "body": "Body.", "visibility": "public"}}),
            ("capture", {"task": {"title": "Template", "body": "Body.", "template": "note"}}),
            ("select", {"task_id": "task-9999-missing"}),
            ("switch_request", {"target": {"mode": "existing", "task_id": "task-9999-missing"}, "reason": "Bad.", "evidence": "Bad."}),
            ("switch_confirm", {"confirmation_id": "confirm-9999", "decision": "accept"}),
            ("progress", {"task_id": "task-0001-current", "summary": "No evidence."}),
            ("checkout", {"task_id": "task-9999-other", "next": "finish", "evidence": "Wrong task."}),
        )
        for action, args in cases:
            with self.subTest(action=action, args=args):
                before = self._taskbox_snapshot(instance["instance_root"], "dev")
                rejected = self._dispatch(
                    instance_json=instance["instance_json"],
                    actor_id="instance-invalid",
                    role="dev",
                    action=action,
                    args=args,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertIs(rejected.get("state_changed"), False, msg=rejected)
                self.assertEqual(self._taskbox_snapshot(instance["instance_root"], "dev"), before)


if __name__ == "__main__":
    unittest.main()
