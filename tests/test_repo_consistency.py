"""Repository consistency checks for active track-page collaboration runtime."""

from __future__ import annotations

import ast
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

import env_store  # noqa: E402
import env_manifest  # noqa: E402
import turn_runtime  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from tests.python_runtime import PYTHON  # noqa: E402

_EXPECTED_TOOLS = {"task_sys", "track", "artifact", "context", "evidence", "search", "message"}
_FORBIDDEN_RUNTIME_SURFACES = {
    "artifact_index",
    "artifact_search",
    "relation",
    "insight",
    "experiment",
    "roadmap",
    "approval",
}

GENERIC_DAEMON_PATHS = (
    Path("tools/launcher/daemon_contracts.py"),
    Path("tools/launcher/daemon_state.py"),
    Path("tools/launcher/daemon_runtime.py"),
    Path("tools/launcher/daemon_core.py"),
    Path("tools/launcher/daemon_mailbox.py"),
    Path("scripts/env/tool_runtime/daemon_client.py"),
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name:
                imported.add(module_name)
            imported.update(
                f"{module_name}.{alias.name}" if module_name else alias.name
                for alias in node.names
            )
    return imported


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
            "tools/launcher/assets/roles",
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

    def _scan_targets(self, pattern: str, targets: list[str]) -> list[str]:
        completed = subprocess.run(
            ["rg", "-n", pattern, *targets, "-g", "!**/__pycache__/**", "-g", "!**/*.pyc"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        return [line for line in completed.stdout.splitlines() if line.strip()]

    def _scan_target_text(self, pattern: str, targets: list[str], *, flags: int = 0) -> list[str]:
        hits: list[str] = []
        for target in targets:
            path = ROOT / target
            if path.is_file():
                files = [path]
            else:
                files = [
                    row
                    for row in path.rglob("*.py")
                    if "__pycache__" not in row.parts and row.suffix == ".py"
                ]
            for file_path in files:
                text = file_path.read_text(encoding="utf-8")
                relative = file_path.relative_to(ROOT)
                for match in re.finditer(pattern, text, flags):
                    line_no = text.count("\n", 0, match.start()) + 1
                    snippet = " ".join(match.group(0).split())
                    hits.append(f"{relative}:{line_no}:{snippet[:260]}")
        return hits

    def test_python_runtime_has_one_non_docs_entrypoint(self) -> None:
        old_command = "python" + "3"
        running_interpreter = "sys." + "executable"
        version_api = "sys." + "version_info"
        platform_version_api = "platform." + "python_version"
        compatibility_package = "tom" + "li"
        version_pattern = re.compile(r"\b[Pp]ython(?:\s*|[-_.]?)[0-9]+\.[0-9]+\b")
        compatibility_package_pattern = re.compile(r"\b" + re.escape(compatibility_package) + r"\b")
        shebang_pattern = re.compile(r"^#!.*\b[Pp]ython(?:[0-9]+(?:\.[0-9]+)*)?\b")
        python_env_name = "BUDDYSWITCH_" + "PYTHON"
        python_default_token = python_env_name + ":-"
        assignment_owner_token = "export " + python_env_name + "="
        resolver_owner_pattern = re.compile(r"\btype\s+-P\s+python\b")

        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            text=False,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8").split("\0")
        tracked_paths = [Path(row) for row in tracked if row]

        residue: list[str] = []
        assignment_owners: set[str] = set()
        resolver_owners: set[str] = set()
        for relative in tracked_paths:
            if relative.parts and relative.parts[0] == "docs":
                continue
            path = ROOT / relative
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            first_line = text.splitlines()[0] if text.splitlines() else ""
            if shebang_pattern.search(first_line):
                residue.append(f"{relative}: first-line Python shebang")
            for label, token in (
                ("old command", old_command),
                ("running interpreter API", running_interpreter),
                ("version API", version_api),
                ("platform version API", platform_version_api),
            ):
                if token in text:
                    residue.append(f"{relative}: {label} token {token!r}")
            if compatibility_package_pattern.search(text):
                residue.append(f"{relative}: compatibility package token {compatibility_package!r}")
            for match in version_pattern.finditer(text):
                residue.append(f"{relative}: version literal {match.group(0)!r}")
            if python_default_token in text:
                residue.append(f"{relative}: BUDDYSWITCH_PYTHON default")
            if assignment_owner_token in text:
                assignment_owners.add(str(relative))
            if resolver_owner_pattern.search(text):
                resolver_owners.add(str(relative))

        staged_python = subprocess.run(
            ["git", "ls-files", "--stage", "*.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        executable_python = [
            row.rsplit("\t", 1)[-1]
            for row in staged_python
            if row.split(maxsplit=1)[0] == "100755"
        ]

        self.assertEqual(residue, [], msg="\n".join(residue))
        self.assertEqual(sorted(assignment_owners), ["tools/launcher/env.sh"])
        self.assertEqual(sorted(resolver_owners), ["tools/launcher/env.sh"])
        self.assertEqual(executable_python, [])

    def test_public_launcher_is_minimal_bootstrap_to_python_cli_adapter(self) -> None:
        launcher = ROOT / "buddyswitch-codex"
        cli_adapter = ROOT / "tools" / "launcher" / "cli.py"
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertTrue(cli_adapter.exists())
        cli_text = cli_adapter.read_text(encoding="utf-8")
        self.assertIn("source \"${ENV_HELPER}\"", launcher_text)
        self.assertIn("buddyswitch_env_init", launcher_text)
        self.assertIn('exec "${BUDDYSWITCH_PYTHON}" "${REPO_ROOT}/tools/launcher/cli.py" "$@"', launcher_text)
        for forbidden in (
            "legacy_" + "command_hint",
            "fail_removed_" + "public_command",
            "__" + "locked-reset",
            "__" + "locked-browser-ensure",
            "__" + "locked-browser-release",
            "__" + "locked-cleanup",
            "instance_" + "side",
            "instance_" + "goal",
            "imessage",
        ):
            self.assertNotIn(forbidden, launcher_text)

        for forbidden in (
            "--" + "json",
            "--" + "output",
            "legacy_" + "command_hint",
            "fail_removed_" + "public_command",
            "__" + "locked-",
            "Side " + "thread",
            "Goal",
            "IM ",
        ):
            self.assertNotIn(forbidden, cli_text)

    def test_public_cli_adapter_delegates_to_concrete_owners_without_repository_writes(self) -> None:
        cli_adapter = ROOT / "tools" / "launcher" / "cli.py"
        self.assertTrue(cli_adapter.exists())
        tree = ast.parse(cli_adapter.read_text(encoding="utf-8"), filename=str(cli_adapter))
        imported = _imported_modules(cli_adapter)
        self.assertIn("tools.launcher.host_control", imported)
        self.assertIn("tools.launcher.actor_session", imported)
        self.assertIn("env.domain.task_read", imported)
        self.assertIn("env.domain.track_read", imported)

        forbidden_calls = {
            "save_track",
            "create_track",
            "update_track",
            "write_json_object",
            "save_actor_identity_profile",
            "save_external_profile",
            "ingest",
            "record_task_close",
            "record_side_need_parent",
            "record_task_analysis_update",
            "record_side_runtime_failure",
        }
        calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.append(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.append(func.attr)
        self.assertEqual(sorted(forbidden_calls.intersection(calls)), [])

    def test_final_daemon_architecture_docs_name_current_single_paths(self) -> None:
        daemon_doc = (ROOT / "docs/arch/daemon-service-architecture.md").read_text(encoding="utf-8")
        web_doc = (ROOT / "docs/arch/web-interface-call-architecture.md").read_text(encoding="utf-8")

        for token in (
            "ActorDirectoryAccess",
            "SignalDeliveryAccess",
            "TaskSysRuntimeAccess",
            "ImActorDeliveryAccess",
            "task_sys_runtime_client.py",
            "task_sys_daemon_adapter.py",
            "actor_task_projection",
            "cancel_pending_schedules_by_source_owner",
        ):
            with self.subTest(document="daemon", token=token):
                self.assertIn(token, daemon_doc)
        for token in (
            "/api/actors/{id}/console",
            "actor_external_task_projection",
            "external Task/Track exact allowlist projections",
            "must not mutate Task or Track state",
            "task_sys.update_task_analysis",
            "host-control facts only",
            "no Task subroute",
        ):
            with self.subTest(document="web", token=token):
                self.assertIn(token, web_doc)
        for document_name, document in (("daemon", daemon_doc), ("web", web_doc)):
            with self.subTest(document=document_name, boundary="task-read-web-consumer"):
                self.assertNotRegex(document, r"`actor_task_projection`[^.\n]*(Web|external|/api/actors/\{id\}/console)")
                self.assertNotRegex(document, r"(Web|external|/api/actors/\{id\}/console)[^.\n]*`actor_task_projection`")
                self.assertNotIn("Web actor console all consume this projection", document)
                self.assertNotIn("Task panels obtain Task state from the Task Sys actor projection", document)

    def test_generic_daemon_modules_have_no_product_dependencies_or_tokens(self) -> None:
        forbidden_import_fragments = (
            "task_sys",
            "im_actor_delivery",
            "im_wake_handler",
            "track_comment",
            "browser_runtime",
            "browser_page",
            "browser_release",
            "web_management",
            "env.services.messages",
            "env.repos.messages",
            "env.repos.tracks",
        )
        forbidden_source_tokens = (
            "task_" + "sys",
            "Task " + "Sys",
            "im." + "message",
            "track." + "comment",
            "browser." + "page",
            "browser." + "cockpit",
        )
        for relative in GENERIC_DAEMON_PATHS:
            path = ROOT / relative
            imports = _imported_modules(path)
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=str(relative), boundary="imports"):
                self.assertFalse(
                    [name for name in imports if any(fragment in name for fragment in forbidden_import_fragments)],
                    imports,
                )
            with self.subTest(path=str(relative), boundary="tokens"):
                self.assertFalse([token for token in forbidden_source_tokens if token in source], source)

    def test_daemon_forward_convergence_retired_paths_are_absent(self) -> None:
        targets = ["tools/launcher", "scripts/env", "tests", "buddyswitch-codex", "docs/arch"]
        forbidden_patterns = (
            r"mailbox\." + "task_sys",
            "_task_sys_" + "status_payload",
            "task_sys_" + "dispatcher",
            "execute_" + "task_sys_instruction",
            "cleanup_" + "task_sys_side_lease",
            "Daemon" + "Access",
            r"\bcontext\.daemon\b",
            "task_checkout_" + "handler",
            "LEGACY_STATE_" + "FIELDS",
            "daemon_origin_" + "turn",
            "daemon_runtime_" + "call",
            "submit_parent_" + "prompt",
        )
        hits = self._scan_targets("|".join(forbidden_patterns), targets)
        self.assertEqual(hits, [], msg="\n".join(hits))
        self.assertFalse((ROOT / "tools/launcher" / ("task_checkout_" + "handler.py")).exists())
        self.assertFalse((ROOT / "tests" / ("test_task_checkout_" + "handler.py")).exists())

    def test_task_actor_projection_is_the_only_current_read_classifier(self) -> None:
        targets = ["tools/launcher", "scripts/env", "tests", "docs/arch"]
        retired = (
            "active_tasks_" + "for_actor",
            "recoverable_tasks_" + "for_actor",
            "has_active_task_" + "for_actor",
        )
        hits = self._scan_targets("|".join(retired), targets)
        self.assertEqual(hits, [], msg="\n".join(hits))

        internal_consumer_paths = (
            ROOT / "scripts/env/tools/task_sys/_impl.py",
            ROOT / "scripts/env/tools/context/_impl.py",
            ROOT / "scripts/env/tool_runtime/registry.py",
        )
        web_path = ROOT / "tools/launcher/web_management.py"
        direct_list_calls: list[str] = []
        for path in internal_consumer_paths:
            source = path.read_text(encoding="utf-8")
            self.assertIn("actor_task_projection", source, msg=path)
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "list_tasks":
                    direct_list_calls.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        web_source = web_path.read_text(encoding="utf-8")
        self.assertIn("task_read.actor_external_task_projection", web_source)
        self.assertNotIn("task_sys.actor_task_projection", web_source)
        web_tree = ast.parse(web_source, filename=str(web_path))
        for node in ast.walk(web_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "list_tasks":
                direct_list_calls.append(f"{web_path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual(direct_list_calls, [])

    def test_daemon_status_and_browser_state_use_final_boundaries(self) -> None:
        core_source = (ROOT / "tools/launcher/daemon_core.py").read_text(encoding="utf-8")
        self.assertNotIn("task_" + "sys", core_source)
        self.assertNotIn("task-sys", core_source)

        browser_path = ROOT / "tools/launcher/browser_runtime_manager.py"
        browser_source = browser_path.read_text(encoding="utf-8")
        browser_imports = _imported_modules(browser_path)
        self.assertIn("daemon_state", browser_imports)
        self.assertNotIn("daemon_core", browser_imports)
        self.assertIn("cancel_pending_schedules_by_source_owner", browser_source)
        for token in (
            "Daemon" + "State",
            "daemon_state_" + "file",
            "state.json",
            "scheduled_trigger_" + "ids",
            "scheduled_" + "triggers",
        ):
            self.assertNotIn(token, browser_source)

    def test_admin_browser_data_helpers_have_no_human_json_output_tracks(self) -> None:
        expectations = {
            "tools/launcher/browser_runtime_manager.py": (
                "_print_" + "human_result",
                "_emit_" + "result",
                "--" + "output",
                '"human"',
            ),
            "tools/launcher/browser_cockpit.sh": (
                "--" + "output",
                "Browser cockpit ready:",
                "Profile:",
            ),
            "tools/launcher/cleanup.sh": (
                "[--" + "json]",
                "--" + "json)",
                "BUDDYSWITCH_CLEANUP_COMMON_ARGS",
                "Removed data cleanup option",
                "--app-runtime",
                "--agent | --all-agents",
                "--project",
                "--all-storage",
                "--execute",
                "--force",
            ),
            "scripts/env_manifest.py": (
                "args." + "json",
                "add_argument(\"--" + "json\"",
            ),
            "scripts/env_cleanup.py": (
                "print_" + "text_plan",
                "args." + "json",
                "add_argument(\"--" + "json\"",
                "Preview mode:",
                "Cleanup completed.",
            ),
            "tools/launcher/cli.py": (
                "[*cleanup_args, REMOVED_" + "JSON_FLAG]",
                "_json_stdout_" + "or_raw",
            ),
            "tools/launcher/host_control.sh": (
                "list-roles --" + "json",
            ),
            "tools/launcher/host_control.py": (
                "import argparse",
                "Sequence",
                "_emit_" + "json",
                "_emit_roles",
                "_emit_instances",
                "_emit_status",
                "_emit_capabilities",
                "_command_",
                "json_output",
                "build_parser",
                "_prevalidate_legacy_messages",
                "def main(",
                "__main__",
                "--" + "json",
                "BuddySwitch instance:",
                "No BuddySwitch instances found.",
                "delete preview",
            ),
        }
        for relative, forbidden_tokens in expectations.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=relative, token=token):
                    self.assertNotIn(token, source)

    def test_handlers_use_stable_contracts_and_instance_daemon_is_sole_composition_root(self) -> None:
        handler_paths = (
            ROOT / "tools/launcher/im_wake_handler.py",
            ROOT / "tools/launcher/track_comment_added_handler.py",
            ROOT / "tools/launcher/browser_page_expired_handler.py",
            ROOT / "tools/launcher/browser_release_handler.py",
        )
        for path in handler_paths:
            imports = _imported_modules(path)
            with self.subTest(path=path.name):
                self.assertIn("daemon_contracts", imports)
                self.assertNotIn("daemon_core", imports)

        composition_roots: list[str] = []
        product_adapter_fragments = (
            "task_sys_daemon_adapter",
            "im_wake_handler",
            "track_comment_added_handler",
            "browser_page_expired_handler",
            "browser_release_handler",
        )
        for path in sorted((ROOT / "tools/launcher").glob("*.py")):
            imports = _imported_modules(path)
            if "daemon_core" in imports and any(
                any(fragment in imported for fragment in product_adapter_fragments)
                for imported in imports
            ):
                composition_roots.append(path.name)
        self.assertEqual(composition_roots, ["instance_daemon.py"])

    def test_external_session_naming_has_no_live_connection_residue(self) -> None:
        surfaces = (
            ROOT / "scripts" / "env" / "repos" / "messages.py",
            ROOT / "scripts" / "env" / "services" / "messages.py",
            ROOT / "tools" / "launcher" / "external_im_session.py",
            ROOT / "tools" / "launcher" / "im_http_router.py",
            ROOT / "tools" / "launcher" / "web_im_identity.py",
            ROOT / "tools" / "launcher" / "imessage_channel.py",
            ROOT / "tools" / "launcher" / "assets" / "web-management" / "app.js",
            ROOT / "docs" / "arch" / "web-interface-call-architecture.md",
        )
        forbidden = (
            "create_external_" + "connection",
            "authenticate_external_" + "connection_key",
            "send_external_" + "connection_message",
            "read_external_" + "connection_events",
            "ack_external_" + "connection_event",
            "save_im_" + "connection",
            "get_im_" + "connection_by_key_hash",
            "connection_" + "key",
            "connection_" + "key_hash",
            "/api/im/" + "connections",
            "state/im/" + "connections",
            "im/" + "connections",
            "Web IM " + "connection",
        )
        for surface in surfaces:
            source = surface.read_text(encoding="utf-8")
            for fragment in forbidden:
                with self.subTest(surface=str(surface.relative_to(ROOT)), fragment=fragment):
                    self.assertNotIn(fragment, source)

    @staticmethod
    def _retired_actor_private_host_path_tokens() -> tuple[str, ...]:
        return (
            " ".join(("actor_private", "write", "--payload")),
            ".".join(("actor_private", "import_file")),
            "_".join(("source", "actor_private", "logical", "name")),
            "_".join(("write", "private", "text")),
            "_".join(("write", "private", "binary")),
            " ".join(("address", "them", "only", "through", "actor_private", "env", "tools")),
        )

    def test_launcher_tools_package_is_not_shadowed_by_env_tools_package(self) -> None:
        env_tools_root = ROOT / "scripts" / "env"
        script = f"""
import json
import sys
sys.path = [{str(ROOT)!r}, {str(env_tools_root)!r}] + [
    path for path in sys.path
    if path not in ({str(env_tools_root)!r}, {str(ROOT)!r}, "")
]
import tools
import tools.launcher
print(json.dumps({{
    "tools_file": getattr(tools, "__file__", None),
    "launcher_paths": list(getattr(tools.launcher, "__path__", [])),
}}))
"""
        completed = subprocess.run(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr + completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(Path(payload["tools_file"]).resolve(strict=False), ROOT / "tools" / "__init__.py")
        self.assertIn(str(ROOT / "tools" / "launcher"), payload["launcher_paths"])

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

    def test_browser_control_plane_has_no_live_old_acquisition_residue(self) -> None:
        forbidden_patterns = (
            "_".join(("ensure", "browser", "url", "for", "instance")),
            "BUDDYSWITCH_BROWSER_COCKPIT_" + "ENSURE_COMMAND",
            'ROOT / "' + "buddyswitch-codex" + '"',
            "env browser " + "ensure",
            "env browser " + "release",
        )
        scan_targets = [
            "scripts/env",
            "scripts/runtime_kernel",
            "tools/launcher",
            "tests",
        ]
        allowed_files = {
            "tools/launcher/cli.py",
            "tests/test_repo_consistency.py",
            "tests/test_buddyswitch_launcher.py",
            "tests/test_browser_cockpit_launcher.py",
            "tests/test_imessage_channel.py",
            "tests/test_web_management.py",
        }
        allowed_lines = (
            "tools/launcher/browser_cockpit.sh:77:",
            "tools/launcher/browser_cockpit.sh:78:",
        )
        hits: list[str] = []
        for pattern in forbidden_patterns:
            completed = subprocess.run(
                ["rg", "-n", pattern, *scan_targets, "-S", "-g", "!**/__pycache__/**", "-g", "!**/*.pyc"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
            for line in completed.stdout.splitlines():
                if not line.strip():
                    continue
                path = line.split(":", 1)[0]
                if path in allowed_files:
                    continue
                if any(fragment in line for fragment in allowed_lines):
                    continue
                hits.append(line)

        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_browser_cockpit_selected_page_live_surfaces_reject_actor_page_cdp_truth(self) -> None:
        self.assertFalse(
            (ROOT / "scripts" / "env" / ("cdp_browser_" + "session.py")).exists(),
            "orphan actor-page CDP browser session helper should be removed",
        )
        scan_files = [
            "tools/launcher/chrome_devtools_cockpit_proxy.py",
            "tools/launcher/browser_page_expired_handler.py",
            "tools/launcher/browser_inbound.py",
            "scripts/env/cdp_browser_lifecycle.py",
        ]
        forbidden_tokens = (
            "cdp_browser_" + "session",
            "browser_" + "session.",
            "open_or_" + "reuse_page",
            "current_" + "target_id",
            "page_id_to_" + "target_id",
            "target_id_for_" + "page_id",
            "create_background_page_" + "target",
            "close_page_" + "target",
            "target_idle_expiry_after_" + "due_at",
            "forget_page_idle_" + "target",
        )
        hits: list[str] = []
        for relative in scan_files:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for token in forbidden_tokens:
                if token in text:
                    hits.append(f"{relative}: {token}")
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_browser_failed_open_cleanup_live_surfaces_keep_cdp_close_scoped(self) -> None:
        required_tokens = {
            "scripts/env/cdp_background_page.py": ("Target." + "closeTarget",),
            "scripts/env/cdp_browser_lifecycle.py": (
                "browser.failed_open_page.cleanup",
                "schedule_failed_open_page_cleanup",
            ),
            "tools/launcher/chrome_devtools_cockpit_proxy.py": (
                "failed_open_page",
                "close_target",
            ),
            "tools/launcher/browser_page_expired_handler.py": (
                "browser.failed_open_page.cleanup",
                "close_target",
            ),
            "tools/launcher/browser_inbound.py": ("browser.failed_open_page.cleanup",),
        }
        for relative, tokens in required_tokens.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            for token in tokens:
                with self.subTest(relative=relative, token=token):
                    self.assertIn(token, source)

        close_scan_targets = [
            "tools/launcher",
            "scripts/env",
            "tests/test_browser_cockpit_proxy.py",
            "tests/test_browser_page_expired_handler.py",
            "tests/test_cdp_browser_session.py",
            "tests/test_repo_consistency.py",
        ]
        allowed_close_files = {
            "scripts/env/cdp_background_page.py",
            "tools/launcher/chrome_devtools_cockpit_proxy.py",
            "tools/launcher/browser_page_expired_handler.py",
            "tests/test_browser_cockpit_proxy.py",
            "tests/test_browser_page_expired_handler.py",
            "tests/test_cdp_browser_session.py",
            "tests/test_repo_consistency.py",
        }
        close_hits = self._scan_targets(r"Target\.closeTarget|\bclose_target\b", close_scan_targets)
        disallowed_close_hits = [
            line
            for line in close_hits
            if line.split(":", 1)[0] not in allowed_close_files
        ]
        self.assertEqual(disallowed_close_hits, [], msg="\n".join(disallowed_close_hits))

        lifecycle_source = (ROOT / "scripts/env/cdp_browser_lifecycle.py").read_text(encoding="utf-8")
        self.assertNotIn("current_" + "target_id", lifecycle_source)
        self.assertNotIn("page_id_to_" + "target_id", lifecycle_source)
        self.assertNotIn("close_target(", lifecycle_source)

        release_source = (ROOT / "tools/launcher/browser_release_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("failed_open_page", release_source)
        self.assertNotIn("close_target", release_source)

    def test_side_thread_lifecycle_boundary_has_no_direct_call_residue(self) -> None:
        targets = ["tools/launcher", "scripts/env", "buddyswitch-codex", "tests"]
        direct_pattern = (
            r"app_server\." + r"(side_start|side_close|thread_fork|thread_inject_items|input_turn)"
            + r"|side_thread_registry\."
            + r"(register_side_thread|require_side_thread|find_task_side_thread|unregister_side_thread)"
            + r"|import task_sys_" + r"runtime|task_sys_" + r"runtime\."
        )
        allowed_direct_prefixes = (
            "tools/launcher/side_thread_lifecycle.py:",
            "tools/launcher/actor_session.py:",
            "tools/launcher/app_server.py:",
            "tools/launcher/side_thread_registry.py:",
            "tools/launcher/task_sys_daemon_adapter.py:",
            "tests/test_actor_session.py:",
            "scripts/env/tool_runtime/context.py:",
            "scripts/env/tool_runtime/task_sys_runtime_client.py:",
            "tests/test_side_thread_lifecycle.py:",
            "tests/test_side_thread_registry.py:",
            "tests/test_task_sys_daemon_adapter.py:",
            "tests/test_task_sys_runtime_client.py:",
            "tests/test_task_sys_runtime_executor.py:",
        )
        direct_hits = [
            line
            for line in self._scan_targets(direct_pattern, targets)
            if not line.startswith(allowed_direct_prefixes)
        ]
        self.assertEqual(direct_hits, [], msg="\n".join(direct_hits))

        legacy_shell_helpers = tuple(
            "buddyswitch_instance_" + action + "_side_thread"
            for action in ("register", "require", "unregister")
        )
        for helper in legacy_shell_helpers:
            helper_hits = self._scan_targets(helper, targets)
            self.assertEqual(helper_hits, [], msg="\n".join(helper_hits))

        terminology_pattern = "|".join(
            (
                "physical_" + "close",
                "startup_" + "interrupt",
                "side_" + r"start\(",
                "side_" + r"close\(",
            )
        )
        terminology_hits = self._scan_targets(terminology_pattern, targets)
        self.assertEqual(terminology_hits, [], msg="\n".join(terminology_hits))

    def test_daemon_side_reuse_surface_is_removed(self) -> None:
        targets = ["tools/launcher", "scripts/env", "buddyswitch-codex", "tests"]
        forbidden = (
            "submit_" + "side_triage_prompt",
            "daemon." + "side_triage",
            "find_or_" + "start_side_thread",
            "find_" + "open_side_thread",
            "find-" + "open",
            "start_" + "or_reuse_side_triage",
            "start_" + "side_triage",
            "send_" + "side_triage",
            "close_" + "side_triage",
        )
        hits: list[str] = []
        for token in forbidden:
            hits.extend(self._scan_targets(token, targets))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_parent_thread_settings_update_is_limited_to_parent_boundary(self) -> None:
        targets = ["tools/launcher", "tests"]
        rpc_hits = self._scan_targets("thread/" + "settings/update", targets)

        allowed_rpc_paths = {
            "tools/launcher/app_server.py",
            "tests/test_app_server_client.py",
            "tests/test_buddyswitch_launcher.py",
            "tests/test_repo_consistency.py",
        }
        disallowed: list[str] = []
        for line in rpc_hits:
            path = line.split(":", 1)[0]
            if path not in allowed_rpc_paths:
                disallowed.append(line)

        update_helper_hits = self._scan_targets("thread_settings_update", targets)
        allowed_update_helper_paths = {
            "tools/launcher/app_server.py",
            "tools/launcher/actor_session.py",
            "tests/test_actor_session.py",
            "tests/test_app_server_client.py",
            "tests/test_repo_consistency.py",
        }
        for line in update_helper_hits:
            path = line.split(":", 1)[0]
            if path not in allowed_update_helper_paths:
                disallowed.append(line)

        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

        app_server_source = (ROOT / "tools/launcher/app_server.py").read_text(encoding="utf-8")
        actor_session_source = (ROOT / "tools/launcher/actor_session.py").read_text(encoding="utf-8")
        self.assertIn("thread/" + "settings/update", app_server_source)
        self.assertIn("app_server.thread_settings_update", actor_session_source)

    def test_side_thread_model_selection_has_no_persistent_config_write_path(self) -> None:
        side_targets = [
            "tools/launcher/actor_side_thread.py",
            "tools/launcher/side_thread_lifecycle.py",
            "buddyswitch-codex",
            "tools/launcher/web_management.py",
        ]
        forbidden = (
            "thread/" + "settings/update",
            "config/" + "batchWrite",
            "Persist" + "ModelSelection",
            "Update" + "Model",
        )
        hits: list[str] = []
        for token in forbidden:
            hits.extend(self._scan_targets(token, side_targets))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_actor_capability_live_surfaces_have_no_retired_vocabulary(self) -> None:
        live_targets = [
            "buddyswitch-codex",
            "tools/launcher",
            "tests/test_actor_capability.py",
            "tests/test_actor_session.py",
            "tests/test_actor_side_thread.py",
            "tests/test_buddyswitch_launcher.py",
            "tests/test_web_management.py",
            "tests/web_management_ui_state.test.js",
            "tests/web_management_ui_contract.test.js",
        ]
        retired_patterns = (
            "actor_" + "model_config",
            "model-" + "config\\.json",
            "/" + "model-config",
            "instance " + "model-config",
            "actorModel" + "Config",
            "actor-model-" + "config",
            "allowed_" + "efforts",
            "VALID_" + "EFFORTS",
            "model_" + "source",
            "model_reasoning_effort_" + "source",
            "model_config_" + "durability",
            "_model_config_" + "result",
            "\\-\\-" + "payload-json",
        )
        hits: list[str] = []
        for pattern in retired_patterns:
            hits.extend(self._scan_targets(pattern, live_targets))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_actor_capability_public_side_surfaces_do_not_accept_raw_overrides(self) -> None:
        public_side_targets = [
            "buddyswitch-codex",
            "tools/launcher/host_control.py",
            "tools/launcher/host_control.sh",
            "tools/launcher/env.sh",
            "tools/launcher/actor_side_thread.py",
            "tools/launcher/web_management.py",
        ]
        self.assertFalse((ROOT / "tools/launcher/instance.sh").exists())
        hits = self._scan_targets("\\-\\-" + "model|\\-\\-" + "effort", public_side_targets)
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_actor_capability_adapters_do_not_duplicate_catalog(self) -> None:
        adapter_targets = [
            "tools/launcher/web_management.py",
            "tools/launcher/host_control.py",
            "tools/launcher/host_control.sh",
            "buddyswitch-codex",
            "tools/launcher/assets/web-management",
        ]
        self.assertFalse((ROOT / "tools/launcher/actor_capability_cli.py").exists())
        hits = self._scan_targets("gpt-5\\.6-(luna|terra|sol)", adapter_targets)
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_actor_capability_internal_rpc_layers_do_not_read_product_storage(self) -> None:
        retired_submit_paths = [
            "tools/launcher/submit_turn.py",
            "tools/launcher/parent_thread_submit.py",
            "tests/test_submit_turn.py",
            "tests/test_parent_thread_submit.py",
        ]
        for relative in retired_submit_paths:
            with self.subTest(relative=relative):
                self.assertFalse((ROOT / relative).exists())

        internal_targets = [
            "tools/launcher/app_server.py",
            "tools/launcher/actor_session.py",
            "tools/launcher/side_thread_lifecycle.py",
            "tools/launcher/daemon_core.py",
            "tools/launcher/task_sys_" + "runtime.py",
        ]
        hits = self._scan_targets(
            "capability-config\\.json|load_actor_capabilities|replace_actor_capabilities",
            internal_targets,
        )
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_actor_capability_retires_direct_start_and_submit_paths(self) -> None:
        direct_side_hits = self._scan_targets(
            "side_thread_lifecycle\\.start_side_thread",
            ["tools/launcher/task_sys_" + "runtime.py", "buddyswitch-codex", "tools/launcher/env.sh"],
        )
        self.assertEqual(direct_side_hits, [], msg="\n".join(direct_side_hits))

        side_cli_hits = self._scan_targets(
            "subparsers\\.add_parser\\(\"start\"",
            ["tools/launcher/side_thread_lifecycle.py"],
        )
        self.assertEqual(side_cli_hits, [], msg="\n".join(side_cli_hits))

        direct_parent_hits = self._scan_targets(
            "launcher_submit_turn\\.submit_turn|import submit_turn as launcher_submit_turn",
            ["tools/launcher/task_sys_" + "runtime.py", "tools/launcher/daemon_core.py"],
        )
        self.assertEqual(direct_parent_hits, [], msg="\n".join(direct_parent_hits))

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
            {
                "create",
                "list",
                "open",
                "add_comment",
                "list_comments",
                "resolve_comment_thread",
                "update_requirements",
                "update_status",
                "add_material",
                "add_update",
                "add_proof",
                "archive",
            },
        )
        artifact_actions = set(tool_catalog.supported_actions("artifact"))
        self.assertEqual(
            artifact_actions,
            {"list", "get", "create_revision", "update_metadata", "attach_file", "list_attachments", "get_attachment"},
        )
    def test_actor_private_env_tool_package_is_removed(self) -> None:
        self.assertFalse((ROOT / "scripts" / "env" / "tools" / "actor_private").exists())
        self.assertNotIn("actor_private", tool_catalog.supported_tools())

    def test_live_guidance_uses_direct_actor_private_directory_not_env_tool_payloads(self) -> None:
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
        for forbidden in self._retired_actor_private_host_path_tokens():
            self.assertNotIn(forbidden, text)
        self.assertIn("buddyswitch_actor_private_dir", text)
        self.assertIn("workspace/private", text)

    def test_actor_identity_live_surfaces_do_not_reintroduce_role_as_actor_residue(self) -> None:
        live_paths = [
            ROOT / "scripts/env/tools/message/tool.py",
            ROOT / "scripts/env/tools/track/tool.py",
            ROOT / "scripts/env/tools/task_sys/tool.py",
            ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
            ROOT / "buddyswitch/skills/pm/define-scope/SKILL.md",
            ROOT / "README.md",
            ROOT / "tools/launcher/assets/web-management/index.html",
            ROOT / "tools/launcher/assets/web-management/app.js",
            ROOT / "framework/contracts/role-env-profile.json",
            *sorted((ROOT / "buddyswitch/env-profiles").glob("*.json")),
        ]
        forbidden_lower = (
            "role messages",
            "direct_role_channel",
            "active_role_inbox",
            "active-role inbox",
            "not the active role",
            "outside the active role",
            "active role cannot",
            "same role id",
            "direct role inbox",
            "direct role messaging",
            "active-role tasksnapshot",
            "active-role taskbox",
            "current active-role taskbox task",
            "active-role work management",
            "role-locked codex instances",
            "runtime workspace per role",
            "active-role-only",
        )
        forbidden_case_sensitive = (
            "selectedBuddy",
            ">Buddy<",
            "Stored local role instances",
        )

        hits: list[str] = []
        for path in live_paths:
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            relative = path.relative_to(ROOT)
            for token in forbidden_lower:
                if token in lowered:
                    hits.append(f"{relative}: {token}")
            for token in forbidden_case_sensitive:
                if token in text:
                    hits.append(f"{relative}: {token}")

        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_retired_message_skill_has_no_live_surface_residue(self) -> None:
        retired_skill_id = "message" + "-tool"
        retired_skill_path = "/".join(("buddyswitch", "skills", "shared", retired_skill_id))
        self.assertFalse((ROOT / retired_skill_path / "SKILL.md").exists())

        live_targets = [
            ROOT / "buddyswitch/manifest.toml",
            ROOT / "tests/test_runtime_skills.py",
            ROOT / "tests/test_env_manifest_v2.py",
            ROOT / "tests/test_repo_consistency.py",
        ]
        hits: list[str] = []
        for path in live_targets:
            text = path.read_text(encoding="utf-8")
            relative = path.relative_to(ROOT)
            if retired_skill_id in text:
                hits.append(f"{relative}: retired skill id")
            if retired_skill_path in text:
                hits.append(f"{relative}: retired skill path")

        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_communication_identity_live_surfaces_have_no_retired_shapes(self) -> None:
        high_signal_targets = [
            "scripts/env/repos/messages.py",
            "scripts/env/services/messages.py",
            "scripts/env/tools/message",
            "scripts/env/tool_runtime/im_client.py",
            "scripts/env/tools/context/_impl.py",
            "scripts/env_cleanup.py",
            "scripts/env_legacy_store.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
            "tools/launcher/assets/web-management/app.js",
            "tools/launcher/imessage_channel.py",
            "tools/launcher/web_im_identity.py",
            "tools/launcher/task_sys_" + "runtime.py",
            "tools/launcher/assets/roles",
            "buddyswitch/skills/shared/track-tool",
            "tests/test_communication_identity_cutover.py",
            "tests/test_im_product_core.py",
            "tests/test_external_im_session.py",
            "tests/test_im_http_router.py",
            "tests/test_external_im_projection_contract.py",
            "tests/test_web_management.py",
            "tests/web_management_ui_state.test.js",
            "tests/web_management_ui_contract.test.js",
            "tests/test_im_web_management_projection.py",
            "tests/test_imessage_channel.py",
            "tests/test_context_binding_env_tool.py",
            "tests/test_cleanup_system.py",
            "tests/test_env_store_v2.py",
            "tests/test_runtime_broker.py",
            "tests/test_browser_page_expired_handler.py",
            "tests/test_notification_center.py",
            "tests/test_daemon_mailbox.py",
            "tests/test_track_env_tool.py",
            "tests/test_artifact_env_tool.py",
            "tests/test_track_comment_env_tool.py",
            "tests/test_artifact_selection.py",
            "tests/test_track_comment_added_handler.py",
            "tests/test_task_sys_runtime_executor.py",
        ]
        flattened_im_targets = [
            "scripts/env/repos/messages.py",
            "scripts/env/tools/context/_impl.py",
            "tools/launcher/assets/web-management/app.js",
            "tools/launcher/imessage_channel.py",
            "tests/test_communication_identity_cutover.py",
            "tests/test_im_product_core.py",
            "tests/test_external_im_projection_contract.py",
            "tests/web_management_ui_state.test.js",
            "tests/test_imessage_channel.py",
            "tests/test_context_binding_env_tool.py",
            "tests/test_runtime_broker.py",
        ]
        participant_field_targets = [
            "scripts/env/repos/messages.py",
            "tools/launcher/web_im_identity.py",
            "tests/test_external_im_projection_contract.py",
            "tests/test_im_http_router.py",
            "tests/test_im_product_core.py",
            "tests/test_web_management.py",
            "tests/test_context_binding_env_tool.py",
            "tests/test_runtime_broker.py",
        ]
        track_artifact_targets = [
            "scripts/env/repos/tracks.py",
            "scripts/env/domain/artifact_visibility.py",
            "tests/test_track_env_tool.py",
            "tests/test_artifact_env_tool.py",
            "tests/test_artifact_selection.py",
        ]
        expanded_live_targets = [
            "tools/launcher/assets/roles",
            "buddyswitch/skills",
            "framework/contracts",
            "scripts/env/tools",
            "scripts/env/tool_runtime",
            "tools/launcher/assets/web-management/app.js",
        ]

        scans = [
            (
                r"ActorAddress|actor_address|from_actor_address|to_actor_address|processed_by_actor_address"
                r"|source_actor_address|target_actor_address|identity_from_im_participant"
                r"|participant\.actor_address|participant\.external_id"
                r"|\"kind\"\s*:\s*\"actor\"|\"kind\"\s*:\s*\"external\"",
                high_signal_targets,
            ),
            (r"\bfrom_identity_id\b|\bto_identity_id\b|\bvisible_to_identity\b", flattened_im_targets),
            (r"['\"]participants['\"]|['\"]participant['\"]", participant_field_targets),
            (r"\bfrom_actor\b", track_artifact_targets),
            (
                r"ActorAddress|actor_address|from_actor_address|to_actor_address|processed_by_actor_address"
                r"|source_actor_address|target_actor_address|identity_from_im_participant"
                r"|participant\.actor_address|participant\.external_id",
                expanded_live_targets,
            ),
            (r"\bfrom_identity_id\b|\bto_identity_id\b|\bvisible_to_identity\b", expanded_live_targets),
        ]

        def is_allowed_hit(line: str) -> bool:
            parts = line.split(":", 2)
            path = parts[0] if parts else ""
            content = parts[2] if len(parts) == 3 else line
            lowered = content.lower()
            if path.startswith("tests/"):
                if "assertNotIn(" in content or "assertNotRegex(" in content or "assertFalse(" in content:
                    return True
                if " not in " in content and ("assertTrue(" in content or "assertEqual(" in content):
                    return True
                if "for forbidden in" in content:
                    return True
                if any(fragment in lowered for fragment in ("legacy", "does_not", "without_actor_address", "no_retired", "retired")):
                    return True
            if "retired_shape" in content or "legacy_rejection_payload" in content:
                return True
            return False

        disallowed: list[str] = []
        for pattern, targets in scans:
            for line in self._scan_targets(pattern, targets):
                if not is_allowed_hit(line):
                    disallowed.append(line)

        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_im_sender_reach_live_surfaces_do_not_expose_actor_handling_coupling(self) -> None:
        targets = [
            "scripts/env/services/messages.py",
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
            "scripts/env/tools/message/tool.py",
            "tests/test_im_product_core.py",
            "tests/test_message_tool_im_client.py",
            "tests/test_external_im_session.py",
            "tests/test_im_http_router.py",
            "tests/test_external_im_projection_contract.py",
            "tests/test_web_management.py",
            "tests/test_env_tool_schema_contract.py",
            "tests/test_env_tool_response_contract.py",
            "tests/test_context_binding_env_tool.py",
        ]
        multiline_patterns = [
            r"send_im_message\([\s\S]{0,500}\btarget_role_id\s*=",
            r"send_im_message\([\s\S]{0,500}\bwake_actor\s*=",
        ]
        patterns = [
            r"\bactor_identity_for_current_send_target\b",
            r"target_identity_id is only required for new actor-directed messages",
            r"new actor-directed message",
            r"external target_identity_id requires reply_to conversation routing context",
        ]
        hits: list[str] = []
        for pattern in multiline_patterns:
            hits.extend(self._scan_target_text(pattern, targets, flags=re.MULTILINE))
        for pattern in patterns:
            hits.extend(self._scan_targets(pattern, targets))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_im_target_resolver_rebuild_has_no_old_send_resolver_residue(self) -> None:
        targets = [
            "scripts/env/services/messages.py",
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
            "scripts/env/tools/message/tool.py",
            "scripts/env/tools/context/_impl.py",
            "tests/test_im_product_core.py",
            "tests/test_message_tool_im_client.py",
            "tests/test_external_im_session.py",
            "tests/test_im_http_router.py",
            "tests/test_env_tool_schema_contract.py",
            "tests/test_env_tool_semantic_contract.py",
            "tests/test_context_binding_env_tool.py",
        ]
        patterns = [
            r"\bidentity_for_current_send_target\b",
            r"not a reachable target identity under current reach policy",
            r"external target_identity_id requires reply_to conversation routing context",
            r"message\.send.*must.*message\.contacts",
            r"message\.contacts.*before message\.send",
            r"contacts.*as.*send.*authority",
        ]
        hits: list[str] = []
        for pattern in patterns:
            hits.extend(self._scan_targets(pattern, targets))

        def is_allowed_hit(line: str) -> bool:
            parts = line.split(":", 2)
            path = parts[0] if parts else ""
            content = parts[2] if len(parts) == 3 else line
            if path.startswith("tests/") and ("assertNotIn(" in content or "forbidden" in content):
                return True
            return False

        disallowed = [line for line in hits if not is_allowed_hit(line)]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_im_reply_wrapper_convergence_has_no_old_core_reply_branch_residue(self) -> None:
        targets = [
            "scripts/env/services/messages.py",
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/task_sys_" + "runtime.py",
            "scripts/env/tools/message/tool.py",
            "buddyswitch/skills/shared/task-management/SKILL.md",
            "tests/test_im_product_core.py",
            "tests/test_message_tool_im_client.py",
            "tests/test_external_im_session.py",
            "tests/test_im_http_router.py",
            "tests/test_im_external_reply_loop.py",
            "tests/test_web_management.py",
            "tests/test_task_sys_runtime_executor.py",
            "tests/test_env_tool_schema_contract.py",
            "tests/test_env_tool_semantic_contract.py",
            "tests/test_task_management_skill_architecture.py",
            "tests/test_context_binding_env_tool.py",
        ]
        patterns = [
            r"\b_resolve_reply_" + r"conversation\b",
            r"\b_direct_conversation_" + r"identity_ids\b",
            r"reply target cannot be " + r"derived from the " + r"direct conversation",
            r"reply_to must stay in the same " + r"direct conversation",
            r"Central IM derives the other " + r"direct identity",
            r"central im derives the other " + r"direct identity",
            r"reply_to only to reply inside the existing " + r"direct conversation",
            r"reply inside the existing " + r"direct conversation",
            r"target_identity_id is only required for a new " + r"target-identity message",
        ]
        multiline_patterns = [
            r"send_im_message\([\s\S]{0,500}\bto\s*=\s*None[\s\S]{0,500}\breply_to\s*=",
            r"send_im_message\([\s\S]{0,500}\breply_to\s*=[\s\S]{0,500}\bto\s*=\s*None",
        ]
        hits: list[str] = []
        for pattern in multiline_patterns:
            hits.extend(self._scan_target_text(pattern, targets, flags=re.MULTILINE))
        for pattern in patterns:
            hits.extend(self._scan_targets(pattern, targets))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_im_send_paths_do_not_use_actor_list_as_target_resolver(self) -> None:
        targets = [
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
        ]
        multiline_patterns = [
            r"def _send_target_identity[\s\S]{0,800}_online_actor_rows",
            r"def send_message[\s\S]{0,1000}_actor_lister",
            r"def send_message[\s\S]{0,1000}list_im_actor_contacts",
        ]
        hits: list[str] = []
        for pattern in multiline_patterns:
            hits.extend(self._scan_target_text(pattern, targets, flags=re.MULTILINE))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_im_actor_handling_surfaces_do_not_accept_sender_supplied_role(self) -> None:
        targets = [
            "scripts/env/tool_runtime/im_actor_delivery.py",
            "scripts/env/tool_runtime/context.py",
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
            "tests/test_im_external_reply_loop.py",
            "tests/test_communication_identity_cutover.py",
            "tests/test_message_tool_im_client.py",
            "tests/test_external_im_session.py",
            "tests/test_im_http_router.py",
            "tests/test_web_management.py",
        ]
        multiline_forbidden = [
            r"deliver\(\s*\{[\s\S]{0,500}\btarget_role_id\b",
        ]
        forbidden = [
            r"payload\.get\([\"']target_role_id[\"']\)",
            r"record\.get\([\"']role_id[\"']\)",
            r"wake_status",
        ]
        hits: list[str] = []
        for pattern in multiline_forbidden:
            hits.extend(self._scan_target_text(pattern, targets, flags=re.MULTILINE))
        for pattern in forbidden:
            hits.extend(self._scan_targets(pattern, targets))

        def is_allowed_hit(line: str) -> bool:
            parts = line.split(":", 2)
            path = parts[0] if parts else ""
            content = parts[2] if len(parts) == 3 else line
            if path.startswith("tests/") and "assertNotIn(" in content:
                return True
            return False

        disallowed = [line for line in hits if not is_allowed_hit(line)]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_im_post_write_delivery_is_not_reimplemented_in_sender_projections(self) -> None:
        targets = [
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
        ]
        forbidden = [
            r"def _with_actor_handling_status",
            r"actor_message_handler",
            r"[\"']type[\"']\s*:\s*[\"']im\.message\.created[\"']",
        ]
        hits: list[str] = []
        for pattern in forbidden:
            hits.extend(self._scan_targets(pattern, targets))
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_central_im_write_does_not_import_processing_or_channel(self) -> None:
        source = (ROOT / "scripts" / "env" / "services" / "messages.py").read_text(encoding="utf-8")
        forbidden = (
            "wake_" + "im_actor",
            "mailbox.local_trigger",
            "task_sys_ingress",
            "ImMessageCreatedHandler",
            "imessage_channel",
        )
        hits = [term for term in forbidden if term in source]
        self.assertEqual(hits, [])

    def test_im_delivery_helper_does_not_import_processing_or_channel(self) -> None:
        source = (ROOT / "scripts" / "env" / "services" / "messages.py").read_text(encoding="utf-8")
        forbidden = (
            "task_sys_ingress",
            "ImMessageCreatedHandler",
            "imessage_channel",
            "web_management",
            "im_http_router",
        )
        hits = [term for term in forbidden if term in source]
        self.assertEqual(hits, [])

    def test_registry_semantic_projections_are_generated_from_definitions(self) -> None:
        desc = tool_catalog.env_tools_description()
        operation_semantics = tool_catalog.operation_semantics()
        compact = tool_catalog.compact_tool_affordances()

        for tool in sorted(tool_catalog.supported_tools()):
            definition = tool_catalog.get_definition(tool)
            with self.subTest(tool=tool):
                self.assertEqual(desc[tool]["object_model"], definition.object_model)
                self.assertEqual(compact[tool]["object_model"], definition.object_model)
                self.assertNotIn("command", desc[tool])
                self.assertNotIn("cli_resource", desc[tool])
                self.assertIn("native_mcp", desc[tool])
                native_mcp = desc[tool]["native_mcp"]
                self.assertIsInstance(native_mcp, dict)
                self.assertEqual(native_mcp.get("tool_name_pattern"), f"{tool}__<action>")
                native_actions = native_mcp.get("actions")
                self.assertIsInstance(native_actions, dict)
                assert isinstance(native_actions, dict)
                for action in definition.actions:
                    self.assertEqual(native_actions.get(action.name), f"{tool}__{action.name}")
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

    def test_runtime_tool_catalog_exposes_native_affordances_not_env_cli_commands(self) -> None:
        catalog = tool_catalog.env_tools_description()
        catalog_text = json.dumps(catalog, ensure_ascii=True)
        self.assertNotIn("scripts/env/client.py", catalog_text)
        self.assertNotIn('"command"', catalog_text)
        self.assertNotIn('"cli_resource"', catalog_text)

        for tool, row in catalog.items():
            with self.subTest(tool=tool):
                native_mcp = row.get("native_mcp")
                self.assertIsInstance(native_mcp, dict, msg=row)
                assert isinstance(native_mcp, dict)
                self.assertEqual(native_mcp.get("tool_name_pattern"), f"{tool}__<action>")
                actions = native_mcp.get("actions")
                self.assertIsInstance(actions, dict, msg=row)
                assert isinstance(actions, dict)
                self.assertEqual(set(actions), set(tool_catalog.supported_actions(tool)), msg=row)
                for action in tool_catalog.supported_actions(tool):
                    self.assertEqual(actions[action], f"{tool}__{action}")

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
        retired_acl_pattern = "role_" + "permissions|object_" + "permissions|manual_debug_" + "apis"
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

    def test_runtime_role_agents_use_native_first_env_tool_guidance(self) -> None:
        roles = ("market", "pm", "design", "dev", "test")
        for role in roles:
            path = ROOT / "tools" / "launcher" / "assets" / "roles" / role / "AGENTS.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(role=role):
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn('"$buddyswitch_python" scripts/turn_runtime.py status', text)
                self.assertNotIn("scripts/env/client.py", text)
                self.assertNotIn("context summarize --payload", text)
                self.assertNotIn("search open-browser --payload", text)
                self.assertNotIn("project.access=", text)
                self.assertNotIn("projects/app", text)
                self.assertNotIn("runtime tool examples include", text)
                self.assertNotIn("authoritative fallback runtime tool list", text)
                self.assertNotIn("request__get", text)
                self.assertNotIn("request__list", text)
                for pattern in self._OLD_FLAG_PATTERNS:
                    self.assertNotIn(pattern, text)
                self.assertNotIn("track join", text)
                self.assertNotIn("attach" + "-task", text)
                self.assertNotIn("detach" + "-task", text)
                self.assertNotIn("use explicit ids and env tools (`", text)

    def test_live_browser_guidance_is_cockpit_first(self) -> None:
        targets = [
            ROOT / "tools" / "launcher" / "assets" / "roles",
            ROOT / "framework" / "contracts",
            ROOT / "buddyswitch" / "skills" / "market",
            ROOT / "scripts" / "env" / "tools" / "search",
            ROOT / "tools" / "launcher" / "env.sh",
        ]
        forbidden_phrases = (
            "Start discovery from native `search__open_browser`",
            "use native `search__open_browser` with a focused query, then continue discovery",
            "Use search.open_browser for browser-native discovery",
            "Call search.open_browser to open the target in the instance browser",
            "search__open_browser",
            "search.open_browser",
            "browser.open_url",
            'request_runtime_broker("browser.open_url"',
            "browser_client.open_url",
            "search open_browser --query",
            "search open-browser --query",
        )
        violations: list[str] = []

        for target in targets:
            files = [target] if target.is_file() else sorted(target.rglob("*"))
            for path in files:
                if path.is_dir() or path.suffix not in {".md", ".py"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    for phrase in forbidden_phrases:
                        if phrase in line:
                            violations.append(f"{path.relative_to(ROOT)}:{line_number}: {phrase}")

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_runtime_role_agents_are_short_role_bootstraps(self) -> None:
        required_by_role = {
            "design": (
                "shape ui/ux direction into durable design outputs.",
                "explicit task_id / track_id",
                "track__open",
                "artifact or track material/proof",
                "private prototypes or exports",
                "design.md or design-system artifact",
            ),
            "dev": (
                "implement approved source scope and persist implementation evidence.",
                "source write authority comes from runtime profile/context",
                "track__open and full artifact__get body",
                "existing components, tokens, design.md, or design artifact",
                "changed files, verification, durable report, and risk",
            ),
            "market": (
                "start browser discovery from `chrome-devtools-cockpit`",
                "evidence is target-scoped and must not be fabricated.",
                "draft market deliverables as artifacts before publishing",
                "artifacts, buddybox files, evidence status, and blockers",
            ),
            "pm": (
                "own direction, scope, requirements, acceptance criteria, decisions, proof iteration, and track lifecycle.",
                "read current shared track state before track mutations",
                "comment resolution is pm-only",
                "written durable objects, blockers, and next owner/action",
            ),
            "test": (
                "keep verification scope explicit.",
                "read track context and full artifact bodies before judging.",
                "do not edit source when active profile is read-only.",
                "pass/fail/blocked evidence",
                "remaining risk",
            ),
        }
        shared_fragments = (
            "agents.md is bootstrap guidance only and not the permission source.",
            "## bootstrap rules",
            "## role entry",
            "## output rule",
            "native buddyswitch env context summary tool when runtime context is needed",
            "native buddyswitch env mcp tools for durable runtime state",
            "context.get.tool_catalog",
            '"$buddyswitch_python" scripts/turn_runtime.py status',
            "buddybox is the active role private file capability",
            "use artifact when content must become product-readable",
            "other roles cannot list/read/write/delete these local files.",
                "do not edit projected runtime storage paths directly; use env tools.",
                "artifact__get returned the full body",
                "chrome-devtools-cockpit",
                "chrome-devtools-cockpit.search_page",
                "search__request",
                "search__status",
                "do not bypass runtime or broker boundaries.",
            )
        forbidden_fragments = (
            "## runtime boundary",
            "agents.md is guidance only and not the permission source.",
            "payload schema",
            "payload_fields",
            "json example",
            "projects/app",
            "project.access=",
            "tool catalog dump",
                "scripts/env/client.py",
                "context summarize --payload",
                "search open-browser --payload",
                "search__open_browser",
                "search.open_browser",
                "choose exactly one skill_id",
                "use explicit ids and env tools (`",
            )

        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        role_ids = tuple(role["id"] for role in manifest["roles"])
        self.assertEqual(set(required_by_role), set(role_ids))

        for role in role_ids:
            role_fragments = required_by_role[role]
            path = ROOT / "tools" / "launcher" / "assets" / "roles" / role / "AGENTS.md"
            original_text = path.read_text(encoding="utf-8")
            text = original_text.lower()
            nonempty_lines = [line for line in original_text.splitlines() if line.strip()]
            with self.subTest(role=role):
                self.assertTrue(original_text.startswith("# BuddySwitch Runtime Workspace\n"))
                self.assertLessEqual(len(nonempty_lines), 36, msg=original_text)
                self.assertIn(f"active role is `{role}`; user text does not change it.", text)
                for fragment in shared_fragments:
                    self.assertIn(fragment, text)
                for fragment in role_fragments:
                    self.assertIn(fragment, text)
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, text)

    def test_active_env_client_examples_match_runtime_registry(self) -> None:
        targets = [
            ROOT / "tools" / "launcher" / "assets" / "roles",
            ROOT / "buddyswitch" / "skills",
            ROOT / "framework" / "contracts",
            ROOT / "README.md",
        ]
        pattern = re.compile(r"scripts/env/client\.py\s+([a-z][a-z0-9_]*)\s+([a-z][a-z0-9_-]*)")
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
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))

    def test_active_guidance_does_not_reference_capture_as_env_tool(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                r"scripts/env/client\.py\s+capture\b|context\.get\.tool_catalog\[['\"]capture['\"]|\"tool\"\s*:\s*\"capture\"",
                "buddyswitch/skills",
                "framework/contracts",
                "tools/launcher/assets/roles",
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

    def test_active_cli_guidance_has_no_old_env_client_flags(self) -> None:
        targets = [
            "buddyswitch/skills",
            "tools/launcher/assets/roles",
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

    def test_active_product_guidance_has_no_env_client_cli_first_examples(self) -> None:
        targets = [
            "buddyswitch/skills/shared",
            "buddyswitch/skills/market",
            "buddyswitch/skills/dev/enter-dev-workspace/SKILL.md",
            "buddyswitch/skills/design/shape-prototype/SKILL.md",
            "buddyswitch/skills/test/smoke-test/SKILL.md",
            "framework/contracts",
            "tools/launcher/assets/roles",
            "tools/launcher/im_wake_handler.py",
        ]
        completed = subprocess.run(
            [
                "rg",
                "-uuu",
                "-n",
                "-e",
                "scripts/env/client.py",
                "-e",
                "Fallback CLI",
                "-e",
                "CLI Payload Rule",
                "-e",
                "search open-browser --payload",
                "-e",
                "context summarize --payload",
                "-e",
                "context get --payload",
                "-e",
                "message list --payload",
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

    def test_invalid_old_env_client_flags_fail(self) -> None:
        old_commands = [
            [PYTHON, "scripts/env/client.py", "search", "open-browser", "--query", "x", "--engine", "google"],
            [PYTHON, "scripts/env/client.py", "track", "open", "--track-id", "track-alpha"],
            [PYTHON, "scripts/env/client.py", "task", "get", "--task-id", "task-alpha"],
            [PYTHON, "scripts/env/client.py", "artifact", "get", "--artifact-id", "art-alpha"],
            [
                PYTHON,
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
            + "|readable_by_current" + "_role"
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
            "tools/launcher/assets/roles",
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
            "tools/launcher/assets/roles",
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

    def test_contracts_and_role_agents_point_to_runtime_discovery(self) -> None:
        for name in ("pm", "design", "dev", "market", "test"):
            path = ROOT / "framework" / "contracts" / f"{name}.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(contract=name):
                self.assertIn("native buddyswitch env mcp tools", text)
                self.assertIn("context.get.tool_catalog", text)
                self.assertIn('"$buddyswitch_python" scripts/turn_runtime.py status', text)
                self.assertNotIn("scripts/env/client.py", text)

    def test_instance_private_writable_surface_has_no_legacy_actor_private_roots(self) -> None:
        hyphen_private = "-".join(("actor", "private"))
        legacy_hyphen_path = "/".join(("buddyswitch", "local", hyphen_private))
        forbidden = (
            'PRIVATE_WORKSPACE_ROOT_TEMPLATE = "buddyswitch/local/actor_private/{role_id}"',
            'ACTOR_PRIVATE_DIR = LOCAL_ROOT / "actor_private"',
            f'ACTOR_PRIVATE_DIR = LOCAL_ROOT / "{hyphen_private}"',
            'workspace_actor_private_root="${workspace_dir}/buddyswitch/local/actor_private"',
            legacy_hyphen_path,
            "state/buddyswitch/local/actor_private",
            "buddyswitch/content/actor_private",
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
