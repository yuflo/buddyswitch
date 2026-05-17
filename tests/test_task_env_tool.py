#!/usr/bin/env python3
"""Task env.tool tests for private task model."""

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
    def _instance_json(self, *, instance_id: str, buddy: str) -> Path:
        path = self._runtime_path(f"instance-{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-17T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
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

    def _create_track(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-task", buddy="pm")
        created = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-task",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-task-private",
                "title": "Private hint",
                "outcome": "outcome",
                "appetite": "1 day",
                "now": {"next": "x", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

    def test_task_track_id_hint_does_not_mutate_track(self) -> None:
        self._create_track()
        before = env_store.get_track("track-task-private")
        self.assertIsInstance(before, dict)

        dev_instance = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        created = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="create",
            args={
                "task_id": "task-dev-private",
                "title": "Private task",
                "track_id": "track-task-private",
                "summary": "hint only",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        after = env_store.get_track("track-task-private")
        self.assertEqual(before, after)

    def test_task_get_rejects_foreign_private_task(self) -> None:
        self._create_track()
        dev_instance = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        self.assertTrue(
            self._dispatch(
                instance_json=dev_instance,
                instance_id="inst-dev-task",
                buddy="dev",
                tool="task",
                action="create",
                args={
                    "task_id": "task-dev-private-2",
                    "title": "Private task",
                    "summary": "private",
                },
            ).get("ok")
        )

        pm_instance = self._instance_json(instance_id="inst-pm-task", buddy="pm")
        denied = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-task",
            buddy="pm",
            tool="task",
            action="get",
            args={"task_id": "task-dev-private-2"},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual(denied.get("permission_boundary"), "task.buddy_scope")

    def test_task_rows_omit_artifact_linkage_fields(self) -> None:
        dev_instance = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        created = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="create",
            args={"task_id": "task-dev-no-art", "title": "No artifact fields", "summary": "x"},
        )
        self.assertTrue(created.get("ok"), msg=created)

        one = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="get",
            args={"task_id": "task-dev-no-art"},
        )
        many = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="list",
            args={},
        )
        self.assertTrue(one.get("ok"), msg=one)
        self.assertTrue(many.get("ok"), msg=many)
        row = one["task"]
        encoded = json.dumps(row, ensure_ascii=True)
        self.assertNotIn("artifact_ids", encoded)
        self.assertNotIn("artifact" + "_slots", encoded)
        self.assertNotIn("current_artifacts", encoded)
        self.assertNotIn("shared_materials", encoded)


if __name__ == "__main__":
    unittest.main()
