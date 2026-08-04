"""Runless decision-surface coverage for product mode host flows."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.runtime_support import env_manifest  # noqa: E402
from buddyswitch.env.repos import runtime_files
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track.private.state import track_comments as track_comment_repo
from buddyswitch.modules.track.private.state import tracks as track_repo
from tests.support import object_builders
from tests.support import task_fixtures  # noqa: E402
from buddyswitch.foundation.tool_runtime import registry as tool_router  # noqa: E402
from tests.support.runtime import RuntimeTestWorkspace  # noqa: E402


class HostDecisionSurfaceProductModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = RuntimeTestWorkspace()
        self.addCleanup(self.workspace.close)
        self.runtime_root = self.workspace.root
        self.manifest_path = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.actor_id = self.workspace.actor_id(role="market", label="act-market-decision-surface")
        self.instance_root = self.workspace.path(f"instances/{self.actor_id}")
        self.instance_json = self.instance_root / "instance.json"
        self.instance_payload = {
            "actor_id": self.actor_id,
            "role": "market",
            "status": "active",
            "instance_root": str(self.instance_root),
            "workspace_dir": str(self.instance_root / "workspace"),
            "browser_port": 9555,
        }
        (self.instance_root / "workspace").mkdir(parents=True, exist_ok=True)
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _seed_task_sys_task(self, *, role: str, track_id: str | None = None) -> str:
        actor_id = self.actor_id if role == self.instance_payload.get("role") else self.workspace.actor_id(
            role=role,
            label=f"act-{role}-decision-surface",
        )
        detail = "Exercise the host decision surface."
        if track_id is not None:
            detail += f" Track context: {track_id}."
        result = task_fixtures.create_task(
            actor_target={"actor_id": actor_id, "role_id": role},
            demand_ref={
                "demand_id": f"demand-decision-surface-{role}-{track_id or 'none'}",
                "basis_revision": 1,
                "demand_ref": f"dref-decision-surface-{role}-{track_id or 'none'}",
            },
            objective=detail,
            selection_reason="The host-decision fixture Demand is selected.",
        )
        return str(result["task_id"])

    def _dispatch(self, *, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self.workspace.actor_id(role=role, label="act-market-decision-surface")
        if not task_fixtures.list_task_records(
            actor_target={"actor_id": actor_id, "role_id": role},
            statuses=task_fixtures.ACTIVE_TASK_STATUSES,
        ):
            self.workspace.seed_active_task(
                instance_json=self.instance_json,
                role=role,
                actor_id=actor_id,
                task_slug=f"{role}-decision-surface",
            )
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "actor_id": actor_id, "role": role},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_context_summarize_projects_runless_decision_surface(self) -> None:
        track = object_builders.create_track(
            "track-market-decision",
            "Market Decision",
            owner_actor={"actor_id": "act-pm-decision", "role_id": "pm"},
            outcome="Ship market decision with clear positioning.",
            now={"next": "Scan market", "blocker": None},
        )
        decision_task_id = self._seed_task_sys_task(role="market", track_id=str(track["id"]))
        response = self._dispatch(role="market", tool="context", action="summarize", args={})
        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["decision_surface"]["binding_state"]["state"], "runless")
        self.assertNotIn("has_memories", response["decision_surface"]["context_readiness"])
        self.assertNotIn("memory_summaries", response)
        self.assertIn("candidate_tracks", response)
        self.assertTrue(any(row.get("track_id") == "track-market-decision" for row in response["candidate_tracks"]))
        removed_candidate_section = "candidate_" + "requests"
        self.assertNotIn(removed_candidate_section, response)
        self.assertIn("candidate_tasks", response)
        self.assertTrue(any(row.get("task_id") == decision_task_id for row in response["candidate_tasks"]))
        self.assertNotIn("requests", response.get("current_context_summary") or {})
        affordances = response.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=response)
        assert isinstance(affordances, dict)
        self.assertTrue({"task_sys", "track", "artifact", "context", "evidence", "search", "message"}.issubset(set(affordances)))
        self.assertNotIn("request", affordances)
        self.assertNotIn("private", affordances)
        self.assertNotIn("handoff", affordances)
        self.assertNotIn("project_source", affordances)
        writable_surfaces = response.get("writable_surfaces")
        self.assertIsInstance(writable_surfaces, dict, msg=response)
        assert isinstance(writable_surfaces, dict)
        persistent = writable_surfaces.get("persistent_files")
        self.assertIsInstance(persistent, dict, msg=writable_surfaces)
        assert isinstance(persistent, dict)
        self.assertEqual(persistent.get("env"), "BUDDYSWITCH_ACTOR_PRIVATE_DIR")
        self.assertEqual(persistent.get("workspace_relative_root"), "private")

    def test_context_summarize_includes_compact_artifacts_comments_and_updates(self) -> None:
        track = object_builders.create_track(
            "track-context-entry-surface",
            "Entry Surface",
            owner_actor={"actor_id": "act-pm-entry", "role_id": "pm"},
            outcome="Validate compact entry surface.",
            now={"next": "Seed artifacts", "blocker": None},
        )
        artifact = object_builders.create_artifact_revision(
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
        object_builders.publish_track_material(
            track_id=str(track["id"]),
            artifact_id=str(artifact["id"]),
            label="Entry",
            from_role="pm",
            summary="Entry summary",
        )
        proof = object_builders.create_artifact_revision(
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
        object_builders.publish_track_proof(
            track_id=str(track["id"]),
            artifact_id=str(proof["id"]),
            label="Proof",
            from_role="pm",
            summary="Proof summary",
        )
        added_comment = self._dispatch(
            role="pm",
            tool="track",
            action="add_comment",
            args={
                "track_id": str(track["id"]),
                "content": "Open discussion",
            },
        )
        self.assertTrue(added_comment.get("ok"), msg=added_comment)
        added_update = self._dispatch(
            role="pm",
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

        summary = self._dispatch(role="market", tool="context", action="summarize", args={})
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertIn("candidate_artifacts", summary)
        removed_candidate_section = "candidate_" + "requests"
        self.assertNotIn(removed_candidate_section, summary)
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
        self.assertTrue(any(isinstance(row, dict) and row.get("track_id") == "track-context-entry-surface" for row in open_threads))
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
        for tool_id in ("artifact", "track", "context"):
            self.assertIn(tool_id, affordances)
        self.assertNotIn("request", affordances)

    def test_context_summarize_track_filter_narrows_artifacts_comments_and_updates(self) -> None:
        track_a = object_builders.create_track(
            "track-context-filter-a",
            "Filter A",
            owner_actor={"actor_id": "act-pm-filter", "role_id": "pm"},
            outcome="A",
            now={"next": "A", "blocker": None},
        )
        track_b = object_builders.create_track(
            "track-context-filter-b",
            "Filter B",
            owner_actor={"actor_id": "act-pm-filter", "role_id": "pm"},
            outcome="B",
            now={"next": "B", "blocker": None},
        )
        art_a = object_builders.create_artifact_revision(
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
        art_b = object_builders.create_artifact_revision(
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
        object_builders.publish_track_material(
            track_id=str(track_a["id"]),
            artifact_id=str(art_a["id"]),
            label="A",
            from_role="pm",
            summary="A",
        )
        object_builders.publish_track_material(
            track_id=str(track_b["id"]),
            artifact_id=str(art_b["id"]),
            label="B",
            from_role="pm",
            summary="B",
        )
        comment_a = self._dispatch(
            role="pm",
            tool="track",
            action="add_comment",
            args={
                "track_id": str(track_a["id"]),
                "content": "A comment",
            },
        )
        self.assertTrue(comment_a.get("ok"), msg=comment_a)
        comment_b = self._dispatch(
            role="pm",
            tool="track",
            action="add_comment",
            args={
                "track_id": str(track_b["id"]),
                "content": "B comment",
            },
        )
        self.assertTrue(comment_b.get("ok"), msg=comment_b)
        update_a = self._dispatch(
            role="pm",
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
            role="pm",
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
            role="market",
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
                self.assertEqual(row.get("track_id"), "track-context-filter-a", msg=row)
                self.assertIn("track-context-filter-a", row.get("track_ids", []), msg=row)
        removed_candidate_section = "candidate_" + "requests"
        self.assertNotIn(removed_candidate_section, filtered)
        for row in filtered.get("open_comment_threads", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("track_id"), "track-context-filter-a", msg=row)
        for row in filtered.get("recent_updates", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("track_id"), "track-context-filter-a", msg=row)

        empty = self._dispatch(
            role="market",
            tool="context",
            action="summarize",
            args={"track_id": "track-context-filter-missing"},
        )
        self.assertTrue(empty.get("ok"), msg=empty)
        self.assertEqual(empty.get("candidate_tracks"), [])
        self.assertEqual(empty.get("candidate_artifacts"), [])
        removed_candidate_section = "candidate_" + "requests"
        self.assertNotIn(removed_candidate_section, empty)
        self.assertEqual(empty.get("open_comment_threads"), [])
        self.assertEqual(empty.get("recent_updates"), [])

    def test_market_evidence_requires_target_scoped_args(self) -> None:
        response = self._dispatch(role="market", tool="evidence", action="issue_browser", args={"reason": "no target"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["permission_boundary"], "request-payload")
        self.assertIn("unsupported payload fields", response["why_blocked"].lower())

    def test_non_owner_track_status_rejected_by_owner_boundary(self) -> None:
        created = self._dispatch(
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-design-unauthorized",
                "title": "No",
                "outcome": "Denied",
                "now": {"next": "Denied", "blocker": None},
            },
        )
        self.assertTrue(created["ok"], msg=created)
        response = self._dispatch(
            role="design",
            tool="track",
            action="update_status",
            args={
                "track_id": "track-design-unauthorized",
                "state": "blocked",
                "now": {"next": "Denied", "blocker": "owner required"},
            },
        )
        self.assertFalse(response["ok"])
        self.assertEqual((response.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")
        self.assertEqual(response["permission_boundary"], "track.owner_identity_id")
        self.assertEqual(response.get("active_role"), "design")

    def test_pm_page_prototype_decision_surface_prefers_direct_private_actor_private_directory_without_phrase_rule(self) -> None:
        pm_agents = (ROOT / "src" / "buddyswitch" / "launcher" / "assets" / "roles" / "pm" / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("project.access=", pm_agents)
        self.assertNotIn("projects/app", pm_agents)
        self.assertIn("Start with the native BuddySwitch env context summary tool", pm_agents)
        self.assertIn("context.get.tool_catalog", pm_agents)
        self.assertNotIn("scripts/env/client.py", pm_agents)

        summary = self._dispatch(role="pm", tool="context", action="summarize", args={})
        self.assertTrue(summary["ok"], msg=summary)
        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        artifact = affordances.get("artifact")
        task = affordances.get("task_sys")
        track = affordances.get("track")
        context_tool = affordances.get("context")
        evidence = affordances.get("evidence")
        search = affordances.get("search")
        self.assertIsInstance(artifact, dict, msg=summary)
        self.assertIsInstance(task, dict, msg=summary)
        self.assertIsInstance(track, dict, msg=summary)
        self.assertIsInstance(context_tool, dict, msg=summary)
        self.assertIsInstance(evidence, dict, msg=summary)
        self.assertIsInstance(search, dict, msg=summary)
        assert isinstance(artifact, dict)
        assert isinstance(task, dict)
        assert isinstance(track, dict)
        assert isinstance(context_tool, dict)
        assert isinstance(evidence, dict)
        assert isinstance(search, dict)
        self.assertNotIn("private", affordances)
        writable_surfaces = summary.get("writable_surfaces")
        self.assertIsInstance(writable_surfaces, dict, msg=summary)
        assert isinstance(writable_surfaces, dict)
        persistent = writable_surfaces.get("persistent_files")
        self.assertIsInstance(persistent, dict, msg=writable_surfaces)
        assert isinstance(persistent, dict)
        self.assertEqual(persistent.get("env"), "BUDDYSWITCH_ACTOR_PRIVATE_DIR")
        self.assertEqual(persistent.get("workspace_relative_root"), "private")
        for compact in (artifact, task, track, context_tool, evidence, search):
            for key in ("capability", "when_to_use", "when_not_to_use", "returns", "state_effect"):
                self.assertIn(key, compact, msg=compact)

        context_get = self._dispatch(role="pm", tool="context", action="get", args={})
        self.assertTrue(context_get["ok"], msg=context_get)
        self.assertNotIn("private", context_get["tool_catalog"])
        self.assertNotIn("actor_private.write", context_get["operation_semantics"])
        semantic_payload = json.dumps(
            {"summary": affordances, "writable_surfaces": writable_surfaces},
            ensure_ascii=True,
        ).lower()
        self.assertNotIn("prototype means", semantic_payload)
        self.assertNotIn("quickly build means", semantic_payload)

        product_objects_root = self.workspace.path("buddyswitch/objects")
        before = sorted(path.relative_to(product_objects_root).as_posix() for path in product_objects_root.rglob("*.json"))
        target = self.instance_root / "workspace" / "private" / "prototypes" / "simple-page.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("<!doctype html><html><body><h1>Prototype</h1></body></html>", encoding="utf-8")
        self.assertTrue(target.exists())
        after = sorted(path.relative_to(product_objects_root).as_posix() for path in product_objects_root.rglob("*.json"))
        self.assertEqual(after, before)
