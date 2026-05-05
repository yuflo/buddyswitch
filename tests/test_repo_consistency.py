#!/usr/bin/env python3
"""Repository consistency checks for the current BuddySwitch architecture."""

from __future__ import annotations

import json
import re
import subprocess
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
    ROOT / "buddyswitch" / "skills" / "pm" / "track-manager" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "SKILL.md",
)
MARKET_SCHEMA_PATHS = (
    ROOT / "framework" / "schemas" / "market" / "market-result.json",
)
BUDDY_RESULT_SCHEMA_PATHS = {
    "pm": ROOT / "framework" / "schemas" / "pm" / "pm-result.json",
    "dev": ROOT / "framework" / "schemas" / "dev" / "dev-result.json",
    "test": ROOT / "framework" / "schemas" / "test" / "test-result.json",
    "market": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    "design": ROOT / "framework" / "schemas" / "design" / "design-result.json",
}
ARTIFACT_SKILL_TO_BUDDY_RESULT_SCHEMA = {
    "research-scan": "framework/schemas/market/market-result.json",
    "pmf-recon": "framework/schemas/market/market-result.json",
    "customer-discovery": "framework/schemas/market/market-result.json",
    "positioning-copy": "framework/schemas/market/market-result.json",
    "channel-discovery": "framework/schemas/market/market-result.json",
    "launch-prep": "framework/schemas/market/market-result.json",
    "write-prd": "framework/schemas/pm/pm-result.json",
    "track-manager": "framework/schemas/pm/pm-result.json",
    "shape-prototype": "framework/schemas/design/design-result.json",
    "implement-task": "framework/schemas/dev/dev-result.json",
    "smoke-test": "framework/schemas/test/test-result.json",
}
ARTIFACT_SKILL_TO_OUTPUT_SLOT = {
    "research-scan": "market-scan",
    "pmf-recon": "pmf-report",
    "customer-discovery": "customer-discovery",
    "positioning-copy": "positioning-brief",
    "channel-discovery": "channel-plan",
    "launch-prep": "launch-prep",
    "write-prd": "prd",
    "track-manager": "track-operation",
    "shape-prototype": "design-handoff",
    "implement-task": "implementation-report",
    "smoke-test": "smoke-test",
}
LEGACY_ARTIFACT_SCHEMA_PATHS = {
    "framework/schemas/pm/" + "write-prd" + ".json",
    "framework/schemas/dev/" + "implement-task" + ".json",
    "framework/schemas/test/" + "smoke-test" + ".json",
    "framework/schemas/design/" + "shape-prototype" + ".json",
    "framework/schemas/market/" + "research-scan" + ".json",
    "framework/schemas/market/" + "pmf-recon" + ".json",
    "framework/schemas/market/" + "customer-discovery" + ".json",
    "framework/schemas/market/" + "positioning-copy" + ".json",
    "framework/schemas/market/" + "channel-discovery" + ".json",
    "framework/schemas/market/" + "launch-prep" + ".json",
}
BROWSER_COCKPIT_METADATA = {
    "execution_mode": "browser-cockpit-native",
    "browser_mode": "headed-only",
    "browser_profile": "instance-browser",
    "browser_executor": "chrome-devtools-cockpit",
    "discovery_mode": "browser-native",
    "login_policy": "mandatory-takeover",
    "fallback_policy": "no-silent-degrade",
    "session_continuity": "instance-cockpit",
    "evidence_capture_level": "medium",
}
BROWSER_COCKPIT_REQUIRED_TOOLS = ["chrome-devtools-cockpit"]
EXPECTED_MARKET_TOOL_SCOPE_PROFILE = "market-browser-native"
NEW_MARKET_TEMPLATE_SCHEMAS = {
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "pmf-report-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "assets" / "interview-brief-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "assets" / "positioning-brief-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "assets" / "channel-plan-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "assets" / "launch-prep-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
}
COMMON_RESULT_ENVELOPE_KEYS = (
    "execution_summary",
    "working_notes",
    "deliverables_or_changed_files",
    "artifact_content",
)
ARTIFACT_TEMPLATE_SCHEMAS = {
    ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "assets" / "prd-template.md": ROOT / "framework" / "schemas" / "pm" / "pm-result.json",
    ROOT / "buddyswitch" / "skills" / "pm" / "track-manager" / "assets" / "track-operation-template.md": ROOT / "framework" / "schemas" / "pm" / "pm-result.json",
    ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md": ROOT / "framework" / "schemas" / "dev" / "dev-result.json",
    ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md": ROOT / "framework" / "schemas" / "test" / "test-result.json",
    ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "assets" / "design-handoff-template.md": ROOT / "framework" / "schemas" / "design" / "design-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "pmf-report-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "evidence-log-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "assets" / "interview-brief-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "assets" / "positioning-brief-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "assets" / "channel-plan-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "assets" / "launch-prep-template.md": ROOT / "framework" / "schemas" / "market" / "market-result.json",
}
MARKET_TEMPLATE_SPECIALIZED_KEYS = {
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md": "research_scan",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "pmf-report-template.md": "pmf_recon",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "assets" / "evidence-log-template.md": "pmf_recon",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "assets" / "interview-brief-template.md": "customer_discovery",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "assets" / "positioning-brief-template.md": "positioning_copy",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "assets" / "channel-plan-template.md": "channel_discovery",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "assets" / "launch-prep-template.md": "launch_prep",
}
ACTIVE_MARKET_CONTRACT_DOCS = (
    ROOT / "framework" / "docs" / "browser-cockpit.md",
    ROOT / "framework" / "contracts" / "market.md",
    ROOT / "framework" / "templates" / "research-report.md",
    ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "SKILL.md",
    ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "SKILL.md",
)
PARALLEL_CONTRACT_FILES = (
    ROOT / "framework" / "contracts" / "prepare-turn-context.json",
    ROOT / "framework" / "contracts" / "persist-skill-result.json",
    ROOT / "framework" / "contracts" / "workspace-projection.json",
)
ACTIVE_BUDDY_PROMPT_DOCS = tuple(
    ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
    for buddy in ("design", "dev", "market", "pm", "test")
)
LEGACY_RUNTIME_AGENTS = ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md"
LEGACY_ROUTER_PROMPT = ROOT / ".codex" / "agents" / "router.toml"
LEGACY_REMOVED_CONTRACT_FILES = (
    ROOT / "framework" / "contracts" / "switch-grammar.json",
)
UI_SURFACE_ROOTS = (
    ROOT / "framework" / "console",
    ROOT / "projects" / "app",
)
UI_RUNTIME_INTERNAL_TOKENS = (
    "env_store",
    "runtime_store.repositories",
    "runtime_store.projections",
    "turn_runtime",
    "workspace_data",
)
UI_RUNTIME_PATH_TOKENS = (
    "buddyswitch/objects",
    "buddyswitch/content/runs",
    "runs/raw",
    "projects/app/.runtime",
)
CONSOLE_RUNTIME_ENDPOINT = "/api/workspace"
RUNTIME_LOCK_GUARD_SOURCES = (
    ROOT / "tools" / "launcher" / "env.sh",
    ROOT / "tools" / "launcher" / "runtime_lock.py",
    ROOT / "scripts" / "turn_runtime.py",
    ROOT / "scripts" / "runtime_store" / "projections.py",
    ROOT / "tests" / "test_cleanup_system.py",
)
ACTIVE_PRODUCT_PATHS = (
    ROOT / "tools" / "launcher" / "assets",
    ROOT / "scripts",
    ROOT / "buddyswitch" / "manifest.toml",
    ROOT / "README.md",
    ROOT / "framework" / "docs",
    ROOT / "framework" / "contracts",
    ROOT / "framework" / "console",
)
HOME_PATH_GUARD_PATHS = (
    "README.md",
    "AGENTS.md",
    ".codex",
    "framework/docs",
    "framework/templates",
    "scripts",
    "buddyswitch/manifest.toml",
)
HOME_PATH_GUARD_SUFFIXES = {".md", ".toml", ".json", ".yaml", ".yml"}


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


