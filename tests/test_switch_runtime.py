#!/usr/bin/env python3
"""Regression tests for task-centric BuddySwitch resolve/persist runtime."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import textwrap
import unittest
import uuid
from contextlib import redirect_stderr
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import switch_runtime  # noqa: E402
import workspace_data  # noqa: E402
from env_store import create_artifact, create_task, create_track, get_track, validate_artifact, validate_track  # noqa: E402


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
        self.assertRegex(payload["task_resolution"]["task_id"], r"^task-dev-[a-z0-9-]+-[0-9a-f]{6}$")
        self.assertLess(len(payload["task_resolution"]["task_id"]), 64)
        self.assertIsNone(payload["effective_track_id"])
        self.assertIsNone(payload["track_artifact_index"])
        self.assertIsNone(payload["artifact_selection"])
        self.assertEqual(payload["eligible_skills"], ["implement-task"])
        self.assertEqual(payload["implicit_skill_id"], "implement-task")
        self.assertEqual(payload["run_instructions"]["selected_inputs"], [])
        self.assertEqual(payload["run_instructions"]["artifact_read_commands"], [])
        card = payload["skill_cards"][0]
        self.assertEqual(card["instruction_path"], "buddyswitch/skills/dev/implement-task/SKILL.md")
        self.assertEqual(card["output_slot"], "implementation-report")
        self.assertEqual(card["input_slots"], ["prd", "design-spec", "task"])
        self.assertNotIn("default_artifact_kind", card)
        self.assertNotIn("auto_summary", card)

    def test_track_manager_skill_card_omits_output_slot_and_compat_fields(self) -> None:
        payload = switch_runtime.resolve_switch("switch pm: manage the active track")

        self.assertTrue(payload["ok"])
        card = next(card for card in payload["skill_cards"] if card["id"] == "track-manager")
        self.assertFalse(card["produces_artifact"])
        self.assertNotIn("output_slot", card)
        self.assertNotIn("default_artifact_kind", card)
        self.assertNotIn("auto_summary", card)

    def test_multi_skill_market_buddy_returns_no_implicit_skill(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["invocation"]["buddy"], "market")
        self.assertEqual(
            payload["eligible_skills"],
            [
                "research-scan",
                "pmf-recon",
                "customer-discovery",
                "positioning-copy",
                "channel-discovery",
                "launch-prep",
            ],
        )
        self.assertIsNone(payload["implicit_skill_id"])

        ids = [card["id"] for card in payload["skill_cards"]]
        self.assertEqual(
            ids,
            [
                "research-scan",
                "pmf-recon",
                "customer-discovery",
                "positioning-copy",
                "channel-discovery",
                "launch-prep",
            ],
        )

        research_card = next(card for card in payload["skill_cards"] if card["id"] == "research-scan")
        self.assertEqual(research_card["output_slot"], "market-scan")

        pmf_card = next(card for card in payload["skill_cards"] if card["id"] == "pmf-recon")
        self.assertEqual(
            pmf_card["instruction_path"],
            "buddyswitch/skills/market/pmf-recon/SKILL.md",
        )
        self.assertEqual(pmf_card["output_slot"], "pmf-report")
        self.assertEqual(
            pmf_card["input_slots"],
            ["research-question", "links", "prior-artifacts"],
        )

    def test_skill_card_uses_package_metadata_for_description_and_objects(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            package_root = Path(temp_dir) / "demo-skill"
            package_root.mkdir()
            (package_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "demo-skill"
                    buddy = "pm"
                    description = "Demo skill package."
                    objects = ["task", "artifact"]
                    produces_artifact = true
                    output_slot = "prd"
                    input_slots = ["research-report"]
                    output_schema = "framework/schemas/pm/write-prd.json"
                    produces = ["prd"]
                    consumes = ["research-report"]
                    side_effect_level = "medium"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["definition"]
                    """
                ),
                encoding="utf-8",
            )
            (package_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # demo-skill

                    ## Purpose
                    - Define product scope.

                    ## Use when
                    - The task is about product definition.

                    ## Do not use when
                    - The task is implementation or testing.

                    ## Inputs
                    - Research and scope context.

                    ## Outputs
                    - A structured PRD result.

                    ## Verification
                    - Confirm scope and open questions.

                    ## Examples
                    - `switch pm: define scope`

                    ## Counterexamples
                    - `switch dev: implement scope`

                    ## Gotchas
                    - Keep scope narrow.
                    """
                ),
                encoding="utf-8",
            )
            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            payload = switch_runtime.resolve_switch("switch pm: define scope", manifest_path=manifest_path)

        self.assertTrue(payload["ok"])
        skill_card = payload["skill_cards"][0]
        self.assertEqual(skill_card["description"], "Demo skill package.")
        self.assertEqual(skill_card["objects"], ["task", "artifact"])
        self.assertNotIn("default_artifact_kind", skill_card)
        self.assertNotIn("auto_summary", skill_card)

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

    def test_resolve_includes_track_artifact_index_with_history(self) -> None:
        track = create_track("track-index-resolve", "Track Index Resolve")
        task = create_task(
            "task-pm-index-resolve",
            "PM Index Resolve",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-index-resolve",
        )
        first_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd",
            title="PM PRD V1",
            buddy="pm",
            skill_id="write-prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-v1",
            summary="First requirement summary.",
            content={"problem": "v1"},
        )
        second_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd-2",
            title="PM PRD V2",
            buddy="pm",
            skill_id="write-prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-v2",
            summary="Second requirement summary.",
            content={"problem": "v2"},
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{first_artifact['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{second_artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch design -> track-index-resolve: continue design handoff based on pm requirements"
        )

        self.assertTrue(payload["ok"])
        self.assertIn("track_artifact_index", payload)
        index = payload["track_artifact_index"]
        self.assertIsInstance(index, dict)
        assert isinstance(index, dict)
        self.assertEqual(index["track_id"], "track-index-resolve")
        self.assertEqual(len(index["tasks"]), 1)
        task_row = index["tasks"][0]
        self.assertEqual(task_row["task_id"], "task-pm-index-resolve")
        self.assertEqual(
            task_row["artifact_slots"]["write-prd"]["current_artifact_id"],
            "art-task-pm-index-resolve-prd-2",
        )
        self.assertEqual(
            [item["artifact_id"] for item in task_row["artifacts"]],
            ["art-task-pm-index-resolve-prd-2", "art-task-pm-index-resolve-prd"],
        )
        self.assertEqual([item["is_current"] for item in task_row["artifacts"]], [True, False])
        self.assertEqual(payload["artifact_selection"]["selected_inputs"], [])
        self.assertEqual(payload["artifact_selection"]["selection_mode"], "slot-current-v2")
        self.assertEqual(payload["run_instructions"]["selected_inputs"], [])
        self.assertEqual(
            payload["run_instructions"]["artifact_read_commands"],
            [],
        )

    def test_resolve_track_artifact_index_exposes_current_artifacts_by_slot(self) -> None:
        track = create_track("track-index-resolve-slot", "Track Index Resolve Slot")
        dev_task = create_task(
            "task-dev-slot-aware",
            "Dev Slot Aware",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-seed-dev-slot-aware",
        )
        task = create_task(
            "task-pm-index-resolve-slot",
            "PM Index Resolve Slot",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-index-resolve-slot",
        )
        first_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd-r1",
            title="PM PRD V1",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-slot-v1",
            summary="First requirement summary.",
            content={"problem": "v1"},
        )
        second_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd-r2",
            title="PM PRD V2",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-slot-v2",
            summary="Second requirement summary.",
            content={"problem": "v2"},
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{dev_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{first_artifact['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{second_artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch dev(task-dev-slot-aware) -> track-index-resolve-slot: continue implementation"
        )

        task_rows = payload["track_artifact_index"]["tasks"]
        pm_row = next(row for row in task_rows if row["buddy"] == "pm")
        prd_row = next(item for item in pm_row["artifacts"] if item["slot"] == "prd" and item["is_current"])

        self.assertEqual(pm_row["artifact_slots"]["prd"]["current_artifact_id"], prd_row["artifact_id"])
        self.assertEqual(prd_row["revision"], 2)
        self.assertEqual(prd_row["supersedes_artifact_id"], "art-task-pm-index-resolve-prd-r1")

    def test_resolve_track_index_includes_task_without_artifacts(self) -> None:
        track = create_track("track-empty-artifacts", "Track Empty Artifacts")
        task = create_task(
            "task-design-empty-artifacts",
            "Design Empty Artifacts",
            buddy="design",
            track_id=track["id"],
            initial_run_id="run-seed-empty-artifacts",
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch dev -> track-empty-artifacts: implement according to current track inputs"
        )

        self.assertTrue(payload["ok"])
        index = payload["track_artifact_index"]
        self.assertIsInstance(index, dict)
        assert isinstance(index, dict)
        self.assertEqual(index["track_id"], "track-empty-artifacts")
        self.assertEqual(len(index["tasks"]), 1)
        self.assertEqual(index["tasks"][0]["task_id"], "task-design-empty-artifacts")
        self.assertEqual(index["tasks"][0]["artifact_slots"], {})
        self.assertEqual(index["tasks"][0]["artifacts"], [])
        self.assertEqual(payload["artifact_selection"]["selected_inputs"], [])
        self.assertEqual(payload["run_instructions"]["selected_inputs"], [])
        self.assertEqual(payload["run_instructions"]["artifact_read_commands"], [])


class WorkspaceDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(ROOT / repo_path)

    def test_artifact_view_uses_object_path_only(self) -> None:
        artifact = {
            "id": "art-task-centric",
            "title": "Task-Centric Artifact",
            "task_id": "task-dev-one",
            "buddy": "dev",
            "skill_id": "implement-task",
            "slot": "implementation-report",
            "revision": 1,
            "supersedes_artifact_id": None,
            "is_current": True,
            "source_run_id": "run-test",
            "summary": "Canonical summary",
            "content": {"task_summary": "ok"},
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        view = workspace_data.build_artifact_view(artifact)
        self.assertFalse(view["missing"])
        self.assertEqual(view["object_path"], "buddyswitch/objects/artifacts/art-task-centric.json")

    def test_task_view_projects_current_artifacts_by_slot(self) -> None:
        task = {
            "id": "task-dev-one",
            "buddy": "dev",
            "title": "Dev Task",
            "status": "active",
            "track_id": "track-dev-one",
            "artifact_ids": ["art-prd", "art-impl"],
            "artifact_slots": {
                "prd": {"current_artifact_id": "art-prd", "revision_count": 2},
                "implementation-report": {"current_artifact_id": "art-impl", "revision_count": 1},
            },
            "run_ids": ["run-seed"],
            "latest_run_id": "run-seed",
            "summary": "Task summary",
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }
        artifact_map = {
            "art-prd": {
                "id": "art-prd",
                "slot": "prd",
                "updated_at": "2026-04-12T10:05:00+08:00",
            },
            "art-impl": {
                "id": "art-impl",
                "slot": "implementation-report",
                "updated_at": "2026-04-12T10:06:00+08:00",
            },
        }

        view = workspace_data.build_task_view(task, artifact_map)

        self.assertEqual(sorted(view["current_artifacts"].keys()), ["implementation-report", "prd"])
        self.assertEqual(view["current_artifacts"]["prd"]["id"], "art-prd")
        self.assertNotIn("latest_artifact", view)

    def test_build_workspace_data_exposes_standalone_tasks(self) -> None:
        track = create_track("track-workspace-linked", "Linked Track")
        tracked_task = create_task(
            "task-dev-workspace-linked",
            "Tracked Task",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-seed-workspace-linked",
        )
        standalone_task = create_task(
            "task-market-standalone-workspace",
            "Standalone Market Task",
            buddy="market",
            initial_run_id="run-seed-standalone-workspace",
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{tracked_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{standalone_task['id']}.json")

        payload = workspace_data.build_workspace_data()

        self.assertIn("standalone_tasks", payload)
        standalone_ids = [task["id"] for task in payload["standalone_tasks"]]
        self.assertIn("task-market-standalone-workspace", standalone_ids)
        self.assertNotIn("task-dev-workspace-linked", standalone_ids)

    def test_scan_run_audits_includes_reference_switches(self) -> None:
        run_id = f"run-workspace-audit-{uuid.uuid4().hex[:8]}"
        run_path = ROOT / f"buddyswitch/content/runs/{run_id}.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "timestamp": "2026-04-12T20:10:00+08:00",
                    "switch": {
                        "buddy": "dev",
                        "task_id": "task-dev-audit-123abc",
                        "track_id": "track-audit",
                        "demand": "implement scope",
                    },
                    "resolved_task_id": "task-dev-audit-123abc",
                    "effective_track_id": "track-audit",
                    "skill_id": "implement-task",
                    "artifact_ids": ["art-audit"],
                    "task_title": "Audit Task Title",
                    "track_title": "Audit Track Title",
                    "reference_switches": {
                        "continue_current_task": "switch dev(task-dev-audit-123abc): <demand>"
                    },
                    "related_run_ids": ["run-prior-a", "run-prior-b"],
                    "recommended_switch": "switch dev(task-dev-audit-123abc): <demand>",
                    "execution_summary": "ok",
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._remember(f"buddyswitch/content/runs/{run_id}.json")

        rows = workspace_data.scan_run_audits()
        row = next((item for item in rows if item.get("run_id") == run_id), None)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["task_title"], "Audit Task Title")
        self.assertEqual(row["track_title"], "Audit Track Title")
        self.assertEqual(
            row["reference_switches"]["continue_current_task"],
            "switch dev(task-dev-audit-123abc): <demand>",
        )
        self.assertEqual(row["related_run_ids"], ["run-prior-a", "run-prior-b"])
        self.assertEqual(row["recommended_switch"], "switch dev(task-dev-audit-123abc): <demand>")
        self.assertNotIn("suggested_next_switch", row)


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
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
                "verification_runs": [{"command": "npm test", "result": "passed", "notes": "Targeted unit coverage."}],
                "known_limitations": ["No production build was executed in this test."],
            },
        }

    def _pmf_recon_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Completed a narrow PMF recon pass for the idea.",
            "working_notes": ["Focused on evidence-backed pain signals only."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Do indie developers show credible demand for AI companion live spaces?",
                "research_strategy": {
                    "depth": "quick",
                    "rationale": "Cover the new persist path with a minimal valid payload.",
                    "collection_mode": "Targeted secondary research",
                    "initial_hypotheses": ["Developers struggle to validate demand before building."],
                    "source_category_targets": ["forums", "founder communities"],
                },
                "channel_plan": ["Founder forums", "Indie hacker communities"],
                "iteration_log": [
                    {
                        "round": 1,
                        "focus": "Demand discovery",
                        "sources_checked": ["https://example.com/source-1"],
                        "evidence_captured": "Found repeated mentions of weak feedback loops.",
                        "synthesis": "Pain centers on confidence in what to build next.",
                        "next_adjustment": "Probe willingness to try lightweight validation tools.",
                    }
                ],
                "evidence": [
                    {
                        "source_id": "src-1",
                        "url": "https://example.com/source-1",
                        "source_type": "forum-thread",
                        "accessed_at": "2026-04-14T10:00:00+08:00",
                        "claim_excerpt": "I keep building without enough real demand signals.",
                        "segment": "indie developers",
                        "pain_category": "demand-validation",
                        "confidence": "medium",
                    }
                ],
                "source_traceability": [
                    {
                        "conclusion": "Early demand validation remains a recurring pain point.",
                        "source_ids": ["src-1"],
                    }
                ],
                "assumptions_used": ["Public founder discussions are directionally useful for this check."],
                "candidate_icps": [
                    {
                        "segment": "Indie developers launching early products",
                        "pain_summary": "Need faster feedback on whether a concept is worth pursuing.",
                        "why_now_or_why_this_segment": "They operate with limited time and budget.",
                    }
                ],
                "strongest_pain_signals": ["Low confidence in what to build", "Weak user feedback volume"],
                "existing_alternatives": [
                    {
                        "name": "Manual interviews",
                        "type": "service",
                        "gaps": ["Slow to schedule", "Hard to maintain cadence"],
                    }
                ],
                "why_current_solutions_fall_short": ["They are too manual for continuous lightweight validation."],
                "pmf_confidence": {
                    "level": "medium",
                    "rationale": "Evidence suggests real pain, but paid demand remains unproven.",
                },
                "recommended_next_step": {
                    "action": "interviews",
                    "rationale": "Direct interviews are the fastest next step to validate urgency.",
                },
                "suggested_interview_angles": ["Current validation workflow", "Signals that would change roadmap decisions"],
                "risks_and_unknowns": ["Willingness to pay is still unclear."],
                "conclusion": "There is enough evidence to continue with direct customer discovery.",
            },
        }

    def test_persist_creates_task_and_run_bound_artifact(self) -> None:
        resolved = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
        payload = switch_runtime.persist_switch(resolved, skill_id=None, result=self._artifact_result())

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "implement-task")
        self.assertEqual(payload["task_id"], resolved["task_resolution"]["task_id"])
        self.assertEqual(payload["artifact_ids"], [payload["artifact_id"]])
        self.assertIn("task_title", payload)
        self.assertIsNone(payload["track_title"])
        self.assertIn("reference_switches", payload)
        self.assertEqual(
            payload["reference_switches"]["continue_current_task"],
            f"switch dev({payload['task_id']}): <demand>",
        )
        self.assertEqual(payload["related_run_ids"], [])
        self.assertEqual(payload["recommended_switch"], payload["reference_switches"]["continue_current_task"])
        self._remember_persisted_paths(payload)

        artifact_json = json.loads((ROOT / payload["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
        task_json = json.loads((ROOT / payload["paths"]["task"]).read_text(encoding="utf-8"))
        run_json = json.loads((ROOT / payload["paths"]["run"]).read_text(encoding="utf-8"))

        self.assertEqual(artifact_json["task_id"], payload["task_id"])
        self.assertEqual(artifact_json["source_run_id"], payload["run_id"])
        self.assertIn(payload["run_id"], task_json["run_ids"])
        self.assertNotIn("latest_artifact_id", task_json)
        self.assertEqual(
            task_json["artifact_slots"][artifact_json["slot"]]["current_artifact_id"],
            payload["artifact_id"],
        )
        self.assertEqual(run_json["resolved_task_id"], payload["task_id"])
        self.assertEqual(run_json["artifact_ids"], [payload["artifact_id"]])
        self.assertEqual(run_json["switch"]["demand"], resolved["switch"]["demand"])
        self.assertEqual(run_json["task_title"], payload["task_title"])
        self.assertEqual(run_json["track_title"], payload["track_title"])
        self.assertEqual(run_json["reference_switches"], payload["reference_switches"])
        self.assertEqual(run_json["related_run_ids"], payload["related_run_ids"])
        self.assertEqual(run_json["recommended_switch"], payload["recommended_switch"])
        self.assertNotIn("suggested_next_switch", run_json)
        self.assertNotIn("artifact_content", run_json)

    def test_persist_multi_skill_market_requires_explicit_skill_id(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )
        task_id = resolved["task_resolution"]["task_id"]
        task_path = ROOT / "buddyswitch" / "objects" / "tasks" / f"{task_id}.json"
        artifact_path = ROOT / "buddyswitch" / "objects" / "artifacts" / f"art-{task_id}-research.json"
        run_dir = ROOT / "buddyswitch" / "content" / "runs"
        before_runs = {path.name for path in run_dir.glob("run-*.json")}

        self.assertFalse(task_path.exists())
        self.assertFalse(artifact_path.exists())

        with self.assertRaisesRegex(
            ValueError,
            "skill_id is required for multi-skill buddies. Choose one from eligible_skills first.",
        ):
            switch_runtime.persist_switch(resolved, skill_id=None, result=self._pmf_recon_result())

        self.assertFalse(task_path.exists())
        self.assertFalse(artifact_path.exists())
        self.assertEqual({path.name for path in run_dir.glob("run-*.json")}, before_runs)

    def test_persist_multi_skill_market_with_pmf_recon_persists_run_bound_artifact(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )

        payload = switch_runtime.persist_switch(
            resolved,
            skill_id="pmf-recon",
            result=self._pmf_recon_result(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "pmf-recon")
        self.assertEqual(payload["task_id"], resolved["task_resolution"]["task_id"])
        self.assertEqual(payload["artifact_ids"], [payload["artifact_id"]])
        self.assertIn("task_title", payload)
        self.assertIsNone(payload["track_title"])
        self.assertIn("reference_switches", payload)
        self.assertEqual(
            payload["reference_switches"]["continue_current_task"],
            f"switch market({payload['task_id']}): <demand>",
        )
        self.assertEqual(payload["related_run_ids"], [])
        self.assertEqual(payload["recommended_switch"], payload["reference_switches"]["continue_current_task"])
        self._remember_persisted_paths(payload)

        artifact_json = json.loads((ROOT / payload["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
        task_json = json.loads((ROOT / payload["paths"]["task"]).read_text(encoding="utf-8"))
        run_json = json.loads((ROOT / payload["paths"]["run"]).read_text(encoding="utf-8"))

        self.assertEqual(artifact_json["task_id"], payload["task_id"])
        self.assertEqual(artifact_json["source_run_id"], payload["run_id"])
        self.assertEqual(artifact_json["skill_id"], "pmf-recon")
        self.assertEqual(artifact_json["slot"], "research")
        self.assertEqual(
            artifact_json["content"]["research_question"],
            self._pmf_recon_result()["artifact_content"]["research_question"],
        )
        self.assertIn(payload["run_id"], task_json["run_ids"])
        self.assertEqual(
            task_json["artifact_slots"][artifact_json["slot"]]["current_artifact_id"],
            payload["artifact_id"],
        )
        self.assertEqual(run_json["resolved_task_id"], payload["task_id"])
        self.assertEqual(run_json["artifact_ids"], [payload["artifact_id"]])
        self.assertEqual(run_json["skill_id"], "pmf-recon")
        self.assertEqual(run_json["switch"]["demand"], resolved["switch"]["demand"])
        self.assertEqual(run_json["task_title"], payload["task_title"])
        self.assertEqual(run_json["track_title"], payload["track_title"])
        self.assertEqual(run_json["reference_switches"], payload["reference_switches"])
        self.assertEqual(run_json["related_run_ids"], payload["related_run_ids"])
        self.assertEqual(run_json["recommended_switch"], payload["recommended_switch"])
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
        self.assertEqual(payload["track_title"], "Track Binding")
        self.assertIn("continue_current_task_in_track", payload["reference_switches"])
        self.assertNotIn("handoff_to_next_buddy", payload["reference_switches"])
        self.assertEqual(payload["recommended_switch"], payload["reference_switches"]["continue_current_task_in_track"])
        track_after = get_track("track-dev-binding")
        self.assertIsNotNone(track_after)
        self.assertIn("task-dev-binding", track_after["task_ids"])

    def test_persist_artifact_skill_requires_output_slot_without_legacy_fallback(self) -> None:
        track = create_track("track-legacy-output-slot", "Track Legacy Output Slot")
        task = create_task(
            "task-dev-legacy-output-slot",
            "Task Legacy Output Slot",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-seed-legacy-output-slot",
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        resolved = switch_runtime.resolve_switch(
            "switch dev(task-dev-legacy-output-slot) -> track-legacy-output-slot: continue implementation"
        )
        skill = {
            "id": "legacy-output-slot-skill",
            "runtime": {
                "default_artifact_kind": "legacy-kind",
                "produces_artifact": True,
                "input_slots": ["task"],
                "output_schema": "framework/schemas/dev/implement-task.json",
            },
        }

        try:
            payload = switch_runtime._persist_artifact_skill(  # type: ignore[attr-defined]
                resolved=resolved,
                skill=skill,
                result=self._artifact_result(),
                run_id="run-legacy-output-slot",
                task=task,
                effective_track_id=track["id"],
            )
        except ValueError as exc:
            self.assertRegex(str(exc), "non-empty output_slot")
        else:
            self._remember_persisted_paths(payload)
            self.fail("Expected _persist_artifact_skill to reject missing output_slot")

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
        self.assertEqual(payload["track_title"], "Track Task Manager Create")
        self.assertIn("handoff_to_next_buddy", payload["reference_switches"])
        self.assertEqual(
            payload["reference_switches"]["handoff_to_next_buddy"],
            "switch design -> track-task-manager-create: <demand>",
        )
        self.assertEqual(payload["recommended_switch"], payload["reference_switches"]["handoff_to_next_buddy"])
        track_json = json.loads((ROOT / payload["paths"]["track"]).read_text(encoding="utf-8"))
        self.assertIn(payload["task_id"], track_json["task_ids"])

    def test_persist_related_runs_surface_previous_task_runs(self) -> None:
        first_resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        first_payload = switch_runtime.persist_switch(first_resolved, skill_id=None, result=self._artifact_result())
        self._remember_persisted_paths(first_payload)

        second_resolved = switch_runtime.resolve_switch(
            f"switch dev({first_payload['task_id']}): continue onboarding improvements"
        )
        second_payload = switch_runtime.persist_switch(second_resolved, skill_id=None, result=self._artifact_result())
        self._remember_persisted_paths(second_payload)

        self.assertIn(first_payload["run_id"], second_payload["related_run_ids"])

    def test_execute_alias_is_not_registered(self) -> None:
        parser = switch_runtime.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["execute", "--resolved", "resolved.json", "--result", "result.json"])


if __name__ == "__main__":
    unittest.main()
