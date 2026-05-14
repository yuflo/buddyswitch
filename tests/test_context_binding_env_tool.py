#!/usr/bin/env python3
"""Functional coverage for broker-routed context, binding, and handoff env tools."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
ENV_CLIENT = ROOT / "scripts" / "env" / "client.py"


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
            "request_id": f"req-context-env-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": tool,
                "action": action,
                "args": args,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        response: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            response[key] = value
        return response

    def _prepare(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        text: str,
    ) -> dict[str, object]:
        prepared = self._dispatch_broker_method(
            method="prepare",
            params={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(prepared.get("ok"), msg=prepared)
        payload = prepared.get("payload") if isinstance(prepared.get("payload"), dict) else prepared
        self.assertIsInstance(payload, dict, msg=prepared)
        assert isinstance(payload, dict)
        return payload

    def _dispatch_broker_method(
        self,
        *,
        method: str,
        params: dict[str, object],
        instance_json: Path,
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-context-broker-{uuid.uuid4().hex}",
            "method": method,
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                **params,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        payload: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
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
        self._seed_task(task_id="task-pm-handoff", buddy="pm", title="PM Handoff Task", track_id="track-handoff")
        self._seed_artifact(
            artifact_id="art-pm-handoff-prd-r1",
            task_id="task-pm-handoff",
            buddy="pm",
            kind="prd",
            title="PM Handoff PRD",
            source_run_id="run-pm-handoff-r1",
        )
        instance_json = self._instance_json(instance_id="inst-pm-example", buddy="pm", current_track_id="track-handoff")
        before = self._load_instance(instance_json)

        accepted = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "track_id": "track-handoff",
                "source_task_id": "task-pm-handoff",
                "source_run_id": "run-pm-handoff-r1",
                "target_buddy": "market",
                "reason": "Market should validate positioning.",
                "context": "Use the PRD and current track summary.",
                "artifact_ids": ["art-pm-handoff-prd-r1"],
                "historical_artifact_ids": [],
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
                "track_id": "track-handoff",
                "source_task_id": "task-pm-handoff",
                "source_run_id": "run-pm-handoff-r1",
                "target_buddy": "unknown",
                "reason": "Unknown buddy should fail.",
                "context": "No mutation should happen.",
                "artifact_ids": ["art-pm-handoff-prd-r1"],
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
                "track_id": "track-handoff",
                "source_task_id": "task-pm-handoff",
                "source_run_id": "run-pm-handoff-r1",
                "target_buddy": "design",
                "reason": "Conflicts with current track next buddy.",
                "context": "No mutation should happen.",
                "artifact_ids": ["art-pm-handoff-prd-r1"],
            },
            instance_json=instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertTrue(conflict.get("ok"), msg=conflict)
        alignment = conflict.get("track_alignment")
        self.assertIsInstance(alignment, dict, msg=conflict)
        assert isinstance(alignment, dict)
        self.assertFalse(alignment.get("target_matches_track_next_buddy"))
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
                "track_id": track_id,
                "source_task_id": "task-pm-handoff-seeded",
                "source_run_id": "run-pm-seeded-r1",
                "target_buddy": "market",
                "reason": "Market should continue from PM output.",
                "context": "Use PM PRD plus run audit context.",
                "artifact_ids": ["art-pm-seeded-prd-r1"],
            },
            instance_json=instance_json,
            instance_id="inst-pm-handoff-semantic",
            buddy="pm",
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        self.assertIn("track_alignment", accepted)
        self.assertIn("discoverability", accepted)
        self.assertTrue(accepted["track_alignment"]["target_matches_track_next_buddy"])
        self.assertEqual(accepted["discoverability"]["available_after"], "handoff.create or run.commit")
        self.assertEqual(
            accepted["discoverability"]["discovery_surfaces"],
            ["track.list", "track.get", "handoff.list"],
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
                "track_id": track_id,
                "source_task_id": "task-pm-handoff-seeded",
                "source_run_id": "run-pm-seeded-r1",
                "target_buddy": "design",
                "reason": "Force a conflicting next buddy.",
                "context": "This should return suggested_next_buddy.",
                "artifact_ids": ["art-pm-seeded-prd-r1"],
            },
            instance_json=instance_json,
            instance_id="inst-pm-handoff-conflict-semantic",
            buddy="pm",
        )
        self.assertTrue(conflict.get("ok"), msg=conflict)
        self.assertIn("track_alignment", conflict)
        self.assertFalse(conflict["track_alignment"]["target_matches_track_next_buddy"])
        self.assertEqual(conflict["track_alignment"]["track_next_buddy"], "market")

    def test_handoff_list_merges_explicit_records_and_run_audit_handoffs(self) -> None:
        track_id, source_task_id = self._seed_pm_track_with_market_handoff()
        env_store.create_handoff(
            handoff_id="handoff-track-pm-handoff-seeded-pm-to-dev-r1",
            track_id=track_id,
            source_buddy="pm",
            target_buddy="dev",
            source_task_id=source_task_id,
            source_run_id="run-pm-seeded-r1",
            artifact_ids=["art-pm-seeded-prd-r1"],
            historical_artifact_ids=[],
            reason="Dev should continue from PM PRD.",
            context="Use PM PRD source.",
            status="active",
        )
        dev_instance = self._instance_json(instance_id="inst-dev-handoff-list", buddy="dev")
        listed = self._dispatch(
            tool="handoff",
            action="list",
            args={"track_id": track_id},
            instance_json=dev_instance,
            instance_id="inst-dev-handoff-list",
            buddy="dev",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        rows = listed.get("handoffs")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        source_types = {row.get("source_type") for row in rows if isinstance(row, dict)}
        self.assertIn("handoff_record", source_types)
        self.assertIn("run_audit", source_types)

        explicit_rows = [row for row in rows if isinstance(row, dict) and row.get("source_type") == "handoff_record"]
        self.assertTrue(explicit_rows, msg=rows)
        explicit = explicit_rows[0]
        self.assertEqual(explicit.get("target_buddy"), "dev")
        self.assertTrue(explicit.get("read_authorizes_active_buddy"))

        unrelated_instance = self._instance_json(instance_id="inst-test-handoff-list", buddy="test")
        unrelated = self._dispatch(
            tool="handoff",
            action="list",
            args={"track_id": track_id},
            instance_json=unrelated_instance,
            instance_id="inst-test-handoff-list",
            buddy="test",
        )
        self.assertTrue(unrelated.get("ok"), msg=unrelated)
        unrelated_rows = unrelated.get("handoffs")
        self.assertIsInstance(unrelated_rows, list, msg=unrelated)
        assert isinstance(unrelated_rows, list)
        explicit_unrelated = [
            row
            for row in unrelated_rows
            if isinstance(row, dict) and row.get("source_type") == "handoff_record" and row.get("handoff_id") == explicit.get("handoff_id")
        ]
        self.assertTrue(explicit_unrelated, msg=unrelated_rows)
        self.assertFalse(explicit_unrelated[0].get("read_authorizes_active_buddy"))

    def test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle(self) -> None:
        track_id = "track-design-create-handoff"
        self._seed_track(
            track_id=track_id,
            title="Design Create Handoff",
            current_buddy="pm",
            next_buddy="dev",
            summary="design create handoff",
        )
        self._seed_task(task_id="task-design-create-handoff", buddy="design", title="Design Source", track_id=track_id)
        self._seed_artifact(
            artifact_id="art-design-create-handoff-r1",
            task_id="task-design-create-handoff",
            buddy="design",
            kind="design-handoff",
            title="Design Source Artifact",
            source_run_id="run-design-create-handoff-r1",
            content={"body": "design source body"},
        )
        before_track = copy.deepcopy(env_store.get_track(track_id))
        assert before_track is not None

        instance_json = self._instance_json(instance_id="inst-design-create-handoff", buddy="design", current_track_id=track_id)
        created = self._dispatch(
            tool="handoff",
            action="create",
            args={
                "track_id": track_id,
                "source_task_id": "task-design-create-handoff",
                "source_run_id": "run-design-create-handoff-r1",
                "target_buddy": "dev",
                "artifact_ids": ["art-design-create-handoff-r1"],
                "historical_artifact_ids": [],
                "reason": "Dev should implement from design handoff.",
                "context": "Use design handoff artifact only.",
            },
            instance_json=instance_json,
            instance_id="inst-design-create-handoff",
            buddy="design",
        )
        self.assertTrue(created.get("ok"), msg=created)
        handoff = created.get("handoff")
        self.assertIsInstance(handoff, dict, msg=created)
        assert isinstance(handoff, dict)
        handoff_id = handoff.get("id")
        self.assertIsInstance(handoff_id, str, msg=created)
        assert isinstance(handoff_id, str)
        persisted = env_store.get_handoff(handoff_id)
        self.assertIsNotNone(persisted)

        after_track = env_store.get_track(track_id)
        self.assertIsNotNone(after_track)
        assert after_track is not None
        for key in ("status", "current_buddy", "next_buddy", "title", "summary"):
            self.assertEqual(after_track.get(key), before_track.get(key))

    def test_handoff_create_rejects_hidden_lifecycle_fields_without_mutation(self) -> None:
        track_id = "track-design-create-handoff-hidden"
        self._seed_track(
            track_id=track_id,
            title="Design Create Handoff Hidden",
            current_buddy="pm",
            next_buddy="dev",
            summary="design create hidden lifecycle",
        )
        self._seed_task(task_id="task-design-create-hidden", buddy="design", title="Design Source", track_id=track_id)
        self._seed_artifact(
            artifact_id="art-design-create-hidden-r1",
            task_id="task-design-create-hidden",
            buddy="design",
            kind="design-handoff",
            title="Design Hidden Source Artifact",
            source_run_id="run-design-create-hidden-r1",
            content={"body": "design hidden source body"},
        )
        before_track = copy.deepcopy(env_store.get_track(track_id))
        before_handoff_ids = {row["id"] for row in env_store.list_handoffs()}

        instance_json = self._instance_json(instance_id="inst-design-create-hidden", buddy="design", current_track_id=track_id)
        rejected = self._dispatch(
            tool="handoff",
            action="create",
            args={
                "track_id": track_id,
                "source_task_id": "task-design-create-hidden",
                "source_run_id": "run-design-create-hidden-r1",
                "target_buddy": "dev",
                "artifact_ids": ["art-design-create-hidden-r1"],
                "historical_artifact_ids": [],
                "reason": "should reject hidden lifecycle field",
                "context": "hidden lifecycle mutation attempt",
                "track_status": "done",
            },
            instance_json=instance_json,
            instance_id="inst-design-create-hidden",
            buddy="design",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "handoff.lifecycle_boundary")
        self.assertEqual(env_store.get_track(track_id), before_track)
        self.assertEqual({row["id"] for row in env_store.list_handoffs()}, before_handoff_ids)

    def test_handoff_create_rejects_unlinked_source_task_without_mutation(self) -> None:
        track_id = "track-design-create-handoff-unlinked"
        task_id = "task-design-create-unlinked"
        artifact_id = "art-design-create-unlinked-r1"
        self._seed_track(
            track_id=track_id,
            title="Design Create Handoff Unlinked",
            current_buddy="pm",
            next_buddy="dev",
            summary="design create unlinked rejection",
        )
        self._seed_task(task_id=task_id, buddy="design", title="Design Source Unlinked", track_id=None)
        self._seed_artifact(
            artifact_id=artifact_id,
            task_id=task_id,
            buddy="design",
            kind="design-handoff",
            title="Design Unlinked Source Artifact",
            source_run_id="run-design-create-unlinked-r1",
            content={"body": "design unlinked source body"},
        )
        before_track = copy.deepcopy(env_store.get_track(track_id))
        before_task = copy.deepcopy(env_store.get_task(task_id))
        before_handoff_ids = {row["id"] for row in env_store.list_handoffs()}

        instance_json = self._instance_json(instance_id="inst-design-create-unlinked", buddy="design", current_track_id=track_id)
        rejected = self._dispatch(
            tool="handoff",
            action="create",
            args={
                "track_id": track_id,
                "source_task_id": task_id,
                "source_run_id": "run-design-create-unlinked-r1",
                "target_buddy": "dev",
                "artifact_ids": [artifact_id],
                "historical_artifact_ids": [],
                "reason": "must reject unlinked source task",
                "context": "handoff.create should not repair source task linkage",
            },
            instance_json=instance_json,
            instance_id="inst-design-create-unlinked",
            buddy="design",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "track.task_linkage")
        self.assertEqual(env_store.get_track(track_id), before_track)
        self.assertEqual(env_store.get_task(task_id), before_task)
        self.assertEqual({row["id"] for row in env_store.list_handoffs()}, before_handoff_ids)

    def test_handoff_validate_rejects_foreign_source_artifact_non_current_without_historical_flag_and_hidden_lifecycle_fields(self) -> None:
        track_id = "track-design-validate-handoff"
        self._seed_track(
            track_id=track_id,
            title="Design Validate Handoff",
            current_buddy="pm",
            next_buddy="dev",
            summary="design validate handoff",
        )
        self._seed_task(task_id="task-design-validate-handoff", buddy="design", title="Design Source", track_id=track_id)
        self._seed_task(task_id="task-pm-validate-handoff", buddy="pm", title="PM Source", track_id=track_id)
        self._seed_artifact(
            artifact_id="art-design-validate-old-r1",
            task_id="task-design-validate-handoff",
            buddy="design",
            kind="design-handoff",
            title="Design Old",
            source_run_id="run-design-validate-r1",
            content={"body": "design old body"},
        )
        self._seed_artifact(
            artifact_id="art-design-validate-new-r2",
            task_id="task-design-validate-handoff",
            buddy="design",
            kind="design-handoff",
            title="Design New",
            source_run_id="run-design-validate-r2",
            content={"body": "design new body"},
        )
        self._seed_artifact(
            artifact_id="art-pm-validate-r1",
            task_id="task-pm-validate-handoff",
            buddy="pm",
            kind="prd",
            title="PM Foreign",
            source_run_id="run-pm-validate-r1",
            content={"body": "pm foreign body"},
        )
        instance_json = self._instance_json(instance_id="inst-design-validate-handoff", buddy="design", current_track_id=track_id)
        before_track = copy.deepcopy(env_store.get_track(track_id))

        foreign = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "track_id": track_id,
                "source_task_id": "task-design-validate-handoff",
                "source_run_id": "run-design-validate-r2",
                "target_buddy": "dev",
                "artifact_ids": ["art-pm-validate-r1"],
                "reason": "should fail foreign",
                "context": "foreign artifact",
            },
            instance_json=instance_json,
            instance_id="inst-design-validate-handoff",
            buddy="design",
        )
        self.assertFalse(foreign.get("ok"), msg=foreign)
        self.assertEqual(foreign.get("permission_boundary"), "handoff.source_artifact_scope")

        historical_missing = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "track_id": track_id,
                "source_task_id": "task-design-validate-handoff",
                "source_run_id": "run-design-validate-r2",
                "target_buddy": "dev",
                "artifact_ids": ["art-design-validate-old-r1"],
                "reason": "should fail missing historical marker",
                "context": "historical artifact without marker",
            },
            instance_json=instance_json,
            instance_id="inst-design-validate-handoff",
            buddy="design",
        )
        self.assertFalse(historical_missing.get("ok"), msg=historical_missing)
        self.assertEqual(historical_missing.get("permission_boundary"), "handoff.historical_marker")

        hidden_lifecycle = self._dispatch(
            tool="handoff",
            action="validate",
            args={
                "track_id": track_id,
                "source_task_id": "task-design-validate-handoff",
                "source_run_id": "run-design-validate-r2",
                "target_buddy": "dev",
                "artifact_ids": ["art-design-validate-new-r2"],
                "reason": "should fail lifecycle field",
                "context": "hidden lifecycle mutation",
                "track_status": "done",
            },
            instance_json=instance_json,
            instance_id="inst-design-validate-handoff",
            buddy="design",
        )
        self.assertFalse(hidden_lifecycle.get("ok"), msg=hidden_lifecycle)
        self.assertEqual(hidden_lifecycle.get("permission_boundary"), "handoff.lifecycle_boundary")
        self.assertEqual(env_store.get_track(track_id), before_track)

    def test_context_feedback_points_to_direct_artifact_tools_not_context_read_actions(self) -> None:
        track_id, _ = self._seed_pm_track_with_market_handoff()
        instance_json = self._instance_json(instance_id="inst-market-direct-tools", buddy="market")
        summary = self._dispatch(
            tool="context",
            action="summarize",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-direct-tools",
            buddy="market",
        )
        self.assertTrue(summary.get("ok"), msg=summary)
        context_get = self._dispatch(
            tool="context",
            action="get",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-direct-tools",
            buddy="market",
        )
        self.assertTrue(context_get.get("ok"), msg=context_get)
        serialized = json.dumps({"summary": summary, "get": context_get}, ensure_ascii=True, sort_keys=True)
        self.assertNotIn("context.get_track_artifacts", serialized)
        self.assertNotIn("context.inspect_track_outputs", serialized)
        self.assertNotIn("context.explain_track_access", serialized)
        self.assertNotIn("context.validate_sources_available", serialized)
        self.assertIn("track.get", serialized)
        self.assertIn("artifact.get", serialized)
        self.assertIn(track_id, serialized)

    def test_handoff_cli_exposes_list_validate_and_create(self) -> None:
        env = os.environ.copy()
        env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
        env.pop("BUDDYSWITCH_INSTANCE_ID", None)
        env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)

        for args, token in (
            (["handoff", "list", "--help"], "--track-id"),
            (["handoff", "validate", "--help"], "--payload"),
            (["handoff", "create", "--help"], "--payload"),
        ):
            with self.subTest(args=args):
                completed = subprocess.run(
                    ["python3", str(ENV_CLIENT), *args],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)
                self.assertIn(token, completed.stdout)


if __name__ == "__main__":
    unittest.main()
