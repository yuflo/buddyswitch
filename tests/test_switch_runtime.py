#!/usr/bin/env python3
"""Regression tests for BuddySwitch resolve/persist runtime."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import switch_runtime  # noqa: E402


class ManifestSkillRuntimeTests(unittest.TestCase):
    def test_output_schema_and_guidance_are_required(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            skill_path = Path(temp_dir) / "SKILL.md"
            skill_path.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: test-skill
                    description: Example test skill.
                    version: "2.0"
                    track_mode: optional
                    default_artifact_kind: note
                    auto_summary: true
                    output_schema: framework/schemas/dev/implement-task.json
                    side_effect_level: low
                    required_tools:
                      - rg
                    required_env:
                      - BUDDYSWITCH_TEST_ENV
                    produces:
                      - note
                    consumes:
                      - task
                    ---

                    # test-skill

                    ## Purpose
                    - Explain the workflow purpose.

                    ## Use when
                    - The task matches the workflow.

                    ## Do not use when
                    - The task belongs to another buddy.

                    ## Inputs
                    - Task input.

                    ## Outputs
                    - Structured result.

                    ## Verification
                    - Verify the result.

                    ## Examples
                    - `switch demo: run the task`

                    ## Counterexamples
                    - `switch other: do something else`

                    ## Gotchas
                    - Beware of drift.
                    """
                ),
                encoding="utf-8",
            )

            runtime = env_manifest._load_skill_runtime(skill_path, "test-skill")

        self.assertEqual(runtime["output_schema"], "framework/schemas/dev/implement-task.json")
        self.assertEqual(runtime["required_tools"], ["rg"])
        self.assertEqual(runtime["required_env"], ["BUDDYSWITCH_TEST_ENV"])
        self.assertIn("The task matches the workflow.", runtime["guidance"]["use_when"])


class ResolveRuntimeTests(unittest.TestCase):
    def test_single_skill_buddy_returns_implicit_skill(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["eligible_skills"], ["implement-task"])
        self.assertEqual(payload["implicit_skill_id"], "implement-task")
        self.assertEqual(
            payload["required_output_schema_by_skill"]["implement-task"],
            "framework/schemas/dev/implement-task.json",
        )

    def test_multi_skill_buddy_returns_candidates_without_auto_selection(self) -> None:
        def fake_track_context(task: str, track_mode: str, *, allow_missing_explicit: bool = False) -> dict[str, object]:
            if track_mode == "required":
                return {
                    "track_mode": track_mode,
                    "track_id": "track-demo",
                    "reason": "explicit",
                    "explicit_track_id": "track-demo",
                    "active_track_ids": ["track-demo"],
                }
            return {
                "track_mode": track_mode,
                "track_id": "track-demo",
                "reason": "explicit",
                "explicit_track_id": "track-demo",
                "active_track_ids": ["track-demo"],
            }

        with patch.object(switch_runtime, "_resolve_track_context", side_effect=fake_track_context):
            payload = switch_runtime.resolve_switch(
                "switch pm: continue track-demo track and define the MVP scope with acceptance criteria"
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["eligible_skills"], ["write-prd", "track-manager"])
        self.assertIsNone(payload["implicit_skill_id"])
        self.assertIn("write-prd", payload["artifact_defaults_by_skill"])
        self.assertNotIn("track-manager", payload["artifact_defaults_by_skill"])


class PersistRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(ROOT / repo_path)

    def _dev_resolved_payload(self, artifact_id: str) -> dict[str, object]:
        artifact_path = f"artifacts/{artifact_id}--test.md"
        summary_path = f"runs/summaries/dev/{artifact_id}.md"
        return {
            "ok": True,
            "switch": {"buddy": "dev", "task": "Implement the approved onboarding improvements in projects/app"},
            "eligible_skills": ["implement-task"],
            "implicit_skill_id": "implement-task",
            "artifact_defaults_by_skill": {
                "implement-task": {
                    "id": artifact_id,
                    "title": "DEV implement-task - test",
                    "kind": "implementation-report",
                    "path": artifact_path,
                    "summary_path": summary_path,
                }
            },
            "summary_defaults_by_skill": {"implement-task": {"enabled": True, "path": summary_path}},
            "track_context_by_skill": {
                "implement-task": {
                    "track_mode": "optional",
                    "track_id": None,
                    "reason": "none",
                    "explicit_track_id": None,
                    "active_track_ids": [],
                }
            },
        }

    def test_persist_rejects_invalid_skill_id(self) -> None:
        resolved = self._dev_resolved_payload(f"art-test-invalid-skill-{uuid.uuid4().hex[:6]}")
        result = {
            "execution_summary": "Implemented the requested change.",
            "working_notes": ["Kept the scope localized."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior."],
                "verification_runs": [{"command": "npm test", "result": "passed", "notes": None}],
                "known_limitations": ["No live browser check in this test."],
            },
        }

        with self.assertRaisesRegex(ValueError, "is not eligible"):
            switch_runtime.persist_switch(resolved, skill_id="write-prd", result=result)

    def test_persist_rejects_schema_invalid_payload(self) -> None:
        resolved = self._dev_resolved_payload(f"art-test-invalid-schema-{uuid.uuid4().hex[:6]}")
        result = {
            "execution_summary": "Implemented the requested change.",
            "working_notes": ["Kept the scope localized."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements."
            },
        }

        with self.assertRaisesRegex(ValueError, "schema validation"):
            switch_runtime.persist_switch(resolved, skill_id="implement-task", result=result)

    def test_persist_writes_structured_content_and_markdown(self) -> None:
        artifact_id = f"art-test-persist-{uuid.uuid4().hex[:6]}"
        resolved = self._dev_resolved_payload(artifact_id)
        result = {
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": ["Scoped the edits to onboarding CTA behavior."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "suggested_next_switch": "switch test: Run smoke checks for the onboarding improvements",
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
                "verification_runs": [{"command": "npm test", "result": "passed", "notes": "Targeted unit coverage."}],
                "known_limitations": ["No production build was executed in this unit test."],
            },
        }

        payload = switch_runtime.persist_switch(resolved, skill_id="implement-task", result=result)

        self.assertTrue(payload["ok"])
        artifact = payload["artifact"]
        summary_path = payload["summary"]["path"]
        run_content_path = payload["run"]["content_path"]

        self._remember(artifact["path"])
        self._remember(artifact["content_path"])
        self._remember(summary_path)
        self._remember(run_content_path)
        self._remember(f"buddyswitch/objects/artifacts/{artifact_id}.json")

        artifact_markdown = (ROOT / artifact["path"]).read_text(encoding="utf-8")
        artifact_json = (ROOT / artifact["content_path"]).read_text(encoding="utf-8")
        summary_markdown = (ROOT / summary_path).read_text(encoding="utf-8")

        self.assertIn("## task_summary", artifact_markdown)
        self.assertIn("Implemented onboarding improvements.", artifact_markdown)
        self.assertIn('"artifact_id":', artifact_json)
        self.assertIn("## execution_summary", summary_markdown)
        self.assertIn("switch test: Run smoke checks", summary_markdown)

    def test_track_manager_persist_creates_track(self) -> None:
        track_id = f"track-test-{uuid.uuid4().hex[:6]}"
        summary_path = f"runs/summaries/pm/{track_id}--track-manager.md"
        resolved = {
            "ok": True,
            "switch": {"buddy": "pm", "task": f"create {track_id} track"},
            "eligible_skills": ["track-manager"],
            "implicit_skill_id": "track-manager",
            "summary_defaults_by_skill": {"track-manager": {"enabled": True, "path": summary_path}},
            "task_hints": {
                "explicit_track_id": track_id,
                "explicit_artifact_id": None,
                "output_path": None,
                "summary_path": None,
                "action_hint": "create",
                "status_hint": None,
                "current_buddy_hint": None,
                "next_buddy_hint": None,
                "summary_hint": None,
            },
        }
        result = {
            "execution_summary": "Created the requested track.",
            "working_notes": ["Reserved PM as the initial owner."],
            "deliverables_or_changed_files": [f"buddyswitch/objects/tracks/{track_id}.json"],
            "track_operation": {
                "action": "create",
                "track_id": track_id,
                "title": "Track Test",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "design",
                "artifact_id": None,
                "summary": "Initial track creation."
            }
        }

        payload = switch_runtime.persist_switch(resolved, skill_id="track-manager", result=result)

        self.assertTrue(payload["ok"])
        self._remember(f"buddyswitch/objects/tracks/{track_id}.json")
        self._remember(payload["summary"]["path"])
        self._remember(payload["run"]["content_path"])

        track_json = (ROOT / f"buddyswitch/objects/tracks/{track_id}.json").read_text(encoding="utf-8")
        self.assertIn('"current_buddy": "pm"', track_json)
        self.assertIn('"next_buddy": "design"', track_json)


if __name__ == "__main__":
    unittest.main()
