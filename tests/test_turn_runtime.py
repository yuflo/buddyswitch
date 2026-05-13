#!/usr/bin/env python3
"""Buddy-run persistence behavior tests for task-management skill architecture."""

from __future__ import annotations

import argparse
import contextlib
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


class TurnRuntimeBuddyRunTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": "instance-test",
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _prepare(self, request_text: str, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy=buddy, payload=payload)):
            prepared = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(prepared["ok"], msg=prepared)
        self.assertIsInstance(prepared.get("run_envelope"), dict)
        return prepared

    def _persist(self, context: dict[str, object], result: dict[str, object]) -> dict[str, object]:
        payload = turn_runtime.persist_buddy_run(context, result=result, manifest_path=MANIFEST)
        self.assertTrue(payload["ok"], msg=payload)
        return payload

    def _persist_via_cmd(
        self,
        *,
        context: dict[str, object],
        result: dict[str, object],
        session_buddy: str,
    ) -> tuple[int, dict[str, object]]:
        raw_dir = self._runtime_path("runs/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
        context_path = raw_dir / "persist-context.json"
        result_path = raw_dir / "persist-result.json"
        context_path.write_text(json.dumps(context, ensure_ascii=True), encoding="utf-8")
        result_path.write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")
        args = argparse.Namespace(context=str(context_path), result=str(result_path), manifest=MANIFEST)
        session = self._session(buddy=session_buddy, payload={})
        stdout = io.StringIO()
        with (
            patch.object(turn_runtime, "_load_product_mode_session", return_value=session),
            patch.object(turn_runtime, "_hold_product_runtime_lock", side_effect=lambda _: contextlib.nullcontext()),
            patch.dict(os.environ, {"BUDDYSWITCH_RUNTIME_BROKER_MODE": "server"}, clear=False),
            patch("sys.stdout", new=stdout),
        ):
            exit_code = turn_runtime._cmd_persist(args)
        return exit_code, json.loads(stdout.getvalue())

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

    def test_prepare_accepts_switch_prefixed_text_as_ordinary_request(self) -> None:
        payload = self._prepare("switch market: do competitor scan", buddy="pm")
        self.assertIsNone(payload.get("current_task_id"))
        self.assertIsNone(payload.get("task_context"))
        tasks_dir = self._runtime_path("buddyswitch/objects/tasks")
        rows = sorted(path.name for path in tasks_dir.glob("*.json")) if tasks_dir.exists() else []
        self.assertEqual(rows, [])
        run_id = payload["run_envelope"]["run_id"]
        reservation_path = self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json")
        reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
        self.assertIsNone(reservation.get("task_id"))

    def test_public_api_persists_buddy_run_without_skill_id(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        payload = self._persist(context, {"execution_summary": "PM recorded a taskless audit run."})
        receipt = payload["receipt"]
        self.assertEqual(receipt["buddy_id"], "pm")
        self.assertIn("run_id", receipt)
        self.assertNotIn("skill_id", receipt)
        self.assertNotIn("task_id", receipt)
        run_id = receipt["run_id"]
        run_payload = json.loads(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(run_payload["writes"], [f"buddyswitch/content/runs/{run_id}.json"])
        self.assertNotIn("skill_id", run_payload)

    def test_persist_rejects_state_effects_with_structured_boundary(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        exit_code, payload = self._persist_via_cmd(
            context=context,
            result={
                "execution_summary": "legacy host payload",
                "state_effects": {"task": {"status": "done"}},
            },
            session_buddy="pm",
        )
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["permission_boundary"], "persist.state_effects")
        self.assertIn("allowed_next_actions", payload)

    def test_persist_rejects_embedded_artifacts_with_structured_boundary(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        exit_code, payload = self._persist_via_cmd(
            context=context,
            result={
                "execution_summary": "legacy host payload",
                "artifacts": [{"kind": "prd", "title": "x", "content": {"a": 1}}],
            },
            session_buddy="pm",
        )
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["permission_boundary"], "persist.artifacts")

    def test_run_id_is_single_use_and_replay_fails_without_new_writes(self) -> None:
        context = self._prepare(PM_REQUEST, buddy="pm")
        first = self._persist(context, {"execution_summary": "first persist"})
        run_id = first["receipt"]["run_id"]
        before = json.loads(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "persist conflict for run_id"):
            turn_runtime.persist_buddy_run(context, result={"execution_summary": "replay"}, manifest_path=MANIFEST)
        after = json.loads(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(after, before)

    def test_persist_allows_optional_task_track_artifact_associations(self) -> None:
        task = env_store.create_task(
            "task-pm-associated",
            "Associated Task",
            buddy="pm",
            track_id=None,
            status="active",
            summary="",
            initial_run_id=None,
        )
        track = env_store.create_track(
            "track-associated",
            "Associated Track",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="",
        )
        env_store.register_task_to_track(track["id"], task["id"])
        context = self._prepare("关联元数据提交", buddy="pm", payload={"current_task_id": task["id"], "current_track_id": track["id"]})
        payload = self._persist(
            context,
            {
                "execution_summary": "associated audit",
                "task_id": task["id"],
                "track_id": track["id"],
                "artifact_ids": [],
            },
        )
        receipt = payload["receipt"]
        self.assertEqual(receipt["task_id"], task["id"])
        self.assertEqual(receipt["track_id"], track["id"])
        self.assertEqual(receipt["next_state"]["mode"], "task_associated")


if __name__ == "__main__":
    unittest.main()
