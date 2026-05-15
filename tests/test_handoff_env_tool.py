#!/usr/bin/env python3
"""Runless handoff env.tool integration tests."""

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


class HandoffEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
            "request_id": f"req-handoff-{uuid.uuid4().hex}",
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

    def _seed_source_objects(self) -> None:
        env_store.create_track("track-handoff-runless", "Handoff Track", current_buddy="design", next_buddy="dev")
        env_store.create_task("task-design-handoff", "Design Task", buddy="design", track_id="track-handoff-runless", summary="seed")
        env_store.create_artifact(
            artifact_id="art-task-design-handoff-r1",
            title="Design Handoff Artifact",
            buddy="design",
            kind="design-handoff",
            task_id="task-design-handoff",
            summary="artifact",
            content={"body": "v1"},
            created_by="design",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.create_memory(
            memory_id="mem-design-handoff",
            buddy="design",
            kind="decision",
            title="Design Decision",
            summary="memory",
            content={"body": "m1"},
            source_refs=[{"type": "note", "label": "memory"}],
        )
        buddybox = env_store.BUDDYBOX_CONTENT_DIR / "design" / "handoff"
        buddybox.mkdir(parents=True, exist_ok=True)
        (buddybox / "handoff.txt").write_text("hello\n", encoding="utf-8")

    def test_validate_and_create_handoff_with_object_refs(self) -> None:
        self._seed_source_objects()
        design_instance = self._instance_json(instance_id="inst-design-handoff", buddy="design")
        payload = {
            "track_id": "track-handoff-runless",
            "source_task_id": "task-design-handoff",
            "target_buddy": "dev",
            "artifact_ids": ["art-task-design-handoff-r1"],
            "memory_ids": ["mem-design-handoff"],
            "buddybox_paths": ["design/handoff/handoff.txt"],
            "reason": "handoff to dev",
            "context": "implement UI",
            "source_refs": [{"type": "note", "label": "handoff"}],
        }

        validated = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-handoff",
            buddy="design",
            tool="handoff",
            action="validate",
            args=payload,
        )
        self.assertTrue(validated.get("ok"), msg=validated)
        self.assertEqual(validated.get("action"), "handoff.validate")

        created = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-handoff",
            buddy="design",
            tool="handoff",
            action="create",
            args=payload,
        )
        self.assertTrue(created.get("ok"), msg=created)
        handoff = created.get("handoff")
        self.assertIsInstance(handoff, dict, msg=created)
        assert isinstance(handoff, dict)
        self.assertEqual(handoff.get("target_buddy"), "dev")
        self.assertEqual(handoff.get("track_id"), "track-handoff-runless")

    def test_handoff_list_visible_to_target_buddy(self) -> None:
        self._seed_source_objects()
        design_instance = self._instance_json(instance_id="inst-design-handoff", buddy="design")
        payload = {
            "track_id": "track-handoff-runless",
            "source_task_id": "task-design-handoff",
            "target_buddy": "dev",
            "artifact_ids": ["art-task-design-handoff-r1"],
            "memory_ids": ["mem-design-handoff"],
            "buddybox_paths": ["design/handoff/handoff.txt"],
            "reason": "handoff to dev",
            "context": "implement UI",
        }
        self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-handoff",
            buddy="design",
            tool="handoff",
            action="create",
            args=payload,
        )

        dev_instance = self._instance_json(instance_id="inst-dev-handoff", buddy="dev")
        listed = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-handoff",
            buddy="dev",
            tool="handoff",
            action="list",
            args={"track_id": "track-handoff-runless"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        rows = listed.get("handoffs")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(any(isinstance(row, dict) and row.get("target_buddy") == "dev" for row in rows))

    def test_handoff_rejects_foreign_artifact_scope(self) -> None:
        env_store.create_track("track-handoff-scope", "Scope", current_buddy="design")
        env_store.create_task("task-design-scope", "Scope Task", buddy="design", track_id="track-handoff-scope")
        env_store.create_track("track-pm-foreign", "Foreign", current_buddy="pm")
        env_store.create_task("task-pm-foreign", "Foreign Task", buddy="pm", track_id="track-pm-foreign")
        env_store.create_artifact(
            artifact_id="art-task-pm-foreign-r1",
            title="Foreign Artifact",
            buddy="pm",
            kind="prd",
            task_id="task-pm-foreign",
            summary="foreign",
            content={"body": "..."},
            created_by="pm",
            source_refs=[{"type": "note", "label": "foreign"}],
        )
        design_instance = self._instance_json(instance_id="inst-design-handoff", buddy="design")

        rejected = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-handoff",
            buddy="design",
            tool="handoff",
            action="validate",
            args={
                "track_id": "track-handoff-scope",
                "source_task_id": "task-design-scope",
                "target_buddy": "dev",
                "artifact_ids": ["art-task-pm-foreign-r1"],
                "reason": "x",
                "context": "y",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_HANDOFF_SCOPE")


if __name__ == "__main__":
    unittest.main()
