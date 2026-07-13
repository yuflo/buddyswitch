"""Track comment repository tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.repos import runtime_files  # noqa: E402
from env.repos import track_comments as comment_repo  # noqa: E402


ACTOR_DEV = {"actor_id": "act-dev-track-comments", "role_id": "dev"}
ACTOR_PM = {"actor_id": "act-pm-track-comments", "role_id": "pm"}
ACTOR_DEV_ID = ACTOR_DEV["actor_id"]
ACTOR_PM_ID = ACTOR_PM["actor_id"]


class TrackCommentsRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.runtime_root = Path(self._tmp_dir.name)
        (self.runtime_root / "AGENTS.md").write_text(
            "# BuddySwitch Runtime Workspace\n\nTest runtime root.\n",
            encoding="utf-8",
        )
        runtime_files.set_runtime_root_override(self.runtime_root)

    def tearDown(self) -> None:
        runtime_files.reset_runtime_root_override()
        self._tmp_dir.cleanup()
        super().tearDown()

    def test_create_root_comment_writes_track_scoped_file_without_legacy_fields(self) -> None:
        comment = comment_repo.create_track_comment(
            track_id="track-repo-a",
            by_identity=ACTOR_DEV_ID,
            content="Root comment",
        )

        self.assertEqual(comment["track_id"], "track-repo-a")
        self.assertEqual(comment["thread_id"], comment["id"])
        self.assertIsNone(comment["reply_to"])
        self.assertEqual(comment["status"], "open")
        self.assertNotIn("target_type", comment)
        self.assertNotIn("target_id", comment)
        self.assertNotIn("anchor", comment)
        self.assertNotIn("artifact_revision_id", comment)

        path = comment_repo.track_comment_file("track-repo-a", comment["id"])
        self.assertEqual(
            path,
            self.runtime_root / "buddyswitch" / "objects" / "track-comments" / "track-repo-a" / f"{comment['id']}.json",
        )
        self.assertTrue(path.exists(), msg=path)
        self.assertFalse((self.runtime_root / "buddyswitch" / "objects" / "comments").exists())

        persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(persisted, comment)

    def test_validate_rejects_missing_track_id_and_legacy_target_fields(self) -> None:
        base = {
            "id": "comment-validate",
            "track_id": "track-validate",
            "thread_id": "comment-validate",
            "by_identity_id": ACTOR_DEV_ID,
            "content": "Validate",
            "reply_to": None,
            "mentioned_identity_ids": [],
            "status": "open",
            "created_at": runtime_files.now_iso(),
            "resolved_by_identity_id": None,
            "resolved_at": None,
            "resolution_summary": None,
        }

        missing_track = dict(base)
        missing_track.pop("track_id")
        with self.assertRaisesRegex(ValueError, "track_id"):
            comment_repo.validate_track_comment(missing_track)

        for field in ("target_type", "target_id", "anchor", "artifact_revision_id"):
            payload = dict(base)
            payload[field] = "legacy"
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "unsupported track comment fields"):
                    comment_repo.validate_track_comment(payload)

    def test_reply_inherits_thread_and_rejects_cross_track_parent(self) -> None:
        root_a = comment_repo.create_track_comment(
            track_id="track-reply-a",
            by_identity=ACTOR_DEV_ID,
            content="Root A",
        )
        root_b = comment_repo.create_track_comment(
            track_id="track-reply-b",
            by_identity=ACTOR_DEV_ID,
            content="Root B",
        )

        reply = comment_repo.reply_to_track_comment(
            track_id="track-reply-a",
            reply_to=root_a["id"],
            by_identity=ACTOR_PM_ID,
            content="Reply A",
        )
        self.assertEqual(reply["reply_to"], root_a["id"])
        self.assertEqual(reply["thread_id"], root_a["thread_id"])
        self.assertEqual(reply["track_id"], "track-reply-a")

        before = comment_repo.comments_for_track("track-reply-a")
        with self.assertRaisesRegex(ValueError, "different track"):
            comment_repo.reply_to_track_comment(
                track_id="track-reply-a",
                reply_to=root_b["id"],
                by_identity=ACTOR_PM_ID,
                content="Bad cross-track reply",
            )
        self.assertEqual(comment_repo.comments_for_track("track-reply-a"), before)

    def test_thread_reads_are_exact_track_scoped_when_thread_ids_collide(self) -> None:
        root_a = comment_repo.create_track_comment(
            track_id="track-thread-a",
            by_identity=ACTOR_DEV_ID,
            content="Root A",
            thread_id="thread-shared",
        )
        root_b = comment_repo.create_track_comment(
            track_id="track-thread-b",
            by_identity=ACTOR_DEV_ID,
            content="Root B",
            thread_id="thread-shared",
        )

        rows_a = comment_repo.comments_for_track_thread("track-thread-a", "thread-shared")
        rows_b = comment_repo.comments_for_track_thread("track-thread-b", "thread-shared")

        self.assertEqual([row["id"] for row in rows_a], [root_a["id"]])
        self.assertEqual([row["id"] for row in rows_b], [root_b["id"]])

    def test_resolve_track_comment_thread_updates_only_one_track(self) -> None:
        root_a = comment_repo.create_track_comment(
            track_id="track-resolve-a",
            by_identity=ACTOR_DEV_ID,
            content="Root A",
            thread_id="thread-collide",
        )
        reply_a = comment_repo.reply_to_track_comment(
            track_id="track-resolve-a",
            reply_to=root_a["id"],
            by_identity=ACTOR_PM_ID,
            content="Reply A",
        )
        root_b = comment_repo.create_track_comment(
            track_id="track-resolve-b",
            by_identity=ACTOR_DEV_ID,
            content="Root B",
            thread_id="thread-collide",
        )

        resolved = comment_repo.resolve_track_comment_thread(
            track_id="track-resolve-a",
            comment_id=reply_a["id"],
            resolved_by_identity=ACTOR_PM_ID,
            resolution_summary="Resolved in Track A only.",
        )

        self.assertEqual({row["id"] for row in resolved}, {root_a["id"], reply_a["id"]})
        self.assertTrue(all(row["status"] == "resolved" for row in resolved))
        self.assertEqual(comment_repo.get_track_comment("track-resolve-b", root_b["id"])["status"], "open")


if __name__ == "__main__":
    unittest.main()
