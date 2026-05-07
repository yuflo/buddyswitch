#!/usr/bin/env python3
"""Buddy-run persistence behavior tests for turn runtime."""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


def _pm_commit() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
        "working_notes": [
            "The user requested PRD creation and track binding in one PM run.",
        ],
        "artifacts": [
            {
                "kind": "prd",
                "title": "AI Schedule Tool Landing Page PRD",
                "summary": "Defines landing page scope, sections, MVP requirements, and acceptance criteria.",
                "content": {
                    "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
                    "requirements": [
                        "Explain the core promise in the hero",
                        "Show concrete scheduling workflows",
                    ],
                },
            }
        ],
        "state_effects": {
            "track": {
                "action": "create",
                "track_id": "track-ai-schedule-landing-page",
                "title": "AI Schedule Tool Landing Page",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "market",
                "summary": "Cross-buddy landing page iteration for an AI schedule tool.",
            },
            "task": {
                "status": "done",
                "summary": "PM PRD is ready for market positioning research.",
            },
        },
        "handoff": {
            "next_buddy": "market",
            "reason": "Market should validate competitor landing page positioning before design.",
            "context": "Use the PRD artifact and track summary as source context.",
        },
        "contributors": {
            "skills": ["write-prd", "track-manager"],
            "agents": [],
        },
    }


class TurnRuntimeBuddyRunTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": "instance-test",
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _prepare(self, request_text: str, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy=buddy, payload=payload)):
            context = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(context["ok"], msg=context)
        return context

    def _persist(self, context: dict[str, object], result: dict[str, object]) -> dict[str, object]:
        payload = turn_runtime.persist_buddy_run(context, result=result, manifest_path=MANIFEST)
        self.assertTrue(payload["ok"], msg=payload)
        return payload

    def _run_payload(self, run_id: str) -> dict[str, object]:
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        return json.loads(run_path.read_text(encoding="utf-8"))

    def _runtime_state_snapshot(self) -> dict[str, object]:
        def _load_dir(dir_path: Path) -> dict[str, object]:
            rows: dict[str, object] = {}
            if not dir_path.exists():
                return rows
            for path in sorted(dir_path.glob("*.json")):
                rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
            return rows

        return {
            "tracks": _load_dir(self._runtime_path("buddyswitch/objects/tracks")),
            "tasks": _load_dir(self._runtime_path("buddyswitch/objects/tasks")),
            "artifacts": _load_dir(self._runtime_path("buddyswitch/objects/artifacts")),
            "runs": _load_dir(self._runtime_path("buddyswitch/content/runs")),
            "reservations": _load_dir(self._runtime_path("buddyswitch/content/runs/reserved")),
        }

    def _assert_runtime_state_unchanged(self, before: dict[str, object], after: dict[str, object]) -> None:
        self.assertEqual(after, before)

    def _persist_via_cmd(
        self,
        *,
        context: dict[str, object],
        result: dict[str, object],
        session_buddy: str,
        broker_mode: str = "server",
    ) -> tuple[int, dict[str, object]]:
        raw_dir = self._runtime_path("runs/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
        context_path = raw_dir / "persist-context.json"
        result_path = raw_dir / "persist-result.json"
        context_path.write_text(json.dumps(context, ensure_ascii=True), encoding="utf-8")
        result_path.write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")
        args = argparse.Namespace(
            context=str(context_path),
            result=str(result_path),
            manifest=MANIFEST,
        )
        session = self._session(buddy=session_buddy, payload={})
        stdout = io.StringIO()
        env_patch = {"BUDDYSWITCH_RUNTIME_BROKER_MODE": broker_mode}
        with (
            patch.object(turn_runtime, "_load_product_mode_session", return_value=session),
            patch.object(turn_runtime, "_hold_product_runtime_lock", side_effect=lambda _: contextlib.nullcontext()),
            patch.dict(os.environ, env_patch, clear=False),
            patch("sys.stdout", new=stdout),
        ):
            exit_code = turn_runtime._cmd_persist(args)
        payload = json.loads(stdout.getvalue())
        return exit_code, payload

    def _prepare_via_cmd(
        self,
        *,
        request_text: str,
        session_buddy: str,
        broker_mode: str = "server",
    ) -> tuple[int, dict[str, object]]:
        args = argparse.Namespace(text=request_text, manifest=MANIFEST)
        session = self._session(buddy=session_buddy, payload={})
        stdout = io.StringIO()
        env_patch = {"BUDDYSWITCH_RUNTIME_BROKER_MODE": broker_mode}
        with (
            patch.object(turn_runtime, "_load_product_mode_session", return_value=session),
            patch.dict(os.environ, env_patch, clear=False),
            patch("sys.stdout", new=stdout),
        ):
            exit_code = turn_runtime._cmd_prepare(args)
        payload = json.loads(stdout.getvalue())
        return exit_code, payload

    def test_persist_cli_help_exposes_context_result_only(self) -> None:
        completed = subprocess.run(
            ["python3", str(ROOT / "scripts" / "turn_runtime.py"), "persist", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("--context", completed.stdout)
        self.assertIn("--result", completed.stdout)
        self.assertNotIn("--skill-id", completed.stdout)

    def test_public_api_persists_buddy_run_without_skill_id(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")

        payload = self._persist(context, _pm_commit())

        receipt = payload["receipt"]
        self.assertEqual(receipt["buddy_id"], "pm")
        self.assertIn("run_id", receipt)
        self.assertIn("artifact_ids", receipt)
        self.assertNotIn("skill_id", receipt)

        artifact = env_store.get_artifact(receipt["artifact_ids"][0])
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact["kind"], "prd")
        self.assertEqual(artifact["buddy"], "pm")
        self.assertEqual(artifact["source_run_id"], receipt["run_id"])
        self.assertNotIn("skill_id", artifact)
        self.assertNotIn("slot", artifact)

        run_audit = self._run_payload(receipt["run_id"])
        self.assertEqual(run_audit["buddy_id"], "pm")
        self.assertIn("contributors", run_audit)
        self.assertNotIn("skill_id", run_audit)

    def test_prepare_accepts_switch_prefixed_text_as_ordinary_request(self) -> None:
        request_text = "switch market: do competitor scan"

        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy="pm")):
            payload = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)

        self.assertTrue(payload["ok"], msg=payload)
        for required_key in (
            "active_buddy",
            "request_text",
            "current_task_id",
            "current_track_id",
            "run_envelope",
            "task_context",
            "warnings",
        ):
            self.assertIn(required_key, payload)
        self.assertEqual(payload["active_buddy"], "pm")
        self.assertEqual(payload["request_text"], request_text)

        run_envelope = payload["run_envelope"]
        self.assertEqual(run_envelope["status"], "reserved")
        self.assertEqual(run_envelope["turn_identity"]["active_buddy"], "pm")
        self.assertEqual(run_envelope["turn_identity"]["request_text"], request_text)
        self.assertEqual(run_envelope["turn_identity"]["instance_id"], "instance-test")

        reservations = self._runtime_state_snapshot()["reservations"]
        self.assertEqual(len(reservations), 1)
        reservation = next(iter(reservations.values()))
        self.assertEqual(reservation["run_id"], run_envelope["run_id"])
        self.assertEqual(reservation["status"], "reserved")
        self.assertEqual(reservation["turn_identity"]["active_buddy"], "pm")
        self.assertEqual(reservation["turn_identity"]["request_text"], request_text)

        turn_identity = run_envelope["turn_identity"]
        forbidden_router_fields = (
            "recommended" + "_switch",
            "reference_" + "switches",
            "selected_" + "skill",
            "selected_" + "skill_id",
            "selected_" + "skill_packet",
            "command_" + "grammar",
            "command_" + "name",
        )
        for field in forbidden_router_fields:
            self.assertNotIn(field, payload)
            self.assertNotIn(field, run_envelope)
            self.assertNotIn(field, turn_identity)

    def test_prepare_uses_locked_buddy_for_switch_prefixed_text(self) -> None:
        cases = (
            ("pm", "switch market: do competitor scan"),
            ("market", "switch dev: summarize positioning gaps"),
            ("dev", "switch pm: implement launcher cleanup"),
        )

        for session_buddy, request_text in cases:
            with self.subTest(session_buddy=session_buddy, request_text=request_text):
                before_count = len(self._runtime_state_snapshot()["reservations"])
                with patch.object(
                    turn_runtime,
                    "_load_product_mode_session",
                    return_value=self._session(buddy=session_buddy),
                ):
                    payload = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)

                self.assertTrue(payload["ok"], msg=payload)
                self.assertEqual(payload["active_buddy"], session_buddy)
                self.assertEqual(payload["request_text"], request_text)
                self.assertEqual(payload["run_envelope"]["turn_identity"]["active_buddy"], session_buddy)
                self.assertEqual(payload["run_envelope"]["turn_identity"]["request_text"], request_text)
                self.assertEqual(payload["run_envelope"]["turn_identity"]["instance_id"], "instance-test")
                self.assertEqual(len(self._runtime_state_snapshot()["reservations"]), before_count + 1)

    def test_prepare_rejects_task_track_binding_conflict_without_reservation(self) -> None:
        env_store.create_track(
            "track-existing",
            "Existing",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="existing",
        )
        env_store.create_task(
            "task-existing",
            "Existing PM Task",
            buddy="pm",
            track_id="track-existing",
            status="active",
            summary="",
            initial_run_id=None,
        )
        session = self._session(
            buddy="pm",
            payload={
                "current_task_id": "task-existing",
                "current_track_id": "track-other",
            },
        )
        with (
            patch.object(turn_runtime, "_load_product_mode_session", return_value=session),
            self.assertRaisesRegex(ValueError, "cannot switch to"),
        ):
            turn_runtime.prepare_turn_context(PM_REQUEST, manifest_path=MANIFEST)
        reserved = list(turn_runtime._reserved_run_path("placeholder").parent.glob("*.json"))  # type: ignore[attr-defined]
        self.assertEqual(reserved, [])

    def test_rejects_top_level_skill_id_before_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["skill_id"] = "write-prd"
        artifacts_before = [row["id"] for row in env_store.list_artifacts()]

        with self.assertRaisesRegex(ValueError, "skill_id"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        artifacts_after = [row["id"] for row in env_store.list_artifacts()]
        self.assertEqual(artifacts_after, artifacts_before)

    def test_rejects_invalid_artifact_kind_for_active_buddy_before_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["artifacts"][0]["kind"] = "market-scan"  # type: ignore[index]
        runs_before = [row["id"] for row in env_store.list_tasks()]

        with self.assertRaisesRegex(ValueError, "artifact kind"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        runs_after = [row["id"] for row in env_store.list_tasks()]
        self.assertEqual(runs_after, runs_before)

    def test_rejects_duplicate_artifact_kinds_atomically(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["artifacts"] = [
            invalid["artifacts"][0],  # type: ignore[index]
            {
                "kind": "prd",
                "title": "Duplicate kind",
                "content": {"note": "duplicate"},
            },
        ]
        artifacts_before = [row["id"] for row in env_store.list_artifacts()]

        with self.assertRaisesRegex(ValueError, "duplicate artifact kind"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        artifacts_after = [row["id"] for row in env_store.list_artifacts()]
        self.assertEqual(artifacts_after, artifacts_before)

    def test_persists_multiple_valid_artifacts_in_single_run(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        commit = _pm_commit()
        commit["artifacts"] = [
            commit["artifacts"][0],  # type: ignore[index]
            {
                "kind": "pm-decision",
                "title": "PM Decision Record",
                "summary": "Decision note for landing page sequencing.",
                "content": {"decision": "Market first, then design."},
            },
        ]

        payload = self._persist(context, commit)
        receipt = payload["receipt"]
        self.assertEqual(len(receipt["artifact_ids"]), 2)
        artifact_rows = [env_store.get_artifact(artifact_id) for artifact_id in receipt["artifact_ids"]]
        self.assertTrue(all(row is not None for row in artifact_rows))
        rows = [row for row in artifact_rows if isinstance(row, dict)]
        self.assertEqual({row["kind"] for row in rows}, {"prd", "pm-decision"})
        self.assertTrue(all(row["source_run_id"] == receipt["run_id"] for row in rows))

    def test_rejects_mixed_valid_and_invalid_artifact_list_atomically(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["artifacts"] = [
            invalid["artifacts"][0],  # type: ignore[index]
            {
                "kind": "market-scan",
                "title": "Wrong buddy kind",
                "content": {"note": "should fail"},
            },
        ]
        state_before = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "artifact kind"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_rejects_handoff_track_next_buddy_mismatch_before_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["handoff"]["next_buddy"] = "design"  # type: ignore[index]
        artifacts_before = [row["id"] for row in env_store.list_artifacts()]

        with self.assertRaisesRegex(ValueError, "must match"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        artifacts_after = [row["id"] for row in env_store.list_artifacts()]
        self.assertEqual(artifacts_after, artifacts_before)

    def test_supports_task_effect_status_and_summary(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")

        payload = self._persist(context, _pm_commit())

        receipt = payload["receipt"]
        task = env_store.get_task(receipt["task_id"])
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["status"], "done")
        self.assertIn("PM PRD", task["summary"])

    def test_second_run_on_same_task_includes_previous_run_in_related_run_ids(self) -> None:
        first_context = self._prepare(PM_REQUEST, buddy="pm")
        first = self._persist(first_context, _pm_commit())
        first_receipt = first["receipt"]

        second_context = self._prepare(
            "继续完善同一个PRD任务并更新结论",
            buddy="pm",
            payload={
                "current_task_id": first_receipt["task_id"],
                "current_track_id": first_receipt["track_id"],
            },
        )
        second_commit = {
            "execution_summary": "PM refined the PRD based on review feedback.",
            "artifacts": [
                {
                    "kind": "prd",
                    "title": "AI Schedule Tool Landing Page PRD v2",
                    "summary": "Refined scope and acceptance criteria.",
                    "content": {"problem": "Refined problem framing."},
                }
            ],
            "contributors": {"skills": ["write-prd"], "agents": []},
        }
        second = self._persist(second_context, second_commit)
        second_receipt = second["receipt"]
        self.assertIn(first_receipt["run_id"], second_receipt["related_run_ids"])

    def test_supports_track_update_advance_and_archive_actions(self) -> None:
        create_context = self._prepare(PM_REQUEST, buddy="pm")
        create_receipt = self._persist(create_context, _pm_commit())["receipt"]
        task_id = create_receipt["task_id"]
        track_id = create_receipt["track_id"]

        update_context = self._prepare(
            "更新track摘要",
            buddy="pm",
            payload={"current_task_id": task_id, "current_track_id": track_id},
        )
        update_commit = {
            "execution_summary": "PM updated track summary.",
            "state_effects": {
                "track": {
                    "action": "update",
                    "track_id": track_id,
                    "summary": "Updated summary for PM->Market flow.",
                }
            },
        }
        update_receipt = self._persist(update_context, update_commit)["receipt"]
        self.assertEqual(update_receipt["track_action"], "update")
        track = env_store.get_track(track_id)
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(track["summary"], "Updated summary for PM->Market flow.")

        advance_context = self._prepare(
            "推进到design",
            buddy="pm",
            payload={"current_task_id": task_id, "current_track_id": track_id},
        )
        advance_commit = {
            "execution_summary": "PM advanced track to design.",
            "state_effects": {
                "track": {
                    "action": "advance",
                    "track_id": track_id,
                    "next_buddy": "design",
                }
            },
        }
        advance_receipt = self._persist(advance_context, advance_commit)["receipt"]
        self.assertEqual(advance_receipt["track_action"], "advance")
        track = env_store.get_track(track_id)
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(track["next_buddy"], "design")

        archive_context = self._prepare(
            "归档track",
            buddy="pm",
            payload={"current_task_id": task_id, "current_track_id": track_id},
        )
        archive_commit = {
            "execution_summary": "PM archived completed track.",
            "state_effects": {"track": {"action": "archive", "track_id": track_id}},
        }
        archive_receipt = self._persist(archive_context, archive_commit)["receipt"]
        self.assertEqual(archive_receipt["track_action"], "archive")
        track = env_store.get_track(track_id)
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(track["status"], "archived")

    def test_rejects_unauthorized_track_action_before_writes(self) -> None:
        context = self._prepare("market request", buddy="market")
        invalid = {
            "execution_summary": "Market attempt",
            "state_effects": {
                "track": {
                    "action": "create",
                    "track_id": "track-market-illegal",
                    "title": "Illegal",
                    "status": "active",
                    "current_buddy": "market",
                }
            },
        }

        with self.assertRaisesRegex(ValueError, "not allowed"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

    def test_rejects_non_pm_track_lifecycle_actions_before_writes(self) -> None:
        cases = [
            (
                "design",
                "advance",
                {
                    "kind": "design-handoff",
                    "title": "Design Handoff",
                    "summary": "Design output.",
                    "content": {"design_goal": "ship a clear page"},
                },
            ),
            (
                "dev",
                "archive",
                {
                    "kind": "implementation-report",
                    "title": "Implementation Report",
                    "summary": "Dev output.",
                    "content": {"implementation_notes": ["changed source"]},
                },
            ),
            (
                "test",
                "update",
                {
                    "kind": "test-report",
                    "title": "Test Report",
                    "summary": "Test output.",
                    "content": {"checks_run": ["smoke"], "readiness": "ready-for-pm-review"},
                },
            ),
        ]
        for buddy, action, artifact in cases:
            with self.subTest(buddy=buddy, action=action):
                context = self._prepare(f"{buddy} request", buddy=buddy)
                invalid = {
                    "execution_summary": f"{buddy} attempted unauthorized track lifecycle mutation.",
                    "artifacts": [artifact],
                    "state_effects": {
                        "track": {
                            "action": action,
                            "track_id": f"track-{buddy}-illegal",
                            "title": f"{buddy} Illegal Track",
                            "status": "active",
                            "current_buddy": buddy,
                        }
                    },
                }
                state_before = self._runtime_state_snapshot()

                with self.assertRaisesRegex(ValueError, "not allowed"):
                    turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

                self._assert_runtime_state_unchanged(state_before, self._runtime_state_snapshot())

    def test_rejects_handoff_to_unknown_buddy_before_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["handoff"]["next_buddy"] = "unknown"  # type: ignore[index]
        artifacts_before = [row["id"] for row in env_store.list_artifacts()]

        with self.assertRaisesRegex(ValueError, "manifest buddy id"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        artifacts_after = [row["id"] for row in env_store.list_artifacts()]
        self.assertEqual(artifacts_after, artifacts_before)

    def test_rejects_handoff_with_empty_reason_before_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = _pm_commit()
        invalid["handoff"]["reason"] = " "  # type: ignore[index]
        artifacts_before = [row["id"] for row in env_store.list_artifacts()]

        with self.assertRaisesRegex(ValueError, "handoff.reason"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        artifacts_after = [row["id"] for row in env_store.list_artifacts()]
        self.assertEqual(artifacts_after, artifacts_before)

    def test_handoff_only_commit_is_valid_durable_signal(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        handoff_only = {
            "execution_summary": "PM requested market follow-up before adding artifacts.",
            "handoff": {
                "next_buddy": "market",
                "reason": "Need market positioning input before expanding scope.",
                "context": "Start from the current PM task context.",
            },
            "contributors": {"skills": ["track-manager"], "agents": []},
        }

        payload = self._persist(context, handoff_only)
        receipt = payload["receipt"]
        self.assertEqual(receipt["artifact_ids"], [])
        self.assertEqual(receipt["handoff"]["next_buddy"], "market")
        run_audit = self._run_payload(receipt["run_id"])
        self.assertEqual(run_audit["handoff"]["next_buddy"], "market")

    def test_rejects_valid_artifact_plus_invalid_track_effect_atomically(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = {
            "execution_summary": "PM attempted artifact + invalid track update.",
            "artifacts": [
                {
                    "kind": "prd",
                    "title": "AI Schedule Tool Landing Page PRD",
                    "content": {"problem": "Busy professionals need schedule help."},
                }
            ],
            "state_effects": {
                "track": {
                    "action": "update",
                    "track_id": "track-does-not-exist",
                    "summary": "should fail",
                }
            },
        }
        state_before = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "Track not found"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_product_mode_context_buddy_mismatch_fails_atomically(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        state_before = self._runtime_state_snapshot()

        exit_code, payload = self._persist_via_cmd(
            context=context,
            result=_pm_commit(),
            session_buddy="market",
        )

        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("buddy mismatch", payload["error"]["message"])
        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_product_mode_prepare_without_broker_returns_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "instance-test",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "",
            },
            clear=False,
        ):
            exit_code, payload = self._prepare_via_cmd(
                request_text=PM_REQUEST,
                session_buddy="pm",
                broker_mode="",
            )
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_RUNTIME_BROKER_UNAVAILABLE")

    def test_product_mode_prepare_routes_through_broker_payload(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "instance-test",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ):
            with patch.object(
                turn_runtime,
                "request_runtime_broker",
                return_value={"ok": True, "payload": {"ok": True, "prepared_context": True}},
            ) as broker_call:
                exit_code, payload = self._prepare_via_cmd(
                    request_text=PM_REQUEST,
                    session_buddy="pm",
                    broker_mode="",
                )
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["prepared_context"])
        self.assertNotIn("payload", payload)
        broker_call.assert_called_once_with("prepare", {"text": PM_REQUEST})

    def test_product_mode_persist_routes_through_broker_instead_of_direct_write(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "instance-test",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ):
            with (
                patch.object(
                    turn_runtime,
                    "request_runtime_broker",
                    return_value={"ok": True, "payload": {"ok": True, "delegated": True}},
                ) as broker_call,
                patch.object(turn_runtime, "persist_buddy_run", side_effect=AssertionError("direct path should not run")),
            ):
                exit_code, payload = self._persist_via_cmd(
                    context=context,
                    result=_pm_commit(),
                    session_buddy="pm",
                    broker_mode="",
                )
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["delegated"])
        self.assertNotIn("payload", payload)
        broker_call.assert_called_once()

    def test_contributor_skill_string_is_persisted_as_audit_metadata(self) -> None:
        context = self._prepare("实现并汇总开发结果", buddy="dev")
        commit = {
            "execution_summary": "Dev completed implementation and recorded contributor audit metadata.",
            "artifacts": [
                {
                    "kind": "implementation-report",
                    "title": "Implementation Report",
                    "summary": "Dev implementation summary.",
                    "content": {"result": "ok"},
                }
            ],
            "contributors": {
                "skills": ["dev-summary"],
                "agents": [],
            },
        }

        payload = self._persist(context, commit)
        receipt = payload["receipt"]
        run_audit = self._run_payload(receipt["run_id"])
        self.assertEqual(run_audit["contributors"]["skills"], ["dev-summary"])

    def test_contributor_skill_id_cannot_bypass_buddy_artifact_kinds(self) -> None:
        context = self._prepare("实现并汇总开发结果", buddy="dev")
        invalid = {
            "execution_summary": "Dev tried to persist imported skill id as artifact kind.",
            "artifacts": [
                {
                    "kind": "dev-summary",
                    "title": "Invalid Kind",
                    "content": {"result": "should fail"},
                }
            ],
            "contributors": {
                "skills": ["dev-summary"],
                "agents": [],
            },
        }
        state_before = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "artifact kind"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_run_id_is_single_use_and_replay_fails_without_new_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")

        first = self._persist(context, _pm_commit())
        first_receipt = first["receipt"]
        state_before_replay = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "already committed"):
            turn_runtime.persist_buddy_run(context, result=_pm_commit(), manifest_path=MANIFEST)

        state_after_replay = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before_replay, state_after_replay)

    def test_rejects_stale_context_revision_before_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        stale = copy.deepcopy(context)
        stale["context_revision"] = "ctx-stale"
        state_before = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "context_revision mismatch"):
            turn_runtime.persist_buddy_run(stale, result=_pm_commit(), manifest_path=MANIFEST)

        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_rejects_task_effect_with_explicit_foreign_task_id_atomically(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        other_task = env_store.create_task(
            "task-pm-other",
            "Other PM Task",
            buddy="pm",
            status="active",
            summary="",
            initial_run_id=None,
        )
        invalid = {
            "execution_summary": "PM tried to patch another task in task effect.",
            "state_effects": {
                "task": {
                    "task_id": other_task["id"],
                    "status": "done",
                }
            },
        }
        state_before = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "unsupported"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_rejects_track_create_that_would_rebind_existing_task_atomically(self) -> None:
        existing_track = env_store.create_track(
            "track-existing",
            "Existing Track",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="existing",
        )
        existing_task = env_store.create_task(
            "task-existing",
            "Existing PM Task",
            buddy="pm",
            track_id=existing_track["id"],
            status="active",
            summary="",
            initial_run_id=None,
        )
        context = self._prepare(
            "继续已有任务但尝试另建新track",
            buddy="pm",
            payload={"current_task_id": existing_task["id"]},
        )
        invalid = {
            "execution_summary": "PM attempted to create a new track for an already bound task.",
            "state_effects": {
                "track": {
                    "action": "create",
                    "title": "New Track Should Not Be Created",
                    "status": "active",
                    "current_buddy": "pm",
                    "summary": "should fail before any writes",
                }
            },
        }
        state_before = self._runtime_state_snapshot()

        with self.assertRaisesRegex(ValueError, "already bound"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)

        state_after = self._runtime_state_snapshot()
        self._assert_runtime_state_unchanged(state_before, state_after)

    def test_rejects_commit_without_durable_signal(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        invalid = {"execution_summary": "summary only"}

        with self.assertRaisesRegex(ValueError, "durable collaboration signal"):
            turn_runtime.persist_buddy_run(context, result=invalid, manifest_path=MANIFEST)


if __name__ == "__main__":
    unittest.main()
