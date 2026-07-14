"""Artifact env.tool integration tests for the single publication path."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import env_legacy_store as env_store  # noqa: E402
from env.repos import artifacts as artifact_repo  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.integration.env_tool._artifact_env_tool_case import ArtifactEnvToolCase

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactRelationTests(ArtifactEnvToolCase):
    def test_get_relation_summary_includes_publication_and_lineage(self) -> None:
        shared_actor_id = "act-art-rel-lineage"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                track_id="track-art-rel-lineage",
            ).get("ok")
        )
        created_r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-lineage-r1",
                "title": "Lineage v1",
                "summary": "v1",
                "template": "brief",
                "body": "v1",
            },
        )
        self.assertTrue(created_r1.get("ok"), msg=created_r1)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                role="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-rel-lineage",
                    "artifact_id": "art-lineage-r1",
                    "label": "Brief",
                    "summary": "v1",
                },
            ).get("ok")
        )

        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        created_dev_private = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-lineage-private-r2",
                "title": "Private supersede",
                "summary": "private",
                "template": "brief",
                "body": "private",
                "source_refs": [{"type": "artifact", "id": "art-lineage-r1"}],
                "read_claim": "summarized-full-content",
            },
        )
        self.assertTrue(created_dev_private.get("ok"), msg=created_dev_private)

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        created_r2 = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-lineage-r2",
                "title": "Lineage v2",
                "summary": "v2",
                "template": "brief",
                "body": "v2",
                "supersedes_artifact_id": "art-lineage-r1",
            },
        )
        self.assertTrue(created_r2.get("ok"), msg=created_r2)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                role="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-rel-lineage",
                    "artifact_id": "art-lineage-r2",
                    "label": "Brief",
                    "summary": "v2",
                },
            ).get("ok")
        )

        fetched = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-lineage-r1"},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        artifact = fetched.get("artifact")
        self.assertIsInstance(artifact, dict, msg=fetched)
        assert isinstance(artifact, dict)
        relation_summary = artifact.get("relation_summary")
        self.assertIsInstance(relation_summary, dict, msg=artifact)
        assert isinstance(relation_summary, dict)
        track_relations = relation_summary.get("track_relations")
        self.assertIsInstance(track_relations, list, msg=relation_summary)
        assert isinstance(track_relations, list)
        self.assertEqual(len(track_relations), 1)
        self.assertEqual(track_relations[0].get("track_id"), "track-art-rel-lineage")
        self.assertEqual(track_relations[0].get("relation"), "track_history")
        self.assertEqual(track_relations[0].get("currentness"), "superseded")
        self.assertNotIn("publication", relation_summary)
        lineage = relation_summary.get("lineage")
        self.assertIsInstance(lineage, dict, msg=relation_summary)
        assert isinstance(lineage, dict)
        self.assertIsNone(lineage.get("supersedes_artifact_id"))
        superseded_by = lineage.get("superseded_by_artifact_ids")
        self.assertIsInstance(superseded_by, list, msg=lineage)
        assert isinstance(superseded_by, list)
        self.assertIn("art-lineage-r2", superseded_by)
        self.assertNotIn("art-lineage-private-r2", superseded_by)

    def test_get_relation_summary_includes_permission_filtered_incoming_refs(self) -> None:
        shared_actor_id = "act-art-rel-incoming"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                track_id="track-art-rel-incoming",
            ).get("ok")
        )
        created_target = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-rel-target",
                "title": "Relation target",
                "summary": "target",
                "template": "brief",
                "body": "target body",
            },
        )
        self.assertTrue(created_target.get("ok"), msg=created_target)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                role="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-rel-incoming",
                    "artifact_id": "art-rel-target",
                    "label": "Target",
                    "summary": "target",
                },
            ).get("ok")
        )

        visible_source = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-rel-source-visible",
                "title": "Visible source",
                "summary": "visible",
                "template": "note",
                "body": "visible",
                "source_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(visible_source.get("ok"), msg=visible_source)

        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        private_source = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-rel-source-private",
                "title": "Private source",
                "summary": "private",
                "template": "note",
                "body": "private",
                "source_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(private_source.get("ok"), msg=private_source)

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        added_update = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": "track-art-rel-incoming",
                "kind": "progress",
                "summary": "Target update",
                "refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(added_update.get("ok"), msg=added_update)
        update_id = str(added_update.get("update_id") or "")
        if not update_id:
            track = env_store.get_track("track-art-rel-incoming")
            self.assertIsInstance(track, dict, msg=added_update)
            assert isinstance(track, dict)
            updates = [row for row in track.get("updates", []) if isinstance(row, dict)]
            self.assertTrue(updates, msg=track)
            update_id = str(updates[-1].get("id") or "")
        self.assertTrue(update_id)

        fetched = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-rel-target"},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        artifact = fetched.get("artifact")
        self.assertIsInstance(artifact, dict, msg=fetched)
        assert isinstance(artifact, dict)
        relation_summary = artifact.get("relation_summary")
        self.assertIsInstance(relation_summary, dict, msg=artifact)
        assert isinstance(relation_summary, dict)
        incoming_refs = relation_summary.get("incoming_refs")
        self.assertIsInstance(incoming_refs, dict, msg=relation_summary)
        assert isinstance(incoming_refs, dict)

        source_rows = incoming_refs.get("source_ref_by_artifacts")
        self.assertIsInstance(source_rows, list, msg=incoming_refs)
        assert isinstance(source_rows, list)
        source_artifact_ids = {
            str(row.get("artifact_id"))
            for row in source_rows
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-rel-source-visible", source_artifact_ids)
        self.assertNotIn("art-rel-source-private", source_artifact_ids)
        for row in source_rows:
            if isinstance(row, dict):
                self.assertNotIn("body", row, msg=row)

        self.assertNotIn("target_ref_by_" + "requests", incoming_refs)
        self.assertNotIn("result_ref_by_" + "requests", incoming_refs)

        update_rows = incoming_refs.get("track_update_refs")
        self.assertIsInstance(update_rows, list, msg=incoming_refs)
        assert isinstance(update_rows, list)
        update_ids = {
            str(row.get("update_id"))
            for row in update_rows
            if isinstance(row, dict) and isinstance(row.get("update_id"), str)
        }
        self.assertIn(update_id, update_ids)

        self.assertNotIn("comment_ids", incoming_refs)

