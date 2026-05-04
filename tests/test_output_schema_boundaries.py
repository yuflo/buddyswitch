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

BUDDY_RESULT_SCHEMA_PATHS = {
    "pm": ROOT / "framework" / "schemas" / "pm" / "pm-result.json",
    "dev": ROOT / "framework" / "schemas" / "dev" / "dev-result.json",
    "test": ROOT / "framework" / "schemas" / "test" / "test-result.json",
    "market": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    "design": ROOT / "framework" / "schemas" / "design" / "design-result.json",
}

COMMON_ENVELOPE_KEYS = {
    "execution_summary",
    "working_notes",
    "deliverables_or_changed_files",
    "artifact_content",
}

RUNTIME_METADATA_FIELDS = {
    "task_id",
    "task_title",
    "track_id",
    "track_title",
    "artifact_id",
    "artifact_ids",
    "run_id",
    "receipt_paths",
    "related_run_ids",
    "next_state",
    "paths",
    "writes",
}

BUDDY_ARTIFACT_REQUIRED_FIELDS = {
    "pm": {
        "summary",
        "decisions",
        "risks",
        "open_questions",
        "suggested_next_step",
        "specialized_sections",
    },
    "dev": {
        "task_summary",
        "changed_files",
        "implementation_notes",
        "verification",
        "risks",
        "follow_ups",
    },
    "test": {
        "test_scope",
        "checks_run",
        "passed_items",
        "failed_items",
        "blocked_items",
        "reproduction_notes",
        "readiness",
    },
    "market": {
        "research_question",
        "evidence",
        "insights",
        "assumptions",
        "risks",
        "conclusion",
        "recommended_next_step",
        "specialized_sections",
    },
    "design": {
        "design_goal",
        "flow_or_screen_summary",
        "interaction_notes",
        "assets_or_preview_refs",
        "handoff_notes",
        "open_questions",
    },
}


