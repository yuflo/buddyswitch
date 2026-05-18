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
            status="published",
            published_to_track=track_id,
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        return str(artifact["id"])

    def test_add_and_list_track_comment_thread_without_target_mutation(self) -> None:
        track = self._seed_track("track-cmt-thread")
        before = env_store.get_track(track["id"])

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
        self.assertEqual(env_store.get_track(track["id"]), before)

    def test_artifact_comment_is_separate_from_artifact_body(self) -> None:
        artifact_id = self._seed_published_artifact(artifact_id="art-cmt-body-separate")
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

        artifact = env_store.get_artifact(artifact_id)
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("body"), "Original body")

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
            status="published",
            published_to_track=track_id,
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.create_artifact_revision(
            artifact_id="art-cmt-chain-r2",
            title="r2",
            summary="r2",
            body="r2",
            template="brief",
            status=None,
            published_to_track=None,
            supersedes_artifact_id="art-cmt-chain-r1",
            created_by="pm",
            authors=None,
            source_refs=[{"type": "note", "label": "seed"}],
        )
        self._seed_published_artifact(artifact_id="art-cmt-other-r1", track_id=track_id)

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

    def test_resolve_and_reopen_thread_updates_thread_status(self) -> None:
        track = self._seed_track("track-cmt-resolve")
        instance_json = self._instance_json(instance_id="inst-dev-cmt", buddy="dev")

        root = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": track["id"], "content": "root"},
        )
        reply = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
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

        resolved = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="resolve",
            args={"comment_id": (reply.get("comment") or {}).get("id")},
        )
        self.assertTrue(resolved.get("ok"), msg=resolved)

        after_resolve = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"], "status": "all"},
        )
        self.assertTrue(after_resolve.get("ok"), msg=after_resolve)
        self.assertEqual((after_resolve.get("status_counts") or {}).get("open"), 0)

        reopened = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="reopen",
            args={"comment_id": (root.get("comment") or {}).get("id")},
        )
        self.assertTrue(reopened.get("ok"), msg=reopened)
        after_reopen = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cmt",
            buddy="dev",
            tool="comment",
            action="list",
            args={"target_type": "track", "target_id": track["id"], "status": "all"},
        )
        self.assertEqual((after_reopen.get("status_counts") or {}).get("open"), 2)

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
            status="draft",
            published_to_track=None,
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
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

    def test_archived_artifact_rejects_comment_add(self) -> None:
        artifact_id = self._seed_published_artifact(artifact_id="art-cmt-archived")
        env_store.archive_artifact(artifact_id, "pm")
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
        self.assertEqual(add.get("permission_boundary"), "artifact.status")


if __name__ == "__main__":
    unittest.main()
