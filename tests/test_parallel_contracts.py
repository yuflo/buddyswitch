#!/usr/bin/env python3
"""Freeze BuddySwitch parallel architecture external contract surfaces."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import switch_runtime  # noqa: E402
import workspace_data  # noqa: E402
from env_store import create_artifact, create_task, create_track  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


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


class SelectedSkillPacketContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_contract_matches_real_prepare_execution_packet(self) -> None:
        contract = _load_json(SELECTED_SKILL_PACKET_CONTRACT)
        track = create_track(
            "track-contract-freeze-public",
            "Contract Freeze Public",
            current_buddy="market",
            next_buddy="pm",
        )
        prior_task = create_task(
            "task-market-prior",
            "Prior Artifacts",
            buddy="market",
            track_id=track["id"],
            initial_run_id="run-market-prior",
        )
        create_artifact(
            artifact_id="art-market-prior",
            title="Prior Artifacts",
            buddy="market",
            skill_id="research-scan",
            slot="prior-artifacts",
            task_id=prior_task["id"],
            source_run_id="run-market-prior",
            content={"ok": True},
        )

        with patch.object(switch_runtime, "ROOT", ROOT):
            resolved = switch_runtime.resolve_switch(
                "switch market -> track-contract-freeze-public: Validate whether indie developers need a lightweight demand-validation workflow before building"
            )
            prepared = switch_runtime.prepare_execution_payload(
                resolved,
                skill_id="research-scan",
            )

        packet = prepared["selected_skill_packet"]
        self.assertEqual(contract["contract_id"], "selected-skill-packet")
        self.assertEqual(list(prepared.keys()), contract["response_key_order"])
        self.assertEqual(list(packet.keys()), contract["packet_key_order"])
        self.assertEqual(
            list(packet["skill_instructions"].keys()),
            contract["nested_shapes"]["skill_instructions"]["key_order"],
        )
        self.assertEqual(
            list(packet["selected_inputs"][0].keys()),
            contract["nested_shapes"]["selected_input_item"]["key_order"],
        )
        self.assertEqual(
            list(packet["execution_constraints"].keys()),
            contract["nested_shapes"]["execution_constraints"]["key_order"],
        )
        self.assertEqual(
            list(packet["tool_scope"].keys()),
            contract["nested_shapes"]["tool_scope"]["key_order"],
        )
        self.assertEqual(
            packet["execution_constraints"],
            contract["nested_shapes"]["execution_constraints"]["market_required_values"],
        )
        self.assertEqual(
            packet["tool_scope"],
            contract["nested_shapes"]["tool_scope"]["market_required_values"],
        )
        self.assertEqual(
            packet["execution_steps"],
            contract["nested_shapes"]["execution_steps"]["market_required_values"],
        )
        self.assertEqual(
            prepared["host_next_actions"],
            contract["host_next_actions"],
        )

    def test_docs_point_to_contract_without_restating_packet_field_lists(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")

        self.assertIn("framework/contracts/switch-grammar.json", switch_spec)
        self.assertIn("framework/contracts/selected-skill-packet.json", switch_spec)
        self.assertNotIn("The packet fields are stable:", switch_spec)
        self.assertNotIn("- `skill_id`", switch_spec)


class WorkspaceProjectionContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_contract_matches_real_workspace_projection(self) -> None:
        contract = _load_json(WORKSPACE_PROJECTION_CONTRACT)

        track = create_track("track-contract-freeze", "Contract Freeze Track", current_buddy="dev", next_buddy="test")
        tracked_task = create_task(
            "task-dev-contract-freeze",
            "Implement contract freeze",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-dev-contract-seed",
        )
        standalone_task = create_task(
            "task-market-standalone-contract",
            "Standalone research",
            buddy="market",
            initial_run_id="run-market-contract-seed",
        )
        artifact = create_artifact(
            artifact_id="art-dev-contract-freeze",
            title="Implementation Report",
            buddy="dev",
            skill_id="implement-task",
            slot="implementation-report",
            task_id=tracked_task["id"],
            source_run_id="run-dev-contract-freeze",
            summary="Implementation summary",
            content={"result": "ok"},
        )
        run_path = self._runtime_path("buddyswitch/content/runs/run-dev-contract-freeze.json")
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(
            json.dumps(
                {
                    "run_id": "run-dev-contract-freeze",
                    "timestamp": "2026-04-21T12:00:00+08:00",
                    "switch": {
                        "buddy": "dev",
                        "task_id": tracked_task["id"],
                        "track_id": track["id"],
                        "demand": "implement scope",
                    },
                    "resolved_task_id": tracked_task["id"],
                    "task_title": tracked_task["title"],
                    "skill_id": "implement-task",
                    "artifact_ids": [artifact["id"]],
                    "effective_track_id": track["id"],
                    "track_title": track["title"],
                    "track_action": "continue",
                    "execution_summary": "Completed implementation",
                    "reference_switches": {"upstream": "switch pm: handoff implementation"},
                    "related_run_ids": ["run-dev-contract-seed"],
                    "recommended_switch": "switch test: verify contract freeze",
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        payload = workspace_data.build_workspace_data()
        task_rows = {task["id"]: task for task in payload["tasks"]}

        self.assertEqual(contract["contract_id"], "workspace-projection")
        self.assertEqual(list(payload.keys()), contract["top_level_key_order"])
        self.assertEqual(
            list(payload["buddies"][0].keys()),
            contract["view_shapes"]["buddy"]["key_order"],
        )
        self.assertEqual(
            list(payload["tracks"][0].keys()),
            contract["view_shapes"]["track"]["key_order"],
        )
        self.assertEqual(
            list(task_rows[tracked_task["id"]].keys()),
            contract["view_shapes"]["task"]["key_order"],
        )
        self.assertEqual(
            list(payload["artifacts"][0].keys()),
            contract["view_shapes"]["artifact"]["key_order"],
        )
        self.assertEqual(
            list(payload["run_audits"][0].keys()),
            contract["view_shapes"]["run_audit"]["key_order"],
        )
        self.assertEqual(
            list(payload["tracks"][0]["tasks"][0].keys()),
            contract["view_shapes"]["task"]["key_order"],
        )
        self.assertEqual(
            list(task_rows[tracked_task["id"]]["current_artifacts"]["implementation-report"].keys()),
            contract["view_shapes"]["artifact"]["key_order"],
        )
        self.assertEqual(
            sorted(payload["standalone_tasks"][0].keys()),
            sorted(contract["view_shapes"]["task"]["key_order"]),
        )
        self.assertEqual(contract["derived_invariants"]["task_view_slot_field"], "current_artifacts")
        self.assertEqual(contract["derived_invariants"]["track_view_missing_reference_field"], "missing_task_ids")
        self.assertEqual(contract["derived_invariants"]["current_artifacts_value_shape"], "artifact")
        self.assertTrue(contract["read_only"])
        self.assertTrue(contract["no_snapshot_fallback"])
        self.assertEqual(payload["manifest_path"], "buddyswitch/manifest.toml")
        self.assertEqual(payload["objects_root"], "buddyswitch/objects")

    def test_docs_point_to_contract_without_restating_workspace_source_lists(self) -> None:
        interface_spec = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")

        self.assertIn("framework/contracts/workspace-projection.json", interface_spec)
        self.assertNotIn("- `buddyswitch/manifest.toml`", interface_spec)
        self.assertNotIn("- `buddyswitch/objects/tracks/*.json`", interface_spec)


if __name__ == "__main__":
    unittest.main()
