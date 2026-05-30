#!/usr/bin/env python3
"""Repository consistency checks for active track-page collaboration runtime."""

from __future__ import annotations

import re
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

_EXPECTED_TOOLS = {"task", "track", "artifact", "context", "evidence", "search", "message", "comment", "request"}
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
_DOC_SPEC_CONTEXT_MARKERS = (
    "alignment",
    "appendix",
    "code-implementation-plan",
    "completion-implementation-plan",
    "development-plan",
    "implementation-plan",
    "objective",
    "parallel-agent-execution-plan",
    "remove-" + "dash" + "board-and-skill-create",
    "scope",
    "task-split",
    "test-plan",
)


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

    @staticmethod
    def _is_docs_spec_context_hit(line: str) -> bool:
        path_text, _sep, _rest = line.partition(":")
        if not path_text.startswith("docs/spec/"):
            return False
        name = Path(path_text).name
        return any(marker in name for marker in _DOC_SPEC_CONTEXT_MARKERS)

    @staticmethod
    def _retired_buddybox_host_path_tokens() -> tuple[str, ...]:
        return (
            " ".join(("buddybox", "write", "--payload")),
            ".".join(("buddybox", "import_file")),
            "_".join(("source", "buddybox", "logical", "name")),
            "_".join(("write", "private", "text")),
            "_".join(("write", "private", "binary")),
            " ".join(("address", "them", "only", "through", "buddybox", "env", "tools")),
        )

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

    def test_removed_visual_panel_and_import_surfaces_are_absent(self) -> None:
        panel_server = "_".join(("serve", "context", "panel"))
        projection_contract = "-".join(("workspace", "projection"))
        console_dir = "/".join(("framework", "console"))
        importer_dir = "-".join(("skill", "creator", "importer"))
        importer_module = "_".join(("skill", "creator", "importer"))
        fixture_dir = "-".join(("community", "skills"))
        console_contract_test = "_".join(("console", "app", "contract"))
        parallel_contracts_test = "_".join(("parallel", "contracts"))
        removed_paths = [
            f"scripts/{panel_server}.py",
            console_dir,
            f"framework/contracts/{projection_contract}.json",
            "scripts/workspace_data.py",
            "scripts/runtime_store/projections.py",
            f"scripts/{importer_module}.py",
            f"buddyswitch/skills/dev/{importer_dir}",
            f"tests/test_{console_contract_test}.py",
            f"tests/test_{parallel_contracts_test}.py",
            f"tests/test_{importer_module}.py",
            f"tests/fixtures/{fixture_dir}/dev-summary",
        ]
        for relative in removed_paths:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists())

    def test_removed_visual_panel_and_import_names_are_not_referenced(self) -> None:
        forbidden = (
            "_".join(("serve", "context", "panel")),
            " ".join(("Context", "Panel")),
            "-".join(("workspace", "projection")),
            "/".join(("framework", "console")),
            "_".join(("skill", "creator", "importer")),
            "-".join(("skill", "creator", "importer")),
            "-".join(("community", "skills")),
        )
        scan_targets = [
            "README.md",
            "AGENTS.md",
            "scripts",
            "buddyswitch",
            "tools",
            "framework",
            "tests",
        ]
        for token in forbidden:
            completed = subprocess.run(
                ["rg", "-n", "-i", token, *scan_targets, "-g", "!**/__pycache__/**", "-g", "!**/*.pyc"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
            self.assertEqual(completed.stdout.strip(), "", msg=f"{token}\n{completed.stdout}")

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
        self.assertEqual(
            artifact_actions,
            {"list", "get", "create_revision", "update_metadata", "attach_file", "list_attachments", "get_attachment"},
        )
        request_actions = set(tool_catalog.supported_actions("request"))
        self.assertEqual(request_actions, {"create", "list", "get", "accept", "block", "complete", "cancel"})

    def test_buddybox_env_tool_package_is_removed(self) -> None:
        self.assertFalse((ROOT / "scripts" / "env" / "tools" / "buddybox").exists())
        self.assertNotIn("buddybox", tool_catalog.supported_tools())

    def test_live_guidance_uses_direct_buddybox_directory_not_env_tool_payloads(self) -> None:
        paths = [
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "framework" / "contracts",
            ROOT / "buddyswitch" / "skills",
        ]
        chunks: list[str] = []
        for root in paths:
            files = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
            for path in files:
                if path.suffix not in {".md", ".toml"}:
                    continue
                chunks.append(path.read_text(encoding="utf-8").lower())
        text = "\n".join(chunks)
        for forbidden in self._retired_buddybox_host_path_tokens():
            self.assertNotIn(forbidden, text)
        self.assertIn("buddyswitch_buddybox_dir", text)
        self.assertIn("workspace/buddybox", text)

    def test_registry_semantic_projections_are_generated_from_definitions(self) -> None:
        desc = tool_catalog.env_tools_description()
        operation_semantics = tool_catalog.operation_semantics()
        compact = tool_catalog.compact_tool_affordances()

        for tool in sorted(tool_catalog.supported_tools()):
            definition = tool_catalog.get_definition(tool)
            with self.subTest(tool=tool):
                self.assertEqual(desc[tool]["object_model"], definition.object_model)
                self.assertEqual(compact[tool]["object_model"], definition.object_model)
                self.assertNotIn("input_schemas", compact[tool])
                self.assertNotIn("payload_fields", compact[tool])
                self.assertNotIn("action_semantics", compact[tool])
            for action in definition.actions:
                key = f"{tool}.{action.name}"
                semantic = desc[tool]["action_semantics"][action.name]
                operation = operation_semantics[key]
                with self.subTest(action=key):
                    self.assertEqual(semantic["visibility"], action.visibility)
                    self.assertEqual(semantic["durability"], action.durability)
                    self.assertEqual(semantic["result_content_level"], action.result_content_level)
                    self.assertEqual(semantic["success_means"], action.success_effect)
                    self.assertEqual(semantic["failure_state_guarantee"], action.failure_state_guarantee)
                    self.assertEqual(semantic["side_effects"]["reads"], list(action.reads))
                    self.assertEqual(semantic["side_effects"]["writes"], list(action.writes))
                    self.assertEqual(semantic["side_effects"]["does_not_write"], list(action.does_not_write))
                    self.assertEqual(operation["reads"], list(action.reads))
                    self.assertEqual(operation["writes"], list(action.writes))
                    self.assertEqual(operation["does_not_write"], list(action.does_not_write))

    def test_env_manifest_has_no_retired_acl_rows(self) -> None:
        completed = subprocess.run(
            ["rg", "-n", r"permissions = \[", "buddyswitch/manifest.toml"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")

    def test_active_runtime_has_no_retired_manifest_acl_references(self) -> None:
        retired_acl_pattern = "buddy_" + "permissions|object_" + "permissions|manual_debug_" + "apis"
        completed = subprocess.run(
            ["rg", "-n", retired_acl_pattern, "scripts", "tests", "buddyswitch"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")

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

    def test_no_project_or_source_write_env_tool_is_shipped(self) -> None:
        forbidden_tools = {"project", "dev_env", "source", "filesystem", "workspace_write"}
        self.assertTrue(forbidden_tools.isdisjoint(set(tool_catalog.supported_tools())))

        tool_packages = {
            path.name
            for path in (ROOT / "scripts" / "env" / "tools").iterdir()
            if path.is_dir() and not path.name.startswith("_")
        }
        self.assertTrue(forbidden_tools.isdisjoint(tool_packages))

        forbidden_actions = {"apply_patch", "write_file", "delete_file", "configure_project"}
        for tool in tool_catalog.supported_tools():
            with self.subTest(tool=tool):
                self.assertTrue(forbidden_actions.isdisjoint(set(tool_catalog.supported_actions(tool))))

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
                self.assertIn("prefer native buddyswitch env mcp tools", text)
                self.assertIn("authoritative fallback runtime tool list", text)
                self.assertIn("runtime tool examples include", text)
                self.assertIn("context summarize --payload '{}'", text)
                self.assertIn("context get --payload '{}'", text)
                self.assertIn("track open --payload '{\"track_id\":\"<track-id>\"}'", text)
                self.assertIn("task current --payload '{\"history_limit\":8}'", text)
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
                self.assertNotIn("use explicit ids and env tools (`", text)

    def test_active_env_client_examples_match_runtime_registry(self) -> None:
        targets = [
            ROOT / "tools" / "launcher" / "assets" / "buddies",
            ROOT / "buddyswitch" / "skills",
            ROOT / "framework" / "contracts",
            ROOT / "README.md",
        ]
        pattern = re.compile(r"python3\s+scripts/env/client\.py\s+([a-z][a-z0-9_]*)\s+([a-z][a-z0-9_-]*)")
        violations: list[str] = []

        for target in targets:
            files = [target] if target.is_file() else sorted(target.rglob("*.md"))
            for path in files:
                text = path.read_text(encoding="utf-8")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    for match in pattern.finditer(line):
                        tool = match.group(1)
                        action = match.group(2).replace("-", "_")
                        if tool not in tool_catalog.supported_tools():
                            violations.append(f"{path.relative_to(ROOT)}:{line_number}: unsupported tool {tool}")
                            continue
                        if action not in tool_catalog.supported_actions(tool):
                            violations.append(
                                f"{path.relative_to(ROOT)}:{line_number}: unsupported action {tool}.{action}"
                            )

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_stable_guidance_does_not_point_to_internal_tool_contract_surfaces(self) -> None:
        targets = [
            "tools/launcher/assets",
            "buddyswitch/skills",
            "docs/bitter",
            "docs/spec",
        ]
        completed = subprocess.run(
            [
                "rg",
                "-n",
                "scripts/env/tools/.*/(contract|semantics)\\.py|contract\\.py|semantics\\.py|TOOL_SPEC|ACTION_SEMANTICS|track\\.get|comment\\.reopen",
                *targets,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [
            line
            for line in completed.stdout.splitlines()
            if line.strip() and not self._is_docs_spec_context_hit(line)
        ]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_docs_spec_drift_filter_rejects_unmarked_live_guidance(self) -> None:
        self.assertTrue(
            self._is_docs_spec_context_hit(
                "docs/spec/2026-05-22-tool-layer-semantic-source-of-truth-implementation-plan.md:1:TOOL_SPEC"
            )
        )

    def test_active_guidance_does_not_reference_capture_as_env_tool(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                r"python3 scripts/env/client\.py\s+capture\b|context\.get\.tool_catalog\[['\"]capture['\"]|\"tool\"\s*:\s*\"capture\"",
                "buddyswitch/skills",
                "framework/contracts",
                "tools/launcher/assets/buddies",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_artifact_tool_files_do_not_add_design_specific_attachment_schema(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                r"design_handoff|ux_flow|screen_state|screenshot_ref",
                "scripts/env/tools/artifact",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))
        self.assertFalse(
            self._is_docs_spec_context_hit(
                "docs/spec/live-runtime-guidance.md:1:Use scripts/env/tools/task/contract.py"
            )
        )

    def test_runtime_buddy_agents_do_not_embed_project_source_facts(self) -> None:
        buddies = ("market", "pm", "design", "dev", "test")
        for buddy in buddies:
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(buddy=buddy):
                self.assertIn("context summarize --payload '{}'", text)
                self.assertIn("context get --payload '{}'", text)
                self.assertIn("agents.md is guidance only and not the permission source", text)
                self.assertIn("do not bypass runtime", text)
                self.assertNotIn("projects/app", text)
                self.assertNotIn("project.access=", text)

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
                "track\\.now|artifact\\.source_refs|comment\\.mentions",
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

    def test_instance_private_writable_surface_has_no_legacy_buddybox_roots(self) -> None:
        forbidden = (
            'BUDDYBOX_ROOT_TEMPLATE = "buddyswitch/local/buddybox/{buddy_id}"',
            'BUDDYBOX_LOCAL_DIR = LOCAL_ROOT / "buddybox"',
            'workspace_buddybox_root="${workspace_dir}/buddyswitch/local/buddybox"',
            "state/buddyswitch/local/buddybox",
            "buddyswitch/content/buddybox",
        )
        scan_targets = ["scripts", "tools", "buddyswitch/env-profiles", "framework/contracts"]
        for token in forbidden:
            completed = subprocess.run(
                ["rg", "-F", "-n", "-g", "!**/__pycache__/**", "--", token, *scan_targets],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
            self.assertEqual(completed.stdout.strip(), "", msg=f"{token}\n{completed.stdout}")

    def test_product_mode_does_not_grant_global_tmp_as_writable_root(self) -> None:
        forbidden = (
            '--temp-root "/tmp"',
            "Path(tempfile.gettempdir())",
            "system tempdir",
        )
        scan_targets = ["tools/launcher/env.sh", "tools/launcher/app_server.sh", "scripts/env/tools/artifact/_impl.py"]
        for token in forbidden:
            completed = subprocess.run(
                ["rg", "-F", "-n", "--", token, *scan_targets],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
            self.assertEqual(completed.stdout.strip(), "", msg=f"{token}\n{completed.stdout}")


if __name__ == "__main__":
    unittest.main()
