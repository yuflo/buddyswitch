"""Tests for the BuddySwitch private Host Control owner."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.launcher import actor_capability
from tools.launcher import host_control as HOST_CONTROL


ROOT = Path(__file__).resolve().parents[1]


def valid_role_row() -> dict[str, object]:
    return {"id": "pm", "label": "PM", "scope": "product"}


def valid_instance_row() -> dict[str, object]:
    return {
        "actor_id": "act-pm-demo",
        "role": "pm",
        "status": "active",
        "app_server_health": "healthy",
        "thread_id": "thread-main",
        "browser_port": 9222,
        "updated_at": "2026-07-13T00:00:00Z",
        "workspace_dir": "/tmp/workspace",
    }


def write_instance(
    shared_root: Path,
    *,
    actor_id: str = "act-pm-demo",
    role: str = "pm",
) -> Path:
    instance_root = shared_root / "instances" / actor_id
    instance_root.mkdir(parents=True, exist_ok=True)
    instance_json = instance_root / "instance.json"
    instance_json.write_text(
        json.dumps(
            {
                "actor_id": actor_id,
                "role": role,
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(instance_root / "workspace"),
                "thread_id": "thread-main",
                "browser_port": 9222,
                "updated_at": "2026-07-13T00:00:00Z",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    actor_capability.seed_actor_capabilities(instance_json)
    return instance_json


class FakePrivateRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], float]] = []
        self.responses: dict[tuple[str, tuple[str, ...]], dict[str, object]] = {}

    def add(self, operation: str, args: list[str], payload: dict[str, object]) -> None:
        self.responses[(operation, tuple(args))] = payload

    def run(self, operation: str, args: list[str], *, timeout_seconds: float) -> dict[str, object]:
        self.calls.append((operation, tuple(args), timeout_seconds))
        key = (operation, tuple(args))
        if key not in self.responses:
            raise AssertionError(f"unexpected host control call: {key!r}")
        return self.responses[key]


class HostControlTests(unittest.TestCase):
    def test_public_facade_exposes_exact_host_control_operations(self) -> None:
        expected = {
            "roles": ["self"],
            "start": ["self", "role_id"],
            "list_instances": ["self", "role_id"],
            "status": ["self", "actor_id"],
            "clear": ["self", "actor_id"],
            "resume": ["self", "actor_id"],
            "stop": ["self", "actor_id"],
            "delete": ["self", "actor_id"],
            "interrupt": ["self", "actor_id"],
            "compact": ["self", "actor_id"],
            "capabilities_get": ["self", "actor_id"],
            "capabilities_set": ["self", "actor_id", "parent", "side"],
        }
        for name, parameters in expected.items():
            with self.subTest(name=name):
                method = getattr(HOST_CONTROL.HostControl, name)
                self.assertEqual(list(inspect.signature(method).parameters), parameters)

    def test_facade_invokes_fixed_private_operations_and_returns_data(self) -> None:
        runner = FakePrivateRunner()
        role_row = valid_role_row()
        instance_row = valid_instance_row()
        runner.add("roles", [], {"roles": [role_row]})
        runner.add(
            "start",
            ["pm"],
            {
                "actor_id": "act-pm-demo",
                "role": "pm",
                "workspace_dir": "/tmp/workspace",
                "project_workspace_dir": "/tmp/project/workspace",
                "instance_record": "/tmp/instances/act-pm-demo/instance.json",
            },
        )
        runner.add("list", [], {"instances": [instance_row]})
        runner.add("list", ["pm"], {"instances": [instance_row]})
        runner.add(
            "status",
            ["act-pm-demo"],
            {
                "actor_id": "act-pm-demo",
                "role": "pm",
                "status": "active",
                "workspace_dir": "/tmp/workspace",
                "browser_port": None,
                "updated_at": "2026-07-13T00:00:00Z",
                "thread_id": "thread-main",
                "app_server": {},
                "daemon": {},
                "runtime_broker": {},
                "thread": {},
            },
        )
        runner.add(
            "clear",
            ["act-pm-demo"],
            {"actor_id": "act-pm-demo", "previous_thread_id": "thread-old", "thread_id": "thread-new"},
        )
        runner.add("resume", ["act-pm-demo"], {"actor_id": "act-pm-demo", "thread_id": "thread-main", "status": "active"})
        runner.add("stop", ["act-pm-demo"], {"actor_id": "act-pm-demo", "status": "inactive"})
        runner.add("delete", ["act-pm-demo"], {"actor_id": "act-pm-demo", "deleted": True})
        runner.add("interrupt", ["act-pm-demo"], {"actor_id": "act-pm-demo", "thread_id": "thread-main", "turn_id": "turn-1"})
        runner.add("compact", ["act-pm-demo"], {"actor_id": "act-pm-demo", "thread_id": "thread-main", "started": True})
        control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)

        roles = control.roles()
        started = control.start("pm")
        instances = control.list_instances()
        self.assertEqual(roles, [role_row])
        self.assertEqual(started["actor_id"], "act-pm-demo")
        self.assertEqual(instances, [instance_row])
        self.assertEqual(control.list_instances("pm"), [instance_row])
        self.assertEqual(control.status("act-pm-demo")["status"], "active")
        self.assertEqual(control.clear("act-pm-demo")["thread_id"], "thread-new")
        self.assertEqual(control.resume("act-pm-demo")["status"], "active")
        self.assertEqual(control.stop("act-pm-demo")["status"], "inactive")
        self.assertEqual(control.delete("act-pm-demo")["deleted"], True)
        self.assertEqual(control.interrupt("act-pm-demo")["turn_id"], "turn-1")
        self.assertEqual(control.compact("act-pm-demo")["started"], True)
        self.assertIsNot(roles[0], role_row)
        self.assertIsNot(instances[0], instance_row)

        self.assertEqual(
            [(operation, args) for operation, args, _timeout in runner.calls],
            [
                ("roles", ()),
                ("start", ("pm",)),
                ("list", ()),
                ("list", ("pm",)),
                ("status", ("act-pm-demo",)),
                ("clear", ("act-pm-demo",)),
                ("resume", ("act-pm-demo",)),
                ("stop", ("act-pm-demo",)),
                ("delete", ("act-pm-demo",)),
                ("interrupt", ("act-pm-demo",)),
                ("compact", ("act-pm-demo",)),
            ],
        )

    def test_facade_rejects_malformed_role_and_instance_list_rows(self) -> None:
        role_payloads = [
            ({**valid_role_row(), field_name: wrong_value}, field_name)
            for field_name, wrong_value in (
                ("id", ""),
                ("label", None),
                ("scope", 123),
            )
        ]
        role_payloads.append(({}, "id"))
        instance_payloads = [
            ({**valid_instance_row(), field_name: wrong_value}, field_name)
            for field_name, wrong_value in (
                ("actor_id", ""),
                ("role", None),
                ("status", 123),
                ("app_server_health", False),
                ("updated_at", ""),
                ("workspace_dir", []),
                ("thread_id", 9222),
                ("browser_port", True),
            )
        ]
        instance_payloads.append(({}, "actor_id"))

        for row, field_name in role_payloads:
            with self.subTest(operation="roles", row=row):
                runner = FakePrivateRunner()
                runner.add("roles", [], {"roles": [row]})
                control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)
                with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                    control.roles()
                self.assertEqual(raised.exception.code, "COMMAND_FAILED")
                self.assertIn(field_name, raised.exception.message)

        for row, field_name in instance_payloads:
            with self.subTest(operation="list", row=row):
                runner = FakePrivateRunner()
                runner.add("list", [], {"instances": [row]})
                control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)
                with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                    control.list_instances()
                self.assertEqual(raised.exception.code, "COMMAND_FAILED")
                self.assertIn(field_name, raised.exception.message)

    def test_facade_validates_actor_and_role_inputs_before_private_runner(self) -> None:
        runner = FakePrivateRunner()
        control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)

        for call in (lambda: control.start("../pm"), lambda: control.start("--bad"), lambda: control.status("pm-demo")):
            with self.subTest(call=call):
                with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_facade_rejects_malformed_lifecycle_payloads(self) -> None:
        valid_payloads = {
            "start": (
                lambda control: control.start("pm"),
                ["pm"],
                {
                    "actor_id": "act-pm-demo",
                    "role": "pm",
                    "workspace_dir": "/tmp/workspace",
                    "project_workspace_dir": "/tmp/project/workspace",
                    "instance_record": "/tmp/instances/act-pm-demo/instance.json",
                },
                "workspace_dir",
                123,
            ),
            "status": (
                lambda control: control.status("act-pm-demo"),
                ["act-pm-demo"],
                {
                    "actor_id": "act-pm-demo",
                    "role": "pm",
                    "status": "active",
                    "workspace_dir": "/tmp/workspace",
                    "browser_port": None,
                    "updated_at": "2026-07-13T00:00:00Z",
                    "thread_id": "thread-main",
                    "app_server": {},
                    "daemon": {},
                    "runtime_broker": {},
                    "thread": {},
                },
                "app_server",
                "not-object",
            ),
            "clear": (
                lambda control: control.clear("act-pm-demo"),
                ["act-pm-demo"],
                {"actor_id": "act-pm-demo", "previous_thread_id": "thread-old", "thread_id": "thread-new"},
                "previous_thread_id",
                None,
            ),
            "resume": (
                lambda control: control.resume("act-pm-demo"),
                ["act-pm-demo"],
                {"actor_id": "act-pm-demo", "thread_id": "thread-main", "status": "active"},
                "thread_id",
                [],
            ),
            "stop": (
                lambda control: control.stop("act-pm-demo"),
                ["act-pm-demo"],
                {"actor_id": "act-pm-demo", "status": "inactive"},
                "status",
                False,
            ),
            "delete": (
                lambda control: control.delete("act-pm-demo"),
                ["act-pm-demo"],
                {"actor_id": "act-pm-demo", "deleted": True},
                "deleted",
                "yes",
            ),
            "interrupt": (
                lambda control: control.interrupt("act-pm-demo"),
                ["act-pm-demo"],
                {"actor_id": "act-pm-demo", "thread_id": "thread-main", "turn_id": "turn-1"},
                "thread_id",
                42,
            ),
            "compact": (
                lambda control: control.compact("act-pm-demo"),
                ["act-pm-demo"],
                {"actor_id": "act-pm-demo", "thread_id": "thread-main", "started": True},
                "started",
                None,
            ),
        }

        for operation, (call, args, valid_payload, field_name, wrong_value) in valid_payloads.items():
            for payload in (self._without_field(valid_payload, field_name), {**valid_payload, field_name: wrong_value}):
                with self.subTest(operation=operation, payload=payload):
                    runner = FakePrivateRunner()
                    runner.add(operation, args, payload)
                    control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)
                    with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                        call(control)
                    self.assertEqual(raised.exception.code, "COMMAND_FAILED")
                    self.assertIn(field_name, raised.exception.message)

    def test_capabilities_use_actor_capability_core_without_private_shell(self) -> None:
        original_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"
            instance_json = write_instance(shared_root)
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            self.addCleanup(self._restore_env_value, "BUDDYSWITCH_SHARED_ROOT", original_shared_root)
            runner = FakePrivateRunner()
            control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)

            get_payload = control.capabilities_get("act-pm-demo")
            set_payload = control.capabilities_set("act-pm-demo", "deep", "maximum")
            parent = actor_capability.resolve_parent_capability(instance_json)
            side = actor_capability.resolve_side_capability(instance_json)

            self.assertEqual(get_payload["actor_id"], "act-pm-demo")
            self.assertEqual(get_payload["capabilities"]["parent"]["level"], "balanced")
            self.assertEqual(set_payload["capabilities"]["parent"]["level"], "deep")
            self.assertEqual((parent.level, side.level), ("deep", "maximum"))
            self.assertEqual(runner.calls, [])

    def test_private_runner_executes_only_host_control_script(self) -> None:
        runner_signature = inspect.signature(HOST_CONTROL._HostControlScriptRunner)
        self.assertNotIn("executable", runner_signature.parameters)
        self.assertNotIn("argv", runner_signature.parameters)
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"actor_id": "act-pm-demo"}, ensure_ascii=True),
            stderr="",
        )
        with mock.patch.object(HOST_CONTROL.subprocess, "run", return_value=completed) as run:
            payload = HOST_CONTROL._HostControlScriptRunner(repo_root=ROOT).run(
                "status",
                ["act-pm-demo"],
                timeout_seconds=12,
            )

        self.assertEqual(payload, {"actor_id": "act-pm-demo"})
        command = run.call_args.args[0]
        self.assertEqual(command, [str(ROOT / "tools" / "launcher" / "host_control.sh"), "status", "act-pm-demo"])

    def test_private_runner_normalizes_json_error_payloads(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=3,
            stdout=json.dumps(
                {"error": {"code": "LIFECYCLE_BLOCKED", "message": "Instance delete blocked."}},
                ensure_ascii=True,
            ),
            stderr="",
        )
        with mock.patch.object(HOST_CONTROL.subprocess, "run", return_value=completed):
            with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                HOST_CONTROL._HostControlScriptRunner(repo_root=ROOT).run(
                    "delete",
                    ["act-pm-demo"],
                    timeout_seconds=12,
                )

        self.assertEqual(raised.exception.code, "LIFECYCLE_BLOCKED")
        self.assertEqual(raised.exception.message, "Instance delete blocked.")
        self.assertEqual(raised.exception.returncode, 3)

    def test_host_control_script_is_private_json_only_no_public_parser_residue(self) -> None:
        source = (ROOT / "tools" / "launcher" / "host_control.sh").read_text(encoding="utf-8")
        forbidden = [
            "print_help",
            "json=0",
            "Unknown instance",
            "BuddySwitch instance:",
            "Thread cleared:",
            "Instance stopped:",
            "Instance deleted:",
            "No BuddySwitch instances found.",
            "BuddySwitch instance delete preview",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)
        self.assertNotRegex(source, r"\b--json\)")

    def test_host_control_script_start_uses_positional_private_role(self) -> None:
        completed = subprocess.run(
            [str(ROOT / "tools" / "launcher" / "host_control.sh"), "start", "--bad"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertIn("Invalid role id", payload["error"]["message"])

    def test_host_control_main_keeps_success_warnings_off_stdout(self) -> None:
        script = """
source "$1"
host_control_run_raw_operation() {
  printf '%s\n' 'non-fatal warning' >&2
  printf '%s\n' '{"ok":true}'
}
host_control_main warning-test
"""
        completed = subprocess.run(
            ["/bin/bash", "-c", script, "host-control-main-test", str(ROOT / "tools" / "launcher" / "host_control.sh")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"ok": True})
        self.assertEqual(completed.stdout, '{"ok":true}\n')
        self.assertEqual(completed.stderr, "non-fatal warning\n")

    @staticmethod
    def _restore_env_value(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    @staticmethod
    def _without_field(payload: dict[str, object], field_name: str) -> dict[str, object]:
        copied = dict(payload)
        copied.pop(field_name)
        return copied
