#!/usr/bin/env python3
"""Repo-level consistency checks for buddy-run persistence architecture."""

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
import turn_runtime  # noqa: E402


class RepoConsistencyTests(unittest.TestCase):
    def _git_ls_files(self, *paths: str) -> list[str]:
        completed = subprocess.run(
            ["git", "ls-files", "--", *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return [line for line in completed.stdout.splitlines() if line and (ROOT / line).exists()]

    def _active_skill_asset_text(self) -> str:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        chunks: list[str] = []
        for skill in manifest.get("skills", []):
            assert isinstance(skill, dict)
            skill_root = ROOT / str(skill["path"])
            for path in skill_root.rglob("*"):
                if path.is_file() and path.suffix in {".md", ".json"}:
                    chunks.append(path.read_text(encoding="utf-8"))
        return "\n".join(chunks)

    def _active_runtime_contract_paths(self) -> list[Path]:
        paths = [
            ROOT / "README.md",
            ROOT / "framework" / "docs" / "architecture-overview.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "skill-runtime-shared-rules.md",
            ROOT / "framework" / "contracts" / "pm.md",
            ROOT / "framework" / "contracts" / "market.md",
            ROOT / "framework" / "contracts" / "design.md",
            ROOT / "framework" / "contracts" / "dev.md",
            ROOT / "framework" / "contracts" / "test.md",
            ROOT / "scripts" / "turn_runtime.py",
        ]
        paths.extend(sorted((ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md")))
        return paths

    def test_runtime_agents_skills_are_instance_only_in_active_docs(self) -> None:
        self.assertFalse((ROOT / ".agents").exists())
        docs = [
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "framework" / "docs" / "turn-runtime-spec.md",
            ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
        ]
        docs.extend((ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"))
        for path in docs:
            text = path.read_text(encoding="utf-8")
            if ".agents/skills" in text:
                self.assertIn("instance", text.lower(), msg=f"{path.relative_to(ROOT)} must describe instance scope")

    def test_launcher_help_keeps_instance_data_env_namespaces(self) -> None:
        completed = subprocess.run(
            ["./buddyswitch-codex", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        output = completed.stdout
        self.assertIn("instance start --buddy", output)
        self.assertIn("data cleanup", output)
        self.assertIn("env browser status", output)
        self.assertIn("Commands:", output)
        self.assertIn("instance", output)
        self.assertIn("data", output)
        self.assertIn("env", output)
        self.assertNotIn("switch pm:", output.lower())
        self.assertNotIn("switch market:", output.lower())

    def test_runtime_state_directories_are_not_tracked_in_main_checkout(self) -> None:
        tracked = self._git_ls_files("buddyswitch/objects", "buddyswitch/content/runs", "runs/raw")
        self.assertEqual(tracked, [])

    def test_runtime_lock_guards_are_present_in_active_sources(self) -> None:
        sources = [
            ROOT / "tools" / "launcher" / "runtime_lock.py",
            ROOT / "scripts" / "turn_runtime.py",
            ROOT / "scripts" / "runtime_store" / "projections.py",
            ROOT / "tests" / "test_cleanup_system.py",
        ]
        for path in sources:
            text = path.read_text(encoding="utf-8")
            self.assertIn("runtime.lock", text, msg=f"{path.relative_to(ROOT)} must reference runtime lock path")

    def test_browser_cockpit_and_native_materialization_docs_are_active(self) -> None:
        cockpit_doc = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8")
        self.assertIn("chrome-devtools-cockpit", cockpit_doc)
        self.assertIn("instance-browser", cockpit_doc)
        self.assertIn(".agents/skills", cockpit_doc)

        runtime_doc = (ROOT / "framework" / "docs" / "skill-runtime-shared-rules.md").read_text(encoding="utf-8")
        self.assertIn(".agents/skills/<skill-id>", runtime_doc)
        self.assertIn("persist --context <context> --result <result>", runtime_doc)

    def test_browser_cockpit_public_contract_requires_ready_page_not_endpoint_only(self) -> None:
        cockpit_doc = (ROOT / "framework" / "docs" / "browser-cockpit.md").read_text(encoding="utf-8")
        lowered = cockpit_doc.lower()
        self.assertIn("ready page", lowered)
        self.assertIn("about:blank", lowered)
        self.assertIn("chrome://intro", lowered)
        self.assertNotIn("ensures the instance-bound headed cockpit endpoint", cockpit_doc)

        browser_launcher = (ROOT / "tools" / "launcher" / "browser_cockpit.sh").read_text(encoding="utf-8").lower()
        self.assertIn("usable ready page", browser_launcher)
        self.assertNotIn("endpoint is reachable", browser_launcher)

    def test_tg07_ready_gate_assets_keep_browser_diagnosis_out_of_prompts_and_compat_migration_out_of_active_surfaces(self) -> None:
        prompt_paths = sorted((ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"))
        prompt_paths.extend(sorted((ROOT / "buddyswitch" / "skills" / "market").rglob("SKILL.md")))
        forbidden_prompt_terms = (
            "chrome://intro",
            "put /json/new",
            "no page selected",
            "first-run chrome",
            "no-first-run",
            "about:blank",
        )
        for path in prompt_paths:
            text = path.read_text(encoding="utf-8").lower()
            for token in forbidden_prompt_terms:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)

        active_launcher_docs_paths = [
            ROOT / "buddyswitch-codex",
            ROOT / "tools" / "launcher" / "browser_cockpit.sh",
            ROOT / "framework" / "docs" / "browser-cockpit.md",
            ROOT / "README.md",
        ]
        forbidden_transition_terms = (
            "old-instance migration",
            "old instance migration",
            "compatibility transition",
            "transition marker",
            "migration marker",
            "old-profile migration",
            "old profile migration",
        )
        for path in active_launcher_docs_paths:
            text = path.read_text(encoding="utf-8").lower()
            for token in forbidden_transition_terms:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)

    def test_console_boundary_uses_workspace_api(self) -> None:
        app_js = (ROOT / "framework" / "console" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/workspace", app_js)
        self.assertNotIn("env_store", app_js)
        self.assertNotIn("turn_runtime", app_js)
        self.assertNotIn("runtime_store.repositories", app_js)

    def test_browser_ui_does_not_import_runtime_internals(self) -> None:
        ui_surfaces = (
            ROOT / "framework" / "console" / "app.js",
        )
        forbidden_runtime_internals = (
            "env_store",
            "runtime_store.projections",
            "turn_runtime",
            "workspace_data",
        )

        for path in ui_surfaces:
            text = path.read_text(encoding="utf-8")
            for token in forbidden_runtime_internals:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)

        console_app_js = (ROOT / "framework" / "console" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/workspace", console_app_js)

        interface_spec = (ROOT / "framework" / "docs" / "interface-spec.md").read_text(encoding="utf-8")
        self.assertIn("`framework/console/app.js`", interface_spec)
        self.assertNotIn("`projects/app/" + "main.js`", interface_spec)

        agents_doc = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Shared product-source mount point: `projects/app/`", agents_doc)
        self.assertNotIn("Main app " + "code: `projects/app/`", agents_doc)

    def test_projects_app_is_framework_placeholder_only(self) -> None:
        tracked = self._git_ls_files("projects/app")
        self.assertEqual(tracked, ["projects/app/README.md"])

        placeholder = ROOT / "projects" / "app" / "README.md"
        text = placeholder.read_text(encoding="utf-8")
        self.assertIn("runtime mount point", text)
        self.assertIn("does not ship a concrete", text)

        forbidden_suffixes = {".html", ".js", ".css", ".jsx", ".tsx", ".vue", ".svelte"}
        concrete_files = [path for path in tracked if Path(path).suffix in forbidden_suffixes]
        self.assertEqual(concrete_files, [])

        forbidden_product_tokens = (
            "Day" + "Flow",
            "AI " + "Scheduler",
            "onboarding" + "-demo",
            "sample landing page",
            "Personal Schedule " + "Manager",
        )
        for path in tracked:
            content = (ROOT / path).read_text(encoding="utf-8")
            for token in forbidden_product_tokens:
                with self.subTest(path=path, token=token):
                    self.assertNotIn(token, content)

    def test_importer_does_not_reintroduce_retired_runtime_paths(self) -> None:
        importer_text = (ROOT / "scripts" / "skill_creator_importer.py").read_text(encoding="utf-8")
        for token in (
            "persist --skill-id",
            "persist-skill-result",
            "runs/summaries/",
            "artifacts/",
            "prepare_context.skills",
            "instruction_path",
        ):
            self.assertNotIn(token, importer_text)

    def test_first_party_skills_have_no_skill_toml(self) -> None:
        for skill_dir in (ROOT / "buddyswitch" / "skills").rglob("*"):
            if not skill_dir.is_dir():
                continue
            with self.subTest(path=str(skill_dir.relative_to(ROOT))):
                self.assertFalse((skill_dir / "skill.toml").exists())
                self.assertFalse((skill_dir / "skill.yaml").exists())
                self.assertFalse((skill_dir / "skill.yml").exists())

    def test_template_assets_exist(self) -> None:
        required_templates = [
            ROOT / "buddyswitch" / "skills" / "pm" / "write-prd" / "assets" / "prd-template.md",
            ROOT / "buddyswitch" / "skills" / "shared" / "track-manager" / "assets" / "track-operation-template.md",
            ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "assets" / "design-handoff-template.md",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md",
        ]
        for path in required_templates:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists())

    def test_framework_markdown_templates_are_removed(self) -> None:
        templates_dir = ROOT / "framework" / "templates"
        self.assertFalse((templates_dir / "prd.md").exists())
        self.assertFalse((templates_dir / "impl-report.md").exists())
        self.assertFalse((templates_dir / "research-report.md").exists())
        self.assertFalse((templates_dir / "test-report.md").exists())

    def test_active_specs_do_not_teach_superseded_runtime_models(self) -> None:
        active_specs = [
            path
            for path in (ROOT / "docs" / "spec").glob("*.md")
            if "complete-residue-cleanup" not in path.name
        ]
        forbidden = (
            "artifact_content",
            "deliverables_or_changed_files",
            "state_effects.track_operation",
            "persist --skill-id",
            "runtime still contains a router-era guard",
            "Command-shaped routing input is rejected",
            "Expected before implementation: FAILED",
            "market-landing-page-brief",
            "specialized_sections",
            "evidence-run-0123456789-abcd1234",
            "downgrade-run-0123456789-abcd1234",
            "\"browser_cockpit_token\": \"evidence-",
            "\"approved_downgrade_token\": \"downgrade-",
        )
        for path in active_specs:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)

    def test_buddy_prompt_assets_exist(self) -> None:
        for buddy in ("design", "dev", "market", "pm", "test"):
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            with self.subTest(buddy=buddy):
                self.assertTrue(path.exists())
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# BuddySwitch Runtime Workspace\n"))
                self.assertIn("user text does not change it", text)

    def test_active_product_paths_exclude_legacy_switch_wire(self) -> None:
        tracked = self._git_ls_files("README.md", "framework/docs", "framework/contracts", "scripts", "tools/launcher/assets", "buddyswitch/skills")
        forbidden_tokens = (
            "persist --skill-id",
            "persist-skill-result",
            "selected skill_id",
            "selected_" + "skill_packet",
            "prepare_context." + "skills",
            "instruction_path",
            "recommended" + "_switch",
            "reference_" + "switches",
            "switch " + "<buddy>:",
            "switch " + "pm:",
            "switch " + "market:",
            "switch " + "dev:",
            "Command-shaped routing input is rejected",
            "command-shaped routing input is rejected",
            "router-era guard",
        )
        for rel_path in tracked:
            path = ROOT / rel_path
            if not path.exists():
                continue
            if path.suffix not in {".md", ".py", ".json", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=rel_path, token=token):
                    self.assertNotIn(token, text)

    def test_active_authoring_surfaces_use_buddy_run_commit_shape(self) -> None:
        tracked = self._git_ls_files(
            "framework/contracts",
            "framework/schemas",
            "buddyswitch/skills",
        )
        forbidden_tokens = (
            "deliverables_or_changed" + "_files",
            "artifact" + "_content",
            "specialized" + "_sections",
            "track" + "_operation",
        )
        for rel_path in tracked:
            path = ROOT / rel_path
            if not path.exists() or path.suffix not in {".md", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=rel_path, token=token):
                    self.assertNotIn(token, text)

    def test_active_store_has_no_legacy_named_repository_layer(self) -> None:
        active_paths = (
            ROOT / "scripts" / "env_store.py",
            ROOT / "scripts" / "runtime_store" / "__init__.py",
            ROOT / "scripts" / "runtime_store" / "projections.py",
            ROOT / "tests" / "test_env_store_v2.py",
        )
        for path in active_paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("_legacy_", text)
        self.assertFalse((ROOT / "scripts" / "runtime_store" / "repositories.py").exists())

    def test_parallel_contract_surface_targets_persist_buddy_run(self) -> None:
        contract_test = (ROOT / "tests" / "test_parallel_contracts.py").read_text(encoding="utf-8")
        self.assertIn("persist-buddy-run", contract_test)
        self.assertNotIn("persist-skill-result", contract_test)

    def test_market_templates_do_not_contain_copyable_fake_evidence_tokens(self) -> None:
        market_assets = ROOT / "buddyswitch" / "skills" / "market"
        forbidden_tokens = (
            "<broker-issued-token-from-current-run>",
            "\"browser_cockpit_token\": \"<",
            "browser_cockpit_token = \"<",
        )
        for path in market_assets.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)

    def test_manifest_skill_rows_are_id_and_path_only(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        for skill in manifest.get("skills", []):
            self.assertIsInstance(skill, dict)
            assert isinstance(skill, dict)
            self.assertEqual(set(skill.keys()), {"id", "path"})

    def test_manifest_buddies_define_artifact_kinds(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        buddies = env_manifest.buddies_by_id(manifest)
        self.assertEqual(
            buddies["market"]["artifact_kinds"],
            [
                "market-scan",
                "pmf-report",
                "customer-discovery",
                "positioning-brief",
                "channel-plan",
                "launch-prep",
            ],
        )
        self.assertEqual(buddies["pm"]["artifact_kinds"], ["prd", "pm-decision", "track-note"])
        self.assertEqual(buddies["design"]["artifact_kinds"], ["design-handoff", "prototype-brief"])
        self.assertEqual(buddies["dev"]["artifact_kinds"], ["implementation-report", "skill-import-report"])
        self.assertEqual(buddies["test"]["artifact_kinds"], ["smoke-test", "test-report"])

    def test_manifest_artifact_kinds_have_active_guidance(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        active_skill_text = self._active_skill_asset_text()
        allowed_without_asset = {
            "pm-decision",
            "track-note",
            "prototype-brief",
            "test-report",
        }
        for buddy in manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            for kind in buddy.get("artifact_kinds", []):
                assert isinstance(kind, str)
                with self.subTest(buddy=buddy["id"], kind=kind):
                    self.assertTrue(
                        kind in allowed_without_asset or kind in active_skill_text,
                        f"{kind} must be documented by an active skill asset or explicit non-template allowlist",
                    )

    def test_runtime_artifact_kind_desc_covers_manifest_kinds(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        expected_kinds = {
            kind
            for buddy in manifest.get("buddies", [])
            if isinstance(buddy, dict)
            for kind in buddy.get("artifact_kinds", [])
            if isinstance(kind, str) and kind
        }
        runtime_desc = getattr(turn_runtime, "_ARTIFACT_KIND_DESC")
        self.assertEqual(set(runtime_desc.keys()), expected_kinds)
        for kind in expected_kinds:
            with self.subTest(kind=kind):
                row = runtime_desc[kind]
                self.assertTrue(str(row.get("label", "")).strip())
                self.assertTrue(str(row.get("use_when", "")).strip())

    def test_turn_runtime_spec_documents_prepare_desc_and_context_save_surfaces(self) -> None:
        runtime_doc = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8")
        for token in (
            "context_save_path",
            "persist_command_hint",
            "runtime_context.desc",
            "runtime_context.track_lifecycle_desc",
            "runtime_context.artifact_kind_desc",
            "runtime_context.context_sources_desc",
        ):
            with self.subTest(token=token):
                self.assertIn(token, runtime_doc)
        self.assertIn("structured feedback", runtime_doc.lower())

    def test_persist_contract_is_buddy_run_and_legacy_contract_removed(self) -> None:
        contract_path = ROOT / "framework" / "contracts" / "persist-buddy-run.json"
        self.assertTrue(contract_path.exists())
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("contract_id"), "persist-buddy-run")
        self.assertEqual(payload.get("contract_version"), "2026-05-06")

        legacy_path = ROOT / "framework" / "contracts" / "persist-skill-result.json"
        self.assertFalse(legacy_path.exists())

    def test_turn_runtime_uses_buddy_run_persist_surface(self) -> None:
        runtime_text = (ROOT / "scripts" / "turn_runtime.py").read_text(encoding="utf-8")
        self.assertIn("def persist_buddy_run", runtime_text)
        self.assertNotIn("def persist_skill_result", runtime_text)
        self.assertNotIn("--skill-id", runtime_text)

    def test_runtime_skills_has_no_persist_runtime_coupling(self) -> None:
        text = (ROOT / "scripts" / "runtime_skills.py").read_text(encoding="utf-8")
        self.assertNotIn("import turn_runtime", text)
        self.assertNotIn("import env_store", text)
        self.assertNotIn("persist-skill-result", text)
        self.assertNotIn("persist-buddy-run", text)

    def test_skill_packages_do_not_instruct_skill_level_persist(self) -> None:
        for skill_md in (ROOT / "buddyswitch" / "skills").rglob("SKILL.md"):
            with self.subTest(skill=str(skill_md.relative_to(ROOT))):
                text = skill_md.read_text(encoding="utf-8")
                self.assertNotIn("persist --skill-id", text)

    def test_active_skill_outputs_do_not_claim_direct_state_writes(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        forbidden = (
            "A PM artifact object in `buddyswitch/objects/artifacts/`",
            "A run audit in `buddyswitch/content/runs/`",
            "A Market artifact object in `buddyswitch/objects/artifacts/`",
            "A Design artifact object in `buddyswitch/objects/artifacts/`",
            "A Dev artifact object in `buddyswitch/objects/artifacts/`",
            "A Test artifact object in `buddyswitch/objects/artifacts/`",
        )
        for skill in manifest.get("skills", []):
            assert isinstance(skill, dict)
            skill_md = ROOT / str(skill["path"]) / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(skill=skill["id"], token=token):
                    self.assertNotIn(token, text)
            self.assertIn("Contribute to one buddy-run commit", text)
            self.assertIn("Do not call persist from inside the skill", text)

    def test_buddy_agent_docs_do_not_reference_legacy_persist_api(self) -> None:
        for agents_md in (ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"):
            with self.subTest(doc=str(agents_md.relative_to(ROOT))):
                text = agents_md.read_text(encoding="utf-8")
                self.assertNotIn("persist --skill-id", text)
                self.assertIn('python3 scripts/turn_runtime.py prepare "<request>"', text)
                self.assertIn("python3 scripts/turn_runtime.py persist --context <context> --result <result>", text)

    def test_active_host_runtime_contract_has_no_bare_turn_runtime_commands(self) -> None:
        bare_pattern = re.compile(r"(?<!python3 )scripts/turn_runtime\.py (prepare|persist)")
        for path in self._active_runtime_contract_paths():
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(
                    bare_pattern.search(text),
                    msg=f"{path.relative_to(ROOT)} contains bare turn_runtime command; use canonical python3 form.",
                )

    def test_runtime_agents_do_not_duplicate_runtime_context_payload_recipes(self) -> None:
        forbidden_snippets = (
            "AI日程工具",
            "AI calendar",
            "browser_cockpit_token\":",
            "approved_downgrade_token\":",
            "\"state_effects\"",
            "\"artifact_kinds\"",
            "instance continue",
            "open-handoff",
        )
        for agents_md in (ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"):
            text = agents_md.read_text(encoding="utf-8")
            with self.subTest(doc=str(agents_md.relative_to(ROOT))):
                self.assertIn("prepare.runtime_context", text)
                for snippet in forbidden_snippets:
                    self.assertNotIn(snippet, text)

    def test_manifest_declares_shared_managers_for_every_buddy(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {
            row["id"]: row
            for row in manifest.get("skills", [])
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
        self.assertIn("task-manager", skills)
        self.assertEqual(
            skills["task-manager"].get("path"),
            "buddyswitch/skills/shared/task-manager",
        )
        self.assertIn("track-manager", skills)
        self.assertEqual(
            skills["track-manager"].get("path"),
            "buddyswitch/skills/shared/track-manager",
        )
        for buddy in manifest.get("buddies", []):
            if not isinstance(buddy, dict):
                continue
            buddy_id = buddy.get("id")
            skill_ids = [item for item in buddy.get("skills", []) if isinstance(item, str)]
            with self.subTest(buddy=buddy_id):
                self.assertEqual(skill_ids.count("task-manager"), 1)
                self.assertEqual(skill_ids.count("track-manager"), 1)

    def test_task_manager_skill_keeps_permissions_in_runtime_code(self) -> None:
        skill_md = ROOT / "buddyswitch" / "skills" / "shared" / "task-manager" / "SKILL.md"
        self.assertTrue(skill_md.exists())
        text = skill_md.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("runtime/tool feedback", lowered)
        self.assertIn("active buddy", lowered)
        for token in (
            "buddyswitch/objects/tasks",
            "buddyswitch/content/runs",
            "write raw state",
            "permission " + "matrix",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, lowered)

    def test_track_manager_skill_keeps_permissions_in_runtime_code(self) -> None:
        skill_md = ROOT / "buddyswitch" / "skills" / "shared" / "track-manager" / "SKILL.md"
        self.assertTrue(skill_md.exists())
        text = skill_md.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("runtime/tool feedback", lowered)
        self.assertIn("active buddy", lowered)
        for token in (
            "buddyswitch/objects/tracks",
            "buddyswitch/content/runs",
            "write raw state",
            "permission " + "matrix",
            "state_effects.track",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, lowered)

    def test_active_surfaces_do_not_advertise_legacy_task_env_method(self) -> None:
        legacy_method = "env" + "." + "task"
        legacy_broker_branch = "method == " + repr(legacy_method)
        legacy_client_call = "request_runtime_broker(" + repr(legacy_method)
        for path_text in self._git_ls_files("scripts", "tests", "framework", "buddyswitch", "tools"):
            path = ROOT / path_text
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path_text, token="legacy_method"):
                self.assertNotIn(legacy_method, text)
            with self.subTest(path=path_text, token="legacy_broker_branch"):
                self.assertNotIn(legacy_broker_branch, text)
            with self.subTest(path=path_text, token="legacy_client_call"):
                self.assertNotIn(legacy_client_call, text)

        env_tools = turn_runtime._build_env_tools_desc()
        task_manager = env_tools.get("task_manager")
        self.assertIsInstance(task_manager, dict)
        assert isinstance(task_manager, dict)
        self.assertEqual(task_manager.get("broker_method"), "env.tool")
        self.assertEqual(task_manager.get("command"), "python3 scripts/env/client.py task <operation>")

    def test_browser_evidence_issuance_uses_env_tool_surface(self) -> None:
        legacy_method = "issue_browser" + "_evidence"
        legacy_broker_branch = "method == " + repr(legacy_method)
        legacy_client_call = "request_runtime_broker(" + repr(legacy_method)
        for path_text in self._git_ls_files("scripts", "tests", "framework", "buddyswitch", "tools"):
            path = ROOT / path_text
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path_text, token="legacy_evidence_method"):
                self.assertNotIn(legacy_method, text)
            with self.subTest(path=path_text, token="legacy_evidence_broker_branch"):
                self.assertNotIn(legacy_broker_branch, text)
            with self.subTest(path=path_text, token="legacy_evidence_client_call"):
                self.assertNotIn(legacy_client_call, text)

        env_tools = turn_runtime._build_env_tools_desc()
        evidence_manager = env_tools.get("evidence_manager")
        self.assertIsInstance(evidence_manager, dict)
        assert isinstance(evidence_manager, dict)
        self.assertEqual(evidence_manager.get("broker_method"), "env.tool")
        self.assertEqual(evidence_manager.get("command"), "python3 scripts/env/client.py evidence <operation>")

    def test_phase8_active_surfaces_agree_on_env_tool_contract(self) -> None:
        env_tools = turn_runtime._build_env_tools_desc()
        expected_tool_names = {
            "artifact_manager": "artifact",
            "binding_manager": "binding",
            "context_manager": "context",
            "evidence_manager": "evidence",
            "handoff_manager": "handoff",
            "run_manager": "run",
            "task_manager": "task",
            "track_manager": "track",
        }
        self.assertEqual(set(env_tools), set(expected_tool_names))
        for manager_name, tool_name in expected_tool_names.items():
            with self.subTest(manager=manager_name):
                desc = env_tools[manager_name]
                self.assertEqual(desc["broker_method"], "env.tool")
                self.assertEqual(desc["envelope"], {"tool": tool_name, "action": "<action>", "args": "<object>"})
                self.assertIn("python3 scripts/env/client.py", desc["command"])

        active_contract_paths = self._active_runtime_contract_paths()
        active_contract_paths.extend(
            [
                ROOT / "buddyswitch" / "skills" / "shared" / "task-manager" / "SKILL.md",
                ROOT / "buddyswitch" / "skills" / "shared" / "track-manager" / "SKILL.md",
                ROOT / "buddyswitch" / "skills" / "shared" / "artifact-manager" / "SKILL.md",
            ]
        )
        for path in active_contract_paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env.tool", text)
                self.assertNotIn("env" + "." + "task", text)

    def test_phase8_retired_product_overlap_scripts_are_not_active_files(self) -> None:
        retired_product_scripts = (
            ROOT / "scripts" / ("env" + "_tasks.py"),
            ROOT / "scripts" / ("env" + "_tracks.py"),
            ROOT / "scripts" / ("env" + "_artifacts.py"),
        )
        for path in retired_product_scripts:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertFalse(path.exists(), msg=f"{path.relative_to(ROOT)} must not remain as an active product path")

        browser_wrapper = ROOT / "scripts" / "browser_evidence.py"
        self.assertTrue(browser_wrapper.exists())
        wrapper_text = browser_wrapper.read_text(encoding="utf-8")
        self.assertIn('"env.tool"', wrapper_text)
        self.assertNotIn("issue_browser" + "_evidence", wrapper_text)

    def test_context_tool_feedback_scope_does_not_touch_peripheral_systems(self) -> None:
        completed = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        changed_paths = set(completed.stdout.splitlines())
        forbidden_paths = {
            "scripts/serve_context_panel.py",
        }
        forbidden_prefixes = (
            "scripts/cleanup",
            "scripts/debug_objects",
            "scripts/skill_importer",
            "tools/launcher/assets/context-panel",
        )
        for path in sorted(changed_paths):
            with self.subTest(path=path):
                self.assertNotIn(path, forbidden_paths)
                self.assertFalse(any(path.startswith(prefix) for prefix in forbidden_prefixes))


if __name__ == "__main__":
    unittest.main()
