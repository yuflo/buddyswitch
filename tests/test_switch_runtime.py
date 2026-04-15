#!/usr/bin/env python3
"""Regression tests for task-centric BuddySwitch resolve/persist runtime."""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import textwrap
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import switch_runtime  # noqa: E402
import workspace_data  # noqa: E402
from env_store import create_artifact, create_task, create_track, get_track, require_id, validate_artifact, validate_track  # noqa: E402


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
        self.assertIsNone(payload["task_resolution"]["task_id"])
        self.assertIsInstance(payload["task_resolution"]["create_token"], str)
        self.assertTrue(payload["task_resolution"]["create_token"])
        self.assertIsNone(payload["switch"]["task_id"])
        self.assertIsNone(payload["effective_track_id"])
        self.assertIsNone(payload["track_artifact_index"])
        self.assertIsNone(payload["artifact_selection"])
        self.assertEqual(payload["eligible_skills"], ["implement-task"])
        self.assertEqual(payload["implicit_skill_id"], "implement-task")
        self.assertEqual(payload["run_instructions"]["selected_inputs"], [])
        self.assertEqual(payload["run_instructions"]["artifact_read_commands"], [])
        self.assertEqual(
            sorted(payload["artifact_selection_by_skill"].keys()),
            ["implement-task"],
        )
        self.assertEqual(
            sorted(payload["run_instructions_by_skill"].keys()),
            ["implement-task"],
        )
        self.assertEqual(
            payload["artifact_selection_by_skill"]["implement-task"]["selected_inputs"],
            [],
        )
        self.assertEqual(
            payload["run_instructions_by_skill"]["implement-task"]["selected_inputs"],
            [],
        )
        self.assertEqual(
            payload["run_instructions_by_skill"]["implement-task"]["next_actions"],
            payload["run_instructions"]["next_actions"],
        )
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
        self.assertIsNone(payload["implicit_skill_id"])

        expected_market_skills = [
            "research-scan",
            "pmf-recon",
            "customer-discovery",
            "positioning-copy",
            "channel-discovery",
            "launch-prep",
        ]
        with self.subTest("eligible_skills_order"):
            self.assertEqual(payload["eligible_skills"], expected_market_skills)

        ids = [card["id"] for card in payload["skill_cards"] if isinstance(card, dict) and "id" in card]
        with self.subTest("skill_cards_order"):
            self.assertEqual(ids, expected_market_skills)

        skill_cards_by_id = {
            card["id"]: card for card in payload["skill_cards"] if isinstance(card, dict) and "id" in card
        }
        with self.subTest("research_scan_output_slot"):
            self.assertIn("research-scan", skill_cards_by_id)
            self.assertEqual(skill_cards_by_id.get("research-scan", {}).get("output_slot"), "market-scan")

        with self.subTest("pmf_recon_contract"):
            self.assertIn("pmf-recon", skill_cards_by_id)
            pmf_card = skill_cards_by_id.get("pmf-recon", {})
            self.assertEqual(
                pmf_card.get("instruction_path"),
                "buddyswitch/skills/market/pmf-recon/SKILL.md",
            )
            self.assertEqual(pmf_card.get("output_slot"), "pmf-report")
            self.assertEqual(
                pmf_card.get("input_slots"),
                ["research-question", "links", "prior-artifacts"],
            )

    def test_pm_and_design_skill_cards_use_explicit_market_inputs(self) -> None:
        pm_payload = switch_runtime.resolve_switch(
            "switch pm: Draft the PRD for a validated market opportunity"
        )
        design_payload = switch_runtime.resolve_switch(
            "switch design: Create the IA spec for a first-touch onboarding flow"
        )

        pm_card = pm_payload["skill_cards"][0]
        design_card = design_payload["skill_cards"][0]

        self.assertEqual(
            pm_card["input_slots"],
            [
                "market-scan",
                "pmf-report",
                "customer-discovery",
                "positioning-brief",
                "channel-plan",
                "launch-prep",
                "requirements",
                "track",
            ],
        )
        self.assertEqual(
            design_card["input_slots"],
            ["prd", "positioning-brief", "launch-prep", "requirements", "track"],
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

    def test_resolve_design_selects_market_context_slots_from_track(self) -> None:
        track = create_track("track-design-first-touch", "Track Design First Touch")
        design_task = create_task(
            "task-design-first-touch",
            "Design First Touch",
            buddy="design",
            track_id=track["id"],
            initial_run_id="run-seed-design-first-touch",
        )
        pm_task = create_task(
            "task-pm-first-touch",
            "PM First Touch",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-pm-first-touch",
        )
        market_task = create_task(
            "task-market-first-touch",
            "Market First Touch",
            buddy="market",
            track_id=track["id"],
            initial_run_id="run-seed-market-first-touch",
        )
        prd_artifact = create_artifact(
            artifact_id="art-task-pm-first-touch-prd-r1",
            title="PRD First Touch",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=pm_task["id"],
            source_run_id="run-pm-first-touch-prd-r1",
            summary="Current PRD for first-touch work.",
            content={"problem": "Define onboarding and landing flow."},
        )
        positioning_artifact = create_artifact(
            artifact_id="art-task-market-first-touch-positioning-brief-r1",
            title="Positioning Brief First Touch",
            buddy="market",
            skill_id="positioning-copy",
            slot="positioning-brief",
            task_id=market_task["id"],
            source_run_id="run-market-first-touch-positioning-r1",
            summary="Current positioning brief for first-touch work.",
            content={"positioning_statement": "Confidence before code."},
        )
        launch_artifact = create_artifact(
            artifact_id="art-task-market-first-touch-launch-prep-r1",
            title="Launch Prep First Touch",
            buddy="market",
            skill_id="launch-prep",
            slot="launch-prep",
            task_id=market_task["id"],
            source_run_id="run-market-first-touch-launch-r1",
            summary="Current launch prep for first-touch work.",
            content={"launch_goal": {"primary_goal": "Collect qualified feedback", "timebox": "10 days"}},
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{design_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{pm_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{market_task['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{prd_artifact['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{positioning_artifact['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{launch_artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch design(task-design-first-touch) -> track-design-first-touch: continue IA spec for landing and onboarding"
        )

        self.assertEqual(payload["artifact_selection"]["selection_mode"], "slot-current-v2")
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["artifact_selection"]["selected_inputs"]],
            [
                ("prd", "art-task-pm-first-touch-prd-r1"),
                ("positioning-brief", "art-task-market-first-touch-positioning-brief-r1"),
                ("launch-prep", "art-task-market-first-touch-launch-prep-r1"),
            ],
        )
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["run_instructions"]["selected_inputs"]],
            [
                ("prd", "art-task-pm-first-touch-prd-r1"),
                ("positioning-brief", "art-task-market-first-touch-positioning-brief-r1"),
                ("launch-prep", "art-task-market-first-touch-launch-prep-r1"),
            ],
        )

    def test_resolve_pm_surfaces_write_prd_selection_for_multi_skill_track_handoff(self) -> None:
        track = create_track("track-pm-market-handoff", "PM Market Handoff")
        market_task = create_task(
            "task-market-pm-handoff",
            "Market PM Handoff",
            buddy="market",
            track_id=track["id"],
            initial_run_id="run-seed-market-pm-handoff",
        )
        market_artifacts = [
            create_artifact(
                artifact_id="art-task-market-pm-handoff-market-scan-r1",
                title="Market Scan PM Handoff",
                buddy="market",
                skill_id="research-scan",
                slot="market-scan",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-market-scan-r1",
                summary="Current market scan for PM handoff.",
                content={"research_question": "What should PM scope next?"},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-pmf-report-r1",
                title="PMF Report PM Handoff",
                buddy="market",
                skill_id="pmf-recon",
                slot="pmf-report",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-pmf-report-r1",
                summary="Current PMF report for PM handoff.",
                content={"conclusion": "Proceed with scoped PM work."},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-customer-discovery-r1",
                title="Customer Discovery PM Handoff",
                buddy="market",
                skill_id="customer-discovery",
                slot="customer-discovery",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-customer-discovery-r1",
                summary="Current customer discovery for PM handoff.",
                content={"recommended_next_step": {"action": "Scope the product surface."}},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-positioning-brief-r1",
                title="Positioning Brief PM Handoff",
                buddy="market",
                skill_id="positioning-copy",
                slot="positioning-brief",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-positioning-brief-r1",
                summary="Current positioning brief for PM handoff.",
                content={"positioning_statement": "Confidence before code."},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-channel-plan-r1",
                title="Channel Plan PM Handoff",
                buddy="market",
                skill_id="channel-discovery",
                slot="channel-plan",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-channel-plan-r1",
                summary="Current channel plan for PM handoff.",
                content={"channels": ["communities"]},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-launch-prep-r1",
                title="Launch Prep PM Handoff",
                buddy="market",
                skill_id="launch-prep",
                slot="launch-prep",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-launch-prep-r1",
                summary="Current launch prep for PM handoff.",
                content={"launch_goal": {"primary_goal": "Validate demand", "timebox": "14 days"}},
            ),
        ]
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{market_task['id']}.json")
        for artifact in market_artifacts:
            self._remember(f"buddyswitch/objects/artifacts/{artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch pm -> track-pm-market-handoff: draft the PRD from the active market evidence"
        )

        expected_inputs = [
            ("market-scan", "art-task-market-pm-handoff-market-scan-r1"),
            ("pmf-report", "art-task-market-pm-handoff-pmf-report-r1"),
            ("customer-discovery", "art-task-market-pm-handoff-customer-discovery-r1"),
            ("positioning-brief", "art-task-market-pm-handoff-positioning-brief-r1"),
            ("channel-plan", "art-task-market-pm-handoff-channel-plan-r1"),
            ("launch-prep", "art-task-market-pm-handoff-launch-prep-r1"),
        ]

        self.assertIsNone(payload["implicit_skill_id"])
        self.assertEqual(payload["eligible_skills"], ["write-prd", "track-manager"])
        self.assertEqual(
            sorted(payload["artifact_selection_by_skill"].keys()),
            ["write-prd"],
        )
        self.assertEqual(
            sorted(payload["run_instructions_by_skill"].keys()),
            ["write-prd"],
        )
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["artifact_selection"]["selected_inputs"]],
            expected_inputs,
        )
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["artifact_selection_by_skill"]["write-prd"]["selected_inputs"]],
            expected_inputs,
        )
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["run_instructions"]["selected_inputs"]],
            expected_inputs,
        )
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["run_instructions_by_skill"]["write-prd"]["selected_inputs"]],
            expected_inputs,
        )
        self.assertEqual(
            payload["run_instructions"]["artifact_read_commands"],
            payload["run_instructions_by_skill"]["write-prd"]["artifact_read_commands"],
        )

    def test_resolve_design_prefers_coherent_market_bundle_across_tasks(self) -> None:
        track = create_track("track-design-bundle-aware", "Design Bundle Aware")
        design_task = create_task(
            "task-design-bundle-aware",
            "Design Bundle Aware",
            buddy="design",
            track_id=track["id"],
            initial_run_id="run-seed-design-bundle-aware",
        )
        pm_task = create_task(
            "task-pm-bundle-aware",
            "PM Bundle Aware",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-pm-bundle-aware",
        )
        market_task_a = create_task(
            "task-market-bundle-a",
            "Market Bundle A",
            buddy="market",
            track_id=track["id"],
            initial_run_id="run-seed-market-bundle-a",
        )
        market_task_b = create_task(
            "task-market-bundle-b",
            "Market Bundle B",
            buddy="market",
            track_id=track["id"],
            initial_run_id="run-seed-market-bundle-b",
        )
        created_artifacts = [
            create_artifact(
                artifact_id="art-task-pm-bundle-aware-prd-r1",
                title="PRD Bundle Aware",
                buddy="pm",
                skill_id="write-prd",
                slot="prd",
                task_id=pm_task["id"],
                source_run_id="run-pm-bundle-aware-prd-r1",
                summary="Current PRD for the bundle-aware design test.",
                content={"problem": "Support the coherent onboarding bundle."},
            ),
            create_artifact(
                artifact_id="art-task-market-bundle-a-positioning-brief-r1",
                title="Bundle A Positioning Brief",
                buddy="market",
                skill_id="positioning-copy",
                slot="positioning-brief",
                task_id=market_task_a["id"],
                source_run_id="run-market-bundle-a-positioning-r1",
                summary="Task A positioning brief.",
                content={"positioning_statement": "Bundle A message."},
            ),
            create_artifact(
                artifact_id="art-task-market-bundle-a-launch-prep-r1",
                title="Bundle A Launch Prep",
                buddy="market",
                skill_id="launch-prep",
                slot="launch-prep",
                task_id=market_task_a["id"],
                source_run_id="run-market-bundle-a-launch-r1",
                summary="Task A launch prep.",
                content={"launch_goal": {"primary_goal": "Validate the coherent bundle", "timebox": "7 days"}},
            ),
            create_artifact(
                artifact_id="art-task-market-bundle-b-positioning-brief-r1",
                title="Bundle B Positioning Brief",
                buddy="market",
                skill_id="positioning-copy",
                slot="positioning-brief",
                task_id=market_task_b["id"],
                source_run_id="run-market-bundle-b-positioning-r1",
                summary="Task B newer but unrelated positioning brief.",
                content={"positioning_statement": "Bundle B message."},
            ),
        ]
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{design_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{pm_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{market_task_a['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{market_task_b['id']}.json")
        for artifact in created_artifacts:
            self._remember(f"buddyswitch/objects/artifacts/{artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch design(task-design-bundle-aware) -> track-design-bundle-aware: continue the IA spec with the active market handoff"
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["artifact_selection"]["selected_inputs"]],
            [
                ("prd", "art-task-pm-bundle-aware-prd-r1"),
                ("positioning-brief", "art-task-market-bundle-a-positioning-brief-r1"),
                ("launch-prep", "art-task-market-bundle-a-launch-prep-r1"),
            ],
        )
        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in payload["run_instructions"]["selected_inputs"]],
            [
                ("prd", "art-task-pm-bundle-aware-prd-r1"),
                ("positioning-brief", "art-task-market-bundle-a-positioning-brief-r1"),
                ("launch-prep", "art-task-market-bundle-a-launch-prep-r1"),
            ],
        )


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

    def _assert_generated_task_id(self, task_id: object, buddy: str) -> None:
        self.assertIsInstance(task_id, str)
        assert isinstance(task_id, str)
        prefix = f"task-{buddy}-"
        self.assertTrue(task_id.startswith(prefix))
        self.assertGreater(len(task_id), len(prefix))
        require_id(task_id, "task id")

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

    def _customer_discovery_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Prepared a customer discovery brief from public market evidence.",
            "working_notes": ["Kept the interview scope narrow and evidence-backed."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Which indie developers should be prioritized for early interviews?",
                "target_segments": [
                    {
                        "segment": "Indie developers validating new SaaS ideas",
                        "pain_context": "They lack confidence in what to validate before building.",
                        "why_this_segment": "They can act quickly on structured interview plans.",
                    }
                ],
                "interview_goals": [
                    "Validate the most urgent demand-validation pain",
                    "Learn how developers currently gather customer signals",
                ],
                "recruiting_criteria": {
                    "must_have": ["Recently evaluated or launched a new product idea"],
                    "nice_to_have": ["Shares validation lessons in public communities"],
                    "exclude_if": ["Has no recent product-validation experience"],
                },
                "interview_guide": [
                    {
                        "section": "Current workflow",
                        "goal": "Understand how validation happens today.",
                        "prompts": ["Walk me through the last time you validated a product idea."],
                    }
                ],
                "hypotheses_to_test": ["Developers default to ad-hoc validation because structured options feel too heavy."],
                "evidence": [
                    {
                        "source_id": "src-disc-1",
                        "url": "https://example.com/discovery-source",
                        "source_type": "forum-thread",
                        "accessed_at": "2026-04-15T10:00:00+08:00",
                        "claim_excerpt": "I keep guessing what users want because I do not have a repeatable discovery process.",
                    }
                ],
                "source_traceability": [
                    {
                        "conclusion": "Interview prompts should focus on current validation habits before solution reactions.",
                        "source_ids": ["src-disc-1"],
                    }
                ],
                "patterns_and_insights": ["Discovery pain is strongest around repeatability and prioritization."],
                "risks_and_unknowns": ["Recruiting may skew toward public builders rather than quieter but similar buyers."],
                "recommended_next_step": {
                    "action": "Recruit five interviews with recent indie launches.",
                    "rationale": "This is enough to test whether the workflow pain is urgent and repeated.",
                },
                "conclusion": "The next customer discovery round should center on repeatable validation habits and switching triggers.",
            },
        }

    def _positioning_copy_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Converted market evidence into a positioning brief for first-touch messaging.",
            "working_notes": ["Kept the message house tied to observed pains and alternatives."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "What positioning should an early demand-validation tool use for indie developers?",
                "target_audience": {
                    "primary": "Indie developers validating SaaS ideas",
                    "context": "They are juggling build decisions with weak user feedback.",
                    "trigger": "They need faster confidence before committing to development work.",
                },
                "status_quo_and_alternatives": [
                    {
                        "option": "Manual interviews and community posts",
                        "type": "workflow",
                        "why_it_persists": "It is familiar and low-cost to start.",
                        "limitations": ["Feedback arrives slowly", "Signals are hard to compare over time"],
                    }
                ],
                "differentiated_capabilities": ["Turns demand signals into a repeatable evidence log", "Keeps early validation lightweight for solo builders"],
                "value_claims": [
                    {
                        "claim": "Validate product ideas with a lighter process than manual outreach alone.",
                        "audience_value": "Developers get faster confidence about what to test next.",
                        "evidence_basis": ["src-pos-1"],
                    }
                ],
                "positioning_statement": "For indie developers validating new SaaS ideas, BuddySwitch keeps demand discovery structured without turning it into a heavy research project.",
                "message_house": {
                    "core_message": "Structured demand discovery for builders who move fast.",
                    "supporting_points": ["Capture repeatable evidence, not vague impressions", "Focus on the sharpest pain before building"],
                },
                "homepage_angles": [
                    {
                        "angle": "Confidence before code",
                        "headline_direction": "Know what is worth building before you build it.",
                        "why_it_might_work": "It speaks directly to the repeated uncertainty found in public founder discussions.",
                    }
                ],
                "evidence": [
                    {
                        "source_id": "src-pos-1",
                        "url": "https://example.com/positioning-source",
                        "source_type": "forum-thread",
                        "accessed_at": "2026-04-15T10:10:00+08:00",
                        "claim_excerpt": "I need clearer proof of demand before I spend another weekend building.",
                    }
                ],
                "source_traceability": [
                    {
                        "conclusion": "First-touch copy should emphasize confidence and speed rather than feature depth.",
                        "source_ids": ["src-pos-1"],
                    }
                ],
                "risks_and_unknowns": ["Positioning still assumes confidence is a stronger hook than speed for this segment."],
                "conclusion": "The strongest positioning angle is structured confidence before development effort.",
            },
        }

    def _channel_discovery_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Ranked believable early channels for the first market experiment.",
            "working_notes": ["Kept the experiment plan constrained to one primary and one backup channel."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Which acquisition channel should be tested first for this indie developer audience?",
                "candidate_channels": [
                    {
                        "channel": "Founder communities",
                        "why_it_is_plausible": "The target audience already discusses validation pain there.",
                        "constraints": ["Requires direct founder participation"],
                    }
                ],
                "selection_criteria": ["Reach the right builders quickly", "Earn trust through context-rich posts"],
                "channel_scores": [
                    {
                        "channel": "Founder communities",
                        "scores": {
                            "reachability": 4,
                            "credibility": 4,
                            "speed": 4,
                            "cost": 5,
                            "signal_quality": 4,
                        },
                        "summary": "Strong fit because the audience already shares validation pain openly in these spaces.",
                    }
                ],
                "recommended_primary_channel": {
                    "channel": "Founder communities",
                    "why": "It offers the best balance of trust, speed, and direct feedback for this audience.",
                    "preconditions": ["Prepare a concrete founder post with one clear CTA"],
                },
                "recommended_secondary_channel": {
                    "channel": "Indie developer newsletters",
                    "why": "Useful backup if community reach stalls after the first test.",
                    "preconditions": ["Find newsletter operators who already cover validation workflows"],
                },
                "experiment_plan": {
                    "goal": "Generate qualified conversations about current validation workflow pain.",
                    "offer": "A lightweight demand-discovery workflow preview.",
                    "audience": "Indie developers validating new SaaS ideas",
                    "steps": ["Publish a founder post", "Collect replies", "Follow up with respondents"],
                    "timebox": "7 days",
                    "success_signal": "At least five qualified responses from builders in scope",
                },
                "kill_signals": ["No qualified replies after two well-placed posts", "Replies focus on unrelated founder problems"],
                "evidence": [
                    {
                        "source_id": "src-chan-1",
                        "url": "https://example.com/channel-source",
                        "source_type": "community-post",
                        "accessed_at": "2026-04-15T10:20:00+08:00",
                        "claim_excerpt": "Founders here swap validation tactics and ask for concrete feedback loops all the time.",
                    }
                ],
                "source_traceability": [
                    {
                        "conclusion": "Founder communities are the most credible first channel because they already host the target pain discussion.",
                        "source_ids": ["src-chan-1"],
                    }
                ],
                "risks_and_unknowns": ["The same audience may saturate quickly if the message is too generic."],
                "conclusion": "Start with founder communities and keep a newsletter outreach backup ready.",
            },
        }

    def _launch_prep_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Prepared a launch brief for the first feedback-oriented release.",
            "working_notes": ["Kept the feedback loop explicit before any broader announcement."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "How should the first launch be staged to maximize useful feedback?",
                "launch_goal": {
                    "primary_goal": "Collect qualified feedback from early indie developer prospects.",
                    "timebox": "10 days",
                    "secondary_goal": "Test whether the positioning angle drives replies.",
                },
                "target_audience": {
                    "primary": "Indie developers validating SaaS ideas",
                    "why_now": "They are already searching for faster ways to validate before building.",
                    "reach_notes": "Reach them through founder communities and direct follow-up threads.",
                },
                "selected_channel": {
                    "channel": "Founder communities",
                    "reason": "This is where the target audience already discusses validation pain openly.",
                    "constraints": ["Needs concise founder-led copy and a manual reply workflow"],
                },
                "launch_assets": [
                    {
                        "asset": "Validation landing page",
                        "purpose": "Explain the workflow and collect interested replies.",
                        "owner": "founder",
                        "notes": "Keep the CTA focused on feedback, not signups alone.",
                    }
                ],
                "instrumentation_plan": {
                    "signals_to_track": ["Replies", "Qualified conversations", "Landing page CTA clicks"],
                    "capture_method": "Manual tracking sheet with daily updates",
                    "review_cadence": "Daily during the first 10 days",
                },
                "feedback_collection_plan": {
                    "collection_methods": ["Reply form", "Direct email follow-up"],
                    "follow_up_path": "Invite qualified responders into short follow-up calls",
                    "response_owner": "founder",
                },
                "success_signals": ["Five qualified conversations", "Consistent resonance with the confidence-before-code angle"],
                "failure_signals": ["Traffic without replies", "Replies that do not describe the target pain"],
                "evidence": [
                    {
                        "source_id": "src-launch-1",
                        "url": "https://example.com/launch-source",
                        "source_type": "community-post",
                        "accessed_at": "2026-04-15T10:30:00+08:00",
                        "claim_excerpt": "Founders respond when the ask is specific and the feedback loop is obvious.",
                    }
                ],
                "source_traceability": [
                    {
                        "conclusion": "The launch should lead with a narrow feedback ask and an explicit follow-up path.",
                        "source_ids": ["src-launch-1"],
                    }
                ],
                "risks_and_unknowns": ["The founder may not have enough time to sustain fast follow-up without a strict daily cadence."],
                "conclusion": "A narrow, feedback-led launch is the right first release shape for this market test.",
            },
        }

    def test_persist_creates_task_and_run_bound_artifact(self) -> None:
        resolved = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
        payload = switch_runtime.persist_switch(resolved, skill_id=None, result=self._artifact_result())

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "implement-task")
        self._assert_generated_task_id(payload["task_id"], buddy="dev")
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
        task_dir = ROOT / "buddyswitch" / "objects" / "tasks"
        artifact_dir = ROOT / "buddyswitch" / "objects" / "artifacts"
        run_dir = ROOT / "buddyswitch" / "content" / "runs"
        before_tasks = {path.name for path in task_dir.glob("task-*.json")}
        before_artifacts = {path.name for path in artifact_dir.glob("art-*.json")}
        before_runs = {path.name for path in run_dir.glob("run-*.json")}
        before_task_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in task_dir.glob("task-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }

        with self.assertRaisesRegex(
            ValueError,
            "skill_id is required for multi-skill buddies. Choose one from eligible_skills first.",
        ):
            switch_runtime.persist_switch(resolved, skill_id=None, result=self._pmf_recon_result())

        self.assertEqual({path.name for path in task_dir.glob("task-*.json")}, before_tasks)
        self.assertEqual({path.name for path in artifact_dir.glob("art-*.json")}, before_artifacts)
        self.assertEqual({path.name for path in run_dir.glob("run-*.json")}, before_runs)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in task_dir.glob("task-*.json")
            },
            before_task_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )

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
        self._assert_generated_task_id(payload["task_id"], buddy="market")
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
        self.assertEqual(artifact_json["slot"], "pmf-report")
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

    def test_create_mode_resolve_does_not_expose_task_id_but_persist_generates_one(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertEqual(resolved["task_resolution"]["mode"], "create")
        self.assertIsNone(resolved["task_resolution"]["task_id"])
        self.assertIsInstance(resolved["task_resolution"]["create_token"], str)
        self.assertTrue(resolved["task_resolution"]["create_token"])
        self.assertIsNone(resolved["switch"]["task_id"])

        payload = switch_runtime.persist_switch(resolved, skill_id=None, result=self._artifact_result())
        self._remember_persisted_paths(payload)

        self.assertIsNone(resolved["task_resolution"]["task_id"])
        self.assertIsInstance(resolved["task_resolution"]["create_token"], str)
        self.assertTrue(resolved["task_resolution"]["create_token"])
        self.assertIsNone(resolved["switch"]["task_id"])
        self._assert_generated_task_id(payload["task_id"], buddy="dev")

        run_json = json.loads((ROOT / payload["paths"]["run"]).read_text(encoding="utf-8"))
        self.assertEqual(run_json["resolved_task_id"], payload["task_id"])
        self.assertIsNone(run_json["switch"]["task_id"])

    def test_create_mode_persist_rejects_prefilled_task_ids(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        malformed_resolution = deepcopy(resolved)
        malformed_resolution["task_resolution"]["task_id"] = "task-dev-prefilled-from-resolution"
        with self.assertRaisesRegex(
            ValueError,
            "resolved.task_resolution.task_id must be null for create mode",
        ):
            switch_runtime.persist_switch(malformed_resolution, skill_id=None, result=self._artifact_result())

        malformed_switch = deepcopy(resolved)
        malformed_switch["switch"]["task_id"] = "task-dev-prefilled-from-switch"
        with self.assertRaisesRegex(
            ValueError,
            "resolved.switch.task_id must be null for create mode",
        ):
            switch_runtime.persist_switch(malformed_switch, skill_id=None, result=self._artifact_result())

    def test_create_mode_persist_rejects_missing_or_blank_create_token(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        missing_token = deepcopy(resolved)
        missing_token["task_resolution"].pop("create_token", None)
        with self.assertRaisesRegex(
            ValueError,
            "resolved.task_resolution.create_token is required for create mode",
        ):
            switch_runtime.persist_switch(missing_token, skill_id=None, result=self._artifact_result())

        blank_token = deepcopy(resolved)
        blank_token["task_resolution"]["create_token"] = "   "
        with self.assertRaisesRegex(
            ValueError,
            "resolved.task_resolution.create_token is required for create mode",
        ):
            switch_runtime.persist_switch(blank_token, skill_id=None, result=self._artifact_result())

    def test_cmd_persist_create_mode_downstream_oserror_returns_runtime_error_payload(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        create_token = resolved["task_resolution"]["create_token"]
        expected_task_id = switch_runtime._derive_task_id("dev", "", create_token=create_token)
        self._remember(f"buddyswitch/objects/tasks/{expected_task_id}.json")

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            resolved_path = temp_root / "resolved.json"
            result_path = temp_root / "result.json"
            resolved_path.write_text(json.dumps(resolved, ensure_ascii=True), encoding="utf-8")
            result_path.write_text(json.dumps(self._artifact_result(), ensure_ascii=True), encoding="utf-8")

            args = argparse.Namespace(
                resolved=str(resolved_path),
                result=str(result_path),
                skill_id=None,
                manifest=switch_runtime.DEFAULT_MANIFEST,
            )

            stdout = io.StringIO()
            with patch("switch_runtime._persist_artifact_skill", side_effect=OSError("disk full")):
                with redirect_stdout(stdout):
                    exit_code = switch_runtime._cmd_persist(args)

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_RUNTIME_PERSIST")
        message = payload["error"]["message"]
        self.assertIn("disk full", message)
        self.assertIn(f"created task_id: {expected_task_id}", message)
        self.assertIn(f"recover with switch dev({expected_task_id}): <demand>", message)

    def test_persist_new_market_skills_with_explicit_slots(self) -> None:
        cases = [
            ("customer-discovery", self._customer_discovery_result, "customer-discovery", "interview_goals"),
            ("positioning-copy", self._positioning_copy_result, "positioning-brief", "positioning_statement"),
            ("channel-discovery", self._channel_discovery_result, "channel-plan", "experiment_plan"),
            ("launch-prep", self._launch_prep_result, "launch-prep", "launch_goal"),
        ]

        for skill_id, result_factory, expected_slot, content_key in cases:
            with self.subTest(skill_id=skill_id):
                resolved = switch_runtime.resolve_switch(
                    "switch market: Continue the market evidence handoff for the current opportunity"
                )

                payload = switch_runtime.persist_switch(
                    resolved,
                    skill_id=skill_id,
                    result=result_factory(),
                )
                self._remember_persisted_paths(payload)

                artifact_json = json.loads((ROOT / payload["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
                run_json = json.loads((ROOT / payload["paths"]["run"]).read_text(encoding="utf-8"))

                self.assertEqual(payload["skill_id"], skill_id)
                self.assertEqual(artifact_json["slot"], expected_slot)
                self.assertIn(content_key, artifact_json["content"])
                self.assertEqual(run_json["skill_id"], skill_id)
                self.assertEqual(run_json["artifact_ids"], [payload["artifact_id"]])

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
