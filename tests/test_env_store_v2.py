#!/usr/bin/env python3
"""Env store v2 contract tests for track-page collaboration model."""

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

from env_store import (  # noqa: E402
    create_artifact,
    create_task,
    create_track,
    get_artifact,
    get_track,
    validate_artifact,
    validate_task,
    validate_track,
)
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class TrackStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _track_payload(self, track_id: str = "track-landing-proof") -> dict[str, object]:
        return {
            "id": track_id,
            "title": "Landing page first proof",
            "outcome": "Validate whether the landing page explains the core value.",
            "owner_buddy": "pm",
            "state": "active",
            "health": "ok",
            "appetite": "2 days",
            "now": {"next": "Design drafts first-screen structure.", "blocker": None},
            "shared_materials": [],
            "updates": [],
            "close_proof": [],
            "created_at": "2026-05-17T12:00:00+08:00",
            "updated_at": "2026-05-17T12:00:00+08:00",
            "archived_at": None,
        }

    def test_validate_track_accepts_page_shape_and_rejects_relation_fields(self) -> None:
        normalized = validate_track(self._track_payload())
        self.assertEqual(normalized["state"], "active")
        self.assertEqual(normalized["health"], "ok")
        self.assertEqual(normalized["shared_materials"], [])
        self.assertEqual(normalized["updates"], [])
        self.assertEqual(normalized["close_proof"], [])

        for field, value in (
            ("task_ids", ["task-old"]),
            ("status", "active"),
            ("summary", "legacy summary"),
            ("artifact_ids", ["art-old"]),
            ("current_buddy", "pm"),
            ("next_buddy", "dev"),
        ):
            payload = self._track_payload(track_id=f"track-bad-{field.replace('_', '-')}")
            payload[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    validate_track(payload)

    def test_create_task_with_track_hint_does_not_mutate_track(self) -> None:
        track = create_track(
            "track-private-hint",
            "Private hint track",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "next", "blocker": None},
        )
        before = json.loads(json.dumps(get_track(track["id"])))

        task = create_task(
            "task-dev-private-hint",
            "Dev private task",
            buddy="dev",
            track_id=track["id"],
            summary="private hint",
        )
        self.assertEqual(task["track_id"], track["id"])

        after = get_track(track["id"])
        self.assertEqual(before, after)


class ArtifactPublicationStoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_publish_material_writes_track_ref_and_artifact_metadata(self) -> None:
        create_track(
            "track-publish-material",
            "Publish material",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "publish", "blocker": None},
        )

        artifact = create_artifact(
            artifact_id="art-pm-prd-r1",
            title="PRD",
            kind="prd",
            created_by="pm",
            published_to_track=None,
            summary="PM PRD",
            content={"body": "PRD body"},
            source_refs=[{"type": "note", "label": "seed"}],
        )

        env_store.publish_track_material(
            track_id="track-publish-material",
            artifact_id=artifact["id"],
            label="PRD",
            from_buddy="pm",
            summary="PM PRD",
        )

        track = get_track("track-publish-material")
        self.assertEqual(len(track["shared_materials"]), 1)
        ref = track["shared_materials"][0]
        self.assertEqual(ref["artifact_id"], artifact["id"])
        self.assertTrue(ref["current"])

        stored_artifact = get_artifact(artifact["id"])
        self.assertEqual(stored_artifact["published_to_track"], "track-publish-material")
        self.assertEqual(stored_artifact["publication_role"], "material")
        self.assertNotIn("task_id", stored_artifact)

    def test_publish_proof_writes_exact_close_proof_ref(self) -> None:
        create_track(
            "track-proof",
            "Proof track",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "proof", "blocker": None},
        )
        artifact = create_artifact(
            artifact_id="art-test-proof-r1",
            title="Smoke",
            kind="smoke-test",
            created_by="test",
            published_to_track=None,
            summary="Smoke result",
            content={"ok": True},
            source_refs=[],
        )

        env_store.publish_track_proof(
            track_id="track-proof",
            artifact_id=artifact["id"],
            label="Smoke",
            from_buddy="test",
            summary="smoke ok",
        )

        track = get_track("track-proof")
        self.assertEqual(len(track["close_proof"]), 1)
        self.assertEqual(track["close_proof"][0]["artifact_id"], artifact["id"])
        self.assertEqual(track["shared_materials"], [])

        stored_artifact = get_artifact(artifact["id"])
        self.assertEqual(stored_artifact["publication_role"], "proof")

    def test_publish_material_rejects_cross_track_republish_without_state_pollution(self) -> None:
        create_track(
            "track-material-a",
            "Material A",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "seed", "blocker": None},
        )
        create_track(
            "track-material-b",
            "Material B",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "seed", "blocker": None},
        )
        artifact = create_artifact(
            artifact_id="art-cross-material-r1",
            title="Cross material",
            kind="prd",
            created_by="pm",
            summary="cross",
            content={"body": "cross"},
        )

        env_store.publish_track_material(
            track_id="track-material-a",
            artifact_id=artifact["id"],
            label="PRD",
            from_buddy="pm",
            summary="published a",
        )
        before_target = json.loads(json.dumps(get_track("track-material-b")))

        with self.assertRaises(ValueError):
            env_store.publish_track_material(
                track_id="track-material-b",
                artifact_id=artifact["id"],
                label="PRD",
                from_buddy="pm",
                summary="published b",
            )

        self.assertEqual(get_track("track-material-b"), before_target)
        stored = get_artifact(artifact["id"])
        self.assertEqual(stored["published_to_track"], "track-material-a")
        self.assertEqual(stored["publication_role"], "material")

    def test_publish_proof_rejects_cross_track_republish_without_state_pollution(self) -> None:
        create_track(
            "track-proof-a",
            "Proof A",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "seed", "blocker": None},
        )
        create_track(
            "track-proof-b",
            "Proof B",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "seed", "blocker": None},
        )
        artifact = create_artifact(
            artifact_id="art-cross-proof-r1",
            title="Cross proof",
            kind="smoke-test",
            created_by="test",
            summary="cross",
            content={"body": "cross"},
        )

        env_store.publish_track_proof(
            track_id="track-proof-a",
            artifact_id=artifact["id"],
            label="Smoke",
            from_buddy="test",
            summary="published a",
        )
        before_target = json.loads(json.dumps(get_track("track-proof-b")))

        with self.assertRaises(ValueError):
            env_store.publish_track_proof(
                track_id="track-proof-b",
                artifact_id=artifact["id"],
                label="Smoke",
                from_buddy="test",
                summary="published b",
            )

        self.assertEqual(get_track("track-proof-b"), before_target)
        stored = get_artifact(artifact["id"])
        self.assertEqual(stored["published_to_track"], "track-proof-a")
        self.assertEqual(stored["publication_role"], "proof")


class TaskAndArtifactValidationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_validate_task_rejects_artifact_linkage_fields(self) -> None:
        payload = {
            "id": "task-dev-private",
            "buddy": "dev",
            "title": "Private task",
            "status": "active",
            "track_id": None,
            "summary": "",
            "created_at": "2026-05-17T12:00:00+08:00",
            "updated_at": "2026-05-17T12:00:00+08:00",
        }
        normalized = validate_task(payload)
        self.assertNotIn("artifact_ids", normalized)
        self.assertNotIn("artifact" + "_slots", normalized)

        with self.assertRaises(ValueError):
            validate_task({**payload, "artifact_ids": ["art-old"]})
        with self.assertRaises(ValueError):
            validate_task({**payload, "artifact" + "_slots": {"prd": {"current_artifact_id": "art-old", "revision_count": 1}}})

    def test_validate_artifact_accepts_published_to_track_and_rejects_task_id(self) -> None:
        create_track(
            "track-artifact-shape",
            "Artifact shape",
            owner_buddy="pm",
            outcome="Outcome",
            appetite="1 day",
            now={"next": "shape", "blocker": None},
        )
        payload = {
            "id": "art-shape-r1",
            "title": "Artifact",
            "kind": "prd",
            "created_by": "pm",
            "published_to_track": "track-artifact-shape",
            "publication_role": "material",
            "summary": "summary",
            "content": {"body": "..."},
            "source_refs": [],
            "revision": 1,
            "supersedes_artifact_id": None,
            "is_current": True,
            "created_at": "2026-05-17T12:00:00+08:00",
            "updated_at": "2026-05-17T12:00:00+08:00",
        }
        normalized = validate_artifact(payload)
        self.assertEqual(normalized["published_to_track"], "track-artifact-shape")

        with self.assertRaises(ValueError):
            validate_artifact({**payload, "task_id": "task-old"})


if __name__ == "__main__":
    unittest.main()
