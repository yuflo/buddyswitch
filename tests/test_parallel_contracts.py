#!/usr/bin/env python3
"""Freeze BuddySwitch parallel architecture external contract surfaces."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


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
RESOLVE_CONTEXT_CONTRACT = CONTRACTS_DIR / "resolve-context.json"
PERSIST_SKILL_RESULT_CONTRACT = CONTRACTS_DIR / "persist-skill-result.json"
SELECTED_SKILL_PACKET_CONTRACT = CONTRACTS_DIR / "selected-skill-packet.json"
WORKSPACE_PROJECTION_CONTRACT = CONTRACTS_DIR / "workspace-projection.json"

EXPECTED_RESOLVE_CONTEXT_CONTRACT = {
    "contract_id": "resolve-context",
    "contract_version": "2026-04-22",
    "response_key_order": [
        "ok",
        "context_revision",
        "switch",
        "buddy",
        "authority",
        "task_resolution",
        "run_envelope",
        "task_context",
        "track_context",
        "inputs",
        "skills",
        "warnings",
    ],
}

EXPECTED_PERSIST_SKILL_RESULT_CONTRACT = {
    "contract_id": "persist-skill-result",
    "contract_version": "2026-04-22",
    "response_key_order": [
        "ok",
        "receipt",
        "refreshed_context",
    ],
}


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains_key_recursive(payload: object, forbidden_key: str) -> bool:
    if isinstance(payload, dict):
        if forbidden_key in payload:
            return True
        return any(_contains_key_recursive(value, forbidden_key) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_key_recursive(item, forbidden_key) for item in payload)
    return False


def _assert_type_case(test: unittest.TestCase, value: object, expected_type: str) -> None:
    if expected_type == "string":
        test.assertIsInstance(value, str)
    elif expected_type == "string-or-null":
        test.assertTrue(value is None or isinstance(value, str))
    elif expected_type == "integer":
        test.assertIsInstance(value, int)
    elif expected_type == "integer-or-null":
        test.assertTrue(value is None or isinstance(value, int))
    elif expected_type == "boolean":
        test.assertIsInstance(value, bool)
    elif expected_type == "object":
        test.assertIsInstance(value, dict)
    elif expected_type == "string-array":
        test.assertIsInstance(value, list)
        test.assertTrue(all(isinstance(item, str) for item in value))
    elif expected_type == "repo-relative-path":
        test.assertIsInstance(value, str)
        test.assertFalse(Path(value).is_absolute())
    elif expected_type == "basename":
        test.assertIsInstance(value, str)
        test.assertEqual(Path(value).name, value)
    elif expected_type == "artifact-map":
        test.assertIsInstance(value, dict)
    elif expected_type == "task-array":
        test.assertIsInstance(value, list)
    elif expected_type == "artifact-map":
        test.assertIsInstance(value, dict)
    elif expected_type == "artifact-slot-map":
        test.assertIsInstance(value, dict)
    elif expected_type == "string-map":
        test.assertIsInstance(value, dict)
        test.assertTrue(all(isinstance(item, str) for item in value.values()))
    elif expected_type == "markdown-string":
        test.assertIsInstance(value, str)
        test.assertTrue(value.startswith("# "))
    else:
        raise AssertionError(f"unsupported expected type {expected_type!r}")


def _assert_field_types(
    test: unittest.TestCase,
    payload: dict[str, object],
    field_types: dict[str, str],
) -> None:
    for field, expected_type in field_types.items():
        test.assertIn(field, payload)
        _assert_type_case(test, payload[field], expected_type)


def _assert_shape(
    test: unittest.TestCase,
    payload: dict[str, object],
    shape_contract: dict[str, object],
) -> None:
    test.assertEqual(list(payload.keys()), shape_contract["key_order"])
    _assert_field_types(test, payload, shape_contract["field_types"])


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

    def test_selected_skill_packet_contract_is_retired(self) -> None:
        self.assertFalse(SELECTED_SKILL_PACKET_CONTRACT.exists())


class ResolveAndPersistContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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

    def test_contract_matches_real_resolve_context_surface(self) -> None:
        contract = _load_json(RESOLVE_CONTEXT_CONTRACT)

        payload = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertEqual(contract, EXPECTED_RESOLVE_CONTEXT_CONTRACT)
        self.assertTrue(payload["ok"])
        self.assertEqual(list(payload.keys()), contract["response_key_order"])
        self.assertEqual(payload["task_resolution"]["task_id"], payload["task_context"]["task"]["id"])
        self.assertEqual(payload["run_envelope"]["status"], "reserved")
        self.assertIsNone(payload["run_envelope"]["previous_run_id"])
        self.assertNotIn("eligible_skills", payload)
        self.assertNotIn("implicit_skill_id", payload)
        self.assertFalse(_contains_key_recursive(payload, "selected_skill_packet"))

    def test_contract_matches_real_persist_skill_result_surface(self) -> None:
        contract = _load_json(PERSIST_SKILL_RESULT_CONTRACT)
        context = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        result = self._artifact_result()
        persisted = switch_runtime.persist_skill_result(
            context,
            skill_id="implement-task",
            result=result,
        )

        self.assertEqual(contract, EXPECTED_PERSIST_SKILL_RESULT_CONTRACT)
        self.assertTrue(persisted["ok"])
        self.assertEqual(list(persisted.keys()), contract["response_key_order"])
        self.assertEqual(persisted["receipt"]["run_id"], context["run_envelope"]["run_id"])
        self.assertEqual(
            persisted["refreshed_context"]["run_envelope"]["previous_run_id"],
            persisted["receipt"]["run_id"],
        )
        self.assertEqual(persisted["refreshed_context"]["run_envelope"]["status"], "reserved")
        self.assertNotIn("skill_id", persisted)
        self.assertNotIn("task_id", persisted)
        self.assertNotIn("artifact_id", persisted)
        self.assertNotIn("run_id", persisted)
        self.assertNotIn("paths", persisted)
        self.assertNotIn("writes", persisted)


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
        _assert_type_case(
            self,
            payload["manifest_path"],
            contract["field_constraints"]["manifest_path"]["type"],
        )
        self.assertEqual(payload["manifest_path"], contract["field_constraints"]["manifest_path"]["exact"])
        _assert_type_case(
            self,
            payload["objects_root"],
            contract["field_constraints"]["objects_root"]["type"],
        )
        self.assertEqual(payload["objects_root"], contract["field_constraints"]["objects_root"]["exact"])
        _assert_shape(self, payload["buddies"][0], contract["view_shapes"]["buddy"])
        _assert_shape(self, payload["tracks"][0], contract["view_shapes"]["track"])
        _assert_shape(self, task_rows[tracked_task["id"]], contract["view_shapes"]["task"])
        _assert_shape(self, payload["artifacts"][0], contract["view_shapes"]["artifact"])
        _assert_shape(self, payload["run_audits"][0], contract["view_shapes"]["run_audit"])
        _assert_shape(self, payload["tracks"][0]["tasks"][0], contract["view_shapes"]["task"])
        _assert_shape(
            self,
            task_rows[tracked_task["id"]]["current_artifacts"]["implementation-report"],
            contract["view_shapes"]["artifact"],
        )
        self.assertEqual(
            sorted(payload["standalone_tasks"][0].keys()),
            sorted(contract["view_shapes"]["task"]["key_order"]),
        )
        _assert_field_types(self, payload["standalone_tasks"][0], contract["view_shapes"]["task"]["field_types"])
        self.assertEqual(
            list(task_rows[tracked_task["id"]]["artifact_slots"]["implementation-report"].keys()),
            contract["view_shapes"]["task"]["artifact_slot_entry"]["key_order"],
        )
        _assert_field_types(
            self,
            task_rows[tracked_task["id"]]["artifact_slots"]["implementation-report"],
            contract["view_shapes"]["task"]["artifact_slot_entry"]["field_types"],
        )
        self.assertEqual(contract["derived_invariants"]["task_view_slot_field"], "current_artifacts")
        self.assertEqual(contract["derived_invariants"]["track_view_missing_reference_field"], "missing_task_ids")
        self.assertEqual(contract["derived_invariants"]["current_artifacts_value_shape"], "artifact")
        self.assertTrue(contract["read_only"])
        self.assertTrue(contract["no_snapshot_fallback"])

    def test_docs_point_to_contract_without_restating_workspace_source_lists(self) -> None:
        interface_spec = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")

        self.assertIn("framework/contracts/workspace-projection.json", interface_spec)
        self.assertNotIn("- `buddyswitch/manifest.toml`", interface_spec)
        self.assertNotIn("- `buddyswitch/objects/tracks/*.json`", interface_spec)


if __name__ == "__main__":
    unittest.main()
