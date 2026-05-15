#!/usr/bin/env python3
"""Runless task env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TaskEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str = "inst-dev-task", buddy: str = "dev", status: str = "active") -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(
        self,
        *,
        instance_json: Path,
        tool: str,
        action: str,
        args: dict[str, object],
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-task-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": tool,
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
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
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

    def test_task_crud_flow_for_active_buddy(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")

        created = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="create",
            args={"task_id": "task-dev-runless", "title": "Runless Task", "summary": "seed"},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertEqual(created.get("action"), "task.create")
        task = created.get("task")
        self.assertIsInstance(task, dict, msg=created)
        assert isinstance(task, dict)
        self.assertEqual(task.get("id"), "task-dev-runless")

        listed = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="list",
            args={},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        tasks = listed.get("tasks")
        self.assertIsInstance(tasks, list, msg=listed)
        assert isinstance(tasks, list)
        task_ids = {row.get("id") for row in tasks if isinstance(row, dict)}
        self.assertIn("task-dev-runless", task_ids)

        fetched = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="get",
            args={"task_id": "task-dev-runless"},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual((fetched.get("task") or {}).get("summary"), "seed")

        updated = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="update",
            args={"task_id": "task-dev-runless", "summary": "updated", "status": "blocked"},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual((updated.get("task") or {}).get("status"), "blocked")

        archived = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="archive",
            args={"task_id": "task-dev-runless"},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual((archived.get("task") or {}).get("status"), "archived")

    def test_task_get_rejects_foreign_buddy_scope(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        env_store.create_task("task-pm-owned", "PM Task", buddy="pm", summary="pm")

        rejected = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="get",
            args={"task_id": "task-pm-owned"},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TASK_BUDDY_SCOPE")
        self.assertEqual(rejected.get("permission_boundary"), "task.buddy_scope")

    def test_task_create_rejects_unknown_payload_field(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")

        rejected = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="create",
            args={"task_id": "task-dev-bad", "title": "Bad", "unknown": 1},
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TASK_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
