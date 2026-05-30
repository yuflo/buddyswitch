#!/usr/bin/env python3
"""Tests for the BuddySwitch Chrome DevTools MCP focus-control proxy."""

from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "tools" / "launcher" / "chrome_devtools_cockpit_proxy.py"


class BrowserCockpitProxyTests(unittest.TestCase):
    def _write_exec(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_fake_upstream(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


calls_path = Path(os.environ["BUDDYSWITCH_TEST_PROXY_CALLS"])
argv_path = Path(os.environ["BUDDYSWITCH_TEST_PROXY_ARGV"])
calls_path.parent.mkdir(parents=True, exist_ok=True)
argv_path.write_text(json.dumps(sys.argv[1:], ensure_ascii=True) + "\\n", encoding="utf-8")

TOOLS = [
    {
        "name": "new_page",
        "description": "Open a new tab and load a URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "background": {
                    "type": "boolean",
                    "description": "Whether to open the page in the background without bringing it to the front.",
                },
                "isolatedContext": {"type": "string"},
            },
        },
    },
    {
        "name": "select_page",
        "description": "Select a page as a context for future tool calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pageId": {"type": "number"},
                "bringToFront": {
                    "type": "boolean",
                    "description": "Whether to focus the page and bring it to the top.",
                },
            },
        },
    },
]


for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    message = json.loads(line)
    with calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=True) + "\\n")

    request_id = message.get("id")
    method = message.get("method")
    if request_id is None:
        continue
    if method == "tools/list":
        response = {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "called " + str(params.get("name")),
                    }
                ]
            },
        }
    else:
        response = {"jsonrpc": "2.0", "id": request_id, "result": {}}
    print(json.dumps(response, ensure_ascii=True), flush=True)
""",
        )

    def _run_proxy(self, messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str]:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            command = [
                sys.executable,
                str(PROXY),
                "--upstream-command",
                f"{sys.executable} {upstream}",
                "--browser-url=http://127.0.0.1:9222",
            ]
            proc = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            input_text = "".join(json.dumps(message, ensure_ascii=True) + "\n" for message in messages)
            try:
                stdout, stderr = proc.communicate(input=input_text, timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
                self.fail(f"proxy timed out\nstdout:\n{stdout}\nstderr:\n{stderr}")

            self.assertEqual(proc.returncode, 0, msg=f"proxy failed\nstdout:\n{stdout}\nstderr:\n{stderr}")
            responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            forwarded = (
                [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if calls_path.exists()
                else []
            )
            upstream_argv = json.loads(argv_path.read_text(encoding="utf-8").splitlines()[0]) if argv_path.exists() else []
            return responses, forwarded, upstream_argv, stderr

    def _single_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

    def test_new_page_defaults_to_background(self) -> None:
        responses, forwarded, upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com"})]
        )

        self.assertEqual(responses[0]["id"], 1)
        self.assertIn("--browser-url=http://127.0.0.1:9222", upstream_argv)
        arguments = forwarded[0]["params"]["arguments"]
        self.assertEqual(arguments["url"], "https://example.com")
        self.assertIs(arguments["background"], True)

    def test_new_page_forces_background_when_caller_requests_foreground(self) -> None:
        _responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com", "background": False})]
        )

        arguments = forwarded[0]["params"]["arguments"]
        self.assertIs(arguments["background"], True)

    def test_select_page_forces_no_bring_to_front(self) -> None:
        _responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("select_page", {"pageId": 3, "bringToFront": True})]
        )

        arguments = forwarded[0]["params"]["arguments"]
        self.assertEqual(arguments["pageId"], 3)
        self.assertIs(arguments["bringToFront"], False)

    def test_new_page_isolated_context_is_rejected_without_forwarding(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com", "isolatedContext": "login"})]
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertEqual(response["id"], 1)
        result = response["result"]
        self.assertIs(result["isError"], True)
        self.assertIn("isolatedContext", result["content"][0]["text"])
        self.assertIn("non-activating", result["content"][0]["text"])

    def test_tools_list_patches_focus_sensitive_descriptions(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        self.assertEqual(forwarded[0]["method"], "tools/list")
        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertIn("BuddySwitch", json.dumps(by_name["new_page"], ensure_ascii=True))
        self.assertIn("non-activating", json.dumps(by_name["select_page"], ensure_ascii=True))


if __name__ == "__main__":
    unittest.main()
