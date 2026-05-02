#!/usr/bin/env python3
"""Integration checks for the BuddySwitch native-turn control flow."""

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
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class NativeTurnIntegrationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    @staticmethod
    def _valid_dev_result() -> dict[str, object]:
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

    def test_red_native_turn_prepare_then_persist_works_without_debug_parser(self) -> None:
        request_text = "switch dev: Implement onboarding behavior"

        self.assertFalse(hasattr(switch_runtime, "parse_switch"))
        resolved = switch_runtime.resolve_switch(request_text)

        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["request_text"], request_text)
        self.assertIn("turn_identity", resolved["run_envelope"])

        payload = switch_runtime.persist_skill_result(
            resolved,
            skill_id="implement-task",
            result=self._valid_dev_result(),
        )

        self.assertTrue(payload["ok"])
        self.assertIn("next_state", payload["receipt"])
        self.assertIn("receipt_paths", payload["receipt"])
        self.assertNotIn("recommended_switch", payload["receipt"])
        self.assertNotIn("reference_switches", payload["receipt"])

    def test_red_native_turn_run_audit_keeps_request_text_and_structured_next_state(self) -> None:
        request_text = "switch dev: Implement onboarding behavior"
        resolved = switch_runtime.resolve_switch(request_text)

        payload = switch_runtime.persist_skill_result(
            resolved,
            skill_id="implement-task",
            result=self._valid_dev_result(),
        )

        receipt = payload["receipt"]
        run_json = json.loads(self._runtime_path(receipt["paths"]["run"]).read_text(encoding="utf-8"))
        self.assertEqual(run_json["request_text"], request_text)
        self.assertIn("next_state", run_json)
        self.assertIn("receipt_paths", run_json)
        self.assertNotIn("recommended_switch", run_json)
        self.assertNotIn("reference_switches", run_json)


if __name__ == "__main__":
    unittest.main()
