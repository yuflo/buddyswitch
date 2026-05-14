#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool track env tool operations."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
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


class TrackManagerEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
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
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-track-env-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": "track",
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
    ) -> None:
        env_store.create_task(
            task_id,
            title,
            buddy=buddy,
            track_id=track_id,
            status="active",
            summary="",
            initial_run_id=None,
        )

    def _tracks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tracks_dir = self._runtime_path("buddyswitch/objects/tracks")
        if not tracks_dir.exists():
            return rows
        for path in sorted(tracks_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def _tasks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tasks_dir = self._runtime_path("buddyswitch/objects/tasks")
        if not tasks_dir.exists():
            return rows
        for path in sorted(tasks_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def _load_instance(self, instance_json: Path) -> dict[str, object]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

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
                        "reason": "handoff for discovery ranking",
                        "context": "continue from PM outputs",
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _assert_lifecycle_rejection(self, response: dict[str, object], *, action: str) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "track")
        self.assertEqual(response.get("action"), action)
        self.assertEqual(response.get("active_buddy"), "dev")
        self.assertEqual(response.get("permission_boundary"), "track.lifecycle_authority")
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_TRACK_LIFECYCLE_AUTHORITY")
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def test_pm_track_lifecycle_operations_use_env_tool_and_persist(self) -> None:
        instance_json = self._instance_json()

        created = self._dispatch(
            action="create",
            args={
                "track_id": "track-env-tool",
                "title": "Env Tool Track",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "market",
                "summary": "Created through the track env tool.",
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertEqual(created.get("tool"), "track")
        self.assertEqual(created.get("action"), "track.create")
        self.assertEqual(created.get("active_buddy"), "pm")
        created_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(created_track)
        assert created_track is not None
        self.assertEqual(created_track["title"], "Env Tool Track")
        self.assertEqual(created_track["current_buddy"], "pm")
        self.assertEqual(created_track["next_buddy"], "market")

        updated = self._dispatch(
            action="update",
            args={
                "track_id": "track-env-tool",
                "title": "Env Tool Track Updated",
                "status": "blocked",
                "summary": "Blocked pending research.",
            },
            instance_json=instance_json,
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual(updated.get("action"), "track.update")
        updated_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(updated_track)
        assert updated_track is not None
        self.assertEqual(updated_track["title"], "Env Tool Track Updated")
        self.assertEqual(updated_track["status"], "blocked")
        self.assertEqual(updated_track["summary"], "Blocked pending research.")

        advanced = self._dispatch(
            action="advance",
            args={
                "track_id": "track-env-tool",
                "current_buddy": "market",
                "next_buddy": "design",
                "status": "active",
                "summary": "Market owns the next step.",
            },
            instance_json=instance_json,
        )
        self.assertTrue(advanced.get("ok"), msg=advanced)
        self.assertEqual(advanced.get("action"), "track.advance")
        advanced_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(advanced_track)
        assert advanced_track is not None
        self.assertEqual(advanced_track["current_buddy"], "market")
        self.assertEqual(advanced_track["next_buddy"], "design")
        self.assertEqual(advanced_track["status"], "active")

        archived = self._dispatch(
            action="archive",
            args={"track_id": "track-env-tool"},
            instance_json=instance_json,
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual(archived.get("action"), "track.archive")
        archived_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(archived_track)
        assert archived_track is not None
        self.assertEqual(archived_track["status"], "archived")

    def test_non_pm_can_read_tracks_but_lifecycle_mutations_reject_without_mutation(self) -> None:
        self._seed_track(
            track_id="track-visible",
            title="Visible Track",
            current_buddy="pm",
            next_buddy="market",
            summary="Readable coordination context.",
        )
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev")

        listed = self._dispatch(
            action="list",
            args={},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        track_ids = {row.get("id") for row in listed.get("tracks", []) if isinstance(row, dict)}
        self.assertIn("track-visible", track_ids)

        fetched = self._dispatch(
            action="get",
            args={"track_id": "track-visible"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched.get("track_id"), "track-visible")

        before_tracks = copy.deepcopy(self._tracks_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())
        for action, args in (
            (
                "create",
                {
                    "track_id": "track-spoofed-create",
                    "title": "Spoofed Create",
                    "active_buddy": "pm",
                },
            ),
            (
                "update",
                {
                    "track_id": "track-visible",
                    "summary": "should not persist",
                    "active_buddy": "pm",
                },
            ),
            (
                "advance",
                {
                    "track_id": "track-visible",
                    "current_buddy": "dev",
                    "next_buddy": "test",
                    "active_buddy": "pm",
                },
            ),
            ("archive", {"track_id": "track-visible", "active_buddy": "pm"}),
        ):
            with self.subTest(action=action):
                response = self._dispatch(
                    action=action,
                    args=args,
                    instance_json=instance_json,
                    instance_id="inst-dev-example",
                    buddy="dev",
                )
                self._assert_lifecycle_rejection(response, action=f"track.{action}")
                self.assertEqual(self._tracks_snapshot(), before_tracks)
                self.assertEqual(self._tasks_snapshot(), before_tasks)

    def test_attach_and_detach_task_keep_task_track_backlinks_consistent(self) -> None:
        self._seed_track(track_id="track-link", title="Link Track", current_buddy="pm")
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Owned Dev Task")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="Foreign PM Task")
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev")

        attached = self._dispatch(
            action="attach_task",
            args={"track_id": "track-link", "task_id": "task-dev-owned"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        self.assertEqual(attached.get("action"), "track.attach_task")
        linked_task = env_store.get_task("task-dev-owned")
        linked_track = env_store.get_track("track-link")
        self.assertIsNotNone(linked_task)
        self.assertIsNotNone(linked_track)
        assert linked_task is not None
        assert linked_track is not None
        self.assertEqual(linked_task["track_id"], "track-link")
        self.assertIn("task-dev-owned", linked_track["task_ids"])

        detached = self._dispatch(
            action="detach_task",
            args={"track_id": "track-link", "task_id": "task-dev-owned"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(detached.get("ok"), msg=detached)
        self.assertEqual(detached.get("action"), "track.detach_task")
        detached_task = env_store.get_task("task-dev-owned")
        detached_track = env_store.get_track("track-link")
        self.assertIsNotNone(detached_task)
        self.assertIsNotNone(detached_track)
        assert detached_task is not None
        assert detached_track is not None
        self.assertIsNone(detached_task["track_id"])
        self.assertNotIn("task-dev-owned", detached_track["task_ids"])

        before_tracks = copy.deepcopy(self._tracks_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())
        foreign = self._dispatch(
            action="attach_task",
            args={"track_id": "track-link", "task_id": "task-pm-foreign"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(foreign.get("ok"), msg=foreign)
        self.assertEqual(foreign.get("permission_boundary"), "task.buddy_scope")
        self.assertEqual(self._tracks_snapshot(), before_tracks)
        self.assertEqual(self._tasks_snapshot(), before_tasks)

        missing_track = self._dispatch(
            action="attach_task",
            args={"track_id": "track-missing", "task_id": "task-dev-owned"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(missing_track.get("ok"), msg=missing_track)
        self.assertEqual(missing_track.get("permission_boundary"), "track.lookup")

        missing_task = self._dispatch(
            action="attach_task",
            args={"track_id": "track-link", "task_id": "task-missing"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(missing_task.get("ok"), msg=missing_task)
        self.assertEqual(missing_task.get("permission_boundary"), "task.lookup")

    def test_track_join_creates_attaches_and_selects_active_buddy_task_without_lifecycle_mutation(self) -> None:
        self._seed_track(
            track_id="track-join-create",
            title="Track Join Create",
            current_buddy="pm",
            next_buddy="dev",
            summary="join create",
        )
        before = copy.deepcopy(env_store.get_track("track-join-create"))
        assert before is not None
        instance_json = self._instance_json(instance_id="inst-dev-join-create", buddy="dev")
        joined = self._dispatch(
            action="join",
            args={"track_id": "track-join-create"},
            instance_json=instance_json,
            instance_id="inst-dev-join-create",
            buddy="dev",
        )
        self.assertTrue(joined.get("ok"), msg=joined)
        self.assertTrue(joined.get("created_task"), msg=joined)
        task_id = joined.get("task_id")
        self.assertIsInstance(task_id, str, msg=joined)
        assert isinstance(task_id, str)
        task = env_store.get_task(task_id)
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.get("buddy"), "dev")
        self.assertEqual(task.get("track_id"), "track-join-create")
        instance_payload = self._load_instance(instance_json)
        self.assertEqual(instance_payload.get("current_task_id"), task_id)
        self.assertEqual(instance_payload.get("current_track_id"), "track-join-create")
        after = env_store.get_track("track-join-create")
        self.assertIsNotNone(after)
        assert after is not None
        for key in ("status", "current_buddy", "next_buddy", "title", "summary"):
            self.assertEqual(after.get(key), before.get(key))
        self.assertIn(task_id, after.get("task_ids", []))

    def test_track_join_reuses_single_existing_active_buddy_task_idempotently(self) -> None:
        self._seed_track(track_id="track-join-reuse", title="Track Join Reuse", current_buddy="pm", next_buddy="dev")
        self._seed_task(task_id="task-dev-join-reuse", buddy="dev", title="Dev Join Reuse", track_id="track-join-reuse")
        instance_json = self._instance_json(instance_id="inst-dev-join-reuse", buddy="dev")
        first = self._dispatch(
            action="join",
            args={"track_id": "track-join-reuse"},
            instance_json=instance_json,
            instance_id="inst-dev-join-reuse",
            buddy="dev",
        )
        second = self._dispatch(
            action="join",
            args={"track_id": "track-join-reuse"},
            instance_json=instance_json,
            instance_id="inst-dev-join-reuse",
            buddy="dev",
        )
        self.assertTrue(first.get("ok"), msg=first)
        self.assertTrue(second.get("ok"), msg=second)
        self.assertEqual(first.get("task_id"), "task-dev-join-reuse")
        self.assertEqual(second.get("task_id"), "task-dev-join-reuse")
        self.assertFalse(second.get("created_task"), msg=second)
        track = env_store.get_track("track-join-reuse")
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(track.get("task_ids", []).count("task-dev-join-reuse"), 1)

    def test_track_join_rejects_multiple_existing_active_buddy_tasks_with_explicit_task_recovery(self) -> None:
        self._seed_track(track_id="track-join-ambiguous", title="Track Join Ambiguous", current_buddy="pm", next_buddy="dev")
        self._seed_task(task_id="task-dev-join-a", buddy="dev", title="Dev Join A", track_id="track-join-ambiguous")
        self._seed_task(task_id="task-dev-join-b", buddy="dev", title="Dev Join B", track_id="track-join-ambiguous")
        instance_json = self._instance_json(instance_id="inst-dev-join-ambiguous", buddy="dev")
        rejected = self._dispatch(
            action="join",
            args={"track_id": "track-join-ambiguous"},
            instance_json=instance_json,
            instance_id="inst-dev-join-ambiguous",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "track.join_ambiguity")
        candidates = rejected.get("candidate_task_ids")
        self.assertIsInstance(candidates, list, msg=rejected)
        assert isinstance(candidates, list)
        self.assertEqual(set(candidates), {"task-dev-join-a", "task-dev-join-b"})
        self.assertIn("--task-id", str(rejected.get("command_hint")))

        selected = self._dispatch(
            action="join",
            args={"track_id": "track-join-ambiguous", "task_id": "task-dev-join-a"},
            instance_json=instance_json,
            instance_id="inst-dev-join-ambiguous",
            buddy="dev",
        )
        self.assertTrue(selected.get("ok"), msg=selected)
        self.assertEqual(selected.get("task_id"), "task-dev-join-a")

    def test_track_join_rejects_foreign_or_other_track_task_without_mutation(self) -> None:
        self._seed_track(track_id="track-join-main", title="Track Join Main", current_buddy="pm", next_buddy="dev")
        self._seed_track(track_id="track-join-other", title="Track Join Other", current_buddy="pm", next_buddy="dev")
        self._seed_task(task_id="task-pm-join-foreign", buddy="pm", title="PM Foreign", track_id="track-join-main")
        self._seed_task(task_id="task-dev-join-other", buddy="dev", title="Dev Other Track", track_id="track-join-other")
        instance_json = self._instance_json(instance_id="inst-dev-join-reject", buddy="dev")
        before_tracks = copy.deepcopy(self._tracks_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())

        foreign = self._dispatch(
            action="join",
            args={"track_id": "track-join-main", "task_id": "task-pm-join-foreign"},
            instance_json=instance_json,
            instance_id="inst-dev-join-reject",
            buddy="dev",
        )
        self.assertFalse(foreign.get("ok"), msg=foreign)
        self.assertEqual(foreign.get("permission_boundary"), "task.buddy_scope")

        other_track = self._dispatch(
            action="join",
            args={"track_id": "track-join-main", "task_id": "task-dev-join-other"},
            instance_json=instance_json,
            instance_id="inst-dev-join-reject",
            buddy="dev",
        )
        self.assertFalse(other_track.get("ok"), msg=other_track)
        self.assertEqual(other_track.get("permission_boundary"), "track.task_linkage")
        self.assertEqual(self._tracks_snapshot(), before_tracks)
        self.assertEqual(self._tasks_snapshot(), before_tasks)

    def test_get_current_reads_active_instance_track_binding(self) -> None:
        self._seed_track(track_id="track-current", title="Current Track", current_buddy="pm")
        instance_json = self._instance_json(current_track_id="track-current")

        current = self._dispatch(action="get_current", args={}, instance_json=instance_json)

        self.assertTrue(current.get("ok"), msg=current)
        self.assertEqual(current.get("action"), "track.get_current")
        self.assertEqual(current.get("track_id"), "track-current")
        binding = current.get("current_binding")
        self.assertIsInstance(binding, dict, msg=current)
        assert isinstance(binding, dict)
        self.assertEqual(binding.get("current_track_id"), "track-current")
        track_payload = current.get("track")
        self.assertIsInstance(track_payload, dict, msg=current)
        assert isinstance(track_payload, dict)
        self.assertEqual(track_payload.get("id"), "track-current")

        unbound_instance_json = self._instance_json(instance_id="inst-pm-unbound")
        unbound = self._dispatch(
            action="get_current",
            args={},
            instance_json=unbound_instance_json,
            instance_id="inst-pm-unbound",
        )
        self.assertTrue(unbound.get("ok"), msg=unbound)
        self.assertIsNone(unbound.get("track"))

    def test_track_list_returns_discovery_summary_with_deterministic_candidate_order(self) -> None:
        self._seed_track(
            track_id="track-handoff-priority",
            title="Handoff Priority",
            current_buddy="pm",
            next_buddy="market",
            summary="recent PM handoff target",
        )
        self._seed_task(
            task_id="task-pm-handoff-priority",
            buddy="pm",
            title="PM Handoff Priority Task",
            track_id="track-handoff-priority",
        )
        self._write_handoff_run(
            run_id="run-handoff-priority-r1",
            task_id="task-pm-handoff-priority",
            track_id="track-handoff-priority",
            buddy_id="pm",
            next_buddy="market",
        )

        self._seed_track(
            track_id="track-next-only",
            title="Next Buddy Only",
            current_buddy="pm",
            next_buddy="market",
            summary="next-buddy match only",
        )
        self._seed_track(
            track_id="track-participant-only",
            title="Participant Only",
            current_buddy="pm",
            next_buddy="design",
            summary="market participates via one task",
        )
        self._seed_task(
            task_id="task-market-participant",
            buddy="market",
            title="Market Participant Task",
            track_id="track-participant-only",
        )
        self._seed_track(
            track_id="track-unrelated",
            title="Unrelated",
            current_buddy="pm",
            next_buddy="design",
            summary="no market relevance",
        )

        instance_json = self._instance_json(instance_id="inst-market-discovery", buddy="market")
        listed = self._dispatch(
            action="list",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-discovery",
            buddy="market",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        discovery_summary = listed.get("discovery_summary")
        self.assertIsInstance(discovery_summary, dict, msg=listed)
        assert isinstance(discovery_summary, dict)
        candidate_ids = discovery_summary.get("candidate_track_ids")
        self.assertEqual(
            candidate_ids,
            ["track-handoff-priority", "track-next-only", "track-participant-only"],
        )
        rows = listed.get("tracks")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        first = rows[0]
        self.assertIsInstance(first, dict, msg=listed)
        assert isinstance(first, dict)
        self.assertEqual(first.get("id"), "track-handoff-priority")
        discovery = first.get("discovery")
        self.assertIsInstance(discovery, dict, msg=listed)
        assert isinstance(discovery, dict)
        self.assertEqual(discovery.get("active_buddy_role"), "next_buddy")
        reasons = discovery.get("relevance_reasons")
        self.assertIsInstance(reasons, list, msg=listed)
        assert isinstance(reasons, list)
        self.assertIn("recent_handoff.next_buddy == active_buddy", reasons)
        self.assertIn("track.next_buddy == active_buddy", reasons)

    def test_track_list_uses_active_explicit_handoff_for_discovery_and_latest_summary_without_run_audit(self) -> None:
        self._seed_track(
            track_id="track-explicit-handoff-only",
            title="Explicit Handoff Only",
            current_buddy="pm",
            next_buddy="design",
            summary="explicit handoff target should drive discovery for market",
        )
        self._seed_task(
            task_id="task-pm-explicit-handoff-only",
            buddy="pm",
            title="PM Explicit Source",
            track_id="track-explicit-handoff-only",
        )
        env_store.create_handoff(
            handoff_id="handoff-explicit-market-r1",
            track_id="track-explicit-handoff-only",
            source_buddy="pm",
            target_buddy="market",
            source_task_id="task-pm-explicit-handoff-only",
            source_run_id="run-pm-explicit-handoff-r1",
            artifact_ids=["art-pm-explicit-handoff-r1"],
            historical_artifact_ids=[],
            reason="Market should continue from explicit handoff record.",
            context="Use explicit handoff context only.",
            status="active",
        )
        self._seed_track(
            track_id="track-explicit-handoff-unrelated",
            title="Explicit Handoff Unrelated",
            current_buddy="pm",
            next_buddy="design",
            summary="no market relevance",
        )

        instance_json = self._instance_json(instance_id="inst-market-explicit-handoff", buddy="market")
        listed = self._dispatch(
            action="list",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-explicit-handoff",
            buddy="market",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        discovery_summary = listed.get("discovery_summary")
        self.assertIsInstance(discovery_summary, dict, msg=listed)
        assert isinstance(discovery_summary, dict)
        candidate_ids = discovery_summary.get("candidate_track_ids")
        self.assertIsInstance(candidate_ids, list, msg=listed)
        assert isinstance(candidate_ids, list)
        self.assertIn("track-explicit-handoff-only", candidate_ids)

        rows = listed.get("tracks")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        target_row = next(
            row for row in rows if isinstance(row, dict) and row.get("id") == "track-explicit-handoff-only"
        )
        self.assertTrue(target_row.get("latest_handoff_summary"), msg=target_row)
        latest = target_row.get("latest_handoff_summary")
        self.assertIsInstance(latest, dict, msg=target_row)
        assert isinstance(latest, dict)
        self.assertEqual(latest.get("source_type"), "handoff_record")
        self.assertEqual(latest.get("target_buddy"), "market")
        self.assertEqual(latest.get("source_run_id"), "run-pm-explicit-handoff-r1")
        discovery = target_row.get("discovery")
        self.assertIsInstance(discovery, dict, msg=target_row)
        assert isinstance(discovery, dict)
        self.assertTrue(discovery.get("latest_handoff_to_active_buddy"), msg=target_row)

    def test_track_get_returns_track_context_summary_without_foreign_full_artifact_content(self) -> None:
        self._seed_track(
            track_id="track-context-summary",
            title="Context Summary Track",
            current_buddy="pm",
            next_buddy="market",
            summary="context summary smoke",
        )
        self._seed_task(
            task_id="task-pm-context-summary",
            buddy="pm",
            title="PM Context Summary Task",
            track_id="track-context-summary",
        )
        self._seed_task(
            task_id="task-market-context-summary",
            buddy="market",
            title="Market Context Summary Task",
            track_id="track-context-summary",
        )
        env_store.create_artifact(
            artifact_id="art-pm-context-prd-r1",
            title="PM PRD",
            buddy="pm",
            kind="prd",
            task_id="task-pm-context-summary",
            source_run_id="run-pm-context-r1",
            summary="pm summary",
            content={"secret": "full pm content must not leak in track summary"},
        )
        self._write_handoff_run(
            run_id="run-pm-context-handoff-r2",
            task_id="task-pm-context-summary",
            track_id="track-context-summary",
            buddy_id="pm",
            next_buddy="market",
        )

        instance_json = self._instance_json(instance_id="inst-market-track-get", buddy="market")
        fetched = self._dispatch(
            action="get",
            args={"track_id": "track-context-summary"},
            instance_json=instance_json,
            instance_id="inst-market-track-get",
            buddy="market",
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        summary = fetched.get("track_context_summary")
        self.assertIsInstance(summary, dict, msg=fetched)
        assert isinstance(summary, dict)
        tasks = summary.get("tasks")
        self.assertIsInstance(tasks, list, msg=fetched)
        assert isinstance(tasks, list)
        pm_row = next(row for row in tasks if isinstance(row, dict) and row.get("id") == "task-pm-context-summary")
        current_artifacts = pm_row.get("current_artifacts")
        self.assertIsInstance(current_artifacts, list, msg=fetched)
        assert isinstance(current_artifacts, list)
        self.assertGreaterEqual(len(current_artifacts), 1)
        art_row = current_artifacts[0]
        self.assertIsInstance(art_row, dict, msg=fetched)
        assert isinstance(art_row, dict)
        for key in ("id", "kind", "title", "summary", "source_buddy", "source_run", "revision", "currentness"):
            self.assertIn(key, art_row)
        self.assertNotIn("content", art_row)

    def test_track_get_returns_current_artifact_rows_with_readability_and_next_actions(self) -> None:
        self._seed_track(
            track_id="track-landing",
            title="Landing Page Track",
            current_buddy="pm",
            next_buddy="dev",
            summary="pm + design source rows",
        )
        self._seed_task(
            task_id="task-pm-prd",
            buddy="pm",
            title="PM PRD Task",
            track_id="track-landing",
        )
        self._seed_task(
            task_id="task-design-handoff",
            buddy="design",
            title="Design Handoff Task",
            track_id="track-landing",
        )
        env_store.create_artifact(
            artifact_id="art-pm-prd-r1",
            title="PM PRD",
            buddy="pm",
            kind="prd",
            task_id="task-pm-prd",
            source_run_id="run-pm-prd-r1",
            summary="pm prd summary",
            content={"body": "pm body must not leak from summary"},
        )
        env_store.create_artifact(
            artifact_id="art-design-handoff-r1",
            title="Design Handoff",
            buddy="design",
            kind="design-handoff",
            task_id="task-design-handoff",
            source_run_id="run-design-handoff-r1",
            summary="design summary",
            content={"body": "design body must not leak from summary"},
        )
        instance_json = self._instance_json(instance_id="inst-dev-track-get", buddy="dev")
        response = self._dispatch(
            action="get",
            args={"track_id": "track-landing"},
            instance_json=instance_json,
            instance_id="inst-dev-track-get",
            buddy="dev",
        )
        self.assertTrue(response.get("ok"), msg=response)
        rows = response.get("current_artifacts")
        self.assertIsInstance(rows, list, msg=response)
        assert isinstance(rows, list)
        artifact_ids = {row.get("artifact_id") for row in rows if isinstance(row, dict)}
        self.assertEqual(artifact_ids, {"art-pm-prd-r1", "art-design-handoff-r1"})
        for row in rows:
            self.assertIsInstance(row, dict, msg=response)
            assert isinstance(row, dict)
            for key in (
                "artifact_id",
                "kind",
                "title",
                "summary",
                "source_buddy",
                "source_task_id",
                "source_run_id",
                "revision",
                "currentness",
                "readable_by_current_buddy",
                "next_action",
            ):
                self.assertIn(key, row)
            self.assertNotIn("content", row)

    def test_invalid_buddy_refs_reject_without_partial_mutation(self) -> None:
        self._seed_track(track_id="track-refs", title="Ref Track", current_buddy="pm")
        instance_json = self._instance_json()
        before_tracks = copy.deepcopy(self._tracks_snapshot())

        for action, args in (
            (
                "create",
                {
                    "track_id": "track-invalid-current",
                    "title": "Invalid Current",
                    "current_buddy": "unknown",
                    "next_buddy": "market",
                },
            ),
            (
                "update",
                {
                    "track_id": "track-refs",
                    "current_buddy": "pm",
                    "next_buddy": "unknown",
                },
            ),
            (
                "advance",
                {
                    "track_id": "track-refs",
                    "current_buddy": "unknown",
                    "next_buddy": "design",
                },
            ),
        ):
            with self.subTest(action=action):
                response = self._dispatch(action=action, args=args, instance_json=instance_json)
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("permission_boundary"), "request-payload")
                self.assertEqual(self._tracks_snapshot(), before_tracks)

    def test_cli_prints_structured_json_for_track_commands(self) -> None:
        env = os.environ.copy()
        env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
        env.pop("BUDDYSWITCH_INSTANCE_ID", None)
        env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)

        unavailable = subprocess.run(
            ["python3", str(ENV_CLIENT), "track", "list"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(unavailable.returncode, 0, msg=unavailable.stderr)
        unavailable_payload = json.loads(unavailable.stdout)
        self.assertFalse(unavailable_payload.get("ok"), msg=unavailable_payload)
        self.assertEqual(unavailable_payload.get("error", {}).get("code"), "E_RUNTIME_BROKER_UNAVAILABLE")

        missing_payload_file = subprocess.run(
            ["python3", str(ENV_CLIENT), "track", "create", "--payload", str(ROOT / "tmp" / "missing-track.json")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_payload_file.returncode, 2)
        self.assertIn("payload file is not readable", missing_payload_file.stderr.lower())

    def test_live_broker_track_cli_uses_env_tool_and_returns_structured_rejection(self) -> None:
        self._seed_track(track_id="track-live", title="Live Track", current_buddy="pm")
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev")

        socket_path = self._runtime_path("runtime/runtime-broker.socket")
        pid_path = self._runtime_path("runtime/runtime-broker.pid")
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        broker_env = os.environ.copy()
        broker_env.update(
            {
                "BUDDYSWITCH_SHARED_ROOT": str(self.runtime_root),
                "BUDDYSWITCH_STATE_ROOT": str(self.runtime_root),
            }
        )
        broker = subprocess.Popen(
            [
                "python3",
                str(ROOT / "scripts" / "runtime_kernel" / "broker.py"),
                "serve",
                "--socket",
                str(socket_path),
                "--pid-file",
                str(pid_path),
                "--instance-json",
                str(instance_json),
                "--manifest",
                str(MANIFEST),
            ],
            cwd=ROOT,
            env=broker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if socket_path.exists():
                    break
                if broker.poll() is not None:
                    break
                time.sleep(0.05)
            if broker.poll() is not None:
                stderr = broker.stderr.read() if broker.stderr else "broker exited"
                self.fail(stderr)
            self.assertTrue(socket_path.exists(), "broker socket was not created")

            client_env = os.environ.copy()
            client_env.update(
                {
                    "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
                    "BUDDYSWITCH_INSTANCE_ID": "inst-dev-example",
                    "BUDDYSWITCH_ACTIVE_BUDDY": "dev",
                }
            )
            completed = subprocess.run(
                ["python3", str(ENV_CLIENT), "track", "archive", "--track-id", "track-live"],
                cwd=ROOT,
                env=client_env,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )
        finally:
            broker.terminate()
            try:
                broker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=5)

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("tool"), "track")
        self.assertEqual(payload.get("action"), "track.archive")
        self.assertEqual(payload.get("permission_boundary"), "track.lifecycle_authority")
        self.assertEqual(env_store.get_track("track-live")["status"], "active")


if __name__ == "__main__":
    unittest.main()
