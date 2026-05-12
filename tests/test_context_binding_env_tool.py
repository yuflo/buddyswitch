#!/usr/bin/env python3
"""Functional coverage for broker-routed context, binding, and handoff env tools."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"


class ContextBindingEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
        status: str = "active",
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch(
        self,
        *,
        tool: str,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "instance_id": instance_id,
            "active_buddy": buddy,
            "method": "env.tool",
            "payload": {"tool": tool, "action": action, "args": args},
        }
        return runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _prepare(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        text: str,
    ) -> dict[str, object]:
        prepared = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": "prepare",
                "payload": {"text": text},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertTrue(prepared.get("ok"), msg=prepared)
        payload = prepared.get("payload")
        self.assertIsInstance(payload, dict, msg=prepared)
        assert isinstance(payload, dict)
        return payload

    def _load_instance(self, instance_json: Path) -> dict[str, object]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def _seed_track(
        self,
        *,
        track_id: str,
        title: str,
        status: str = "active",
        current_buddy: str = "pm",
        next_buddy: str | None = None,
        summary: str = "",
    ) -> None:
        env_store.create_track(
            track_id,
            title,
            status=status,
            current_buddy=current_buddy,
            next_buddy=next_buddy,
            summary=summary,
        )

    def _seed_task(
        self,
        *,
        task_id: str,
        buddy: str,
        title: str,
        track_id: str | None = None,
        initial_run_id: str | None = None,
    ) -> None:
        env_store.create_task(
            task_id,
            title,
            buddy=buddy,
            track_id=track_id,
            status="active",
            summary="",
            initial_run_id=initial_run_id,
        )

    def _seed_artifact(
        self,
        *,
        artifact_id: str,
        task_id: str,
        buddy: str,
        kind: str,
        title: str,
        source_run_id: str,
        content: dict[str, object] | None = None,
    ) -> None:
        env_store.create_artifact(
            artifact_id=artifact_id,
            title=title,
            buddy=buddy,
            kind=kind,
            task_id=task_id,
            source_run_id=source_run_id,
            summary=f"{title} summary",
            content=content or {"body": title},
        )

    def _write_handoff_run(
        self,
        *,
        run_id: str,
        task_id: str,
        track_id: str,
        buddy_id: str,
        next_buddy: str,
    ) -> None:
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "track_id": track_id,
                    "buddy_id": buddy_id,
                    "timestamp": "2026-05-11T00:00:00Z",
                    "handoff": {
                        "next_buddy": next_buddy,
                        "reason": "Next buddy should continue from the current artifact.",
                        "context": "Use the current artifact and track summary.",
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _seed_pm_track_with_market_handoff(self) -> tuple[str, str]:
        track_id = "track-pm-handoff-seeded"
        pm_task_id = "task-pm-handoff-seeded"
        self._seed_track(
            track_id=track_id,
            title="PM Handoff Track",
            current_buddy="pm",
            next_buddy="market",
            summary="Seeded PM-to-Market handoff track.",
        )
        self._seed_task(
            task_id=pm_task_id,
            buddy="pm",
            title="PM Seed Task",
            track_id=track_id,
            initial_run_id="run-pm-seeded-r1",
        )
        self._seed_artifact(
            artifact_id="art-pm-seeded-prd-r1",
            task_id=pm_task_id,
            buddy="pm",
            kind="prd",
            title="PM Seed PRD",
            source_run_id="run-pm-seeded-r1",
            content={
                "problem": "Busy teams lose time to scheduling overhead.",
                "requirements": ["Hero value clarity", "Concrete CTA"],
            },
        )
        self._write_handoff_run(
            run_id="run-pm-seeded-handoff-r2",
            task_id=pm_task_id,
            track_id=track_id,
            buddy_id="pm",
            next_buddy="market",
        )
        return track_id, pm_task_id

    def test_binding_get_and_set_task_sync_active_instance_json(self) -> None:
        self._seed_track(track_id="track-dev-example", title="Dev Track", next_buddy="dev")
        self._seed_task(task_id="task-dev-untracked", buddy="dev", title="Dev Untracked")
        self._seed_task(
            task_id="task-dev-tracked",
            buddy="dev",
            title="Dev Tracked",
            track_id="track-dev-example",
        )
        instance_json = self._instance_json()

        initial = self._dispatch(tool="binding", action="get", args={}, instance_json=instance_json)
        self.assertTrue(initial.get("ok"), msg=initial)
        self.assertEqual(initial.get("tool"), "binding")
        self.assertEqual(initial.get("action"), "binding.get")
        binding = initial.get("current_binding")
        self.assertIsInstance(binding, dict, msg=initial)
        assert isinstance(binding, dict)
        self.assertEqual(binding.get("instance_id"), "inst-dev-example")
        self.assertEqual(binding.get("active_buddy"), "dev")
        self.assertIsNone(binding.get("current_task_id"))
        self.assertIsNone(binding.get("current_track_id"))

        untracked = self._dispatch(
            tool="binding",
            action="set_task",
            args={"task_id": "task-dev-untracked"},
            instance_json=instance_json,
        )
        self.assertTrue(untracked.get("ok"), msg=untracked)
        self.assertEqual(untracked.get("action"), "binding.set_task")
        after_untracked = self._load_instance(instance_json)
        self.assertEqual(after_untracked["current_task_id"], "task-dev-untracked")
        self.assertIsNone(after_untracked["current_track_id"])

        tracked = self._dispatch(
            tool="binding",
            action="set_task",
            args={"task_id": "task-dev-tracked"},
            instance_json=instance_json,
        )
        self.assertTrue(tracked.get("ok"), msg=tracked)
        after_tracked = self._load_instance(instance_json)
        self.assertEqual(after_tracked["current_task_id"], "task-dev-tracked")
        self.assertEqual(after_tracked["current_track_id"], "track-dev-example")

    def test_binding_rejections_leave_instance_json_unchanged(self) -> None:
        self._seed_track(track_id="track-shared", title="Shared Track", next_buddy="dev")
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="PM Foreign", track_id="track-shared")
        instance_json = self._instance_json(current_task_id="task-dev-current")
        before = self._load_instance(instance_json)

        foreign_task = self._dispatch(
            tool="binding",
            action="set_task",
            args={"task_id": "task-pm-foreign"},
            instance_json=instance_json,
        )
        self.assertFalse(foreign_task.get("ok"), msg=foreign_task)
        self.assertEqual(foreign_task.get("tool"), "binding")
        self.assertEqual(foreign_task.get("action"), "binding.set_task")
        self.assertEqual(foreign_task.get("permission_boundary"), "task.buddy_scope")
        self.assertEqual(self._load_instance(instance_json), before)

        non_pm_track = self._dispatch(
            tool="binding",
            action="set_track",
            args={"track_id": "track-shared"},
            instance_json=instance_json,
        )
        self.assertFalse(non_pm_track.get("ok"), msg=non_pm_track)
        self.assertEqual(non_pm_track.get("action"), "binding.set_track")
        self.assertEqual(non_pm_track.get("permission_boundary"), "track.lifecycle_authority")
        self.assertEqual(self._load_instance(instance_json), before)

    def test_pm_can_set_track_binding_and_clear_active_instance_binding(self) -> None:
        self._seed_track(track_id="track-pm-owned", title="PM Owned", current_buddy="pm", next_buddy="dev")
        instance_json = self._instance_json(instance_id="inst-pm-example", buddy="pm")

        set_track = self._dispatch(
            tool="binding",
            action="set_track",
            args={"track_id": "track-pm-owned"},
            instance_json=instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertTrue(set_track.get("ok"), msg=set_track)
        after_set = self._load_instance(instance_json)
        self.assertIsNone(after_set["current_task_id"])
        self.assertEqual(after_set["current_track_id"], "track-pm-owned")

        cleared = self._dispatch(
            tool="binding",
            action="clear",
            args={},
            instance_json=instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertTrue(cleared.get("ok"), msg=cleared)
        after_clear = self._load_instance(instance_json)
        self.assertIsNone(after_clear["current_task_id"])
        self.assertIsNone(after_clear["current_track_id"])

    def test_context_tools_return_current_context_without_raw_global_state(self) -> None:
        self._seed_track(
            track_id="track-dev-context",
            title="Dev Context Track",
            current_buddy="pm",
            next_buddy="dev",
            summary="Cross-buddy delivery context.",
        )
        self._seed_task(
            task_id="task-dev-context",
            buddy="dev",
            title="Dev Context",
            track_id="track-dev-context",
        )
        self._seed_artifact(
            artifact_id="art-dev-context-report-r1",
            task_id="task-dev-context",
            buddy="dev",
            kind="implementation-report",
            title="Implementation Report",
            source_run_id="run-dev-context-r1",
            content={"details": "full implementation details"},
        )
        self._write_handoff_run(
            run_id="run-pm-handoff",
            task_id="task-dev-context",
            track_id="track-dev-context",
            buddy_id="pm",
            next_buddy="dev",
        )
        instance_json = self._instance_json(
            current_task_id="task-dev-context",
            current_track_id="track-dev-context",
        )

        context = self._dispatch(tool="context", action="get", args={}, instance_json=instance_json)
        self.assertTrue(context.get("ok"), msg=context)
        self.assertEqual(context.get("tool"), "context")
        self.assertEqual(context.get("action"), "context.get")
        task_context = context.get("task_context")
        self.assertIsInstance(task_context, dict, msg=context)
        assert isinstance(task_context, dict)
        artifacts = task_context.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=context)
        assert isinstance(artifacts, list)
        self.assertEqual(artifacts[0]["content"], {"details": "full implementation details"})
        track_context = context.get("track_context")
        self.assertIsInstance(track_context, dict, msg=context)
        assert isinstance(track_context, dict)
        self.assertEqual(track_context["track"]["id"], "track-dev-context")
        self.assertEqual(track_context["recent_handoffs"][0]["next_buddy"], "dev")
        self.assertNotIn("buddyswitch/objects", json.dumps(context, ensure_ascii=True))

        summary = self._dispatch(tool="context", action="summarize", args={}, instance_json=instance_json)
        self.assertTrue(summary.get("ok"), msg=summary)
        compact = summary.get("current_context_summary")
        self.assertIsInstance(compact, dict, msg=summary)
        assert isinstance(compact, dict)
        self.assertEqual(compact["task"]["id"], "task-dev-context")
        self.assertEqual(compact["track"]["id"], "track-dev-context")
        compact_artifact = compact["artifacts"][0]
        self.assertEqual(compact_artifact["id"], "art-dev-context-report-r1")
        self.assertNotIn("details", json.dumps(compact_artifact, ensure_ascii=True))

        sources = self._dispatch(tool="context", action="list_sources", args={}, instance_json=instance_json)
        self.assertTrue(sources.get("ok"), msg=sources)
        source_names = sources.get("sources")
        self.assertIsInstance(source_names, dict, msg=sources)
        assert isinstance(source_names, dict)
        self.assertIn("task_context.artifacts", source_names)
        self.assertIn("track_context.recent_handoffs", source_names)

    def test_context_get_rejects_mismatched_or_stale_context_payload_without_mutation(self) -> None:
        self._seed_task(
            task_id="task-dev-context-stale",
            buddy="dev",
            title="Dev Context Stale",
            initial_run_id="run-dev-context-stale-r1",
        )
        instance_json = self._instance_json(current_task_id="task-dev-context-stale")
        before = self._load_instance(instance_json)
        valid_context = {
            "ok": True,
            "instance_id": "inst-dev-example",
            "active_buddy": "dev",
            "current_task_id": "task-dev-context-stale",
            "current_track_id": None,
            "context_revision": "ctx-task-dev-context-stale-turn-2",
            "run_envelope": {
                "sequence": 2,
                "turn_identity": {
                    "instance_id": "inst-dev-example",
                    "active_buddy": "dev",
                    "task_id": "task-dev-context-stale",
                    "track_id": None,
                    "context_revision": "ctx-task-dev-context-stale-turn-2",
                    "sequence": 2,
                    "run_id": "run-dev-context-stale-r2",
                },
            },
        }

        wrong_instance = copy.deepcopy(valid_context)
        wrong_instance["instance_id"] = "inst-other"
        rejected_instance = self._dispatch(
            tool="context",
            action="get",
            args={"context": wrong_instance},
            instance_json=instance_json,
        )
        self.assertFalse(rejected_instance.get("ok"), msg=rejected_instance)
        self.assertEqual(rejected_instance.get("permission_boundary"), "active-instance")
        self.assertEqual(self._load_instance(instance_json), before)

        wrong_buddy = copy.deepcopy(valid_context)
        wrong_buddy["active_buddy"] = "pm"
        rejected_buddy = self._dispatch(
            tool="context",
            action="get",
            args={"context": wrong_buddy},
            instance_json=instance_json,
        )
        self.assertFalse(rejected_buddy.get("ok"), msg=rejected_buddy)
        self.assertEqual(rejected_buddy.get("permission_boundary"), "active-buddy")
        self.assertEqual(self._load_instance(instance_json), before)

        stale = copy.deepcopy(valid_context)
        stale["context_revision"] = "ctx-task-dev-context-stale-turn-1"
        stale["run_envelope"]["sequence"] = 1
        rejected_stale = self._dispatch(
            tool="context",
            action="get",
            args={"context": stale},
            instance_json=instance_json,
        )
        self.assertFalse(rejected_stale.get("ok"), msg=rejected_stale)
        self.assertEqual(rejected_stale.get("permission_boundary"), "prepare.context_revision")
        self.assertEqual(self._load_instance(instance_json), before)

    def test_handoff_validate_accepts_known_target_and_rejects_unknown_or_conflicting_target(self) -> None:
        self._seed_track(track_id="track-handoff", title="Handoff Track", current_buddy="pm", next_buddy="market")
        instance_json = self._instance_json(instance_id="inst-pm-example", buddy="pm", current_track_id="track-handoff")
        before = self._load_instance(instance_json)

        accepted = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "next_buddy": "market",
                "reason": "Market should validate positioning.",
                "context": "Use the PRD and current track summary.",
            },
            instance_json=instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertEqual(accepted.get("tool"), "handoff")
        self.assertEqual(accepted.get("action"), "handoff.validate")
        self.assertEqual(accepted.get("handoff", {}).get("next_buddy"), "market")
        self.assertEqual(self._load_instance(instance_json), before)

        unknown = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "next_buddy": "unknown",
                "reason": "Unknown buddy should fail.",
                "context": "No mutation should happen.",
            },
            instance_json=instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertFalse(unknown.get("ok"), msg=unknown)
        self.assertEqual(unknown.get("permission_boundary"), "manifest.buddies")
        self.assertEqual(self._load_instance(instance_json), before)

        conflict = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "next_buddy": "design",
                "reason": "Conflicts with current track next buddy.",
                "context": "No mutation should happen.",
            },
            instance_json=instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertFalse(conflict.get("ok"), msg=conflict)
        self.assertEqual(conflict.get("permission_boundary"), "handoff.track_transition")
        self.assertEqual(self._load_instance(instance_json), before)

    def test_context_get_and_summarize_return_same_decision_surface_for_active_binding(self) -> None:
        track_id, _ = self._seed_pm_track_with_market_handoff()
        market_task_id = "task-market-context-decision-surface"
        self._seed_task(
            task_id=market_task_id,
            buddy="market",
            title="Market Bound Task",
            track_id=track_id,
            initial_run_id="run-market-bound-r1",
        )
        instance_json = self._instance_json(
            instance_id="inst-market-example",
            buddy="market",
            current_task_id=market_task_id,
            current_track_id=track_id,
        )
        prepared = self._prepare(
            instance_json=instance_json,
            instance_id="inst-market-example",
            buddy="market",
            text="Continue PM handoff in market context.",
        )
        context_get = self._dispatch(
            tool="context",
            action="get",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertTrue(context_get.get("ok"), msg=context_get)
        summary = self._dispatch(
            tool="context",
            action="summarize",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertTrue(summary.get("ok"), msg=summary)

        self.assertIn("decision_surface", prepared["runtime_context"])
        self.assertIn("decision_surface", context_get)
        self.assertIn("decision_surface", summary)
        self.assertEqual(context_get["decision_surface"], prepared["runtime_context"]["decision_surface"])
        self.assertEqual(summary["decision_surface"], prepared["runtime_context"]["decision_surface"])

    def test_context_list_sources_matches_prepare_structured_descriptors(self) -> None:
        track_id, _ = self._seed_pm_track_with_market_handoff()
        market_task_id = "task-market-structured-source"
        self._seed_task(
            task_id=market_task_id,
            buddy="market",
            title="Market Structured Source Task",
            track_id=track_id,
            initial_run_id="run-market-structured-source-r1",
        )
        instance_json = self._instance_json(
            instance_id="inst-market-source-desc",
            buddy="market",
            current_task_id=market_task_id,
            current_track_id=track_id,
        )
        prepared = self._prepare(
            instance_json=instance_json,
            instance_id="inst-market-source-desc",
            buddy="market",
            text="Read structured context sources.",
        )
        listed = self._dispatch(
            tool="context",
            action="list_sources",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-source-desc",
            buddy="market",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        prepare_sources = prepared["runtime_context"]["context_sources_desc"]
        listed_sources = listed["sources"]
        self.assertEqual(set(prepare_sources), set(listed_sources))
        for name, descriptor in listed_sources.items():
            with self.subTest(name=name):
                self.assertIsInstance(descriptor, dict)
                assert isinstance(descriptor, dict)
                for field in ("description", "content", "scope", "nullable", "decision_use"):
                    self.assertIn(field, descriptor)
        self.assertEqual(listed_sources["task_context.artifacts"]["content"], "full")
        self.assertEqual(listed_sources["current_context_summary"]["content"], "summary")

    def test_context_summarize_unbound_market_returns_candidate_tracks_without_binding_mutation(self) -> None:
        track_id, _ = self._seed_pm_track_with_market_handoff()
        instance_json = self._instance_json(instance_id="inst-market-unbound", buddy="market")
        before = self._load_instance(instance_json)
        summary = self._dispatch(
            tool="context",
            action="summarize",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-unbound",
            buddy="market",
        )
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertIn("candidate_tracks", summary)
        candidate_tracks = summary["candidate_tracks"]
        self.assertIsInstance(candidate_tracks, list, msg=summary)
        assert isinstance(candidate_tracks, list)
        self.assertIn(track_id, {row["track_id"] for row in candidate_tracks})
        first_row = candidate_tracks[0]
        self.assertIn("relevance_reasons", first_row)
        self.assertIn("track.next_buddy == active_buddy", first_row["relevance_reasons"])
        self.assertEqual(self._load_instance(instance_json), before)

    def test_handoff_validate_returns_track_alignment_and_discoverability(self) -> None:
        track_id, _ = self._seed_pm_track_with_market_handoff()
        instance_json = self._instance_json(
            instance_id="inst-pm-handoff-semantic",
            buddy="pm",
            current_track_id=track_id,
        )
        before = self._load_instance(instance_json)
        accepted = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "next_buddy": "market",
                "reason": "Market should continue from PM output.",
                "context": "Use PM PRD plus run audit context.",
            },
            instance_json=instance_json,
            instance_id="inst-pm-handoff-semantic",
            buddy="pm",
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertIn("track_alignment", accepted)
        self.assertIn("discoverability", accepted)
        self.assertTrue(accepted["track_alignment"]["target_matches_track_next_buddy"])
        self.assertEqual(accepted["discoverability"]["available_after"], "run.commit")
        self.assertEqual(
            accepted["discoverability"]["discovery_surfaces"],
            ["track.list", "track.get", "context.summarize"],
        )
        self.assertEqual(self._load_instance(instance_json), before)

    def test_handoff_validate_conflict_returns_suggested_next_buddy(self) -> None:
        track_id, _ = self._seed_pm_track_with_market_handoff()
        instance_json = self._instance_json(
            instance_id="inst-pm-handoff-conflict-semantic",
            buddy="pm",
            current_track_id=track_id,
        )
        conflict = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "next_buddy": "design",
                "reason": "Force a conflicting next buddy.",
                "context": "This should return suggested_next_buddy.",
            },
            instance_json=instance_json,
            instance_id="inst-pm-handoff-conflict-semantic",
            buddy="pm",
        )
        self.assertFalse(conflict.get("ok"), msg=conflict)
        self.assertEqual(conflict.get("permission_boundary"), "handoff.track_transition")
        self.assertIn("track_alignment", conflict)
        self.assertEqual(conflict["track_alignment"]["suggested_next_buddy"], "market")


if __name__ == "__main__":
    unittest.main()