class OutputSchemaBoundaryTests(unittest.TestCase):
    def _load_buddy_schema(self, buddy_id: str) -> dict[str, object]:
        path = BUDDY_RESULT_SCHEMA_PATHS[buddy_id].relative_to(ROOT).as_posix()
        return output_schema.load_output_schema(path)

    def _sample_payload_for_buddy(self, buddy_id: str) -> dict[str, object]:
        artifact_content_by_buddy: dict[str, dict[str, object]] = {
            "pm": {
                "summary": "PRD summary",
                "decisions": ["Ship guided flow first."],
                "risks": ["Copy may still be unclear."],
                "open_questions": ["Need localization in v1?"],
                "suggested_next_step": "Hand off to design for flow draft.",
                "specialized_sections": {
                    "prd": {
                        "problem": "Users cannot complete onboarding quickly.",
                        "user_value": "Faster onboarding completion.",
                        "requirements": ["Define scope", "Capture acceptance criteria"],
                        "scope": {"in_scope": ["Onboarding copy"], "out_of_scope": ["Billing refactor"]},
                    }
                },
            },
            "dev": {
                "task_summary": "Implemented onboarding banner behavior.",
                "changed_files": ["projects/app/main.js"],
                "implementation_notes": ["Kept state mutation local."],
                "verification": {
                    "checks_run": ["python3 -m pytest tests/test_turn_runtime.py -q"],
                    "passed": ["Runtime tests passed"],
                    "failed": [],
                    "blocked": [],
                },
                "risks": ["Browser smoke not executed."],
                "follow_ups": ["Run manual browser check."],
            },
            "test": {
                "test_scope": "Smoke validation for onboarding path.",
                "checks_run": ["npm test -- smoke"],
                "passed_items": ["Core route loads"],
                "failed_items": [],
                "blocked_items": [],
                "reproduction_notes": [],
                "readiness": "ready",
            },
            "market": {
                "research_question": "Do founders need faster validation loops?",
                "evidence": ["Interview themes from founder calls."],
                "insights": ["Speed and confidence are both required."],
                "assumptions": ["SMB focus remains stable."],
                "risks": ["Sample size still small."],
                "conclusion": "Demand appears real but incomplete.",
                "recommended_next_step": "Run 5 targeted interviews.",
                "specialized_sections": {
                    "pmf_recon": {"candidate_icps": ["B2B SaaS founders"]},
                },
            },
            "design": {
                "design_goal": "Clarify onboarding decisions.",
                "flow_or_screen_summary": "Single-step guidance panel in setup flow.",
                "interaction_notes": ["Primary CTA keeps user in context."],
                "assets_or_preview_refs": ["runs/raw/design-preview.png"],
                "handoff_notes": ["Include empty/loading states."],
                "open_questions": ["Need accessibility review before handoff?"],
            },
        }
        return {
            "execution_summary": f"{buddy_id} result summary",
            "working_notes": ["Focused on buddy-level schema contract."],
            "deliverables_or_changed_files": ["runs/raw/result.json"],
            "artifact_content": artifact_content_by_buddy[buddy_id],
        }

    def test_buddy_result_schema_boundary_is_exactly_five_buddies(self) -> None:
        self.assertEqual(set(BUDDY_RESULT_SCHEMA_PATHS), {"pm", "dev", "test", "market", "design"})

    def test_normalize_schema_path_rejects_parent_escape(self) -> None:
        with self.assertRaisesRegex(output_schema.OutputSchemaError, "repo-relative"):
            output_schema.normalize_schema_path("../framework/schemas/dev/invalid-schema.json")

    def test_normalize_schema_path_rejects_wrong_root(self) -> None:
        with self.assertRaisesRegex(output_schema.OutputSchemaError, "under framework/schemas/"):
            output_schema.normalize_schema_path("schemas/dev/invalid-schema.json")

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

    def test_buddy_result_schema_requires_common_envelope_and_blocks_runtime_metadata(self) -> None:
        for buddy_id in BUDDY_RESULT_SCHEMA_PATHS:
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                required = schema.get("required")
                self.assertEqual(set(required), COMMON_ENVELOPE_KEYS)
                self.assertFalse(schema.get("additionalProperties"))

                properties = schema.get("properties")
                self.assertIsInstance(properties, dict)
                assert isinstance(properties, dict)
                self.assertTrue(COMMON_ENVELOPE_KEYS.issubset(set(properties)))
                for runtime_field in RUNTIME_METADATA_FIELDS:
                    self.assertNotIn(runtime_field, properties)
                self.assertEqual(properties["artifact_content"].get("type"), "object")

    def test_buddy_result_schema_requires_expected_artifact_content_fields(self) -> None:
        for buddy_id, expected_fields in BUDDY_ARTIFACT_REQUIRED_FIELDS.items():
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                properties = schema.get("properties")
                self.assertIsInstance(properties, dict)
                assert isinstance(properties, dict)
                artifact_content = properties.get("artifact_content")
                self.assertIsInstance(artifact_content, dict)
                assert isinstance(artifact_content, dict)
                required = artifact_content.get("required")
                self.assertIsInstance(required, list)
                assert isinstance(required, list)
                self.assertEqual(set(required), expected_fields)

    def test_buddy_result_schema_rejects_runtime_metadata_top_level_fields(self) -> None:
        for buddy_id in BUDDY_RESULT_SCHEMA_PATHS:
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                payload = self._sample_payload_for_buddy(buddy_id)
                payload["task_id"] = "task-should-not-be-present"
                errors = output_schema.validate_output_payload(payload, schema)
                self.assertIn("$: unsupported property 'task_id'", errors)

    def test_market_result_schema_allows_specialized_sections_extension(self) -> None:
        schema = self._load_buddy_schema("market")
        payload = self._sample_payload_for_buddy("market")
        payload["artifact_content"]["specialized_sections"] = {
            "research_scan": {"channel_plan": ["founder communities"]},
            "launch_prep": {"launch_window": "2026-Q3"},
        }
        self.assertEqual(output_schema.validate_output_payload(payload, schema), [])

    def test_market_result_schema_accepts_examples_for_all_current_market_skills(self) -> None:
        schema = self._load_buddy_schema("market")
        base = self._sample_payload_for_buddy("market")
        specialized_cases = {
            "research-scan": {"research_scan": {"source_traceability": [{"source_id": "src-1"}]}},
            "pmf-recon": {"pmf_recon": {"candidate_icps": ["SMB founders"]}},
            "customer-discovery": {"customer_discovery": {"interview_targets": ["PM lead", "Founding engineer"]}},
            "positioning-copy": {"positioning_copy": {"message_pillars": ["faster validation", "less guesswork"]}},
            "channel-discovery": {"channel_discovery": {"channel_plan": ["Founder forums", "Slack groups"]}},
            "launch-prep": {"launch_prep": {"launch_checklist": ["docs final", "pilot outreach"]}},
        }
        for skill_id, specialized_sections in specialized_cases.items():
            with self.subTest(skill=skill_id):
                payload = {
                    "execution_summary": base["execution_summary"],
                    "working_notes": list(base["working_notes"]),
                    "deliverables_or_changed_files": list(base["deliverables_or_changed_files"]),
                    "artifact_content": dict(base["artifact_content"]),
                }
                artifact_content = dict(payload["artifact_content"])
                artifact_content["specialized_sections"] = specialized_sections
                payload["artifact_content"] = artifact_content
                self.assertEqual(output_schema.validate_output_payload(payload, schema), [])

    def test_only_pm_schema_accepts_track_operation_state_effect(self) -> None:
        pm_schema = self._load_buddy_schema("pm")
        pm_payload = self._sample_payload_for_buddy("pm")
        pm_payload["state_effects"] = {
            "track_operation": {
                "action": "advance",
                "track_id": "track-onboarding",
                "next_buddy": "dev",
            }
        }
        self.assertEqual(output_schema.validate_output_payload(pm_payload, pm_schema), [])

        for buddy_id in ("dev", "test", "market", "design"):
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                payload = self._sample_payload_for_buddy(buddy_id)
                payload["state_effects"] = {
                    "track_operation": {
                        "action": "advance",
                    }
                }
                errors = output_schema.validate_output_payload(payload, schema)
                self.assertIn("$: unsupported property 'state_effects'", errors)


if __name__ == "__main__":
    unittest.main()
