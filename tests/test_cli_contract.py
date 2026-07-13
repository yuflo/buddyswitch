"""Machine-first CLI output contract tests."""

from __future__ import annotations

import io
import json
import unittest

from tools.launcher import cli_contract


class CliContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
