#!/usr/bin/env python3
"""Comment env.tool tests aligned with direct track publication boundaries."""

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

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class CommentEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
                    "updated_at": "2026-05-18T00:00:00Z",
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
            "request_id": f"req-comment-{uuid.uuid4().hex}",
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

    def _seed_track_and_material(self, track_id: str = "track-comment") -> tuple[Path, str]:
        pm_instance = self._instance_json(instance_id="inst-pm-comment", buddy="pm")
        created = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-comment",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": "Comment track",
                "outcome": "comment outcome",
                "appetite": "1 day",
                "now": {"next": "publish", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        material = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-comment",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "kind": "prd",
                "label": "PRD",
                "title": "PRD",
                "summary": "summary",
                "content": {"body": "body"},
            },
        )
        self.assertTrue(material.get("ok"), msg=material)
        return pm_instance, material["artifact_id"]

    def test_add_and_list_track_comment(self) -> None:
        pm_instance, _ = self._seed_track_and_material(track_id="track-comment-track")

        design_instance = self._instance_json(instance_id="inst-design-comment", buddy="design")
        added = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-comment",
            buddy="design",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": "track-comment-track", "content": "Looks good"},
        )
        self.assertTrue(added.get("ok"), msg=added)

        listed = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-comment",
            buddy="pm",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": "track-comment-track"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        rows = listed.get("comments")
        self.assertIsInstance(rows, list)
        assert isinstance(rows, list)
        self.assertEqual(len(rows), 1)

    def test_comment_add_artifact_uses_direct_published_material_boundary(self) -> None:
        _, artifact_id = self._seed_track_and_material(track_id="track-comment-art")
        dev_instance = self._instance_json(instance_id="inst-dev-comment", buddy="dev")

        added = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-comment",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": artifact_id, "content": "Can implement this"},
        )
        self.assertTrue(added.get("ok"), msg=added)

    def test_comment_add_rejects_private_draft_artifact(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-comment", buddy="pm")
        private = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-comment",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "kind": "prd",
                "title": "Private",
                "summary": "private",
                "content": {"body": "private"},
            },
        )
        self.assertTrue(private.get("ok"), msg=private)

        dev_instance = self._instance_json(instance_id="inst-dev-comment", buddy="dev")
        denied = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-comment",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": private["artifact_id"], "content": "nope"},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual(denied.get("permission_boundary"), "artifact.publication")

    def test_comments_reject_archived_track_and_material(self) -> None:
        pm_instance, artifact_id = self._seed_track_and_material(track_id="track-comment-archived")
        archived = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-comment",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-comment-archived"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        dev_instance = self._instance_json(instance_id="inst-dev-comment", buddy="dev")
        for action, args in (
            ("add", {"target_type": "track", "target_id": "track-comment-archived", "content": "x"}),
            ("list", {"target_type": "track", "target_id": "track-comment-archived"}),
            ("add", {"target_type": "artifact", "target_id": artifact_id, "content": "x"}),
            ("list", {"target_type": "artifact", "target_id": artifact_id}),
        ):
            rejected = self._dispatch(
                instance_json=dev_instance,
                instance_id="inst-dev-comment",
                buddy="dev",
                tool="comment",
                action=action,
                args=args,
            )
            with self.subTest(action=action, args=args):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual(rejected.get("permission_boundary"), "track.lifecycle_status")


if __name__ == "__main__":
    unittest.main()
