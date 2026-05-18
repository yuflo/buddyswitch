#!/usr/bin/env python3
"""Runless end-to-end env layer coverage for track/artifact publication path."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_store  # noqa: E402
from env.tools import router as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class EnvLayerEndToEndTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_payload = {
            "instance_id": "inst-e2e-runless",
            "buddy": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9333,
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-e2e-runless",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def _create_track(self, track_id: str) -> dict[str, object]:
        return self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": track_id,
                "outcome": "flow",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )

    def _create_draft(
        self,
        *,
        buddy: str,
        artifact_id: str,
        template: str,
        body: str,
        summary: str,
        supersedes_artifact_id: str | None = None,
    ) -> dict[str, object]:
        args: dict[str, object] = {
            "artifact_id": artifact_id,
            "title": artifact_id,
            "summary": summary,
            "template": template,
            "body": body,
        }
        if supersedes_artifact_id:
            args["supersedes_artifact_id"] = supersedes_artifact_id
        return self._dispatch(buddy=buddy, tool="artifact", action="create_revision", args=args)

    def test_pm_design_dev_test_track_artifact_publication_flow(self) -> None:
        track_id = "track-e2e-publication-flow"
        created = self._create_track(track_id)
        self.assertTrue(created.get("ok"), msg=created)

        pm_r1 = self._create_draft(
            buddy="pm",
            artifact_id="art-pm-brief-r1",
            template="brief",
            body="# PM Brief v1\n\nScope v1",
            summary="pm brief v1",
        )
        self.assertTrue(pm_r1.get("ok"), msg=pm_r1)
        pm_pub_r1 = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "artifact_id": "art-pm-brief-r1",
                "label": "PM Brief",
                "summary": "v1",
            },
        )
        self.assertTrue(pm_pub_r1.get("ok"), msg=pm_pub_r1)
        self.assertTrue(bool(pm_pub_r1.get("state_changed")), msg=pm_pub_r1)
        self.assertEqual(pm_pub_r1.get("durability"), "durable")

        pm_r2 = self._create_draft(
            buddy="pm",
            artifact_id="art-pm-brief-r2",
            template="brief",
            body="# PM Brief v2\n\nScope v2",
            summary="pm brief v2",
            supersedes_artifact_id="art-pm-brief-r1",
        )
        self.assertTrue(pm_r2.get("ok"), msg=pm_r2)
        pm_pub_r2 = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "artifact_id": "art-pm-brief-r2",
                "label": "PM Brief",
                "summary": "v2",
            },
        )
        self.assertTrue(pm_pub_r2.get("ok"), msg=pm_pub_r2)

        design_open = self._dispatch(buddy="design", tool="track", action="open", args={"track_id": track_id})
        self.assertTrue(design_open.get("ok"), msg=design_open)
        current_material_ids = [row.get("artifact_id") for row in (design_open.get("track") or {}).get("shared_materials", [])]
        self.assertEqual(current_material_ids, ["art-pm-brief-r2"])

        design_read_pm = self._dispatch(
            buddy="design",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-brief-r2"},
        )
        self.assertTrue(design_read_pm.get("ok"), msg=design_read_pm)
        self.assertIn("Scope v2", (design_read_pm.get("artifact") or {}).get("body", ""))

        design_draft = self._create_draft(
            buddy="design",
            artifact_id="art-design-r1",
            template="design",
            body="# Design Draft\n\nWireframe spec",
            summary="design",
        )
        self.assertTrue(design_draft.get("ok"), msg=design_draft)
        design_pub = self._dispatch(
            buddy="design",
            tool="track",
            action="add_material",
            args={"track_id": track_id, "artifact_id": "art-design-r1", "label": "Design", "summary": "handoff"},
        )
        self.assertTrue(design_pub.get("ok"), msg=design_pub)

        dev_open = self._dispatch(buddy="dev", tool="track", action="open", args={"track_id": track_id})
        self.assertTrue(dev_open.get("ok"), msg=dev_open)
        current_material_ids = [row.get("artifact_id") for row in (dev_open.get("track") or {}).get("shared_materials", [])]
        self.assertEqual(current_material_ids, ["art-pm-brief-r2", "art-design-r1"])
        dev_read_pm = self._dispatch(buddy="dev", tool="artifact", action="get", args={"artifact_id": "art-pm-brief-r2"})
        dev_read_design = self._dispatch(buddy="dev", tool="artifact", action="get", args={"artifact_id": "art-design-r1"})
        self.assertTrue(dev_read_pm.get("ok"), msg=dev_read_pm)
        self.assertTrue(dev_read_design.get("ok"), msg=dev_read_design)

        dev_draft = self._create_draft(
            buddy="dev",
            artifact_id="art-dev-r1",
            template="proposal",
            body="# Implementation Plan\n\nStep list",
            summary="dev plan",
        )
        self.assertTrue(dev_draft.get("ok"), msg=dev_draft)
        dev_pub = self._dispatch(
            buddy="dev",
            tool="track",
            action="add_material",
            args={"track_id": track_id, "artifact_id": "art-dev-r1", "label": "Implementation", "summary": "plan"},
        )
        self.assertTrue(dev_pub.get("ok"), msg=dev_pub)

        test_open = self._dispatch(buddy="test", tool="track", action="open", args={"track_id": track_id})
        self.assertTrue(test_open.get("ok"), msg=test_open)
        material_ids = [row.get("artifact_id") for row in (test_open.get("track") or {}).get("shared_materials", [])]
        self.assertEqual(material_ids, ["art-pm-brief-r2", "art-design-r1", "art-dev-r1"])

        test_proof_draft = self._create_draft(
            buddy="test",
            artifact_id="art-test-proof-r1",
            template="proof",
            body="# Test Proof\n\nSmoke passed",
            summary="proof",
        )
        self.assertTrue(test_proof_draft.get("ok"), msg=test_proof_draft)
        test_proof_pub = self._dispatch(
            buddy="test",
            tool="track",
            action="add_proof",
            args={"track_id": track_id, "artifact_id": "art-test-proof-r1", "label": "Smoke", "summary": "pass"},
        )
        self.assertTrue(test_proof_pub.get("ok"), msg=test_proof_pub)
        proof_changes = {row.get("change") for row in test_proof_pub.get("state_changes", []) if isinstance(row, dict)}
        self.assertIn("published_proof", proof_changes)
        self.assertIn("proof_added", proof_changes)
        self.assertIn("update_added", proof_changes)

        pm_open = self._dispatch(buddy="pm", tool="track", action="open", args={"track_id": track_id})
        self.assertTrue(pm_open.get("ok"), msg=pm_open)
        track_page = pm_open.get("track")
        self.assertIsInstance(track_page, dict, msg=pm_open)
        assert isinstance(track_page, dict)
        self.assertEqual([row.get("artifact_id") for row in track_page.get("shared_materials", [])], ["art-pm-brief-r2", "art-design-r1", "art-dev-r1"])
        self.assertEqual([row.get("artifact_id") for row in track_page.get("close_proof", [])], ["art-test-proof-r1"])

        pm_update = self._dispatch(
            buddy="pm",
            tool="track",
            action="update_now",
            args={"track_id": track_id, "state": "done", "health": "ok", "now": {"next": "ship", "blocker": None}},
        )
        self.assertTrue(pm_update.get("ok"), msg=pm_update)

        persisted_track = env_store.get_track(track_id)
        self.assertIsInstance(persisted_track, dict)
        assert isinstance(persisted_track, dict)
        persisted_rows = [row for row in persisted_track.get("shared_materials", []) if isinstance(row, dict)]
        self.assertEqual(len(persisted_rows), 4)
        current_map = {str(row.get("artifact_id")): bool(row.get("current")) for row in persisted_rows}
        self.assertFalse(current_map["art-pm-brief-r1"])
        self.assertTrue(current_map["art-pm-brief-r2"])

        for artifact_id in ("art-pm-brief-r1", "art-pm-brief-r2", "art-design-r1", "art-dev-r1", "art-test-proof-r1"):
            read = self._dispatch(buddy="dev", tool="artifact", action="get", args={"artifact_id": artifact_id})
            self.assertTrue(read.get("ok"), msg=read)
            self.assertIsInstance((read.get("artifact") or {}).get("body"), str, msg=read)

    def test_cross_buddy_identity_scope_follows_service_permissions(self) -> None:
        env_store.create_artifact_revision(
            artifact_id="art-pm-private-r1",
            title="Private artifact",
            summary="private",
            body="private",
            template="note",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        denied = self._dispatch(
            buddy="design",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-private-r1", "summary": "mutate"},
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["permission_boundary"], "artifact.buddy_scope")
        self.assertEqual((denied.get("error") or {}).get("code"), "E_ARTIFACT_SCOPE")

    def test_response_planes_distinguish_product_private_token_and_browser_session(self) -> None:
        track = self._create_track("track-e2e-planes")
        self.assertTrue(track["ok"], msg=track)
        artifact = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-e2e-planes-r1",
                "title": "Planes spec",
                "summary": "seed",
                "template": "note",
                "body": "seed",
            },
        )
        self.assertTrue(artifact["ok"], msg=artifact)
        self.assertEqual(artifact.get("durability"), "durable")
        self.assertTrue(bool(artifact.get("state_changed")), msg=artifact)

        reject_direct_publish = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-e2e-planes-r2",
                "title": "Invalid publish",
                "summary": "invalid",
                "template": "note",
                "body": "x",
                "published_to_track": "track-e2e-planes",
            },
        )
        self.assertFalse(reject_direct_publish.get("ok"), msg=reject_direct_publish)
        self.assertEqual(reject_direct_publish.get("durability"), "none")
        self.assertFalse(bool(reject_direct_publish.get("state_changed")), msg=reject_direct_publish)

        buddybox_write = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "planes/private.txt", "content": "private"},
        )
        self.assertTrue(buddybox_write["ok"], msg=buddybox_write)
        self.assertEqual(buddybox_write.get("durability"), "active_instance_local")
        self.assertFalse(buddybox_write.get("mutates_product_state"), msg=buddybox_write)

        published = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-e2e-planes", "artifact_id": "art-e2e-planes-r1", "label": "Note", "summary": "planes"},
        )
        self.assertTrue(published.get("ok"), msg=published)

        evidence = self._dispatch(
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": "art-e2e-planes-r1"},
        )
        self.assertTrue(evidence["ok"], msg=evidence)
        self.assertEqual(evidence.get("durability"), "transient token")
        self.assertFalse(evidence.get("mutates_product_state"), msg=evidence)


if __name__ == "__main__":
    unittest.main()