def _tracked_repo_files(paths: tuple[str, ...]) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / relative_path for relative_path in result.stdout.splitlines() if relative_path]


def _manifest_skill_package_roots() -> list[Path]:
    manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
    roots: list[Path] = []
    for skill in manifest.get("skills", []):
        if not isinstance(skill, dict):
            continue
        raw_path = skill.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        roots.append(ROOT / raw_path)
    return roots


class RepoConsistencyTests(unittest.TestCase):
    def test_legacy_agents_skills_tree_is_removed(self) -> None:
        self.assertFalse((ROOT / ".agents").exists())

    def test_runtime_agents_skills_are_documented_as_instance_only(self) -> None:
        self.assertFalse((ROOT / ".agents").exists())
        active_docs = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
            *ACTIVE_BUDDY_PROMPT_DOCS,
        )
        for path in active_docs:
            text = path.read_text(encoding="utf-8")
            if ".agents/skills" in text:
                self.assertIn("instance", text.lower(), msg=f"{path.relative_to(ROOT)} must describe instance-scoped runtime skills")

    def test_active_docs_use_canonical_not_strict_switch_wording(self) -> None:
        self.assertFalse(LEGACY_ROUTER_PROMPT.exists())
        targets = (
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

        self.assertNotIn("Use the strict directive:", combined)
        self.assertNotIn("Parse with strict syntax only.", combined)
        self.assertNotIn("is the only canonical ui", combined.lower())
        self.assertNotIn("keep strict syntax handling", combined.lower())
        self.assertIn("canonical", combined.lower())
        self.assertIn("ordinary request", combined.lower())
        self.assertIn("prepare-turn-context", combined.lower())

    def test_control_docs_define_failure_actions_and_structure_only_schema_boundary(self) -> None:
        targets = (
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("reject", combined)
        self.assertIn("validation errors", combined)
        self.assertIn("identity integrity", combined)

    def test_cleanup_docs_reference_run_content_without_legacy_artifact_content(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("buddyswitch/content/runs", combined)
        self.assertIn("run audits", combined)
        self.assertNotIn("legacy " + "artifact content", combined)
        self.assertNotIn("buddyswitch/content/" + "artifacts", combined)

    def test_active_cleanup_surfaces_use_data_cleanup_command(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
            ROOT / "framework" / "console" / "app.js",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

        self.assertIn("./buddyswitch-codex data cleanup --buddy", combined)
        self.assertIn("./buddyswitch-codex data cleanup --all-data", combined)
        self.assertNotIn("./buddyswitch-codex data cleanup --app-runtime", combined)
        self.assertNotIn("./buddyswitch-codex cleanup --agent", combined)
        self.assertNotIn("./buddyswitch-codex cleanup --all-agents", combined)
        self.assertNotIn("./buddyswitch-codex cleanup --project app", combined)
        self.assertNotIn("./buddyswitch-codex cleanup --all-storage", combined)
        self.assertNotIn("scripts/cleanup_buddyswitch.sh --agent", combined)
        self.assertNotIn("scripts/cleanup_buddyswitch.sh --all-agents", combined)
        self.assertNotIn("scripts/cleanup_buddyswitch.sh --project app", combined)
        self.assertNotIn("scripts/cleanup_buddyswitch.sh --all-storage", combined)

    def test_active_docs_remove_project_app_runtime_cleanup_surface(self) -> None:
        docs_roots = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs",
            ROOT / "tools" / "launcher" / "assets",
            ROOT / "buddyswitch" / "skills",
            ROOT / "framework" / "console" / "app.js",
        )
        scanned: list[Path] = []
        for target in docs_roots:
            if target.is_file():
                paths = [target]
            else:
                paths = [
                    path
                    for path in target.rglob("*")
                    if path.is_file() and path.suffix in {".md", ".toml", ".json", ".js"}
                ]
            for path in paths:
                scanned.append(path)
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(
                    "data cleanup --app-runtime",
                    text,
                    msg=f"legacy app-runtime cleanup surface should be removed from {path.relative_to(ROOT)}",
                )
                self.assertNotIn(
                    "projects/app/.runtime",
                    text,
                    msg=f"legacy project runtime path should be removed from {path.relative_to(ROOT)}",
                )
        self.assertTrue(scanned)

    def test_legacy_workspace_migration_and_cleanup_helpers_are_removed(self) -> None:
        targets = (
            ROOT / "tools" / "launcher" / "workspace.sh",
            ROOT / "tools" / "launcher" / "cleanup.sh",
            ROOT / "scripts" / "env_cleanup.py",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)
        self.assertNotIn("buddyswitch_workspace_migrate_legacy_state_if_needed", combined)
        self.assertNotIn("buddyswitch_cleanup_strip_legacy_runtime_excludes", combined)

    def test_active_docs_and_env_store_use_final_public_command_surface(self) -> None:
        targets = (
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
            ROOT / "scripts" / "env_store.py",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

        forbidden_patterns = (
            r"\./buddyswitch-codex start\b",
            r"\./buddyswitch-codex buddy\b",
            r"\./buddyswitch-codex cleanup\b",
            r"\./buddyswitch-codex reset\b",
            r"\./buddyswitch-codex browser\b",
            r"\./buddyswitch-codex workspace\b",
        )
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, combined), msg=f"legacy public command leaked: {pattern}")

        self.assertIn("./buddyswitch-codex instance start --buddy <buddy>", combined)
        self.assertIn("./buddyswitch-codex env browser ensure --instance <instance-id>", combined)
        self.assertIn("./buddyswitch-codex env browser status", combined)

    def test_active_launcher_helpers_use_final_reset_command_surface(self) -> None:
        text = (ROOT / "tools" / "launcher" / "workspace.sh").read_text(encoding="utf-8")

        self.assertNotIn("buddyswitch-codex reset --yes", text)

    def test_readme_documents_instance_lifecycle_cli(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("./buddyswitch-codex instance buddies", readme)
        self.assertIn("./buddyswitch-codex instance start --buddy <buddy>", readme)
        self.assertIn("./buddyswitch-codex instance list", readme)
        self.assertIn("./buddyswitch-codex instance open <instance-id>", readme)
        self.assertIn("./buddyswitch-codex instance delete <instance-id>", readme)
        self.assertNotIn("start --buddy <buddy>` reuses an existing instance", readme)
        self.assertNotIn("start --buddy <buddy>` reuses an existing valid buddy instance", readme)

    def test_launcher_help_surfaces_only_final_public_namespaces(self) -> None:
        launcher = (ROOT / "buddyswitch-codex").read_text(encoding="utf-8")
        self.assertIn("print_help() {", launcher)
        self.assertIn("start_codex()", launcher)
        help_block = launcher.split("print_help() {", 1)[1].split("start_codex()", 1)[0]

        self.assertIn("buddyswitch-codex instance buddies", help_block)
        self.assertIn("buddyswitch-codex instance start --buddy <buddy>", help_block)
        self.assertIn("buddyswitch-codex data cleanup --buddy <buddy>", help_block)
        self.assertIn("buddyswitch-codex env status", help_block)
        self.assertIn("buddyswitch-codex env reset [--yes]", help_block)
        self.assertIn("buddyswitch-codex help", help_block)
        self.assertIn("  instance", help_block)
        self.assertIn("  data", help_block)
        self.assertIn("  env", help_block)
        self.assertIn("  help", help_block)
        self.assertNotIn("buddyswitch-codex [codex args...]", help_block)
        self.assertNotIn("buddyswitch-codex start ", help_block)
        self.assertNotIn("buddyswitch-codex buddy ", help_block)
        self.assertNotIn("buddyswitch-codex cleanup ", help_block)
        self.assertNotIn("buddyswitch-codex reset ", help_block)
        self.assertNotIn("buddyswitch-codex browser ", help_block)
        self.assertNotIn("buddyswitch-codex workspace ", help_block)

    def test_launcher_main_dispatch_only_exposes_final_public_namespaces(self) -> None:
        launcher = (ROOT / "buddyswitch-codex").read_text(encoding="utf-8")
        main_match = re.search(r"(?ms)^main\(\) \{\n(.*?)^\}\n\nmain \"\$@\"\n?$", launcher)
        self.assertIsNotNone(main_match, msg="missing top-level main() dispatch block")
        assert main_match is not None
        main_block = main_match.group(1)

        self.assertIn("    instance)", main_block)
        self.assertIn("    data)", main_block)
        self.assertIn("    env)", main_block)
        self.assertIn("    help|-h|--help)", main_block)

        self.assertIn("    __locked-start-bootstrap)", main_block)
        self.assertIn("    __locked-workspace-sync)", main_block)
        self.assertIn("    __locked-reset)", main_block)
        self.assertIn("    __locked-browser-ensure)", main_block)
        self.assertIn("    __locked-instance-set-inactive)", main_block)
        self.assertIn("    __locked-instance-open-bootstrap)", main_block)
        self.assertIn("    __locked-instance-delete)", main_block)
        self.assertIn("    __locked-cleanup)", main_block)

        self.assertNotIn("    start)", main_block)
        self.assertNotIn("    buddy)", main_block)
        self.assertNotIn("    cleanup)", main_block)
        self.assertNotIn("    reset)", main_block)
        self.assertNotIn("    browser)", main_block)
        self.assertNotIn("    workspace)", main_block)
        self.assertNotIn('      start_codex "$@"', main_block)

    def test_main_checkout_does_not_track_legacy_runtime_placeholders(self) -> None:
        self.assertFalse((ROOT / "buddyswitch" / "content" / "artifacts" / ".gitkeep").exists())
        self.assertFalse((ROOT / "projects" / "app" / ".runtime" / ".gitkeep").exists())
        gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("!projects/app/.runtime/.gitkeep", gitignore_text)

    def test_main_checkout_does_not_keep_runtime_state_directories(self) -> None:
        runtime_dirs = (
            ROOT / "buddyswitch" / "content",
            ROOT / "buddyswitch" / "objects",
            ROOT / "runs" / "raw",
            ROOT / "projects" / "app" / ".runtime",
            ROOT / "buddyswitch" / "objects" / "tracks",
            ROOT / "buddyswitch" / "objects" / "tasks",
            ROOT / "buddyswitch" / "objects" / "artifacts",
            ROOT / "buddyswitch" / "content" / "runs",
            ROOT / "buddyswitch" / "content" / "artifacts",
        )
        for path in runtime_dirs:
            self.assertFalse(path.exists(), msg=f"main checkout should not retain runtime dir {path.relative_to(ROOT)}")

    def test_main_checkout_gitignore_does_not_silence_runtime_workspace_dirs(self) -> None:
        gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("projects/app/.runtime/**", gitignore_text)
        self.assertNotIn("artifacts/**", gitignore_text)
        self.assertNotIn("runs/summaries/**", gitignore_text)

    def test_runtime_storage_docs_point_to_launcher_workspace_without_gitkeep_language(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "artifacts-runs-git-policy.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()
        self.assertIn("launcher-owned execution workspace", combined)
        self.assertNotIn(".gitkeep", combined)

    def test_legacy_eval_assets_are_removed(self) -> None:
        self.assertFalse(
            (ROOT / "evals").exists(),
            msg="legacy evals must not remain in the active checkout; current behavior is covered by contracts and pytest",
        )

    def test_active_docs_do_not_reference_legacy_evals_as_verification_assets(self) -> None:
        active_targets = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs",
            ROOT / "framework" / "contracts",
            ROOT / "tools" / "launcher",
            ROOT / "scripts",
        )
        eval_root = "evals" + "/"
        forbidden_tokens = (
            eval_root,
            eval_root + "**",
            eval_root + "cases",
            eval_root + "rubrics",
        )

        checked_files: list[Path] = []
        for target in active_targets:
            if target.is_file():
                paths = [target]
            else:
                paths = [path for path in target.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
            for path in paths:
                try:
                    text = path.read_text(encoding="utf-8").lower()
                except UnicodeDecodeError:
                    continue
                checked_files.append(path)
                for token in forbidden_tokens:
                    self.assertNotIn(token, text, msg=f"legacy eval token {token!r} found in {path.relative_to(ROOT)}")

        self.assertTrue(checked_files, msg="expected active documentation/runtime files to be scanned")

    def test_residual_risk_memo_records_eval_cleanup_closure(self) -> None:
        memo_path = ROOT / "docs" / "memo" / "2026-05-03-final-review-residual-risks.md"
        text = memo_path.read_text(encoding="utf-8")
        lower = text.lower()
        eval_root = "evals" + "/"

        self.assertIn("## Risk 1: Switch-Era Evals Remain Outside The Scoped Residue Scan", text)
        self.assertIn("Status: Closed by follow-up cleanup.", text)
        self.assertIn(f"active `{eval_root}` tree was removed", lower)
        self.assertIn("must not be restored as compatibility fixtures", lower)
        self.assertIn("Status: Closed by independent rerun.", text)
        self.assertIn("Independent rerun result: 259 passed, 1 skipped.", text)

        stale_phrases = (
            "For active evals, replace switch-era setup",
            "Determine whether " + eval_root + " are active verification assets",
            "move them out of active searchable guidance",
        )
        for phrase in stale_phrases:
            self.assertNotIn(phrase.lower(), lower, msg=f"stale suggested action remains in residual-risk memo: {phrase}")

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

    def test_product_buddy_prompts_define_receipt_summary_contract(self) -> None:
        buddy_docs = (
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "design" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "dev" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "market" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "test" / "AGENTS.md",
        )
        for path in buddy_docs:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("## receipt contract", text)
            self.assertIn("## summary contract", text)
            self.assertIn("persisted: ok|failed", text)
            self.assertNotIn("receipt -> commands -> summary", text)

    def test_root_agents_describes_execution_worktree_without_full_runtime_contract(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()

        self.assertIn("execution worktree", text)
        self.assertIn("repo-root work focused on buddyswitch source", text)
        self.assertNotIn("inject `selected_skill_packet.skill_instructions` verbatim", text)

    def test_root_agents_define_preflight_and_reviewer_rubric(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()

        self.assertIn("preflight gate before analysis, planning, or implementation", text)
        self.assertIn("confirmed facts with file, code, log, or command evidence", text)
        self.assertIn("verification plan and stop condition", text)
        self.assertIn("reviewer rubric for substantial changes", text)
        self.assertIn("root cause or only symptoms", text)
        self.assertIn("do not rely on a separate template file", text)
        self.assertIn("do not rely on a separate rubric file", text)

    def test_runtime_agents_doc_uses_context_then_persist_flow(self) -> None:
        self.assertFalse(LEGACY_RUNTIME_AGENTS.exists())
        for path in ACTIVE_BUDDY_PROMPT_DOCS:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn(".agents/skills", text)
            self.assertIn("codex cli", text)
            self.assertIn("request_text", text)
            self.assertIn("scripts/turn_runtime.py persist", text)
            self.assertIn("## receipt contract", text)
            self.assertIn("## summary contract", text)
            self.assertNotIn("selected_skill_packet", text)
            self.assertNotIn("prepare-execution", text)
            self.assertNotIn("prepare_context.skills", text)
            self.assertNotIn("receipt.recommended_switch", text)
            self.assertNotIn("reference_switches", text)

    def test_readme_quick_start_distinguishes_development_and_launcher_modes(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8").lower()

        self.assertIn("development mode", text)
        self.assertIn("product mode", text)
        self.assertIn("./buddyswitch-codex instance start --buddy <buddy>", text)
        self.assertIn("${buddyswitch_shared_root}/instances/<instance-id>/workspace", text)
        self.assertIn("${buddyswitch_shared_root}/state", text)
        self.assertNotIn("product mode uses:\n\n- `${buddyswitch_shared_root}`", text)
        self.assertNotIn("${buddyswitch_shared_root}/workspace` for the execution worktree", text)

    def test_active_product_mode_docs_do_not_teach_singleton_workspace(self) -> None:
        active_docs = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        forbidden = (
            "${buddyswitch_shared_root}/workspace for the execution worktree",
            "~/.codex-buddyswitch/workspace",
            "launcher-managed execution worktree under `${buddyswitch_shared_root}/workspace`",
        )
        required = (
            "${buddyswitch_shared_root}/instances/<instance-id>/workspace",
            "${buddyswitch_shared_root}/state",
        )
        for path in active_docs:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    self.assertNotIn(token, text)
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        for token in required:
            self.assertIn(token, readme)

    def test_runtime_sources_do_not_construct_legacy_shared_root_lock_paths(self) -> None:
        combined_runtime_sources = "\n".join(path.read_text(encoding="utf-8") for path in RUNTIME_LOCK_GUARD_SOURCES)

        self.assertNotIn('Path(f"{shared_root}.lock")', combined_runtime_sources)
        self.assertNotIn('Path(f"{derived_shared_root}.lock")', combined_runtime_sources)
        self.assertNotIn("BUDDYSWITCH_RUNTIME_LOCK_PROOF", combined_runtime_sources)
        self.assertNotIn("BUDDYSWITCH_RUNTIME_LOCK_TOKEN", combined_runtime_sources)

    def test_tracked_docs_and_config_examples_do_not_hardcode_current_home_shared_root(self) -> None:
        current_home_shared_root = str(Path.home() / ".codex-buddyswitch")
        tracked_files = _tracked_repo_files(HOME_PATH_GUARD_PATHS)
        checked_files: list[Path] = []

        for path in tracked_files:
            if path.suffix not in HOME_PATH_GUARD_SUFFIXES:
                continue
            if not path.exists():
                continue
            checked_files.append(path)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                current_home_shared_root,
                text,
                msg=f"{path.relative_to(ROOT)} should not hard-code {current_home_shared_root}",
            )
            self.assertNotIn(
                'Path.home() / ".codex-buddyswitch"',
                text,
                msg=f"{path.relative_to(ROOT)} should not include a current-home shared root example",
            )

        self.assertTrue(checked_files, msg="expected tracked docs/config example files to be scanned")

    def test_switch_spec_documents_context_only_prepare_shape(self) -> None:
        text = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8")

        self.assertIn("track_artifact_index", text)
        self.assertIn("persist", text)
        self.assertIn("skill_id", text)
        self.assertNotIn("- `skills`", text)
        self.assertNotIn("inputs_by_skill", text)
        self.assertNotIn("run_instructions_by_skill", text)

    def test_switch_spec_describes_multi_skill_choice_without_selection_maps(self) -> None:
        text = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8")

        self.assertIn("request_text", text)
        self.assertIn("prepare_turn_context", text)
        self.assertIn("persist_skill_result", text)
        self.assertNotIn("`resolve_context.inputs` is the current selected input bundle", text)
        self.assertNotIn("top-level `artifact_selection` is `None` for multi-skill resolves", text)
        self.assertNotIn("top-level `run_instructions` remains available as neutral host guidance", text)

    def test_contracts_and_skills_define_summary_selection_semantics(self) -> None:
        contracts = (
            ROOT / "framework" / "contracts" / "market.md",
            ROOT / "framework" / "contracts" / "pm.md",
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

    def test_manifest_skill_paths_are_declared_for_runtime_materialization(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        for skill in manifest.get("skills", []):
            if not isinstance(skill, dict):
                continue
            with self.subTest(skill=skill.get("id")):
                path = skill.get("path")
                self.assertIsInstance(path, str)
                assert isinstance(path, str)
                self.assertTrue(path.strip())

    def test_manifest_persistence_fields_exist_for_all_skills(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        for skill in manifest.get("skills", []):
            if not isinstance(skill, dict):
                continue
            with self.subTest(skill=skill.get("id")):
                persistence = skill.get("persistence")
                self.assertIsInstance(persistence, dict)
                assert isinstance(persistence, dict)
                self.assertIn("produces_artifact", persistence)
                self.assertIn("output_schema", persistence)
                self.assertIn("output_slot", persistence)
                schema_path = ROOT / persistence["output_schema"]
                self.assertTrue(schema_path.exists(), msg=f"missing schema: {schema_path.relative_to(ROOT)}")
                with schema_path.open("r", encoding="utf-8") as handle:
                    self.assertIsInstance(json.load(handle), dict)

    def test_pm_write_prd_manifest_persistence_uses_expected_output_slot(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}
        self.assertEqual(skills["write-prd"]["persistence"]["output_slot"], "prd")
        self.assertEqual(skills["track-manager"]["persistence"]["output_slot"], "track-operation")

    def test_artifact_skill_output_slots_remain_product_specific(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}
        for skill_id, expected_slot in ARTIFACT_SKILL_TO_OUTPUT_SLOT.items():
            with self.subTest(skill=skill_id):
                self.assertEqual(skills[skill_id]["persistence"]["output_slot"], expected_slot)

    def test_buddy_level_result_schemas_exist_for_all_artifact_buddies(self) -> None:
        for buddy_id, schema_path in BUDDY_RESULT_SCHEMA_PATHS.items():
            with self.subTest(buddy=buddy_id):
                self.assertTrue(schema_path.exists(), msg=f"missing buddy-level schema: {schema_path.relative_to(ROOT)}")
                loaded = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertIsInstance(loaded, dict)

    def test_artifact_skill_manifest_entries_use_buddy_level_result_schemas(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}

        for skill_id, expected_schema in ARTIFACT_SKILL_TO_BUDDY_RESULT_SCHEMA.items():
            with self.subTest(skill=skill_id):
                persistence = skills[skill_id]["persistence"]
                self.assertTrue(persistence["produces_artifact"])
                self.assertEqual(persistence["output_schema"], expected_schema)

    def test_track_manager_is_artifact_skill_without_runtime_special_case(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}
        track_manager = skills["track-manager"]["persistence"]
        self.assertTrue(track_manager["produces_artifact"])
        self.assertEqual(track_manager["output_slot"], "track-operation")
        self.assertEqual(track_manager["output_schema"], "framework/schemas/pm/pm-result.json")
        self.assertFalse((ROOT / "framework" / "schemas" / "pm" / "track-manager.json").exists())

        runtime_text = (ROOT / "scripts" / "turn_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("_persist_track_manager(", runtime_text)
        self.assertNotIn('selected_skill_id == "track-manager"', runtime_text)

    def test_legacy_artifact_skill_specific_schemas_are_not_active_in_manifest(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        for skill in manifest.get("skills", []):
            if not isinstance(skill, dict):
                continue
            persistence = skill.get("persistence")
            if not isinstance(persistence, dict):
                continue
            output_schema = persistence.get("output_schema")
            if not isinstance(output_schema, str):
                continue
            self.assertNotIn(
                output_schema,
                LEGACY_ARTIFACT_SCHEMA_PATHS,
                msg=f"skill '{skill.get('id')}' still references legacy schema '{output_schema}'",
            )

    def test_market_schemas_share_canonical_evidence_and_traceability_fields(self) -> None:
        for path in MARKET_SCHEMA_PATHS:
            with self.subTest(schema=str(path.relative_to(ROOT))):
                schema = json.loads(path.read_text(encoding="utf-8"))
                artifact_content = schema["properties"]["artifact_content"]
                required = set(artifact_content["required"])
                self.assertIn("research_question", required)
                self.assertIn("evidence", required)
                self.assertIn("insights", required)
                self.assertIn("assumptions", required)
                self.assertIn("risks", required)
                self.assertIn("conclusion", required)
                self.assertIn("recommended_next_step", required)
                self.assertIn("specialized_sections", required)
                self.assertNotIn("source_traceability", required)

    def test_market_skill_membership_and_persistence_contracts_are_manifest_driven(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        buddies = {buddy["id"]: buddy for buddy in manifest.get("buddies", []) if isinstance(buddy, dict)}
        skills = {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}
        market_skill_ids = buddies["market"]["skills"]
        self.assertGreaterEqual(len(market_skill_ids), 6)
        for skill_id in market_skill_ids:
            with self.subTest(skill=skill_id):
                persistence = skills[skill_id]["persistence"]
                self.assertTrue(persistence["produces_artifact"])
                self.assertIsInstance(persistence["output_slot"], str)
                self.assertTrue((ROOT / persistence["output_schema"]).exists())

    def test_market_skill_docs_reference_shared_cockpit_doc(self) -> None:
        for path in ARTIFACT_SKILL_DOCS[:6]:
            with self.subTest(skill_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("framework/docs/browser-cockpit.md", text)
                self.assertIn("headed", text)
                self.assertIn("mandatory takeover", text)
                self.assertIn("instance-browser", text)

    def test_market_skill_docs_start_with_execution_order(self) -> None:
        for path in ARTIFACT_SKILL_DOCS[:6]:
            with self.subTest(skill_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("## execution order", text)
                self.assertIn("before any market research", text)
                self.assertIn("pause for mandatory takeover", text)
                self.assertIn("do not continue with snippet-only or text-only research", text)

    def test_market_active_contract_docs_require_browser_native_wording(self) -> None:
        required_tokens = ("chrome-devtools-cockpit", "browser-native")
        forbidden_tokens = ("search-assist", "shared-browser", "shared-cockpit")

        for path in ACTIVE_MARKET_CONTRACT_DOCS:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in required_tokens:
                    self.assertIn(token, text, msg=f"{path.relative_to(ROOT)} missing required token '{token}'")
                for token in forbidden_tokens:
                    self.assertNotIn(token, text, msg=f"{path.relative_to(ROOT)} must not include '{token}'")

    def test_market_browser_contract_docs_require_instance_cockpit_tokens(self) -> None:
        for path in (
            ROOT / "framework" / "contracts" / "market.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
        ):
            with self.subTest(active_browser_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("instance-browser", text)
                self.assertIn("instance-cockpit", text)

    def test_browser_cockpit_docs_define_mcp_auto_approval_without_parallel_calls(self) -> None:
        text = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8").lower()
        self.assertIn("all enabled mcp servers", text)
        self.assertIn('default_tools_approval_mode = "approve"', text)
        self.assertIn("do not set `supports_parallel_tool_calls = true`", text)

    def test_market_schemas_share_market_cockpit_evidence_fields(self) -> None:
        for path in MARKET_SCHEMA_PATHS:
            with self.subTest(schema=str(path.relative_to(ROOT))):
                schema = json.loads(path.read_text(encoding="utf-8"))
                artifact_content = schema["properties"]["artifact_content"]
                evidence = artifact_content["properties"]["evidence"]
                self.assertEqual(evidence["type"], "array")
                self.assertEqual(evidence["items"]["type"], "string")
                specialized_sections = artifact_content["properties"]["specialized_sections"]
                self.assertEqual(specialized_sections["type"], "object")

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
        for common_field in (
            "research_question",
            "evidence",
            "insights",
            "assumptions",
            "risks",
            "conclusion",
            "recommended_next_step",
            "specialized_sections",
        ):
            self.assertIn(common_field, output_section)
        top_level_lines = [line.strip() for line in output_section.splitlines() if re.match(r"^\\d+\\.\\s+`", line.strip())]
        for non_common_field in ("source_traceability", "research_strategy", "channel_plan", "iteration_log"):
            self.assertTrue(
                all(f"`{non_common_field}`" not in line for line in top_level_lines),
                msg=f"{non_common_field} must stay in specialized_sections, not top-level required fields",
            )

    def test_market_contract_describes_specialized_sections_extension(self) -> None:
        contract_path = ROOT / "framework" / "contracts" / "market.md"
        evidence_section = _markdown_section(
            contract_path.read_text(encoding="utf-8"),
            "Required Output Structure",
        )
        self.assertIn("specialized_sections", evidence_section)
        self.assertIn("object", evidence_section.lower())

    def test_market_contract_describes_instance_bound_cockpit_without_implying_multi_skill_runs(self) -> None:
        contract_text = (ROOT / "framework" / "contracts" / "market.md").read_text(encoding="utf-8").lower()
        self.assertIn("run the selected market skill in the instance-bound headed cockpit", contract_text)
        self.assertIn("active buddy instance", contract_text)
        self.assertNotIn("run all six market skills", contract_text)

    def test_active_browser_docs_do_not_use_legacy_shared_cockpit_terms(self) -> None:
        active_docs = (
            ROOT / "framework" / "contracts" / "market.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
        )
        forbidden = (
            "shared headed cockpit",
            "shared browser cockpit",
            "shared browser endpoint",
            "shared browser profile",
            "shared-browser",
            "shared-cockpit",
        )
        for path in active_docs:
            with self.subTest(active_doc=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    self.assertNotIn(token, text)
                self.assertIn("instance-browser", text)
                self.assertIn("instance-cockpit", text)

    def test_market_contract_chat_return_blocks_match_schema_surface(self) -> None:
        chat_return_section = _markdown_section(
            (ROOT / "framework" / "contracts" / "market.md").read_text(encoding="utf-8"),
            "Chat Return Blocks",
        ).lower()
        self.assertNotIn("suggested next switch", chat_return_section)

    def test_market_cockpit_doc_defines_native_skill_boundary(self) -> None:
        cockpit_doc = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn(".agents/skills", cockpit_doc)
        self.assertIn("codex", cockpit_doc)
        self.assertIn("native", cockpit_doc)
        self.assertIn("prepare", cockpit_doc)
        self.assertNotIn("selected_skill_packet", cockpit_doc)
        self.assertNotIn("prepare-execution", cockpit_doc)
        self.assertNotIn("prepare_context.skills", cockpit_doc)

    def test_switch_spec_documents_prepare_context_loop(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("framework/contracts/prepare-turn-context.json", switch_spec)
        self.assertIn("persist-skill-result", switch_spec)
        self.assertIn("refreshed_context", switch_spec)
        self.assertIn("reserves one run envelope", switch_spec)
        self.assertNotIn("prepare-execution", switch_spec)
        self.assertNotIn("selected_skill_packet", switch_spec)

    def test_switch_spec_defers_skill_execution_to_codex_native_discovery(self) -> None:
        cockpit_doc = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8").lower()
        self.assertIn(".agents/skills", cockpit_doc)
        self.assertIn("browser-native", cockpit_doc)
        self.assertNotIn("prepare_context.skills", cockpit_doc)
        self.assertNotIn("selected_skill_packet.execution_steps", cockpit_doc)

    def test_top_level_docs_define_prepare_and_persist_flow_without_custom_skill_packet(self) -> None:
        self.assertFalse(LEGACY_ROUTER_PROMPT.exists())
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "AGENTS.md",
                ROOT / "README.md",
                ROOT / "framework" / "docs" / "turn-runtime-spec.md",
                *ACTIVE_BUDDY_PROMPT_DOCS,
            )
        ).lower()

        self.assertIn(".agents/skills", combined)
        self.assertIn("prepare", combined)
        self.assertIn("persist-skill-result", combined)
        self.assertIn("refreshed_context", combined)
        self.assertIn("buddyswitch does not open browser tools itself", (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8").lower())
        self.assertNotIn("prepare-execution", combined)
        self.assertNotIn("selected_skill_packet", combined)
        self.assertNotIn("prepare_context.skills", combined)

    def test_runtime_docs_state_resolve_and_persist_require_runtime_workspace(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("${buddyswitch_shared_root}/instances/<instance-id>/workspace", readme)
        self.assertIn("${buddyswitch_shared_root}/state", readme)
        self.assertIn("scripts/turn_runtime.py", switch_spec)
        self.assertIn("buddyswitch/content/runs/*.json", switch_spec)

    def test_product_mode_docs_define_shared_project_workspace(self) -> None:
        docs = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            *ACTIVE_BUDDY_PROMPT_DOCS,
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in docs).lower()

        self.assertIn("projects/app", combined)
        self.assertIn("shared product source", combined)
        self.assertIn("runtime workspace", combined)
        self.assertNotIn("${buddyswitch_shared_root}/project/workspace/projects/app", combined)

    def test_host_docs_remove_custom_prepare_inputs_by_skill_bundle(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        buddy_prompts = "\n".join(path.read_text(encoding="utf-8").lower() for path in ACTIVE_BUDDY_PROMPT_DOCS)
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("request_text", readme)
        self.assertIn("prepare-turn-context", readme)
        self.assertNotIn("inputs_by_skill", switch_spec)
        self.assertNotIn("prepare_context.skills", switch_spec)
        self.assertNotIn("resolve_context.inputs[", buddy_prompts)

    def test_docs_place_persist_follow_up_fields_inside_receipt(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("receipt.next_state", readme)
        self.assertIn("receipt.next_state", switch_spec)
        self.assertNotIn("receipt.recommended_switch", switch_spec)

    def test_active_host_prompts_require_refresh_context_check_and_retry(self) -> None:
        self.assertFalse(LEGACY_RUNTIME_AGENTS.exists())
        self.assertFalse(LEGACY_ROUTER_PROMPT.exists())
        targets = ACTIVE_BUDDY_PROMPT_DOCS
        legacy_unconditional_runtime = (
            "continue from `refreshed_context` when another buddy turn is needed after a successful persist."
        )
        legacy_unconditional_router = (
            "continue from `refreshed_context` after a successful persist when the task needs another turn."
        )

        for path in targets:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("if another turn is needed", text, msg=f"missing post-persist turn guidance in {path.relative_to(ROOT)}")
            self.assertIn("prepare", text, msg=f"missing prepare retry guidance in {path.relative_to(ROOT)}")
            self.assertIn("request_text", text, msg=f"missing request_text retry guidance in {path.relative_to(ROOT)}")
            self.assertNotIn("receipt.recommended_switch", text, msg=f"legacy follow-up field in {path.relative_to(ROOT)}")
            self.assertNotIn(
                legacy_unconditional_runtime,
                text,
                msg=f"legacy unconditional refreshed_context instruction must be removed in {path.relative_to(ROOT)}",
            )
            self.assertNotIn(
                legacy_unconditional_router,
                text,
                msg=f"legacy unconditional refreshed_context instruction must be removed in {path.relative_to(ROOT)}",
            )

    def test_docs_define_persist_as_end_of_turn_explicit_resolve_boundary(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("successful `persist` does not reserve a follow-up run", readme)
        self.assertIn("receipt.next_state", readme)
        self.assertIn("if another turn is needed", readme)
        self.assertIn("`prepare`", readme)
        self.assertIn("request_text", readme)
        self.assertNotIn("receipt.recommended_switch", readme)
        self.assertNotIn("continue from `refreshed_context`", readme)

        self.assertIn("does not auto-reserve a follow-up run", switch_spec)
        self.assertIn("receipt.next_state", switch_spec)
        self.assertNotIn("receipt.recommended_switch", switch_spec)
        self.assertNotIn("`refreshed_context` normally carries the next-turn resolve handoff", switch_spec)
        self.assertNotIn("continue from `refreshed_context` when it is true", switch_spec)

    def test_active_host_prompts_require_explicit_resolve_after_persist(self) -> None:
        self.assertFalse(LEGACY_RUNTIME_AGENTS.exists())
        self.assertFalse(LEGACY_ROUTER_PROMPT.exists())
        targets = ACTIVE_BUDDY_PROMPT_DOCS

        for path in targets:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("if another turn is needed", text)
            self.assertIn("request_text", text)
            self.assertIn("prepare", text)
            self.assertNotIn("receipt.recommended_switch", text)
            self.assertIn("if another turn is needed", text)
            self.assertNotIn("continue from `refreshed_context`", text)
            self.assertNotIn(
                "`refreshed_context` is the canonical follow-up handoff after a successful persist",
                text,
            )

    def _assert_buddy_prompt_base_contract(self, buddy_id: str, path: Path) -> tuple[str, str]:
        self.assertTrue(path.exists(), msg=f"missing buddy prompt asset: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertTrue(text.startswith("# BuddySwitch Runtime Workspace\n"))
        self.assertIn(f"locked to the `{buddy_id}` buddy", lower)
        self.assertIn("scripts/turn_runtime.py prepare", text)
        self.assertIn("scripts/turn_runtime.py persist", text)
        self.assertIn("buddy-level result json", lower)
        self.assertIn("emit", lower)
        self.assertIn("directly", lower)
        self.assertNotIn("scripts/result_bridge.py", text)
        self.assertIn(f"ordinary user requests belong to `{buddy_id}`", lower)
        return text, lower

    def test_buddy_prompt_assets_exist_for_every_manifest_buddy(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        buddies = manifest.get("buddies", [])
        self.assertTrue(buddies)
        for buddy in buddies:
            buddy_id = buddy["id"]
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy_id / "AGENTS.md"
            with self.subTest(buddy=buddy_id):
                _, lower = self._assert_buddy_prompt_base_contract(buddy_id, path)
                self.assertIn(".agents/skills", lower)
                self.assertIn("codex cli", lower)
                self.assertIn("native skill", lower)
                self.assertIn("buddy-level result json", lower)
                self.assertIn("emit buddy-level result json directly", lower)
                self.assertIn("runs/raw/", lower)
                self.assertIn("projects/app", lower)
                self.assertIn("## receipt contract", lower)
                self.assertIn("persisted: ok|failed", lower)
                self.assertIn("task: <task_title> [<task_id>]", lower)
                self.assertIn("artifact: <artifact_id|none>", lower)
                self.assertIn("run: <run_id>", lower)
                self.assertIn("related runs: <run_id_1>, <run_id_2>", lower)
                self.assertIn("## summary contract", lower)

    def test_buddy_prompts_do_not_allow_user_facing_switch_commands(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        buddies = manifest.get("buddies", [])
        self.assertTrue(buddies)
        for buddy in buddies:
            buddy_id = buddy["id"]
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy_id / "AGENTS.md"
            with self.subTest(buddy=buddy_id):
                _, lower = self._assert_buddy_prompt_base_contract(buddy_id, path)
                self.assertNotIn("same-buddy canonical", lower)
                self.assertNotIn(f"switch {buddy_id}", lower)
                self.assertNotIn("receipt -> commands -> summary", lower)
                required_runtime_tokens = (
                    ".agents/skills",
                    "codex cli",
                    "native skill",
                    "skill_id",
                    "emit buddy-level result json directly",
                    "runs/raw/",
                    "projects/app",
                    "## receipt contract",
                    "## summary contract",
                )
                for token in required_runtime_tokens:
                    self.assertIn(token, lower)
                self.assertNotIn("choose exactly one skill_id from prepare_context.skills", lower)
                self.assertNotIn("read and execute the selected buddyswitch skill.md", lower)
                self.assertNotIn("instruction_path", lower)
                self.assertNotIn("projects/app/.runtime/", lower)
                self.assertNotIn("result_bridge.py", lower)

    def test_runtime_prompt_does_not_present_switch_as_product_ui(self) -> None:
        self.assertFalse(LEGACY_RUNTIME_AGENTS.exists())
        combined_prompts = "\n".join(path.read_text(encoding="utf-8").lower() for path in ACTIVE_BUDDY_PROMPT_DOCS)
        self.assertIn("ordinary user requests", combined_prompts)
        self.assertNotIn("switch <buddy>", combined_prompts)
        self.assertNotIn("switch pm:", combined_prompts)

    def test_product_docs_do_not_teach_switch_as_buddy_instance_input(self) -> None:
        docs = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
        )
        forbidden_tokens = ("switch pm:", "switch dev:", "switch market:", "switch test:", "switch design:")
        for path in docs:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(product_doc=str(path.relative_to(ROOT))):
                for token in forbidden_tokens:
                    self.assertNotIn(token, text)

    def test_active_product_paths_do_not_contain_legacy_switch_wire(self) -> None:
        allowed_files = {
            ROOT / "tests" / "test_repo_consistency.py",
        }
        forbidden_patterns = (
            r"\bswitch\s+<buddy>",
            r"\bswitch\s+[a-z][a-z0-9-]*\s*:",
            r"_parse_wire_switch",
            r"_STRUCTURAL_SWITCH_PATTERN",
            r"WIRE_SYNTAX",
            r"switch-grammar",
            r"parse_switch\.py",
            r"codex_router\.py",
            r"resolved\.get\(\"switch\"\)",
            r"payload\.get\(\"switch\"\)",
            r"\bswitch_payload\b",
            r"resolved\.switch",
        )

        checked_files: list[Path] = []
        for target in ACTIVE_PRODUCT_PATHS:
            if target.is_file():
                candidates = [target]
            else:
                candidates = [path for path in target.rglob("*") if path.is_file()]

            for path in candidates:
                if path in allowed_files or "__pycache__" in path.parts:
                    continue
                checked_files.append(path)
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                for pattern in forbidden_patterns:
                    if re.search(pattern, text, flags=re.IGNORECASE):
                        self.fail(f"{path.relative_to(ROOT)} matched forbidden pattern {pattern!r}")

        self.assertTrue(checked_files)

    def test_switch_spec_is_marked_internal_debug_wire_contract(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("users submit ordinary request text", switch_spec)
        self.assertNotIn("switch <buddy>", switch_spec)

    def test_product_output_docs_do_not_reintroduce_command_section_or_copyable_switch_guidance(self) -> None:
        product_output_docs = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "interface-spec.md",
            *sorted((ROOT / "framework" / "contracts").glob("*.md")),
        )
        forbidden_tokens = (
            "receipt -> commands -> summary",
            "suggested next switch",
            "one `template`",
            "one `recommended`",
            "copyable switch",
        )
        for path in product_output_docs:
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(product_output_doc=str(path.relative_to(ROOT))):
                for token in forbidden_tokens:
                    self.assertNotIn(token, text)

        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("receipt.next_state", readme)
        self.assertIn("receipt.next_state", switch_spec)

        # Legacy switch-command follow-up fields must stay retired from output docs.
        self.assertNotIn("receipt.reference_switches", switch_spec)
        self.assertNotIn("receipt.recommended_switch", switch_spec)
        self.assertNotIn("commands order", switch_spec)

    def test_runtime_host_prompt_defines_codex_native_skill_loop(self) -> None:
        self.assertFalse(LEGACY_RUNTIME_AGENTS.exists())
        text = "\n".join(path.read_text(encoding="utf-8").lower() for path in ACTIVE_BUDDY_PROMPT_DOCS)

        required_semantics = (
            ".agents/skills",
            "codex cli",
            "native skill",
            "emit buddy-level result json directly",
            "buddy-level result json",
            "persist",
            "skill_id",
        )
        for token in required_semantics:
            self.assertIn(token, text, msg=f"missing runtime semantic: {token}")
        self.assertNotIn("scripts/result_bridge.py", text)
        self.assertNotIn("choose exactly one skill_id from prepare_context.skills", text)
        self.assertNotIn("read and execute the selected buddyswitch skill.md", text)
        self.assertNotIn("instruction_path", text)
        self.assertNotIn("run_instructions_by_skill", text)

    def test_bridge_module_and_bridge_only_tests_are_removed_from_active_runtime_surface(self) -> None:
        self.assertFalse((ROOT / "scripts" / "result_bridge.py").exists())
        self.assertFalse((ROOT / "tests" / "test_result_bridge.py").exists())

        active_targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs",
            ROOT / "framework" / "contracts",
            ROOT / "tools" / "launcher" / "assets",
            ROOT / "buddyswitch" / "skills",
            ROOT / "scripts",
        )
        for target in active_targets:
            if target.is_file():
                paths = [target]
            else:
                paths = [path for path in target.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
            for path in paths:
                try:
                    text = path.read_text(encoding="utf-8").lower()
                except UnicodeDecodeError:
                    continue
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotIn("scripts/result_bridge.py", text)
                    self.assertNotIn("result_bridge.py", text)
                    self.assertNotIn("bridge it with", text)
                    self.assertNotIn("native output ->", text)

    def test_browser_cockpit_doc_references_native_runtime_skill_materialization(self) -> None:
        self.assertFalse(LEGACY_ROUTER_PROMPT.exists())
        text = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8").lower()

        self.assertIn(".agents/skills", text)
        self.assertIn("chrome-devtools-cockpit", text)
        self.assertIn("browser-native", text)
        self.assertIn("mandatory takeover", text)
        self.assertNotIn("prepare_context.skills", text)
        self.assertNotIn("selected_skill_packet", text)

    def test_router_doc_lists_task_objects_as_canonical_state(self) -> None:
        self.assertFalse(LEGACY_ROUTER_PROMPT.exists())
        text = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8").lower()
        self.assertIn("buddyswitch/objects/tasks/*.json", text)

    def test_switch_spec_lists_current_runtime_errors(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8")
        self.assertIn("`prepare` returns `ok=false` on validation errors", switch_spec)
        self.assertIn("`persist` validates and commits exactly one selected skill output", switch_spec)
        self.assertNotIn("E_RUNTIME_PREPARE_EXECUTION", switch_spec)

    def test_artifact_skill_templates_emit_full_buddy_level_result_envelope(self) -> None:
        for path, schema_path in ARTIFACT_TEMPLATE_SCHEMAS.items():
            with self.subTest(template=str(path.relative_to(ROOT))):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)

                for key in COMMON_RESULT_ENVELOPE_KEYS:
                    self.assertIn(key, payload, msg=f"missing envelope key '{key}' in {path.relative_to(ROOT)}")

                artifact_content = payload["artifact_content"]
                self.assertIsInstance(artifact_content, dict)

                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                schema_artifact_content = schema["properties"]["artifact_content"]
                required_fields = schema_artifact_content["required"]
                for field_name in required_fields:
                    self.assertIn(
                        field_name,
                        artifact_content,
                        msg=f"missing artifact_content field '{field_name}' in {path.relative_to(ROOT)}",
                    )

                if path in MARKET_TEMPLATE_SPECIALIZED_KEYS:
                    specialized_sections = artifact_content.get("specialized_sections")
                    self.assertIsInstance(specialized_sections, dict)
                    expected_key = MARKET_TEMPLATE_SPECIALIZED_KEYS[path]
                    self.assertIn(
                        expected_key,
                        specialized_sections,
                        msg=f"missing specialized section '{expected_key}' in {path.relative_to(ROOT)}",
                    )

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
            ROOT / "buddyswitch" / "skills" / "pm" / "track-manager" / "assets" / "track-operation-template.md",
            ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "assets" / "design-handoff-template.md",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
        )
        for path in expected_assets:
            with self.subTest(asset=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), msg=f"missing template asset: {path.relative_to(ROOT)}")

    def test_shape_prototype_package_files_exist(self) -> None:
        self.assertTrue((ROOT / "framework" / "schemas" / "design" / "design-result.json").exists())
        self.assertTrue((ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "SKILL.md").exists())

    def test_active_docs_use_slot_revision_and_package_contract_language(self) -> None:
        targets = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
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

    def test_parallel_contract_files_exist_and_define_expected_ids(self) -> None:
        expected_contract_ids = {
            "prepare-turn-context": PARALLEL_CONTRACT_FILES[0],
            "persist-skill-result": PARALLEL_CONTRACT_FILES[1],
            "workspace-projection": PARALLEL_CONTRACT_FILES[2],
        }
        loaded_contracts: dict[str, dict[str, object]] = {}
        for contract_id, path in expected_contract_ids.items():
            with self.subTest(contract=contract_id):
                self.assertTrue(path.exists(), msg=f"missing contract file {path.relative_to(ROOT)}")
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload.get("contract_id"), contract_id)
                self.assertIn("contract_version", payload)
                loaded_contracts[contract_id] = payload
        for path in LEGACY_REMOVED_CONTRACT_FILES:
            with self.subTest(removed_contract=str(path.relative_to(ROOT))):
                self.assertFalse(path.exists(), msg=f"legacy contract must stay removed: {path.relative_to(ROOT)}")

        prepare_context = loaded_contracts["prepare-turn-context"]
        self.assertIn("response_key_order", prepare_context)
        self.assertIn("context_revision", prepare_context["response_key_order"])
        self.assertIn("track_artifact_index", prepare_context["response_key_order"])
        self.assertNotIn("skills", prepare_context["response_key_order"])

        persist_skill_result = loaded_contracts["persist-skill-result"]
        self.assertIn("response_key_order", persist_skill_result)
        self.assertEqual(
            persist_skill_result["response_key_order"],
            ["ok", "receipt", "refreshed_context"],
        )

        workspace_projection = loaded_contracts["workspace-projection"]
        self.assertIn("top_level_key_order", workspace_projection)
        self.assertIn("view_shapes", workspace_projection)
        self.assertIn("derived_invariants", workspace_projection)
        self.assertIn("buddy", workspace_projection["view_shapes"])
        self.assertIn("artifact", workspace_projection["view_shapes"])
        self.assertIn("task", workspace_projection["view_shapes"])
        self.assertIn("track", workspace_projection["view_shapes"])
        self.assertIn("run_audit", workspace_projection["view_shapes"])
        self.assertIn("key_order", workspace_projection["view_shapes"]["buddy"])
        self.assertIn("key_order", workspace_projection["view_shapes"]["artifact"])
        self.assertIn("key_order", workspace_projection["view_shapes"]["task"])
        self.assertIn("key_order", workspace_projection["view_shapes"]["track"])
        self.assertIn("key_order", workspace_projection["view_shapes"]["run_audit"])
        self.assertIn("task_view_slot_field", workspace_projection["derived_invariants"])
        self.assertIn("track_view_missing_reference_field", workspace_projection["derived_invariants"])

    def test_switch_and_interface_specs_reference_parallel_contract_files(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8")
        interface_spec = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")

        self.assertNotIn("framework/contracts/switch-grammar.json", switch_spec)
        self.assertIn("framework/contracts/prepare-turn-context.json", switch_spec)
        self.assertIn("framework/contracts/persist-skill-result.json", switch_spec)
        self.assertIn("framework/contracts/workspace-projection.json", interface_spec)

    def test_ui_surface_scripts_do_not_reference_runtime_internal_modules(self) -> None:
        js_files = sorted(path for root in UI_SURFACE_ROOTS for path in root.rglob("*.js"))
        self.assertTrue(js_files, msg="expected at least one UI browser script")

        for path in js_files:
            with self.subTest(surface=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), msg=f"missing ui surface {path.relative_to(ROOT)}")
                text = path.read_text(encoding="utf-8")
                for token in UI_RUNTIME_INTERNAL_TOKENS:
                    self.assertNotIn(token, text, msg=f"{path.relative_to(ROOT)} should not reference {token}")
                for token in UI_RUNTIME_PATH_TOKENS:
                    self.assertNotIn(token, text, msg=f"{path.relative_to(ROOT)} should not reference {token}")

        console_text = (ROOT / "framework" / "console" / "app.js").read_text(encoding="utf-8")
        api_tokens = sorted(set(re.findall(r"/api/[A-Za-z0-9_/-]+", console_text)))
        self.assertEqual([CONSOLE_RUNTIME_ENDPOINT], api_tokens)

    def test_interface_spec_locks_ui_surface_boundary_to_api_workspace(self) -> None:
        text = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")

        self.assertIn("framework/console/app.js", text)
        self.assertIn("projects/app/main.js", text)
        self.assertIn(CONSOLE_RUNTIME_ENDPOINT, text)
        self.assertIn("must not reference runtime internals", text.lower())
        self.assertIn("env_store", text)
        self.assertIn("runtime_store.repositories", text)
        self.assertIn("runtime_store.projections", text)
        self.assertIn("turn_runtime", text)
        self.assertIn("workspace_data", text)
        self.assertIn("runtime object reads", text.lower())
        self.assertIn("runtime write paths", text.lower())

    def test_console_does_not_expect_track_object_path_before_contract_adds_it(self) -> None:
        workspace_projection = json.loads(
            (ROOT / "framework" / "contracts" / "workspace-projection.json").read_text(encoding="utf-8")
        )
        track_shape = workspace_projection["view_shapes"]["track"]
        track_fields = track_shape["key_order"]
        console_text = (ROOT / "framework" / "console" / "app.js").read_text(encoding="utf-8")

        if "object_path" not in track_fields:
            self.assertNotIn("track.object_path", console_text)


if __name__ == "__main__":
    unittest.main()
