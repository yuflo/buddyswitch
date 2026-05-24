#!/usr/bin/env python3
"""Runless end-to-end env layer coverage for track/artifact publication path."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_legacy_store as env_store  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class EnvLayerEndToEndTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_root = self._instance_root("inst-e2e-runless")
        self.instance_json = self.instance_root / "instance.json"
        self.workspace_dir = self.instance_root / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.instance_payload = {
            "instance_id": "inst-e2e-runless",
            "buddy": "pm",
            "status": "active",
            "instance_root": str(self.instance_root),
            "workspace_dir": str(self.workspace_dir),
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

    def _instance_task_snapshot(self) -> dict[str, str]:
        taskbox_root = self._instance_root("inst-e2e-runless") / "taskbox"
        if not taskbox_root.exists():
            return {}
        return {
            path.relative_to(taskbox_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(taskbox_root.rglob("*.json"))
        }

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
            template="note",
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

        context_full = self._dispatch(
            buddy="dev",
            tool="context",
            action="get",
            args={"track_id": track_id, "limit": 5},
        )
        self.assertTrue(context_full.get("ok"), msg=context_full)
        tool_catalog = context_full.get("tool_catalog")
        self.assertIsInstance(tool_catalog, dict, msg=context_full)
        assert isinstance(tool_catalog, dict)
        track_catalog = tool_catalog.get("track")
        self.assertIsInstance(track_catalog, dict, msg=tool_catalog)
        assert isinstance(track_catalog, dict)
        track_ops = track_catalog.get("operations")
        self.assertIsInstance(track_ops, list, msg=track_catalog)
        assert isinstance(track_ops, list)
        self.assertIn("add_material", track_ops)
        artifact_catalog = tool_catalog.get("artifact")
        self.assertIsInstance(artifact_catalog, dict, msg=tool_catalog)
        assert isinstance(artifact_catalog, dict)
        artifact_ops = artifact_catalog.get("operations")
        self.assertIsInstance(artifact_ops, list, msg=artifact_catalog)
        assert isinstance(artifact_ops, list)
        self.assertIn("attach_file", artifact_ops)
        self.assertIn("list_attachments", artifact_ops)
        self.assertIn("get_attachment", artifact_ops)
        op_semantics = context_full.get("operation_semantics")
        self.assertIsInstance(op_semantics, dict, msg=context_full)
        assert isinstance(op_semantics, dict)
        self.assertIn("track.add_material", op_semantics)
        self.assertIn("artifact.get", op_semantics)
        self.assertIn("artifact.attach_file", op_semantics)
        self.assertIn("artifact.list_attachments", op_semantics)
        self.assertIn("artifact.get_attachment", op_semantics)

        for artifact_id in ("art-pm-brief-r1", "art-pm-brief-r2", "art-design-r1", "art-dev-r1", "art-test-proof-r1"):
            read = self._dispatch(buddy="dev", tool="artifact", action="get", args={"artifact_id": artifact_id})
            self.assertTrue(read.get("ok"), msg=read)
            self.assertIsInstance((read.get("artifact") or {}).get("body"), str, msg=read)

    def test_track_open_attachment_discovery_flows_to_exact_attachment_read(self) -> None:
        track_id = "track-e2e-attachments"
        created = self._create_track(track_id)
        self.assertTrue(created.get("ok"), msg=created)

        design_draft = self._create_draft(
            buddy="design",
            artifact_id="art-design-attach-e2e-r1",
            template="design",
            body="# Design",
            summary="design attachment",
        )
        self.assertTrue(design_draft.get("ok"), msg=design_draft)

        source = self.instance_root / "tmp" / "chrome-devtools" / "desktop.png"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"\x89PNG\r\n")
        imported = self._dispatch(
            buddy="design",
            tool="buddybox",
            action="import_file",
            args={
                "logical_name": "screenshots/desktop.png",
                "source_path": str(source),
                "content_type": "image/png",
            },
        )
        self.assertTrue(imported.get("ok"), msg=imported)

        attached = self._dispatch(
            buddy="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-design-attach-e2e-r1",
                "filename": "desktop.png",
                "source_buddybox_logical_name": "screenshots/desktop.png",
                "content_type": "image/png",
            },
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        attachment = attached.get("attachment")
        self.assertIsInstance(attachment, dict, msg=attached)
        assert isinstance(attachment, dict)
        attachment_id = str(attachment.get("attachment_id"))

        published = self._dispatch(
            buddy="design",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "artifact_id": "art-design-attach-e2e-r1",
                "label": "Design",
                "summary": "handoff",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        opened = self._dispatch(buddy="dev", tool="track", action="open", args={"track_id": track_id})
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        shared_materials = track.get("shared_materials")
        self.assertIsInstance(shared_materials, list, msg=track)
        assert isinstance(shared_materials, list)
        self.assertEqual(len(shared_materials), 1)
        material_ref = shared_materials[0]
        self.assertEqual(material_ref.get("attachment_count"), 1)
        ref_attachments = material_ref.get("attachments")
        self.assertIsInstance(ref_attachments, list, msg=material_ref)
        assert isinstance(ref_attachments, list)
        self.assertEqual([row.get("attachment_id") for row in ref_attachments], [attachment_id])
        self.assertNotIn("content_base64", ref_attachments[0])
        self.assertNotIn("path", ref_attachments[0])

        fetched = self._dispatch(
            buddy="dev",
            tool="artifact",
            action="get_attachment",
            args={"artifact_id": "art-design-attach-e2e-r1", "attachment_id": attachment_id},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched.get("content_base64"), "iVBORw0K")

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

    def test_request_lifecycle_and_pm_comment_resolution_flow(self) -> None:
        track_id = "track-e2e-request-flow"
        created = self._create_track(track_id)
        self.assertTrue(created.get("ok"), msg=created)

        pm_scope = self._create_draft(
            buddy="pm",
            artifact_id="art-pm-scope-r1",
            template="brief",
            body="# Scope\n\nApproved baseline",
            summary="pm scope",
        )
        self.assertTrue(pm_scope.get("ok"), msg=pm_scope)
        pm_scope_pub = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "artifact_id": "art-pm-scope-r1",
                "label": "PM Scope",
                "summary": "baseline",
            },
        )
        self.assertTrue(pm_scope_pub.get("ok"), msg=pm_scope_pub)

        before_messages = list(env_store.list_messages())
        before_tasks = self._instance_task_snapshot()

        request_created = self._dispatch(
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": track_id,
                "to_buddy": "dev",
                "title": "Implement approved scope",
                "summary": "Build implementation artifact from PM scope.",
                "target_refs": [{"type": "artifact", "id": "art-pm-scope-r1"}],
            },
        )
        self.assertTrue(request_created.get("ok"), msg=request_created)
        request_id = str((request_created.get("request") or {}).get("id"))
        self.assertTrue(request_id.startswith("req-"))

        dev_inbox = self._dispatch(
            buddy="dev",
            tool="request",
            action="list",
            args={"box": "inbox", "track_id": track_id},
        )
        self.assertTrue(dev_inbox.get("ok"), msg=dev_inbox)
        inbox_ids = [row.get("id") for row in dev_inbox.get("requests", []) if isinstance(row, dict)]
        self.assertIn(request_id, inbox_ids)

        accepted = self._dispatch(
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": request_id},
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual((accepted.get("request") or {}).get("status"), "accepted")

        dev_result = self._create_draft(
            buddy="dev",
            artifact_id="art-dev-req-r1",
            template="note",
            body="# Implementation\n\nDelivered",
            summary="dev implementation",
        )
        self.assertTrue(dev_result.get("ok"), msg=dev_result)
        dev_result_pub = self._dispatch(
            buddy="dev",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "artifact_id": "art-dev-req-r1",
                "label": "Implementation",
                "summary": "done",
            },
        )
        self.assertTrue(dev_result_pub.get("ok"), msg=dev_result_pub)

        completed = self._dispatch(
            buddy="dev",
            tool="request",
            action="complete",
            args={
                "request_id": request_id,
                "result_refs": [{"type": "artifact", "id": "art-dev-req-r1"}],
            },
        )
        self.assertTrue(completed.get("ok"), msg=completed)
        self.assertEqual((completed.get("request") or {}).get("status"), "done")

        test_comment = self._dispatch(
            buddy="test",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact",
                "target_id": "art-dev-req-r1",
                "content": "Need PM closure review.",
            },
        )
        self.assertTrue(test_comment.get("ok"), msg=test_comment)
        comment_id = str((test_comment.get("comment") or {}).get("id"))

        resolved = self._dispatch(
            buddy="pm",
            tool="comment",
            action="resolve",
            args={"comment_id": comment_id, "resolution_summary": "Reviewed and accepted."},
        )
        self.assertTrue(resolved.get("ok"), msg=resolved)
        self.assertIn(comment_id, resolved.get("updated_ids", []))

        resolved_list = self._dispatch(
            buddy="pm",
            tool="comment",
            action="list",
            args={"target_type": "artifact", "target_id": "art-dev-req-r1", "status": "resolved"},
        )
        self.assertTrue(resolved_list.get("ok"), msg=resolved_list)
        self.assertEqual(len(resolved_list.get("comments", [])), 1)
        self.assertEqual((resolved_list.get("comments", [{}])[0]).get("status"), "resolved")

        pm_context = self._dispatch(
            buddy="pm",
            tool="context",
            action="get",
            args={"track_id": track_id, "limit": 10},
        )
        self.assertTrue(pm_context.get("ok"), msg=pm_context)
        request_rows = [row for row in pm_context.get("requests", []) if isinstance(row, dict)]
        request_row = next(row for row in request_rows if row.get("id") == request_id)
        self.assertEqual(request_row.get("status"), "done")

        after_messages = list(env_store.list_messages())
        after_tasks = self._instance_task_snapshot()
        self.assertEqual(before_messages, after_messages)
        self.assertEqual(before_tasks, after_tasks)

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
        self.assertEqual(buddybox_write.get("durability"), "durable")
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
        self.assertEqual(evidence.get("durability"), "transient")
        self.assertFalse(evidence.get("mutates_product_state"), msg=evidence)


class EnvLayerProductRootSplitTests(unittest.TestCase):
    def test_object_writes_use_state_root_when_workspace_and_state_are_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shared_root = Path(temp_dir) / "shared"
            workspace_dir = shared_root / "instances" / "inst-e2e-product" / "workspace"
            state_root = shared_root / "state"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            (workspace_dir / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")

            updates = {
                "BUDDYSWITCH_INSTANCE_ID": "inst-e2e-product",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                "BUDDYSWITCH_WORKSPACE_DIR": str(workspace_dir),
                "BUDDYSWITCH_STATE_ROOT": str(state_root),
            }
            with unittest.mock.patch.dict(os.environ, updates, clear=False):
                try:
                    runtime_files.refresh_runtime_roots_from_env()
                    track_id = "track-e2e-product-state-root"
                    created = env_store.create_track(
                        track_id,
                        "State Root Split",
                        owner_buddy="pm",
                        outcome="verify state split",
                        appetite="1 day",
                        now={"next": "verify", "blocker": None},
                    )
                    self.assertEqual(created.get("id"), track_id)
                    self.assertTrue((state_root / "buddyswitch" / "objects" / "tracks" / f"{track_id}.json").exists())
                    self.assertFalse((workspace_dir / "buddyswitch" / "objects" / "tracks" / f"{track_id}.json").exists())
                finally:
                    runtime_files.refresh_runtime_roots_from_env()


if __name__ == "__main__":
    unittest.main()
