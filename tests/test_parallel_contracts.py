#!/usr/bin/env python3
"""Freeze BuddySwitch parallel architecture external contract surfaces."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = ROOT / "framework" / "contracts"
SWITCH_GRAMMAR_CONTRACT = CONTRACTS_DIR / "switch-grammar.json"
SELECTED_SKILL_PACKET_CONTRACT = CONTRACTS_DIR / "selected-skill-packet.json"
WORKSPACE_PROJECTION_CONTRACT = CONTRACTS_DIR / "workspace-projection.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class ParallelContractFreezeTests(unittest.TestCase):
    def test_switch_grammar_contract_surface(self) -> None:
        contract = _load_json(SWITCH_GRAMMAR_CONTRACT)

        self.assertEqual(contract["contract_id"], "switch-grammar")
        self.assertEqual(
            contract["canonical_syntax"],
            "switch <buddy>(<task-id>) -> <track-id>: <demand>",
        )
        self.assertEqual(
            contract["supported_forms"],
            [
                "switch <buddy>: <demand>",
                "switch <buddy> -> <track-id>: <demand>",
                "switch <buddy>(<task-id>): <demand>",
                "switch <buddy>(<task-id>) -> <track-id>: <demand>",
            ],
        )
        self.assertEqual(
            contract["rules"],
            [
                "message must start with 'switch'",
                "<buddy> is one token",
                "optional <task-id> appears in parentheses immediately after buddy",
                "optional <track-id> appears after '->'",
                "':' is required",
                "<demand> must be non-empty",
                "text after ':' is demand text, not a task object",
                "minor CLI whitespace variation around ':', '->', and task parentheses may be normalized",
            ],
        )
        self.assertEqual(
            contract["parse_error_codes"],
            [
                "E_EMPTY_INPUT",
                "E_INVALID_SYNTAX",
                "E_UNKNOWN_AGENT",
                "E_EMPTY_DEMAND",
                "E_ENV_MANIFEST",
            ],
        )

    def test_selected_skill_packet_contract_surface(self) -> None:
        contract = _load_json(SELECTED_SKILL_PACKET_CONTRACT)

        self.assertEqual(contract["contract_id"], "selected-skill-packet")
        self.assertEqual(
            contract["packet_fields"],
            [
                "skill_id",
                "buddy",
                "instruction_path",
                "skill_instructions",
                "selected_inputs",
                "output_schema_path",
                "execution_constraints",
                "tool_scope",
                "execution_steps",
            ],
        )
        self.assertEqual(
            contract["host_execution_requirements"],
            [
                "host executes selected_skill_packet in-session",
                "inject selected_skill_packet.skill_instructions verbatim",
                "treat selected_skill_packet.execution_steps as ordered requirements",
                "apply selected_skill_packet.tool_scope before run",
            ],
        )
        self.assertEqual(
            contract["market_execution_boundary"],
            {
                "execution_constraints": "chrome-devtools-cockpit/browser-native/no-silent-degrade",
                "tool_scope": "declarative host-facing tool boundary",
                "execution_steps": "ordered browser workflow requirements",
            },
        )

    def test_workspace_projection_contract_surface(self) -> None:
        contract = _load_json(WORKSPACE_PROJECTION_CONTRACT)

        self.assertEqual(contract["contract_id"], "workspace-projection")
        self.assertEqual(contract["endpoint"], "/api/workspace")
        self.assertEqual(
            contract["top_level_fields"],
            [
                "generated_at",
                "manifest_path",
                "objects_root",
                "buddies",
                "tracks",
                "standalone_tasks",
                "tasks",
                "artifacts",
                "run_audits",
            ],
        )
        self.assertEqual(
            contract["data_sources"],
            [
                "buddyswitch/manifest.toml",
                "buddyswitch/objects/tracks/*.json",
                "buddyswitch/objects/tasks/*.json",
                "buddyswitch/objects/artifacts/*.json",
                "buddyswitch/content/runs/*.json",
            ],
        )
        self.assertTrue(contract["read_only"])
        self.assertTrue(contract["no_snapshot_fallback"])
        self.assertEqual(contract["task_view_slot_field"], "current_artifacts")
        self.assertEqual(contract["track_view_missing_reference_field"], "missing_task_ids")

    def test_docs_reference_contract_files(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")
        interface_spec = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")

        self.assertIn("framework/contracts/switch-grammar.json", switch_spec)
        self.assertIn("framework/contracts/selected-skill-packet.json", switch_spec)
        self.assertIn("framework/contracts/workspace-projection.json", interface_spec)


if __name__ == "__main__":
    unittest.main()
