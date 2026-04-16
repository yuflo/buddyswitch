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

    def test_market_schema_rejects_suggested_next_switch(self) -> None:
        schema = output_schema.load_output_schema("framework/schemas/market/research-scan.json")
        payload = {
            "execution_summary": "Completed market scan",
            "working_notes": [],
            "deliverables_or_changed_files": [],
            "suggested_next_switch": "switch pm: scope the opportunity",
            "artifact_content": {
                "research_question": "Do founders need faster validation loops?",
                "research_strategy": {
                    "complexity_tier": "quick",
                    "rationale": "Boundary test only.",
                    "collection_mode": "browser-first",
                    "inclusion_notes": [],
                },
                "channel_plan": [],
                "iteration_log": [],
                "evidence": [],
                "source_traceability": [],
                "patterns_and_insights": [],
                "risks_and_caveats": [],
                "conclusion": "Too thin for a real conclusion.",
            },
        }

        self.assertNotEqual(output_schema.validate_output_payload(payload, schema), [])

    def test_market_schema_requires_medium_strength_evidence_fields(self) -> None:
        schema = output_schema.load_output_schema("framework/schemas/market/pmf-recon.json")
        payload = {
            "execution_summary": "Validated PMF signals",
            "working_notes": [],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Do founders need workflow validation help?",
                "research_strategy": {
                    "depth": "standard",
                    "rationale": "Test evidence boundaries.",
                    "collection_mode": "browser-native",
                    "initial_hypotheses": [],
                    "source_category_targets": [],
                },
                "channel_plan": [],
                "iteration_log": [],
                "evidence": [
                    {
                        "source_id": "src-1",
                        "url": "https://example.com/post",
                        "source_type": "forum",
                        "accessed_at": "2026-04-16T12:00:00+08:00",
                        "claim_excerpt": "This is painful.",
                        "segment": "founders",
                        "pain_category": "validation",
                    }
                ],
                "source_traceability": [{"conclusion": "Found demand.", "source_ids": ["src-1"]}],
                "assumptions_used": [],
                "candidate_icps": [],
                "strongest_pain_signals": [],
                "existing_alternatives": [],
                "why_current_solutions_fall_short": [],
                "pmf_confidence": {"level": "medium", "rationale": "Preliminary evidence only."},
                "recommended_next_step": {"action": "interviews", "rationale": "Need direct validation."},
                "suggested_interview_angles": [],
                "risks_and_unknowns": [],
                "conclusion": "Promising but incomplete.",
            },
        }

        errors = output_schema.validate_output_payload(payload, schema)

        self.assertIn(
            "$.artifact_content.evidence[0]: missing required property 'page_title'",
            errors,
        )
        self.assertIn(
            "$.artifact_content.evidence[0]: missing required property 'auth_state'",
            errors,
        )
        self.assertIn(
            "$.artifact_content.evidence[0]: missing required property 'query_or_filter_used'",
            errors,
        )
        self.assertIn(
            "$.artifact_content.evidence[0]: missing required property 'interaction_steps_summary'",
            errors,
        )
        self.assertIn(
            "$.artifact_content.evidence[0]: missing required property 'screenshot_ref_or_snapshot_ref'",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
