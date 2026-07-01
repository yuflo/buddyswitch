#!/usr/bin/env python3
"""Env store V1 contract tests for artifact collaboration page model."""

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
from env.domain import task_sys  # noqa: E402
from env.repos import runtime_files  # noqa: E402

from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class ArtifactStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _artifact_path(self, artifact_id: str) -> Path:
        return self._runtime_path(f"buddyswitch/objects/artifacts/{artifact_id}.json")

    def test_create_artifact_uses_independent_content_carrier_shape(self) -> None:
        artifact = env_store.create_artifact_revision(
            artifact_id="art-pm-canonical-r1",
            title="Artifact canonical contract",
            summary="seed",
            body="## Context\n\nSeed",
            template="brief",
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
            "revision",
            "is_current",
            "supersedes_artifact_id",
            "created_by_identity_id",
            "author_identity_ids",
            "source_refs",
            "attachments",
            "created_at",
            "updated_at",
        }
        self.assertEqual(set(artifact.keys()), expected_keys)
        self.assertEqual(artifact["template"], "brief")
        self.assertEqual(artifact["created_by_identity_id"], "act-pm-legacy")
        self.assertEqual(artifact["author_identity_ids"], ["act-pm-legacy"])
        self.assertEqual(artifact["attachments"], [])
        self.assertEqual(artifact["body"], "## Context\n\nSeed")

        stored = json.loads(self._artifact_path("art-pm-canonical-r1").read_text(encoding="utf-8"))
        self.assertEqual(set(stored.keys()), expected_keys)
        self.assertNotIn("status", stored)
        self.assertNotIn("published_to_track", stored)
        self.assertNotIn("publication_role", stored)
        self.assertNotIn("kind", stored)
        self.assertNotIn("content", stored)
        self.assertNotIn("task_id", stored)

    def test_artifact_validation_rejects_retired_and_publication_lifecycle_fields(self) -> None:
        base = {
            "id": "art-pm-reject-r1",
            "title": "Reject retired fields",
            "summary": "x",
            "body": "body",
            "template": "note",
            "revision": 1,
            "is_current": True,
            "supersedes_artifact_id": None,
            "created_by_actor": {"actor_id": "act-pm-reject", "role_id": "pm"},
            "author_actors": [{"actor_id": "act-pm-reject", "role_id": "pm"}],
            "attachments": [],
            "source_refs": [{"type": "note", "label": "seed"}],
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:00:00+08:00",
        }
        for retired_field in (
            "status",
            "published_to_track",
            "publication_role",
            "task_id",
            "kind",
            "content",
            "asset",
            "media",
            "material",
            "blocks",
            "figma_file",
        ):
            payload = dict(base)
            payload[retired_field] = "published" if retired_field == "status" else "x"
            with self.subTest(field=retired_field):
                with self.assertRaises(ValueError):
                    env_store.validate_artifact(payload)

    def test_superseding_artifact_is_artifact_local_currentness(self) -> None:
        r1 = env_store.create_artifact_revision(
            artifact_id="art-pm-lineage-r1",
            title="Artifact lineage r1",
            summary="r1",
            body="body r1",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        self.assertTrue(r1["is_current"], msg=r1)

        r2 = env_store.create_artifact_revision(
            artifact_id="art-pm-lineage-r2",
            title="Artifact lineage r2",
            summary="r2",
            body="body r2",
            template="brief",
            supersedes_artifact_id="art-pm-lineage-r1",
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "artifact", "id": "art-pm-lineage-r1"}],
        )

        stored_r1 = env_store.get_artifact("art-pm-lineage-r1")
        stored_r2 = env_store.get_artifact("art-pm-lineage-r2")
        self.assertIsInstance(stored_r1, dict)
        self.assertIsInstance(stored_r2, dict)
        assert isinstance(stored_r1, dict)
        assert isinstance(stored_r2, dict)
        self.assertFalse(stored_r1["is_current"], msg=stored_r1)
        self.assertTrue(stored_r2["is_current"], msg=stored_r2)
        self.assertEqual(r2["revision"], 2)
        self.assertEqual(r2["supersedes_artifact_id"], "art-pm-lineage-r1")
        for row in (stored_r1, stored_r2):
            self.assertNotIn("status", row)
            self.assertNotIn("published_to_track", row)
            self.assertNotIn("publication_role", row)


class RuntimeRootFoundationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_runtime_root_override_routes_object_writes_to_runtime_workspace(self) -> None:
        runtime_root = self.runtime_root.resolve(strict=False)
        self.assertEqual(env_store.ROOT, runtime_root)
        self.assertEqual(env_store.STATE_ROOT, runtime_root)
        self.assertEqual(env_store.runtime_workspace_root(), runtime_root)

        artifact_id = f"art-pm-runtime-root-{uuid.uuid4().hex[:8]}-r1"
        env_store.create_artifact_revision(
            artifact_id=artifact_id,
            title="Runtime Root",
            summary="root override proof",
            body="runtime root write path",
            template="note",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )

        runtime_path = self._runtime_path(f"buddyswitch/objects/artifacts/{artifact_id}.json")
        source_checkout_path = ROOT / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
        self.assertTrue(runtime_path.exists())
        self.assertFalse(source_checkout_path.exists())

    def test_runtime_root_override_auto_syncs_env_store_without_manual_refresh(self) -> None:
        original_runtime_root = self.runtime_root.resolve(strict=False)
        alternate_runtime_root = self._runtime_path("runtime-root-auto-sync")
        alternate_runtime_root.mkdir(parents=True, exist_ok=True)
        (alternate_runtime_root / "AGENTS.md").write_text(
            runtime_files.RUNTIME_WORKSPACE_AGENTS_HEADER + "\n",
            encoding="utf-8",
        )

        try:
            runtime_files.set_runtime_root_override(alternate_runtime_root)
            self.assertEqual(env_store.ROOT, alternate_runtime_root.resolve(strict=False))
            self.assertEqual(env_store.STATE_ROOT, alternate_runtime_root.resolve(strict=False))
            self.assertEqual(env_store.runtime_workspace_root(), alternate_runtime_root.resolve(strict=False))

            artifact_id = f"art-pm-auto-sync-{uuid.uuid4().hex[:8]}-r1"
            env_store.create_artifact_revision(
                artifact_id=artifact_id,
                title="Auto Sync Runtime Root",
                summary="listener proof",
                body="runtime root listener write path",
                template="note",
                supersedes_artifact_id=None,
                created_by="pm",
                authors=["pm"],
                source_refs=[{"type": "note", "label": "seed"}],
            )

            alternate_path = alternate_runtime_root / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
            original_path = original_runtime_root / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
            self.assertTrue(alternate_path.exists())
            self.assertFalse(original_path.exists())
        finally:
            runtime_files.set_runtime_root_override(original_runtime_root)


class ArtifactCompatibilityTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_legacy_kind_content_task_artifact_is_rejected_without_normalization(self) -> None:
        legacy_payload = {
            "id": "art-design-legacy-r1",
            "title": "Legacy artifact",
            "task_id": "task-design-old",
            "role": "design",
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

        with self.assertRaisesRegex(ValueError, "retired"):
            env_store.get_artifact("art-design-legacy-r1")


class TaskTrackStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_task_track_id_hint_does_not_mutate_track_state(self) -> None:
        env_store.create_track(
            "track-task-hint",
            "Task Hint",
            owner_actor={"actor_id": "act-pm-task-hint", "role_id": "pm"},
            outcome="Task hint outcome",
            now={"next": "seed", "blocker": None},
        )
        before = json.loads(env_store.track_file("track-task-hint").read_text(encoding="utf-8"))

        instance_root = self._instance_root("act-task-track-hint")
        result = task_sys.ingest(
            {
                "source": {"type": "test.fixture", "ref": {"title": "Task hint", "track_id": "track-task-hint"}},
                "actor_target": {"actor_id": "act-dev-task-track-hint", "role_id": "dev"},
                "context": {"instance_root": str(instance_root)},
            }
        )
        task = result["task"]

        after = json.loads(env_store.track_file("track-task-hint").read_text(encoding="utf-8"))
        self.assertEqual(after, before)
        self.assertEqual(task["source_ref"]["track_id"], "track-task-hint")
        self.assertNotIn("artifact_ids", task)
        self.assertNotIn("artifact_slots", task)

        stored = task_sys.get_task(result["task_id"])
        self.assertIsNotNone(stored)
        assert isinstance(stored, dict)
        self.assertNotIn("artifact_ids", stored)
        self.assertNotIn("artifact_slots", stored)

    def test_validate_task_rejects_legacy_artifact_linkage_fields(self) -> None:
        payload = {
            "id": "task-dev-legacy-drop",
            "role": "dev",
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
    def test_create_track_uses_artifact_relations_not_publication_slots(self) -> None:
        track = env_store.create_track(
            "track-relation-shape",
            "Relation Shape",
            owner_actor={"actor_id": "act-pm-relation", "role_id": "pm"},
            outcome="Relation outcome",
            now={"next": "seed", "blocker": None},
        )

        self.assertIn("artifact_relations", track)
        self.assertEqual(track["artifact_relations"], [])
        self.assertNotIn("shared_materials", track)
        self.assertNotIn("close_proof", track)

        stored = env_store.get_track("track-relation-shape")
        self.assertIsInstance(stored, dict)
        assert isinstance(stored, dict)
        self.assertIn("artifact_relations", stored)
        self.assertNotIn("shared_materials", stored)
        self.assertNotIn("close_proof", stored)

    def test_validate_track_rejects_publication_slot_fields(self) -> None:
        base = {
            "id": "track-reject-publication-slots",
            "title": "Reject publication slots",
            "outcome": "outcome",
            "owner_actor": {"actor_id": "act-pm-reject-track", "role_id": "pm"},
            "state": "active",
            "now": {"next": "next", "blocker": None},
            "artifact_relations": [],
            "updates": [],
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:00:00+08:00",
            "archived_at": None,
        }
        for stale_field in ("shared_materials", "close_proof"):
            payload = dict(base)
            payload[stale_field] = []
            with self.subTest(field=stale_field):
                with self.assertRaisesRegex(ValueError, "legacy track fields are retired"):
                    env_store.validate_track(payload)

    def test_validate_track_normalizes_artifact_relations(self) -> None:
        track = env_store.validate_track(
            {
                "id": "track-relation-normalize",
                "title": "Relation Normalize",
                "outcome": "outcome",
                "owner_actor": {"actor_id": "act-pm-relation", "role_id": "pm"},
                "state": "active",
                "now": {"next": "next", "blocker": None},
                "artifact_relations": [
                    {
                        "relation_id": "rel-material-r1",
                        "type": "artifact",
                        "artifact_id": "art-material-r1",
                        "role": "material",
                        "label": "Brief",
                        "template": "brief",
                        "from_actor": {"actor_id": "act-pm-relation", "role_id": "pm"},
                        "summary": "Shared brief",
                        "current": True,
                        "created_at": "2026-05-18T10:00:00+08:00",
                    }
                ],
                "updates": [],
                "created_at": "2026-05-18T10:00:00+08:00",
                "updated_at": "2026-05-18T10:00:00+08:00",
                "archived_at": None,
            }
        )

        self.assertEqual(len(track["artifact_relations"]), 1)
        relation = track["artifact_relations"][0]
        self.assertEqual(relation["role"], "material")
        self.assertEqual(relation["template"], "brief")
        self.assertTrue(relation["current"])

    def test_validate_track_rejects_invalid_artifact_relation_role(self) -> None:
        payload = {
            "id": "track-relation-invalid-role",
            "title": "Relation Invalid",
            "outcome": "outcome",
            "owner_actor": {"actor_id": "act-pm-relation", "role_id": "pm"},
            "state": "active",
            "now": {"next": "next", "blocker": None},
            "artifact_relations": [
                {
                    "relation_id": "rel-invalid",
                    "type": "artifact",
                    "artifact_id": "art-invalid",
                    "role": "publication",
                    "label": "Invalid",
                    "template": "brief",
                    "from_actor": {"actor_id": "act-pm-relation", "role_id": "pm"},
                    "summary": "Invalid",
                    "current": True,
                    "created_at": "2026-05-18T10:00:00+08:00",
                }
            ],
            "updates": [],
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:00:00+08:00",
            "archived_at": None,
        }
        with self.assertRaisesRegex(ValueError, "track.artifact_relations\\[\\].role"):
            env_store.validate_track(payload)

    def test_validate_track_rejects_legacy_task_ids(self) -> None:
        payload = {
            "id": "track-pm-legacy",
            "title": "Legacy track",
            "status": "active",
            "owner_role": "pm",
            "task_ids": ["task-pm-old"],
            "summary": "",
            "updated_at": "2026-05-18T10:00:00+08:00",
        }
        with self.assertRaisesRegex(ValueError, "legacy track fields are retired: owner_role, status, summary, task_ids"):
            env_store.validate_track(payload)


class CommentStoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_track_comment_helper_normalizes_role_author_to_actor_address(self) -> None:
        created = env_store.create_track_comment(
            track_id="track-helper-comments",
            by_role="pm",
            content="track scoped",
        )

        self.assertEqual(created["track_id"], "track-helper-comments")
        self.assertEqual(created["by_identity_id"], "act-pm-legacy")
        self.assertNotIn("target_type", created)
        self.assertNotIn("target_id", created)
        self.assertEqual(created["thread_id"], created["id"])
        self.assertEqual(created["status"], "open")
        self.assertEqual(created["mentioned_identity_ids"], [])

        persisted = env_store.get_track_comment("track-helper-comments", created["id"])
        self.assertEqual(persisted, created)
        path = env_store.track_comment_file("track-helper-comments", created["id"])
        self.assertTrue(path.exists(), msg=path)


if __name__ == "__main__":
    unittest.main()
