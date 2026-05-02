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
    ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "SKILL.md",
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
    ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "skill.toml",
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
MARKET_EVIDENCE_FIELDS = (
    "source_id",
    "url",
    "source_type",
    "accessed_at",
    "claim_excerpt",
    "page_title",
    "auth_state",
    "query_or_filter_used",
)
OPTIONAL_MARKET_EVIDENCE_FIELDS = (
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
    ROOT / "framework" / "docs" / "browser-cockpit.md",
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
PARALLEL_CONTRACT_FILES = (
    ROOT / "framework" / "contracts" / "switch-grammar.json",
    ROOT / "framework" / "contracts" / "resolve-context.json",
    ROOT / "framework" / "contracts" / "persist-skill-result.json",
    ROOT / "framework" / "contracts" / "workspace-projection.json",
)
UI_SURFACE_ROOTS = (
    ROOT / "framework" / "console",
    ROOT / "projects" / "app",
)
UI_RUNTIME_INTERNAL_TOKENS = (
    "env_store",
    "runtime_store.repositories",
    "runtime_store.projections",
    "switch_runtime",
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
    ROOT / "scripts" / "switch_runtime.py",
    ROOT / "scripts" / "runtime_store" / "projections.py",
    ROOT / "tests" / "test_cleanup_system.py",
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
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()

        self.assertIn("buddyswitch/content/runs", combined)
        self.assertIn("run content", combined)
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
            ROOT / "framework" / "docs" / "switch-spec.md",
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
        self.assertIn("creates a fresh buddy-locked instance", readme)
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
            ROOT / "evals" / "cases" / "07-cleanup-storage-script.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in targets).lower()
        self.assertIn("launcher runtime workspace", combined)
        self.assertNotIn(".gitkeep", combined)

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
            self.assertIn("receipt -> summary", text)
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
        text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("prepare-turn-context", text)
        self.assertIn("request_text", text)
        self.assertIn("persist-skill-result", text)
        self.assertIn("receipt -> summary", text)
        self.assertNotIn("selected_skill_packet", text)
        self.assertNotIn("prepare-execution", text)
        self.assertNotIn("receipt.recommended_switch", text)
        self.assertNotIn("reference_switches", text)

    def test_readme_quick_start_distinguishes_development_and_launcher_modes(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8").lower()

        self.assertIn("two modes exist", text)
        self.assertIn("develop buddyswitch", text)
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
            ROOT / "framework" / "docs" / "switch-spec.md",
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

    def test_switch_spec_keeps_multi_skill_choice_on_resolve_context_skills(self) -> None:
        text = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")

        self.assertIn("the host must choose one `skill_id` from `resolve_context.skills`", text)
        self.assertIn("inputs_by_skill", text)
        self.assertNotIn("artifact_selection_by_skill[chosen_skill_id]", text)
        self.assertNotIn("run_instructions_by_skill[chosen_skill_id]", text)

    def test_switch_spec_describes_multi_skill_choice_without_selection_maps(self) -> None:
        text = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")

        self.assertIn("request_text", text)
        self.assertIn("prepare-turn-context", text)
        self.assertIn("the host should choose by combining the resolved skill metadata with `task_context`, `track_context`, and the buddy contract docs", text)
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

    def test_pm_skill_metadata_uses_explicit_market_inputs(self) -> None:
        path = ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "skill.toml"
        expected_slots = [
            "market-scan",
            "pmf-report",
            "customer-discovery",
            "positioning-brief",
            "channel-plan",
            "launch-prep",
            "requirements",
            "track",
        ]

        parsed = env_manifest._load_toml(path)  # type: ignore[attr-defined]
        self.assertEqual(parsed["input_slots"], expected_slots)
        self.assertEqual(parsed["consumes"], expected_slots)

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
        manifest = env_manifest.load_manifest()
        market_skills = {
            skill["id"]: skill["runtime"]
            for skill in manifest.get("skills", [])
            if isinstance(skill, dict)
            and isinstance(skill.get("runtime"), dict)
            and skill["runtime"].get("buddy") == "market"
        }
        for path in SKILL_TOMLS[:6]:
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                parsed = market_skills.get(path.parent.name, {})
                host_execution = parsed.get("host_execution", {}) if isinstance(parsed, dict) else {}
                for key, value in BROWSER_COCKPIT_METADATA.items():
                    self.assertEqual(host_execution.get(key), value, msg=f"{path.relative_to(ROOT)} missing {key}={value}")
                self.assertEqual(
                    parsed.get("required_tools"),
                    BROWSER_COCKPIT_REQUIRED_TOOLS,
                    msg=f"{path.relative_to(ROOT)} missing required_tools={BROWSER_COCKPIT_REQUIRED_TOOLS}",
                )

    def test_market_skill_metadata_uses_instance_cockpit_tokens(self) -> None:
        for path in SKILL_TOMLS[:6]:
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                parsed = env_manifest._load_toml(path)  # type: ignore[attr-defined]
                self.assertEqual(parsed["browser_profile"], "instance-browser")
                self.assertEqual(parsed["session_continuity"], "instance-cockpit")
                self.assertNotEqual(parsed["browser_profile"], "shared-browser")
                self.assertNotEqual(parsed["session_continuity"], "shared-cockpit")

    def test_market_skills_share_market_tool_scope_profile(self) -> None:
        for path in SKILL_TOMLS[:6]:
            with self.subTest(skill_toml=str(path.relative_to(ROOT))):
                parsed = env_manifest._load_toml(path)  # type: ignore[attr-defined]
                self.assertEqual(
                    parsed.get("tool_scope_profile"),
                    EXPECTED_MARKET_TOOL_SCOPE_PROFILE,
                    msg=f"{path.relative_to(ROOT)} missing tool_scope_profile={EXPECTED_MARKET_TOOL_SCOPE_PROFILE}",
                )

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
        required_tokens = ("chrome-devtools-cockpit", "browser-native", "user-approved")
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
        for path in (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
            ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md",
        ):
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("all enabled mcp servers", text)
                self.assertIn('default_tools_approval_mode = "approve"', text)
                self.assertIn("supports_parallel_tool_calls = true", text)
                self.assertIn("do not set", text)

    def test_market_schemas_share_market_cockpit_evidence_fields(self) -> None:
        for path in MARKET_SCHEMA_PATHS:
            with self.subTest(schema=str(path.relative_to(ROOT))):
                schema = json.loads(path.read_text(encoding="utf-8"))
                evidence_item = schema["properties"]["artifact_content"]["properties"]["evidence"]["items"]
                evidence_required = evidence_item["required"]
                evidence_properties = evidence_item["properties"]
                for field_name in MARKET_EVIDENCE_FIELDS:
                    self.assertIn(field_name, evidence_required, msg=f"{path.relative_to(ROOT)} missing {field_name}")
                for field_name in OPTIONAL_MARKET_EVIDENCE_FIELDS:
                    self.assertIn(field_name, evidence_properties, msg=f"{path.relative_to(ROOT)} missing optional property {field_name}")
                    self.assertNotIn(field_name, evidence_required, msg=f"{path.relative_to(ROOT)} should not require {field_name}")

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
        self.assertIn("may also include", evidence_section)
        for field_name in OPTIONAL_MARKET_EVIDENCE_FIELDS:
            self.assertIn(field_name, evidence_section)

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

    def test_market_cockpit_doc_defines_resolve_context_execution_boundary(self) -> None:
        cockpit_doc = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("resolve_context.skills[*].host_execution", cockpit_doc)
        self.assertIn("resolve_context.skills[*].tool_scope", cockpit_doc)
        self.assertIn("does not imply that top-level `resolve_context.inputs` is already populated", cockpit_doc)
        self.assertIn("host stays the only executor", cockpit_doc)
        self.assertIn("these six skills stay separate", cockpit_doc)
        self.assertIn("not a second source of truth", cockpit_doc)
        self.assertNotIn("selected_skill_packet", cockpit_doc)
        self.assertNotIn("prepare-execution", cockpit_doc)

    def test_switch_spec_documents_resolve_context_loop(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("resolve_context", switch_spec)
        self.assertIn("persist-skill-result", switch_spec)
        self.assertIn("refreshed_context", switch_spec)
        self.assertIn("preserves the resolved task-track binding", switch_spec)
        self.assertNotIn("prepare-execution", switch_spec)
        self.assertNotIn("selected_skill_packet", switch_spec)

    def test_switch_spec_defers_market_execution_boundary_to_skill_metadata(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("resolve_context.skills[*].host_execution", switch_spec)
        self.assertIn("resolve_context.skills[*].tool_scope", switch_spec)
        self.assertIn("browser-native", switch_spec)
        self.assertNotIn("selected_skill_packet.execution_steps", switch_spec)

    def test_top_level_docs_define_resolve_context_flow(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "AGENTS.md",
                ROOT / "README.md",
                ROOT / ".codex" / "agents" / "router.toml",
                ROOT / "framework" / "docs" / "switch-spec.md",
            )
        ).lower()

        self.assertIn("resolve_context", combined)
        self.assertIn("persist-skill-result", combined)
        self.assertIn("refreshed_context", combined)
        self.assertIn("buddyswitch does not execute host tools", combined)
        self.assertNotIn("prepare-execution", combined)
        self.assertNotIn("selected_skill_packet", combined)

    def test_runtime_docs_state_resolve_and_persist_require_runtime_workspace(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("launcher-owned runtime workspace", readme)
        self.assertIn("repo-root development checkout blocks it", readme)
        self.assertIn("launcher-owned runtime workspace", switch_spec)
        self.assertIn("repo-root source checkout", switch_spec)

    def test_product_mode_docs_define_shared_project_workspace(self) -> None:
        buddy_docs = (
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "design" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "dev" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "market" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "test" / "AGENTS.md",
        )
        docs = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md",
            *buddy_docs,
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in docs).lower()

        self.assertIn("projects/app", combined)
        self.assertIn("shared project workspace", combined)
        self.assertIn("instance runtime workspace", combined)
        self.assertIn("shared product source", combined)
        self.assertNotIn("${buddyswitch_project_workspace_dir}/projects/app", combined)
        self.assertNotIn("${buddyswitch_shared_root}/project/workspace/projects/app", combined)
        self.assertNotIn(
            "durable product source edits belong under `${buddyswitch_shared_root}/instances/<instance-id>/workspace/projects/app`",
            combined,
        )

    def test_host_docs_treat_inputs_as_conditional_selected_bundle(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        runtime_agents = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
            encoding="utf-8"
        ).lower()
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("request_text", readme)
        self.assertIn("prepare-turn-context", readme)
        self.assertIn("inputs_by_skill", switch_spec)
        self.assertNotIn("top-level `inputs` may be empty", switch_spec)
        self.assertNotIn("resolve_context.inputs[", runtime_agents)

    def test_docs_place_persist_follow_up_fields_inside_receipt(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()

        self.assertTrue(
            "the host-facing follow-up data lives inside `receipt`" in readme
            or "host-facing follow-up fields live inside `receipt`" in readme
        )
        self.assertIn("receipt.next_state", readme)
        self.assertIn("receipt_paths", readme)
        self.assertIn("host-facing follow-up fields live inside `receipt`", switch_spec)
        self.assertIn("receipt.next_state", switch_spec)
        self.assertIn("receipt.receipt_paths", switch_spec)
        self.assertNotIn("receipt.recommended_switch", switch_spec)

    def test_active_host_prompts_require_refresh_context_check_and_retry(self) -> None:
        targets = (
            ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md",
            ROOT / ".codex" / "agents" / "router.toml",
        )
        legacy_unconditional_runtime = (
            "continue from `refreshed_context` when another buddy turn is needed after a successful persist."
        )
        legacy_unconditional_router = (
            "continue from `refreshed_context` after a successful persist when the task needs another turn."
        )

        for path in targets:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("check `refreshed_context.ok`", text, msg=f"missing refreshed_context.ok guard in {path.relative_to(ROOT)}")
            self.assertIn("e_runtime_refresh_context", text, msg=f"missing refresh error code in {path.relative_to(ROOT)}")
            self.assertIn("`resolve`", text, msg=f"missing resolve retry guidance in {path.relative_to(ROOT)}")
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
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()

        self.assertIn("successful `persist` does not reserve a follow-up run", readme)
        self.assertIn("receipt.next_state", readme)
        self.assertIn("receipt_paths", readme)
        self.assertIn("if another turn is needed", readme)
        self.assertIn("`resolve`", readme)
        self.assertIn("request_text", readme)
        self.assertNotIn("receipt.recommended_switch", readme)
        self.assertNotIn("continue from `refreshed_context`", readme)

        self.assertIn("`persist` is the end-of-turn commit boundary", switch_spec)
        self.assertIn("successful `persist` does not reserve a follow-up run", switch_spec)
        self.assertIn("receipt.next_state", switch_spec)
        self.assertIn("receipt.receipt_paths", switch_spec)
        self.assertNotIn("receipt.recommended_switch", switch_spec)
        self.assertNotIn("`refreshed_context` normally carries the next-turn resolve handoff", switch_spec)
        self.assertNotIn("continue from `refreshed_context` when it is true", switch_spec)

    def test_active_host_prompts_require_explicit_resolve_after_persist(self) -> None:
        targets = (
            ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md",
            ROOT / ".codex" / "agents" / "router.toml",
        )

        for path in targets:
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("check `refreshed_context.ok`", text)
            self.assertIn("e_runtime_refresh_context", text)
            self.assertIn("request_text", text)
            self.assertIn("`resolve`", text)
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
        self.assertIn("scripts/switch_runtime.py resolve", text)
        self.assertIn("scripts/switch_runtime.py persist", text)
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
                self.assertIn("resolve_context", lower)
                self.assertIn("refreshed_context", lower)
                self.assertIn("runs/raw/", lower)
                self.assertIn("projects/app", lower)

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
                self.assertIn("receipt -> summary", lower)
                required_runtime_tokens = (
                    "resolve_context",
                    "selected-skill preflight",
                    "host_execution",
                    "tool_scope",
                    "persist-skill-result",
                    "refreshed_context",
                    "runs/raw/",
                    "projects/app",
                )
                for token in required_runtime_tokens:
                    self.assertIn(token, lower)
                self.assertNotIn("projects/app/.runtime/", lower)

    def test_runtime_prompt_does_not_present_switch_as_product_ui(self) -> None:
        runtime_agents = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("internal/debug wire", runtime_agents)
        self.assertNotIn("canonical ui", runtime_agents)
        self.assertNotIn("use the canonical directive", runtime_agents)

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

    def test_switch_spec_is_marked_internal_debug_wire_contract(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("internal/debug wire", switch_spec)
        self.assertNotIn("product-mode users should type", switch_spec)

    def test_product_output_docs_do_not_reintroduce_command_section_or_copyable_switch_guidance(self) -> None:
        product_output_docs = (
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "switch-spec.md",
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
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
        self.assertIn("receipt -> summary", readme)
        self.assertIn("receipt -> summary", switch_spec)

        # Legacy switch-command follow-up fields must stay retired from output docs.
        self.assertNotIn("reference_switches", switch_spec)
        self.assertNotIn("recommended_switch", switch_spec)
        self.assertNotIn("commands order", switch_spec)

    def test_runtime_host_prompt_defines_selected_skill_preflight_mitigation(self) -> None:
        text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
            encoding="utf-8"
        ).lower()

        required_semantics = (
            "selected skill",
            "preflight",
            "host_execution",
            "tool_scope",
            "login_policy",
            "fallback_policy",
            "required_tools",
            "required_env",
            "browser_executor",
            "browser-native",
            "explicit user approval",
            "advisory",
        )
        positions: dict[str, int] = {}
        for token in required_semantics:
            position = text.find(token)
            self.assertNotEqual(position, -1, msg=f"missing selected-skill preflight runtime semantic: {token}")
            positions[token] = position

        grouped_tokens = (
            "selected skill",
            "preflight",
            "host_execution",
            "tool_scope",
            "login_policy",
            "fallback_policy",
            "required_tools",
            "required_env",
            "browser_executor",
            "browser-native",
            "explicit user approval",
            "advisory",
        )
        grouped_positions = [positions[token] for token in grouped_tokens]
        self.assertLess(
            max(grouped_positions) - min(grouped_positions),
            1800,
            msg="selected-skill preflight runtime semantics should stay grouped in the host preflight area",
        )
        self.assertRegex(
            text,
            r"temporary downgrade tools[\s\S]{0,200}explicit user approval",
            msg="runtime prompt must bind temporary downgrade tools to explicit user approval",
        )
        self.assertRegex(
            text,
            r"login_policy[\s\S]{0,120}mandatory-takeover[\s\S]{0,200}pause for takeover",
            msg="runtime prompt must tie mandatory-takeover to a pause-for-takeover instruction",
        )
        self.assertIn(
            "do not reinterpret missing executor availability, login takeover, and genuine browser-native blocking as the same path",
            text,
            msg="runtime prompt must keep missing executor, takeover, and genuine browser-native blocking as separate paths",
        )
        self.assertNotIn("for market runs", text)
        self.assertNotIn("hard gate", text)
        self.assertNotIn("enforced", text)
        self.assertNotIn("prevented", text)
        self.assertNotIn("before any external action", text)
        self.assertNotIn("required tools must be present before continuing", text)

    def test_router_prompt_keeps_selected_skill_preflight_reduced_parity(self) -> None:
        text = (ROOT / ".codex" / "agents" / "router.toml").read_text(encoding="utf-8").lower()

        required_semantics = (
            "selected skill",
            "preflight",
            "host_execution",
            "tool_scope",
            "required_tools",
            "required_env",
            "browser_executor",
            "browser-native",
            "explicit user approval",
            "mandatory-takeover",
            "advisory",
        )
        positions: dict[str, int] = {}
        for token in required_semantics:
            position = text.find(token)
            self.assertNotEqual(position, -1, msg=f"missing selected-skill preflight router reduced semantic: {token}")
            positions[token] = position

        grouped_positions = [positions[token] for token in required_semantics]
        self.assertLess(
            max(grouped_positions) - min(grouped_positions),
            1800,
            msg="router selected-skill preflight reduced semantics should stay grouped in host responsibility guidance",
        )
        self.assertRegex(
            text,
            r"mandatory-takeover[\s\S]{0,160}separate[\s\S]{0,160}downgrade",
            msg="router reduced parity must keep mandatory-takeover separate from downgrade handling",
        )
        self.assertNotIn("for market runs", text)
        self.assertNotIn(
            "do not reinterpret missing executor availability, login takeover, and genuine browser-native blocking as the same path",
            text,
        )
        self.assertNotIn("external tool invocation or evidence capture", text)

    def test_router_doc_lists_task_objects_as_canonical_state(self) -> None:
        text = (ROOT / ".codex" / "agents" / "router.toml").read_text(encoding="utf-8").lower()

        self.assertIn("buddyswitch/objects/tasks/*.json", text)

    def test_switch_spec_lists_current_runtime_errors(self) -> None:
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")
        self.assertIn(
            "Runtime should return explicit errors:\n\n- `E_RUNTIME_RESOLVE`\n- `E_RUNTIME_PERSIST`\n- `E_RUNTIME_REFRESH_CONTEXT`",
            switch_spec,
        )
        self.assertNotIn("E_RUNTIME_PREPARE_EXECUTION", switch_spec)

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
            ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype",
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
            ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype",
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
            ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "assets" / "design-handoff-template.md",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
        )
        for path in expected_assets:
            with self.subTest(asset=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), msg=f"missing template asset: {path.relative_to(ROOT)}")

    def test_shape_prototype_package_files_exist(self) -> None:
        self.assertTrue((ROOT / "framework" / "schemas" / "design" / "shape-prototype.json").exists())
        self.assertTrue((ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "skill.toml").exists())
        self.assertTrue((ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "SKILL.md").exists())

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

    def test_parallel_contract_files_exist_and_define_expected_ids(self) -> None:
        expected_contract_ids = {
            "switch-grammar": PARALLEL_CONTRACT_FILES[0],
            "resolve-context": PARALLEL_CONTRACT_FILES[1],
            "persist-skill-result": PARALLEL_CONTRACT_FILES[2],
            "workspace-projection": PARALLEL_CONTRACT_FILES[3],
        }
        loaded_contracts: dict[str, dict[str, object]] = {}
        for contract_id, path in expected_contract_ids.items():
            with self.subTest(contract=contract_id):
                self.assertTrue(path.exists(), msg=f"missing contract file {path.relative_to(ROOT)}")
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload.get("contract_id"), contract_id)
                self.assertIn("contract_version", payload)
                loaded_contracts[contract_id] = payload

        resolve_context = loaded_contracts["resolve-context"]
        self.assertIn("response_key_order", resolve_context)
        self.assertIn("context_revision", resolve_context["response_key_order"])
        self.assertIn("skills", resolve_context["response_key_order"])

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
        switch_spec = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8")
        interface_spec = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")

        self.assertIn("framework/contracts/switch-grammar.json", switch_spec)
        self.assertIn("framework/contracts/resolve-context.json", switch_spec)
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
        self.assertIn("switch_runtime", text)
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
