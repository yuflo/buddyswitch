#!/usr/bin/env python3
"""Integration checks for the BuddySwitch switch control flow."""

from __future__ import annotations

import json
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


class SwitchFlowIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(ROOT / repo_path)

    def test_tolerant_switch_flow_resolves_and_persists(self) -> None:
        text = "switch dev : Implement the approved onboarding improvements in projects/app"

        parsed = parse_switch.parse_switch(text)
        routed = codex_router.route_switch(text)
        resolved = switch_runtime.resolve_switch(text)

        self.assertTrue(parsed["ok"])
        self.assertTrue(routed["ok"])
        self.assertTrue(resolved["ok"])
        self.assertEqual(parsed["normalized_text"], routed["invocation"]["normalized_text"])
        self.assertEqual(parsed["normalized_text"], resolved["invocation"]["normalized_text"])
        self.assertEqual(resolved["implicit_skill_id"], "implement-task")
        self.assertEqual(resolved["task_resolution"]["mode"], "create")
        self.assertNotIn("default_artifact_kind", resolved["skill_cards"][0])
        self.assertNotIn("auto_summary", resolved["skill_cards"][0])

        result = {
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": ["Scoped the edits to onboarding CTA behavior."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
                "verification_runs": [
                    {"command": "npm test", "result": "passed", "notes": "Targeted unit coverage."}
                ],
                "known_limitations": ["No production build was executed in this integration test."],
            },
        }

        persisted = switch_runtime.persist_switch(resolved, skill_id=None, result=result)

        self.assertTrue(persisted["ok"])
        self.assertEqual(persisted["skill_id"], "implement-task")
        self.assertEqual(persisted["artifact_ids"], [persisted["artifact_id"]])
        self.assertIn("recommended_switch", persisted)
        self.assertEqual(persisted["related_run_ids"], [])

        self._remember(persisted["paths"]["artifacts"][0])
        self._remember(persisted["paths"]["task"])
        self._remember(persisted["paths"]["run"])

        self.assertIn(persisted["paths"]["artifacts"][0], persisted["writes"])
        self.assertIn(persisted["paths"]["task"], persisted["writes"])
        self.assertIn(persisted["paths"]["run"], persisted["writes"])
        self.assertNotIn("artifact_markdown", persisted["paths"])
        self.assertNotIn("summary", persisted["paths"])
        self.assertNotIn("suggested_next_switch", persisted)
        run_json = json.loads((ROOT / persisted["paths"]["run"]).read_text(encoding="utf-8"))
        self.assertNotIn("suggested_next_switch", run_json)
        self.assertEqual(
            persisted["recommended_switch"],
            persisted["reference_switches"]["continue_current_task"],
        )


if __name__ == "__main__":
    unittest.main()
