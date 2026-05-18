#!/usr/bin/env python3
"""Boundary checks for BuddySwitch output schema validation."""

from __future__ import annotations

import json
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

COMMON_REQUIRED_COMMIT_KEYS = {"execution_summary"}
COMMON_OPTIONAL_COMMIT_KEYS = {
    "working_notes",
    "artifacts",
    "state_effects",
    "contributors",
    "tool_evidence",
}


class OutputSchemaBoundaryTests(unittest.TestCase):
    def _load_buddy_schema(self, buddy_id: str) -> dict[str, object]:
        path = BUDDY_RESULT_SCHEMA_PATHS[buddy_id].relative_to(ROOT).as_posix()
        return output_schema.load_output_schema(path)

    def _sample_payload_for_buddy(self, buddy_id: str) -> dict[str, object]:
        template_by_buddy = {
            "pm": "brief",
            "dev": "brief",
            "test": "proof",
            "market": "brief",
            "design": "design",
        }
        return {
            "execution_summary": f"{buddy_id} result summary",
            "working_notes": ["Focused contract result."],
            "artifacts": [
                {
                    "template": template_by_buddy[buddy_id],
                    "title": f"{buddy_id} artifact",
                    "summary": f"{buddy_id} artifact summary",
                    "body": "x",
                }
            ],
        }

    def test_buddy_result_schema_boundary_is_exactly_five_buddies(self) -> None:
        self.assertEqual(set(BUDDY_RESULT_SCHEMA_PATHS), {"pm", "dev", "test", "market", "design"})

    def test_buddy_result_schema_uses_compact_boundary_without_handoff(self) -> None:
        expected_properties = COMMON_REQUIRED_COMMIT_KEYS | COMMON_OPTIONAL_COMMIT_KEYS
        for buddy_id in BUDDY_RESULT_SCHEMA_PATHS:
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                self.assertEqual(set(schema.get("required", [])), COMMON_REQUIRED_COMMIT_KEYS)
                self.assertFalse(schema.get("additionalProperties"))
                properties = schema.get("properties")
                self.assertIsInstance(properties, dict)
                assert isinstance(properties, dict)
                self.assertTrue(expected_properties.issubset(set(properties)))
                self.assertNotIn("handoff", properties)

    def test_buddy_result_schema_rejects_handoff_payload(self) -> None:
        for buddy_id in BUDDY_RESULT_SCHEMA_PATHS:
            with self.subTest(buddy=buddy_id):
                schema = self._load_buddy_schema(buddy_id)
                payload = self._sample_payload_for_buddy(buddy_id)
                payload["handoff"] = {"next_buddy": "dev", "reason": "legacy", "context": "legacy"}
                errors = output_schema.validate_output_payload(payload, schema)
                self.assertIn("$: unsupported property 'handoff'", errors)

    def test_pm_schema_rejects_track_advance_effect(self) -> None:
        schema = self._load_buddy_schema("pm")
        payload = self._sample_payload_for_buddy("pm")
        payload["state_effects"] = {
            "track": {
                "action": "advance",
                "track_id": "track-onboarding",
            }
        }
        errors = output_schema.validate_output_payload(payload, schema)
        self.assertTrue(any("enum" in line or "advance" in line for line in errors), msg=json.dumps(errors, ensure_ascii=True))

    def test_pm_schema_accepts_track_update_effect_without_next_actor_fields(self) -> None:
        schema = self._load_buddy_schema("pm")
        payload = self._sample_payload_for_buddy("pm")
        payload["state_effects"] = {
            "track": {
                "action": "update",
                "track_id": "track-onboarding",
                "title": "New title",
                "status": "active",
                "summary": "summary",
            }
        }
        self.assertEqual(output_schema.validate_output_payload(payload, schema), [])


if __name__ == "__main__":
    unittest.main()
