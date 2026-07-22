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
from tools.launcher import codex_runtime
from tools.launcher import host_control as HOST_CONTROL


from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
TEST_RUNTIME = codex_runtime.CodexRuntime(
    executable=Path("/opt/buddyswitch/codex"),
    version="codex-cli test-runtime",
)


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
        "last_failure": None,
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
    codex_bin = shared_root / "test-runtime" / "codex"
    codex_bin.parent.mkdir(parents=True, exist_ok=True)
    codex_bin.write_text("#!/bin/sh\nprintf '%s\\n' 'codex-cli test-runtime'\n", encoding="utf-8")
    codex_bin.chmod(0o755)
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
                "codex_runtime": {
                    "executable": str(codex_bin.resolve(strict=False)),
                    "version": "codex-cli test-runtime",
                },
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
        self.errors: dict[tuple[str, tuple[str, ...]], HOST_CONTROL.HostControlError] = {}

    def add(self, operation: str, args: list[str], payload: dict[str, object]) -> None:
        self.responses[(operation, tuple(args))] = payload

    def add_error(self, operation: str, args: list[str], error: HOST_CONTROL.HostControlError) -> None:
        self.errors[(operation, tuple(args))] = error

    def run(self, operation: str, args: list[str], *, timeout_seconds: float) -> dict[str, object]:
        self.calls.append((operation, tuple(args), timeout_seconds))
        key = (operation, tuple(args))
        if key in self.errors:
            raise self.errors[key]
        if key not in self.responses:
            raise AssertionError(f"unexpected host control call: {key!r}")
        return self.responses[key]


