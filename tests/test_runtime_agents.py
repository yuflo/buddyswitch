#!/usr/bin/env python3
"""Focused tests for runtime AGENTS template validation."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_agents  # noqa: E402


MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class RuntimeAgentsValidationTests(unittest.TestCase):
    def test_validate_runtime_agents_template_rejects_corrupt_template_without_external_mutation(self) -> None:
        buddy_id = "pm"
        checked_in_template = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy_id / "AGENTS.md"
        checked_in_before = checked_in_template.read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            template_path = Path(tmp) / "AGENTS.md"
            template_path.write_text(
                "\n".join(
                    [
                        "# BuddySwitch Runtime Workspace",
                        "Active buddy is `pm`.",
                        "Use scripts/turn_runtime.py prepare before each run.",
                        "Use scripts/turn_runtime.py persist after execution.",
                        "project.access=readonly",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(runtime_agents.RuntimeAgentsError, "project access wording"):
                runtime_agents.validate_runtime_agents_template(
                    buddy_id=buddy_id,
                    template_path=template_path,
                    manifest_path=MANIFEST,
                )

        checked_in_after = checked_in_template.read_text(encoding="utf-8")
        self.assertEqual(checked_in_after, checked_in_before)

    def test_runtime_agents_validate_all_cli_succeeds(self) -> None:
        completed = subprocess.run(
            ["python3", str(ROOT / "scripts" / "runtime_agents.py"), "validate-all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        output = completed.stdout
        for buddy_id in ("market", "pm", "design", "dev", "test"):
            self.assertIn(f"{buddy_id}: ok", output)


if __name__ == "__main__":
    unittest.main()
