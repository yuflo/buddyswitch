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
PERSIST_BUDDY_RUN_CONTRACT = CONTRACTS_DIR / "persist-buddy-run.json"
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

EXPECTED_PERSIST_BUDDY_RUN_CONTRACT = {
    "contract_id": "persist-buddy-run",
    "contract_version": "2026-05-06",
    "request_boundary": "active_buddy + reserved run_id + current task/track context",
    "response_key_order": [
        "ok",
        "receipt",
        "refreshed_context",
    ],
    "commit_required_keys": [
        "execution_summary",
    ],
    "commit_optional_keys": [
        "working_notes",
        "artifacts",
        "state_effects",
        "handoff",
        "contributors",
        "tool_evidence",
    ],
    "receipt_required_keys": [
        "ok",
        "buddy_id",
        "task_id",
        "task_title",
        "artifact_ids",
        "run_id",
        "next_state",
        "receipt_paths",
        "related_run_ids",
    ],
    "receipt_optional_keys": [
        "track_id",
        "track_title",
        "track_action",
        "handoff",
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
    elif expected_type == "artifact-slot-map":
        test.assertIsInstance(value, dict)
    elif expected_type == "task-array":
        test.assertIsInstance(value, list)
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
        result: dict[str, object],
        env: dict[str, str],
    ) -> dict[str, object]:
        with patch.dict(os.environ, env, clear=True):
            return turn_runtime.persist_buddy_run(
                context,
                result=result,
                manifest_path=turn_runtime.DEFAULT_MANIFEST,
            )

    def _dev_commit(self) -> dict[str, object]:
        return {
            "execution_summary": "Implemented onboarding improvements and persisted dev report.",
            "working_notes": ["Focused on onboarding CTA behavior."],
            "artifacts": [
                {
                    "kind": "implementation-report",
                    "title": "Onboarding CTA Implementation Report",
                    "summary": "Implementation details and verification notes.",
                    "content": {
                        "task_summary": "Updated CTA behavior.",
                        "changed_files": ["projects/app/src/example.ts"],
                        "implementation_notes": ["Kept state transitions stable."],
                        "verification": {
                            "checks_run": ["npm test"],
                            "passed": ["Targeted unit tests"],
                            "failed": [],
                            "blocked": [],
                        },
                        "risks": [],
                        "follow_ups": [],
                    },
                }
            ],
            "contributors": {
                "skills": ["implement-task"],
                "agents": [],
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
        for forbidden in (
            "selected_skill",
            "skill_candidates",
            "skill_instructions",
            "run_instructions_by_skill",
            "selected_skill_packet",
            "instruction_path",
        ):
            self.assertFalse(_contains_key_recursive(payload, forbidden), msg=f"forbidden prepare concept leaked: {forbidden}")

    def test_contract_matches_real_persist_buddy_run_surface(self) -> None:
        contract = _load_json(PERSIST_BUDDY_RUN_CONTRACT)
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
        persisted = self._persist(
            context,
            result=self._dev_commit(),
            env=env,
        )

        self.assertEqual(contract, EXPECTED_PERSIST_BUDDY_RUN_CONTRACT)
        self.assertTrue(persisted["ok"])
        self.assertEqual(list(persisted.keys()), contract["response_key_order"])
        receipt = persisted["receipt"]
        self.assertIsInstance(receipt, dict)
        if isinstance(receipt, dict):
            for key in contract["receipt_required_keys"]:
                self.assertIn(key, receipt)
            self.assertEqual(receipt["run_id"], context["run_envelope"]["run_id"])
            self.assertEqual(receipt["buddy_id"], "dev")
            self.assertIsInstance(receipt["artifact_ids"], list)
            self.assertNotIn("skill_id", receipt)
            self.assertIsInstance(receipt["receipt_paths"], dict)
            if isinstance(receipt["receipt_paths"], dict):
                for rel_path in receipt["receipt_paths"].values():
                    if isinstance(rel_path, str):
                        self.assertTrue(self._runtime_path(rel_path).exists())
                    elif isinstance(rel_path, list):
                        for item in rel_path:
                            if isinstance(item, str):
                                self.assertTrue(self._runtime_path(item).exists())

        self.assertNotIn("skill_id", persisted)
        self.assertNotIn("artifact_id", persisted)
        self.assertNotIn("task_id", persisted)

    def test_persist_contract_clears_reservation_after_commit(self) -> None:
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
            result=self._dev_commit(),
            env=env,
        )

        self.assertTrue(persisted["ok"])
        self.assertFalse(consumed_path.exists())
        reserved_dir = turn_runtime._reserved_run_path("placeholder").parent  # type: ignore[attr-defined]
        remaining = sorted(reserved_dir.glob("*.json")) if reserved_dir.exists() else []
        self.assertEqual(remaining, [])

    def test_persist_rejects_legacy_top_level_skill_id_without_side_effects(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-contract-04", buddy="dev")
        env = self._product_env(
            instance_json,
            buddy="dev",
            instance_id="inst-contract-04",
            shared_root=self.runtime_root,
        )
        context = self._prepare(
            "Implement the approved onboarding improvements in projects/app",
            env=env,
        )
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_runs = {path.name for path in run_dir.glob("run-*.json")}
        before_artifacts = {path.name for path in artifact_dir.glob("art-*.json")}

        invalid = self._dev_commit()
        invalid["skill_id"] = "implement-task"

        with self.assertRaisesRegex((TypeError, ValueError), "skill_id"):
            self._persist(
                context,
                result=invalid,
                env=env,
            )

        self.assertEqual({path.name for path in run_dir.glob("run-*.json")}, before_runs)
        self.assertEqual({path.name for path in artifact_dir.glob("art-*.json")}, before_artifacts)


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
        create_task(
            "task-market-standalone-contract",
            "Standalone research",
            buddy="market",
            initial_run_id="run-market-contract-seed",
        )
        artifact = create_artifact(
            artifact_id="art-dev-contract-freeze",
            title="Implementation Report",
            buddy="dev",
            kind="implementation-report",
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
                    "buddy_id": "dev",
                    "task_id": tracked_task["id"],
                    "track_id": track["id"],
                    "task_title": tracked_task["title"],
                    "artifact_ids": [artifact["id"]],
                    "track_title": track["title"],
                    "track_action": "update",
                    "execution_summary": "Completed implementation",
                    "handoff": {
                        "next_buddy": "test",
                        "reason": "Needs smoke validation",
                        "context": "Use implementation report artifact",
                    },
                    "contributors": {
                        "skills": ["implement-task"],
                        "agents": [],
                    },
                    "state_effects": {},
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
                    "writes": [],
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
        self.assertNotIn("skill_id", payload["run_audits"][0])
        _assert_shape(self, payload["run_audits"][0], contract["view_shapes"]["run_audit"])
        _assert_shape(self, payload["tracks"][0]["tasks"][0], contract["view_shapes"]["task"])
        _assert_shape(
            self,
            task_rows[tracked_task["id"]]["current_artifacts"]["implementation-report"],
            contract["view_shapes"]["artifact"],
        )
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
