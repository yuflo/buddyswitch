"""Env store V1 contract tests for artifact collaboration page model."""

from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.env.repos import messages as message_repo
from buddyswitch.env.repos import runtime_files
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track.private.state import track_comments as track_comment_repo
from buddyswitch.modules.track.private.state import tracks as track_repo
from tests.support import object_builders
from tests.support import task_fixtures  # noqa: E402

from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


class ArtifactStoreContractTests(RuntimeWorkspaceTestCase):
    def _artifact_path(self, artifact_id: str) -> Path:
        return self._state_path(f"buddyswitch/objects/artifacts/{artifact_id}.json")

    def test_create_artifact_uses_independent_content_carrier_shape(self) -> None:
        artifact = object_builders.create_artifact_revision(
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
        self.assertEqual(artifact["created_by_identity_id"], "act-pm-fixture")
        self.assertEqual(artifact["author_identity_ids"], ["act-pm-fixture"])
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
                    artifact_repo.validate_artifact(payload)

    def test_superseding_artifact_is_artifact_local_currentness(self) -> None:
        r1 = object_builders.create_artifact_revision(
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

        r2 = object_builders.create_artifact_revision(
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

        stored_r1 = artifact_repo.get_artifact("art-pm-lineage-r1")
        stored_r2 = artifact_repo.get_artifact("art-pm-lineage-r2")
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


class RuntimeRootFoundationTests(RuntimeWorkspaceTestCase):
    def test_environment_bound_runtime_roots_route_object_writes_to_state(self) -> None:
        runtime_root = self.runtime_root.resolve(strict=False)
        runtime_state_root = self.runtime_state_root.resolve(strict=False)
        self.assertEqual(runtime_files.ROOT, runtime_root)
        self.assertEqual(runtime_files.STATE_ROOT, runtime_state_root)
        self.assertEqual(runtime_files.runtime_workspace_root(), runtime_root)

        artifact_id = f"art-pm-runtime-root-{uuid.uuid4().hex[:8]}-r1"
        object_builders.create_artifact_revision(
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

        runtime_path = self._state_path(f"buddyswitch/objects/artifacts/{artifact_id}.json")
        source_checkout_path = ROOT / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
        self.assertTrue(runtime_path.exists())
        self.assertFalse(source_checkout_path.exists())

    def test_environment_refresh_syncs_env_store_bindings(self) -> None:
        alternate_shared_root = self._runtime_path("runtime-root-env-sync")
        alternate_runtime_root = alternate_shared_root / "workspace"
        alternate_state_root = alternate_shared_root / "state"
        alternate_runtime_root.mkdir(parents=True, exist_ok=True)
        alternate_state_root.mkdir(parents=True, exist_ok=True)
        (alternate_runtime_root / "AGENTS.md").write_text(
            runtime_files.RUNTIME_WORKSPACE_AGENTS_HEADER + "\n",
            encoding="utf-8",
        )

        try:
            with mock.patch.dict(
                os.environ,
                {
                    "BUDDYSWITCH_SHARED_ROOT": str(alternate_shared_root),
                    "BUDDYSWITCH_STATE_ROOT": str(alternate_state_root),
                    "BUDDYSWITCH_WORKSPACE_DIR": str(alternate_runtime_root),
                },
            ):
                runtime_files.refresh_runtime_roots_from_env()
                self.assertEqual(runtime_files.ROOT, alternate_shared_root.resolve(strict=False))
                self.assertEqual(runtime_files.STATE_ROOT, alternate_state_root.resolve(strict=False))
                self.assertEqual(runtime_files.runtime_workspace_root(), alternate_runtime_root.resolve(strict=False))

                artifact_id = f"art-pm-env-sync-{uuid.uuid4().hex[:8]}-r1"
                object_builders.create_artifact_revision(
                    artifact_id=artifact_id,
                    title="Environment Sync Runtime Root",
                    summary="listener proof",
                    body="runtime environment listener write path",
                    template="note",
                    supersedes_artifact_id=None,
                    created_by="pm",
                    authors=["pm"],
                    source_refs=[{"type": "note", "label": "seed"}],
                )

                alternate_path = alternate_state_root / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
                original_path = self.runtime_state_root / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"
                self.assertTrue(alternate_path.exists())
                self.assertFalse(original_path.exists())
        finally:
            runtime_files.refresh_runtime_roots_from_env()


class ArtifactCompatibilityTests(RuntimeWorkspaceTestCase):
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
        artifact_repo.artifact_file("art-design-legacy-r1").parent.mkdir(parents=True, exist_ok=True)
        artifact_repo.artifact_file("art-design-legacy-r1").write_text(
            json.dumps(legacy_payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "retired"):
            artifact_repo.get_artifact("art-design-legacy-r1")


class TaskTrackStoreContractTests(RuntimeWorkspaceTestCase):
    def test_task_track_id_hint_does_not_mutate_track_state(self) -> None:
        object_builders.create_track(
            "track-task-hint",
            "Task Hint",
            owner_identity="act-pm-task-hint",
            outcome="Task hint outcome",
            now={"next": "seed", "blocker": None},
        )
        before = json.loads(track_repo._track_file("track-task-hint").read_text(encoding="utf-8"))

        instance_root = self._instance_root("act-task-track-hint")
        result = task_fixtures.create_task(
            actor_target={"actor_id": "act-dev-task-track-hint", "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-task-track-hint",
                "basis_revision": 1,
                "demand_ref": "dref-task-track-hint",
            },
            objective=f"Exercise the Task projection. Track context: track-task-hint. Instance: {instance_root}.",
            selection_reason="The Task slot is empty and this fixture Demand is selected.",
        )
        task = result["task"]

        after = json.loads(track_repo._track_file("track-task-hint").read_text(encoding="utf-8"))
        self.assertEqual(after, before)
        self.assertEqual(
            task["demand_ref"],
            {
                "demand_id": "demand-task-track-hint",
                "basis_revision": 1,
                "demand_ref": "dref-task-track-hint",
            },
        )
        self.assertIn(
            "Track context: track-task-hint",
            task["objective"],
        )
        self.assertNotIn("artifact_ids", task)
        self.assertNotIn("artifact_slots", task)

        stored = task_fixtures.get_task_record(result["task_id"])
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
        with self.assertRaisesRegex(ValueError, "retired or invalid Task record"):
            task_fixtures.validate_task_record(payload)


class TrackStoreContractTests(RuntimeWorkspaceTestCase):
    def test_create_track_uses_artifact_relations_not_publication_slots(self) -> None:
        track = object_builders.create_track(
            "track-relation-shape",
            "Relation Shape",
            owner_identity="act-pm-relation",
            outcome="Relation outcome",
            now={"next": "seed", "blocker": None},
        )

        self.assertIn("artifact_relations", track)
        self.assertEqual(track["artifact_relations"], [])
        self.assertNotIn("shared_materials", track)
        self.assertNotIn("close_proof", track)

        stored = track_repo.get_track("track-relation-shape")
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
            "owner_identity_id": "act-pm-reject-track",
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
                    track_repo.validate_track(payload)

    def test_validate_track_normalizes_artifact_relations(self) -> None:
        track = track_repo.validate_track(
            {
                "id": "track-relation-normalize",
                "title": "Relation Normalize",
                "outcome": "outcome",
                "owner_identity_id": "act-pm-relation",
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
                        "from_identity_id": "act-pm-relation",
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
            "owner_identity_id": "act-pm-relation",
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
                    "from_identity_id": "act-pm-relation",
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
            track_repo.validate_track(payload)

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
            track_repo.validate_track(payload)


class MessageStoreRetirementTests(RuntimeWorkspaceTestCase):
    def test_legacy_message_object_apis_are_retired(self) -> None:
        for name in ("validate_message", "list_messages", "get_message", "save_message", "create_message"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(message_repo, name))

    def test_runtime_env_store_message_api_guidance_points_to_identity_im(self) -> None:
        for name in ("save_im_message", "list_im_messages", "get_im_message"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(message_repo, name)))


class CommentStoreTests(RuntimeWorkspaceTestCase):
    def test_track_comment_helper_normalizes_role_author_to_identity(self) -> None:
        created = object_builders.create_track_comment(
            track_id="track-helper-comments",
            by_role="pm",
            content="track scoped",
        )

        self.assertEqual(created["track_id"], "track-helper-comments")
        self.assertEqual(created["by_identity_id"], "act-pm-fixture")
        self.assertNotIn("target_type", created)
        self.assertNotIn("target_id", created)
        self.assertEqual(created["thread_id"], created["id"])
        self.assertEqual(created["status"], "open")
        self.assertEqual(created["mentioned_identity_ids"], [])

        persisted = track_comment_repo.get_track_comment("track-helper-comments", created["id"])
        self.assertEqual(persisted, created)
        path = track_comment_repo.track_comment_file("track-helper-comments", created["id"])
        self.assertTrue(path.exists(), msg=path)
