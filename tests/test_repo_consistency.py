#!/usr/bin/env python3
"""Repository consistency checks for the current BuddySwitch architecture."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402

CANONICAL_PATHS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / ".codex",
    ROOT / "framework" / "docs",
    ROOT / "scripts",
    ROOT / "buddyswitch" / "manifest.toml",
)
TEXT_SUFFIXES = {".md", ".toml", ".py", ".json"}
DESIGN_SKILL_PACKAGE_ROOTS = (
    ROOT / "buddyswitch" / "skills" / "design" / "product-design-spec",
    ROOT / "buddyswitch" / "skills" / "design" / "experience-shaping",
    ROOT / "buddyswitch" / "skills" / "design" / "activation-and-first-value",
    ROOT / "buddyswitch" / "skills" / "design" / "initiative-and-intervention",
    ROOT / "buddyswitch" / "skills" / "design" / "execution-boundaries",
    ROOT / "buddyswitch" / "skills" / "design" / "memory-and-context",
    ROOT / "buddyswitch" / "skills" / "design" / "conversation-and-clarity",
    ROOT / "buddyswitch" / "skills" / "design" / "recovery-and-escalation",
    ROOT / "buddyswitch" / "skills" / "design" / "design-critique",
)
DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME = {package_root.name: package_root for package_root in DESIGN_SKILL_PACKAGE_ROOTS}
DESIGN_SPECIALIST_TEMPLATE_PATHS = (
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["experience-shaping"] / "assets" / "design-brief-template.md",
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["activation-and-first-value"] / "assets" / "activation-spec-template.md",
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["initiative-and-intervention"] / "assets" / "initiative-spec-template.md",
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["execution-boundaries"] / "assets" / "boundaries-spec-template.md",
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["memory-and-context"] / "assets" / "memory-spec-template.md",
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["conversation-and-clarity"] / "assets" / "conversation-spec-template.md",
    DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["recovery-and-escalation"] / "assets" / "recovery-spec-template.md",
)
ARTIFACT_SKILL_DOCS = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "SKILL.md",
    *(package_root / "SKILL.md" for package_root in DESIGN_SKILL_PACKAGE_ROOTS),
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "SKILL.md",
)
SKILL_TOMLS = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "pm" / "track-manager" / "skill.toml",
    *(package_root / "skill.toml" for package_root in DESIGN_SKILL_PACKAGE_ROOTS),
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "skill.toml",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "skill.toml",
)
MARKET_SCHEMA_PATHS = (
    ROOT / "framework" / "schemas" / "market" / "research-scan.json",
    ROOT / "framework" / "schemas" / "market" / "pmf-recon.json",
    ROOT / "framework" / "schemas" / "market" / "customer-discovery.json",
    ROOT / "framework" / "schemas" / "market" / "positioning-copy.json",
    ROOT / "framework" / "schemas" / "market" / "channel-discovery.json",
    ROOT / "framework" / "schemas" / "market" / "launch-prep.json",
)
MARKET_COCKPIT_METADATA = {
    "execution_mode": "market-browser-native",
    "browser_mode": "headed-only",
    "browser_profile": "shared-market",
    "browser_executor": "chrome-devtools-market",
    "discovery_mode": "browser-native",
    "login_policy": "mandatory-takeover",
    "fallback_policy": "no-silent-degrade",
    "session_continuity": "shared-cockpit",
    "evidence_capture_level": "medium",
}
MARKET_REQUIRED_TOOLS = ["chrome-devtools-market"]
MARKET_EVIDENCE_FIELDS = (
    "source_id",
    "url",
    "source_type",
    "accessed_at",
    "claim_excerpt",
    "page_title",
    "auth_state",
    "query_or_filter_used",
    "interaction_steps_summary",
    "screenshot_ref_or_snapshot_ref",
)
NEW_MARKET_TEMPLATE_SCHEMAS = {
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md": ROOT / "framework" / "schemas" / "market" / "research-scan.json",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "pmf-report-template.md": ROOT / "framework" / "schemas" / "market" / "pmf-recon.json",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "assets" / "interview-brief-template.md": ROOT / "framework" / "schemas" / "market" / "customer-discovery.json",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "assets" / "positioning-brief-template.md": ROOT / "framework" / "schemas" / "market" / "positioning-copy.json",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "assets" / "channel-plan-template.md": ROOT / "framework" / "schemas" / "market" / "channel-discovery.json",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "assets" / "launch-prep-template.md": ROOT / "framework" / "schemas" / "market" / "launch-prep.json",
}
ACTIVE_MARKET_CONTRACT_DOCS = (
    ROOT / "framework" / "docs" / "market-research-cockpit.md",
    ROOT / "framework" / "contracts" / "market.md",
    ROOT / "framework" / "docs" / "switch-spec.md",
    ROOT / "framework" / "templates" / "research-report.md",
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "SKILL.md",
)


def _markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    lines = text.splitlines()
    try:
        start_index = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(f"missing section '{heading}'") from exc

    section_lines: list[str] = []
    for line in lines[start_index + 1 :]:
        if line.startswith("## "):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def _schema_heading(field_name: str) -> str:
    return "## " + field_name.replace("_", " ").title()


def _required_template_tokens(schema: dict[str, object]) -> list[str]:
    schema_type = schema.get("type")
    if schema_type == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(props, dict) or not isinstance(required, list):
            return []
        tokens: list[str] = []
        for key in required:
            if not isinstance(key, str):
                continue
            tokens.append(f"{key}:")
            child = props.get(key)
            if isinstance(child, dict):
                tokens.extend(_required_template_tokens(child))
        return list(dict.fromkeys(tokens))

    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return _required_template_tokens(items)
    return []


class RepoConsistencyTests(unittest.TestCase):
    def test_legacy_agents_skills_tree_is_removed(self) -> None:
        self.assertFalse((ROOT / ".agents").exists())

    def test_canonical_paths_do_not_activate_legacy_agents_skills(self) -> None:
        forbidden = (
            "repo-local skills under `.agents/skills/`",
            "relevant repo-local skills in `.agents/skills/`",
            "`.agents/skills/**/SKILL.md`",
        )
        checked_files: list[Path] = []

        for base in CANONICAL_PATHS:
            if base.is_file():
                paths = [base]
            else:
                paths = [
                    path
                    for path in base.rglob("*")
                    if path.is_file() and path.suffix in TEXT_SUFFIXES and "__pycache__" not in path.parts
                ]
            for path in paths:
                checked_files.append(path)
                text = path.read_text(encoding="utf-8")
                for needle in forbidden:
                    self.assertNotIn(needle, text, msg=f"Found legacy native-skill activation in {path.relative_to(ROOT)}")

        self.assertTrue(checked_files)

    def test_active_docs_use_canonical_not_strict_switch_wording(self) -> None:
        targets = (
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / ".codex" / "agents" / "router.toml",
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

        self.assertNotIn("Use the strict directive:", combined)
        self.assertNotIn("Parse with strict syntax only.", combined)
        self.assertNotIn("is the only canonical ui", combined.lower())
        self.assertNotIn("keep strict syntax handling", combined.lower())
        self.assertIn("canonical", combined.lower())
        self.assertIn("minor cli spacing variation", combined.lower())
        self.assertIn("advisory", combined.lower())
        self.assertIn("manual/debug", combined.lower())

    def test_control_docs_define_failure_actions_and_structure_only_schema_boundary(self) -> None:
        targets = (
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "docs" / "reviews" / "buddyswitch-control-layer" / "07-implementation-status.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("normalize", combined)
        self.assertIn("warn", combined)
        self.assertIn("ask", combined)
        self.assertIn("reject", combined)
        self.assertIn("structure-only", combined)
        self.assertIn("not a business-quality review", combined)

    def test_cleanup_docs_reference_run_content_without_legacy_artifact_content(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
            ROOT / "docs" / "reviews" / "buddyswitch-control-layer" / "07-implementation-status.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("buddyswitch/content/runs", combined)
        self.assertIn("run content", combined)
        self.assertNotIn("legacy " + "artifact content", combined)
        self.assertNotIn("buddyswitch/content/" + "artifacts", combined)

    def test_active_docs_and_skills_do_not_use_track_mode_field(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs",
            ROOT / "buddyswitch" / "skills",
        )
        checked_files: list[Path] = []
        for target in targets:
            if target.is_file():
                paths = [target]
            else:
                paths = [path for path in target.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES]
            for path in paths:
                checked_files.append(path)
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("track_mode", text, msg=f"track_mode should not appear in {path.relative_to(ROOT)}")
        self.assertTrue(checked_files)

    def test_active_docs_define_three_section_terminal_contract(self) -> None:
        targets = (
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "switch-spec.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("receipt", combined)
        self.assertIn("commands", combined)
        self.assertIn("summary", combined)
        self.assertIn("reference_switches", combined)
        self.assertIn("recommended_switch", combined)
        self.assertIn("related_run_ids", combined)
        self.assertIn("continue_current_task", combined)
        self.assertIn("debug", combined)

    def test_switch_spec_directs_multi_skill_hosts_to_per_skill_selection_maps(self) -> None:
        text = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")

        self.assertIn("artifact_selection_by_skill[chosen_skill_id]", text)
        self.assertIn("run_instructions_by_skill[chosen_skill_id]", text)
        self.assertNotIn("read `track_artifact_index` and `artifact_selection`", text)
        self.assertNotIn("artifact_selection.selected_inputs", text)

    def test_switch_spec_describes_neutral_top_level_run_instructions_for_multi_skill_resolves(self) -> None:
        text = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")

        self.assertIn("top-level `artifact_selection` is `None` for multi-skill resolves", text)
        self.assertIn("top-level `run_instructions` remains available as neutral host guidance", text)
        self.assertIn("chosen-skill-specific selected inputs and read commands come from", text)
        self.assertIn("artifact_selection_by_skill[chosen_skill_id]", text)
        self.assertIn("run_instructions_by_skill[chosen_skill_id]", text)

    def test_contracts_and_skills_define_summary_selection_semantics(self) -> None:
        contracts = (
            ROOT / "framework" / "contracts" / "market.md",
            ROOT / "framework" / "contracts" / "pm.md",
            ROOT / "framework" / "contracts" / "design.md",
            ROOT / "framework" / "contracts" / "dev.md",
            ROOT / "framework" / "contracts" / "test.md",
        )
        shared_runtime_rules = ROOT / "framework" / "docs" / "skill-runtime-shared-rules.md"

        for path in contracts:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("execution_summary", text, msg=f"missing execution_summary rule in {path.relative_to(ROOT)}")
            self.assertIn("artifact.summary", text, msg=f"missing artifact.summary rule in {path.relative_to(ROOT)}")
            self.assertIn("selection-ready", text, msg=f"missing selection-ready wording in {path.relative_to(ROOT)}")

        shared_text = shared_runtime_rules.read_text(encoding="utf-8").lower()
        self.assertIn("execution_summary", shared_text, msg="missing execution summary rule in shared runtime rules")
        self.assertIn("artifact.summary", shared_text, msg="missing artifact.summary rule in shared runtime rules")
        self.assertIn("selection-ready", shared_text, msg="missing selection-ready wording in shared runtime rules")
        self.assertIn("task and artifact boundaries", shared_text, msg="missing task/artifact boundary section in shared runtime rules")
        self.assertIn("durable output paths", shared_text, msg="missing durable output path section in shared runtime rules")

        for path in ARTIFACT_SKILL_DOCS:
            with self.subTest(skill_doc=str(path.relative_to(ROOT))):
                if not path.exists():
                    # Existence failures are owned by the dedicated package/file existence tests.
                    continue
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("framework/docs/skill-runtime-shared-rules.md", text, msg=f"missing shared runtime rules reference in {path.relative_to(ROOT)}")
                self.assertNotIn("## execution summary rule", text, msg=f"execution summary rule should be shared in {path.relative_to(ROOT)}")
                self.assertNotIn("## track/object handling", text, msg=f"track/object handling should be shared in {path.relative_to(ROOT)}")
                self.assertNotIn("## output path", text, msg=f"output path should be shared in {path.relative_to(ROOT)}")

    def test_skill_toml_descriptions_use_activation_style(self) -> None:
        disallowed_summary_tokens = (
            "workflow",
            "steps",
            "template",
            "persist",
            "execution summary",
            "artifact.summary",
        )
        for path in SKILL_TOMLS:
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                if not path.exists():
                    # Existence failures are owned by the dedicated package/file existence tests.
                    continue
                text = path.read_text(encoding="utf-8").splitlines()
                description_lines = [line for line in text if line.startswith("description = ")]
                self.assertEqual(1, len(description_lines), msg=f"expected one description in {path.relative_to(ROOT)}")
                self.assertTrue(
                    description_lines[0].startswith('description = "Use when '),
                    msg=f"description must use activation style in {path.relative_to(ROOT)}",
                )
                lowered = description_lines[0].lower()
                for token in disallowed_summary_tokens:
                    self.assertNotIn(
                        token,
                        lowered,
                        msg=f"description should not summarize workflow details in {path.relative_to(ROOT)}",
                    )

    def test_skill_toml_output_schemas_exist_and_are_parseable_json(self) -> None:
        for path in SKILL_TOMLS:
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                if not path.exists():
                    # Existence failures are owned by the dedicated package/file existence tests.
                    continue
                schema_path = None
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("output_schema = "):
                        schema_path = line.split("=", 1)[1].strip().strip('"')
                        break
                self.assertIsNotNone(schema_path, msg=f"missing output_schema in {path.relative_to(ROOT)}")
                resolved_schema = ROOT / schema_path
                self.assertTrue(
                    resolved_schema.exists(),
                    msg=f"missing output schema for {path.relative_to(ROOT)}: {schema_path}",
                )
                with resolved_schema.open("r", encoding="utf-8") as handle:
                    parsed_schema = json.load(handle)
                self.assertIsInstance(
                    parsed_schema,
                    dict,
                    msg=f"output schema must be a JSON object in {resolved_schema.relative_to(ROOT)}",
                )

    def test_pm_and_design_skill_metadata_use_explicit_market_inputs(self) -> None:
        cases = {
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "skill.toml": [
                "market-scan",
                "pmf-report",
                "customer-discovery",
                "positioning-brief",
                "channel-plan",
                "launch-prep",
                "requirements",
                "track",
            ],
            ROOT / "buddyswitch" / "skills" / "design" / "product-design-spec" / "skill.toml": [
                "prd",
                "positioning-brief",
                "launch-prep",
                "requirements",
                "track",
            ],
        }

        for path, expected_slots in cases.items():
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                parsed = env_manifest._load_toml(path)  # type: ignore[attr-defined]
                self.assertEqual(parsed["input_slots"], expected_slots)
                self.assertEqual(parsed["consumes"], expected_slots)

    def test_design_contract_describes_functional_ai_product_design_system(self) -> None:
        text = (ROOT / "framework" / "contracts" / "design.md").read_text(encoding="utf-8").lower()

        self.assertIn("functional ai product", text)
        self.assertIn("design-spec", text)
        self.assertIn("design-review", text)
        self.assertNotIn("define information architecture (ia).", text)

    def test_market_schemas_share_canonical_evidence_and_traceability_fields(self) -> None:
        for path in MARKET_SCHEMA_PATHS:
            with self.subTest(schema=str(path.relative_to(ROOT))):
                schema = json.loads(path.read_text(encoding="utf-8"))
                artifact_content = schema["properties"]["artifact_content"]
                evidence_required = artifact_content["properties"]["evidence"]["items"]["required"]
                traceability_required = artifact_content["properties"]["source_traceability"]["items"]["required"]

                self.assertIn("claim_excerpt", evidence_required)
                self.assertNotIn("summary", evidence_required)
                self.assertIn("conclusion", traceability_required)
                self.assertNotIn("claim", traceability_required)

    def test_market_skills_share_market_cockpit_execution_metadata(self) -> None:
        for path in SKILL_TOMLS[:6]:
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                parsed = env_manifest._load_toml(path)  # type: ignore[attr-defined]
                for key, value in MARKET_COCKPIT_METADATA.items():
                    self.assertEqual(parsed[key], value, msg=f"{path.relative_to(ROOT)} missing {key}={value}")
                self.assertEqual(
                    parsed["required_tools"],
                    MARKET_REQUIRED_TOOLS,
                    msg=f"{path.relative_to(ROOT)} missing required_tools={MARKET_REQUIRED_TOOLS}",
                )

    def test_market_skill_docs_reference_shared_cockpit_doc(self) -> None:
        for path in ARTIFACT_SKILL_DOCS[:6]:
            with self.subTest(skill_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("framework/docs/market-research-cockpit.md", text)
                self.assertIn("headed", text)
                self.assertIn("mandatory takeover", text)
                self.assertIn("shared-market", text)

    def test_market_skill_docs_start_with_execution_order(self) -> None:
        for path in ARTIFACT_SKILL_DOCS[:6]:
            with self.subTest(skill_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("## execution order", text)
                self.assertIn("before any market research", text)
                self.assertIn("pause for mandatory takeover", text)
                self.assertIn("do not continue with snippet-only or text-only research", text)

    def test_market_active_contract_docs_require_browser_native_wording(self) -> None:
        required_tokens = ("chrome-devtools-market", "browser-native", "user-approved")
        forbidden_tokens = ("search-assist",)

        for path in ACTIVE_MARKET_CONTRACT_DOCS:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in required_tokens:
                    self.assertIn(token, text, msg=f"{path.relative_to(ROOT)} missing required token '{token}'")
                for token in forbidden_tokens:
                    self.assertNotIn(token, text, msg=f"{path.relative_to(ROOT)} must not include '{token}'")

    def test_market_schemas_share_market_cockpit_evidence_fields(self) -> None:
        for path in MARKET_SCHEMA_PATHS:
            with self.subTest(schema=str(path.relative_to(ROOT))):
                schema = json.loads(path.read_text(encoding="utf-8"))
                evidence_required = schema["properties"]["artifact_content"]["properties"]["evidence"]["items"]["required"]
                for field_name in MARKET_EVIDENCE_FIELDS:
                    self.assertIn(field_name, evidence_required, msg=f"{path.relative_to(ROOT)} missing {field_name}")

    def test_market_contract_separates_skill_ids_from_output_slots_and_common_fields(self) -> None:
        contract_path = ROOT / "framework" / "contracts" / "market.md"
        text = contract_path.read_text(encoding="utf-8")

        must_do_section = _markdown_section(text, "Must Do")
        select_line = next(line for line in must_do_section.splitlines() if "Select the executable market skill" in line)
        for skill_id in (
            "research-scan",
            "pmf-recon",
            "customer-discovery",
            "positioning-copy",
            "channel-discovery",
            "launch-prep",
        ):
            self.assertIn(skill_id, select_line)
        for slot_name in ("market-scan", "pmf-report", "positioning-brief", "channel-plan"):
            self.assertNotIn(slot_name, select_line)

        slot_section = _markdown_section(text, "Output Slot Taxonomy")
        for slot_name in (
            "market-scan",
            "pmf-report",
            "customer-discovery",
            "positioning-brief",
            "channel-plan",
            "launch-prep",
        ):
            self.assertIn(slot_name, slot_section)

        output_section = _markdown_section(text, "Required Output Structure")
        for common_field in ("research_question", "evidence", "source_traceability", "conclusion"):
            self.assertIn(common_field, output_section)
        for non_common_field in ("research_strategy", "channel_plan", "iteration_log"):
            self.assertNotIn(non_common_field, output_section)

    def test_market_contract_lists_medium_strength_evidence_fields(self) -> None:
        contract_path = ROOT / "framework" / "contracts" / "market.md"
        evidence_section = _markdown_section(
            contract_path.read_text(encoding="utf-8"),
            "Evidence And Traceability Requirements",
        )
        for field_name in MARKET_EVIDENCE_FIELDS:
            self.assertIn(field_name, evidence_section)

    def test_market_contract_describes_shared_cockpit_without_implying_multi_skill_runs(self) -> None:
        contract_text = (ROOT / "framework" / "contracts" / "market.md").read_text(encoding="utf-8").lower()
        self.assertIn("run the selected market skill in the shared headed cockpit", contract_text)
        self.assertNotIn("run all six market skills", contract_text)

    def test_market_contract_chat_return_blocks_match_schema_surface(self) -> None:
        chat_return_section = _markdown_section(
            (ROOT / "framework" / "contracts" / "market.md").read_text(encoding="utf-8"),
            "Chat Return Blocks",
        ).lower()
        self.assertNotIn("suggested next switch", chat_return_section)

    def test_market_cockpit_doc_defines_selected_skill_execution_boundary(self) -> None:
        cockpit_doc = (ROOT / "framework" / "docs" / "market-research-cockpit.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("selected_skill_packet", cockpit_doc)
        self.assertIn("host stays the only executor", cockpit_doc)
        self.assertIn("these six skills stay separate", cockpit_doc)
        self.assertIn("not a second source of truth", cockpit_doc)

    def test_dev0039_docs_keep_only_active_selected_skill_plans(self) -> None:
        docs_dir = ROOT / "docs" / "dev0039"
        if not docs_dir.exists():
            self.skipTest("docs/dev0039 is absent in the current worktree")
        names = {path.name for path in docs_dir.glob("*.md")}

        self.assertIn("2026-04-16-selected-skill-injection-execution-plan.md", names)
        self.assertIn("2026-04-16-selected-skill-injection-closure-cleanup-plan.md", names)
        self.assertNotIn("2026-04-16-market-research-cockpit-design.md", names)
        self.assertNotIn("2026-04-16-market-cockpit-host-execution-bridge-plan.md", names)
        self.assertNotIn("2026-04-16-market-research-cockpit-implementation-plan.md", names)

    def test_switch_spec_documents_selected_skill_packet_fields(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("execution_steps", switch_spec)
        self.assertIn("execution_constraints", switch_spec)
        self.assertIn("output_schema_path", switch_spec)

    def test_switch_spec_defers_runtime_order_to_execution_steps(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("treat `selected_skill_packet.execution_steps` as ordered requirements", switch_spec)
        self.assertNotIn("read `selected_skill_packet.selected_inputs` by slot before other work", switch_spec)

    def test_top_level_docs_define_selected_skill_packet_flow(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "AGENTS.md",
                ROOT / "README.md",
                ROOT / ".codex" / "agents" / "router.toml",
                ROOT / "framework" / "docs" / "switch-spec.md",
            )
        ).lower()

        self.assertIn("prepare-execution", combined)
        self.assertIn("selected_skill_packet", combined)
        self.assertIn("inject `selected_skill_packet.skill_instructions` verbatim", combined)
        self.assertIn("buddyswitch does not execute host tools", combined)

    def test_dev0039_active_plans_define_selected_skill_packet_flow(self) -> None:
        docs = (
            ROOT / "docs" / "dev0039" / "2026-04-16-selected-skill-injection-execution-plan.md",
            ROOT / "docs" / "dev0039" / "2026-04-16-selected-skill-injection-closure-cleanup-plan.md",
        )
        if not all(path.exists() for path in docs):
            self.skipTest("active dev0039 selected-skill plan docs are absent in the current worktree")
        combined = "\n".join(path.read_text(encoding="utf-8") for path in docs).lower()

        self.assertIn("selected_skill_packet", combined)
        self.assertIn("explicit skill injection", combined)
        self.assertIn("buddyswitch does not execute host tools", combined)

    def test_switch_spec_lists_prepare_execution_runtime_error(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")
        self.assertIn("E_RUNTIME_PREPARE_EXECUTION", switch_spec)

    def test_new_market_templates_expose_schema_derived_contract_fields(self) -> None:
        for path, schema_path in NEW_MARKET_TEMPLATE_SCHEMAS.items():
            with self.subTest(template=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                artifact_content = schema["properties"]["artifact_content"]
                required_fields = artifact_content["required"]
                props = artifact_content["properties"]

                for field_name in required_fields:
                    self.assertIn(
                        _schema_heading(field_name).lower(),
                        text,
                        msg=f"missing section for '{field_name}' in {path.relative_to(ROOT)}",
                    )
                    field_schema = props[field_name]
                    for token in _required_template_tokens(field_schema):
                        self.assertIn(
                            token.lower(),
                            text,
                            msg=f"missing schema-derived token '{token}' in {path.relative_to(ROOT)}",
                        )

    def test_skill_packages_include_skill_toml_and_instruction_markdown(self) -> None:
        expected_packages = (
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan",
            ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon",
            ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery",
            ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy",
            ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery",
            ROOT / "buddyswitch" / "skills" / "market" / "launch-prep",
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd",
            ROOT / "buddyswitch" / "skills" / "pm" / "track-manager",
            *DESIGN_SKILL_PACKAGE_ROOTS,
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test",
        )
        for package_root in expected_packages:
            with self.subTest(package=str(package_root.relative_to(ROOT))):
                self.assertTrue((package_root / "skill.toml").exists(), msg=f"missing skill.toml in {package_root}")
                self.assertTrue((package_root / "SKILL.md").exists(), msg=f"missing SKILL.md in {package_root}")

    def test_skill_instructions_are_markdown_only_without_frontmatter_metadata(self) -> None:
        expected_packages = (
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan",
            ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon",
            ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery",
            ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy",
            ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery",
            ROOT / "buddyswitch" / "skills" / "market" / "launch-prep",
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd",
            ROOT / "buddyswitch" / "skills" / "pm" / "track-manager",
            *DESIGN_SKILL_PACKAGE_ROOTS,
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test",
        )
        for package_root in expected_packages:
            with self.subTest(package=str(package_root.relative_to(ROOT))):
                skill_doc = package_root / "SKILL.md"
                if not skill_doc.exists():
                    # Existence failures are owned by the dedicated package/file existence tests.
                    continue
                lines = skill_doc.read_text(encoding="utf-8").splitlines()
                self.assertTrue(lines, msg=f"empty SKILL.md in {package_root}")
                self.assertNotEqual(lines[0].strip(), "---", msg=f"frontmatter not allowed in {skill_doc.relative_to(ROOT)}")
                self.assertTrue(lines[0].startswith("# "), msg=f"SKILL.md must start with heading in {skill_doc.relative_to(ROOT)}")

    def test_template_references_are_materialized_in_assets(self) -> None:
        expected_assets = (
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "pmf-report-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "evidence-log-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "assets" / "interview-brief-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "assets" / "positioning-brief-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "assets" / "channel-plan-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "assets" / "launch-prep-template.md",
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "assets" / "prd-template.md",
            DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["product-design-spec"] / "assets" / "design-spec-template.md",
            DESIGN_SKILL_PACKAGE_ROOTS_BY_NAME["design-critique"] / "assets" / "design-review-template.md",
            *DESIGN_SPECIALIST_TEMPLATE_PATHS,
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
        )
        for path in expected_assets:
            with self.subTest(asset=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), msg=f"missing template asset: {path.relative_to(ROOT)}")

    def test_active_docs_use_slot_revision_and_package_contract_language(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
            ROOT / "framework" / "docs" / "track-registry.md",
            ROOT / "scripts" / "env_cleanup.py",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("artifact slot", combined)
        self.assertIn("revision", combined)
        self.assertIn("skill package", combined)
        self.assertNotIn("latest_artifact_id", combined)
        self.assertNotIn("suggested_next_switch", combined)

    def test_architecture_overview_describes_six_skill_market_collection(self) -> None:
        text = (ROOT / "framework" / "docs" / "architecture-overview.md").read_text(encoding="utf-8")

        self.assertIn("customer-discovery", text)
        self.assertIn("positioning-copy", text)
        self.assertIn("channel-discovery", text)
        self.assertIn("launch-prep", text)
        self.assertNotIn('eligible_skills = ["research-scan", "pmf-recon"]', text)


if __name__ == "__main__":
    unittest.main()
