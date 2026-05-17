#!/usr/bin/env python3
"""Runtime skill contract tests."""

from __future__ import annotations

import re
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

    def test_handoff_tool_skill_is_removed(self) -> None:
        self.assertFalse((ROOT / "buddyswitch/skills/shared/handoff-tool/SKILL.md").exists())
        all_skill_ids = [row.get("id") for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertNotIn("handoff-tool", all_skill_ids)

    def test_each_buddy_keeps_shared_runtime_tools_without_handoff(self) -> None:
        required = {"track-tool", "artifact-tool", "task-tool", "buddybox-tool"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            skills = set(buddy.get("skills", []))
            with self.subTest(buddy=buddy.get("id")):
                self.assertTrue(required.issubset(skills))
                self.assertNotIn("handoff-tool", skills)

    def test_shared_tool_skills_do_not_teach_handoff_or_next_buddy(self) -> None:
        shared_skill_files = [
            ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
        ]
        for path in shared_skill_files:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env.tool", text)
                self.assertNotIn("handoff", text)
                self.assertNotIn("next_buddy", text)
                self.assertNotIn("track.advance", text)

    def test_role_skills_remove_optional_handoff_guidance(self) -> None:
        role_skill_files = [
            ROOT / "buddyswitch/skills/market/research-scan/SKILL.md",
            ROOT / "buddyswitch/skills/pm/write-prd/SKILL.md",
            ROOT / "buddyswitch/skills/design/shape-prototype/SKILL.md",
            ROOT / "buddyswitch/skills/dev/implement-task/SKILL.md",
            ROOT / "buddyswitch/skills/test/smoke-test/SKILL.md",
        ]
        for path in role_skill_files:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("use optional `handoff`", lowered)
                self.assertNotIn("next_buddy", lowered)
                self.assertNotIn("track.advance", lowered)

    def test_track_tool_operation_set_excludes_advance(self) -> None:
        track_skill = (ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md").read_text(encoding="utf-8")
        operations_line = ""
        for line in track_skill.splitlines():
            if line.strip().startswith("- Operations:"):
                operations_line = line
                break
        self.assertTrue(operations_line, msg="track-tool SKILL.md must define an Operations line")
        operations = set(re.findall(r"`([^`]+)`", operations_line))
        self.assertEqual(
            operations,
            {"list", "get", "join", "create", "update", "archive", "attach-task", "detach-task"},
        )


if __name__ == "__main__":
    unittest.main()
