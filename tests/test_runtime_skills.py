#!/usr/bin/env python3
"""Runtime skill contract tests."""

from __future__ import annotations
import sys
import unittest
from pathlib import Path

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.9 fallback
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class RuntimeSkillsTests(unittest.TestCase):
    _OLD_FLAG_PATTERNS = (
        "search open-browser --query",
        "search open_browser --query",
        "--query",
        "--engine",
        "--track-id",
        "--task-id",
        "--artifact-id",
        "--target-type",
        "--target-id",
    )
    SHARED_TOOL_SKILLS = {
        "task": ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
        "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
        "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
        "buddybox": ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
        "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
        "comment": ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
        "request": ROOT / "buddyswitch/skills/shared/request-tool/SKILL.md",
    }

    def setUp(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    def _active_skill_files(self) -> list[Path]:
        files: list[Path] = []
        for row in self.manifest.get("skills", []):
            if not isinstance(row, dict):
                continue
            rel = row.get("path")
            if not isinstance(rel, str) or not rel.strip():
                continue
            skill_file = ROOT / rel / "SKILL.md"
            if skill_file.exists():
                files.append(skill_file)
        return files

    def test_handoff_tool_skill_is_removed(self) -> None:
        self.assertFalse((ROOT / "buddyswitch/skills/shared/handoff-tool/SKILL.md").exists())
        all_skill_ids = [row.get("id") for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertNotIn("handoff-tool", all_skill_ids)

    def test_each_buddy_keeps_shared_runtime_tools_without_handoff(self) -> None:
        required = {"track-tool", "artifact-tool", "task-tool", "buddybox-tool", "message-tool", "comment-tool", "request-tool"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            skills = set(buddy.get("skills", []))
            with self.subTest(buddy=buddy.get("id")):
                self.assertTrue(required.issubset(skills))
                self.assertNotIn("handoff-tool", skills)

    def test_shared_tool_skills_do_not_teach_handoff_or_next_buddy(self) -> None:
        shared_skill_files = list(self.SHARED_TOOL_SKILLS.values())
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
        skill_paths = list(self.SHARED_TOOL_SKILLS.values())
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("--payload", text)
                self.assertIn("json object string", text)
                self.assertNotIn("--payload /tmp", text)
                self.assertNotIn("payload file path", text)
                self.assertNotIn("payload file", text)

    def test_active_skills_do_not_teach_old_env_client_flags(self) -> None:
        for path in self._active_skill_files():
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                for pattern in self._OLD_FLAG_PATTERNS:
                    self.assertNotIn(pattern, text)

    def test_market_skills_use_payload_browser_entry(self) -> None:
        market_files = [
            ROOT / "buddyswitch/skills/market/research-scan/SKILL.md",
            ROOT / "buddyswitch/skills/market/pmf-recon/SKILL.md",
            ROOT / "buddyswitch/skills/market/customer-discovery/SKILL.md",
            ROOT / "buddyswitch/skills/market/channel-discovery/SKILL.md",
            ROOT / "buddyswitch/skills/market/positioning-copy/SKILL.md",
            ROOT / "buddyswitch/skills/market/launch-prep/SKILL.md",
        ]
        for path in market_files:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("search open-browser --payload", text)
                self.assertIn("chrome-devtools-cockpit", text)
                self.assertNotIn("search open-browser --query", text)
                self.assertNotIn("search open_browser --query", text)

    def test_shared_tool_skill_env_client_examples_use_payload(self) -> None:
        for tool, path in self.SHARED_TOOL_SKILLS.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(tool=tool):
                for line in text.splitlines():
                    stripped = line.strip()
                    if "python3 scripts/env/client.py" not in stripped:
                        continue
                    if stripped.startswith("#"):
                        continue
                    if "..." in stripped:
                        continue
                    if stripped.startswith("- Runtime execution uses env.tool"):
                        continue
                    if " --help" in stripped:
                        continue
                    self.assertIn("--payload", stripped, msg=f"{path.relative_to(ROOT)} line missing --payload: {stripped}")

    def test_shared_tool_skills_route_exact_fields_to_runtime_discovery(self) -> None:
        skill_paths = list(self.SHARED_TOOL_SKILLS.values())
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn("turn_runtime.py status", text)

    def test_shared_tool_skills_name_only_runtime_discovery_surfaces_for_exact_contracts(self) -> None:
        required_refs = (
            "context.get.tool_catalog",
            "python3 scripts/turn_runtime.py status",
        )
        accepted_contract_refs = (
            "context.get.tool_catalog",
            "context.summarize.tool_affordances",
            "python3 scripts/turn_runtime.py status",
            "runtime response fields",
        )
        forbidden_refs = (
            "scripts/env/tools/",
            "contract.py",
            "semantics.py",
            "handlers.py",
            "service.py",
            "payload_fields",
            "action_semantics",
            "TOOL" + "_SPEC",
            "ACTION" + "_SEMANTICS",
        )
        for tool, path in self.SHARED_TOOL_SKILLS.items():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(tool=tool):
                for required in required_refs:
                    self.assertIn(required, text)
                self.assertTrue(
                    any(ref in text for ref in accepted_contract_refs),
                    msg=f"{path.relative_to(ROOT)} does not route exact contract knowledge to runtime discovery",
                )
                for forbidden in forbidden_refs:
                    self.assertNotIn(forbidden.lower(), lowered)

    def test_shared_tool_skills_do_not_embed_payload_or_return_schema_blocks(self) -> None:
        skill_paths = [
            ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
            ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
        ]
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("**payload:**", text)
                self.assertNotIn("**returns:**", text)
                self.assertNotIn("## payload examples", text)

    def test_message_comment_shared_tool_skills_stay_atomic(self) -> None:
        """MCT-SURF-006: Message/comment skills don't teach non-goal features."""
        msg_skill = (ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md").read_text(encoding="utf-8").lower()
        cmt_skill = (ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md").read_text(encoding="utf-8").lower()
        non_goals = ["broadcast", "read receipt", "read_receipt", "handoff", "edit", "delete", "reopen", "task comment", "whiteboard"]
        for skill_text, label in [(msg_skill, "message-tool"), (cmt_skill, "comment-tool")]:
            with self.subTest(skill=label):
                self.assertIn("env.tool", skill_text)
                self.assertIn("context.get.tool_catalog", skill_text)
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

    def test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs(self) -> None:
        skill_paths = {
            "task": ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
            "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            "buddybox": ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
            "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
            "comment": ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
            "request": ROOT / "buddyswitch/skills/shared/request-tool/SKILL.md",
        }
        for tool, path in skill_paths.items():
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(tool=tool):
                self.assertNotIn("## operations", text)
                self.assertNotRegex(text, r"(?m)^- operations:")
                self.assertNotRegex(text, rf"env\.tool\s*[→>\-]+\s*{tool}\.")
                self.assertIn(f"context.get.tool_catalog['{tool}']", text)
                self.assertIn("python3 scripts/turn_runtime.py status", text)

    def test_runtime_contract_not_shared_skill_owns_inactive_actions(self) -> None:
        from env.tool_runtime import registry as catalog

        self.assertNotIn("advance", catalog.supported_actions("track"))
        self.assertIn("resolve", catalog.supported_actions("comment"))
        self.assertNotIn("reopen", catalog.supported_actions("comment"))


if __name__ == "__main__":
    unittest.main()
