#!/usr/bin/env python3
"""CLI payload parsing contract tests for scripts/env/client.py."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SHIPPED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "message", "comment", "search"}


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

    def test_json_object_payload_dispatches_for_every_payload_operation(self) -> None:
        cases = [
            (["task", "create"], "task", "create", {"task_id": "task-json", "title": "Task", "buddy": "dev"}),
            (["task", "update"], "task", "update", {"task_id": "task-json", "summary": "Updated"}),
            (
                ["track", "create"],
                "track",
                "create",
                {
                    "track_id": "track-json",
                    "title": "Track",
                    "outcome": "Outcome",
                    "appetite": "1 day",
                    "now": {"next": "next", "blocker": None},
                },
            ),
            (
                ["track", "update-now"],
                "track",
                "update_now",
                {"track_id": "track-json", "now": {"next": "next", "blocker": None}},
            ),
            (
                ["track", "add-material"],
                "track",
                "add_material",
                {
                    "track_id": "track-json",
                    "artifact_id": "art-json",
                    "label": "Brief",
                    "summary": "Summary",
                },
            ),
            (
                ["track", "add-update"],
                "track",
                "add_update",
                {"track_id": "track-json", "summary": "Progress", "kind": "progress"},
            ),
            (
                ["track", "add-proof"],
                "track",
                "add_proof",
                {
                    "track_id": "track-json",
                    "artifact_id": "art-proof",
                    "label": "Proof",
                    "summary": "Summary",
                },
            ),
            (
                ["artifact", "create-revision"],
                "artifact",
                "create_revision",
                {"title": "Artifact", "summary": "Summary", "template": "brief", "body": "# Body"},
            ),
            (
                ["artifact", "update-metadata"],
                "artifact",
                "update_metadata",
                {"artifact_id": "art-json", "summary": "Updated"},
            ),
            (
                ["buddybox", "write"],
                "buddybox",
                "write",
                {"logical_name": "notes.md", "content": "hello"},
            ),
            (
                ["message", "send"],
                "message",
                "send",
                {"to_buddy": "design", "content": "Please review"},
            ),
            (
                ["comment", "add"],
                "comment",
                "add",
                {"target_type": "track", "target_id": "track-json", "content": "Looks good"},
            ),
        ]

        for prefix, expected_tool, expected_action, payload in cases:
            with self.subTest(argv=prefix):
                code, output, broker = self._run_client([*prefix, "--payload", json.dumps(payload)])
                self.assertEqual(code, 0, msg=output)
                broker.assert_called_once_with(
                    "env.tool",
                    {"tool": expected_tool, "action": expected_action, "args": payload},
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

    def test_missing_payload_argument_exits_before_broker_dispatch(self) -> None:
        with mock.patch.object(sys, "argv", ["client.py", "artifact", "create-revision"]):
            with mock.patch.object(self.client, "request_runtime_broker") as broker:
                with self.assertRaises(SystemExit) as exc_info:
                    self.client.main()
        self.assertEqual(exc_info.exception.code, 2)
        broker.assert_not_called()

    def test_client_has_no_per_tool_dispatch_branches(self) -> None:
        source = (ROOT / "scripts" / "env" / "client.py").read_text(encoding="utf-8")
        for tool in sorted(SHIPPED_TOOLS):
            with self.subTest(tool=tool):
                self.assertNotIn(f"def _dispatch_{tool}(", source)

    def test_flag_payload_operations_still_map_to_expected_envelopes(self) -> None:
        cases = [
            (["task", "list", "--status", "active", "--limit", "10"], "task", "list", {"status": "active", "limit": 10}),
            (["track", "list"], "track", "list", {}),
            (["context", "list-sources"], "context", "list_sources", {}),
            (["buddybox", "desc"], "buddybox", "desc", {}),
            (
                ["evidence", "issue-browser", "--target-type", "artifact", "--target-id", "art-1"],
                "evidence",
                "issue_browser",
                {"target_type": "artifact", "target_id": "art-1"},
            ),
            (["search", "status"], "search", "status", {}),
            (["message", "list", "--buddy", "design"], "message", "list", {"buddy": "design"}),
            (
                ["comment", "list", "--target-type", "track", "--target-id", "track-json", "--status", "open"],
                "comment",
                "list",
                {"target_type": "track", "target_id": "track-json", "status": "open"},
            ),
        ]

        for argv, expected_tool, expected_action, expected_args in cases:
            with self.subTest(argv=argv):
                code, output, broker = self._run_client(argv)
                self.assertEqual(code, 0, msg=output)
                broker.assert_called_once_with(
                    "env.tool",
                    {"tool": expected_tool, "action": expected_action, "args": expected_args},
                )


if __name__ == "__main__":
    unittest.main()
