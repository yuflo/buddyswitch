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

_RETIRED_BUDDY_RUN_COMMIT = ("buddy-" + "run") + " " + "commit"


class RuntimeSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    def test_run_tool_skill_is_removed(self) -> None:
        self.assertFalse((ROOT / "buddyswitch/skills/shared/run-tool/SKILL.md").exists())
        all_skill_paths = [row.get("path") for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertFalse(any(isinstance(path, str) and "run-tool" in path for path in all_skill_paths))

    def test_each_buddy_keeps_runless_shared_tool_skills(self) -> None:
        required = {"track-tool", "artifact-tool", "task-tool", "handoff-tool", "buddybox-tool"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            skills = set(buddy.get("skills", []))
            with self.subTest(buddy=buddy.get("id")):
                self.assertTrue(required.issubset(skills))

    def test_buddybox_tool_skill_exists_with_required_frontmatter_and_sections(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "buddybox-tool" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        text = skill_path.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("name: buddybox-tool", lowered)
        for token in (
            "active buddy",
            "private local workspace",
            "drafts",
            "prototypes",
            "exports",
            "logs",
            "reports",
            "binary outputs",
            "buddyswitch env tools",
        ):
            with self.subTest(token=token):
                self.assertIn(token, lowered)
        for token in (
            "what buddybox is",
            "when to use",
            "when not to use",
            "commands",
            "path",
            "payload",
            "response",
            "promotion",
            "runtime closing",
            "common flows",
        ):
            with self.subTest(section=token):
                self.assertIn(token, lowered)

    def test_buddybox_tool_teaches_env_tool_not_direct_filesystem(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "buddybox-tool" / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in (
            "python3 scripts/env/client.py buddybox",
            "desc",
            "list",
            "read",
            "write",
            "delete",
            "<active_buddy>/",
            "content",
            "content_base64",
            "content_type",
            "encoding",
            "artifact.create_revision",
            "allowed_next_actions",
            "allowed_next_action_options",
            "env.tool",
        ):
            with self.subTest(token=token):
                self.assertIn(token, lowered)
        for forbidden in (
            'cat > buddyswitch/local/buddybox',
            'tee buddyswitch/local/buddybox',
            'open("buddyswitch/local/buddybox',
            'path("buddyswitch/local/buddybox',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)
        for forbidden in (
            "prepare",
            "persist",
            "run-tool",
            "always create artifact",
            "prototype means",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    def test_buddybox_tool_search_flow_is_conditional_and_does_not_shell_search(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "buddybox-tool" / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("search", lowered)
        self.assertTrue(
            "when available" in lowered
            or "if the runtime exposes" in lowered
            or "if tool catalog exposes" in lowered,
            msg=lowered,
        )
        self.assertTrue("context.get" in lowered or "scripts/turn_runtime.py status" in lowered, msg=lowered)
        self.assertTrue("do not shell-search" in lowered or "do not use shell search" in lowered, msg=lowered)
        for forbidden in (
            "rg buddyswitch/local/buddybox",
            "grep -r buddyswitch/local/buddybox",
            "find buddyswitch/local/buddybox",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    def test_shared_tool_skills_teach_env_tool_not_prepare_persist(self) -> None:
        shared_skill_files = [
            ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/handoff-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
        ]
        for path in shared_skill_files:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env.tool", text)
                self.assertNotIn("prepare", text)
                self.assertNotIn("persist", text)
                self.assertNotIn(_RETIRED_BUDDY_RUN_COMMIT, text)


if __name__ == "__main__":
    unittest.main()
