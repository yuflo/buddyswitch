#!/usr/bin/env python3
"""Task env.tool tests for instance-local taskbox behavior."""

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

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
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

    def _legacy_task_file(self, task_id: str) -> Path:
        return self._runtime_path(f"{'buddyswitch/objects'}/tasks/{task_id}.json")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _make_instance_context(self, *, instance_id: str = "instance-a", buddy: str = "dev") -> dict[str, Any]:
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
            "updated_at": "2026-05-23T00:00:00+08:00",
        }
        instance_json = instance_root / "instance.json"
        self._write_json(instance_json, instance_payload)
        return {
            "instance_root": instance_root,
            "instance_json": instance_json,
            "instance_payload": instance_payload,
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

    def _snapshot_taskbox_task_ids(self, instance_root: Path, buddy: str) -> list[str]:
        tasks_dir = self._taskbox_tasks_dir(instance_root, buddy)
        if not tasks_dir.exists():
            return []
        return sorted(path.stem for path in tasks_dir.glob("*.json"))

    def _seed_track(self, track_id: str) -> None:
        env_store.create_track(track_id, f"{track_id} title", owner_buddy="pm")

    def _seed_legacy_shared_task(self, *, task_id: str = "task-legacy-shared", buddy: str = "dev") -> None:
        self._write_json(
            self._legacy_task_file(task_id),
            {
                "id": task_id,
                "buddy": buddy,
                "title": "Legacy shared task",
                "status": "active",
                "track_id": None,
                "summary": "This must not appear.",
                "created_at": "2026-05-23T00:00:00+08:00",
                "updated_at": "2026-05-23T00:00:00+08:00",
            },
        )

    def _seed_taskbox_task(
        self,
        *,
        instance_root: Path,
        buddy: str,
        task_id: str,
        title: str,
        status: str = "active",
        priority: str = "normal",
        track_id: str | None = None,
        summary: str = "",
        refs: list[dict[str, object]] | None = None,
        created_at: str = "2026-05-23T12:00:00+08:00",
        updated_at: str = "2026-05-23T12:00:00+08:00",
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
                "status": status,
                "priority": priority,
                "track_id": track_id,
                "refs": refs or [],
                "created_at": created_at,
                "updated_at": updated_at,
                "closed_at": closed_at,
            },
        )

    def _history_lines(self, instance_root: Path, buddy: str) -> list[str]:
        return self._history_file(instance_root, buddy).read_text(encoding="utf-8").splitlines()

    def test_create_writes_instance_local_task_with_priority_refs_and_history(self) -> None:
        self._seed_track("track-alpha")
        instance = self._make_instance_context(instance_id="instance-a", buddy="dev")

        payload = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="create",
            args={
                "task_id": "task-dev-high",
                "title": "Inspect design handoff",
                "summary": "Review artifact references and risks.",
                "priority": "high",
                "track_id": "track-alpha",
                "refs": [
                    {"type": "track", "id": "track-alpha", "label": "Primary track"},
                    {"type": "artifact", "id": "art-design-handoff", "label": "Prototype"},
                ],
            },
        )

        self.assertTrue(payload.get("ok"), msg=payload)
        task = payload["task"]
        self.assertEqual(task["id"], "task-dev-high")
        self.assertEqual(task["owner_buddy"], "dev")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["track_id"], "track-alpha")
        self.assertEqual(task["refs"][1]["id"], "art-design-handoff")
        self.assertIsNone(task["closed_at"])

        task_file = self._task_file(instance["instance_root"], "dev", "task-dev-high")
        self.assertTrue(task_file.is_file())
        self.assertFalse(self._legacy_task_file("task-dev-high").exists())
        stored = json.loads(task_file.read_text(encoding="utf-8"))
        self.assertEqual(stored["owner_buddy"], "dev")
        self.assertNotIn("buddy", stored)
        self.assertIn("task.create task-dev-high", self._history_file(instance["instance_root"], "dev").read_text(encoding="utf-8"))

    def test_list_and_get_ignore_legacy_shared_task_files(self) -> None:
        instance = self._make_instance_context(instance_id="instance-a", buddy="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-dev-local",
            title="Local task",
            priority="normal",
        )
        self._seed_legacy_shared_task()

        listed = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={"include_archived": True},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual([task["id"] for task in listed["tasks"]], ["task-dev-local"])

        missing = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="get",
            args={"task_id": "task-legacy-shared"},
        )
        self.assertFalse(missing.get("ok"), msg=missing)
        self.assertIn("task not found", str((missing.get("error") or {}).get("message")))

    def test_same_task_id_isolated_across_instances(self) -> None:
        instance_a = self._make_instance_context(instance_id="instance-a", buddy="dev")
        instance_b = self._make_instance_context(instance_id="instance-b", buddy="dev")

        created_a = self._dispatch(
            instance_json=instance_a["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="create",
            args={"task_id": "task-dev-high", "title": "Instance A title"},
        )
        created_b = self._dispatch(
            instance_json=instance_b["instance_json"],
            instance_id="instance-b",
            buddy="dev",
            action="create",
            args={"task_id": "task-dev-high", "title": "Instance B title"},
        )
        self.assertTrue(created_a.get("ok"), msg=created_a)
        self.assertTrue(created_b.get("ok"), msg=created_b)
        self.assertEqual(created_a["task"]["title"], "Instance A title")
        self.assertEqual(created_b["task"]["title"], "Instance B title")

        listed_a = self._dispatch(
            instance_json=instance_a["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={},
        )
        listed_b = self._dispatch(
            instance_json=instance_b["instance_json"],
            instance_id="instance-b",
            buddy="dev",
            action="list",
            args={},
        )
        self.assertEqual([task["id"] for task in listed_a["tasks"]], ["task-dev-high"])
        self.assertEqual([task["id"] for task in listed_b["tasks"]], ["task-dev-high"])
        self.assertTrue(self._task_file(instance_a["instance_root"], "dev", "task-dev-high").is_file())
        self.assertTrue(self._task_file(instance_b["instance_root"], "dev", "task-dev-high").is_file())

    def test_active_buddy_cannot_read_or_mutate_other_taskbox_tasks(self) -> None:
        instance = self._make_instance_context(instance_id="instance-a", buddy="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="design",
            task_id="task-design-private",
            title="Design private task",
        )

        listed = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={"include_archived": True},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertNotIn("task-design-private", {task["id"] for task in listed["tasks"]})

        for action, args in (
            ("get", {"task_id": "task-design-private"}),
            ("update", {"task_id": "task-design-private", "title": "Nope"}),
            ("archive", {"task_id": "task-design-private"}),
        ):
            with self.subTest(action=action):
                rejected = self._dispatch(
                    instance_json=instance["instance_json"],
                    instance_id="instance-a",
                    buddy="dev",
                    action=action,
                    args=args,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                message = str((rejected.get("error") or {}).get("message"))
                self.assertTrue(
                    "task not found" in message or "owned by buddy" in message,
                    msg=rejected,
                )

    def test_list_filters_sort_by_priority_updated_time_and_id(self) -> None:
        instance = self._make_instance_context(instance_id="instance-a", buddy="dev")
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-dev-low",
            title="Low",
            priority="low",
            status="active",
            track_id="track-alpha",
            updated_at="2026-05-23T12:03:00+08:00",
        )
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-dev-high",
            title="High",
            priority="high",
            status="active",
            track_id="track-beta",
            updated_at="2026-05-23T12:01:00+08:00",
        )
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-dev-high-b",
            title="High B",
            priority="high",
            status="active",
            track_id="track-beta",
            updated_at="2026-05-23T12:01:00+08:00",
        )
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-dev-normal",
            title="Normal",
            priority="normal",
            status="blocked",
            track_id="track-alpha",
            updated_at="2026-05-23T12:02:00+08:00",
        )
        self._seed_taskbox_task(
            instance_root=instance["instance_root"],
            buddy="dev",
            task_id="task-dev-archived",
            title="Archived",
            priority="high",
            status="archived",
            track_id="track-alpha",
            updated_at="2026-05-23T12:04:00+08:00",
        )

        default_list = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={},
        )
        self.assertTrue(default_list.get("ok"), msg=default_list)
        self.assertEqual(
            [task["id"] for task in default_list["tasks"]],
            ["task-dev-high", "task-dev-high-b", "task-dev-normal", "task-dev-low"],
        )

        high_list = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={"priority": "high", "include_archived": True},
        )
        self.assertTrue(high_list.get("ok"), msg=high_list)
        self.assertEqual(
            [task["id"] for task in high_list["tasks"]],
            ["task-dev-archived", "task-dev-high", "task-dev-high-b"],
        )

        alpha_list = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={"track_id": "track-alpha"},
        )
        self.assertTrue(alpha_list.get("ok"), msg=alpha_list)
        self.assertEqual([task["id"] for task in alpha_list["tasks"]], ["task-dev-normal", "task-dev-low"])

        blocked_list = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="list",
            args={"status": "blocked"},
        )
        self.assertTrue(blocked_list.get("ok"), msg=blocked_list)
        self.assertEqual([task["id"] for task in blocked_list["tasks"]], ["task-dev-normal"])

    def test_task_lifecycle_updates_closed_at_and_appends_history(self) -> None:
        instance = self._make_instance_context(instance_id="instance-a", buddy="dev")

        created = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="create",
            args={"task_id": "task-dev-high", "title": "Lifecycle task"},
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertIsNone(created["task"]["closed_at"])

        updated = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="update",
            args={"task_id": "task-dev-high", "priority": "high"},
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual(updated["task"]["priority"], "high")

        blocked = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="update",
            args={"task_id": "task-dev-high", "status": "blocked"},
        )
        self.assertTrue(blocked.get("ok"), msg=blocked)
        self.assertEqual(blocked["task"]["status"], "blocked")
        self.assertIsNone(blocked["task"]["closed_at"])

        done = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="update",
            args={"task_id": "task-dev-high", "status": "done"},
        )
        self.assertTrue(done.get("ok"), msg=done)
        self.assertEqual(done["task"]["status"], "done")
        self.assertIsNotNone(done["task"]["closed_at"])

        reopened = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="update",
            args={"task_id": "task-dev-high", "status": "active"},
        )
        self.assertTrue(reopened.get("ok"), msg=reopened)
        self.assertEqual(reopened["task"]["status"], "active")
        self.assertIsNone(reopened["task"]["closed_at"])

        archived = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="archive",
            args={"task_id": "task-dev-high"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual(archived["task"]["status"], "archived")
        self.assertIsNotNone(archived["task"]["closed_at"])

        history_before_repeat = self._history_lines(instance["instance_root"], "dev")
        archived_again = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="archive",
            args={"task_id": "task-dev-high"},
        )
        self.assertTrue(archived_again.get("ok"), msg=archived_again)
        self.assertEqual(self._history_lines(instance["instance_root"], "dev"), history_before_repeat)

        history_lines = self._history_lines(instance["instance_root"], "dev")
        for marker in (
            "task.create task-dev-high",
            "task.update task-dev-high",
            "task.block task-dev-high",
            "task.close task-dev-high",
            "task.reopen task-dev-high",
            "task.archive task-dev-high",
        ):
            with self.subTest(marker=marker):
                self.assertEqual(sum(marker in line for line in history_lines), 1, msg=history_lines)

        history_payload = self._dispatch(
            instance_json=instance["instance_json"],
            instance_id="instance-a",
            buddy="dev",
            action="history",
            args={"limit": 3},
        )
        self.assertTrue(history_payload.get("ok"), msg=history_payload)
        self.assertEqual(len(history_payload["entries"]), 3)
        self.assertTrue(all(str(entry["line"]).startswith("- ") for entry in history_payload["entries"]))

    def test_validation_rejects_invalid_task_payloads_without_creating_files(self) -> None:
        instance = self._make_instance_context(instance_id="instance-a", buddy="dev")
        before_task_ids = self._snapshot_taskbox_task_ids(instance["instance_root"], "dev")

        cases = (
            {"title": "Missing task id"},
            {"task_id": "task-dev-invalid-priority", "title": "Bad priority", "priority": "urgent"},
            {"task_id": "task-dev-invalid-status", "title": "Bad status", "status": "waiting"},
            {"task_id": "task-dev-invalid-refs", "title": "Bad refs type", "refs": "track-alpha"},
            {"task_id": "task-dev-missing-ref-id", "title": "Missing ref id", "refs": [{"type": "track"}]},
            {"task_id": "task-dev-bad-buddybox-ref", "title": "Bad buddybox ref", "refs": [{"type": "buddybox", "logical_name": "prototype/index.html"}]},
            {"task_id": "task-dev-source-refs", "title": "Reject source_refs", "source_refs": []},
            {"task_id": "task-dev-visibility", "title": "Reject visibility", "visibility": "public"},
            {"task_id": "../escape", "title": "Reject traversal"},
        )

        for args in cases:
            with self.subTest(args=args):
                rejected = self._dispatch(
                    instance_json=instance["instance_json"],
                    instance_id="instance-a",
                    buddy="dev",
                    action="create",
                    args=args,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual(rejected.get("permission_boundary"), "request-payload")
                self.assertIs(rejected.get("state_changed"), False)
                if args.get("task_id") == "task-dev-bad-buddybox-ref":
                    self.assertIn("not supported", json.dumps(rejected, ensure_ascii=True).lower())
                self.assertEqual(self._snapshot_taskbox_task_ids(instance["instance_root"], "dev"), before_task_ids)


if __name__ == "__main__":
    unittest.main()
