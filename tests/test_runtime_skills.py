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
        "task": ROOT / "buddyswitch/skills/shared/task-management/SKILL.md",
        "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
        "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
        "message": ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
        "comment": ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
        "request": ROOT / "buddyswitch/skills/shared/request-tool/SKILL.md",
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
        "comment-tool",
        "request-tool",
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
        required = {"track-tool", "artifact-tool", "task-management", "message-tool", "comment-tool", "request-tool"}
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
            text = self._market_skill_text(skill_id).lower()
            with self.subTest(skill=skill_id):
                self.assertIn("search__open_browser", text)
                self.assertIn("chrome-devtools-cockpit", text)
                self.assertIn("native buddyswitch env mcp tools", text)
                self.assertNotIn("python3 scripts/env/client.py", text)
                self.assertNotIn("search open-browser --payload", text)
                self.assertNotIn("search open-browser --query", text)
                self.assertNotIn("search open_browser --query", text)

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

    def test_market_p0_skills_preserve_runtime_evidence_boundaries(self) -> None:
        required = (
            "search__open_browser",
            "chrome-devtools-cockpit",
            "artifact.create_revision",
            "tool_evidence",
            "do not invent",
            "no silent downgrade",
            "runtime discovery",
        )
        for skill_id in self.MARKET_P0_SKILLS:
            text = self._market_skill_text(skill_id).lower()
            with self.subTest(skill=skill_id):
                for token in required:
                    self.assertIn(token, text)

    def test_market_source_seed_atlas_covers_seed_families_and_overclaim_caveats(self) -> None:
        text = self._market_skill_text("market-source-seed-atlas").lower()
        required = (
            "user-language communities",
            "review and comparison",
            "official and competitor",
            "search and content demand",
            "ad and distribution",
            "b2b structural",
            "developer ecosystem",
            "reddit",
            "x.com",
            "hacker news",
            "github issues",
            "g2",
            "capterra",
            "product hunt",
            "chrome web store",
            "google trends",
            "meta ads library",
            "google ads transparency",
            "sec edgar",
            "census",
            "job posts",
            "competitor pricing",
            "competitor docs",
            "competitor changelog",
            "competitor careers",
            "best for",
            "bad for",
            "query operators",
            "access constraints",
            "allowed claims",
            "forbidden overclaims",
            "not market size",
            "not absolute demand",
            "not confirmed product intent",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertIn("reddit and x", text)
        self.assertIn("review volume", text)
        self.assertIn("homepage claims", text)
        self.assertIn("normalized search interest", text)
        self.assertIn("job posts and patents", text)

    def test_market_search_operator_builder_requires_reproducible_query_plan(self) -> None:
        text = self._market_skill_text("market-search-operator-builder").lower()
        required = (
            "discovery queries",
            "validation queries",
            "negative evidence",
            "source-specific",
            "freshness",
            "query log",
            "primary source",
            "snippet",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_market_evidence_core_skills_cover_quality_triangulation_and_claim_audit(self) -> None:
        skill_tokens = {
            "source-quality-rater": (
                "freshness",
                "bias",
                "source type",
                "methodology",
                "usable claims",
            ),
            "data-triangulator": (
                "observed",
                "inferred",
                "hypothesized",
                "two independent source families",
                "directional",
            ),
            "hallucination-guard": (
                "audit urls",
                "dates",
                "numbers",
                "claim-source mapping",
                "block them",
                "cautious wording",
            ),
        }
        forbidden = (
            "single source is enough for high confidence",
            "publish unsupported claims",
        )
        for skill_id, required in skill_tokens.items():
            text = self._market_skill_text(skill_id).lower()
            with self.subTest(skill=skill_id):
                for token in required:
                    self.assertIn(token, text)
                for token in forbidden:
                    self.assertNotIn(token, text)

    def test_market_micro_signal_skills_capture_subtle_clues_with_guardrails(self) -> None:
        required_sections = (
            "micro signal",
            "why it is interesting",
            "possible hidden demand",
            "alternative explanations",
            "expansion queries",
            "validation probe",
            "confidence",
            "spark",
            "pattern",
            "commitment",
        )
        guardrails = (
            "do not generalize",
            "do not treat likes",
            "do not hide uncertainty",
            "do not turn hunches into facts",
            "always propose",
        )
        for skill_id in ("weak-signal-scout", "workaround-miner", "market-tension-finder"):
            text = self._market_skill_text(skill_id).lower()
            with self.subTest(skill=skill_id):
                for token in required_sections:
                    self.assertIn(token, text)
                for token in guardrails:
                    self.assertIn(token, text)

    def test_workaround_miner_captures_behavior_linked_demand(self) -> None:
        text = self._market_skill_text("workaround-miner").lower()
        required = (
            "spreadsheets",
            "scripts",
            "zapier",
            "notion",
            "airtable",
            "manual services",
            "internal tools",
            "stitched-together products",
            "copy-paste",
            "current workaround",
            "trigger moment",
            "cost",
            "owner",
            "frequency",
            "failure mode",
            "switching implication",
            "willingness to pay",
            "commitment evidence",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_market_tension_finder_extracts_contradictions_and_probes(self) -> None:
        text = self._market_skill_text("market-tension-finder").lower()
        required = (
            "stated",
            "observed behavior",
            "contradiction",
            "continued usage",
            "buyer confusion",
            "market implication",
            "validation probe",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_market_demand_discovery_skills_create_traceable_segment_and_icp_artifacts(self) -> None:
        required_by_skill = {
            "customer-voice-mining": (
                "interviews",
                "reviews",
                "support notes",
                "sales notes",
                "community posts",
                "pain themes",
                "language patterns",
                "traceable",
                "do not invent quotes",
            ),
            "segment-map-builder": (
                "role",
                "business context",
                "workflow context",
                "trigger moment",
                "workaround",
                "exclusions",
                "reachability",
            ),
            "icp-scorer": (
                "pain urgency",
                "reachability",
                "ability to pay",
                "switching trigger",
                "referenceability",
                "retention",
                "expansion proxy",
                "positive fit",
                "negative fit",
                "score bands",
                "next validation action",
            ),
        }
        for skill_id, required in required_by_skill.items():
            text = self._market_skill_text(skill_id).lower()
            with self.subTest(skill=skill_id):
                for token in required:
                    self.assertIn(token, text)

    def test_market_action_skills_turn_evidence_into_one_runnable_experiment(self) -> None:
        required_by_skill = {
            "positioning-message-map": (
                "who",
                "alternative",
                "differentiated value",
                "proof",
                "message hierarchy",
                "testable angle",
            ),
            "growth-bottleneck-diagnoser": (
                "one current growth bottleneck",
                "broad marketing plan",
            ),
            "channel-strategy-mapper": (
                "icp fit",
                "intent fit",
                "reachability",
                "cac",
                "payback",
                "founder access",
                "speed to learning",
            ),
            "experiment-design-reviewer": (
                "hypothesis",
                "primary metric",
                "guardrail metric",
                "duration",
                "sample sanity",
                "stop/scale rule",
                "kill signal",
            ),
        }
        for skill_id, required in required_by_skill.items():
            text = self._market_skill_text(skill_id).lower()
            with self.subTest(skill=skill_id):
                for token in required:
                    self.assertIn(token, text)
        action_text = "\n".join(self._market_skill_text(skill_id).lower() for skill_id in required_by_skill)
        self.assertIn("kill signal", action_text)
        self.assertNotIn("generic multi-channel plan with no kill signal", action_text)

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
                self.assertIn("Prefer native BuddySwitch env MCP tools", text)
                self.assertIn("start with the native buddyswitch env context summary tool", lowered)
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn("python3 scripts/turn_runtime.py status", text)
                self.assertIn("do not bypass runtime", lowered)
                self.assertNotIn("python3 scripts/env/client.py", text)
                self.assertNotIn("context summarize --payload", lowered)
                self.assertNotIn("search open-browser --payload", lowered)
                self.assertNotIn("Runtime tool examples include", text)
                self.assertNotIn("authoritative fallback runtime tool list", lowered)
                self.assertNotIn("Use explicit ids and env tools (`", text)

    def test_shared_comment_skill_target_support_matches_runtime_semantics(self) -> None:
        comment_skill = self.SHARED_TOOL_SKILLS["comment"].read_text(encoding="utf-8").lower()
        comment_model = tool_registry.compact_tool_affordances()["comment"]["object_model"].lower()
        self.assertIn("artifact_section", comment_model)
        self.assertIn("artifact_section", comment_skill)
        self.assertNotIn("only `track` and `artifact`", comment_skill)
        self.assertNotIn("only track and artifact", comment_skill)

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
            ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
        ]
        for path in skill_paths:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("**payload:**", text)
                self.assertNotIn("**returns:**", text)
                self.assertNotIn("## payload examples", text)

    def test_shared_message_skill_prevents_observed_invalid_calls(self) -> None:
        message_skill = self.SHARED_TOOL_SKILLS["message"].read_text(encoding="utf-8").lower()

        self.assertIn("message__contacts", message_skill)
        self.assertIn("target_actor_address", message_skill)
        self.assertIn("contact.actor_address", message_skill)
        self.assertIn("message__send", message_skill)
        self.assertIn("message__conversation", message_skill)
        self.assertIn("message__list", message_skill)
        self.assertIn("does not accept `box`", message_skill)
        self.assertIn("request__list", message_skill)
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

        for role in ("pm", "market"):
            with self.subTest(materialized_for=role):
                with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
                    workspace = Path(temp_dir) / f"{role}-workspace"
                    workspace.mkdir()
                    runtime_skills.install_runtime_skills(
                        manifest_path=ROOT / "buddyswitch/manifest.toml",
                        role_id=role,
                        workspace=workspace,
                    )
                    installed = (workspace / ".agents" / "skills" / "message-tool" / "SKILL.md").read_text(
                        encoding="utf-8"
                    ).lower()
                    self.assertIn("target_actor_address", installed)
                    self.assertIn("message__conversation", installed)
                    self.assertNotIn("to_role", installed)
                    self.assertNotIn("from_role", installed)

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

    def test_pm_define_scope_teaches_track_boundary_heuristics_without_routing_rules(self) -> None:
        text = self._pm_skill_file("define-scope").read_text(encoding="utf-8").lower()
        for token in (
            "use a track as a shared product outcome thread",
            "reuse an active track when the work advances the same outcome, lifecycle, and proof path",
            "create a new track when the outcome, lifecycle, collaborators, or proof path should be tracked independently",
            "use private tasks for active-role work management",
            "use requests for durable cross-role asks",
            "use comments/messages for discussion, not product lifecycle state",
            "context.get.tool_catalog",
            "python3 scripts/turn_runtime.py status",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "every feature phrase creates a track",
            "every user request maps to exactly one track",
            "always create a task after creating a track",
            "always ask design/dev/test after pm writes requirements",
            "one-track-per-feature",
            "**payload:**",
            "payload_fields",
        ):
            self.assertNotIn(forbidden, text)

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

    def test_implement_scoped_change_teaches_buddyswitch_tdd_default(self) -> None:
        text = self._dev_skill_text("implement-scoped-change")
        for token in (
            "failing test first",
            "confirm the failure",
            "smallest direct change",
            "locked source root",
            "exception reason",
            "after green",
            "do not silently change product scope",
        ):
            self.assertIn(token, text)
        self.assertNotIn("when practical", text)

    def test_debug_regression_teaches_systematic_root_cause_loop(self) -> None:
        text = self._dev_skill_text("debug-regression")
        for token in (
            "reproduce",
            "root cause",
            "trace",
            "working example",
            "single hypothesis",
            "one change",
            "regression test",
            "three",
            "architecture",
            "do not add broad fallback",
            "do not swallow errors",
        ):
            self.assertIn(token, text)

    def test_select_local_verification_requires_fresh_evidence_before_completion_claims(self) -> None:
        text = self._dev_skill_text("select-local-verification")
        for token in (
            "fresh",
            "exit code",
            "command proves",
            "read output",
            "before claiming",
            "blocked",
            "blast radius",
            "no stale output",
        ):
            self.assertIn(token, text)
        self.assertNotIn("should pass", text)

    def test_plan_thin_slice_implementation_skill_covers_scope_file_map_and_verification(self) -> None:
        text = self._dev_skill_text("plan-thin-slice-implementation")
        for token in (
            "## purpose",
            "## use when",
            "## do not use when",
            "## inputs",
            "## steps",
            "## outputs",
            "## guardrails",
            "## stop conditions",
            "## verification",
            "## examples",
            "## counterexamples",
            "smallest verifiable",
            "file map",
            "non-goals",
            "acceptance",
            "verification",
            "product semantics",
            "security",
            "privacy",
            "payment",
            "data migration",
        ):
            self.assertIn(token, text)
        self.assertNotIn("workflow engine", text)
        self.assertNotIn("platform planning", text)

    def test_request_dev_code_review_skill_covers_review_inputs_and_severity(self) -> None:
        text = self._dev_skill_text("request-dev-code-review")
        for token in (
            "requirements",
            "changed files",
            "verification evidence",
            "known risks",
            "spec compliance",
            "code quality",
            "critical",
            "important",
        ):
            self.assertIn(token, text)
        self.assertNotIn("review replaces tests", text)

    def test_handle_review_feedback_skill_requires_verification_before_implementation(self) -> None:
        text = self._dev_skill_text("handle-review-feedback")
        for token in (
            "read",
            "clarify",
            "verify",
            "evaluate",
            "one item at a time",
            "push back",
            "yagni",
            "focused verification",
            "do not blindly implement",
            "stop and clarify",
        ):
            self.assertIn(token, text)

    def test_finish_dev_change_skill_respects_worktree_and_completion_boundaries(self) -> None:
        text = self._dev_skill_text("finish-dev-change")
        for token in (
            "fresh verification",
            "linked worktree",
            "detached head",
            "pull request",
            "keep",
            "discard",
            "explicit confirmation",
            "do not delete launcher-owned",
            "do not merge into main without",
        ):
            self.assertIn(token, text)
        self.assertNotIn("git clean -fd", text)
        self.assertNotIn("git reset --hard", text)

    def test_pressure_test_dev_skill_teaches_skill_behavior_testing(self) -> None:
        text = self._dev_skill_text("pressure-test-dev-skill")
        for token in (
            "pressure scenario",
            "baseline",
            "failure",
            "behavior",
            "verify",
            "static tests",
            "not a one-off",
        ):
            self.assertIn(token, text)

    def test_parallelize_independent_dev_work_skill_requires_disjoint_scope(self) -> None:
        text = self._dev_skill_text("parallelize-independent-dev-work")
        for token in (
            "independent",
            "shared state",
            "overlapping write",
            "sequential dependency",
            "critical path",
            "review and integrate",
            "do not parallelize",
        ):
            self.assertIn(token, text)

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

        self.assertIn("artifact__create_revision", artifact_skill)
        self.assertIn("private draft", artifact_skill)
        self.assertIn("track__add_material", artifact_skill)
        self.assertIn("track__add_proof", artifact_skill)
        self.assertNotIn("published_to_track", artifact_skill)
        self.assertNotIn("content.prd", artifact_skill)
        self.assertNotIn("kind=prd", artifact_skill)

        self.assertIn("track__add_material", track_skill)
        self.assertIn("track__add_proof", track_skill)
        self.assertIn("artifact__get", track_skill)
        self.assertNotIn("content.prd", track_skill)
        self.assertNotIn("kind=prd", track_skill)
        self.assertNotIn("published_to_track", track_skill)

    def test_pm_contract_and_agents_align_with_generic_skill_surface(self) -> None:
        contract = (ROOT / "framework/contracts/pm.md").read_text(encoding="utf-8").lower()
        agents = (ROOT / "tools/launcher/assets/roles/pm/AGENTS.md").read_text(encoding="utf-8").lower()
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
        self.assertIn("native buddyswitch env mcp tools", contract)
        self.assertIn("context.get.tool_catalog", contract)
        self.assertIn("python3 scripts/turn_runtime.py status", contract)
        self.assertNotIn("python3 scripts/env/client.py", combined)

    def test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs(self) -> None:
        skill_paths = {
            "task": ROOT / "buddyswitch/skills/shared/task-management/SKILL.md",
            "track": ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            "artifact": ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
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
