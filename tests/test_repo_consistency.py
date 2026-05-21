#!/usr/bin/env python3
"""Repository consistency checks for active track-page collaboration runtime."""

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

import env_store  # noqa: E402
import turn_runtime  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402

_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment", "request"}
_FORBIDDEN_RUNTIME_SURFACES = {
    "artifact_index",
    "artifact_search",
    "relation",
    "insight",
    "experiment",
    "roadmap",
    "review",
    "approval",
}


class RepoConsistencyTests(unittest.TestCase):
    _OLD_FLAG_PATTERNS = (
        "search open-browser --query",
        "search open_browser --query",
        "--engine",
        "--track-id",
        "--task-id",
        "--artifact-id",
        "--target-type",
        "--target-id",
    )

    def _scan(self, pattern: str) -> list[str]:
        targets = [
            "README.md",
            "AGENTS.md",
            "scripts",
            "buddyswitch",
            "tools/launcher/assets/buddies",
            "framework/contracts",
            "framework/schemas",
            "framework/console/app.js",
            "tests",
        ]
        completed = subprocess.run(
            ["rg", "-uuu", "-n", pattern, *targets, "-g", "!**/__pycache__/**", "-g", "!**/*.pyc"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        return [line for line in completed.stdout.splitlines() if line.strip()]

    def test_active_runtime_modules_do_not_import_env_store(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                r"(^|\\s)(import\\s+env_store|from\\s+env_store\\s+import)",
                "scripts/turn_runtime.py",
                "scripts/env/tools",
                "scripts/env/domain",
                "scripts/env/repos",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_env_store_module_is_runtime_root_compat_only(self) -> None:
        retired_api = (
            "create_track",
            "update_track",
            "create_task",
            "update_task",
            "create_artifact_revision",
            "update_artifact",
            "publish_track_material",
            "publish_track_proof",
            "append_track_update",
            "create_message",
            "create_comment",
            "list_tracks",
            "list_tasks",
            "list_artifacts",
            "get_track",
            "get_task",
            "get_artifact",
            "save_track",
            "save_task",
            "save_artifact",
        )
        for symbol in retired_api:
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(env_store, symbol), msg=f"env_store unexpectedly exposes {symbol}")

    def test_env_tool_surface_uses_track_page_actions(self) -> None:
        env_tools = turn_runtime._build_env_tools_desc()
        registry_tools = set(tool_catalog.supported_tools())
        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertEqual(set(env_tools), _EXPECTED_TOOLS)

        track_actions = set(tool_catalog.supported_actions("track"))
        self.assertEqual(
            track_actions,
            {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
        )
        artifact_actions = set(tool_catalog.supported_actions("artifact"))
        self.assertEqual(artifact_actions, {"list", "get", "create_revision", "update_metadata"})
        request_actions = set(tool_catalog.supported_actions("request"))
        self.assertEqual(request_actions, {"create", "list", "get", "accept", "block", "complete", "cancel"})

    def test_forbidden_runtime_surfaces_are_not_shipped(self) -> None:
        self.assertTrue(_FORBIDDEN_RUNTIME_SURFACES.isdisjoint(set(tool_catalog.supported_tools())))
        for tool in sorted(tool_catalog.supported_tools()):
            actions = set(tool_catalog.supported_actions(tool))
            with self.subTest(tool=tool):
                self.assertTrue(_FORBIDDEN_RUNTIME_SURFACES.isdisjoint(actions))

        tool_packages = {
            path.name
            for path in (ROOT / "scripts" / "env" / "tools").iterdir()
            if path.is_dir() and not path.name.startswith("_")
        }
        self.assertTrue(_FORBIDDEN_RUNTIME_SURFACES.isdisjoint(tool_packages))

        objects_root = ROOT / "buddyswitch" / "objects"
        object_dirs = {
            path.name
            for path in objects_root.iterdir()
            if path.is_dir()
        } if objects_root.exists() else set()
        self.assertTrue(_FORBIDDEN_RUNTIME_SURFACES.isdisjoint(object_dirs))

    def test_workspace_projection_contract_uses_track_page_shape(self) -> None:
        payload = json.loads((ROOT / "framework" / "contracts" / "workspace-projection.json").read_text(encoding="utf-8"))
        top = set(payload.get("top_level_key_order", []))
        self.assertIn("tracks", top)
        self.assertIn("tasks", top)
        self.assertIn("artifacts", top)
        self.assertNotIn("handoffs", top)

        track_keys = set(payload["view_shapes"]["track"]["key_order"])
        self.assertIn("outcome", track_keys)
        self.assertIn("state", track_keys)
        self.assertIn("health", track_keys)
        self.assertIn("shared_materials", track_keys)
        self.assertNotIn("task_ids", track_keys)
        self.assertNotIn("tasks", track_keys)

        task_keys = set(payload["view_shapes"]["task"]["key_order"])
        self.assertNotIn("artifact_ids", task_keys)
        self.assertNotIn("artifact" + "_slots", task_keys)

        artifact_keys = set(payload["view_shapes"]["artifact"]["key_order"])
        self.assertIn("published_to_track", artifact_keys)
        self.assertNotIn("task_id", artifact_keys)

    def test_role_contracts_teach_direct_track_material_path(self) -> None:
        for name in ("pm", "design", "dev", "market", "test"):
            path = ROOT / "framework" / "contracts" / f"{name}.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(contract=name):
                self.assertIn("track.open", text)
                self.assertNotIn("track" + ".join", text)
                self.assertNotIn("attach" + "_task", text)
                self.assertNotIn("detach" + "_task", text)
                if name == "pm":
                    self.assertIn("artifact.create_revision", text)
                    self.assertIn("track.add_material", text)
                    self.assertIn("track.add_proof", text)
                    self.assertNotIn("published_to_track", text)

    def test_runtime_buddy_agents_use_payload_env_client_guidance(self) -> None:
        buddies = ("market", "pm", "design", "dev", "test")
        for buddy in buddies:
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(buddy=buddy):
                self.assertIn("context summarize --payload '{}'", text)
                self.assertIn("context get --payload '{}'", text)
                self.assertIn("track open --payload '{\"track_id\":\"<track-id>\"}'", text)
                self.assertIn("task get --payload '{\"task_id\":\"<task-id>\"}'", text)
                self.assertIn("artifact get --payload '{\"artifact_id\":\"<artifact-id>\"}'", text)
                self.assertIn("request get --payload '{\"request_id\":\"<request-id>\"}'", text)
                self.assertIn("search status --payload '{}'", text)
                self.assertIn(
                    "search open-browser --payload '{\"query\":\"<query>\",\"engine\":\"google\"}'",
                    text,
                )
                if buddy == "pm":
                    self.assertIn("comment resolve --payload '{\"comment_id\":\"<comment-id>\",\"resolution_summary\":\"<summary>\"}'", text)
                for pattern in self._OLD_FLAG_PATTERNS:
                    self.assertNotIn(pattern, text)
                self.assertNotIn("track join", text)
                self.assertNotIn("attach" + "-task", text)
                self.assertNotIn("detach" + "-task", text)

    def test_active_cli_guidance_has_no_old_env_client_flags(self) -> None:
        targets = [
            "buddyswitch/skills",
            "tools/launcher/assets/buddies",
            "scripts/env/client.py",
            "tests/test_runtime_skills.py",
            "tests/test_repo_consistency.py",
        ]
        completed = subprocess.run(
            [
                "rg",
                "-uuu",
                "-n",
                "-e",
                "search open-browser --query",
                "-e",
                "search open_browser --query",
                "-e",
                "--engine",
                "-e",
                "--track-id",
                "-e",
                "--task-id",
                "-e",
                "--artifact-id",
                "-e",
                "--target-type",
                "-e",
                "--target-id",
                *targets,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        allowed_hits: list[str] = []
        for line in hits:
            lower = line.lower()
            if line.startswith("tests/test_runtime_skills.py:"):
                allowed_hits.append(line)
                continue
            if line.startswith("tests/test_repo_consistency.py:"):
                allowed_hits.append(line)
                continue
        disallowed = [line for line in hits if line not in allowed_hits]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_invalid_old_env_client_flags_fail(self) -> None:
        old_commands = [
            ["python3", "scripts/env/client.py", "search", "open-browser", "--query", "x", "--engine", "google"],
            ["python3", "scripts/env/client.py", "track", "open", "--track-id", "track-alpha"],
            ["python3", "scripts/env/client.py", "task", "get", "--task-id", "task-alpha"],
            ["python3", "scripts/env/client.py", "artifact", "get", "--artifact-id", "art-alpha"],
            [
                "python3",
                "scripts/env/client.py",
                "comment",
                "list",
                "--target-type",
                "track",
                "--target-id",
                "track-alpha",
            ],
        ]
        for command in old_commands:
            with self.subTest(command=" ".join(command)):
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)

    def test_role_rebuild_residue_scan(self) -> None:
        pattern_1 = (
            "track\\." + "join"
            + "|attach" + "_task"
            + "|detach" + "_task"
            + "|attach" + "-task"
            + "|detach" + "-task"
            + "|track" + "_task"
            + "|readable_by_current" + "_buddy"
        )
        pattern_2 = (
            "track\\." + "task_ids"
            + "|artifact\\." + "task_id"
            + "|artifact" + "_slots"
            + "|source_" + "task_id"
        )
        pattern_3 = (
            "current-task" + "-id"
            + "|task_id" + "_scope"
            + "|[Cc]ompatibility" + " facade"
        )
        hits_1 = self._scan(pattern_1)
        hits_2 = self._scan(pattern_2)
        hits_3 = self._scan(pattern_3)
        hits = hits_1 + hits_2 + hits_3
        allowed: list[str] = []
        for line in hits:
            lower = line.lower()
            if "design-handoff" in lower:
                allowed.append(line)
                continue
            if "test_role_rebuild_residue_scan" in lower:
                allowed.append(line)
                continue
            if line.startswith("tests/"):
                allowed.append(line)
                continue
            if "/docs/spec/" in lower or "/docs/memo/" in lower:
                allowed.append(line)
                continue
            if line.startswith("scripts/artifact_selection.py:"):
                allowed.append(line)
                continue
            if line.startswith("scripts/workspace_data.py:"):
                allowed.append(line)
                continue
        disallowed = [line for line in hits if line not in allowed]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_track_artifact_publication_residue_scan(self) -> None:
        pattern = (
            "kind=prd"
            + "|content\\.prd"
            + "|track\\.join"
            + "|attach_task"
            + "|detach_task"
            + "|attach-task"
            + "|detach-task"
        )
        hits = self._scan(pattern)
        disallowed: list[str] = []
        for line in hits:
            lower = line.lower()
            if line.startswith("tests/"):
                continue
            if "/docs/spec/" in lower or "/docs/memo/" in lower or "/docs/bitter/" in lower:
                continue
            disallowed.append(line)
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_tool_semantic_contract_has_no_transition_residue(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                (
                    "schema " + "card"
                    + "|semantic " + "card"
                    + "|compatibility " + "adapter"
                    + "|dual " + "catalog"
                    + "|fallback " + "registry"
                    + "|minimal_" + "payload"
                ),
                "scripts",
                "tests",
                "buddyswitch",
                "tools",
                "README.md",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        disallowed = [line for line in hits if not line.startswith("tests/")]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

        per_tool_completed = subprocess.run(
            [
                "rg",
                "-n",
                "track\\.now|artifact\\.source_refs|comment\\.mentions|buddybox\\.list",
                "scripts/env/tool_runtime",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(per_tool_completed.returncode, {0, 1}, msg=per_tool_completed.stderr)
        per_tool_hits = [line for line in per_tool_completed.stdout.splitlines() if line.strip()]
        self.assertEqual(per_tool_hits, [], msg="\n".join(per_tool_hits))

    def test_active_cli_guidance_has_no_payload_file_route(self) -> None:
        targets = [
            "AGENTS.md",
            "buddyswitch/skills",
            "framework/contracts",
            "tools/launcher/assets/buddies",
            "scripts/env/client.py",
        ]
        completed = subprocess.run(
            [
                "rg",
                "-uuu",
                "-n",
                "payload file|--payload /tmp|--payload <json-file>|--payload <file>|PAYLOAD_JSON_FILE",
                *targets,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables(self) -> None:
        targets = [
            "buddyswitch/skills",
            "framework/contracts",
            "tools/launcher/assets/buddies",
        ]
        legacy_runtime_tool_path = "scripts/env/tools/.*/"
        legacy_contract_file = "contract" + "\\.py"
        legacy_semantics_file = "semantics" + "\\.py"
        legacy_handlers_file = "handlers" + "\\.py"
        legacy_service_file = "service" + "\\.py"
        completed = subprocess.run(
            [
                "rg",
                "-uuu",
                "-n",
                "--glob",
                "*.md",
                (
                    "payload_fields"
                    + "|action_semantics"
                    + "|operation_semantics"
                    + "|" + ("TOOL" + "_SPEC")
                    + "|" + ("ACTION" + "_SEMANTICS")
                    + "|" + ("HANDLER" + "_SPECS")
                    + "|" + legacy_runtime_tool_path + legacy_contract_file
                    + "|" + legacy_runtime_tool_path + legacy_semantics_file
                    + "|" + legacy_runtime_tool_path + legacy_handlers_file
                    + "|" + legacy_runtime_tool_path + legacy_service_file
                    + "|\\|\\s*tool\\s*\\|\\s*action\\s*\\|\\s*payload"
                    + "|\\|\\s*action\\s*\\|\\s*payload"
                    + "|\\*\\*payload:\\*\\*"
                    + "|\\*\\*returns:\\*\\*"
                    + "|##\\s*payload\\s+examples"
                    + "|##\\s*operations"
                    + "|##\\s*`[^`]+`\\s+payload"
                ),
                *targets,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_parallel_modular_architecture_memo_documents_current_skill_tool_boundary(self) -> None:
        path = ROOT / "docs/memo/buddyswitch-parallel-modular-architecture.md"
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()

        self.assertIn("## skill / tool contract 衔接规则", lowered)
        self.assertIn("context.get.tool_catalog", text)
        self.assertIn("python3 scripts/turn_runtime.py status", text)
        self.assertIn("scripts/env/tool_runtime/definition.py", text)
        self.assertIn("scripts/env/tool_runtime/registry.py", text)
        self.assertIn("scripts/env/tools/<tool>/tool.py", text)
        self.assertIn("scripts/env/tools/<tool>/_impl.py", text)
        self.assertIn("skill 通过 runtime discovery 消费能力，不复制能力", lowered)
        self.assertNotIn("## 第一阶段落地", text)
        self.assertIn("## 已落地基础", text)
        self.assertIn("workflow engine", lowered)
        self.assertIn("plugin system", lowered)
        self.assertIn("event bus", lowered)

    def test_readme_runtime_sources_match_per_tool_runtime(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("scripts/env/tool_runtime/definition.py", text)
        self.assertIn("scripts/env/tool_runtime/context.py", text)
        self.assertIn("scripts/env/tool_runtime/results.py", text)
        self.assertIn("scripts/env/tool_runtime/registry.py", text)
        self.assertIn("scripts/env/tools/<tool>/tool.py", text)
        self.assertIn("scripts/env/tools/<tool>/_impl.py", text)

        legacy_catalog_path = "scripts/env/tools/" + "catalog.py"
        legacy_contract_path = "scripts/env/tools/<tool>/" + "contract.py"
        legacy_semantics_path = "scripts/env/tools/<tool>/" + "semantics.py"
        legacy_cli_path = "scripts/env/tools/<tool>/" + "cli.py"
        legacy_handlers_path = "scripts/env/tools/<tool>/" + "handlers.py"
        legacy_service_path = "scripts/env/tools/<tool>/" + "service.py"
        self.assertNotIn(legacy_catalog_path, text)
        self.assertNotIn(legacy_contract_path, text)
        self.assertNotIn(legacy_semantics_path, text)
        self.assertNotIn(legacy_cli_path, text)
        self.assertNotIn(legacy_handlers_path, text)
        self.assertNotIn(legacy_service_path, text)

    def test_contracts_and_buddy_agents_point_to_runtime_discovery(self) -> None:
        for name in ("pm", "design", "dev", "market", "test"):
            path = ROOT / "framework" / "contracts" / f"{name}.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(contract=name):
                self.assertIn("context summarize", text)
                self.assertIn("context get", text)

        for buddy in ("market", "pm", "design", "dev", "test"):
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(buddy=buddy):
                self.assertIn("context summarize", text)
                self.assertIn("context get", text)


if __name__ == "__main__":
    unittest.main()