class HostControlTests(unittest.TestCase):
    @staticmethod
    def _failed_status(actor_id: str = "act-pm-failed") -> dict[str, object]:
        return {
            "actor_id": actor_id,
            "role": "pm",
            "status": "inactive",
            "workspace_dir": f"/tmp/instances/{actor_id}/workspace",
            "browser_port": None,
            "updated_at": "2026-07-18T00:00:00Z",
            "thread_id": None,
            "codex_runtime": TEST_RUNTIME.to_record(),
            "last_failure": {
                "phase": "daemon_start",
                "message": "Daemon start failed.",
                "failed_at": "2026-07-18T00:00:00Z",
            },
            "app_server": {},
            "daemon": {},
            "runtime_broker": {},
            "thread": {},
        }

    def test_instance_list_skips_record_removed_after_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"
            missing_instance_json = shared_root / "instances" / "act-pm-gone" / "instance.json"
            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            completed = run_process(
                [
                    "bash",
                    "-c",
                    "\n".join(
                        [
                            'source "$1"',
                            'missing_instance_json="$2"',
                            'buddyswitch_instance_json_files() { printf \'%s\\n\' "${missing_instance_json}"; }',
                            "buddyswitch_instance_list",
                        ]
                    ),
                    "bash",
                    str(ROOT / "tools" / "launcher" / "host_control.sh"),
                    str(missing_instance_json),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"instances": []})

    def test_start_uses_owner_allocated_actor_id_at_every_private_boundary(self) -> None:
        runner = FakePrivateRunner()
        runtime = codex_runtime.CodexRuntime(
            executable=Path("/opt/buddyswitch/codex"),
            version="codex-cli test-runtime",
        )
        control = HOST_CONTROL.HostControl(
            repo_root=ROOT,
            runner=runner,
            runtime_resolver=lambda: runtime,
        )

        self.assertTrue(
            hasattr(control, "allocate_actor_id"),
            "Host Control must allocate the actor id before Start is enqueued.",
        )
        with mock.patch.object(
            HOST_CONTROL,
            "uuid4",
            return_value=mock.Mock(hex="0123456789abcdef0123456789abcdef"),
        ):
            actor_id = control.allocate_actor_id("pm")
        runner.add(
            "start",
            ["pm", str(runtime.executable), runtime.version, actor_id],
            {
                "actor_id": actor_id,
                "role": "pm",
                "workspace_dir": "/tmp/workspace",
                "project_workspace_dir": "/tmp/project/workspace",
                "instance_record": f"/tmp/instances/{actor_id}/instance.json",
            },
        )

        payload = control.start("pm", actor_id=actor_id)

        self.assertEqual(actor_id, "act-pm-0123456789ab")
        self.assertEqual(payload["actor_id"], actor_id)
        self.assertEqual(
            [(operation, args) for operation, args, _timeout in runner.calls],
            [
                (
                    "start",
                    ("pm", "/opt/buddyswitch/codex", "codex-cli test-runtime", actor_id),
                )
            ],
        )

    def test_start_rejects_private_result_with_different_actor_id(self) -> None:
        runner = FakePrivateRunner()
        runtime = codex_runtime.CodexRuntime(
            executable=Path("/opt/buddyswitch/codex"),
            version="codex-cli test-runtime",
        )
        control = HOST_CONTROL.HostControl(
            repo_root=ROOT,
            runner=runner,
            runtime_resolver=lambda: runtime,
        )
        self.assertIn(
            "actor_id",
            inspect.signature(control.start).parameters,
            "Start must accept the owner-issued actor id.",
        )
        runner.add(
            "start",
            [
                "pm",
                str(runtime.executable),
                runtime.version,
                "act-pm-expected",
            ],
            {
                "actor_id": "act-pm-different",
                "role": "pm",
                "workspace_dir": "/tmp/workspace",
                "project_workspace_dir": "/tmp/project/workspace",
                "instance_record": "/tmp/instances/act-pm-different/instance.json",
            },
        )

        with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
            control.start("pm", actor_id="act-pm-expected")

        self.assertEqual(raised.exception.code, "COMMAND_FAILED")
        self.assertIn("actor id mismatch", raised.exception.message.lower())

    def test_prepare_retry_requires_inactive_start_failure_and_allocates_same_role_replacement(self) -> None:
        accepted_runner = FakePrivateRunner()
        accepted_runner.add("status", ["act-pm-failed"], self._failed_status())
        control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=accepted_runner)
        self.assertTrue(hasattr(control, "prepare_retry"), "Host Control must own Retry preparation.")
        with mock.patch.object(
            HOST_CONTROL,
            "uuid4",
            return_value=mock.Mock(hex="abcdef0123456789abcdef0123456789"),
        ):
            prepared = control.prepare_retry("act-pm-failed")

        self.assertEqual(
            prepared,
            {
                "actor_id": "act-pm-failed",
                "replacement_actor_id": "act-pm-abcdef012345",
                "role": "pm",
            },
        )

        for name, status, failure in (
            ("active", "active", self._failed_status()["last_failure"]),
            ("stopped", "inactive", None),
        ):
            with self.subTest(name=name):
                runner = FakePrivateRunner()
                runner.add(
                    "status",
                    ["act-pm-failed"],
                    dict(self._failed_status(), status=status, last_failure=failure),
                )
                with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                    HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner).prepare_retry("act-pm-failed")
                self.assertEqual(raised.exception.code, "LIFECYCLE_BLOCKED")

        missing_runner = FakePrivateRunner()
        missing_runner.add_error(
            "status",
            ["act-pm-missing"],
            HOST_CONTROL.HostControlError("NOT_FOUND", "actor instance not found: act-pm-missing"),
        )
        with self.assertRaises(HOST_CONTROL.HostControlError) as missing:
            HOST_CONTROL.HostControl(repo_root=ROOT, runner=missing_runner).prepare_retry("act-pm-missing")
        self.assertEqual(missing.exception.code, "NOT_FOUND")

        malformed_runner = FakePrivateRunner()
        malformed_runner.add(
            "status",
            ["act-pm-failed"],
            dict(self._failed_status(), role="../pm"),
        )
        with self.assertRaises(HOST_CONTROL.HostControlError) as malformed:
            HOST_CONTROL.HostControl(repo_root=ROOT, runner=malformed_runner).prepare_retry("act-pm-failed")
        self.assertEqual(malformed.exception.code, "COMMAND_FAILED")
        self.assertIn("role", malformed.exception.message)

    def test_retry_revalidates_then_deletes_before_starting_same_role_with_replacement_id(self) -> None:
        runner = FakePrivateRunner()
        replacement_actor_id = "act-pm-replacement"
        runner.add("status", ["act-pm-failed"], self._failed_status())
        runner.add("delete", ["act-pm-failed"], {"actor_id": "act-pm-failed", "deleted": True})
        runner.add(
            "start",
            ["pm", str(TEST_RUNTIME.executable), TEST_RUNTIME.version, replacement_actor_id],
            {
                "actor_id": replacement_actor_id,
                "role": "pm",
                "workspace_dir": f"/tmp/instances/{replacement_actor_id}/workspace",
                "project_workspace_dir": "/tmp/project/workspace",
                "instance_record": f"/tmp/instances/{replacement_actor_id}/instance.json",
            },
        )
        control = HOST_CONTROL.HostControl(
            repo_root=ROOT,
            runner=runner,
            runtime_resolver=lambda: TEST_RUNTIME,
        )
        self.assertTrue(hasattr(control, "retry"), "Host Control must compose Retry.")

        payload = control.retry("act-pm-failed", replacement_actor_id)

        self.assertEqual(payload["previous_actor_id"], "act-pm-failed")
        self.assertEqual(payload["actor_id"], replacement_actor_id)
        self.assertEqual(
            [(operation, args) for operation, args, _timeout in runner.calls],
            [
                ("status", ("act-pm-failed",)),
                ("delete", ("act-pm-failed",)),
                (
                    "start",
                    ("pm", str(TEST_RUNTIME.executable), TEST_RUNTIME.version, replacement_actor_id),
                ),
            ],
        )

    def test_retry_delete_failure_does_not_start(self) -> None:
        runner = FakePrivateRunner()
        runner.add("status", ["act-pm-failed"], self._failed_status())
        runner.add_error(
            "delete",
            ["act-pm-failed"],
            HOST_CONTROL.HostControlError("COMMAND_FAILED", "Delete failed."),
        )
        control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)

        with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
            control.retry("act-pm-failed", "act-pm-replacement")

        self.assertEqual(raised.exception.message, "Delete failed.")
        self.assertEqual([call[0] for call in runner.calls], ["status", "delete"])

    def test_retry_rejects_nonfresh_or_wrong_role_replacement_before_delete(self) -> None:
        for replacement_actor_id in ("act-pm-failed", "act-dev-replacement"):
            with self.subTest(replacement_actor_id=replacement_actor_id):
                runner = FakePrivateRunner()
                runner.add("status", ["act-pm-failed"], self._failed_status())
                control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)

                with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                    control.retry("act-pm-failed", replacement_actor_id)

                self.assertEqual(raised.exception.code, "INVALID_REQUEST")
                self.assertEqual([call[0] for call in runner.calls], ["status"])

    def test_retry_start_failure_keeps_delete_effect_without_restoring_old_actor(self) -> None:
        runner = FakePrivateRunner()
        replacement_actor_id = "act-pm-replacement"
        runner.add("status", ["act-pm-failed"], self._failed_status())
        runner.add("delete", ["act-pm-failed"], {"actor_id": "act-pm-failed", "deleted": True})
        runner.add_error(
            "start",
            ["pm", str(TEST_RUNTIME.executable), TEST_RUNTIME.version, replacement_actor_id],
            HOST_CONTROL.HostControlError("COMMAND_FAILED", "Replacement start failed."),
        )
        control = HOST_CONTROL.HostControl(
            repo_root=ROOT,
            runner=runner,
            runtime_resolver=lambda: TEST_RUNTIME,
        )

        with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
            control.retry("act-pm-failed", replacement_actor_id)

        self.assertEqual(raised.exception.message, "Replacement start failed.")
        self.assertEqual([call[0] for call in runner.calls], ["status", "delete", "start"])

    def test_start_resolves_runtime_once_and_passes_descriptor_to_private_owner(self) -> None:
        runner = FakePrivateRunner()
        runtime = codex_runtime.CodexRuntime(
            executable=Path("/opt/buddyswitch/codex"),
            version="codex-cli test-runtime",
        )
        runner.add(
            "start",
            ["pm", str(runtime.executable), runtime.version, "act-pm-demo"],
            {
                "actor_id": "act-pm-demo",
                "role": "pm",
                "workspace_dir": "/tmp/workspace",
                "project_workspace_dir": "/tmp/project/workspace",
                "instance_record": "/tmp/instances/act-pm-demo/instance.json",
            },
        )
        resolutions: list[bool] = []

        def resolve_runtime() -> codex_runtime.CodexRuntime:
            resolutions.append(True)
            return runtime

        control = HOST_CONTROL.HostControl(
            repo_root=ROOT,
            runner=runner,
            runtime_resolver=resolve_runtime,
        )

        payload = control.start("pm", actor_id="act-pm-demo")

        self.assertEqual(payload["actor_id"], "act-pm-demo")
        self.assertEqual(resolutions, [True])
        self.assertEqual(
            [(operation, args) for operation, args, _timeout in runner.calls],
            [("start", ("pm", "/opt/buddyswitch/codex", "codex-cli test-runtime", "act-pm-demo"))],
        )

    def test_resume_uses_recorded_runtime_and_ignores_current_selection(self) -> None:
        runner = FakePrivateRunner()
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared"
            instance_json = write_instance(shared_root)
            record = json.loads(instance_json.read_text(encoding="utf-8"))["codex_runtime"]
            runner.add(
                "resume",
                ["act-pm-demo", record["executable"], record["version"]],
                {"actor_id": "act-pm-demo", "thread_id": "thread-main", "status": "active"},
            )
            previous_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
            previous_codex_bin = os.environ.get("BUDDYSWITCH_CODEX_BIN")
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            os.environ["BUDDYSWITCH_CODEX_BIN"] = "/current/path/must-not-win"
            try:
                control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)
                payload = control.resume("act-pm-demo")
            finally:
                self._restore_env_value("BUDDYSWITCH_SHARED_ROOT", previous_shared_root)
                self._restore_env_value("BUDDYSWITCH_CODEX_BIN", previous_codex_bin)

        self.assertEqual(payload["status"], "active")
        self.assertEqual(runner.calls[0][1], ("act-pm-demo", record["executable"], record["version"]))

    def test_resume_rejects_missing_or_changed_recorded_runtime_without_private_call(self) -> None:
        for invalid_state in ("missing", "changed"):
            with self.subTest(invalid_state=invalid_state), tempfile.TemporaryDirectory() as temp_root:
                shared_root = Path(temp_root) / "shared"
                instance_json = write_instance(shared_root)
                record = json.loads(instance_json.read_text(encoding="utf-8"))
                if invalid_state == "missing":
                    record.pop("codex_runtime")
                else:
                    codex_bin = Path(record["codex_runtime"]["executable"])
                    codex_bin.write_text("#!/bin/sh\nprintf '%s\\n' 'codex-cli changed-runtime'\n", encoding="utf-8")
                    codex_bin.chmod(0o755)
                instance_json.write_text(json.dumps(record, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
                previous_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
                os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
                runner = FakePrivateRunner()
                try:
                    control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)
                    with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                        control.resume("act-pm-demo")
                finally:
                    self._restore_env_value("BUDDYSWITCH_SHARED_ROOT", previous_shared_root)

                self.assertEqual(raised.exception.code, "RUNTIME_MISMATCH")
                self.assertEqual(runner.calls, [])

    def test_stop_and_delete_do_not_require_recorded_runtime(self) -> None:
        runner = FakePrivateRunner()
        runner.add("stop", ["act-pm-demo"], {"actor_id": "act-pm-demo", "status": "inactive"})
        runner.add("delete", ["act-pm-demo"], {"actor_id": "act-pm-demo", "deleted": True})
        control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner)

        self.assertEqual(control.stop("act-pm-demo")["status"], "inactive")
        self.assertTrue(control.delete("act-pm-demo")["deleted"])
        self.assertEqual([call[0] for call in runner.calls], ["stop", "delete"])

    def test_private_status_reports_missing_recorded_runtime_as_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            shared_root = root / "shared"
            instance_json = write_instance(shared_root)
            record = json.loads(instance_json.read_text(encoding="utf-8"))
            record.pop("codex_runtime")
            instance_json.write_text(json.dumps(record, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_SOURCE_HOME"] = str(root / "home")

            completed = run_process(
                [str(ROOT / "tools" / "launcher" / "host_control.sh"), "status", "act-pm-demo"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIsNone(json.loads(completed.stdout)["codex_runtime"])

    def test_status_and_list_require_nullable_start_failure_fact(self) -> None:
        status_payload = {
            "actor_id": "act-pm-demo",
            "role": "pm",
            "status": "inactive",
            "workspace_dir": "/tmp/workspace",
            "browser_port": None,
            "updated_at": "2026-07-13T00:00:00Z",
            "thread_id": None,
            "codex_runtime": TEST_RUNTIME.to_record(),
            "app_server": {},
            "daemon": {},
            "runtime_broker": {},
            "thread": {},
        }
        list_row = valid_instance_row()
        list_row["status"] = "inactive"
        list_row.pop("last_failure")

        for operation, payload in (("status", status_payload), ("list", list_row)):
            with self.subTest(operation=operation):
                runner = FakePrivateRunner()
                if operation == "status":
                    runner.add("status", ["act-pm-demo"], payload)
                    action = lambda: HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner).status("act-pm-demo")
                else:
                    runner.add("list", [], {"instances": [payload]})
                    action = lambda: HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner).list_instances()
                with self.assertRaises(HOST_CONTROL.HostControlError) as raised:
                    action()
                self.assertEqual(raised.exception.code, "COMMAND_FAILED")
                self.assertIn("last_failure", raised.exception.message)

        for last_failure in (None, {"phase": "daemon_start", "message": "Daemon start failed.", "failed_at": "2026-07-18T00:00:00Z"}):
            with self.subTest(valid_last_failure=last_failure):
                runner = FakePrivateRunner()
                valid_status = dict(status_payload, last_failure=last_failure)
                runner.add("status", ["act-pm-demo"], valid_status)
                self.assertEqual(
                    HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner).status("act-pm-demo")["last_failure"],
                    last_failure,
                )

    def test_host_control_start_routes_every_published_phase_through_one_cleanup_owner(self) -> None:
        source = (ROOT / "tools" / "launcher" / "host_control.sh").read_text(encoding="utf-8")
        start_block = source.split("start_locked_bootstrap() {", 1)[1].split(
            "instance_set_inactive_locked() {",
            1,
        )[0]
        phases = (
            "capability_seed",
            "runtime_broker_ensure",
            "codex_config_patch",
            "env_mcp_ensure",
            "browser_register",
            "app_server_ensure",
            "thread_start",
            "thread_bootstrap",
            "daemon_start",
        )

        self.assertIn("buddyswitch_run_published_start_phase", source)
        self.assertEqual(source.count("buddyswitch_start_failure_cleanup()"), 1)
        for phase in phases:
            with self.subTest(phase=phase):
                self.assertIn(f'"{phase}"', start_block)
        self.assertNotIn("buddyswitch_start_failure_cleanup \\\n", start_block)

    def test_public_facade_exposes_exact_host_control_operations(self) -> None:
        expected = {
            "roles": ["self"],
            "allocate_actor_id": ["self", "role_id"],
            "start": ["self", "role_id", "actor_id"],
            "prepare_retry": ["self", "actor_id"],
            "retry": ["self", "actor_id", "replacement_actor_id"],
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
            ["pm", str(TEST_RUNTIME.executable), TEST_RUNTIME.version, "act-pm-demo"],
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
                "codex_runtime": TEST_RUNTIME.to_record(),
                "last_failure": None,
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
        runner.add(
            "resume",
            ["act-pm-demo", str(TEST_RUNTIME.executable), TEST_RUNTIME.version],
            {"actor_id": "act-pm-demo", "thread_id": "thread-main", "status": "active"},
        )
        runner.add("stop", ["act-pm-demo"], {"actor_id": "act-pm-demo", "status": "inactive"})
        runner.add("delete", ["act-pm-demo"], {"actor_id": "act-pm-demo", "deleted": True})
        runner.add("interrupt", ["act-pm-demo"], {"actor_id": "act-pm-demo", "thread_id": "thread-main", "turn_id": "turn-1"})
        runner.add("compact", ["act-pm-demo"], {"actor_id": "act-pm-demo", "thread_id": "thread-main", "started": True})
        control = HOST_CONTROL.HostControl(repo_root=ROOT, runner=runner, runtime_resolver=lambda: TEST_RUNTIME)

        with mock.patch.object(control, "_recorded_runtime", return_value=TEST_RUNTIME):
            roles = control.roles()
            started = control.start("pm", actor_id="act-pm-demo")
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
                ("start", ("pm", str(TEST_RUNTIME.executable), TEST_RUNTIME.version, "act-pm-demo")),
                ("list", ()),
                ("list", ("pm",)),
                ("status", ("act-pm-demo",)),
                ("clear", ("act-pm-demo",)),
                ("resume", ("act-pm-demo", str(TEST_RUNTIME.executable), TEST_RUNTIME.version)),
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

    def test_facade_rejects_instance_rows_with_invalid_actor_or_role_identifiers(self) -> None:
        malformed_rows = [
            ({**valid_instance_row(), "actor_id": "pm-demo"}, "actor_id"),
            ({**valid_instance_row(), "actor_id": "act/pm-demo"}, "actor_id"),
            ({**valid_instance_row(), "role": "--pm"}, "role"),
            ({**valid_instance_row(), "role": "../pm"}, "role"),
        ]

        for row, field_name in malformed_rows:
            with self.subTest(row=row):
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
                lambda control: control.start("pm", actor_id="act-pm-demo"),
                ["pm", str(TEST_RUNTIME.executable), TEST_RUNTIME.version, "act-pm-demo"],
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
                    "codex_runtime": TEST_RUNTIME.to_record(),
                    "last_failure": None,
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
                ["act-pm-demo", str(TEST_RUNTIME.executable), TEST_RUNTIME.version],
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
                    control = HOST_CONTROL.HostControl(
                        repo_root=ROOT,
                        runner=runner,
                        runtime_resolver=lambda: TEST_RUNTIME,
                    )
                    with (
                        mock.patch.object(control, "_recorded_runtime", return_value=TEST_RUNTIME),
                        self.assertRaises(HOST_CONTROL.HostControlError) as raised,
                    ):
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

    def test_private_host_control_classifies_missing_instance_as_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("BUDDYSWITCH_") or key == "BUDDYSWITCH_PYTHON"
            }
            env["HOME"] = source_home
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(ROOT / "tools" / "launcher" / "host_control.sh"), "delete", "act-pm-missing"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 6)
        self.assertEqual(completed.stderr, "")
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertEqual(payload["error"]["message"], "Instance not found: act-pm-missing")
        self.assertNotIn(source_home, completed.stdout)

    def test_unrelated_status_six_remains_command_failed(self) -> None:
        error = HOST_CONTROL._error_from_payload({}, returncode=6, fallback_message="dependency failed")
        self.assertEqual(error.code, "COMMAND_FAILED")

        script = """
source "$1"
host_control_emit_error_for_output "$2" "$3"
"""
        cases = (
            (1, "Instance not found: act-pm-forged"),
            (6, "Instance not found: act-pm-forged"),
            (6, "dependency failed"),
        )
        for status, message in cases:
            with self.subTest(status=status, message=message):
                completed = run_process(
                    [
                        "/bin/bash",
                        "-c",
                        script,
                        "host-control-status-test",
                        str(ROOT / "tools" / "launcher" / "host_control.sh"),
                        str(status),
                        message,
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 0)
                self.assertEqual(completed.stderr, "")
                payload = json.loads(completed.stdout)
                self.assertEqual(payload["error"], {"code": "COMMAND_FAILED", "message": message})

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

    def test_host_control_start_has_one_builder_boundary_before_runtime_services(self) -> None:
        source = (ROOT / "tools" / "launcher" / "host_control.sh").read_text(encoding="utf-8")
        start_block = source.split("start_locked_bootstrap() {", 1)[1].split(
            "instance_set_inactive_locked() {",
            1,
        )[0]
        resume_block = source.split("instance_resume_locked() {", 1)[1].split(
            "instance_stop() {",
            1,
        )[0]

        self.assertEqual(start_block.count("actor_environment.py"), 1)
        self.assertEqual(source.count("actor_environment.py"), 1)
        self.assertNotIn("workspace.sh", source)
        self.assertNotIn("WORKSPACE_HELPER", source)
        self.assertNotIn("buddyswitch_workspace_", start_block)
        for forbidden in (
            "actor_environment.py",
            "--validate-existing",
            "buddyswitch_require_env_profile",
            "buddyswitch_require_role_agents_template",
        ):
            with self.subTest(resume_forbidden=forbidden):
                self.assertNotIn(forbidden, resume_block)
        builder_index = start_block.index("actor_environment.py")
        for service_call in (
            "buddyswitch_runtime_broker_ensure",
            "buddyswitch_app_server_ensure",
            "buddyswitch_app_server_thread_start",
            "buddyswitch_daemon_start",
        ):
            with self.subTest(service_call=service_call):
                self.assertGreater(start_block.index(service_call), builder_index)

    def test_host_control_module_has_no_temporary_cli_entrypoint_residue(self) -> None:
        source = (ROOT / "tools" / "launcher" / "host_control.py").read_text(encoding="utf-8")
        forbidden = [
            "import argparse",
            "Sequence",
            "_emit_json",
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
            "--json",
            "BuddySwitch instance:",
            "No BuddySwitch instances found.",
            "delete preview",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)
        for name in ("build_parser", "main", "_emit_json", "_prevalidate_legacy_messages"):
            with self.subTest(attribute=name):
                self.assertFalse(hasattr(HOST_CONTROL, name))

    def test_host_control_script_start_uses_positional_private_role(self) -> None:
        completed = run_process(
            [
                str(ROOT / "tools" / "launcher" / "host_control.sh"),
                "start",
                "--bad",
                "/bin/sh",
                "test-version",
                "act-bad-demo",
            ],
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
        completed = run_process(
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
