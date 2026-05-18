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
        required = {"track-tool", "artifact-tool", "task-tool", "buddybox-tool", "message-tool", "comment-tool"}
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
            ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
        ]
        for path in shared_skill_files:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env.tool", text)
                self.assertNotIn("next_buddy", text)
                self.assertNotIn("track.advance", text)
                # Allow 'handoff' only in explicit "do not" prohibition context
                if "handoff" in text:
                    do_not_idx = text.find("do not")
                    handoff_idx = text.find("handoff")
                    self.assertGreaterEqual(do_not_idx, 0, msg=f"{path}: 'handoff' found without 'do not' section")
                    self.assertGreater(handoff_idx, do_not_idx, msg=f"{path}: 'handoff' found before 'do not' section")

    def test_shared_tool_skills_teach_inline_json_payloads(self) -> None:
        skill_paths = [
            ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
        ]
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("--payload", text)
                self.assertIn("json object string", text)
                self.assertNotIn("--payload /tmp", text)
                self.assertNotIn("payload file path", text)
                self.assertNotIn("payload file", text)

    def test_message_comment_shared_tool_skills_stay_atomic(self) -> None:
        """MCT-SURF-006: Message/comment skills don't teach non-goal features."""
        msg_skill = (ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md").read_text(encoding="utf-8").lower()
        cmt_skill = (ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md").read_text(encoding="utf-8").lower()
        non_goals = ["broadcast", "read receipt", "read_receipt", "handoff", "edit", "delete", "resolve", "task comment", "whiteboard"]
        for skill_text, label in [(msg_skill, "message-tool"), (cmt_skill, "comment-tool")]:
            with self.subTest(skill=label):
                self.assertIn("env.tool", skill_text)
                self.assertIn("message.send" if "message" in label else "comment.add", skill_text)
                # Non-goals should only appear in "Do not" context
                for term in non_goals:
                    if term in skill_text:
                        # Allow "do not" context
                        do_not_idx = skill_text.find("do not")
                        term_idx = skill_text.find(term)
                        self.assertTrue(do_not_idx >= 0, msg=f"{label}: '{term}' found without 'do not' section")

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

    def test_pm_and_shared_tool_skills_describe_single_publication_path(self) -> None:
        pm_skill = (ROOT / "buddyswitch/skills/pm/write-prd/SKILL.md").read_text(encoding="utf-8").lower()
        artifact_skill = (ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md").read_text(encoding="utf-8").lower()
        track_skill = (ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md").read_text(encoding="utf-8").lower()

        self.assertIn("artifact.create_revision", pm_skill)
        self.assertIn("track.add_material", pm_skill)
        self.assertIn("track.add_proof", pm_skill)
        self.assertIn("track.open", pm_skill)
        self.assertIn("artifact.get", pm_skill)
        self.assertNotIn("published_to_track", pm_skill)
        self.assertNotIn("content.prd", pm_skill)
        self.assertNotIn("kind=prd", pm_skill)

        self.assertIn("create-revision", artifact_skill)
        self.assertIn("private draft", artifact_skill)
        self.assertIn("track.add-material", artifact_skill)
        self.assertIn("track.add-proof", artifact_skill)
        self.assertNotIn("published_to_track", artifact_skill)
        self.assertNotIn("content.prd", artifact_skill)
        self.assertNotIn("kind=prd", artifact_skill)

        self.assertIn("add-material", track_skill)
        self.assertIn("add-proof", track_skill)
        self.assertIn("artifact.get", track_skill)
        self.assertNotIn("content.prd", track_skill)
        self.assertNotIn("kind=prd", track_skill)
        self.assertNotIn("published_to_track", track_skill)

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
            {"create", "list", "open", "update-now", "add-material", "add-update", "add-proof", "archive"},
        )
        self.assertNotIn("join", operations)
        self.assertNotIn("attach-task", operations)
        self.assertNotIn("detach-task", operations)


if __name__ == "__main__":
    unittest.main()
