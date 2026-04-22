#!/usr/bin/env python3
"""Integration checks for the BuddySwitch switch control flow."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import codex_router  # noqa: E402
import parse_switch  # noqa: E402
import switch_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class SwitchFlowIntegrationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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

    def test_tolerant_switch_flow_resolves_without_prepare_execution(self) -> None:
        text = "switch dev : Implement the approved onboarding improvements in projects/app"

        parsed = parse_switch.parse_switch(text)
        routed = codex_router.route_switch(text)
        resolved = switch_runtime.resolve_switch(text)

        self.assertTrue(parsed["ok"])
        self.assertTrue(routed["ok"])
        self.assertTrue(resolved["ok"])
        self.assertEqual(parsed["normalized_text"], routed["invocation"]["normalized_text"])
        self.assertEqual(resolved["skills"][0]["id"], "implement-task")
        self.assertEqual(resolved["task_resolution"]["mode"], "create")
        self.assertEqual(resolved["run_envelope"]["status"], "reserved")

    def test_resolve_then_persist_returns_refreshed_context(self) -> None:
        resolved = switch_runtime.resolve_switch("switch dev: Implement onboarding behavior")

        payload = switch_runtime.persist_skill_result(
            resolved,
            skill_id="implement-task",
            result=self._valid_dev_result(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["receipt"]["run_id"], resolved["run_envelope"]["run_id"])
        self.assertEqual(
            payload["refreshed_context"]["run_envelope"]["previous_run_id"],
            payload["receipt"]["run_id"],
        )
        self.assertEqual(
            payload["refreshed_context"]["task_context"]["task"]["latest_run_id"],
            payload["receipt"]["run_id"],
        )


if __name__ == "__main__":
    unittest.main()
