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


class ArtifactListingTests(ArtifactEnvToolCase):
    def test_create_revision_from_archived_published_artifact_rejects_without_new_artifact(self) -> None:
        track = env_store.create_track(
            "track-art-revision-archived",
            "Archived Revision",
            owner_identity="act-pm-system",
            outcome="Archived revision outcome",
            now={"next": "seed", "blocker": None},
        )
        artifact = env_store.create_artifact_revision(
            artifact_id="art-revision-archived-r1",
            title="Archived source",
            summary="source",
            body="source body",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=str(track["id"]),
            artifact_id=str(artifact["id"]),
            label="Archived source",
            from_role="pm",
            summary="source",
        )
        env_store.update_track(str(track["id"]), {"archived_at": "2026-05-19T00:00:00Z"})
        before_artifacts = {row["id"] for row in env_store.list_artifacts()}
        instance_json = self._instance_json(actor_id="act-pm-art-archived-revision", role="pm")

        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art-archived-revision",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-revision-archived-r2",
                "title": "New archived revision",
                "summary": "new",
                "template": "brief",
                "body": "new body",
                "supersedes_artifact_id": str(artifact["id"]),
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(set(row["id"] for row in env_store.list_artifacts()), before_artifacts)

    def test_archive_track_blocks_track_open_and_published_artifact_reads(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art", role="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, actor_id="act-pm-art", track_id="track-art-archive").get("ok"))

        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-archive-r1",
                "title": "Archive me",
                "summary": "",
                "template": "decision",
                "body": "archive body",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        published = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-archive",
                "artifact_id": "art-pm-archive-r1",
                "label": "Decision",
                "summary": "archive material",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        archived = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-art-archive"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        track_open = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="open",
            args={"track_id": "track-art-archive"},
        )
        self.assertFalse(track_open.get("ok"), msg=track_open)
        self.assertEqual(track_open.get("permission_boundary"), "track.lifecycle_status")

        owner_read = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-archive-r1"},
        )
        self.assertTrue(owner_read.get("ok"), msg=owner_read)
        self.assertEqual((owner_read.get("artifact") or {}).get("relation"), "owner")

        for role, actor_id in (("dev", "act-dev-art"),):
            instance_json = self._instance_json(actor_id=actor_id, role=role)
            denied = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_id,
                role=role,
                tool="artifact",
                action="get",
                args={"artifact_id": "art-pm-archive-r1"},
            )
            with self.subTest(role=role):
                self.assertFalse(denied.get("ok"), msg=denied)
                self.assertEqual(denied.get("permission_boundary"), "track.lifecycle_status")

    def test_list_returns_owner_draft_summaries_without_body(self) -> None:
        shared_actor_id = "act-art-list-owner"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        created_pm_brief = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-pm-brief",
                "title": "PM Brief",
                "summary": "Owner brief",
                "template": "brief",
                "body": "brief body",
                "source_refs": [{"type": "note", "label": "seed-brief"}],
            },
        )
        self.assertTrue(created_pm_brief.get("ok"), msg=created_pm_brief)
        created_pm_note = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-pm-note",
                "title": "PM Note",
                "summary": "Owner note",
                "template": "note",
                "body": "note body",
                "source_refs": [{"type": "note", "label": "seed-note"}],
            },
        )
        self.assertTrue(created_pm_note.get("ok"), msg=created_pm_note)

        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        created_dev_private = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-dev-private",
                "title": "Dev Private",
                "summary": "Private to dev",
                "template": "note",
                "body": "dev draft body",
            },
        )
        self.assertTrue(created_dev_private.get("ok"), msg=created_dev_private)

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        listed = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("state_changed"), False, msg=listed)
        self.assertEqual(listed.get("durability"), "none", msg=listed)
        rows = listed.get("artifacts")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        rows_by_id = {
            str(row.get("artifact_id")): row
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-list-pm-brief", rows_by_id)
        self.assertIn("art-list-pm-note", rows_by_id)
        self.assertNotIn("art-list-dev-private", rows_by_id)
        for artifact_id in ("art-list-pm-brief", "art-list-pm-note"):
            row = rows_by_id[artifact_id]
            self.assertNotIn("status", row, msg=row)
            self.assertEqual(row.get("currentness"), "draft", msg=row)
            self.assertEqual(row.get("relation"), "owner", msg=row)
            self.assertNotIn("body", row, msg=row)
            self.assertIsInstance(row.get("source_refs_summary"), list, msg=row)
            for key in (
                "open_comment_count",
                "resolved_comment_count",
                "incoming_source_ref_count",
                "track_update_ref_count",
                "comment_count",
            ):
                self.assertIn(key, row, msg=row)
            self.assertNotIn("target_" + "request_count", row, msg=row)
            self.assertNotIn("result_" + "request_count", row, msg=row)

    def test_list_returns_published_material_proof_and_history_summaries(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art-list-published", role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-published",
                track_id="track-art-list-published",
            ).get("ok")
        )

        created_r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-brief-r1",
                "title": "Brief v1",
                "summary": "v1",
                "template": "brief",
                "body": "v1 body",
            },
        )
        self.assertTrue(created_r1.get("ok"), msg=created_r1)
        published_r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-list-published",
                "artifact_id": "art-list-brief-r1",
                "label": "Brief",
                "summary": "v1",
            },
        )
        self.assertTrue(published_r1.get("ok"), msg=published_r1)

        instance_test = self._instance_json(actor_id="act-pm-art-list-published", role="test")
        created_proof = self._dispatch(
            instance_json=instance_test,
            actor_id="act-pm-art-list-published",
            role="test",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-proof-r1",
                "title": "Proof v1",
                "summary": "proof",
                "template": "proof",
                "body": "proof body",
            },
        )
        self.assertTrue(created_proof.get("ok"), msg=created_proof)
        published_proof = self._dispatch(
            instance_json=instance_test,
            actor_id="act-pm-art-list-published",
            role="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-art-list-published",
                "artifact_id": "art-list-proof-r1",
                "label": "Close proof",
                "summary": "proof",
            },
        )
        self.assertTrue(published_proof.get("ok"), msg=published_proof)

        instance_pm = self._instance_json(actor_id="act-pm-art-list-published", role="pm")
        created_r2 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-brief-r2",
                "title": "Brief v2",
                "summary": "v2",
                "template": "brief",
                "body": "v2 body",
                "supersedes_artifact_id": "art-list-brief-r1",
            },
        )
        self.assertTrue(created_r2.get("ok"), msg=created_r2)
        published_r2 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-list-published",
                "artifact_id": "art-list-brief-r2",
                "label": "Brief",
                "summary": "v2",
            },
        )
        self.assertTrue(published_r2.get("ok"), msg=published_r2)

        listed = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-published"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        rows = listed.get("artifacts")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        rows_by_id = {
            str(row.get("artifact_id")): row
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-list-brief-r1", rows_by_id)
        self.assertIn("art-list-brief-r2", rows_by_id)
        self.assertIn("art-list-proof-r1", rows_by_id)
        self.assertEqual(rows_by_id["art-list-brief-r2"].get("relation"), "track_material")
        self.assertEqual(rows_by_id["art-list-brief-r2"].get("currentness"), "current")
        self.assertEqual(rows_by_id["art-list-proof-r1"].get("relation"), "track_proof")
        self.assertEqual(rows_by_id["art-list-proof-r1"].get("currentness"), "proof")
        self.assertEqual(rows_by_id["art-list-brief-r1"].get("relation"), "track_history")
        self.assertEqual(rows_by_id["art-list-brief-r1"].get("currentness"), "superseded")
        for row in rows:
            if isinstance(row, dict):
                self.assertNotIn("body", row, msg=row)

    def test_list_filters_are_simple_and_title_summary_only(self) -> None:
        shared_actor_id = "act-art-list-filter"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                track_id="track-art-list-filter",
            ).get("ok")
        )

        created_pm_brief = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-alpha-brief",
                "title": "Alpha Brief",
                "summary": "Signup flow",
                "template": "brief",
                "body": "brief body",
            },
        )
        self.assertTrue(created_pm_brief.get("ok"), msg=created_pm_brief)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                role="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-list-filter",
                    "artifact_id": "art-alpha-brief",
                    "label": "Brief",
                    "summary": "Signup flow",
                },
            ).get("ok")
        )

        instance_design = self._instance_json(actor_id=shared_actor_id, role="design")
        created_design = self._dispatch(
            instance_json=instance_design,
            actor_id=shared_actor_id,
            role="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-alpha-design",
                "title": "Alpha Design",
                "summary": "Visual state",
                "template": "design",
                "body": "design body",
            },
        )
        self.assertTrue(created_design.get("ok"), msg=created_design)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_design,
                actor_id=shared_actor_id,
                role="design",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-list-filter",
                    "artifact_id": "art-alpha-design",
                    "label": "Design",
                    "summary": "Visual state",
                },
            ).get("ok")
        )

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        instance_test = self._instance_json(actor_id=shared_actor_id, role="test")
        created_body_only = self._dispatch(
            instance_json=instance_test,
            actor_id=shared_actor_id,
            role="test",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-beta-proof",
                "title": "Beta Proof",
                "summary": "Release evidence",
                "template": "proof",
                "body": "Contains SIGNUP keyword only in body.",
            },
        )
        self.assertTrue(created_body_only.get("ok"), msg=created_body_only)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_test,
                actor_id=shared_actor_id,
                role="test",
                tool="track",
                action="add_proof",
                args={
                    "track_id": "track-art-list-filter",
                    "artifact_id": "art-beta-proof",
                    "label": "Proof",
                    "summary": "Release evidence",
                },
            ).get("ok")
        )

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        created_draft = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-filter-draft",
                "title": "Draft Only",
                "summary": "still draft",
                "template": "note",
                "body": "draft body",
            },
        )
        self.assertTrue(created_draft.get("ok"), msg=created_draft)

        q_signup = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={"q": "signup"},
        )
        self.assertTrue(q_signup.get("ok"), msg=q_signup)
        q_ids = {
            str(row.get("artifact_id"))
            for row in (q_signup.get("artifacts") or [])
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-alpha-brief", q_ids)
        self.assertNotIn("art-beta-proof", q_ids)

        created_by_design = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={"created_by_identity_id": self._runtime_actor_id(role="design", label=shared_actor_id)},
        )
        self.assertTrue(created_by_design.get("ok"), msg=created_by_design)
        created_by_design_ids = {
            str(row.get("artifact_id"))
            for row in (created_by_design.get("artifacts") or [])
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertEqual(created_by_design_ids, {"art-alpha-design"})
        for row in created_by_design.get("artifacts", []):
            if isinstance(row, dict):
                self.assertNotIn("from_role", row, msg=row)
                self.assertEqual(row.get("created_by_identity_id"), self._runtime_actor_id(role="design", label=shared_actor_id), msg=row)

        template_brief = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={"template": "brief"},
        )
        self.assertTrue(template_brief.get("ok"), msg=template_brief)
        for row in template_brief.get("artifacts", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("template"), "brief", msg=row)

        limited = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={"limit": 1},
        )
        self.assertTrue(limited.get("ok"), msg=limited)
        limited_rows = limited.get("artifacts")
        self.assertIsInstance(limited_rows, list, msg=limited)
        assert isinstance(limited_rows, list)
        self.assertEqual(len(limited_rows), 1, msg=limited_rows)

        track_scoped = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-filter"},
        )
        self.assertTrue(track_scoped.get("ok"), msg=track_scoped)
        for row in track_scoped.get("artifacts", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("track_id"), "track-art-list-filter", msg=row)
                self.assertNotIn("published_to_track", row, msg=row)

        default_limit = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={},
        )
        self.assertTrue(default_limit.get("ok"), msg=default_limit)
        default_rows = default_limit.get("artifacts")
        self.assertIsInstance(default_rows, list, msg=default_limit)
        assert isinstance(default_rows, list)
        self.assertLessEqual(len(default_rows), 20)

    def test_list_rejects_invalid_filters_without_state_change(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art-list-invalid", role="pm")
        cases = [
            {"unsupported": "x"},
            {"template": "prd"},
            {"status": "live"},
            {"created_by": "unknown"},
            {"q": 123},
            {"limit": 0},
            {"limit": "1"},
            {"track_id": "   "},
            {"track_id": "track-missing"},
        ]
        for args in cases:
            result = self._dispatch(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-invalid",
                role="pm",
                tool="artifact",
                action="list",
                args=args,
            )
            with self.subTest(args=args):
                self.assertFalse(result.get("ok"), msg=result)
                self.assertEqual(result.get("state_changed"), False, msg=result)
                self.assertEqual(result.get("durability"), "none", msg=result)
                self.assertIsInstance(result.get("permission_boundary"), str, msg=result)
                self.assertTrue(str(result.get("permission_boundary")).strip(), msg=result)
                self.assertIsInstance(result.get("why_blocked"), str, msg=result)
                self.assertTrue(str(result.get("why_blocked")).strip(), msg=result)

    def test_list_hides_archived_track_artifacts_and_rejects_archived_track_filter(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art-list-archived", role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-archived",
                track_id="track-art-list-archived",
            ).get("ok")
        )
        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-archived",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-archived-r1",
                "title": "Archived material",
                "summary": "archive me",
                "template": "brief",
                "body": "archive body",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-archived",
                role="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-list-archived",
                    "artifact_id": "art-list-archived-r1",
                    "label": "Archived",
                    "summary": "archive me",
                },
            ).get("ok")
        )
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-archived",
                role="pm",
                tool="track",
                action="archive",
                args={"track_id": "track-art-list-archived"},
            ).get("ok")
        )

        listed = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-archived",
            role="pm",
            tool="artifact",
            action="list",
            args={},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        listed_ids = {
            str(row.get("artifact_id"))
            for row in (listed.get("artifacts") or [])
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-list-archived-r1", listed_ids)

        track_filtered = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-archived",
            role="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-archived"},
        )
        self.assertFalse(track_filtered.get("ok"), msg=track_filtered)
        self.assertEqual(track_filtered.get("state_changed"), False, msg=track_filtered)
        self.assertEqual(track_filtered.get("durability"), "none", msg=track_filtered)

