"""Machine-first CLI output contract tests."""

from __future__ import annotations

import io
import json
import unittest
from dataclasses import FrozenInstanceError, replace

from buddyswitch.application import cli_runtime as application_cli_runtime
from buddyswitch.application.build import activate_application
from buddyswitch.foundation.actor_runtime import codex_runtime
from buddyswitch.foundation.actor_runtime import session as actor_session
from buddyswitch.foundation.cli_runtime import contracts as cli_contract
from buddyswitch.foundation.host_control import runtime as host_control
from buddyswitch.foundation.cli_runtime import runtime as cli


class CliRuntimeContractTests(unittest.TestCase):
    def test_application_supplies_one_frozen_complete_cli_runtime_input(self) -> None:
        application_input = application_cli_runtime.assemble_cli_runtime(
            activate_application()
        )

        self.assertEqual(
            application_input.web_module,
            application_cli_runtime.WEB_MODULE,
        )
        self.assertEqual(
            application_input.actor_build_module,
            application_cli_runtime.ACTOR_BUILD_MODULE,
        )
        self.assertEqual(
            application_input.browser_runtime_module,
            application_cli_runtime.BROWSER_RUNTIME_MODULE,
        )
        self.assertEqual(
            application_input.env_mcp_module,
            application_cli_runtime.ENV_MCP_MODULE,
        )
        self.assertEqual(
            application_input.browser_cockpit_proxy_module,
            application_cli_runtime.BROWSER_COCKPIT_PROXY_MODULE,
        )
        self.assertEqual(
            application_input.cleanup_module,
            application_cli_runtime.CLEANUP_MODULE,
        )
        self.assertEqual(
            application_input.diagnostics_module,
            application_cli_runtime.DIAGNOSTICS_MODULE,
        )
        self.assertEqual(application_input.resolve_role("dev").source_access, "write")
        self.assertEqual(
            application_input.parent_disabled_tools,
            ("demand_sys__resolve_inbound",),
        )
        with self.assertRaises(FrozenInstanceError):
            application_input.web_module = "replacement"  # type: ignore[misc]

    def test_cli_runtime_application_input_fails_closed(self) -> None:
        application_input = application_cli_runtime.assemble_cli_runtime(
            activate_application()
        )

        with self.assertRaisesRegex(ValueError, "web module"):
            replace(application_input, web_module="")
        with self.assertRaisesRegex(ValueError, "resolver must be callable"):
            replace(application_input, role_runtime_resolver=None)  # type: ignore[arg-type]

    def test_cli_runtime_shell_environment_projects_current_role_fact(self) -> None:
        application_input = application_cli_runtime.assemble_cli_runtime(
            activate_application()
        )

        environment = cli.application_environment(
            application_input,
            base={"PRESERVED": "yes"},
            role_browser_capability=(
                application_cli_runtime.resolve_role_browser_capability(
                    application_input,
                    "pm",
                )
            ),
        )

        self.assertEqual(environment["PRESERVED"], "yes")
        self.assertEqual(
            environment["BUDDYSWITCH_CLI_RUNTIME_ACTOR_BUILD_MODULE"],
            application_cli_runtime.ACTOR_BUILD_MODULE,
        )
        self.assertEqual(
            environment["BUDDYSWITCH_CLI_RUNTIME_BROWSER_MODULE"],
            application_cli_runtime.BROWSER_RUNTIME_MODULE,
        )
        self.assertEqual(
            environment["BUDDYSWITCH_CLI_RUNTIME_ROLE_BROWSER_CAPABILITY"],
            "available",
        )

    def test_cli_runtime_shell_environment_rejects_stale_role_fact(self) -> None:
        application_input = application_cli_runtime.assemble_cli_runtime(
            activate_application()
        )

        environment = cli.application_environment(
            application_input,
            base={"BUDDYSWITCH_CLI_RUNTIME_ROLE_BROWSER_CAPABILITY": "required"},
        )

        self.assertNotIn(
            "BUDDYSWITCH_CLI_RUNTIME_ROLE_BROWSER_CAPABILITY",
            environment,
        )

    def test_success_envelope_has_stable_machine_keys(self) -> None:
        payload = cli_contract.success("task_result", {"task_id": "task-1"})

        self.assertEqual(["ok", "kind", "data"], list(payload))
        self.assertEqual(
            payload,
            {
                "ok": True,
                "kind": "task_result",
                "data": {"task_id": "task-1"},
            },
        )

    def test_failure_envelope_has_stable_error_keys(self) -> None:
        error = cli_contract.CliError("NOT_FOUND", "Task not found", {"task_id": "task-1"})

        payload = cli_contract.failure(error)

        self.assertEqual(["ok", "error"], list(payload))
        self.assertEqual(["code", "message", "details"], list(payload["error"]))
        self.assertEqual(
            payload,
            {
                "ok": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Task not found",
                    "details": {"task_id": "task-1"},
                },
            },
        )

    def test_emit_writes_one_json_line_and_preserves_unicode(self) -> None:
        payload = cli_contract.success("message", {"text": "hello \u96ea"})
        stream = io.StringIO()

        cli_contract.emit(payload, stream)

        output = stream.getvalue()
        self.assertTrue(output.endswith("\n"), msg=output)
        self.assertEqual(1, output.count("\n"), msg=output)
        self.assertEqual(payload, json.loads(output))
        self.assertIn("hello \u96ea", output)
        self.assertNotIn("\\u96ea", output)

    def test_emit_stdout_contains_no_raw_ansi_escape(self) -> None:
        payload = cli_contract.failure(cli_contract.CliError("EXECUTION_FAILED", "\x1b[31mboom\x1b[0m"))
        stream = io.StringIO()

        cli_contract.emit(payload, stream)

        output = stream.getvalue()
        self.assertNotIn("\x1b", output)
        self.assertEqual(payload, json.loads(output))

    def test_exit_code_maps_stable_error_codes(self) -> None:
        cases = {
            "INTERNAL_ERROR": 1,
            "EXECUTION_FAILED": 1,
            "INVALID_ARGUMENT": 2,
            "UNKNOWN_COMMAND": 2,
            "NOT_FOUND": 3,
            "CONFLICT": 4,
            "PRECONDITION_FAILED": 4,
            "CONFIRMATION_REQUIRED": 4,
            "RUNTIME_UNAVAILABLE": 5,
            "RUNTIME_MISMATCH": 5,
            "TIMEOUT": 5,
        }

        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(expected, cli_contract.exit_code(cli_contract.CliError(code, code)))

    def test_unknown_exception_normalizes_to_internal_error(self) -> None:
        normalized = cli_contract.normalize_error(RuntimeError("boom"))

        self.assertIsInstance(normalized, cli_contract.CliError)
        self.assertEqual("INTERNAL_ERROR", normalized.code)
        self.assertEqual("Unexpected internal error", normalized.message)
        self.assertEqual({}, normalized.details)

    def test_normalize_error_preserves_cli_error(self) -> None:
        error = cli_contract.CliError("INVALID_ARGUMENT", "Bad payload")

        self.assertIs(error, cli_contract.normalize_error(error))

    def test_unknown_cli_error_code_uses_public_internal_error_contract(self) -> None:
        error = cli_contract.CliError("INTERAL_ERROR", "Typo code should not escape")

        normalized = cli_contract.normalize_error(error)
        payload = cli_contract.failure(error)

        self.assertEqual(
            cli_contract.CliError("INTERNAL_ERROR", "Unexpected internal error"),
            normalized,
        )
        self.assertEqual(cli_contract.failure(normalized), payload)
        self.assertEqual(1, cli_contract.exit_code(error))
        self.assertNotIn("INTERAL_ERROR", json.dumps(payload, ensure_ascii=False))

    def test_cli_maps_host_control_errors_to_canonical_public_codes(self) -> None:
        cases = (
            (host_control.HostControlError("INVALID_REQUEST", "bad", returncode=2), "INVALID_ARGUMENT"),
            (host_control.HostControlError("NOT_FOUND", "missing", returncode=1), "NOT_FOUND"),
            (host_control.HostControlError("LIFECYCLE_BLOCKED", "active", returncode=3), "CONFLICT"),
            (host_control.HostControlError("LOCK_BUSY", "busy", returncode=4), "CONFLICT"),
            (host_control.HostControlError("COMMAND_TIMEOUT", "slow", timed_out=True), "TIMEOUT"),
            (host_control.HostControlError("CAPABILITY_CONFIG_INVALID", "bad capability", returncode=3), "PRECONDITION_FAILED"),
            (host_control.HostControlError("COMMAND_FAILED", "bad payload", returncode=1), "EXECUTION_FAILED"),
            (host_control.HostControlError("CAPABILITY_CONFIG_WRITE_FAILED", "write failed", returncode=2), "EXECUTION_FAILED"),
            (host_control.HostControlError("RUNTIME_UNAVAILABLE", "missing runtime", returncode=5), "RUNTIME_UNAVAILABLE"),
            (host_control.HostControlError("RUNTIME_MISMATCH", "changed runtime", returncode=5), "RUNTIME_MISMATCH"),
            (host_control.HostControlError("NEW_LOWER_LAYER_CODE", "typed but unknown", returncode=1), "INTERNAL_ERROR"),
        )

        for error, expected_code in cases:
            with self.subTest(code=error.code):
                mapped = cli._map_host_control_error(error)
                payload = cli_contract.failure(mapped)

                self.assertEqual(expected_code, mapped.code)
                self.assertEqual(expected_code, payload["error"]["code"])

    def test_cli_maps_codex_runtime_failures_without_reselecting_runtime(self) -> None:
        for lower_code in ("INVALID_RUNTIME_RECORD", "RUNTIME_MISMATCH"):
            with self.subTest(lower_code=lower_code):
                mapped = cli._map_exception(codex_runtime.CodexRuntimeError(lower_code, "recorded runtime invalid"))

                self.assertEqual(mapped.code, "RUNTIME_MISMATCH")
                self.assertEqual(cli_contract.exit_code(mapped), 5)

    def test_cli_maps_actor_session_errors_without_hiding_known_runtime_failures(self) -> None:
        cases = (
            (actor_session.ActorSessionError("invalid actor id"), "INVALID_ARGUMENT"),
            (actor_session.ActorSessionError("input text is required"), "INVALID_ARGUMENT"),
            (actor_session.ActorSessionError("actor not found: act-missing"), "NOT_FOUND"),
            (actor_session.ActorSessionError("actor app server unhealthy for act-pm-demo: socket missing"), "RUNTIME_UNAVAILABLE"),
            (actor_session.ActorSessionError("actor has no thread id; stop/delete and recreate the instance"), "RUNTIME_UNAVAILABLE"),
            (actor_session.ActorSessionError("parent capability invalid: unsupported parent level"), "PRECONDITION_FAILED"),
            (actor_session.ActorSessionError("parent settings update failed: denied"), "EXECUTION_FAILED"),
            (actor_session.ActorSessionError("input turn failed: thread not loaded"), "EXECUTION_FAILED"),
            (actor_session.ActorSessionError("thread/resume failed for thr-main: denied"), "EXECUTION_FAILED"),
            (actor_session.ActorSessionError("thread/resume returned unexpected thread id: thr-other"), "EXECUTION_FAILED"),
            (actor_session.ActorSessionError("actor record mismatch: act-pm-demo"), "INTERNAL_ERROR"),
        )

        for error, expected_code in cases:
            with self.subTest(message=str(error)):
                mapped = cli._map_actor_session_error(error)
                payload = cli_contract.failure(mapped)

                self.assertEqual(expected_code, mapped.code)
                self.assertEqual(expected_code, payload["error"]["code"])
