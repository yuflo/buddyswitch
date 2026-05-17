#!/usr/bin/env python3
"""Comment env.tool integration tests."""

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


class CommentEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
            "request_id": f"req-cmt-{uuid.uuid4().hex}",
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

    def _seed_active_track(self):
        return env_store.create_track("track-cmt-active", "Active Track")

    def _seed_archived_track(self):
        return env_store.create_track("track-cmt-archived", "Archived Track", status="archived")

    def _seed_readable_artifact(self, buddy: str = "dev"):
        task = env_store.create_task("task-cmt-art", "Comment Art Task", buddy=buddy, track_id="track-cmt-active")
        return env_store.create_artifact(
            artifact_id="art-cmt-test",
            title="Comment Artifact",
            buddy=buddy,
            kind="prd",
            task_id=task["id"],
            created_by=buddy,
        )

    def test_add_and_list_track_comment_uses_comment_object_relation_without_target_mutation(self):
        track = self._seed_active_track()
        before_track = env_store.get_track(track["id"])
        instance_json = self._instance_json(instance_id="inst-design-cmt", buddy="design")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-cmt",
            buddy="design",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track["id"], "content": "Nice track design!"},
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertIn("comment_id", response)
        self.assertEqual(response["comment"]["target_type"], "track")
        self.assertEqual(response["comment"]["target_id"], track["id"])
        self.assertEqual(response["comment"]["content"], "Nice track design!")
        self.assertEqual(response["comment"]["author_buddy"], "design")

        stored_comment = env_store.get_comment(response["comment_id"])
        self.assertEqual(stored_comment["target_type"], "track")
        self.assertEqual(stored_comment["target_id"], track["id"])
        self.assertEqual(env_store.get_track(track["id"]), before_track)

        list_resp = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-cmt",
            buddy="design",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"]},
        )
        self.assertTrue(list_resp.get("ok"), msg=list_resp)
        comments = list_resp.get("comments", [])
        self.assertEqual([row["id"] for row in comments], [response["comment_id"]])

    def test_add_and_list_artifact_comment_uses_comment_object_relation_without_target_mutation(self):
        self._seed_active_track()
        artifact = self._seed_readable_artifact(buddy="dev")
        before_artifact = env_store.get_artifact(artifact["id"])
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": artifact["id"], "content": "Review this artifact."},
        )
        self.assertTrue(response.get("ok"), msg=response)

        stored_comment = env_store.get_comment(response["comment_id"])
        self.assertEqual(stored_comment["target_type"], "artifact")
        self.assertEqual(stored_comment["target_id"], artifact["id"])
        self.assertEqual(env_store.get_artifact(artifact["id"]), before_artifact)

        list_resp = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "artifact", "target_id": artifact["id"]},
        )
        self.assertTrue(list_resp.get("ok"), msg=list_resp)
        self.assertEqual([row["id"] for row in list_resp.get("comments", [])], [response["comment_id"]])

    def test_comment_add_rejects_archived_track(self):
        self._seed_archived_track()
        instance_json = self._instance_json(instance_id="inst-dev-arch", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-arch",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": "track-cmt-archived", "content": "Should be blocked."},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("track.lifecycle_status", str(response.get("permission_boundary", "")))

    def test_comment_list_rejects_archived_track(self):
        self._seed_archived_track()
        instance_json = self._instance_json(instance_id="inst-dev-arch-list", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-arch-list",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": "track-cmt-archived"},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("track.lifecycle_status", str(response.get("permission_boundary", "")))

    def test_comment_add_rejects_blank_content(self):
        self._seed_active_track()
        instance_json = self._instance_json(instance_id="inst-design-blank", buddy="design")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-blank",
            buddy="design",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": "track-cmt-active", "content": "   "},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_COMMENT_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_comment_list_is_read_only(self):
        self._seed_active_track()
        env_store.create_comment(
            target_type="track",
            target_id="track-cmt-active",
            author_buddy="design",
            content="Static comment",
        )
        instance_json = self._instance_json(instance_id="inst-design-ro", buddy="design")
        resp1 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-ro",
            buddy="design",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": "track-cmt-active"},
        )
        resp2 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-ro",
            buddy="design",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": "track-cmt-active"},
        )
        self.assertTrue(resp1.get("ok"), msg=resp1)
        self.assertTrue(resp2.get("ok"), msg=resp2)
        self.assertIs(resp1.get("state_changed"), False)

    def test_comment_list_ignores_legacy_target_comment_ids_and_uses_comment_objects(self):
        track = self._seed_active_track()
        legacy_track = env_store.get_track(track["id"])
        legacy_track["comment_ids"] = ["comment-stale"]
        env_store.track_file(track["id"]).write_text(
            json.dumps(legacy_track, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

        real = env_store.create_comment(
            target_type="track",
            target_id=track["id"],
            author_buddy="design",
            content="Real relation",
        )
        instance_json = self._instance_json(instance_id="inst-design-legacy-list", buddy="design")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-legacy-list",
            buddy="design",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual([row["id"] for row in response.get("comments", [])], [real["id"]])

    def test_comment_tool_rejects_task_target(self):
        task = env_store.create_task("task-cmt-reject", "Reject Cmt", buddy="dev")
        instance_json = self._instance_json(instance_id="inst-dev-task-cmt", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-task-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "task", "target_id": task["id"], "content": "No task comments"},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_COMMENT_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_comment_reply_to_accepts_same_target(self):
        self._seed_active_track()
        cmt1 = env_store.create_comment(
            target_type="track",
            target_id="track-cmt-active",
            author_buddy="design",
            content="First comment",
        )
        instance_json = self._instance_json(instance_id="inst-design-reply", buddy="design")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-reply",
            buddy="design",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": "track-cmt-active", "content": "Reply", "reply_to": cmt1["id"]},
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["comment"]["reply_to"], cmt1["id"])

    def test_comment_reply_to_requires_same_target(self):
        self._seed_active_track()
        # Create a second track and seed comment there
        track_b = env_store.create_track("track-cmt-b", "Track B")
        cmt_on_a = env_store.create_comment(
            target_type="track",
            target_id="track-cmt-active",
            author_buddy="design",
            content="On track A",
        )
        instance_json = self._instance_json(instance_id="inst-dev-cross", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cross",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track_b["id"], "content": "Bad reply", "reply_to": cmt_on_a["id"]},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_COMMENT_REPLY_SCOPE", response.get("error", {}).get("code", ""))

    def _seed_track_with_pm_artifact_and_dev_task(self):
        """Create track with PM artifact and Dev active task relation on same track."""
        track = env_store.create_track("track-cmt-relation", "Cross-Buddy Track")
        pm_task = env_store.create_task("task-cmt-pm", "PM Task", buddy="pm", track_id=track["id"])
        dev_task = env_store.create_task("task-cmt-dev", "Dev Task", buddy="dev", track_id=track["id"])
        artifact = env_store.create_artifact(
            artifact_id="art-cmt-pm-relation",
            title="PM Cross-Buddy Artifact",
            buddy="pm",
            kind="prd",
            task_id=pm_task["id"],
            created_by="pm",
        )
        return track, pm_task, dev_task, artifact

    def test_comment_add_artifact_uses_artifact_track_relation_read_boundary(self):
        """MCT-COM-007: Dev with active task on PM's track can comment on PM's artifact."""
        self._seed_track_with_pm_artifact_and_dev_task()
        instance_json = self._instance_json(instance_id="inst-dev-relation", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-relation",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": "art-cmt-pm-relation", "content": "Dev feedback on PM artifact via track relation."},
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["comment"]["author_buddy"], "dev")
        self.assertEqual(response["target_type"], "artifact")
        stored = env_store.get_comment(response["comment_id"])
        self.assertEqual(stored["target_type"], "artifact")
        self.assertEqual(stored["target_id"], "art-cmt-pm-relation")

    def test_comment_add_artifact_rejects_missing_track_relation(self):
        """MCT-COM-008: Dev without task on PM's track cannot comment on PM's artifact."""
        track = env_store.create_track("track-cmt-no-rel", "No Relation Track")
        pm_task = env_store.create_task("task-cmt-pm-norel", "PM Task", buddy="pm", track_id=track["id"])
        env_store.create_artifact(
            artifact_id="art-cmt-pm-norel",
            title="PM Isolated Artifact",
            buddy="pm",
            kind="prd",
            task_id=pm_task["id"],
            created_by="pm",
        )
        instance_json = self._instance_json(instance_id="inst-dev-norel", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-norel",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": "art-cmt-pm-norel", "content": "Outsider comment."},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("artifact.track_relation", str(response.get("permission_boundary", "")))

    def test_comment_add_rejects_foreign_superseded_artifact(self):
        """MCT-COM-009: Foreign superseded artifact cannot be commented on via currentness boundary."""
        track, pm_task, dev_task, _ = self._seed_track_with_pm_artifact_and_dev_task()
        # Create a superseded revision r1 (not current)
        env_store.create_artifact(
            artifact_id="art-cmt-pm-old",
            title="PM Old Revision",
            buddy="pm",
            kind="prd",
            task_id=pm_task["id"],
            created_by="pm",
        )
        # Mark it as superseded
        current = env_store.create_artifact(
            artifact_id="art-cmt-pm-current",
            title="PM Current Revision",
            buddy="pm",
            kind="prd",
            task_id=pm_task["id"],
            created_by="pm",
        )
        # Make the first one not current and superseded_by the second
        old = env_store.get_artifact("art-cmt-pm-old")
        old["is_current"] = False
        old["supersedes_artifact_id"] = None
        env_store.save_artifact(old)
        current_from_store = env_store.get_artifact("art-cmt-pm-current")
        current_from_store["supersedes_artifact_id"] = "art-cmt-pm-old"
        env_store.save_artifact(current_from_store)

        instance_json = self._instance_json(instance_id="inst-dev-super", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-super",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": "art-cmt-pm-old", "content": "Commenting on old revision."},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("artifact.currentness", str(response.get("permission_boundary", "")))

    def test_comment_edit_delete_actions_are_unsupported(self):
        instance_json = self._instance_json(instance_id="inst-dev-cmt-unsup", buddy="dev")
        for action in ("edit", "update", "delete"):
            with self.subTest(action=action):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-cmt-unsup",
                    buddy="dev",
                    tool="comment",
                    action=action,
                    args={},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertIn("E_ENV_TOOL", response.get("error", {}).get("code", ""))

    def test_comment_status_and_resolution_fields_are_rejected(self):
        self._seed_active_track()
        instance_json = self._instance_json(instance_id="inst-dev-res", buddy="dev")
        for extra in ({"status": "open"}, {"resolved": False}, {"resolved_at": "x"}, {"resolution": "fixed"}):
            with self.subTest(extra=extra):
                args = {"target_type": "track", "target_id": "track-cmt-active", "content": "Test", **extra}
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-res",
                    buddy="dev",
                    tool="comment",
                    action="add",
                    args=args,
                )
                self.assertFalse(response.get("ok"), msg=f"Should have rejected {extra}: {response}")


if __name__ == "__main__":
    unittest.main()
