#!/usr/bin/env python3
"""Regression tests for BuddySwitch resolve/persist runtime."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
import uuid
import io
import json
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import switch_runtime  # noqa: E402
import workspace_data  # noqa: E402


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
        self.assertEqual(payload["intent"], "switch")
        self.assertEqual(payload["invocation"]["buddy"], "dev")
        self.assertEqual(payload["eligible_skills"], ["implement-task"])
        self.assertEqual(payload["implicit_skill_id"], "implement-task")
        self.assertEqual(payload["profile"]["authority"]["permission_scope"], "manual_debug_apis")
        self.assertEqual(payload["skill_cards"][0]["runtime_requirements"]["policy"], "advisory")
        self.assertIn("resolve parses the invocation", payload["run_instructions"]["resolve_notes"][0])
        self.assertIn("Artifact skills write artifact objects", payload["run_instructions"]["persist_notes"][0])
        self.assertIn("Use implicit_skill_id 'implement-task'", payload["run_instructions"]["next_actions"][0])
        self.assertEqual(
            payload["required_output_schema_by_skill"]["implement-task"],
            "framework/schemas/dev/implement-task.json",
        )

    def test_required_env_and_tools_remain_metadata_not_rejection_gates(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_path = Path(temp_dir)
            skill_path = temp_path / "SKILL.md"
            skill_repo_path = skill_path.relative_to(ROOT).as_posix()
            skill_path.write_text(
                textwrap.dedent(
                    f"""\
                    ---
                    name: demo-scan
                    description: Demo resolve skill.
                    version: "2.0"
                    track_mode: optional
                    default_artifact_kind: note
                    auto_summary: true
                    output_schema: framework/schemas/dev/implement-task.json
                    side_effect_level: low
                    required_tools:
                      - tool-that-does-not-exist
                    required_env:
                      - BUDDYSWITCH_MISSING_ENV
                    produces:
                      - note
                    consumes:
                      - task
                    ---

                    # demo-scan

                    ## Purpose
                    - Resolve demo skill.

                    ## Use when
                    - A demo scan is enough.

                    ## Do not use when
                    - Another skill owns the task.

                    ## Inputs
                    - Task input.

                    ## Outputs
                    - Structured result.

                    ## Verification
                    - Verify the result.

                    ## Examples
                    - `switch demo: run a scan`

                    ## Counterexamples
                    - `switch other: do something else`

                    ## Gotchas
                    - Keep the demo simple.
                    """
                ),
                encoding="utf-8",
            )

            manifest_path = temp_path / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo Env"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo adapter"

                    [[skills]]
                    id = "demo-scan"
                    path = "{skill_repo_path}"
                    description = "Demo scan skill"
                    buddies = ["demo"]
                    objects = ["artifact"]

                    [[buddies]]
                    id = "demo"
                    label = "Demo"
                    scope = "Demo scope"
                    skills = ["demo-scan"]
                    permissions = ["track.read", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            payload = switch_runtime.resolve_switch("switch demo: Run the demo scan", manifest_path=manifest_path)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["eligible_skills"], ["demo-scan"])
        self.assertEqual(payload["skill_cards"][0]["required_tools"], ["tool-that-does-not-exist"])
        self.assertEqual(payload["skill_cards"][0]["required_env"], ["BUDDYSWITCH_MISSING_ENV"])
        self.assertEqual(
            payload["skill_cards"][0]["runtime_requirements"]["required_tools"],
            ["tool-that-does-not-exist"],
        )
        self.assertEqual(
            payload["skill_cards"][0]["runtime_requirements"]["required_env"],
            ["BUDDYSWITCH_MISSING_ENV"],
        )
        self.assertEqual(payload["skill_cards"][0]["runtime_requirements"]["policy"], "advisory")

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
        self.assertNotIn("artifact_defaults_by_skill", payload)
        self.assertNotIn("summary_defaults_by_skill", payload)

    def test_resolve_rejects_legacy_markdown_output_requests(self) -> None:
        with self.assertRaisesRegex(ValueError, "Derived markdown outputs are retired"):
            switch_runtime.resolve_switch(
                "switch dev: Implement the approved onboarding improvements and write to artifacts/demo.md"
            )


class WorkspaceDataTests(unittest.TestCase):
    def test_artifact_view_uses_object_path_only(self) -> None:
        artifact = {
            "id": "art-missing-markdown",
            "title": "Missing Markdown",
            "track_id": None,
            "buddy": "dev",
            "skill_id": "implement-task",
            "summary": "Canonical summary",
            "content": {"task_summary": "ok"},
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        view = workspace_data.build_artifact_view(artifact)

        self.assertFalse(view["missing"])
        self.assertEqual(view["object_path"], "buddyswitch/objects/artifacts/art-missing-markdown.json")
        self.assertNotIn("markdown_exists", view)


class PersistRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(ROOT / repo_path)

    def _dev_resolved_payload(self) -> dict[str, object]:
        return {
            "ok": True,
            "switch": {"buddy": "dev", "task": "Implement the approved onboarding improvements in projects/app"},
            "eligible_skills": ["implement-task"],
            "implicit_skill_id": "implement-task",
            "task_hints": {},
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
        resolved = self._dev_resolved_payload()
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
        resolved = self._dev_resolved_payload()
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

    def test_persist_writes_structured_content_and_run_audit_only(self) -> None:
        resolved = self._dev_resolved_payload()
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
        self.assertEqual(payload["skill_id"], "implement-task")
        artifact_id = payload["artifact_id"]
        artifact_object_path = payload["paths"]["artifact"]
        run_content_path = payload["paths"]["run"]

        self._remember(artifact_object_path)
        self._remember(run_content_path)

        artifact_json = (ROOT / artifact_object_path).read_text(encoding="utf-8")
        run_json = (ROOT / run_content_path).read_text(encoding="utf-8")

        self.assertEqual(artifact_id, payload["artifact_id"])
        self.assertIn('"id":', artifact_json)
        self.assertIn('"content":', artifact_json)
        self.assertIn('"summary": "Implemented the requested change and verified the core path."', artifact_json)
        self.assertIn('"execution_summary": "Implemented the requested change and verified the core path."', run_json)
        self.assertNotIn('"result":', run_json)
        self.assertNotIn('"artifact_content":', run_json)
        self.assertNotIn('"artifact_markdown"', json.dumps(payload))
        self.assertNotIn('"summary"', json.dumps(payload["paths"]))
        self.assertIn(artifact_object_path, payload["writes"])
        self.assertIn(run_content_path, payload["writes"])
        self.assertFalse(any(path.startswith("artifacts/") for path in payload["writes"]))
        self.assertFalse(any(path.startswith("runs/summaries/") for path in payload["writes"]))

    def test_track_manager_persist_creates_track(self) -> None:
        track_id = f"track-test-{uuid.uuid4().hex[:6]}"
        resolved = {
            "ok": True,
            "switch": {"buddy": "pm", "task": f"create {track_id} track"},
            "eligible_skills": ["track-manager"],
            "implicit_skill_id": "track-manager",
            "task_hints": {
                "explicit_track_id": track_id,
                "explicit_artifact_id": None,
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
        self.assertEqual(payload["skill_id"], "track-manager")
        self.assertEqual(payload["track_id"], track_id)
        self._remember(payload["paths"]["track"])
        self._remember(payload["paths"]["run"])

        track_json = (ROOT / f"buddyswitch/objects/tracks/{track_id}.json").read_text(encoding="utf-8")
        run_json = (ROOT / payload["paths"]["run"]).read_text(encoding="utf-8")
        self.assertIn('"current_buddy": "pm"', track_json)
        self.assertIn('"next_buddy": "design"', track_json)
        self.assertIn('"track_action": "create"', run_json)
        self.assertNotIn('"result":', run_json)
        self.assertIn(f"buddyswitch/objects/tracks/{track_id}.json", payload["writes"])

    def test_execute_alias_is_not_registered(self) -> None:
        parser = switch_runtime.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["execute", "--resolved", "resolved.json", "--result", "result.json"])


if __name__ == "__main__":
    unittest.main()
