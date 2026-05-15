#!/usr/bin/env python3
"""Runless track env.tool integration tests."""

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


class TrackEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
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

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-track-{uuid.uuid4().hex}",
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

    def test_pm_track_lifecycle_mutations(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-track", buddy="pm")

        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-runless-pm",
                "title": "Runless Track",
                "current_buddy": "pm",
                "next_buddy": "design",
                "summary": "seed",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertEqual((created.get("track") or {}).get("id"), "track-runless-pm")

        advanced = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="advance",
            args={"track_id": "track-runless-pm", "current_buddy": "design", "next_buddy": "dev", "status": "active"},
        )
        self.assertTrue(advanced.get("ok"), msg=advanced)
        self.assertEqual((advanced.get("track") or {}).get("current_buddy"), "design")

        archived = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-runless-pm"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual((archived.get("track") or {}).get("status"), "archived")

    def test_non_pm_cannot_create_track(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="create",
            args={"track_id": "track-nope", "title": "Nope"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")

    def test_join_track_creates_or_reuses_active_buddy_task_without_binding_mutation(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-join-runless", "title": "Join Flow", "current_buddy": "pm"},
        )

        dev_instance = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        joined = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="join",
            args={"track_id": "track-join-runless", "title": "Dev Join Task", "summary": "join"},
        )
        self.assertTrue(joined.get("ok"), msg=joined)
        self.assertNotIn("binding_changed", joined)
        task_id = (joined.get("task") or {}).get("id")
        self.assertIsInstance(task_id, str, msg=joined)
        assert isinstance(task_id, str)
        stored_task = env_store.get_task(task_id)
        self.assertIsInstance(stored_task, dict)
        assert isinstance(stored_task, dict)
        self.assertEqual(stored_task.get("track_id"), "track-join-runless")

    def test_attach_and_detach_task(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-attach-runless", "title": "Attach Flow", "current_buddy": "pm"},
        )

        env_store.create_task("task-dev-detach", "Detach Task", buddy="dev", summary="seed")
        dev_instance = self._instance_json(instance_id="inst-dev-track", buddy="dev")

        attached = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="attach_task",
            args={"track_id": "track-attach-runless", "task_id": "task-dev-detach"},
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        self.assertEqual((attached.get("task") or {}).get("track_id"), "track-attach-runless")

        detached = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="detach_task",
            args={"track_id": "track-attach-runless", "task_id": "task-dev-detach"},
        )
        self.assertTrue(detached.get("ok"), msg=detached)
        self.assertIsNone((detached.get("task") or {}).get("track_id"))


if __name__ == "__main__":
    unittest.main()
