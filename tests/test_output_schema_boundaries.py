#!/usr/bin/env python3
"""Boundary checks for BuddySwitch output schema validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import output_schema  # noqa: E402


class OutputSchemaBoundaryTests(unittest.TestCase):
    def test_normalize_schema_path_rejects_parent_escape(self) -> None:
        with self.assertRaisesRegex(output_schema.OutputSchemaError, "repo-relative"):
            output_schema.normalize_schema_path("../framework/schemas/dev/implement-task.json")

    def test_normalize_schema_path_rejects_wrong_root(self) -> None:
        with self.assertRaisesRegex(output_schema.OutputSchemaError, "under framework/schemas/"):
            output_schema.normalize_schema_path("schemas/dev/implement-task.json")

    def test_validate_reports_missing_required_property(self) -> None:
        schema = {
            "type": "object",
            "required": ["execution_summary"],
            "properties": {"execution_summary": {"type": "string"}},
        }

        errors = output_schema.validate_output_payload({}, schema)

        self.assertEqual(errors, ["$: missing required property 'execution_summary'"])

    def test_validate_reports_type_and_enum_mismatch(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["passed", "failed"]},
                "count": {"type": "integer"},
            },
        }

        errors = output_schema.validate_output_payload({"status": "unknown", "count": "3"}, schema)

        self.assertIn("$.status: value 'unknown' is not in enum ['passed', 'failed']", errors)
        self.assertIn("$.count: expected integer, got str", errors)

    def test_validate_reports_additional_properties_when_forbidden(self) -> None:
        schema = {
            "type": "object",
            "properties": {"execution_summary": {"type": "string"}},
            "additionalProperties": False,
        }

        errors = output_schema.validate_output_payload(
            {"execution_summary": "done", "extra": "unexpected"},
            schema,
        )

        self.assertEqual(errors, ["$: unsupported property 'extra'"])

    def test_validate_reports_min_items(self) -> None:
        schema = {"type": "array", "minItems": 2, "items": {"type": "string"}}

        errors = output_schema.validate_output_payload(["only-one"], schema)

        self.assertEqual(errors, ["$: expected at least 2 item(s), got 1"])

    def test_structure_validator_does_not_impose_business_quality_rules(self) -> None:
        schema = {
            "type": "object",
            "required": ["execution_summary"],
            "properties": {"execution_summary": {"type": "string"}},
        }

        errors = output_schema.validate_output_payload({"execution_summary": "ok"}, schema)

        self.assertEqual(errors, [])

    def test_dev_schema_rejects_suggested_next_switch(self) -> None:
        schema = output_schema.load_output_schema("framework/schemas/dev/implement-task.json")
        payload = {
            "execution_summary": "Implemented onboarding flow",
            "working_notes": [],
            "deliverables_or_changed_files": ["projects/app/src/onboarding.tsx"],
            "suggested_next_switch": "switch test: run smoke",
            "artifact_content": {
                "task_summary": "Implemented onboarding flow",
                "changed_files": ["projects/app/src/onboarding.tsx"],
                "implementation_notes": [],
                "verification_runs": [],
                "known_limitations": [],
            },
        }
        self.assertNotEqual(output_schema.validate_output_payload(payload, schema), [])


if __name__ == "__main__":
    unittest.main()
