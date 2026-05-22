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
    DEV_PRODUCT_SKILLS = (
        "enter-dev-workspace",
        "read-implementation-context",
        "handle-empty-source-root",
        "implement-scoped-change",
        "debug-regression",
        "select-local-verification",
        "write-implementation-report",
        "prepare-review-readiness",
    )
    PM_PRODUCT_SKILLS = (
        "read-product-context",
        "synthesize-cross-functional-inputs",
        "frame-product-direction",
        "define-scope",
        "write-requirements",
        "write-acceptance-criteria",
        "make-product-decision",
        "decide-from-proof",
        "triage-track",
        "sequence-product-work",
    )
    SHARED_RUNTIME_TOOL_SKILLS = {
        "track-tool",
        "artifact-tool",
        "task-tool",
        "buddybox-tool",
        "message-tool",
        "comment-tool",
        "request-tool",
    }
    PM_SCENARIO_TERMS = (
        "wukong",
        "landing page",
        "pricing page",
        "launch page",
        "marketing surface",
        "marketing-surface",
    )

    def setUp(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    def _dev_skill_file(self, skill_id: str) -> Path:
        return ROOT / "buddyswitch" / "skills" / "dev" / skill_id / "SKILL.md"

    def _pm_skill_file(self, skill_id: str) -> Path:
        return ROOT / "buddyswitch" / "skills" / "pm" / skill_id / "SKILL.md"

    def _pm_buddy(self) -> dict:
        return next(
            row
            for row in self.manifest.get("buddies", [])
            if isinstance(row, dict) and row.get("id") == "pm"
        )

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

    def test_shared_message_and_buddybox_skills_prevent_observed_invalid_calls(self) -> None:
        message_skill = self.SHARED_TOOL_SKILLS["message"].read_text(encoding="utf-8").lower()
        buddybox_skill = self.SHARED_TOOL_SKILLS["buddybox"].read_text(encoding="utf-8").lower()

        self.assertIn("message list --payload '{}'", message_skill)
        self.assertIn("does not accept `box`", message_skill)
        self.assertIn("request.list", message_skill)
        self.assertNotIn('message list --payload \'{"box":"inbox"}\'', message_skill)
        self.assertNotIn('message list --payload "{\\"box\\":\\"inbox\\"}"', message_skill)

        self.assertIn("do not use absolute paths, traversal", buddybox_skill)
        self.assertIn("buddy id prefix", buddybox_skill)
        self.assertIn("logical_name", buddybox_skill)
        self.assertIn("heartbeats/b.md", buddybox_skill)

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
            *(self._pm_skill_file(skill_id) for skill_id in self.PM_PRODUCT_SKILLS),
            ROOT / "buddyswitch/skills/design/shape-prototype/SKILL.md",
            ROOT / "buddyswitch/skills/test/smoke-test/SKILL.md",
            *(self._dev_skill_file(skill_id) for skill_id in self.DEV_PRODUCT_SKILLS),
        ]
        for path in role_skill_files:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("use optional `handoff`", lowered)
                self.assertNotIn("next_buddy", lowered)
                self.assertNotIn("track.advance", lowered)

    def test_pm_product_skill_chain_is_registered(self) -> None:
        skills_by_id = {row["id"]: row for row in self.manifest.get("skills", []) if isinstance(row, dict)}
        pm_skills = set(self._pm_buddy().get("skills", []))
        expected_product = set(self.PM_PRODUCT_SKILLS)

        self.assertTrue(expected_product.issubset(pm_skills))
        self.assertTrue(self.SHARED_RUNTIME_TOOL_SKILLS.issubset(pm_skills))
        self.assertNotIn("write-prd", pm_skills)

        for skill_id in expected_product:
            self.assertIn(skill_id, skills_by_id, msg=skill_id)
            self.assertTrue((ROOT / skills_by_id[skill_id]["path"] / "SKILL.md").exists(), msg=skill_id)

        for skill_id in pm_skills:
            lowered = skill_id.lower()
            for term in self.PM_SCENARIO_TERMS:
                self.assertNotIn(term, lowered, msg=skill_id)

    def test_pm_write_prd_skill_package_is_removed(self) -> None:
        self.assertFalse((ROOT / "buddyswitch/skills/pm/write-prd/SKILL.md").exists())
        self.assertFalse((ROOT / "buddyswitch/skills/pm/write-prd/assets/prd-template.md").exists())
        skill_ids = [row.get("id") for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertNotIn("write-prd", skill_ids)

    def test_pm_skills_have_valid_frontmatter_and_trigger_descriptions(self) -> None:
        forbidden_description_tokens = (
            "1.",
            "2.",
            "python3 scripts/env/client.py",
            "track.open",
            "artifact.get",
            "artifact.create_revision",
            "track.add_material",
            "track.add_proof",
            "## ",
        )
        for skill_id in self.PM_PRODUCT_SKILLS:
            path = self._pm_skill_file(skill_id)
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            with self.subTest(skill=skill_id):
                self.assertEqual(lines[0], "---")
                self.assertIn(f"name: {skill_id}", lines[:6])
                description_lines = [line for line in lines[:8] if line.startswith("description: ")]
                self.assertEqual(len(description_lines), 1)
                description = description_lines[0].split("description: ", 1)[1]
                self.assertTrue(description.startswith("Use when "), msg=description)
                self.assertLessEqual(len(description), 1024)
                for token in forbidden_description_tokens:
                    self.assertNotIn(token, description)

    def test_pm_skills_include_product_work_sections_and_quality_bars(self) -> None:
        required_headings = (
            "## purpose",
            "## use when",
            "## do not use when",
            "## inputs",
            "## steps",
            "## outputs",
            "## quality bar",
            "## runtime boundary",
            "## examples",
            "## counterexamples",
        )
        required_by_skill = {
            "read-product-context": ("facts", "assumptions", "decisions", "blockers", "missing inputs"),
            "synthesize-cross-functional-inputs": ("market", "design", "dev", "test", "product impact"),
            "frame-product-direction": ("audience", "problem", "value", "constraints", "non-goals"),
            "define-scope": ("smallest valuable", "in-scope", "non-goals", "cut", "downstream"),
            "write-requirements": ("observable", "actor", "trigger", "behavior", "owner boundary"),
            "write-acceptance-criteria": ("pass", "fail", "blocked", "criteria", "proof"),
            "make-product-decision": ("decision", "evidence", "tradeoff", "rejected", "next owner"),
            "decide-from-proof": ("continue", "revise", "send back", "stop", "blocked"),
            "triage-track": ("stale", "current truth", "obsolete", "missing proof", "next action"),
            "sequence-product-work": ("owner", "output", "dependency", "stop condition", "sequence"),
        }
        for skill_id in self.PM_PRODUCT_SKILLS:
            lowered = self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                for heading in required_headings:
                    self.assertIn(heading, lowered)
                for token in required_by_skill[skill_id]:
                    self.assertIn(token, lowered)

    def test_pm_skills_do_not_copy_runtime_schema_or_action_catalogs(self) -> None:
        forbidden = (
            "payload_fields",
            "operation_semantics",
            "**payload:**",
            "**returns:**",
            "## operations",
            "scripts/env/tools/",
            "action_semantics",
            "tool_spec",
            "published_to_track",
            "content.prd",
            "kind=prd",
        )
        required_refs = (
            "context.get.tool_catalog",
            "python3 scripts/turn_runtime.py status",
            "runtime response fields",
        )
        for skill_id in self.PM_PRODUCT_SKILLS:
            lowered = self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                for token in forbidden:
                    self.assertNotIn(token, lowered)
                for token in required_refs:
                    self.assertIn(token, lowered)

    def test_pm_skills_are_not_page_or_case_specific(self) -> None:
        for skill_id in self.PM_PRODUCT_SKILLS:
            text = self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                self.assertNotIn("wukong", text)
                self.assertNotIn("landing page", text)
                self.assertNotIn("landing-page", text)
                self.assertNotIn("pricing page", text)
                self.assertNotIn("pricing-page", text)
                self.assertNotIn("launch page", text)
                self.assertNotIn("launch-page", text)
                self.assertNotIn("marketing surface", text)
                self.assertNotIn("marketing-surface", text)

    def test_dev_product_engineering_skill_chain_is_registered(self) -> None:
        skills_by_id = {row["id"]: row for row in self.manifest.get("skills", []) if isinstance(row, dict)}
        dev = next(row for row in self.manifest.get("buddies", []) if isinstance(row, dict) and row.get("id") == "dev")
        dev_skills = set(dev.get("skills", []))
        expected = set(self.DEV_PRODUCT_SKILLS)
        self.assertTrue(expected.issubset(dev_skills))
        self.assertIn("skill-creator-importer", dev_skills)
        self.assertNotIn("implement-task", dev_skills)
        for skill_id in expected:
            self.assertIn(skill_id, skills_by_id, msg=skill_id)
            skill_file = ROOT / skills_by_id[skill_id]["path"] / "SKILL.md"
            self.assertTrue(skill_file.exists(), msg=skill_file)

    def test_dev_skills_keep_operational_sections_and_scenarios(self) -> None:
        required_headings = (
            "## use when",
            "## do not use when",
            "## inputs",
            "## steps",
            "## outputs",
            "## guardrails",
        )
        for skill_id in self.DEV_PRODUCT_SKILLS:
            path = self._dev_skill_file(skill_id)
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(skill=skill_id):
                self.assertIn("name:", lowered)
                self.assertIn("description:", lowered)
                for heading in required_headings:
                    self.assertIn(heading, lowered)
                self.assertTrue(
                    "## verification" in lowered or "## stop conditions" in lowered,
                    msg=f"{path} missing verification/stop section",
                )
                self.assertIn("## examples", lowered)
                self.assertIn("## counterexamples", lowered)

    def test_dev_skills_do_not_copy_runtime_schema_or_action_catalogs(self) -> None:
        forbidden = (
            "payload_fields",
            "operation_semantics",
            "**payload:**",
            "**returns:**",
            "## operations",
            "project.write_file",
            "project.apply_patch",
            "configure_project",
            "delete_file",
        )
        for skill_id in self.DEV_PRODUCT_SKILLS:
            path = self._dev_skill_file(skill_id)
            lowered = path.read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                for token in forbidden:
                    self.assertNotIn(token, lowered)
                self.assertIn("context.get.tool_catalog", lowered)
                self.assertIn("turn_runtime.py status", lowered)

    def test_dev_skills_use_runtime_source_facts_and_not_literal_path_authority(self) -> None:
        for skill_id in self.DEV_PRODUCT_SKILLS:
            path = self._dev_skill_file(skill_id)
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(skill=skill_id):
                self.assertNotIn("project.access=", lowered)
                self.assertNotIn("`projects/app` is the authority", lowered)

        enter_workspace = self._dev_skill_file("enter-dev-workspace").read_text(encoding="utf-8").lower()
        implement_scope = self._dev_skill_file("implement-scoped-change").read_text(encoding="utf-8").lower()
        self.assertIn("source_workspace.path", enter_workspace)
        self.assertIn("locked source root", enter_workspace)
        self.assertIn("changed files", implement_scope)
        self.assertIn("locked source root", implement_scope)

    def test_dev_skill_scenario_coverage_for_empty_root_verification_and_review_handoff(self) -> None:
        handle_empty = self._dev_skill_file("handle-empty-source-root").read_text(encoding="utf-8").lower()
        verification = self._dev_skill_file("select-local-verification").read_text(encoding="utf-8").lower()
        reporting = self._dev_skill_file("write-implementation-report").read_text(encoding="utf-8").lower()
        review_ready = self._dev_skill_file("prepare-review-readiness").read_text(encoding="utf-8").lower()
        debug = self._dev_skill_file("debug-regression").read_text(encoding="utf-8").lower()
        read_context = self._dev_skill_file("read-implementation-context").read_text(encoding="utf-8").lower()

        for token in ("missing", "empty", "readme_only", "has_source"):
            self.assertIn(token, handle_empty)
        self.assertIn("not source-link missing", handle_empty)
        self.assertIn("scaffold", handle_empty)
        self.assertIn("pm/user", handle_empty)
        self.assertIn("artifact body", read_context)
        self.assertIn("outside locked root", self._dev_skill_file("implement-scoped-change").read_text(encoding="utf-8").lower())
        self.assertIn("reproduce", debug)
        self.assertIn("root cause", debug)
        self.assertIn("no project test command", verification)
        self.assertIn("verification blocked", reporting)
        self.assertIn("changed files", reporting)
        self.assertIn("risks", reporting)
        self.assertIn("follow-ups", reporting)
        self.assertIn("blast radius", review_ready)
        self.assertIn("residual risk", review_ready)

    def test_pm_and_shared_tool_skills_describe_single_publication_path(self) -> None:
        pm_skill = "\n".join(
            self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            for skill_id in self.PM_PRODUCT_SKILLS
        )
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

    def test_pm_contract_and_agents_align_with_generic_skill_surface(self) -> None:
        contract = (ROOT / "framework/contracts/pm.md").read_text(encoding="utf-8").lower()
        agents = (ROOT / "tools/launcher/assets/buddies/pm/AGENTS.md").read_text(encoding="utf-8").lower()
        combined = contract + "\n" + agents

        self.assertNotIn("write-prd", combined)
        for token in (
            "context intake",
            "product direction",
            "scope",
            "requirements",
            "acceptance criteria",
            "decision",
            "proof",
            "track triage",
            "sequencing",
        ):
            self.assertIn(token, contract)
        self.assertLess(contract.count("python3 scripts/env/client.py"), 8)

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
