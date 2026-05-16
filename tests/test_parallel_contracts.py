#!/usr/bin/env python3
"""Runless parallel contract coverage for workspace projection surfaces."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import workspace_data  # noqa: E402

_RETIRED_BUDDYBOX_FILE_ROWS_FIELD = "buddybox_" + "files"
from env_store import create_artifact, create_handoff, create_task, create_track  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


CONTRACTS_DIR = ROOT / "framework" / "contracts"
WORKSPACE_PROJECTION_CONTRACT = CONTRACTS_DIR / "workspace-projection.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_type_case(test: unittest.TestCase, value: object, expected_type: str) -> None:
    if expected_type == "string":
        test.assertIsInstance(value, str)
        return
    if expected_type == "string-or-null":
        test.assertTrue(value is None or isinstance(value, str))
        return
    if expected_type == "integer":
        test.assertIsInstance(value, int)
        return
    if expected_type == "boolean":
        test.assertIsInstance(value, bool)
        return
    if expected_type == "object":
        test.assertIsInstance(value, dict)
        return
    if expected_type == "string-array":
        test.assertIsInstance(value, list)
        test.assertTrue(all(isinstance(item, str) for item in value))
        return
    if expected_type == "object-array-or-null":
        test.assertTrue(value is None or (isinstance(value, list) and all(isinstance(item, dict) for item in value)))
        return
    if expected_type == "repo-relative-path":
        test.assertIsInstance(value, str)
        test.assertFalse(Path(value).is_absolute())
        return
    if expected_type == "basename":
        test.assertIsInstance(value, str)
        test.assertEqual(Path(value).name, value)
        return
    if expected_type == "artifact-map":
        test.assertIsInstance(value, dict)
        return
    if expected_type == "artifact-slot-map":
        test.assertIsInstance(value, dict)
        return
    if expected_type == "task-array":
        test.assertIsInstance(value, list)
        return
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
    def test_legacy_parallel_contract_files_are_removed(self) -> None:
        retired = (
            CONTRACTS_DIR / ("persist-buddy-" + "run.json"),
            CONTRACTS_DIR / "selected-skill-packet.json",
        )
        for path in retired:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertFalse(path.exists())


class WorkspaceProjectionContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_contract_matches_runless_workspace_projection(self) -> None:
        contract = _load_json(WORKSPACE_PROJECTION_CONTRACT)

        track = create_track("track-contract-freeze", "Contract Freeze Track", current_buddy="dev", next_buddy="test")
        tracked_task = create_task(
            "task-dev-contract-freeze",
            "Implement contract freeze",
            buddy="dev",
            track_id=track["id"],
        )
        artifact = create_artifact(
            artifact_id="art-dev-contract-freeze",
            title="Implementation Report",
            buddy="dev",
            kind="implementation-report",
            task_id=tracked_task["id"],
            summary="Implementation summary",
            content={"result": "ok"},
            created_by="dev",
            source_refs=[{"type": "note", "label": "contract freeze"}],
        )
        create_handoff(
            handoff_id="handoff-dev-test-contract-freeze",
            track_id=track["id"],
            source_buddy="dev",
            target_buddy="test",
            source_task_id=tracked_task["id"],
            artifact_ids=[artifact["id"]],
            source_refs=[{"type": "artifact", "id": artifact["id"]}],
            reason="Need test validation.",
            context="Run focused test suite.",
            status="active",
        )

        payload = workspace_data.build_workspace_data()
        self.assertEqual(contract["contract_id"], "workspace-projection")
        self.assertEqual(list(payload.keys()), contract["top_level_key_order"])
        self.assertNotIn("run_audits", payload)
        self.assertNotIn("memories", payload)

        _assert_type_case(self, payload["manifest_path"], contract["field_constraints"]["manifest_path"]["type"])
        _assert_type_case(self, payload["objects_root"], contract["field_constraints"]["objects_root"]["type"])
        self.assertEqual(payload["manifest_path"], contract["field_constraints"]["manifest_path"]["exact"])
        self.assertEqual(payload["objects_root"], contract["field_constraints"]["objects_root"]["exact"])
        self.assertNotIn("content_root", payload)

        self.assertGreaterEqual(len(payload["buddies"]), 1)
        self.assertGreaterEqual(len(payload["tracks"]), 1)
        self.assertGreaterEqual(len(payload["tasks"]), 1)
        self.assertGreaterEqual(len(payload["artifacts"]), 1)
        self.assertGreaterEqual(len(payload["handoffs"]), 1)
        self.assertNotIn(_RETIRED_BUDDYBOX_FILE_ROWS_FIELD, payload)

        _assert_shape(self, payload["buddies"][0], contract["view_shapes"]["buddy"])
        _assert_shape(self, payload["tracks"][0], contract["view_shapes"]["track"])
        _assert_shape(self, payload["tasks"][0], contract["view_shapes"]["task"])
        _assert_shape(self, payload["artifacts"][0], contract["view_shapes"]["artifact"])
        _assert_shape(self, payload["handoffs"][0], contract["view_shapes"]["handoff"])

        task_rows = {task["id"]: task for task in payload["tasks"]}
        task_row = task_rows[tracked_task["id"]]
        self.assertNotIn("run_ids", task_row)
        self.assertNotIn("latest_run_id", task_row)
        self.assertIn("current_artifacts", task_row)

        artifact_row = next(row for row in payload["artifacts"] if row["id"] == artifact["id"])
        self.assertIn("created_by", artifact_row)
        self.assertIn("source_refs", artifact_row)
        self.assertNotIn("source_run_id", artifact_row)

    def test_readme_points_to_workspace_projection_contract(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contract = _load_json(WORKSPACE_PROJECTION_CONTRACT)
        self.assertIn("framework/contracts/workspace-projection.json", readme)
        self.assertEqual(contract["contract_id"], "workspace-projection")
        top_keys = set(contract["top_level_key_order"])
        self.assertIn("handoffs", top_keys)
        self.assertNotIn("memories", top_keys)
        self.assertNotIn("run_audits", top_keys)
        self.assertNotIn("content_root", top_keys)


if __name__ == "__main__":
    unittest.main()
