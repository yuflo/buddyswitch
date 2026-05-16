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

    def test_buddybox_tool_skill_exists_with_required_frontmatter_and_boundary_guidance(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "buddybox-tool" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        text = skill_path.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("name: buddybox-tool", lowered)
        for token in (
            "active buddy",
            "private file capability",
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
        self.assertIn("context.get.tool_catalog['buddybox']", lowered)
        self.assertIn("runtime feedback", lowered)
        self.assertNotIn("common flows", lowered)

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
            "logical_name",
            "content",
            "content_base64",
            "content_type",
            "encoding",
            "artifact.create_revision",
            "env.tool",
            "allowed_next_action_options",
            "correctable_fields",
            "alternative_capabilities",
        ):
            with self.subTest(token=token):
                self.assertIn(token, lowered)
        for forbidden in (
            'cat > buddyswitch/local/buddybox',
            'tee buddyswitch/local/buddybox',
            'open("buddyswitch/local/buddybox',
            'path("buddyswitch/local/buddybox',
            "--path",
            "<active_buddy>/",
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
        self.assertTrue("context.get" in lowered or "scripts/turn_runtime.py status" in lowered, msg=lowered)
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
                self.assertNotIn(_RETIRED_BUDDY_RUN_COMMIT, text)
                self.assertTrue(
                    "context.get.tool_catalog" in text
                    or "context.summarize.tool_affordances" in text
                    or "scripts/turn_runtime.py status" in text
                )
                self.assertNotIn("payload_fields", text)
                self.assertNotIn("action_semantics", text)
                self.assertNotIn("after writing a prd", text)
                self.assertNotIn("if the user says", text)

    def test_buddybox_tool_skill_stays_workflow_level_and_defers_to_runtime_feedback(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "buddybox-tool" / "SKILL.md"
        lowered = skill_path.read_text(encoding="utf-8").lower()
        self.assertIn("active buddy private file capability", lowered)
        self.assertIn("logical_name", lowered)
        self.assertIn("runtime feedback", lowered)
        self.assertIn("state_changed", lowered)
        self.assertIn("durability", lowered)
        self.assertIn("allowed_next_action_options", lowered)
        self.assertIn("correctable_fields", lowered)
        self.assertIn("alternative_capabilities", lowered)
        self.assertNotIn("common flows", lowered)
        self.assertNotIn("--path", lowered)
        self.assertNotIn("buddyswitch/local/buddybox", lowered)
        self.assertNotIn("must promote", lowered)


if __name__ == "__main__":
    unittest.main()
