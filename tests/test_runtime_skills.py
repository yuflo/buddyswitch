#!/usr/bin/env python3
"""Runtime skill contract tests."""

from __future__ import annotations
import sys
import tempfile
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

from env.tool_runtime import registry as tool_registry  # noqa: E402
import runtime_skills  # noqa: E402


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
        "task_sys": ROOT / "buddyswitch/skills/shared/task-management/SKILL.md",
        "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
        "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
        "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
    }
    DEV_PRODUCT_SKILLS = (
        "enter-dev-workspace",
        "read-implementation-context",
        "handle-empty-source-root",
        "plan-thin-slice-implementation",
        "implement-scoped-change",
        "debug-regression",
        "select-local-verification",
        "request-dev-code-review",
        "handle-review-feedback",
        "finish-dev-change",
        "pressure-test-dev-skill",
        "parallelize-independent-dev-work",
        "write-implementation-report",
        "prepare-review-readiness",
    )
    DEV_STARTUP_SKILLS = {
        "plan-thin-slice-implementation",
        "request-dev-code-review",
        "handle-review-feedback",
        "finish-dev-change",
        "pressure-test-dev-skill",
        "parallelize-independent-dev-work",
    }
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
    MARKET_P0_SKILLS = (
        "market-source-seed-atlas",
        "market-search-operator-builder",
        "source-quality-rater",
        "data-triangulator",
        "hallucination-guard",
        "weak-signal-scout",
        "workaround-miner",
        "market-tension-finder",
        "customer-voice-mining",
        "segment-map-builder",
        "icp-scorer",
        "positioning-message-map",
        "growth-bottleneck-diagnoser",
        "channel-strategy-mapper",
        "experiment-design-reviewer",
    )
    OLD_MARKET_SKILLS = (
        "research-scan",
        "pmf-recon",
        "customer-discovery",
        "positioning-copy",
        "channel-discovery",
        "launch-prep",
    )
    SHARED_RUNTIME_TOOL_SKILLS = {
        "track-tool",
        "artifact-tool",
        "task-management",
        "message-tool",
    }
    ROLE_AGENT_FILES = (
        ROOT / "tools/launcher/assets/roles/pm/AGENTS.md",
        ROOT / "tools/launcher/assets/roles/dev/AGENTS.md",
        ROOT / "tools/launcher/assets/roles/design/AGENTS.md",
        ROOT / "tools/launcher/assets/roles/market/AGENTS.md",
        ROOT / "tools/launcher/assets/roles/test/AGENTS.md",
    )
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

    def _dev_skill_text(self, skill_id: str) -> str:
        return self._dev_skill_file(skill_id).read_text(encoding="utf-8").lower()

    def _pm_skill_file(self, skill_id: str) -> Path:
        return ROOT / "buddyswitch" / "skills" / "pm" / skill_id / "SKILL.md"

    def _pm_role(self) -> dict:
        return next(
            row
            for row in self.manifest.get("roles", [])
            if isinstance(row, dict) and row.get("id") == "pm"
        )

    def _market_role(self) -> dict:
        return next(
            row
            for row in self.manifest.get("roles", [])
            if isinstance(row, dict) and row.get("id") == "market"
        )

    def _market_skill_file(self, skill_id: str) -> Path:
        return ROOT / "buddyswitch" / "skills" / "market" / skill_id / "SKILL.md"

    def _market_skill_text(self, skill_id: str) -> str:
        path = self._market_skill_file(skill_id)
        self.assertTrue(path.exists(), msg=path)
        return path.read_text(encoding="utf-8")

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

    def test_each_role_keeps_shared_runtime_tools_without_handoff(self) -> None:
        required = {"track-tool", "artifact-tool", "task-management", "message-tool"}
        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            skills = set(role.get("skills", []))
            with self.subTest(role=role.get("id")):
                self.assertTrue(required.issubset(skills))
                self.assertNotIn("handoff-tool", skills)

    def test_manifest_and_runtime_skill_materialization_exclude_actor_private_tool(self) -> None:
        all_skill_ids = {row.get("id") for row in self.manifest.get("skills", []) if isinstance(row, dict)}
        self.assertNotIn("actor_private-tool", all_skill_ids)
        self.assertFalse((ROOT / "buddyswitch/skills/shared/actor_private-tool/SKILL.md").exists())
        for role in ("pm", "design", "dev", "market", "test"):
            role_row = next(
                row
                for row in self.manifest.get("roles", [])
                if isinstance(row, dict) and row.get("id") == role
            )
            self.assertNotIn("actor_private-tool", set(role_row.get("skills", [])), msg=role)
            with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
                workspace = Path(temp_dir) / f"{role}-workspace"
                workspace.mkdir()
                installed = runtime_skills.install_runtime_skills(
                    manifest_path=ROOT / "buddyswitch" / "manifest.toml",
                    role_id=role,
                    workspace=workspace,
                )
                self.assertNotIn("actor_private-tool", set(installed), msg=role)
                self.assertFalse((workspace / ".agents" / "skills" / "actor_private-tool").exists(), msg=role)

    def test_shared_tool_skills_do_not_teach_handoff_or_next_role(self) -> None:
        shared_skill_files = list(self.SHARED_TOOL_SKILLS.values())
        for path in shared_skill_files:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env.tool", text)
                self.assertNotIn("next_role", text)
                self.assertNotIn("track.advance", text)
                # Allow 'handoff' only in explicit "do not" prohibition context
                if "handoff" in text:
                    do_not_idx = text.find("do not")
                    handoff_idx = text.find("handoff")
                    self.assertGreaterEqual(do_not_idx, 0, msg=f"{path}: 'handoff' found without 'do not' section")
                    self.assertGreater(handoff_idx, do_not_idx, msg=f"{path}: 'handoff' found before 'do not' section")

    def test_shared_tool_skills_use_native_first_runtime_discovery(self) -> None:
        skill_paths = list(self.SHARED_TOOL_SKILLS.values())
        for path in skill_paths:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("native buddyswitch env mcp tools", lowered)
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn("python3 scripts/turn_runtime.py status", text)
                self.assertNotIn("python3 scripts/env/client.py", text)
                self.assertNotIn("CLI Payload Rule", text)
                self.assertNotIn("--payload", text)

    def test_active_skills_do_not_teach_old_env_client_flags(self) -> None:
        for path in self._active_skill_files():
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                for pattern in self._OLD_FLAG_PATTERNS:
                    self.assertNotIn(pattern, text)

    def test_market_skills_use_native_browser_entry(self) -> None:
        for skill_id in self.MARKET_P0_SKILLS:
            text = self._market_skill_text(skill_id)
            lowered = text.lower()
            with self.subTest(skill=skill_id):
                self.assertIn("search__open_browser", lowered)
                self.assertIn("chrome-devtools-cockpit", lowered)
                self.assertIn("query-to-url wrapper", lowered)
                self.assertIn("native buddyswitch env mcp tools", lowered)
                self.assertNotIn("use native `search__open_browser`", lowered)
                self.assertNotIn("start discovery from native `search__open_browser`", lowered)
                self.assertNotIn("python3 scripts/env/client.py", lowered)
                self.assertNotIn("search open-browser --payload", lowered)
                self.assertNotIn("search open-browser --query", lowered)
                self.assertNotIn("search open_browser --query", lowered)

    def test_market_p0_startup_marketer_skill_chain_is_registered(self) -> None:
        lookup = {
            row.get("id"): row
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict)
        }
        market_skills = set(self._market_role().get("skills", []))
        expected = set(self.MARKET_P0_SKILLS)

        self.assertTrue(expected.issubset(market_skills), msg=sorted(expected - market_skills))
        self.assertTrue(self.SHARED_RUNTIME_TOOL_SKILLS.issubset(market_skills))
        for skill_id in self.MARKET_P0_SKILLS:
            with self.subTest(skill=skill_id):
                self.assertIn(skill_id, lookup)
                self.assertTrue(self._market_skill_file(skill_id).exists())

        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            if role.get("id") == "market":
                continue
            with self.subTest(role=role.get("id")):
                self.assertTrue(expected.isdisjoint(set(role.get("skills", []))))

    def test_old_broad_market_skills_are_removed(self) -> None:
        skill_ids = {
            row.get("id")
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict)
        }
        market_skills = set(self._market_role().get("skills", []))
        for skill_id in self.OLD_MARKET_SKILLS:
            with self.subTest(skill=skill_id):
                self.assertNotIn(skill_id, skill_ids)
                self.assertNotIn(skill_id, market_skills)
                self.assertFalse((ROOT / "buddyswitch" / "skills" / "market" / skill_id).exists())

    def test_market_p0_skills_have_valid_frontmatter_and_trigger_descriptions(self) -> None:
        for skill_id in self.MARKET_P0_SKILLS:
            text = self._market_skill_text(skill_id)
            lowered = text.lower()
            with self.subTest(skill=skill_id):
                self.assertTrue(text.startswith("---\n"))
                self.assertIn(f"name: {skill_id}", text)
                description_line = next((line for line in text.splitlines() if line.startswith("description: ")), "")
                self.assertTrue(description_line.startswith("description: Use when "), msg=description_line)
                self.assertLessEqual(len(description_line), 500)
                self.assertNotIn("python3 scripts/env/client.py", description_line)
                self.assertNotIn("artifact.create_revision", description_line)
                self.assertNotIn("##", description_line)
                self.assertNotIn("1.", description_line)
                self.assertNotIn(" then ", description_line.lower())
                self.assertIn("## artifact", lowered)
                self.assertIn("## verification", lowered)
                self.assertIn("## guardrails", lowered)

    def test_runtime_skill_installer_materializes_market_p0_skill_set(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            installed = runtime_skills.install_runtime_skills(
                manifest_path=ROOT / "buddyswitch" / "manifest.toml",
                role_id="market",
                workspace=workspace,
            )
            installed_set = set(installed)
            expected = set(self.MARKET_P0_SKILLS) | self.SHARED_RUNTIME_TOOL_SKILLS
            self.assertTrue(expected.issubset(installed_set), msg=sorted(expected - installed_set))
            self.assertTrue(set(self.OLD_MARKET_SKILLS).isdisjoint(installed_set))
            for skill_id in self.MARKET_P0_SKILLS:
                self.assertTrue((workspace / ".agents" / "skills" / skill_id / "SKILL.md").exists(), msg=skill_id)

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            workspace = Path(temp_dir) / "pm-workspace"
            workspace.mkdir()
            installed = runtime_skills.install_runtime_skills(
                manifest_path=ROOT / "buddyswitch" / "manifest.toml",
                role_id="pm",
                workspace=workspace,
            )
            self.assertTrue(set(self.MARKET_P0_SKILLS).isdisjoint(set(installed)))

    def test_design_shape_prototype_guidance_uses_direct_actor_private_files_and_explicit_attachments(self) -> None:
        skill_text = (ROOT / "buddyswitch/skills/design/shape-prototype/SKILL.md").read_text(encoding="utf-8").lower()
        template_text = (
            ROOT / "buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md"
        ).read_text(encoding="utf-8").lower()
        retired_import = ".".join(("actor_private", "import_file"))

        self.assertIn("buddyswitch_actor_private_dir", skill_text)
        self.assertIn("source_path", skill_text)
        self.assertNotIn(retired_import, skill_text)
        self.assertIn("buddyswitch_actor_private_dir", template_text)
        self.assertIn("attachment_id", template_text)
        self.assertIn("chrome-devtools-cockpit", template_text)
        self.assertIn("chrome-devtools-cockpit", skill_text)
        self.assertIn("artifact.attach_file", skill_text)
        self.assertIn("artifact.get_attachment", skill_text)

    def test_shared_tool_skills_do_not_include_copyable_env_client_examples(self) -> None:
        for tool, path in self.SHARED_TOOL_SKILLS.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(tool=tool):
                self.assertNotIn("python3 scripts/env/client.py", text)
                self.assertNotIn("CLI Payload Rule", text)
                self.assertNotIn("--payload", text)

    def test_shared_tool_skills_route_exact_fields_to_runtime_discovery(self) -> None:
        skill_paths = list(self.SHARED_TOOL_SKILLS.values())
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("native buddyswitch env mcp tools", text)
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn("turn_runtime.py status", text)

    def test_role_agents_do_not_present_authoritative_hardcoded_tool_lists(self) -> None:
        for path in self.ROLE_AGENT_FILES:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn("python3 scripts/turn_runtime.py status", text)
                self.assertNotIn("python3 scripts/env/client.py", text)
                self.assertNotIn("context summarize --payload", lowered)
                self.assertNotIn("search open-browser --payload", lowered)
                self.assertNotIn("Runtime tool examples include", text)
                self.assertNotIn("authoritative fallback runtime tool list", lowered)
                self.assertNotIn("Use explicit ids and env tools (`", text)

    def test_track_skill_comment_support_matches_runtime_semantics(self) -> None:
        track_skill = self.SHARED_TOOL_SKILLS["track"].read_text(encoding="utf-8").lower()
        track_actions = tool_registry.supported_actions("track")
        self.assertIn("add_comment", track_actions)
        self.assertIn("list_comments", track_actions)
        self.assertIn("resolve_comment_thread", track_actions)
        self.assertIn("track__add_comment", track_skill)
        self.assertIn("track__list_comments", track_skill)
        self.assertIn("track__resolve_comment_thread", track_skill)
        self.assertNotIn("artifact_section", track_skill)

    def test_shared_skills_do_not_name_stale_actions_or_internal_contract_surfaces(self) -> None:
        forbidden = (
            "track.get",
            "comment.reopen",
            "scripts/env/tools/",
            "contract.py",
            "semantics.py",
            "TOOL_SPEC",
            "ACTION_SEMANTICS",
        )
        for path in self._active_skill_files():
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(ROOT))):
                for token in forbidden:
                    self.assertNotIn(token.lower(), text.lower())

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
            ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
        ]
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("**payload:**", text)
                self.assertNotIn("**returns:**", text)
                self.assertNotIn("## payload examples", text)

    def test_shared_message_skill_prevents_observed_invalid_calls(self) -> None:
        message_skill = self.SHARED_TOOL_SKILLS["message"].read_text(encoding="utf-8").lower()
        forbidden_identity_residue = (
            "active role cannot",
            "same role id",
            "same role cannot",
            "same-role cannot",
            "same buddy",
            "buddybox",
            "role messages",
            "direct_role_channel",
            "active-role inbox",
            "not the active role",
        )

        self.assertIn("message__contacts", message_skill)
        self.assertIn("target_identity_id", message_skill)
        self.assertIn("contact.identity_id", message_skill)
        self.assertIn("message__get", message_skill)
        self.assertIn("message__send", message_skill)
        self.assertIn("message__mark", message_skill)
        self.assertIn("message__conversation", message_skill)
        self.assertIn("message__list", message_skill)
        self.assertNotIn("request__list", message_skill)
        self.assertIn("context.get.tool_catalog['message']", message_skill)
        self.assertNotIn("message contacts --payload", message_skill)
        self.assertNotIn("message send --payload", message_skill)
        self.assertNotIn("message conversation --payload", message_skill)
        self.assertNotIn("message list --payload", message_skill)
        self.assertNotIn("to_role", message_skill)
        self.assertNotIn("from_role", message_skill)
        self.assertNotIn('"actor_address":', message_skill)
        self.assertNotIn('"message":', message_skill)
        self.assertNotIn('message list --payload \'{"box":"inbox"}\'', message_skill)
        self.assertNotIn('message list --payload "{\\"box\\":\\"inbox\\"}"', message_skill)
        self.assertNotIn("selected target role", message_skill)
        self.assertNotIn("role selector", message_skill)
        for token in forbidden_identity_residue:
            with self.subTest(source_token=token):
                self.assertNotIn(token, message_skill)

    def test_message_track_shared_tool_skills_stay_atomic(self) -> None:
        """MCT-SURF-006: Message/Track skills don't teach non-goal features."""
        msg_skill = (ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md").read_text(encoding="utf-8").lower()
        track_skill = (ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md").read_text(encoding="utf-8").lower()
        non_goals = ["broadcast", "read receipt", "read_receipt", "handoff", "edit", "delete", "reopen", "task comment", "whiteboard"]
        for skill_text, label in [(msg_skill, "message-tool"), (track_skill, "track-tool")]:
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
            *(self._market_skill_file(skill_id) for skill_id in self.MARKET_P0_SKILLS),
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
                self.assertNotIn("next_role", lowered)
                self.assertNotIn("track.advance", lowered)

    def test_pm_product_skill_chain_is_registered(self) -> None:
        skills_by_id = {row["id"]: row for row in self.manifest.get("skills", []) if isinstance(row, dict)}
        pm_skills = set(self._pm_role().get("skills", []))
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
        dev = next(row for row in self.manifest.get("roles", []) if isinstance(row, dict) and row.get("id") == "dev")
        dev_skills = set(dev.get("skills", []))
        expected = set(self.DEV_PRODUCT_SKILLS)
        removed_importer = "-".join(("skill", "creator", "importer"))
        self.assertTrue(expected.issubset(dev_skills))
        self.assertTrue(self.DEV_STARTUP_SKILLS.issubset(dev_skills))
        self.assertTrue(self.SHARED_RUNTIME_TOOL_SKILLS.issubset(dev_skills))
        self.assertNotIn(removed_importer, dev_skills)
        self.assertNotIn("implement-task", dev_skills)
        for skill_id in expected:
            self.assertIn(skill_id, skills_by_id, msg=skill_id)
            skill_file = ROOT / skills_by_id[skill_id]["path"] / "SKILL.md"
            self.assertTrue(skill_file.exists(), msg=skill_file)
        for role_id in ("market", "pm", "design", "test"):
            role = next(
                row
                for row in self.manifest.get("roles", [])
                if isinstance(row, dict) and row.get("id") == role_id
            )
            with self.subTest(role=role_id):
                self.assertTrue(self.DEV_STARTUP_SKILLS.isdisjoint(set(role.get("skills", []))))

    def test_dev_skills_have_valid_frontmatter_and_trigger_descriptions(self) -> None:
        forbidden_description_tokens = (
            "1.",
            "2.",
            "python3 scripts/env/client.py",
            "track.open",
            "artifact.get",
            "## ",
        )
        for skill_id in self.DEV_PRODUCT_SKILLS:
            path = self._dev_skill_file(skill_id)
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

    def test_runtime_skill_installer_materializes_expanded_dev_skill_set(self) -> None:
        expected = set(self.DEV_PRODUCT_SKILLS) | self.SHARED_RUNTIME_TOOL_SKILLS
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            installed = runtime_skills.install_runtime_skills(
                manifest_path=ROOT / "buddyswitch" / "manifest.toml",
                role_id="dev",
                workspace=workspace,
            )
            installed_set = set(installed)
            self.assertTrue(expected.issubset(installed_set))
            for skill_id in self.DEV_STARTUP_SKILLS:
                skill_file = workspace / ".agents" / "skills" / skill_id / "SKILL.md"
                self.assertTrue(skill_file.exists(), msg=skill_id)

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            workspace = Path(temp_dir) / "pm-workspace"
            workspace.mkdir()
            installed = runtime_skills.install_runtime_skills(
                manifest_path=ROOT / "buddyswitch" / "manifest.toml",
                role_id="pm",
                workspace=workspace,
            )
            self.assertTrue(self.DEV_STARTUP_SKILLS.isdisjoint(set(installed)))

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

    def test_pm_and_shared_tool_skills_describe_single_publication_path(self) -> None:
        pm_skill = "\n".join(
            self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            for skill_id in self.PM_PRODUCT_SKILLS
        )
        artifact_skill = (ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md").read_text(encoding="utf-8").lower()
        track_skill = (ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md").read_text(encoding="utf-8").lower()

        self.assertNotIn("published_to_track", pm_skill)
        self.assertNotIn("content.prd", pm_skill)
        self.assertNotIn("kind=prd", pm_skill)

        self.assertNotIn("published_to_track", artifact_skill)
        self.assertNotIn("content.prd", artifact_skill)
        self.assertNotIn("kind=prd", artifact_skill)

        self.assertNotIn("content.prd", track_skill)
        self.assertNotIn("kind=prd", track_skill)
        self.assertNotIn("published_to_track", track_skill)

    def test_pm_contract_and_agents_align_with_generic_skill_surface(self) -> None:
        contract = (ROOT / "framework/contracts/pm.md").read_text(encoding="utf-8").lower()
        agents = (ROOT / "tools/launcher/assets/roles/pm/AGENTS.md").read_text(encoding="utf-8").lower()
        combined = contract + "\n" + agents

        self.assertNotIn("write-prd", combined)
        self.assertIn("native buddyswitch env mcp tools", contract)
        self.assertIn("context.get.tool_catalog", contract)
        self.assertIn("python3 scripts/turn_runtime.py status", contract)
        self.assertNotIn("python3 scripts/env/client.py", combined)

    def test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs(self) -> None:
        skill_paths = {
            "task_sys": ROOT / "buddyswitch/skills/shared/task-management/SKILL.md",
            "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
            "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
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
        self.assertIn("resolve_comment_thread", catalog.supported_actions("track"))
        self.assertNotIn("reopen_comment_thread", catalog.supported_actions("track"))


if __name__ == "__main__":
    unittest.main()
