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

import env_legacy_store as env_store  # noqa: E402
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

    def _seed_track(self, track_id: str = "track-comment") -> dict[str, object]:
        return env_store.create_track(track_id, "Comment Track", owner_buddy="pm")

    def _seed_published_artifact(self, *, artifact_id: str, track_id: str = "track-comment") -> str:
        if env_store.get_track(track_id) is None:
            self._seed_track(track_id)
        artifact = env_store.create_artifact_revision(
            artifact_id=artifact_id,
            title=f"{artifact_id} title",
            summary="seed summary",
            body="Original body",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=track_id,
            artifact_id=str(artifact["id"]),
            label="Seed",
            from_buddy="pm",
            summary="seed summary",
        )
        return str(artifact["id"])

    def _snapshot_track_json(self, track_id: str) -> str:
        track = env_store.get_track(track_id)
        self.assertIsInstance(track, dict)
        assert isinstance(track, dict)
        return json.dumps(track, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _snapshot_artifact_json(self, artifact_id: str) -> str:
        artifact = env_store.get_artifact(artifact_id)
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        return json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def test_add_and_list_track_comment_thread_without_target_mutation(self) -> None:
        track = self._seed_track("track-cmt-thread")
        before = self._snapshot_track_json(str(track["id"]))

        instance_json = self._instance_json(instance_id="inst-design-cmt", buddy="design")
        added = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-cmt",
            buddy="design",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track["id"], "content": "Nice track."},
        )
        self.assertTrue(added.get("ok"), msg=added)
        comment = added.get("comment")
        self.assertIsInstance(comment, dict, msg=added)
        assert isinstance(comment, dict)
        self.assertEqual(comment.get("by_buddy"), "design")
        self.assertEqual(comment.get("status"), "open")
        self.assertEqual(comment.get("thread_id"), comment.get("id"))
        self.assertEqual(self._snapshot_track_json(str(track["id"])), before)

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-cmt",
            buddy="design",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"], "status": "all"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(len(listed.get("comments", [])), 1)
        self.assertEqual(len(listed.get("threads", [])), 1)
        self.assertEqual(self._snapshot_track_json(str(track["id"])), before)

    def test_artifact_comment_is_separate_from_artifact_body(self) -> None:
        artifact_id = self._seed_published_artifact(artifact_id="art-cmt-body-separate")
        before = self._snapshot_artifact_json(artifact_id)
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")

        added = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": artifact_id, "content": "Please revise this."},
        )
        self.assertTrue(added.get("ok"), msg=added)
        self.assertEqual(self._snapshot_artifact_json(artifact_id), before)

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "artifact", "target_id": artifact_id, "status": "all"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(self._snapshot_artifact_json(artifact_id), before)

        artifact = env_store.get_artifact(artifact_id)
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("body"), "Original body")

    def test_unsupported_target_type_rejects_before_write_without_target_mutation(self) -> None:
        track = self._seed_track("track-cmt-unsupported-target")
        before_track = self._snapshot_track_json(str(track["id"]))
        before_comment_count = len(env_store.list_comments())
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")

        add = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "task", "target_id": str(track["id"]), "content": "nope"},
        )
        self.assertFalse(add.get("ok"), msg=add)
        self.assertEqual((add.get("error") or {}).get("code"), "E_COMMENT_PAYLOAD")
        self.assertEqual(self._snapshot_track_json(str(track["id"])), before_track)
        self.assertEqual(len(env_store.list_comments()), before_comment_count)

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "task", "target_id": str(track["id"]), "status": "all"},
        )
        self.assertFalse(listed.get("ok"), msg=listed)
        self.assertEqual((listed.get("error") or {}).get("code"), "E_COMMENT_PAYLOAD")
        self.assertEqual(self._snapshot_track_json(str(track["id"])), before_track)
        self.assertEqual(len(env_store.list_comments()), before_comment_count)

    def test_artifact_section_comment_requires_anchor(self) -> None:
        artifact_id = self._seed_published_artifact(artifact_id="art-cmt-anchor")
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")

        missing = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact_section", "target_id": artifact_id, "content": "Missing anchor"},
        )
        self.assertFalse(missing.get("ok"), msg=missing)
        self.assertEqual((missing.get("error") or {}).get("code"), "E_COMMENT_PAYLOAD")

        added = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact_section",
                "target_id": artifact_id,
                "anchor": "Current Conclusion",
                "content": "Anchored",
            },
        )
        self.assertTrue(added.get("ok"), msg=added)
        comment = added.get("comment")
        self.assertEqual((comment or {}).get("anchor"), "Current Conclusion")

    def test_artifact_section_revision_reference_must_belong_to_same_chain(self) -> None:
        track_id = "track-cmt-revision-chain"
        self._seed_track(track_id)
        env_store.create_artifact_revision(
            artifact_id="art-cmt-chain-r1",
            title="r1",
            summary="r1",
            body="r1",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=track_id,
            artifact_id="art-cmt-chain-r1",
            label="R1",
            from_buddy="pm",
            summary="r1",
        )
        env_store.create_artifact_revision(
            artifact_id="art-cmt-chain-r2",
            title="r2",
            summary="r2",
            body="r2",
            template="brief",
            supersedes_artifact_id="art-cmt-chain-r1",
            created_by="pm",
            authors=None,
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=track_id,
            artifact_id="art-cmt-chain-r2",
            label="R2",
            from_buddy="pm",
            summary="r2",
        )
        self._seed_published_artifact(artifact_id="art-cmt-other-r1", track_id=track_id)
        before_target = self._snapshot_artifact_json("art-cmt-chain-r2")
        before_other = self._snapshot_artifact_json("art-cmt-other-r1")

        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")
        valid = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact_section",
                "target_id": "art-cmt-chain-r2",
                "artifact_revision_id": "art-cmt-chain-r1",
                "anchor": "Goal",
                "content": "valid ref",
            },
        )
        self.assertTrue(valid.get("ok"), msg=valid)
        self.assertEqual(self._snapshot_artifact_json("art-cmt-chain-r2"), before_target)
        self.assertEqual(self._snapshot_artifact_json("art-cmt-other-r1"), before_other)
        before_comment_count = len(env_store.list_comments())

        invalid = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact_section",
                "target_id": "art-cmt-chain-r2",
                "artifact_revision_id": "art-cmt-other-r1",
                "anchor": "Goal",
                "content": "invalid ref",
            },
        )
        self.assertFalse(invalid.get("ok"), msg=invalid)
        self.assertEqual(invalid.get("permission_boundary"), "comment.artifact_revision_scope")
        self.assertEqual(self._snapshot_artifact_json("art-cmt-chain-r2"), before_target)
        self.assertEqual(self._snapshot_artifact_json("art-cmt-other-r1"), before_other)
        self.assertEqual(len(env_store.list_comments()), before_comment_count)

    def test_reply_to_must_stay_on_same_target_thread(self) -> None:
        track_a = self._seed_track("track-cmt-a")
        track_b = self._seed_track("track-cmt-b")
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")

        root_a = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track_a["id"], "content": "root a"},
        )
        root_b = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track_b["id"], "content": "root b"},
        )
        self.assertTrue(root_a.get("ok"), msg=root_a)
        self.assertTrue(root_b.get("ok"), msg=root_b)

        ok_reply = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "track",
                "target_id": track_a["id"],
                "content": "reply a",
                "reply_to": (root_a.get("comment") or {}).get("id"),
            },
        )
        self.assertTrue(ok_reply.get("ok"), msg=ok_reply)
        self.assertEqual((ok_reply.get("comment") or {}).get("thread_id"), (root_a.get("comment") or {}).get("id"))

        bad_reply = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "track",
                "target_id": track_a["id"],
                "content": "bad reply",
                "reply_to": (root_b.get("comment") or {}).get("id"),
            },
        )
        self.assertFalse(bad_reply.get("ok"), msg=bad_reply)
        self.assertEqual(bad_reply.get("permission_boundary"), "comment.reply_to_scope")

    def test_pm_resolve_updates_entire_thread_and_list_state(self) -> None:
        track = self._seed_track("track-cmt-resolve-pm")
        pm_instance_id = "inst-cmt-resolve-pm"
        dev_instance_id = "inst-cmt-resolve-dev"
        design_instance_id = "inst-cmt-resolve-design"
        before_track = self._snapshot_track_json(str(track["id"]))

        root = self._dispatch(
            instance_json=self._instance_json(instance_id=dev_instance_id, buddy="dev"),
            instance_id=dev_instance_id,
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track["id"], "content": "root"},
        )
        reply = self._dispatch(
            instance_json=self._instance_json(instance_id=design_instance_id, buddy="design"),
            instance_id=design_instance_id,
            buddy="design",
            tool="comment",
            action="add",
            args={
                "target_type": "track",
                "target_id": track["id"],
                "content": "reply",
                "reply_to": (root.get("comment") or {}).get("id"),
            },
        )
        self.assertTrue(root.get("ok"), msg=root)
        self.assertTrue(reply.get("ok"), msg=reply)
        root_id = str((root.get("comment") or {}).get("id"))
        reply_id = str((reply.get("comment") or {}).get("id"))

        resolved = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={
                "comment_id": reply_id,
                "resolution_summary": "Reviewed by PM; addressed in art-dev-r1.",
            },
        )
        self.assertTrue(resolved.get("ok"), msg=resolved)
        self.assertTrue(resolved.get("state_changed"), msg=resolved)
        self.assertEqual(resolved.get("durability"), "durable")
        self.assertEqual(set(resolved.get("updated_ids", [])), {root_id, reply_id})
        self.assertEqual(self._snapshot_track_json(str(track["id"])), before_track)

        listed = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"], "status": "all"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        comments = listed.get("comments", [])
        self.assertEqual(len(comments), 2)
        for row in comments:
            self.assertEqual(row.get("status"), "resolved")
            self.assertEqual(row.get("resolved_by"), "pm")
            self.assertIsInstance(row.get("resolved_at"), str)
            self.assertEqual(row.get("resolution_summary"), "Reviewed by PM; addressed in art-dev-r1.")
        self.assertEqual((listed.get("status_counts") or {}).get("open"), 0)
        self.assertEqual((listed.get("status_counts") or {}).get("resolved"), 2)

        open_only = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"], "status": "open"},
        )
        self.assertTrue(open_only.get("ok"), msg=open_only)
        self.assertEqual(open_only.get("comments"), [])

    def test_comment_resolve_pm_boundary_payload_boundary_and_target_boundary(self) -> None:
        track = self._seed_track("track-cmt-resolve-boundary")
        pm_instance_id = "inst-cmt-boundary-pm"
        dev_instance_id = "inst-cmt-boundary-dev"
        dev_instance_json = self._instance_json(instance_id=dev_instance_id, buddy="dev")

        root = self._dispatch(
            instance_json=dev_instance_json,
            instance_id=dev_instance_id,
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track["id"], "content": "root"},
        )
        self.assertTrue(root.get("ok"), msg=root)
        root_id = str((root.get("comment") or {}).get("id"))

        non_pm = self._dispatch(
            instance_json=dev_instance_json,
            instance_id=dev_instance_id,
            buddy="dev",
            tool="comment",
            action="resolve",
            args={"comment_id": root_id, "resolution_summary": "should fail"},
        )
        self.assertFalse(non_pm.get("ok"), msg=non_pm)
        self.assertEqual((non_pm.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
        self.assertEqual(non_pm.get("permission_boundary"), "tool.role_authority")
        self.assertEqual(non_pm.get("required_permission"), "comment.resolve")
        self.assertEqual(non_pm.get("active_role"), "dev")
        self.assertEqual(non_pm.get("allowed_roles"), ["pm"])
        self.assertIs(non_pm.get("state_changed"), False)
        stored_root = env_store.get_comment(root_id)
        self.assertIsInstance(stored_root, dict)
        assert isinstance(stored_root, dict)
        self.assertEqual(stored_root.get("status"), "open")

        blank_summary = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"comment_id": root_id, "resolution_summary": "   "},
        )
        self.assertFalse(blank_summary.get("ok"), msg=blank_summary)
        self.assertEqual(blank_summary.get("permission_boundary"), "request-payload")

        missing_id_field = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"resolution_summary": "x"},
        )
        self.assertFalse(missing_id_field.get("ok"), msg=missing_id_field)
        self.assertEqual(missing_id_field.get("permission_boundary"), "request-payload")

        before_comment_count = len(env_store.list_comments())
        missing_comment = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"comment_id": "comment-missing", "resolution_summary": "x"},
        )
        self.assertFalse(missing_comment.get("ok"), msg=missing_comment)
        self.assertEqual(len(env_store.list_comments()), before_comment_count)

        env_store.update_track(str(track["id"]), {"archived_at": "2026-05-21T10:00:00+08:00"})
        archived_target = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"comment_id": root_id, "resolution_summary": "x"},
        )
        self.assertFalse(archived_target.get("ok"), msg=archived_target)
        self.assertEqual(archived_target.get("permission_boundary"), "track.lifecycle_status")

    def test_comment_resolve_rejects_already_resolved_and_reopen_is_unsupported(self) -> None:
        track = self._seed_track("track-cmt-resolve-state")
        pm_instance_id = "inst-cmt-state-pm"
        dev_instance_id = "inst-cmt-state-dev"
        dev_instance_json = self._instance_json(instance_id=dev_instance_id, buddy="dev")

        root = self._dispatch(
            instance_json=dev_instance_json,
            instance_id=dev_instance_id,
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track["id"], "content": "root"},
        )
        reply = self._dispatch(
            instance_json=dev_instance_json,
            instance_id=dev_instance_id,
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "track",
                "target_id": track["id"],
                "content": "reply",
                "reply_to": (root.get("comment") or {}).get("id"),
            },
        )
        self.assertTrue(root.get("ok"), msg=root)
        self.assertTrue(reply.get("ok"), msg=reply)
        root_id = str((root.get("comment") or {}).get("id"))

        first_resolve = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"comment_id": root_id, "resolution_summary": "done"},
        )
        self.assertTrue(first_resolve.get("ok"), msg=first_resolve)

        second_resolve = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"comment_id": root_id, "resolution_summary": "done again"},
        )
        self.assertFalse(second_resolve.get("ok"), msg=second_resolve)
        self.assertEqual(second_resolve.get("permission_boundary"), "comment.state")

        reopened = self._dispatch(
            instance_json=self._instance_json(instance_id=pm_instance_id, buddy="pm"),
            instance_id=pm_instance_id,
            buddy="pm",
            tool="comment",
            action="reopen",
            args={"comment_id": root_id},
        )
        self.assertFalse(reopened.get("ok"), msg=reopened)
        self.assertEqual((reopened.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_mentions_must_reference_manifest_buddies(self) -> None:
        track = self._seed_track("track-cmt-mentions")
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")
        ok = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "track",
                "target_id": track["id"],
                "content": "with mentions",
                "mentions": ["pm", "design"],
            },
        )
        self.assertTrue(ok.get("ok"), msg=ok)
        self.assertEqual((ok.get("comment") or {}).get("mentions"), ["pm", "design"])

        bad = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={
                "target_type": "track",
                "target_id": track["id"],
                "content": "bad mention",
                "mentions": ["ops"],
            },
        )
        self.assertFalse(bad.get("ok"), msg=bad)
        self.assertEqual((bad.get("error") or {}).get("code"), "E_COMMENT_PAYLOAD")

    def test_comment_tool_reuses_artifact_read_boundary_for_drafts(self) -> None:
        env_store.create_artifact_revision(
            artifact_id="art-cmt-draft-private",
            title="Draft",
            summary="",
            body="draft body",
            template="note",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        before = self._snapshot_artifact_json("art-cmt-draft-private")
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")
        add = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": "art-cmt-draft-private", "content": "no access"},
        )
        self.assertFalse(add.get("ok"), msg=add)
        self.assertEqual(add.get("permission_boundary"), "artifact.status")
        self.assertEqual(self._snapshot_artifact_json("art-cmt-draft-private"), before)

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "artifact", "target_id": "art-cmt-draft-private", "status": "all"},
        )
        self.assertFalse(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("permission_boundary"), "artifact.status")
        self.assertEqual(self._snapshot_artifact_json("art-cmt-draft-private"), before)

    def test_archived_artifact_rejects_comment_add(self) -> None:
        artifact_id = self._seed_published_artifact(artifact_id="art-cmt-archived")
        env_store.update_track("track-comment", {"archived_at": "2026-05-18T10:00:00+08:00"})
        before_artifact = self._snapshot_artifact_json(artifact_id)
        before_track = self._snapshot_track_json("track-comment")
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")

        add = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "artifact", "target_id": artifact_id, "content": "no archived comments"},
        )
        self.assertFalse(add.get("ok"), msg=add)
        self.assertEqual(add.get("permission_boundary"), "track.lifecycle_status")
        self.assertEqual(self._snapshot_artifact_json(artifact_id), before_artifact)
        self.assertEqual(self._snapshot_track_json("track-comment"), before_track)


if __name__ == "__main__":
    unittest.main()
