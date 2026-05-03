#!/usr/bin/env python3
"""Integration red tests for turn-runtime product behavior."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_store.projections as workspace_projections  # noqa: E402
import workspace_data  # noqa: E402
from tests.test_turn_runtime import _load_turn_runtime  # noqa: E402


RUNTIME_WORKSPACE_HEADER = "# BuddySwitch Runtime Workspace\n"


def _relative_to_runtime_or_repo(path: Path) -> str:
    candidate = path.resolve()
    for base in (workspace_data.ROOT, ROOT):
        try:
            return candidate.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return candidate.as_posix()


class TurnRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self._tmp_dir.cleanup)
        self.runtime_root = Path(self._tmp_dir.name)
        (self.runtime_root / "AGENTS.md").write_text(
            RUNTIME_WORKSPACE_HEADER + "\nTest-only integration runtime workspace.\n",
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
        skill_id: str,
        env: dict[str, str],
        result: dict[str, object] | None = None,
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

    @staticmethod
    def _skill_ids(context: dict[str, object]) -> list[str]:
        skills = context.get("skills")
        if not isinstance(skills, list):
            return []
        ids: list[str] = []
        for card in skills:
            if isinstance(card, dict):
                skill_id = card.get("id")
                if isinstance(skill_id, str) and skill_id:
                    ids.append(skill_id)
        return ids

    def test_complete_turn_persists_single_skill_result(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-it-01", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-it-01", shared_root=self.runtime_root)

        context = self._prepare("Draft the MVP PRD for onboarding rewrite", env=env)
        self.assertTrue(context["ok"])
        self.assertIn("write-prd", self._skill_ids(context))

        persisted = self._persist(context, skill_id="write-prd", env=env)
        self.assertTrue(persisted["ok"])
        receipt = persisted["receipt"]
        self.assertEqual(receipt["run_id"], context["run_envelope"]["run_id"])

        task_path = self._runtime_path(receipt["receipt_paths"]["task"])
        run_path = self._runtime_path(receipt["receipt_paths"]["run"])
        self.assertTrue(task_path.exists())
        self.assertTrue(run_path.exists())

        task_payload = json.loads(task_path.read_text(encoding="utf-8"))
        run_payload = json.loads(run_path.read_text(encoding="utf-8"))
        self.assertIn(receipt["run_id"], task_payload.get("run_ids", []))
        self.assertEqual(run_payload.get("run_id"), receipt["run_id"])
        self.assertEqual(run_payload.get("skill_id"), "write-prd")

    def test_natural_language_switch_request_runs_full_prepare_persist_path(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-it-02", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-it-02", shared_root=self.runtime_root)

        context = self._prepare("Help users switch plans without losing draft data", env=env)
        self.assertTrue(context["ok"])
        self.assertEqual(context["request_text"], "Help users switch plans without losing draft data")

        persisted = self._persist(context, skill_id="write-prd", env=env)
        self.assertTrue(persisted["ok"])

        projection = workspace_projections.build_workspace_projection()
        self.assertTrue(projection["run_audits"])
        self.assertIn("next_state", projection["run_audits"][0])

    def test_legacy_command_shaped_input_has_no_side_effects_and_followup_ordinary_request_succeeds(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-it-03", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-it-03", shared_root=self.runtime_root)

        tasks_before = list(self._runtime_path("buddyswitch/objects/tasks").glob("*.json"))
        legacy_payload = self._prepare("switch dev: Draft onboarding PRD", env=env)
        self.assertFalse(legacy_payload.get("ok"))
        self.assertEqual(tasks_before, list(self._runtime_path("buddyswitch/objects/tasks").glob("*.json")))

        ordinary_payload = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(ordinary_payload["ok"])

    def test_product_prepare_and_persist_do_not_import_debug_parser_or_router_modules(self) -> None:
        import builtins

        instance_json = self._write_instance_json(instance_id="inst-it-04", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-it-04", shared_root=self.runtime_root)

        real_import = builtins.__import__

        def guarded_import(name: str, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
            blocked = (
                "parse_switch",
                "codex_router",
                "scripts.debug.parse_switch",
                "scripts.debug.codex_router",
            )
            if any(name == item or name.endswith(f".{item}") for item in blocked):
                raise AssertionError(f"debug dependency import blocked: {name}")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=guarded_import):
            context = self._prepare("Draft onboarding PRD", env=env)
            self.assertTrue(context["ok"])
            persisted = self._persist(context, skill_id="write-prd", env=env)
            self.assertTrue(persisted["ok"])

    def test_multi_skill_prepare_requires_exactly_one_selected_skill_for_persist(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-it-05", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-it-05", shared_root=self.runtime_root)

        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])
        skill_ids = self._skill_ids(context)
        self.assertGreaterEqual(len(skill_ids), 2)

        try:
            invalid = self._persist(context, skill_id="", env=env)
        except Exception:
            invalid_ok = False
        else:
            invalid_ok = bool(invalid.get("ok"))
        self.assertFalse(invalid_ok)

        persisted = self._persist(context, skill_id="write-prd", env=env)
        self.assertTrue(persisted["ok"])

    def test_source_checkout_remains_clean_while_runtime_state_writes_stay_in_instance_workspace(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-it-06", buddy="pm")
        env = self._product_env(instance_json, buddy="pm", instance_id="inst-it-06", shared_root=self.runtime_root)

        context = self._prepare("Draft onboarding PRD", env=env)
        self.assertTrue(context["ok"])
        persisted = self._persist(context, skill_id="write-prd", env=env)
        self.assertTrue(persisted["ok"])

        receipt = persisted["receipt"]
        run_rel_path = receipt["receipt_paths"]["run"]
        runtime_run_path = self._runtime_path(run_rel_path)
        source_run_path = ROOT / run_rel_path
        self.assertTrue(runtime_run_path.exists())
        self.assertFalse(source_run_path.exists())


if __name__ == "__main__":
    unittest.main()
