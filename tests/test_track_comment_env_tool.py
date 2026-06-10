#!/usr/bin/env python3
"""Track-native comment env.tool integration tests."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.repos import track_comments as comment_repo  # noqa: E402
from env.repos import tracks as track_repo  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TrackCommentEnvToolTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.runtime_root = Path(self._tmp_dir.name)
        (self.runtime_root / "AGENTS.md").write_text(
            "# BuddySwitch Runtime Workspace\n\nTrack comment env tool test root.\n",
            encoding="utf-8",
        )
        runtime_files.set_runtime_root_override(self.runtime_root)

    def tearDown(self) -> None:
        runtime_files.reset_runtime_root_override()
        self._tmp_dir.cleanup()
        super().tearDown()

    def _runtime_actor_id(self, *, role: str, label: str) -> str:
        if label.startswith(f"act-{role}-"):
            suffix = label.removeprefix(f"act-{role}-")
            if len(suffix) == 12 and all(char in "0123456789abcdef" for char in suffix):
                return label
        digest = hashlib.sha1(f"{role}:{label}".encode("utf-8")).hexdigest()[:12]
        return f"act-{role}-{digest}"

    def _instance_json(self, *, actor_id: str, role: str) -> Path:
        normalized_actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self.runtime_root / "instances" / normalized_actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        path = instance_root / "instance.json"
        path.write_text(
            json.dumps(
                {
                    "actor_id": normalized_actor_id,
                    "role": role,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "instance_root": str(instance_root),
                    "browser_port": None,
                    "updated_at": "2026-06-10T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task(instance_root=instance_root, actor_id=normalized_actor_id, role=role)
        return path

    def _seed_active_task(self, *, instance_root: Path, actor_id: str, role: str) -> None:
        taskbox = instance_root / "taskbox" / role
        tasks_dir = taskbox / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_id = f"task-0001-{role}-track-comment"
        (tasks_dir / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "owner_actor": {"actor_id": actor_id, "role_id": role},
                    "title": "Active task",
                    "summary": "Active task seeded for track comment tests.",
                    "body": "Active task seeded for track comment tests.",
                    "status": "active",
                    "priority": "normal",
                    "origin": {"type": "manual"},
                    "track_id": None,
                    "refs": [],
                    "progress_summary": "Active task seeded for track comment tests.",
                    "created_at": "2026-06-10T00:00:00Z",
                    "updated_at": "2026-06-10T00:00:00Z",
                    "closed_at": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (taskbox / "history.md").write_text(
            f"- 2026-06-10T00:00:00Z task.selected {task_id} reason=\"seed active task fixture\"\n",
            encoding="utf-8",
        )

    def _dispatch(self, *, actor_id: str, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_json = self._instance_json(actor_id=actor_id, role=role)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-track-comment-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": self._runtime_actor_id(role=role, label=actor_id),
                "active_role": role,
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

    def _seed_track(self, track_id: str) -> dict[str, object]:
        return track_repo.create_track(
            track_id,
            f"Track {track_id}",
            owner_role="pm",
            created_by_actor={"actor_id": "act-pm-seed", "role_id": "pm"},
            outcome="Track comment test outcome",
            appetite="1 day",
            now={"next": "test", "blocker": None},
        )

    def test_add_list_reply_and_open_are_track_native(self) -> None:
        self._seed_track("track-comment-a")
        self._seed_track("track-comment-b")

        root = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-a",
                "content": "Root Track A",
                "mentioned_actors": [{"actor_id": "act-pm-mentioned", "role_id": "pm"}],
            },
        )
        self.assertTrue(root.get("ok"), msg=root)
        comment = root.get("comment")
        self.assertIsInstance(comment, dict, msg=root)
        assert isinstance(comment, dict)
        self.assertEqual(comment.get("track_id"), "track-comment-a")
        self.assertEqual(comment.get("thread_id"), comment.get("id"))
        self.assertIsNone(comment.get("reply_to"))
        self.assertNotIn("target_type", comment)
        self.assertNotIn("target_id", comment)
        self.assertTrue(comment_repo.track_comment_file("track-comment-a", str(comment["id"])).exists())
        self.assertFalse((self.runtime_root / "buddyswitch" / "objects" / "comments").exists())

        reply = self._dispatch(
            actor_id="act-design-track-comment",
            role="design",
            tool="track",
            action="add_comment",
            args={"track_id": "track-comment-a", "content": "Reply Track A", "reply_to": comment["id"]},
        )
        self.assertTrue(reply.get("ok"), msg=reply)
        reply_comment = reply.get("comment")
        self.assertIsInstance(reply_comment, dict, msg=reply)
        assert isinstance(reply_comment, dict)
        self.assertEqual(reply_comment.get("thread_id"), comment["thread_id"])

        other = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-comment-b", "content": "Root Track B"},
        )
        self.assertTrue(other.get("ok"), msg=other)
        bad_reply = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-comment-a",
                "content": "Bad cross-track reply",
                "reply_to": (other.get("comment") or {}).get("id"),
            },
        )
        self.assertFalse(bad_reply.get("ok"), msg=bad_reply)
        self.assertEqual(bad_reply.get("permission_boundary"), "track_comment.reply_to_scope")

        listed = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="list_comments",
            args={"track_id": "track-comment-a", "status": "all"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual([row.get("track_id") for row in listed.get("comments", [])], ["track-comment-a", "track-comment-a"])
        self.assertEqual(len(listed.get("threads", [])), 1)

        opened = self._dispatch(
            actor_id="act-dev-track-comment",
            role="dev",
            tool="track",
            action="open",
            args={"track_id": "track-comment-a"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        cues = ((opened.get("track") or {}).get("comment_cues") or {})
        self.assertEqual(cues.get("open_thread_count"), 1)
        self.assertLessEqual(len(cues.get("recent_comments", [])), 3)

    def test_resolve_is_pm_only_and_exact_track_scoped(self) -> None:
        self._seed_track("track-resolve-a")
        self._seed_track("track-resolve-b")
        root_a = self._dispatch(
            actor_id="act-dev-resolve-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-resolve-a", "content": "Root A"},
        )
        root_b = self._dispatch(
            actor_id="act-dev-resolve-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={"track_id": "track-resolve-b", "content": "Root B"},
        )
        self.assertTrue(root_a.get("ok"), msg=root_a)
        self.assertTrue(root_b.get("ok"), msg=root_b)
        root_a_id = str((root_a.get("comment") or {}).get("id"))
        root_b_id = str((root_b.get("comment") or {}).get("id"))

        non_pm = self._dispatch(
            actor_id="act-dev-resolve-comment",
            role="dev",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_a_id, "resolution_summary": "Nope"},
        )
        self.assertFalse(non_pm.get("ok"), msg=non_pm)
        self.assertEqual((non_pm.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
        self.assertEqual(non_pm.get("required_permission"), "track.resolve_comment_thread")

        cross_track = self._dispatch(
            actor_id="act-pm-resolve-comment",
            role="pm",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_b_id, "resolution_summary": "Wrong track"},
        )
        self.assertFalse(cross_track.get("ok"), msg=cross_track)
        self.assertEqual(cross_track.get("permission_boundary"), "track_comment.thread_scope")
        self.assertEqual(comment_repo.get_track_comment("track-resolve-b", root_b_id)["status"], "open")

        resolved = self._dispatch(
            actor_id="act-pm-resolve-comment",
            role="pm",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_a_id, "resolution_summary": "Resolved."},
        )
        self.assertTrue(resolved.get("ok"), msg=resolved)
        self.assertEqual(resolved.get("updated_ids"), [root_a_id])
        self.assertEqual((resolved.get("comments") or [])[0].get("status"), "resolved")

        repeat = self._dispatch(
            actor_id="act-pm-resolve-comment",
            role="pm",
            tool="track",
            action="resolve_comment_thread",
            args={"track_id": "track-resolve-a", "comment_id": root_a_id, "resolution_summary": "Again."},
        )
        self.assertFalse(repeat.get("ok"), msg=repeat)
        self.assertEqual(repeat.get("permission_boundary"), "track_comment.state")

    def test_old_comment_tool_and_old_payload_fields_are_rejected(self) -> None:
        self._seed_track("track-old-comment-fields")
        old_tool = self._dispatch(
            actor_id="act-dev-old-comment",
            role="dev",
            tool="comment",
            action="add",
            args={"target_type": "track", "target_id": "track-old-comment-fields", "content": "old"},
        )
        self.assertFalse(old_tool.get("ok"), msg=old_tool)
        self.assertEqual((old_tool.get("error") or {}).get("code"), "E_ENV_TOOL")

        old_fields = self._dispatch(
            actor_id="act-dev-old-comment",
            role="dev",
            tool="track",
            action="add_comment",
            args={
                "track_id": "track-old-comment-fields",
                "target_type": "artifact",
                "target_id": "art-old",
                "anchor": "section",
                "artifact_revision_id": "art-old-r1",
                "content": "old fields",
            },
        )
        self.assertFalse(old_fields.get("ok"), msg=old_fields)
        self.assertEqual(old_fields.get("permission_boundary"), "request-payload")
        self.assertEqual(
            old_fields.get("correctable_fields"),
            ["anchor", "artifact_revision_id", "target_id", "target_type"],
        )


if __name__ == "__main__":
    unittest.main()
