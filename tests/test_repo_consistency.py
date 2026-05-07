#!/usr/bin/env python3
"""Repo-level consistency checks for buddy-run persistence architecture."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402


class RepoConsistencyTests(unittest.TestCase):
    def _git_ls_files(self, *paths: str) -> list[str]:
        completed = subprocess.run(
            ["git", "ls-files", "--", *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return [line for line in completed.stdout.splitlines() if line]

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

    def test_console_boundary_uses_workspace_api(self) -> None:
        app_js = (ROOT / "framework" / "console" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/workspace", app_js)
        self.assertNotIn("env_store", app_js)
        self.assertNotIn("turn_runtime", app_js)
        self.assertNotIn("runtime_store.repositories", app_js)

    def test_browser_ui_does_not_import_runtime_internals(self) -> None:
        ui_surfaces = (
            ROOT / "framework" / "console" / "app.js",
            ROOT / "projects" / "app" / "main.js",
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
            ROOT / "buddyswitch" / "skills" / "pm" / "track-manager" / "assets" / "track-operation-template.md",
            ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "assets" / "design-handoff-template.md",
            ROOT / "buddyswitch" / "skills" / "dev" / "implement-task" / "assets" / "implementation-report-template.md",
            ROOT / "buddyswitch" / "skills" / "test" / "smoke-test" / "assets" / "test-report-template.md",
            ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "assets" / "research-report-template.md",
        ]
        for path in required_templates:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists())

    def test_buddy_prompt_assets_exist(self) -> None:
        for buddy in ("design", "dev", "market", "pm", "test"):
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            with self.subTest(buddy=buddy):
                self.assertTrue(path.exists())
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# BuddySwitch Runtime Workspace\n"))

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
                "market-landing-page-brief",
            ],
        )
        self.assertEqual(buddies["pm"]["artifact_kinds"], ["prd", "pm-decision", "track-note"])
        self.assertEqual(buddies["design"]["artifact_kinds"], ["design-handoff", "prototype-brief"])
        self.assertEqual(buddies["dev"]["artifact_kinds"], ["implementation-report", "skill-import-report"])
        self.assertEqual(buddies["test"]["artifact_kinds"], ["smoke-test", "test-report"])

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

    def test_buddy_agent_docs_do_not_reference_legacy_persist_api(self) -> None:
        for agents_md in (ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"):
            with self.subTest(doc=str(agents_md.relative_to(ROOT))):
                text = agents_md.read_text(encoding="utf-8")
                self.assertNotIn("persist --skill-id", text)
                self.assertIn("persist --context", text)
                self.assertIn("--result", text)


if __name__ == "__main__":
    unittest.main()
