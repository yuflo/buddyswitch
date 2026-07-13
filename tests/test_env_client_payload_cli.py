"""CLI payload parsing contract tests for scripts/env/client.py."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import registry as tool_registry  # noqa: E402
from runtime_kernel.client import RuntimeBrokerError  # noqa: E402
from tests.python_runtime import PYTHON  # noqa: E402


class EnvClientPayloadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = importlib.import_module("env.client")

    def _run_client(
        self,
        argv: list[str],
        *,
        broker_response: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, object], mock.Mock]:
        response = broker_response if broker_response is not None else {"ok": True}
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["client.py", *argv]):
            with mock.patch.object(self.client, "request_runtime_broker", return_value=response) as broker:
                with contextlib.redirect_stdout(stdout):
                    code = self.client.main()
        return code, json.loads(stdout.getvalue()), broker

    def _tool_help_actions(self, tool: str) -> set[str]:
        completed = subprocess.run(
            [PYTHON, "scripts/env/client.py", tool, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        actions = set()
        for action in tool_registry.supported_actions(tool):
            dashed = action.replace("_", "-")
            if dashed in completed.stdout or action in completed.stdout:
                actions.add(action)
        return actions

    def test_cli_help_lists_tools_from_registry(self) -> None:
        completed = subprocess.run(
            [PYTHON, "scripts/env/client.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        for tool in sorted(tool_registry.supported_tools()):
            with self.subTest(tool=tool):
                self.assertIn(tool, completed.stdout)

    def test_tool_help_lists_actions_from_registry(self) -> None:
        for tool in sorted(tool_registry.supported_tools()):
            with self.subTest(tool=tool):
                self.assertEqual(self._tool_help_actions(tool), set(tool_registry.supported_actions(tool)))

    def test_json_object_payload_dispatches_for_every_action(self) -> None:
        for tool in sorted(tool_registry.supported_tools()):
            for action in sorted(tool_registry.supported_actions(tool)):
                payload = {field: f"value-for-{field}" for field in tool_registry.payload_fields_for_action(tool, action)}
                cli_action = action.replace("_", "-")
                with self.subTest(tool=tool, action=action):
                    code, output, broker = self._run_client([tool, cli_action, "--payload", json.dumps(payload)])
                    self.assertEqual(code, 0, msg=output)
                    broker.assert_called_once_with(
                        "env.tool",
                        {"tool": tool, "action": action, "args": payload},
                    )

    def test_product_mode_env_cli_refuses_runtime_action_without_admin_override(self) -> None:
        stdout = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-dev-test",
                "BUDDYSWITCH_ROLE_ID": "dev",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime.sock",
            },
            clear=False,
        ):
            with mock.patch.object(sys, "argv", ["client.py", "message", "list", "--payload", "{}"]):
                with mock.patch.object(self.client, "request_runtime_broker") as broker:
                    with contextlib.redirect_stdout(stdout):
                        code = self.client.main()

        output = json.loads(stdout.getvalue())
        self.assertEqual(code, 1, msg=output)
        self.assertEqual(output.get("error", {}).get("code"), "E_ENV_CLI_PRODUCT_MODE_DISABLED")
        self.assertEqual(output.get("permission_boundary"), "product-mode-native-mcp-only")
        self.assertIs(output.get("state_changed"), False, msg=output)
        self.assertEqual(output.get("durability"), "none", msg=output)
        self.assertIn("allowed_next_actions", output)
        self.assertNotIn("scripts/env/client.py", json.dumps(output, ensure_ascii=True))
        broker.assert_not_called()

    def test_product_mode_env_cli_allows_explicit_admin_override(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-dev-test",
                "BUDDYSWITCH_ROLE_ID": "dev",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime.sock",
                "BUDDYSWITCH_ALLOW_ENV_ADMIN_CLI": "1",
            },
            clear=False,
        ):
            code, output, broker = self._run_client(["message", "list", "--payload", "{}"])

        self.assertEqual(code, 0, msg=output)
        broker.assert_called_once_with(
            "env.tool",
            {"tool": "message", "action": "list", "args": {}},
        )

    def test_missing_payload_defaults_to_empty_object(self) -> None:
        code, output, broker = self._run_client(["context", "list-sources"])
        self.assertEqual(code, 0, msg=output)
        broker.assert_called_once_with(
            "env.tool",
            {"tool": "context", "action": "list_sources", "args": {}},
        )

    def test_actor_private_cli_resource_is_not_registered(self) -> None:
        completed = subprocess.run(
            [PYTHON, str(ROOT / "scripts" / "env" / "client.py"), "actor_private", "write", "--payload", "{}"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid choice", completed.stderr)

    def test_artifact_attachment_cli_commands_use_hyphenated_spelling_and_canonical_actions(self) -> None:
        cases = (
            ("attach-file", "attach_file", {"artifact_id": "art-1", "filename": "desktop.png", "source_path": "/tmp/shots/desktop.png"}),
            ("list-attachments", "list_attachments", {"artifact_id": "art-1"}),
            ("get-attachment", "get_attachment", {"artifact_id": "art-1", "attachment_id": "att-1"}),
        )
        for cli_action, action, payload in cases:
            with self.subTest(action=action):
                code, output, broker = self._run_client(["artifact", cli_action, "--payload", json.dumps(payload)])
                self.assertEqual(code, 0, msg=output)
                broker.assert_called_once_with(
                    "env.tool",
                    {"tool": "artifact", "action": action, "args": payload},
                )

    def test_payload_file_path_string_is_rejected_without_file_read(self) -> None:
        with mock.patch.object(sys, "argv", ["client.py", "artifact", "create-revision", "--payload", "/tmp/artifact.json"]):
            with mock.patch.object(self.client, "request_runtime_broker") as broker:
                with mock.patch("pathlib.Path.read_text", side_effect=AssertionError("must not read payload file")):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        code = self.client.main()

        output = json.loads(stdout.getvalue())
        self.assertEqual(code, 1, msg=output)
        self.assertFalse(output.get("ok"), msg=output)
        self.assertEqual((output.get("error") or {}).get("code"), "E_ENV_CLI")
        self.assertIn("--payload must be a JSON object string", str((output.get("error") or {}).get("message", "")))
        broker.assert_not_called()

    def test_malformed_payload_rejects_before_broker_dispatch(self) -> None:
        code, output, broker = self._run_client(["track", "add-material", "--payload", "{not-json"])
        self.assertEqual(code, 1, msg=output)
        self.assertFalse(output.get("ok"), msg=output)
        self.assertEqual((output.get("error") or {}).get("code"), "E_ENV_CLI")
        message = str((output.get("error") or {}).get("message", ""))
        self.assertIn("--payload must be a JSON object string", message)
        self.assertIn("char", message)
        broker.assert_not_called()

    def test_non_object_json_payload_rejects_before_broker_dispatch(self) -> None:
        for raw in ("[]", '"text"', "null", "1", "true"):
            with self.subTest(raw=raw):
                code, output, broker = self._run_client(["message", "send", "--payload", raw])
                self.assertEqual(code, 1, msg=output)
                self.assertFalse(output.get("ok"), msg=output)
                self.assertEqual((output.get("error") or {}).get("code"), "E_ENV_CLI")
                self.assertIn("--payload must be a JSON object string", str((output.get("error") or {}).get("message", "")))
                broker.assert_not_called()

    def test_client_has_no_per_tool_dispatch_branches(self) -> None:
        source = (ROOT / "scripts" / "env" / "client.py").read_text(encoding="utf-8")
        for tool in sorted(tool_registry.supported_tools()):
            with self.subTest(tool=tool):
                self.assertNotIn(f"def _dispatch_{tool}(", source)

    def test_broker_role_auth_error_preserves_receipt_fields_at_top_level(self) -> None:
        receipt = {
            "tool": "track",
            "action": "track.create",
            "category": "auth_denied",
            "permission_boundary": "tool.role_authority",
            "auth_source": "env.tool role-action policy",
            "auth_stage": "pre_dispatch",
            "executed": False,
            "state_changed": False,
            "durability": "none",
            "retryable": False,
            "retry_guidance": "Use an action allowed for this role.",
            "why_blocked": "Action track.create is restricted by env.tool role-action policy.",
            "impact": "No env action ran and runtime state was unchanged.",
            "required_permission": "track.create",
            "active_role": "market",
            "allowed_roles": ["pm"],
            "allowed_next_actions": ["Use context.summarize to inspect runtime policy preview for this role."],
        }
        error = RuntimeBrokerError(
            "E_TOOL_ROLE_AUTH",
            "active role is not allowed to run this tool action",
            response={
                "ok": False,
                "error": {
                    "code": "E_TOOL_ROLE_AUTH",
                    "message": "active role is not allowed to run this tool action",
                },
                **receipt,
            },
            details=dict(receipt),
        )
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["client.py", "track", "create", "--payload", "{}"]):
            with mock.patch.object(self.client, "request_runtime_broker", side_effect=error):
                with contextlib.redirect_stdout(stdout):
                    code = self.client.main()
        output = json.loads(stdout.getvalue())
        self.assertEqual(code, 1, msg=output)
        self.assertEqual((output.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
        for key, value in receipt.items():
            with self.subTest(key=key):
                self.assertEqual(output.get(key), value, msg=output)


if __name__ == "__main__":
    unittest.main()
