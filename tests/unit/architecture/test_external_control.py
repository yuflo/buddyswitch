"""Permanent architecture gates for external control interfaces."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.env.domain import task_read, track_read  # noqa: E402


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _constant_assignment(source: str, name: str) -> Any:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"missing constant assignment: {name}")


def _stripped_statements(source: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in source.splitlines() if line.strip())


def _contains_mapping_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_mapping_key(item, key) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_mapping_key(item, key) for item in value)
    return False


def _fold_static_string(node: ast.AST, names: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _fold_static_string(node.left, names)
        right = _fold_static_string(node.right, names)
        if left is not None and right is not None:
            return left + right
    return None


def _retired_public_literal_hits(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    names: dict[str, str] = {}
    pending = [node for node in tree.body if isinstance(node, ast.Assign)]
    while pending:
        unresolved: list[ast.Assign] = []
        changed = False
        for assignment in pending:
            value = _fold_static_string(assignment.value, names)
            targets = [target.id for target in assignment.targets if isinstance(target, ast.Name)]
            if value is None or not targets:
                unresolved.append(assignment)
                continue
            for target in targets:
                names[target] = value
            changed = True
        if not changed:
            break
        pending = unresolved

    retired = ("--" + "json", "--" + "output", "__" + "locked-")
    hits = {
        token
        for node in ast.walk(tree)
        if (value := _fold_static_string(node, names)) is not None
        for token in retired
        if token in value
    }
    return tuple(sorted(hits))


CANONICAL_LAUNCHER_STATEMENTS = (
    "#!/usr/bin/env bash",
    "set -euo pipefail",
    'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
    'RUNTIME_DIR="${BUDDYSWITCH_RUNTIME_DIR:-${SCRIPT_DIR}/.buddyswitch-runtime}"',
    "emit_runtime_unavailable() {",
    'local message="$1"',
    "printf '{\"ok\":false,\"error\":{\"code\":\"RUNTIME_UNAVAILABLE\",\"message\":\"%s\",\"details\":{}}}\\n' \"${message}\"",
    "exit 5",
    "}",
    'if [[ "${RUNTIME_DIR}" != /* ]]; then',
    'emit_runtime_unavailable "BUDDYSWITCH_RUNTIME_DIR must be an absolute path."',
    "fi",
    'if [[ ! -f "${RUNTIME_DIR}/activation.json" ]]; then',
    'emit_runtime_unavailable "Runtime activation.json is missing."',
    "fi",
    'if [[ ! -x "${RUNTIME_DIR}/venv/bin/python" ]]; then',
    'emit_runtime_unavailable "Runtime venv/bin/python is missing or not executable."',
    "fi",
    'export BUDDYSWITCH_RUNTIME_DIR="${RUNTIME_DIR}"',
    "unset BUDDYSWITCH_RUNTIME_IDENTITY",
    "unset BUDDYSWITCH_PACKAGE_ROOT",
    "unset BUDDYSWITCH_PROJECT_SOURCE",
    "unset BUDDYSWITCH_PYTHON",
    "unset BUDDYSWITCH_SOURCE_ROOT",
    'exec "${RUNTIME_DIR}/venv/bin/python" -I -m buddyswitch.application.entrypoints.cli "$@"',
)


class ExternalControlArchitectureTests(unittest.TestCase):
    def test_web_uses_private_owners_and_terminal_handoff_without_cli_execution(self) -> None:
        source = _source("src/buddyswitch/launcher/web_management.py")
        forbidden = (
            "Launcher" + "CommandRunner",
            "--" + "json",
            "/" + "side",
            'subprocess.run(["./buddy' + 'switch-codex"',
            'subprocess.Popen(["./buddy' + 'switch-codex"',
            "resolve_" + "attach",
            "terminal_command_from_" + "descriptor",
            "actor_session." + "ActorSession",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)
        self.assertIn("host_control_module.HostControl", source)
        self.assertIn("build_attach_cli_command", source)

    def test_actor_session_has_no_task_runtime_or_standalone_cli_entrypoint(self) -> None:
        source = _source("src/buddyswitch/launcher/actor_session.py")
        forbidden = (
            "task_" + "sys",
            "task_" + "id",
            "side_" + "frame",
            "side_" + "thread",
            "task_sys_" + "ingress",
            "task_sys_" + "runtime_client",
            "import " + "argparse",
            "build_" + "parser",
            "def " + "main(",
            "__" + "main__",
            "--" + "json",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_actor_environment_build_is_private_to_host_control(self) -> None:
        cli_source = _source("src/buddyswitch/launcher/cli.py")
        web_source = _source("src/buddyswitch/launcher/web_management.py")
        host_source = _source("src/buddyswitch/launcher/shell/host_control.sh")
        env_source = _source("src/buddyswitch/launcher/shell/env.sh")
        browser_source = _source("src/buddyswitch/launcher/shell/browser_cockpit.sh")
        start_block = host_source.split("start_locked_bootstrap() {", 1)[1].split(
            "instance_set_inactive_locked() {",
            1,
        )[0]
        resume_block = host_source.split("instance_resume_locked() {", 1)[1].split(
            "instance_stop() {",
            1,
        )[0]

        self.assertIn("host_control.HostControl", cli_source)
        self.assertIn("host_control_module.HostControl", web_source)
        self.assertNotIn("actor_environment", cli_source)
        self.assertNotIn("actor_environment", web_source)
        self.assertEqual(
            start_block.count("buddyswitch.application.entrypoints.actor_build"),
            1,
        )
        self.assertEqual(
            host_source.count("buddyswitch.application.entrypoints.actor_build"),
            1,
        )
        for forbidden in (
            "actor_environment.py",
            "--validate-existing",
            "buddyswitch_require_env_profile",
            "buddyswitch_require_role_agents_template",
        ):
            with self.subTest(resume_forbidden=forbidden):
                self.assertNotIn(forbidden, resume_block)
        self.assertNotIn("buddyswitch_workspace_", host_source)
        self.assertNotIn("buddyswitch_instance_ensure_private_writable_surface", env_source)
        self.assertNotIn("buddyswitch_prepare_actor_runtime_env", env_source)
        self.assertNotIn("buddyswitch_prepare_actor_runtime_env", browser_source)

    def test_public_launcher_is_only_the_canonical_python_bootstrap(self) -> None:
        source = _source("buddyswitch-codex")
        self.assertEqual(_stripped_statements(source), CANONICAL_LAUNCHER_STATEMENTS)

    def test_public_launcher_gate_rejects_control_dispatch_mutations(self) -> None:
        source = _source("buddyswitch-codex")
        canonical_exec = CANONICAL_LAUNCHER_STATEMENTS[-1]
        mutations = (
            source.replace(canonical_exec, 'case "$1" in start) exit 0 ;; esac\n' + canonical_exec),
            source.replace(canonical_exec, 'shift\n' + canonical_exec),
            source.replace(canonical_exec, 'getopts "x" option\n' + canonical_exec),
            source.replace(canonical_exec, 'exec "${SCRIPT_DIR}/host_control.sh" "$@"\n' + canonical_exec),
        )
        for mutation in mutations:
            with self.subTest(mutation=_stripped_statements(mutation)[-2]):
                self.assertNotEqual(_stripped_statements(mutation), CANONICAL_LAUNCHER_STATEMENTS)

    def test_replaced_helper_entrypoints_and_dedicated_tests_are_absent(self) -> None:
        deleted = (
            "src/buddyswitch/launcher/" + "instance.sh",
            "src/buddyswitch/launcher/" + "workspace.sh",
            "src/buddyswitch/launcher/" + "submit_turn.py",
            "src/buddyswitch/launcher/" + "parent_thread_" + "submit.py",
            "src/buddyswitch/launcher/" + "actor_capability_" + "cli.py",
            "tests/test_" + "submit_turn.py",
            "tests/test_parent_thread_" + "submit.py",
            "tests/test_actor_capability_" + "cli.py",
            "tests/system/instance_lifecycle/test_" + "worktree_safety.py",
        )
        self.assertEqual([path for path in deleted if (ROOT / path).exists()], [])

    def test_public_cli_and_help_have_no_retired_command_families_or_output_tracks(self) -> None:
        source = _source("src/buddyswitch/launcher/cli.py")
        tree = ast.parse(source)
        help_text = _constant_assignment(source, "_HELP_TEMPLATE")
        forbidden_source = (
            "legacy_" + "command_hint",
            "fail_removed_" + "public_command",
            "_print_" + "human_result",
            "__" + "locked-",
            "REMOVED_" + "JSON_FLAG",
            "REMOVED_" + "OUTPUT_FLAG",
            "_reject_removed_" + "public_flags",
            "_is_instance_" + "input_text_value",
        )
        for token in forbidden_source:
            with self.subTest(surface="source", token=token):
                self.assertNotIn(token, source)
        self.assertEqual(_retired_public_literal_hits(source), ())
        dispatch = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_dispatch"
        )
        command_prefix_checks = [
            node
            for node in ast.walk(dispatch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "startswith"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "command"
        ]
        self.assertEqual(command_prefix_checks, [])
        mutations = (
            source.replace(
                "    command, rest = args[0], args[1:]\n",
                "    command, rest = args[0], args[1:]\n"
                "    if command == \"__\" + \"locked-reset\":\n"
                "        raise RuntimeError(command)\n",
                1,
            ),
            source.replace(
                "        result = _dispatch(args, commands=commands, help_text=help_text)\n",
                "        if any(arg == \"--\" + \"json\" for arg in args):\n"
                "            raise RuntimeError(args)\n"
                "        result = _dispatch(args, commands=commands, help_text=help_text)\n",
                1,
            ),
            source.replace(
                'YES_FLAG = DASH + "yes"\n',
                'RETIRED_PREFIX = "--"\nRETIRED_NAME = "output"\nYES_FLAG = DASH + "yes"\n',
                1,
            ).replace(
                "        result = _dispatch(args, commands=commands, help_text=help_text)\n",
                "        if any(arg == RETIRED_PREFIX + RETIRED_NAME for arg in args):\n"
                "            raise RuntimeError(args)\n"
                "        result = _dispatch(args, commands=commands, help_text=help_text)\n",
                1,
            ),
        )
        expected_hits = ("__" + "locked-", "--" + "json", "--" + "output")
        for mutation, expected_hit in zip(mutations, expected_hits, strict=True):
            self.assertIn(expected_hit, _retired_public_literal_hits(mutation))
        forbidden_help = (
            "instance " + "side",
            "instance " + "goal",
            "  " + "side ",
            "  " + "goal ",
            "  " + "im ",
            "Side " + "thread",
            "Goal " + "command",
            "IM " + "command",
            "--" + "output human",
            "--" + "json",
            "__" + "locked-",
        )
        for token in forbidden_help:
            with self.subTest(surface="help", token=token):
                self.assertNotIn(token, help_text)

    def test_external_task_and_track_projections_have_exact_allowlists(self) -> None:
        task_record = {
            "schema_version": 1,
            "id": "task-demo",
            "demand_ref": {
                "demand_id": "demand-external-control",
                "basis_revision": 1,
                "demand_ref": "dref-external-control",
            },
            "objective": "Deliver the external-control projection.",
            "selection": {"reason": "Projection test.", "selected_at": "2026-07-14T00:00:00Z"},
            "goal_binding": None,
            "status": "active",
            "result": None,
            "actor_target": {"actor_id": "act-pm-demo", "role_id": "pm", "secret": True},
            "created_at": "2026-07-14T00:00:00Z",
            "updated_at": "2026-07-14T00:00:00Z",
            "secret": True,
        }
        track_record = {
            "id": "track-demo",
            "title": "Demo",
            "outcome": "Done",
            "owner_identity_id": "act-pm-demo",
            "state": "active",
            "now": {"next": "Verify", "blocker": None, "secret": True},
            "acceptance_criteria": ["Exact"],
            "non_goals": ["Mutation"],
            "updated_at": "2026-07-14T00:00:00Z",
            "artifact_relations": [
                {"role": "material", "artifact_id": "artifact-demo", "secret": True, "repo_path": "/private"}
            ],
            "updates": [
                {
                    "id": "update-demo",
                    "refs": [
                        {"type": "artifact", "id": "artifact-demo", "secret": True, "repo_path": "/private"}
                    ],
                    "secret": True,
                    "repo_path": "/private",
                }
            ],
            "secret": True,
            "repo_path": "/private",
        }
        comments = [
            {
                "id": "comment-demo",
                "track_id": "track-demo",
                "thread_id": "thread-demo",
                "by_identity_id": "act-pm-demo",
                "content": "Visible",
                "reply_to": None,
                "mentioned_identity_ids": [],
                "status": "open",
                "created_at": "2026-07-14T00:00:00Z",
                "secret": True,
                "repo_path": "/private",
            }
        ]

        with mock.patch.object(task_read.task_sys, "list_tasks", return_value=[task_record]), mock.patch.object(
            task_read.task_sys,
            "get_task",
            return_value=task_record,
        ), mock.patch.object(track_read.track_repo, "list_tracks", return_value=[track_record]), mock.patch.object(
            track_read.track_repo,
            "get_track",
            return_value=track_record,
        ), mock.patch.object(track_read.track_comment_repo, "comments_for_track", return_value=comments):
            tasks = task_read.list_external_tasks()
            task = task_read.get_external_task("task-demo")
            tracks = track_read.list_external_tracks()
            track = track_read.get_external_track("track-demo")

        task_keys = (
            "task_id",
            "demand_ref",
            "objective",
            "selection",
            "goal_binding",
            "status",
            "result",
            "actor",
            "updated_at",
        )
        for row in (*tasks, task):
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(tuple(row), task_keys)
            self.assertEqual(tuple(row["actor"]), ("actor_id", "role_id"))
            self.assertEqual(
                row["demand_ref"],
                {
                    "demand_id": "demand-external-control",
                    "demand_ref": "dref-external-control",
                },
            )

        track_summary_keys = (
            "id",
            "title",
            "outcome",
            "owner_identity_id",
            "state",
            "now",
            "acceptance_criteria",
            "non_goals",
            "updated_at",
            "comment_summary",
        )
        for row in tracks:
            self.assertEqual(tuple(row), track_summary_keys)
            self.assertEqual(tuple(row["now"]), ("next", "blocker"))
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(
            tuple(track),
            (*track_summary_keys, "materials", "proofs", "updates", "comment_threads"),
        )
        self.assertEqual(tuple(track["now"]), ("next", "blocker"))
        self.assertEqual(
            tuple(track["materials"][0]),
            (
                "type",
                "relation_id",
                "artifact_id",
                "role",
                "label",
                "template",
                "from_identity_id",
                "summary",
                "current",
                "created_at",
            ),
        )
        self.assertEqual(
            tuple(track["updates"][0]),
            ("id", "by_identity_id", "summary", "kind", "refs", "created_at"),
        )
        self.assertEqual(tuple(track["updates"][0]["refs"][0]), ("type", "id"))
        self.assertEqual(
            tuple(track["comment_threads"][0]["comments"][0]),
            (
                "id",
                "track_id",
                "thread_id",
                "by_identity_id",
                "content",
                "reply_to",
                "mentioned_identity_ids",
                "status",
                "created_at",
                "resolved_by_identity_id",
                "resolved_at",
                "resolution_summary",
            ),
        )

        for payload in (tasks, task, tracks, track):
            for private_key in ("secret", "repo_path"):
                self.assertFalse(_contains_mapping_key(payload, private_key))

        web_source = _source("src/buddyswitch/launcher/web_management.py")
        self.assertIn("task_read.actor_external_task_projection", web_source)
        self.assertNotIn("task_" + "sys.actor_task_projection", web_source)

    def test_durable_architecture_names_the_final_single_track_boundaries(self) -> None:
        document = _source("docs/arch/web-interface-call-architecture.md")
        required = (
            "Web and the public CLI are peer adapters",
            "private Host Control",
            "Actor Session owns direct parent-thread input and attach resolution.",
            "Browser -> Web Open TUI -> Terminal -> public CLI attach -> Actor Session",
            "`/api/im/*` is the single browser-facing Message contract.",
            "Demand, Task, and Track reads to external-safe domain projections",
            "Web to Actor runtime mutation tools for console reads",
            "Web or CLI to native Goal mutation",
            "Actor Session to Demand or Task mutation",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, document)
        for token in ("migration", "compatibility", "phase one", "phase two"):
            with self.subTest(token=token):
                self.assertNotIn(token, document.lower())
