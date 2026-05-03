#!/usr/bin/env python3
"""Red tests for turn-oriented BuddySwitch runtime behavior."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_store.projections as workspace_projections  # noqa: E402
import workspace_data  # noqa: E402


RUNTIME_WORKSPACE_HEADER = "# BuddySwitch Runtime Workspace\n"


def _load_turn_runtime():
    try:
        return importlib.import_module("turn_runtime")
    except ModuleNotFoundError as exc:
        raise AssertionError(
            "scripts/turn_runtime.py is required for turn-runtime tests"
        ) from exc


def _relative_to_runtime_or_repo(path: Path) -> str:
    candidate = path.resolve()
    for base in (workspace_data.ROOT, ROOT):
        try:
            return candidate.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return candidate.as_posix()


class TurnRuntimeWorkspaceTestMixin:
    def setUp(self) -> None:
        super().setUp()
        self._tmp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self._tmp_dir.cleanup)
        self.runtime_root = Path(self._tmp_dir.name)
        (self.runtime_root / "AGENTS.md").write_text(
            RUNTIME_WORKSPACE_HEADER + "\nTest-only runtime workspace.\n",
            encoding="utf-8",
        )

        objects_root = self.runtime_root / "buddyswitch" / "objects"
        content_root = self.runtime_root / "buddyswitch" / "content"

        self._patchers = [
            patch.object(env_store, "ROOT", self.runtime_root),
            patch.object(env_store, "OBJECTS_ROOT", objects_root),
            patch.object(env_store, "TRACKS_DIR", objects_root / "tracks"),
            patch.object(env_store, "TASKS_DIR", objects_root / "tasks"),
            patch.object(env_store, "ARTIFACT_OBJECTS_DIR", objects_root / "artifacts"),
            patch.object(env_store, "CONTENT_ROOT", content_root),
            patch.object(env_store, "RUN_CONTENT_DIR", content_root / "runs"),
            patch.object(workspace_data, "ROOT", self.runtime_root),
            patch.object(workspace_data, "rel", _relative_to_runtime_or_repo),
        ]
        for patcher in self._patchers:
            patcher.start()
        self.addCleanup(self._stop_patchers)

    def _stop_patchers(self) -> None:
        for patcher in reversed(self._patchers):
            patcher.stop()

    def _runtime_path(self, repo_relative_path: str) -> Path:
        return self.runtime_root / repo_relative_path


class TurnRuntimeBehaviorTests(TurnRuntimeWorkspaceTestMixin, unittest.TestCase):
    def _write_instance_json(
        self,
        *,
        instance_id: str,
        buddy: str,
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        instance_root = self.runtime_root / "instances" / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_payload = {
            "instance_id": instance_id,
            "buddy": buddy,
            "status": "active",
            "current_task_id": current_task_id,
            "current_track_id": current_track_id,
            "workspace_dir": str(instance_root / "workspace"),
            "created_at": "2026-05-02T00:00:00Z",
            "updated_at": "2026-05-02T00:00:00Z",
        }
        instance_json.write_text(json.dumps(instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return instance_json

    @staticmethod
    def _product_env(instance_json: Path, *, buddy: str, instance_id: str, shared_root: Path) -> dict[str, str]:
        return {
            "BUDDYSWITCH_ACTIVE_BUDDY": buddy,
            "BUDDYSWITCH_INSTANCE_ID": instance_id,
            "BUDDYSWITCH_INSTANCE_JSON": str(instance_json),
            "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        }

    @staticmethod
    def _pm_result_payload() -> dict[str, object]:
        return {
            "execution_summary": "Captured onboarding PRD updates.",
            "working_notes": ["Focused on scope and acceptance criteria."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "problem": "Users need clearer onboarding scope.",
                "goals": ["Clarify outcomes", "Preserve current flows"],
                "non_goals": ["Implement delivery code"],
                "users_and_scenarios": ["PM iterates on onboarding PRD"],
                "scope_p0_p1": {
                    "p0": ["Define launch acceptance criteria"],
                    "p1": ["Capture follow-up questions"],
                },
                "acceptance_criteria": ["PRD payload validates and persists"],
                "risks": ["Unknown migration edge cases"],
                "open_questions": ["Need follow-up QA pass?"],
            },
        }

    def _prepare(self, request_text: str, *, env: dict[str, str]) -> dict[str, object]:
        turn_runtime = _load_turn_runtime()
        with patch.dict(os.environ, env, clear=True):
            return turn_runtime.prepare_turn_context(
                request_text,
                manifest_path=turn_runtime.DEFAULT_MANIFEST,
            )

    def _persist(
        self,
        context: dict[str, object],
        *,
        skill_id: object,
        result: dict[str, object] | None = None,
        env: dict[str, str],
    ) -> dict[str, object]:
        turn_runtime = _load_turn_runtime()
        payload = result or self._pm_result_payload()
        with patch.dict(os.environ, env, clear=True):
            return turn_runtime.persist_skill_result(
                context,
                skill_id=skill_id,
                result=payload,
                manifest_path=turn_runtime.DEFAULT_MANIFEST,
            )

    def _runtime_state_counts(self) -> dict[str, int]:
        return {
            "tasks": len(list(self._runtime_path("buddyswitch/objects/tasks").glob("*.json"))),
            "tracks": len(list(self._runtime_path("buddyswitch/objects/tracks").glob("*.json"))),
            "artifacts": len(list(self._runtime_path("buddyswitch/objects/artifacts").glob("*.json"))),
            "runs": len(list(self._runtime_path("buddyswitch/content/runs").glob("run-*.json"))),
            "reservations": len(list(self._runtime_path("buddyswitch/content/runs/reserved").glob("*.json"))),
        }

    @staticmethod
    def _skill_ids(context: dict[str, object]) -> list[str]:
        skills = context.get("skills")
        if not isinstance(skills, list):
            return []
        result: list[str] = []
        for card in skills:
            if isinstance(card, dict):
                skill_id = card.get("id")
                if isinstance(skill_id, str) and skill_id:
                    result.append(skill_id)
        return result

    def _assert_prepare_rejected_without_writes(self, request_text: str, *, env: dict[str, str], instance_json: Path) -> None:
        counts_before = self._runtime_state_counts()
        instance_before = instance_json.read_text(encoding="utf-8")

        payload = self._prepare(request_text, env=env)

        self.assertFalse(payload.get("ok"), msg=f"legacy command-shaped input should fail closed: {request_text}")
        error_payload = payload.get("error")
        self.assertIsInstance(error_payload, dict)
        if isinstance(error_payload, dict):
            self.assertIn("ordinary request", json.dumps(error_payload).lower())

        self.assertEqual(self._runtime_state_counts(), counts_before)
        self.assertEqual(instance_json.read_text(encoding="utf-8"), instance_before)

    def _assert_persist_rejected_without_writes(
        self,
        context: dict[str, object],
        *,
        skill_id: object,
        env: dict[str, str],
    ) -> None:
        counts_before = self._runtime_state_counts()
        try:
            payload = self._persist(context, skill_id=skill_id, env=env)
        except Exception:
            rejected = True
        else:
            rejected = not bool(payload.get("ok"))
        self.assertTrue(rejected, msg="persist input should be rejected")
        self.assertEqual(self._runtime_state_counts(), counts_before)

    def test_prepare_turn_context_accepts_ordinary_request_and_creates_reserved_run(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-01", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-01", shared_root=self.runtime_root)

        payload = self._prepare("Draft the MVP PRD for onboarding rewrite", env=env)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["active_buddy"], "pm")
        self.assertEqual(payload["request_text"], "Draft the MVP PRD for onboarding rewrite")
        self.assertIsInstance(payload.get("current_task_id"), str)
        run_envelope = payload.get("run_envelope")
        self.assertIsInstance(run_envelope, dict)
        if isinstance(run_envelope, dict):
            self.assertEqual(run_envelope.get("status"), "reserved")
            self.assertIsInstance(run_envelope.get("run_id"), str)

        task_path = self._runtime_path(f"buddyswitch/objects/tasks/{payload['current_task_id']}.json")
        self.assertTrue(task_path.exists())
        reserved_dir = self._runtime_path("buddyswitch/content/runs/reserved")
        self.assertTrue(any(reserved_dir.glob("*.json")))

    def test_prepare_turn_context_reuses_existing_instance_binding(self) -> None:
        existing_track_id = "track-existing-binding"
        existing_task_id = "task-existing-binding"
        env_store.create_track(existing_track_id, "Existing onboarding track", current_buddy="pm")
        env_store.create_task(existing_task_id, "Existing onboarding task", buddy="pm", track_id=existing_track_id)
        env_store.register_task_to_track(existing_track_id, existing_task_id)

        instance_json = self._write_instance_json(
            instance_id="inst-ut-02",
            buddy="pm",
            current_task_id=existing_task_id,
            current_track_id=existing_track_id,
        )
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-02", shared_root=self.runtime_root)

        payload = self._prepare("Continue the onboarding PRD", env=env)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["current_task_id"], existing_task_id)
        self.assertEqual(payload["current_track_id"], existing_track_id)
        self.assertEqual(len(list(self._runtime_path("buddyswitch/objects/tasks").glob("*.json"))), 1)

    def test_locked_buddy_stays_bound_to_instance_scope(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-03", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-03", shared_root=self.runtime_root)

        context = self._prepare("Ask dev later to implement this after PRD approval", env=env)

        self.assertTrue(context["ok"])
        self.assertEqual(context["active_buddy"], "pm")
        self.assertFalse(list(self._runtime_path("buddyswitch/objects/tasks").glob("task-dev-*.json")))

        self._assert_persist_rejected_without_writes(context, skill_id="implement-task", env=env)

    def test_command_shaped_legacy_input_is_rejected_before_any_writes(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-04", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-04", shared_root=self.runtime_root)

        self._assert_prepare_rejected_without_writes("switch pm: Draft the PRD", env=env, instance_json=instance_json)
        self._assert_prepare_rejected_without_writes("switch dev: Implement the PRD", env=env, instance_json=instance_json)
        self._assert_prepare_rejected_without_writes(
            "switch dev(task-a) -> track-a: Implement the PRD",
            env=env,
            instance_json=instance_json,
        )

    def test_natural_language_switch_word_is_accepted(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-05", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-05", shared_root=self.runtime_root)

        payload = self._prepare("Help users switch plans without losing draft data", env=env)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["request_text"], "Help users switch plans without losing draft data")
        self.assertTrue(any(self._runtime_path("buddyswitch/content/runs/reserved").glob("*.json")))

    def test_prepare_turn_context_has_no_debug_parser_or_router_dependency(self) -> None:
        turn_runtime = _load_turn_runtime()
        source = (ROOT / "scripts" / "turn_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("parse_switch", source)
        self.assertNotIn("codex_router", source)

        instance_json = self._write_instance_json(instance_id="inst-ut-06", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-06", shared_root=self.runtime_root)
        payload = self._prepare("Draft onboarding PRD", env=env)

        self.assertTrue(payload["ok"])
        self.assertTrue(hasattr(turn_runtime, "prepare_turn_context"))

    def test_persist_accepts_exactly_one_skill_from_current_context(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-07", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-07", shared_root=self.runtime_root)

        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])
        skill_ids = self._skill_ids(context)
        self.assertTrue(skill_ids)

        self._assert_persist_rejected_without_writes(context, skill_id="", env=env)
        self._assert_persist_rejected_without_writes(context, skill_id=[skill_ids[0]], env=env)
        self._assert_persist_rejected_without_writes(context, skill_id="not-in-context", env=env)

        payload = self._persist(context, skill_id=skill_ids[0], env=env)
        self.assertTrue(payload["ok"])

    def test_persist_rejects_tampered_context_identity_without_writes(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-08", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-08", shared_root=self.runtime_root)
        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])
        skill_ids = self._skill_ids(context)
        self.assertTrue(skill_ids)

        tamper_cases = []

        buddy_tampered = deepcopy(context)
        buddy_tampered["active_buddy"] = "dev"
        tamper_cases.append(buddy_tampered)

        task_tampered = deepcopy(context)
        task_tampered["current_task_id"] = "task-tampered"
        tamper_cases.append(task_tampered)

        run_tampered = deepcopy(context)
        if isinstance(run_tampered.get("run_envelope"), dict):
            run_tampered["run_envelope"] = dict(run_tampered["run_envelope"])
            run_tampered["run_envelope"]["run_id"] = "run-tampered"
        tamper_cases.append(run_tampered)

        request_tampered = deepcopy(context)
        request_tampered["request_text"] = "Tampered request"
        tamper_cases.append(request_tampered)

        for tampered in tamper_cases:
            with self.subTest(tamper=tampered.get("request_text", "case")):
                self._assert_persist_rejected_without_writes(tampered, skill_id=skill_ids[0], env=env)

    def test_successful_persist_returns_structured_receipt_contract(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-09", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-09", shared_root=self.runtime_root)
        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])
        skill_ids = self._skill_ids(context)
        self.assertIn("write-prd", skill_ids)

        payload = self._persist(context, skill_id="write-prd", env=env)

        self.assertTrue(payload["ok"])
        self.assertIn("receipt", payload)
        self.assertIn("refreshed_context", payload)
        receipt = payload["receipt"]
        self.assertIsInstance(receipt, dict)
        if isinstance(receipt, dict):
            for key in (
                "ok",
                "skill_id",
                "task_id",
                "task_title",
                "artifact_id",
                "artifact_ids",
                "run_id",
                "next_state",
                "receipt_paths",
                "related_run_ids",
            ):
                self.assertIn(key, receipt)
            self.assertEqual(receipt["run_id"], context["run_envelope"]["run_id"])
            self.assertIn(receipt["artifact_id"], receipt["artifact_ids"])
            self.assertEqual(receipt["next_state"]["task_id"], receipt["task_id"])
            self.assertNotIn("recommended_switch", receipt)
            self.assertNotIn("reference_switches", receipt)
            receipt_paths = receipt.get("receipt_paths")
            self.assertIsInstance(receipt_paths, dict)
            if isinstance(receipt_paths, dict):
                for rel_path in receipt_paths.values():
                    if isinstance(rel_path, str):
                        self.assertTrue(self._runtime_path(rel_path).exists())
                    elif isinstance(rel_path, list):
                        for item in rel_path:
                            if isinstance(item, str):
                                self.assertTrue(self._runtime_path(item).exists())

    def test_track_manager_persist_receipt_uses_empty_artifact_ids(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-09-track", buddy="pm")
        env = self._product_env(
            instance_json,
            buddy="pm",
            instance_id="inst-ut-09-track",
            shared_root=self.runtime_root,
        )
        context = self._prepare("Create onboarding delivery track", env=env)
        self.assertTrue(context["ok"])

        payload = self._persist(
            context,
            skill_id="track-manager",
            result={
                "execution_summary": "Created onboarding track.",
                "working_notes": ["Initialized track manager flow."],
                "deliverables_or_changed_files": [],
                "track_operation": {
                    "action": "create",
                    "track_id": "track-onboarding-delivery",
                    "title": "Onboarding Delivery",
                    "status": "active",
                    "current_buddy": "pm",
                    "next_buddy": "design",
                    "summary": "Cross-functional onboarding delivery flow.",
                },
            },
            env=env,
        )

        self.assertTrue(payload["ok"])
        receipt = payload["receipt"]
        self.assertIsInstance(receipt, dict)
        if isinstance(receipt, dict):
            self.assertEqual(receipt.get("track_action"), "create")
            self.assertEqual(receipt.get("artifact_ids"), [])
            self.assertNotIn("artifact_id", receipt)
            self.assertIsInstance(receipt.get("track_id"), str)
            self.assertIsInstance(receipt.get("track_title"), str)

    def test_persist_rejects_top_level_runtime_metadata_in_skill_payload(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-09-boundary", buddy="pm")
        env = self._product_env(
            instance_json,
            buddy="pm",
            instance_id="inst-ut-09-boundary",
            shared_root=self.runtime_root,
        )
        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])

        counts_before = self._runtime_state_counts()
        invalid_result = self._pm_result_payload()
        invalid_result["task_id"] = "task-should-not-be-accepted"
        with self.assertRaises(ValueError):
            self._persist(context, skill_id="write-prd", result=invalid_result, env=env)
        self.assertEqual(self._runtime_state_counts(), counts_before)

        valid_result = self._pm_result_payload()
        payload = self._persist(context, skill_id="write-prd", result=valid_result, env=env)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["receipt"]["task_id"], context["current_task_id"])

    def test_workspace_projection_uses_structured_state_after_persist(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-10", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-10", shared_root=self.runtime_root)
        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])

        persisted = self._persist(context, skill_id="write-prd", env=env)
        self.assertTrue(persisted["ok"])

        projection = workspace_projections.build_workspace_projection()
        self.assertTrue(projection["tasks"])
        self.assertTrue(projection["artifacts"])
        self.assertTrue(projection["run_audits"])

        run_row = projection["run_audits"][0]
        self.assertIn("next_state", run_row)
        self.assertIn("receipt_paths", run_row)
        self.assertNotIn("recommended_switch", json.dumps(run_row))
        self.assertNotIn("reference_switches", json.dumps(run_row))

    def test_runtime_state_writes_stay_in_runtime_workspace_not_source_checkout(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-ut-11", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-ut-11", shared_root=self.runtime_root)
        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])

        persisted = self._persist(context, skill_id="write-prd", env=env)
        self.assertTrue(persisted["ok"])
        receipt = persisted["receipt"]
        self.assertIsInstance(receipt, dict)
        assert isinstance(receipt, dict)

        run_path = self._runtime_path(receipt["receipt_paths"]["run"])
        self.assertTrue(run_path.exists())

        source_run_path = ROOT / receipt["receipt_paths"]["run"]
        self.assertFalse(source_run_path.exists())


if __name__ == "__main__":
    unittest.main()
