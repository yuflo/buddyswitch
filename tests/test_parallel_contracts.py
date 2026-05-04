#!/usr/bin/env python3
"""Freeze BuddySwitch parallel architecture external contract surfaces."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import turn_runtime  # noqa: E402
import workspace_data  # noqa: E402
from env_store import create_artifact, create_task, create_track  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


CONTRACTS_DIR = ROOT / "framework" / "contracts"
PREPARE_TURN_CONTEXT_CONTRACT = CONTRACTS_DIR / "prepare-turn-context.json"
PERSIST_SKILL_RESULT_CONTRACT = CONTRACTS_DIR / "persist-skill-result.json"
SELECTED_SKILL_PACKET_CONTRACT = CONTRACTS_DIR / "selected-skill-packet.json"
WORKSPACE_PROJECTION_CONTRACT = CONTRACTS_DIR / "workspace-projection.json"

EXPECTED_PREPARE_TURN_CONTEXT_CONTRACT = {
    "contract_id": "prepare-turn-context",
    "contract_version": "2026-05-03",
    "response_key_order": [
        "ok",
        "context_revision",
        "instance_id",
        "active_buddy",
        "request_text",
        "current_task_id",
        "current_track_id",
        "task_context",
        "track_context",
        "track_artifact_index",
        "run_envelope",
        "warnings",
    ],
}

EXPECTED_PERSIST_SKILL_RESULT_CONTRACT = {
    "contract_id": "persist-skill-result",
    "contract_version": "2026-05-03",
    "response_key_order": [
        "ok",
        "receipt",
        "refreshed_context",
    ],
    "receipt_required_keys": [
        "ok",
        "skill_id",
        "task_id",
        "task_title",
        "artifact_ids",
        "run_id",
        "next_state",
        "receipt_paths",
        "related_run_ids",
    ],
    "receipt_optional_keys": [
        "artifact_id",
        "track_id",
        "track_title",
        "track_action",
        "warnings",
    ],
}


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains_key_recursive(payload: object, forbidden_key: str) -> bool:
    forbidden_lower = forbidden_key.lower()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and forbidden_lower in key.lower():
                return True
            if _contains_key_recursive(value, forbidden_key):
                return True
        return False
    if isinstance(payload, list):
        return any(_contains_key_recursive(item, forbidden_key) for item in payload)
    if isinstance(payload, str):
        return forbidden_lower in payload.lower()
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
    def test_legacy_switch_grammar_contract_is_removed(self) -> None:
        legacy_contract = CONTRACTS_DIR / ("switch" + "-grammar.json")
        self.assertFalse(legacy_contract.exists())

    def test_selected_skill_packet_contract_is_retired(self) -> None:
        self.assertFalse(SELECTED_SKILL_PACKET_CONTRACT.exists())


class ResolveAndPersistContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _write_instance_json(self, *, instance_id: str, buddy: str) -> Path:
        instance_root = self.runtime_root / "instances" / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(instance_root / "workspace"),
                    "created_at": "2026-05-02T00:00:00Z",
                    "updated_at": "2026-05-02T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    @staticmethod
    def _product_env(instance_json: Path, *, buddy: str, instance_id: str, shared_root: Path) -> dict[str, str]:
        return {
            "BUDDYSWITCH_ACTIVE_BUDDY": buddy,
            "BUDDYSWITCH_INSTANCE_ID": instance_id,
            "BUDDYSWITCH_INSTANCE_JSON": str(instance_json),
            "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        }

    def _prepare(self, request_text: str, *, env: dict[str, str]) -> dict[str, object]:
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
        result: dict[str, object],
        env: dict[str, str],
    ) -> dict[str, object]:
        with patch.dict(os.environ, env, clear=True):
            return turn_runtime.persist_skill_result(
                context,
                skill_id=skill_id,  # type: ignore[arg-type]
                result=result,
                manifest_path=turn_runtime.DEFAULT_MANIFEST,
            )

    def _artifact_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": ["Scoped the edits to onboarding CTA behavior."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
                "verification": {
                    "checks_run": ["npm test"],
                    "passed": ["Targeted unit coverage."],
                    "failed": [],
                    "blocked": [],
                },
                "risks": ["No production build was executed in this test."],
                "follow_ups": [],
            },
        }

    def test_contract_matches_real_prepare_turn_context_surface(self) -> None:
        contract = _load_json(PREPARE_TURN_CONTEXT_CONTRACT)
        request_text = "Implement the approved onboarding improvements in projects/app"
        instance_json = self._write_instance_json(instance_id="inst-contract-01", buddy="dev")
        env = self._product_env(
            instance_json,
            buddy="dev",
            instance_id="inst-contract-01",
            shared_root=self.runtime_root,
        )

        payload = self._prepare(request_text, env=env)

        self.assertEqual(contract, EXPECTED_PREPARE_TURN_CONTEXT_CONTRACT)
        self.assertTrue(payload["ok"])
        self.assertEqual(list(payload.keys()), contract["response_key_order"])
        self.assertEqual(payload["request_text"], request_text)
        self.assertEqual(payload["current_task_id"], payload["task_context"]["task"]["id"])
        self.assertEqual(payload["run_envelope"]["status"], "reserved")
        self.assertIn("turn_identity", payload["run_envelope"])
        self.assertNotIn("switch", payload)
        self.assertNotIn("inputs", payload)
        self.assertNotIn("artifact_selection_by_skill", payload)
        self.assertNotIn("skills", payload)
        self.assertNotIn("inputs_by_skill", payload)
        for forbidden in (
            "selected_skill",
            "skill_candidates",
            "skill_instructions",
            "run_instructions_by_skill",
            "selected_skill_packet",
            "instruction_path",
        ):
            self.assertFalse(_contains_key_recursive(payload, forbidden), msg=f"forbidden prepare concept leaked: {forbidden}")

    def test_contract_matches_real_persist_skill_result_surface(self) -> None:
        contract = _load_json(PERSIST_SKILL_RESULT_CONTRACT)
        instance_json = self._write_instance_json(instance_id="inst-contract-02", buddy="dev")
        env = self._product_env(
            instance_json,
            buddy="dev",
            instance_id="inst-contract-02",
            shared_root=self.runtime_root,
        )
        context = self._prepare(
            "Implement the approved onboarding improvements in projects/app",
            env=env,
        )
        result = self._artifact_result()
        persisted = self._persist(
            context,
            skill_id="implement-task",
            result=result,
            env=env,
        )

        self.assertEqual(contract, EXPECTED_PERSIST_SKILL_RESULT_CONTRACT)
        self.assertTrue(persisted["ok"])
        self.assertEqual(list(persisted.keys()), contract["response_key_order"])
        receipt = persisted["receipt"]
        self.assertIsInstance(receipt, dict)
        if isinstance(receipt, dict):
            for key in contract["receipt_required_keys"]:
                self.assertIn(key, receipt)
            self.assertEqual(receipt["run_id"], context["run_envelope"]["run_id"])
            self.assertIsInstance(receipt["task_id"], str)
            self.assertTrue(receipt["task_id"])
            self.assertIsInstance(receipt["task_title"], str)
            self.assertTrue(receipt["task_title"])
            self.assertIsInstance(receipt["artifact_id"], str)
            self.assertIn(receipt["artifact_id"], receipt["artifact_ids"])
            self.assertIsInstance(receipt["receipt_paths"], dict)
            if isinstance(receipt["receipt_paths"], dict):
                for rel_path in receipt["receipt_paths"].values():
                    if isinstance(rel_path, str):
                        self.assertTrue(self._runtime_path(rel_path).exists())
                    elif isinstance(rel_path, list):
                        for item in rel_path:
                            if isinstance(item, str):
                                self.assertTrue(self._runtime_path(item).exists())
            self.assertEqual(receipt["next_state"]["task_id"], receipt["task_id"])
            self.assertNotIn("reference_switches", receipt)
            self.assertNotIn("recommended_switch", receipt)
        self.assertNotIn("skill_id", persisted)
        self.assertNotIn("task_id", persisted)
        self.assertNotIn("artifact_id", persisted)
        self.assertNotIn("run_id", persisted)
        self.assertNotIn("paths", persisted)
        self.assertNotIn("writes", persisted)

    def test_track_manager_persist_returns_receipt_without_artifact_id(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-contract-02-track", buddy="pm")
        env = self._product_env(
            instance_json,
            buddy="pm",
            instance_id="inst-contract-02-track",
            shared_root=self.runtime_root,
        )
        context = self._prepare("Create onboarding delivery track", env=env)
        persisted = self._persist(
            context,
            skill_id="track-manager",
            result={
                "execution_summary": "Created track for onboarding delivery.",
                "working_notes": ["Initialized track lifecycle."],
                "deliverables_or_changed_files": [],
                "track_operation": {
                    "action": "create",
                    "track_id": "track-onboarding-delivery",
                    "title": "Onboarding Delivery",
                    "status": "active",
                    "current_buddy": "pm",
                    "next_buddy": "design",
                    "summary": "Cross-functional onboarding execution track.",
                },
            },
            env=env,
        )

        self.assertTrue(persisted["ok"])
        receipt = persisted["receipt"]
        self.assertIsInstance(receipt, dict)
        if isinstance(receipt, dict):
            self.assertEqual(receipt.get("track_action"), "create")
            self.assertEqual(receipt.get("artifact_ids"), [])
            self.assertNotIn("artifact_id", receipt)
            self.assertIsInstance(receipt.get("track_id"), str)
            self.assertIsInstance(receipt.get("track_title"), str)

    def test_persist_contract_does_not_leave_hidden_follow_up_reservation(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-contract-03", buddy="dev")
        env = self._product_env(
            instance_json,
            buddy="dev",
            instance_id="inst-contract-03",
            shared_root=self.runtime_root,
        )
        context = self._prepare(
            "Implement the approved onboarding improvements in projects/app",
            env=env,
        )
        consumed_run_id = context["run_envelope"]["run_id"]
        consumed_path = turn_runtime._reserved_run_path(consumed_run_id)  # type: ignore[attr-defined]
        self.assertTrue(consumed_path.exists())

        persisted = self._persist(
            context,
            skill_id="implement-task",
            result=self._artifact_result(),
            env=env,
        )

        self.assertTrue(persisted["ok"])
        self.assertFalse(consumed_path.exists())
        self.assertNotIn("reference_switches", persisted["receipt"])
        self.assertNotIn("recommended_switch", persisted["receipt"])

        reserved_dir = turn_runtime._reserved_run_path("placeholder").parent  # type: ignore[attr-defined]
        remaining = sorted(reserved_dir.glob("*.json")) if reserved_dir.exists() else []
        self.assertEqual(remaining, [])

    def test_red_native_turn_persist_rejects_skill_array_without_side_effects(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-contract-04", buddy="market")
        env = self._product_env(
            instance_json,
            buddy="market",
            instance_id="inst-contract-04",
            shared_root=self.runtime_root,
        )
        context = self._prepare(
            "Validate an AI tool idea for indie developers",
            env=env,
        )
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_runs = {path.name for path in run_dir.glob("run-*.json")}
        before_artifacts = {path.name for path in artifact_dir.glob("art-*.json")}
        instance_before = instance_json.read_text(encoding="utf-8")

        with self.assertRaisesRegex((TypeError, ValueError), "single skill_id"):
            self._persist(
                context,
                skill_id=["pmf-recon"],  # type: ignore[arg-type]
                result={
                    "execution_summary": "Completed PMF recon",
                    "working_notes": [],
                    "deliverables_or_changed_files": [],
                    "artifact_content": {
                        "research_question": "Is there early demand?",
                        "research_strategy": {
                            "depth": "quick",
                            "rationale": "fast probe",
                            "collection_mode": "manual",
                            "initial_hypotheses": ["demand exists"],
                            "source_category_targets": ["forums"],
                        },
                        "channel_plan": ["forums"],
                        "iteration_log": [],
                        "evidence": [],
                        "source_traceability": [],
                        "assumptions_used": [],
                        "candidate_icps": [],
                        "strongest_pain_signals": [],
                        "existing_alternatives": [],
                        "why_current_solutions_fall_short": [],
                        "pmf_confidence": {"level": "low", "rationale": "no data"},
                        "recommended_next_step": {"action": "interviews", "rationale": "collect primary data"},
                        "suggested_interview_angles": [],
                        "risks_and_unknowns": [],
                        "conclusion": "insufficient evidence",
                    },
                },
                env=env,
            )

        self.assertEqual({path.name for path in run_dir.glob("run-*.json")}, before_runs)
        self.assertEqual({path.name for path in artifact_dir.glob("art-*.json")}, before_artifacts)
        self.assertEqual(instance_json.read_text(encoding="utf-8"), instance_before)


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
                    "active_buddy": "dev",
                    "current_task_id": tracked_task["id"],
                    "current_track_id": track["id"],
                    "request_text": "implement scope",
                    "resolved_task_id": tracked_task["id"],
                    "task_title": tracked_task["title"],
                    "skill_id": "implement-task",
                    "artifact_ids": [artifact["id"]],
                    "effective_track_id": track["id"],
                    "track_title": track["title"],
                    "track_action": "continue",
                    "execution_summary": "Completed implementation",
                    "related_run_ids": ["run-dev-contract-seed"],
                    "next_state": {
                        "task_id": tracked_task["id"],
                        "track_id": track["id"],
                        "current_buddy": "dev",
                        "next_buddy": "test",
                        "mode": "handoff",
                    },
                    "receipt_paths": {
                        "run": "buddyswitch/content/runs/run-dev-contract-freeze.json",
                        "task": f"buddyswitch/objects/tasks/{tracked_task['id']}.json",
                        "track": f"buddyswitch/objects/tracks/{track['id']}.json",
                        "artifacts": [f"buddyswitch/objects/artifacts/{artifact['id']}.json"],
                    },
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
        self.assertIn("next_state", payload["run_audits"][0])
        self.assertIn("receipt_paths", payload["run_audits"][0])
        self.assertNotIn("reference_switches", payload["run_audits"][0])
        self.assertNotIn("recommended_switch", payload["run_audits"][0])
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
