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

        result = {
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": ["Scoped the edits to onboarding CTA behavior."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "suggested_next_switch": "switch test: Run smoke checks for the onboarding improvements",
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
        self.assertEqual(persisted["skill"]["id"], "implement-task")
        self.assertIn("artifact", persisted["effects"]["summary"].lower())

        artifact = persisted["artifact"]
        self._remember(f"buddyswitch/objects/artifacts/{artifact['id']}.json")
        self._remember(artifact["content_path"])
        self._remember(artifact["path"])
        if persisted["summary"]["path"]:
            self._remember(persisted["summary"]["path"])
        self._remember(persisted["run"]["content_path"])

        self.assertIn(artifact["path"], persisted["effects"]["writes"])
        self.assertIn(persisted["run"]["content_path"], persisted["effects"]["writes"])


if __name__ == "__main__":
    unittest.main()
