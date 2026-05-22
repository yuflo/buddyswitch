#!/usr/bin/env python3
"""Runless decision-surface coverage for product mode host flows."""

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
import env_legacy_store as env_store  # noqa: E402
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class HostDecisionSurfaceProductModeTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_payload = {
            "instance_id": "inst-market-decision-surface",
            "buddy": "market",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9555,
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-market-decision-surface",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_context_summarize_projects_runless_decision_surface(self) -> None:
        track = env_store.create_track(
            "track-market-decision",
            "Market Decision",
            owner_buddy="pm",
            outcome="Ship market decision with clear positioning.",
            appetite="1 day",
            now={"next": "Scan market", "blocker": None},
        )
        env_store.create_task("task-market-decision", "Scan market", buddy="market", track_id=track["id"])
        request_created = self._dispatch(
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": str(track["id"]),
                "to_buddy": "market",
                "title": "Collect market proof",
                "summary": "Scan competitors and report signal quality.",
                "target_refs": [{"type": "track", "id": str(track["id"])}],
            },
        )
        self.assertTrue(request_created["ok"], msg=request_created)

        response = self._dispatch(buddy="market", tool="context", action="summarize", args={})
        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["decision_surface"]["binding_state"]["state"], "runless")
        self.assertNotIn("has_memories", response["decision_surface"]["context_readiness"])
        self.assertNotIn("memory_summaries", response)
        self.assertIn("candidate_tracks", response)
        self.assertTrue(any(row.get("track_id") == "track-market-decision" for row in response["candidate_tracks"]))
        self.assertIn("candidate_requests", response)
        self.assertTrue(any(row.get("track_id") == "track-market-decision" for row in response["candidate_requests"]))
        self.assertGreaterEqual(int((response.get("current_context_summary") or {}).get("requests", 0)), 1)
        affordances = response.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=response)
        assert isinstance(affordances, dict)
        self.assertTrue({"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment", "request"}.issubset(set(affordances)))
        self.assertNotIn("handoff", affordances)
        self.assertNotIn("project_source", affordances)

    def test_context_summarize_includes_compact_artifacts_comments_and_updates(self) -> None:
        track = env_store.create_track(
            "track-context-entry-surface",
            "Entry Surface",
            owner_buddy="pm",
            outcome="Validate compact entry surface.",
            appetite="1 day",
            now={"next": "Seed artifacts", "blocker": None},
        )
        artifact = env_store.create_artifact_revision(
            artifact_id="art-context-entry-r1",
            title="Entry Artifact",
            summary="Entry summary",
            body="Entry body",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=str(track["id"]),
            artifact_id=str(artifact["id"]),
            label="Entry",
            from_buddy="pm",
            summary="Entry summary",
        )
        proof = env_store.create_artifact_revision(
            artifact_id="art-context-proof-r1",
            title="Entry Proof",
            summary="Proof summary",
            body="Proof body",
            template="proof",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "proof-seed"}],
        )
        env_store.publish_track_proof(
            track_id=str(track["id"]),
            artifact_id=str(proof["id"]),
            label="Proof",
            from_buddy="pm",
            summary="Proof summary",
        )
        created_request = self._dispatch(
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": str(track["id"]),
                "to_buddy": "market",
                "title": "Validate entry surface",
                "summary": "Check entry artifacts and updates.",
                "target_refs": [{"type": "artifact", "id": str(artifact["id"])}],
            },
        )
        self.assertTrue(created_request.get("ok"), msg=created_request)
        added_comment = self._dispatch(
            buddy="pm",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact",
                "target_id": str(artifact["id"]),
                "content": "Open discussion",
            },
        )
        self.assertTrue(added_comment.get("ok"), msg=added_comment)
        added_update = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": str(track["id"]),
                "kind": "progress",
                "summary": "Entry progress",
                "refs": [{"type": "artifact", "id": str(artifact["id"])}],
            },
        )
        self.assertTrue(added_update.get("ok"), msg=added_update)

        summary = self._dispatch(buddy="market", tool="context", action="summarize", args={})
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertIn("candidate_artifacts", summary)
        self.assertIn("candidate_requests", summary)
        self.assertIn("open_comment_threads", summary)
        self.assertIn("recent_updates", summary)
        candidate_artifacts = summary.get("candidate_artifacts")
        self.assertIsInstance(candidate_artifacts, list, msg=summary)
        assert isinstance(candidate_artifacts, list)
        self.assertTrue(any(isinstance(row, dict) and row.get("artifact_id") == "art-context-entry-r1" for row in candidate_artifacts))
        for row in candidate_artifacts:
            if isinstance(row, dict):
                self.assertNotIn("body", row, msg=row)
        open_threads = summary.get("open_comment_threads")
        self.assertIsInstance(open_threads, list, msg=summary)
        assert isinstance(open_threads, list)
        self.assertTrue(any(isinstance(row, dict) and row.get("target_id") == "art-context-entry-r1" for row in open_threads))
        recent_updates = summary.get("recent_updates")
        self.assertIsInstance(recent_updates, list, msg=summary)
        assert isinstance(recent_updates, list)
        self.assertTrue(any(isinstance(row, dict) and row.get("track_id") == "track-context-entry-surface" for row in recent_updates))
        context_summary = summary.get("current_context_summary")
        self.assertIsInstance(context_summary, dict, msg=summary)
        assert isinstance(context_summary, dict)
        self.assertGreaterEqual(int(context_summary.get("artifacts", 0)), 1)
        self.assertGreaterEqual(int(context_summary.get("open_comment_threads", 0)), 1)
        self.assertGreaterEqual(int(context_summary.get("recent_updates", 0)), 1)
        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        for tool_id in ("artifact", "request", "comment", "track", "context"):
            self.assertIn(tool_id, affordances)

    def test_context_summarize_track_filter_narrows_artifacts_requests_comments_and_updates(self) -> None:
        track_a = env_store.create_track(
            "track-context-filter-a",
            "Filter A",
            owner_buddy="pm",
            outcome="A",
            appetite="1 day",
            now={"next": "A", "blocker": None},
        )
        track_b = env_store.create_track(
            "track-context-filter-b",
            "Filter B",
            owner_buddy="pm",
            outcome="B",
            appetite="1 day",
            now={"next": "B", "blocker": None},
        )
        art_a = env_store.create_artifact_revision(
            artifact_id="art-context-filter-a-r1",
            title="Artifact A",
            summary="A",
            body="A",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "A"}],
        )
        art_b = env_store.create_artifact_revision(
            artifact_id="art-context-filter-b-r1",
            title="Artifact B",
            summary="B",
            body="B",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "B"}],
        )
        env_store.publish_track_material(
            track_id=str(track_a["id"]),
            artifact_id=str(art_a["id"]),
            label="A",
            from_buddy="pm",
            summary="A",
        )
        env_store.publish_track_material(
            track_id=str(track_b["id"]),
            artifact_id=str(art_b["id"]),
            label="B",
            from_buddy="pm",
            summary="B",
        )
        request_a = self._dispatch(
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": str(track_a["id"]),
                "to_buddy": "market",
                "title": "Request A",
                "summary": "A",
                "target_refs": [{"type": "artifact", "id": str(art_a["id"])}],
            },
        )
        self.assertTrue(request_a.get("ok"), msg=request_a)
        request_b = self._dispatch(
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": str(track_b["id"]),
                "to_buddy": "market",
                "title": "Request B",
                "summary": "B",
                "target_refs": [{"type": "artifact", "id": str(art_b["id"])}],
            },
        )
        self.assertTrue(request_b.get("ok"), msg=request_b)
        comment_a = self._dispatch(
            buddy="pm",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact",
                "target_id": str(art_a["id"]),
                "content": "A comment",
            },
        )
        self.assertTrue(comment_a.get("ok"), msg=comment_a)
        comment_b = self._dispatch(
            buddy="pm",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact",
                "target_id": str(art_b["id"]),
                "content": "B comment",
            },
        )
        self.assertTrue(comment_b.get("ok"), msg=comment_b)
        update_a = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": str(track_a["id"]),
                "kind": "progress",
                "summary": "A update",
                "refs": [{"type": "artifact", "id": str(art_a["id"])}],
            },
        )
        self.assertTrue(update_a.get("ok"), msg=update_a)
        update_b = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": str(track_b["id"]),
                "kind": "progress",
                "summary": "B update",
                "refs": [{"type": "artifact", "id": str(art_b["id"])}],
            },
        )
        self.assertTrue(update_b.get("ok"), msg=update_b)

        filtered = self._dispatch(
            buddy="market",
            tool="context",
            action="summarize",
            args={"track_id": "track-context-filter-a"},
        )
        self.assertTrue(filtered.get("ok"), msg=filtered)
        self.assertEqual(
            [row.get("track_id") for row in filtered.get("candidate_tracks", []) if isinstance(row, dict)],
            ["track-context-filter-a"],
        )
        for row in filtered.get("candidate_artifacts", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("published_to_track"), "track-context-filter-a", msg=row)
        for row in filtered.get("candidate_requests", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("track_id"), "track-context-filter-a", msg=row)
        for row in filtered.get("open_comment_threads", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("target_id"), "art-context-filter-a-r1", msg=row)
        for row in filtered.get("recent_updates", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("track_id"), "track-context-filter-a", msg=row)

        empty = self._dispatch(
            buddy="market",
            tool="context",
            action="summarize",
            args={"track_id": "track-context-filter-missing"},
        )
        self.assertTrue(empty.get("ok"), msg=empty)
        self.assertEqual(empty.get("candidate_tracks"), [])
        self.assertEqual(empty.get("candidate_artifacts"), [])
        self.assertEqual(empty.get("candidate_requests"), [])
        self.assertEqual(empty.get("open_comment_threads"), [])
        self.assertEqual(empty.get("recent_updates"), [])

    def test_market_evidence_requires_target_scoped_args(self) -> None:
        response = self._dispatch(buddy="market", tool="evidence", action="issue_browser", args={"reason": "no target"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["permission_boundary"], "request-payload")
        self.assertIn("unsupported payload fields", response["why_blocked"].lower())

    def test_non_pm_track_write_rejected_by_authority_boundary(self) -> None:
        response = self._dispatch(
            buddy="design",
            tool="track",
            action="create",
            args={
                "track_id": "track-design-unauthorized",
                "title": "No",
                "outcome": "Denied",
                "appetite": "1 day",
                "now": {"next": "Denied", "blocker": None},
            },
        )
        self.assertFalse(response["ok"])
        self.assertEqual((response.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")
        self.assertEqual(response["permission_boundary"], "track.lifecycle_authority")

    def test_pm_page_prototype_decision_surface_prefers_private_buddybox_without_phrase_rule(self) -> None:
        pm_agents = (ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("project.access=", pm_agents)
        self.assertNotIn("projects/app", pm_agents)
        self.assertIn("context summarize --payload '{}'", pm_agents)

        summary = self._dispatch(buddy="pm", tool="context", action="summarize", args={})
        self.assertTrue(summary["ok"], msg=summary)
        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        buddybox = affordances.get("buddybox")
        artifact = affordances.get("artifact")
        task = affordances.get("task")
        track = affordances.get("track")
        context_tool = affordances.get("context")
        evidence = affordances.get("evidence")
        search = affordances.get("search")
        self.assertIsInstance(buddybox, dict, msg=summary)
        self.assertIsInstance(artifact, dict, msg=summary)
        self.assertIsInstance(task, dict, msg=summary)
        self.assertIsInstance(track, dict, msg=summary)
        self.assertIsInstance(context_tool, dict, msg=summary)
        self.assertIsInstance(evidence, dict, msg=summary)
        self.assertIsInstance(search, dict, msg=summary)
        assert isinstance(buddybox, dict)
        assert isinstance(artifact, dict)
        assert isinstance(task, dict)
        assert isinstance(track, dict)
        assert isinstance(context_tool, dict)
        assert isinstance(evidence, dict)
        assert isinstance(search, dict)
        for compact in (buddybox, artifact, task, track, context_tool, evidence, search):
            for key in ("capability", "when_to_use", "when_not_to_use", "returns", "state_effect"):
                self.assertIn(key, compact, msg=compact)

        context_get = self._dispatch(buddy="pm", tool="context", action="get", args={})
        self.assertTrue(context_get["ok"], msg=context_get)
        buddybox_catalog = context_get["tool_catalog"]["buddybox"]
        write_semantics = buddybox_catalog["action_semantics"]["write"]
        self.assertEqual(write_semantics.get("title"), "buddybox.write")
        self.assertIn("side_effects", write_semantics)
        semantic_payload = json.dumps(
            {"summary": affordances, "buddybox_write": write_semantics},
            ensure_ascii=True,
        ).lower()
        self.assertNotIn("prototype means", semantic_payload)
        self.assertNotIn("quickly build means", semantic_payload)

        written = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={
                "logical_name": "prototypes/simple-page.html",
                "content": "<!doctype html><html><body><h1>Prototype</h1></body></html>",
                "content_type": "text/html",
            },
        )
        self.assertTrue(written["ok"], msg=written)
        self.assertTrue(self._runtime_path("buddyswitch/local/buddybox/pm/prototypes/simple-page.html").exists())
        self.assertFalse(written.get("mutates_product_state"), msg=written)
        self.assertEqual(written.get("mutated_product_objects"), [], msg=written)

        options = written.get("allowed_next_action_options")
        self.assertIsInstance(options, list, msg=written)
        assert isinstance(options, list)
        option_pairs = {
            (row.get("tool"), row.get("action"))
            for row in options
            if isinstance(row, dict)
        }
        self.assertIn(("buddybox", "read"), option_pairs)
        self.assertIn(("buddybox", "list"), option_pairs)
        self.assertIn(("artifact", "create_revision"), option_pairs)
        promotion = next(
            row
            for row in options
            if isinstance(row, dict) and row.get("tool") == "artifact" and row.get("action") == "create_revision"
        )
        self.assertIn("when", str(promotion.get("reason", "")).lower())
        self.assertNotIn("must", str(promotion.get("reason", "")).lower())
        self.assertNotIn("always", str(promotion.get("reason", "")).lower())
        for row in options:
            if not isinstance(row, dict):
                continue
            for key in ("tool", "action", "mutates", "preconditions", "reason", "source_refs"):
                self.assertIn(key, row, msg=row)


if __name__ == "__main__":
    unittest.main()
