#!/usr/bin/env python3
"""Runless repository consistency checks for active product surfaces."""

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
import turn_runtime  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402

_RETIRED_BUDDYBOX_FILES_FIELD = "buddybox_" + "files"
_RETIRED_BUDDYBOX_PATHS_FIELD = "buddybox_" + "paths"
_RETIRED_BUDDYBOX_CONTENT_ROOT = "buddyswitch/content/" + "buddybox"


class RepoConsistencyTests(unittest.TestCase):
    def _scan(self, pattern: str) -> list[str]:
        scopes = ["scripts", "buddyswitch", "tools", "framework", "README.md", "AGENTS.md"]
        completed = subprocess.run(
            ["rg", "-n", pattern, *scopes],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        return [line for line in completed.stdout.splitlines() if line.strip()]

    def _scan_with_allowlist(self, pattern: str, *, allowed: tuple[str, ...]) -> list[str]:
        hits = self._scan(pattern)
        return [line for line in hits if not any(token in line for token in allowed)]

    def _git_worktree_entries(self) -> dict[Path, dict[str, str]]:
        completed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        entries: dict[Path, dict[str, str]] = {}
        block: dict[str, str] = {}
        for raw_line in [*completed.stdout.splitlines(), ""]:
            line = raw_line.strip()
            if not line:
                if "worktree" in block:
                    entries[Path(block["worktree"]).resolve()] = dict(block)
                block = {}
                continue
            key, _, value = raw_line.partition(" ")
            block[key] = value
        return entries

    def test_worktree_isolated_for_dev_worktree(self) -> None:
        current_root = ROOT.resolve()
        worktrees = self._git_worktree_entries()
        self.assertIn(current_root, worktrees)
        self.assertIn(".worktrees", current_root.parts)

        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        self.assertNotIn(current_branch, {"", "HEAD", "main"})
        self.assertEqual(current_root.name, current_branch)
        self.assertEqual(worktrees[current_root].get("branch"), f"refs/heads/{current_branch}")

        common_git_dir = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
        ).resolve()
        primary_checkout_root = common_git_dir.parent
        self.assertIn(primary_checkout_root, worktrees)
        self.assertNotEqual(current_root, primary_checkout_root)

    def test_runless_architecture_residue_scan(self) -> None:
        disallowed_1 = self._scan_with_allowlist(
            r"run\.commit|run\.validate_result|run\.get_receipt|run\.get_raw|binding\.",
            allowed=(),
        )
        self.assertEqual(disallowed_1, [], msg="\n".join(disallowed_1))

        # Allow explicit old-field rejection text in runtime validators only.
        disallowed_2 = self._scan_with_allowlist(
            r"source_run_id|run_ids|latest_run_id|current_task_id|current_track_id",
            allowed=(
                "scripts/env_store.py",
                "scripts/env/services/artifacts.py",
                "scripts/env/services/handoffs.py",
                "scripts/env/services/tasks.py",
            ),
        )
        self.assertEqual(disallowed_2, [], msg="\n".join(disallowed_2))

        disallowed_3 = self._scan_with_allowlist(
            r"run_envelope|persist_command_hint|prepare-context|buddyswitch/content/runs|runs/raw",
            allowed=(
                "deprecated prepare/persist",
                "runless mode",
                "Retired in runless mode",
            ),
        )
        self.assertEqual(disallowed_3, [], msg="\n".join(disallowed_3))

    def test_manifest_skill_rows_are_id_and_path_only(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        for row in manifest.get("skills", []):
            self.assertIsInstance(row, dict)
            assert isinstance(row, dict)
            self.assertEqual(set(row.keys()), {"id", "path"})

    def test_manifest_buddy_permissions_are_runless(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        for buddy in manifest.get("buddies", []):
            self.assertIsInstance(buddy, dict)
            assert isinstance(buddy, dict)
            permissions = set(buddy.get("permissions", []))
            self.assertNotIn("run.commit", permissions)
            self.assertNotIn("binding.get", permissions)
            self.assertFalse(any(item.startswith("memory.") for item in permissions))
            self.assertIn("buddybox.read", permissions)
            self.assertIn("context.read", permissions)

    def test_active_runtime_surface_excludes_memory(self) -> None:
        pattern = (
            r"memory|memories|memory_ids|memory_kind|MEMORY_|"
            r"create_memory|get_memory|list_memories|update_memory|memory\."
        )
        scopes = [
            "README.md",
            "scripts",
            "framework",
            "buddyswitch",
            "tools",
            "projects/app/README.md",
        ]
        completed = subprocess.run(
            [
                "rg",
                "-n",
                pattern,
                *scopes,
                "-g",
                "!docs/memo/**",
                "-g",
                "!docs/spec/2026-05-14-*",
                "-g",
                "!docs/spec/2026-05-15-memory-removal-*",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_memory_lifecycle_tests_are_removed(self) -> None:
        self.assertFalse((ROOT / "tests" / "test_memory_env_tool.py").exists())
        collected = subprocess.run(
            ["python3", "-m", "pytest", "--collect-only", "-q", "tests"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(collected.returncode, 0, msg=collected.stdout + collected.stderr)
        self.assertNotIn("memory_owner_lifecycle", collected.stdout)

    def test_legacy_run_contract_and_run_tool_are_removed(self) -> None:
        self.assertFalse((ROOT / "framework" / "contracts" / "persist-buddy-run.json").exists())
        self.assertFalse((ROOT / "buddyswitch" / "skills" / "shared" / "run-tool" / "SKILL.md").exists())

    def test_turn_runtime_is_runless_runtime_support(self) -> None:
        text = (ROOT / "scripts" / "turn_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("def persist_buddy_run", text)
        self.assertNotIn("def prepare_turn_context", text)
        self.assertNotIn("run_envelope", text)
        self.assertIn("RuntimeFeedbackError", text)

    def test_env_tool_surface_is_runtime_visible_and_runless(self) -> None:
        env_tools = turn_runtime._build_env_tools_desc()
        self.assertEqual(set(env_tools), {row["tool"] for row in tool_contracts.TOOL_REGISTRY})
        self.assertEqual(
            set(env_tools),
            {"task", "track", "artifact", "handoff", "buddybox", "context", "evidence", "search"},
        )
        self.assertNotIn("run", env_tools)
        self.assertNotIn("binding", env_tools)
        self.assertEqual(tool_contracts.semantic_contract_errors(), [])
        compact_affordances = tool_contracts.compact_tool_affordances()
        self.assertEqual(set(compact_affordances), {"buddybox", "artifact"})
        runtime_env_tools = turn_runtime._build_env_tools_desc()
        self.assertIn("buddybox", runtime_env_tools)
        self.assertIn("artifact", runtime_env_tools)
        for tool, row in env_tools.items():
            with self.subTest(tool=tool):
                self.assertEqual(row.get("broker_method"), "env.tool")
                self.assertIn("python3 scripts/env/client.py", str(row.get("command", "")))
        affordances = tool_contracts.compact_tool_affordances()
        self.assertEqual(set(affordances), {"buddybox", "artifact"})
        self.assertIn("action_semantics", env_tools["buddybox"])

    def test_active_runtime_feedback_points_to_current_tool_discovery_surfaces(self) -> None:
        retired_hits = self._scan(r"prepare\.runtime_context\.env_tools")
        self.assertEqual(retired_hits, [], msg="\n".join(retired_hits))

        router_text = (ROOT / "scripts" / "env" / "tools" / "router.py").read_text(encoding="utf-8")
        for token in (
            "context.get.tool_catalog",
            "context.summarize.tool_affordances",
            "scripts/turn_runtime.py status",
        ):
            with self.subTest(token=token):
                self.assertIn(token, router_text)

    def test_active_docs_teach_runless_flow(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        runtime_doc = (ROOT / "framework" / "docs" / "turn-runtime-spec.md").read_text(encoding="utf-8")
        self.assertIn("runless", readme.lower())
        self.assertIn("context", readme.lower())
        self.assertIn("env.tool", runtime_doc)
        self.assertNotIn("persist-buddy-run", readme)

    def test_runtime_broker_runbook_is_runless(self) -> None:
        runbook = (ROOT / "framework" / "docs" / "runtime-broker-v2-runbook.md").read_text(encoding="utf-8")
        for token in ("env.tool", "ping", "status"):
            self.assertIn(token, runbook)
        self.assertNotIn("prepare`: no blind retry", runbook)
        self.assertNotIn("E_RUNTIME_IDEMPOTENCY_REQUIRED", runbook)
        self.assertNotIn("E_RUNTIME_PERSIST_CONFLICT", runbook)

    def test_shared_skills_are_runless(self) -> None:
        shared = [
            ROOT / "buddyswitch" / "skills" / "shared" / "task-tool" / "SKILL.md",
            ROOT / "buddyswitch" / "skills" / "shared" / "track-tool" / "SKILL.md",
            ROOT / "buddyswitch" / "skills" / "shared" / "artifact-tool" / "SKILL.md",
            ROOT / "buddyswitch" / "skills" / "shared" / "handoff-tool" / "SKILL.md",
            ROOT / "buddyswitch" / "skills" / "shared" / "buddybox-tool" / "SKILL.md",
        ]
        for path in shared:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("buddy-run commit", lowered)
                self.assertNotIn("turn_runtime.py persist", lowered)
                self.assertNotIn("prepare.runtime_context", lowered)
                self.assertIn("env.tool", lowered)

    def test_role_contracts_keep_buddybox_guidance_short_and_role_specific(self) -> None:
        expectations = {
            "pm": (
                "pm-owned private local drafts",
                "lightweight prototypes",
                "artifact when content must become product-readable",
            ),
            "design": (
                "private local prototypes",
                "exports",
                "artifact for design handoffs or prototype briefs",
            ),
            "dev": (
                "private logs",
                "generated files",
                "binary outputs",
                "artifact for implementation reports",
            ),
            "test": (
                "private logs",
                "raw evidence files",
                "artifact for pass/fail reports",
            ),
            "market": (
                "private research exports",
                "logs",
                "artifact for market deliverables",
            ),
        }
        for buddy, tokens in expectations.items():
            text = (ROOT / "framework" / "contracts" / f"{buddy}.md").read_text(encoding="utf-8").lower()
            with self.subTest(buddy=buddy):
                for token in tokens:
                    self.assertIn(token, text)
                for forbidden in (
                    "payload_fields",
                    "action_semantics",
                    "prepare.runtime_context",
                    "always create artifact",
                ):
                    self.assertNotIn(forbidden, text)

    def test_buddy_agents_contain_direct_id_artifact_read_boundary(self) -> None:
        buddy_assets = sorted((ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"))
        self.assertEqual(len(buddy_assets), 5)
        guard = "Do not claim artifact content was read unless `artifact.get` returned the full body for that artifact id."
        for path in buddy_assets:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("python3 scripts/env/client.py context summarize", text)
                self.assertIn("If you see a `track_id`", text)
                self.assertIn("If you see a `task_id`", text)
                self.assertIn("If you see an `artifact_id`", text)
                self.assertIn(guard, text)
                self.assertIn("do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly", text.lower())
                self.assertNotIn("scripts/turn_runtime.py prepare", text)
                self.assertNotIn("scripts/turn_runtime.py persist", text)

    def test_search_tool_visible_surface_is_projected(self) -> None:
        buddy_assets = sorted((ROOT / "tools" / "launcher" / "assets" / "buddies").rglob("AGENTS.md"))
        for path in buddy_assets:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("env_tools.search", text)
                self.assertIn("Native Codex `web_search` is unavailable", text)
                self.assertIn("scripts/env/client.py search status", text)

    def test_active_store_has_no_legacy_repository_layer(self) -> None:
        active_paths = (
            ROOT / "scripts" / "env_store.py",
            ROOT / "scripts" / "runtime_store" / "__init__.py",
            ROOT / "scripts" / "runtime_store" / "projections.py",
        )
        for path in active_paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("_legacy_", text)
        self.assertFalse((ROOT / "scripts" / "runtime_store" / "repositories.py").exists())

    def test_workspace_projection_contract_is_runless(self) -> None:
        payload = json.loads((ROOT / "framework" / "contracts" / "workspace-projection.json").read_text(encoding="utf-8"))
        self.assertEqual(payload.get("contract_id"), "workspace-projection")
        top = set(payload.get("top_level_key_order", []))
        self.assertIn("handoffs", top)
        self.assertNotIn("memories", top)
        self.assertNotIn(_RETIRED_BUDDYBOX_FILES_FIELD, top)
        self.assertNotIn("content_root", top)
        self.assertNotIn("run_audits", top)

    def test_legacy_prepare_persist_entrypoints_are_absent(self) -> None:
        legacy_prepare = (
            "prepare_turn_context"
            "_request"
        )
        legacy_persist_key = (
            "make_persist_idempotency"
            "_key"
        )
        prepare_subparser = (
            r"\bprepare\b.*"
            r"subparsers"
        )
        persist_subparser = (
            r"\bpersist\b.*"
            r"subparsers"
        )
        pattern = "|".join((legacy_prepare, legacy_persist_key, prepare_subparser, persist_subparser))
        completed = subprocess.run(
            ["rg", "-n", pattern, "scripts", "tests", "framework"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_no_hardcoded_intent_to_buddybox_phrase_routing(self) -> None:
        pattern = "|".join(
            (
                "prototype means",
                "quickly build means",
                "simple page prototype means",
                "route prototype to buddybox",
                "hardcoded trigger",
                "always create artifact",
            )
        )
        completed = subprocess.run(
            [
                "rg",
                "-n",
                pattern,
                "README.md",
                "AGENTS.md",
                "scripts",
                "framework",
                "buddyswitch",
                "tools",
                "-g",
                "!docs/memo/**",
                "-g",
                "!docs/spec/**",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_retired_buddybox_tokens_are_absent_from_active_surfaces(self) -> None:
        pattern = "|".join(
            (
                "BUDDYBOX_CONTENT_" + "DIR",
                _RETIRED_BUDDYBOX_CONTENT_ROOT,
                _RETIRED_BUDDYBOX_FILES_FIELD,
                _RETIRED_BUDDYBOX_PATHS_FIELD,
                "durable buddy-" + "owned",
                "readable buddybox " + "scope",
            )
        )
        completed = subprocess.run(
            [
                "rg",
                "-n",
                pattern,
                "README.md",
                "AGENTS.md",
                "scripts",
                "framework",
                "buddyswitch",
                "tools",
                "tests",
                "-g",
                "!docs/memo/**",
                "-g",
                "!docs/spec/**",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))


if __name__ == "__main__":
    unittest.main()
