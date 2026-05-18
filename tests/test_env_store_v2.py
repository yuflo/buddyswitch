#!/usr/bin/env python3
"""Env store V1 contract tests for artifact collaboration page model."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402

from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class ArtifactStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _artifact_path(self, artifact_id: str) -> Path:
        return self._runtime_path(f"buddyswitch/objects/artifacts/{artifact_id}.json")

    def test_create_artifact_uses_canonical_markdown_page_shape(self) -> None:
        artifact = env_store.create_artifact_revision(
            artifact_id="art-pm-canonical-r1",
            title="Artifact canonical contract",
            summary="seed",
            body="## Context\n\nSeed",
            template="brief",
            status="draft",
            published_to_track=None,
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )

        expected_keys = {
            "id",
            "title",
            "summary",
            "body",
            "template",
            "status",
            "published_to_track",
            "revision",
            "is_current",
            "supersedes_artifact_id",
            "created_by",
            "authors",
            "source_refs",
            "created_at",
            "updated_at",
        }
        self.assertEqual(set(artifact.keys()), expected_keys)
        self.assertEqual(artifact["template"], "brief")
        self.assertEqual(artifact["status"], "draft")
        self.assertIsNone(artifact["published_to_track"])
        self.assertEqual(artifact["authors"], ["pm"])
        self.assertEqual(artifact["body"], "## Context\n\nSeed")

        stored = json.loads(self._artifact_path("art-pm-canonical-r1").read_text(encoding="utf-8"))
        self.assertEqual(set(stored.keys()), expected_keys)
        self.assertNotIn("kind", stored)
        self.assertNotIn("content", stored)
        self.assertNotIn("task_id", stored)

    def test_new_artifact_shape_rejects_retired_fields(self) -> None:
        base = {
            "id": "art-pm-reject-r1",
            "title": "Reject retired fields",
            "summary": "x",
            "body": "body",
            "template": "note",
            "status": "draft",
            "published_to_track": None,
            "revision": 1,
            "is_current": True,
            "supersedes_artifact_id": None,
            "created_by": "pm",
            "authors": ["pm"],
            "source_refs": [{"type": "note", "label": "seed"}],
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:00:00+08:00",
        }
        for retired_field in ("task_id", "kind", "content", "asset", "media", "material", "blocks", "figma_file"):
            payload = dict(base)
            payload[retired_field] = "x"
            with self.subTest(field=retired_field):
                with self.assertRaises(ValueError):
                    env_store.validate_artifact(payload)


class ArtifactCompatibilityTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_legacy_kind_content_task_artifact_normalizes_to_v1_draft(self) -> None:
        legacy_payload = {
            "id": "art-design-legacy-r1",
            "title": "Legacy artifact",
            "task_id": "task-design-old",
            "buddy": "design",
            "kind": "design-handoff",
            "summary": "legacy",
            "content": {"body": "legacy body"},
            "revision": 1,
            "is_current": True,
            "supersedes_artifact_id": None,
            "created_by": "design",
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:01:00+08:00",
        }
        env_store.artifact_file("art-design-legacy-r1").parent.mkdir(parents=True, exist_ok=True)
        env_store.artifact_file("art-design-legacy-r1").write_text(
            json.dumps(legacy_payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

        normalized = env_store.get_artifact("art-design-legacy-r1")
        self.assertIsNotNone(normalized)
        assert isinstance(normalized, dict)
        self.assertEqual(normalized["template"], "design")
        self.assertEqual(normalized["body"], "legacy body")
        self.assertEqual(normalized["status"], "draft")
        self.assertIsNone(normalized["published_to_track"])
        self.assertIn("design", normalized["authors"])

        saved = env_store.save_artifact(normalized)
        self.assertEqual(saved["template"], "design")
        raw = json.loads(env_store.artifact_file("art-design-legacy-r1").read_text(encoding="utf-8"))
        self.assertNotIn("kind", raw)
        self.assertNotIn("content", raw)
        self.assertNotIn("task_id", raw)


class TaskTrackStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_task_track_id_hint_does_not_mutate_track_state(self) -> None:
        env_store.create_track("track-task-hint", "Task Hint", owner_buddy="pm")
        before = json.loads(env_store.track_file("track-task-hint").read_text(encoding="utf-8"))

        task = env_store.create_task(
            "task-dev-track-hint",
            "Task hint",
            buddy="dev",
            track_id="track-task-hint",
        )

        after = json.loads(env_store.track_file("track-task-hint").read_text(encoding="utf-8"))
        self.assertEqual(after, before)
        self.assertEqual(task["track_id"], "track-task-hint")
        self.assertNotIn("artifact_ids", task)
        self.assertNotIn("artifact_slots", task)

        stored = env_store.get_task("task-dev-track-hint")
        self.assertIsNotNone(stored)
        assert isinstance(stored, dict)
        self.assertNotIn("artifact_ids", stored)
        self.assertNotIn("artifact_slots", stored)

    def test_validate_task_rejects_legacy_artifact_linkage_fields(self) -> None:
        payload = {
            "id": "task-dev-legacy-drop",
            "buddy": "dev",
            "title": "Legacy drop",
            "status": "active",
            "track_id": None,
            "artifact_ids": ["art-old-r1"],
            "artifact_slots": {
                "legacy": {
                    "current_artifact_id": "art-old-r1",
                    "revision_count": 1,
                }
            },
            "summary": "",
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:00:00+08:00",
        }
        with self.assertRaisesRegex(ValueError, "legacy task fields are retired: artifact_ids, artifact_slots"):
            env_store.validate_task(payload)


class TrackStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_validate_track_rejects_legacy_task_ids(self) -> None:
        payload = {
            "id": "track-pm-legacy",
            "title": "Legacy track",
            "status": "active",
            "owner_buddy": "pm",
            "task_ids": ["task-pm-old"],
            "summary": "",
            "updated_at": "2026-05-18T10:00:00+08:00",
        }
        with self.assertRaisesRegex(ValueError, "legacy track fields are retired: status, summary, task_ids"):
            env_store.validate_track(payload)


class CommentStoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_legacy_author_buddy_comment_normalizes_to_by_buddy(self) -> None:
        raw = {
            "id": "comment-legacy-author",
            "target_type": "track",
            "target_id": "track-legacy-comments",
            "author_buddy": "pm",
            "content": "legacy",
            "reply_to": None,
            "created_at": "2026-05-18T10:00:00+08:00",
        }
        env_store.comment_file("comment-legacy-author").parent.mkdir(parents=True, exist_ok=True)
        env_store.comment_file("comment-legacy-author").write_text(
            json.dumps(raw, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

        normalized = env_store.get_comment("comment-legacy-author")
        self.assertIsNotNone(normalized)
        assert isinstance(normalized, dict)
        self.assertEqual(normalized["by_buddy"], "pm")
        self.assertEqual(normalized["thread_id"], "comment-legacy-author")
        self.assertEqual(normalized["status"], "open")
        self.assertEqual(normalized["mentions"], [])

        saved = env_store.save_comment(normalized)
        self.assertEqual(saved["by_buddy"], "pm")
        persisted = json.loads(env_store.comment_file("comment-legacy-author").read_text(encoding="utf-8"))
        self.assertNotIn("author_buddy", persisted)


if __name__ == "__main__":
    unittest.main()
