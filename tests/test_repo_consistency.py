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
ARTIFACT_SKILL_DOCS = (
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "SKILL.md",
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
    ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "skill.toml",
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
NEW_MARKET_TEMPLATE_SCHEMAS = {
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "assets" / "interview-brief-template.md": ROOT / "framework" / "schemas" / "market" / "customer-discovery.json",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "assets" / "positioning-brief-template.md": ROOT / "framework" / "schemas" / "market" / "positioning-copy.json",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "assets" / "channel-plan-template.md": ROOT / "framework" / "schemas" / "market" / "channel-discovery.json",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "assets" / "launch-prep-template.md": ROOT / "framework" / "schemas" / "market" / "launch-prep.json",
}


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
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

        self.assertNotIn("Use the strict directive:", combined)
        self.assertNotIn("Parse with strict syntax only.", combined)
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
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "skill.toml": [
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

    def test_design_docs_treat_market_context_as_explicit_upstream_inputs(self) -> None:
        targets = (
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "SKILL.md",
            ROOT / "framework" / "contracts" / "design.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

        self.assertNotIn("Optional `positioning-brief` and `launch-prep`", combined)
        self.assertIn("explicit upstream", combined.lower())
        self.assertIn("positioning-brief", combined)
        self.assertIn("launch-prep", combined)
        self.assertIn("landing", combined.lower())
        self.assertIn("onboarding", combined.lower())

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

    def test_every_skill_package_has_metadata_and_instruction_files(self) -> None:
        expected_packages = (
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan",
            ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon",
            ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery",
            ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy",
            ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery",
            ROOT / "buddyswitch" / "skills" / "market" / "launch-prep",
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd",
            ROOT / "buddyswitch" / "skills" / "pm" / "track-manager",
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec",
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
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec",
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
            ROOT / "buddyswitch" / "skills" / "design" / "ia-spec" / "assets" / "design-spec-template.md",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
        )
        for path in expected_assets:
            with self.subTest(asset=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), msg=f"missing template asset: {path.relative_to(ROOT)}")

    def test_active_docs_use_slot_revision_and_package_contract_language(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "switch-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("artifact slot", combined)
        self.assertIn("revision", combined)
        self.assertIn("skill package", combined)
        self.assertNotIn("latest_artifact_id", combined)
        self.assertNotIn("suggested_next_switch", combined)


if __name__ == "__main__":
    unittest.main()
