#!/usr/bin/env python3
"""Runless runtime skill contract tests."""

from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class RuntimeSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    def test_run_tool_skill_is_removed(self) -> None:
        self.assertFalse((ROOT / "buddyswitch/skills/shared/run-tool/SKILL.md").exists())
        all_skill_paths = [row.get("path") for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertFalse(any(isinstance(path, str) and "run-tool" in path for path in all_skill_paths))

    def test_each_buddy_keeps_runless_shared_tool_skills(self) -> None:
        required = {"track-tool", "artifact-tool", "task-tool", "handoff-tool"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            skills = set(buddy.get("skills", []))
            with self.subTest(buddy=buddy.get("id")):
                self.assertTrue(required.issubset(skills))

    def test_shared_tool_skills_teach_env_tool_not_prepare_persist(self) -> None:
        shared_skill_files = [
            ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/handoff-tool/SKILL.md",
        ]
        for path in shared_skill_files:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env.tool", text)
                self.assertNotIn("prepare", text)
                self.assertNotIn("persist", text)
                self.assertNotIn("buddy-run commit", text)


if __name__ == "__main__":
    unittest.main()
