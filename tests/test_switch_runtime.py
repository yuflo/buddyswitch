#!/usr/bin/env python3
"""Regression tests for task-centric BuddySwitch resolve/persist runtime."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import switch_runtime  # noqa: E402
import workspace_data  # noqa: E402
from env_store import create_task, create_track, get_track, validate_artifact, validate_track  # noqa: E402


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
                      - demand
                    ---

                    # test-skill

                    ## Purpose
                    - Explain the workflow purpose.

                    ## Use when
                    - The demand matches the workflow.

                    ## Do not use when
                    - The demand belongs to another buddy.

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
        self.assertIn("The demand matches the workflow.", runtime["guidance"]["use_when"])

    def test_track_mode_front_matter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            skill_path = Path(temp_dir) / "SKILL.md"
            skill_path.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: test-skill
                    description: Example test skill.
                    track_mode: optional
                    default_artifact_kind: note
                    auto_summary: true
                    output_schema: framework/schemas/dev/implement-task.json
                    ---

                    # test-skill

                    ## Purpose
                    - Explain the workflow purpose.

                    ## Use when
                    - The demand matches the workflow.

                    ## Do not use when
                    - The demand belongs to another buddy.

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

            with self.assertRaisesRegex(env_manifest.ManifestError, "track_mode is retired"):
                env_manifest._load_skill_runtime(skill_path, "test-skill")


class EnvStoreRetiredFieldTests(unittest.TestCase):
    def test_validate_track_rejects_legacy_artifact_ids_field(self) -> None:
        payload = {
            "id": "track-legacy-field",
            "title": "Legacy Field Track",
            "status": "active",
            "current_buddy": "pm",
            "next_buddy": None,
            "task_ids": [],
            "artifact_ids": ["art-old-link"],
            "summary": "",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        with self.assertRaisesRegex(ValueError, "track.artifact_ids is retired"):
            validate_track(payload)

    def test_validate_artifact_rejects_legacy_track_id_field(self) -> None:
        payload = {
            "id": "art-legacy-field",
            "title": "Legacy Artifact",
            "task_id": "task-dev-legacy",
            "track_id": "track-legacy-field",
            "buddy": "dev",
            "skill_id": "implement-task",
            "source_run_id": "run-legacy-field",
            "summary": "",
            "content": {},
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        with self.assertRaisesRegex(ValueError, "artifact.track_id is retired"):
            validate_artifact(payload)


class ResolveRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(ROOT / repo_path)

    def test_single_skill_buddy_returns_implicit_skill(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["invocation"]["buddy"], "dev")
        self.assertEqual(payload["switch"]["demand"], "Implement the approved onboarding improvements in projects/app")
        self.assertEqual(payload["task_resolution"]["mode"], "create")
        self.assertTrue(payload["task_resolution"]["task_id"].startswith("task-dev-"))
        self.assertIsNone(payload["effective_track_id"])
        self.assertEqual(payload["eligible_skills"], ["implement-task"])
        self.assertEqual(payload["implicit_skill_id"], "implement-task")

    def test_resolve_reuses_explicit_task(self) -> None:
        task = create_task(
            "task-dev-resolve-reuse",
            "Resolve Reuse",
            buddy="dev",
            initial_run_id="run-seed-reuse",
        )
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        payload = switch_runtime.resolve_switch("switch dev(task-dev-resolve-reuse): continue implementation")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_resolution"]["mode"], "reuse")
        self.assertEqual(payload["task_resolution"]["task_id"], "task-dev-resolve-reuse")
        self.assertEqual(payload["task_context"]["task"]["id"], "task-dev-resolve-reuse")

    def test_resolve_rejects_task_buddy_mismatch(self) -> None:
        task = create_task(
            "task-market-forbidden",
            "Market task",
            buddy="market",
            initial_run_id="run-seed-market",
        )
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        with self.assertRaisesRegex(ValueError, "belongs to buddy"):
            switch_runtime.resolve_switch("switch dev(task-market-forbidden): continue implementation")

    def test_resolve_rejects_legacy_markdown_output_requests(self) -> None:
        with self.assertRaisesRegex(ValueError, "Derived markdown outputs are retired"):
            switch_runtime.resolve_switch(
                "switch dev: Implement onboarding and write to artifacts/demo.md"
            )


class WorkspaceDataTests(unittest.TestCase):
    def test_artifact_view_uses_object_path_only(self) -> None:
        artifact = {
            "id": "art-task-centric",
            "title": "Task-Centric Artifact",
            "task_id": "task-dev-one",
            "buddy": "dev",
            "skill_id": "implement-task",
            "source_run_id": "run-test",
            "summary": "Canonical summary",
            "content": {"task_summary": "ok"},
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        view = workspace_data.build_artifact_view(artifact)
        self.assertFalse(view["missing"])
        self.assertEqual(view["object_path"], "buddyswitch/objects/artifacts/art-task-centric.json")


class PersistRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(ROOT / repo_path)

    def _remember_persisted_paths(self, payload: dict[str, object]) -> None:
        paths = payload.get("paths", {})
        if not isinstance(paths, dict):
            return
        run_path = paths.get("run")
        task_path = paths.get("task")
        artifact_paths = paths.get("artifacts")
        track_path = paths.get("track")
        if isinstance(run_path, str):
            self._remember(run_path)
        if isinstance(task_path, str):
            self._remember(task_path)
        if isinstance(track_path, str):
            self._remember(track_path)
        if isinstance(artifact_paths, list):
            for item in artifact_paths:
                if isinstance(item, str):
                    self._remember(item)

    def _artifact_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": ["Scoped the edits to onboarding CTA behavior."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "suggested_next_switch": "switch test: Run smoke checks for the onboarding improvements",
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
                "verification_runs": [{"command": "npm test", "result": "passed", "notes": "Targeted unit coverage."}],
                "known_limitations": ["No production build was executed in this test."],
            },
        }

    def test_persist_creates_task_and_run_bound_artifact(self) -> None:
        resolved = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
        payload = switch_runtime.persist_switch(resolved, skill_id=None, result=self._artifact_result())

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "implement-task")
        self.assertEqual(payload["task_id"], resolved["task_resolution"]["task_id"])
        self.assertEqual(payload["artifact_ids"], [payload["artifact_id"]])
        self._remember_persisted_paths(payload)

        artifact_json = json.loads((ROOT / payload["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
        task_json = json.loads((ROOT / payload["paths"]["task"]).read_text(encoding="utf-8"))
        run_json = json.loads((ROOT / payload["paths"]["run"]).read_text(encoding="utf-8"))

        self.assertEqual(artifact_json["task_id"], payload["task_id"])
        self.assertEqual(artifact_json["source_run_id"], payload["run_id"])
        self.assertIn(payload["run_id"], task_json["run_ids"])
        self.assertEqual(task_json["latest_artifact_id"], payload["artifact_id"])
        self.assertEqual(run_json["resolved_task_id"], payload["task_id"])
        self.assertEqual(run_json["artifact_ids"], [payload["artifact_id"]])
        self.assertEqual(run_json["switch"]["demand"], resolved["switch"]["demand"])
        self.assertNotIn("artifact_content", run_json)

    def test_persist_reuses_task_and_binds_to_track(self) -> None:
        track = create_track("track-dev-binding", "Track Binding")
        task = create_task("task-dev-binding", "Task Binding", buddy="dev", initial_run_id="run-seed-binding")
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        resolved = switch_runtime.resolve_switch("switch dev(task-dev-binding) -> track-dev-binding: continue implementation")
        payload = switch_runtime.persist_switch(resolved, skill_id=None, result=self._artifact_result())
        self._remember_persisted_paths(payload)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_id"], "task-dev-binding")
        self.assertEqual(payload["track_id"], "track-dev-binding")
        track_after = get_track("track-dev-binding")
        self.assertIsNotNone(track_after)
        self.assertIn("task-dev-binding", track_after["task_ids"])

    def test_track_manager_create_track_binds_current_task(self) -> None:
        resolved = switch_runtime.resolve_switch("switch pm: create new track and set ownership")
        result = {
            "execution_summary": "Created the requested track.",
            "working_notes": ["Reserved PM as the initial owner."],
            "deliverables_or_changed_files": [],
            "track_operation": {
                "action": "create",
                "track_id": "track-task-manager-create",
                "title": "Track Task Manager Create",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "design",
                "summary": "Initial track creation.",
            },
        }
        payload = switch_runtime.persist_switch(resolved, skill_id="track-manager", result=result)
        self._remember_persisted_paths(payload)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "track-manager")
        self.assertEqual(payload["track_action"], "create")
        self.assertEqual(payload["track_id"], "track-task-manager-create")
        track_json = json.loads((ROOT / payload["paths"]["track"]).read_text(encoding="utf-8"))
        self.assertIn(payload["task_id"], track_json["task_ids"])

    def test_execute_alias_is_not_registered(self) -> None:
        parser = switch_runtime.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["execute", "--resolved", "resolved.json", "--result", "result.json"])


if __name__ == "__main__":
    unittest.main()
