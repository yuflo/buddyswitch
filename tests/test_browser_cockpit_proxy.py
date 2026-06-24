#!/usr/bin/env python3
"""Tests for the BuddySwitch Chrome DevTools MCP focus-control proxy."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "tools" / "launcher" / "chrome_devtools_cockpit_proxy.py"
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
DAEMON_MAILBOX_PATH = ROOT / "tools" / "launcher" / "daemon_mailbox.py"
MODULE_COUNTER = count()
SOFT_PAGE_HINT_5 = "Browser pages: 5/10. Reuse or close pages before opening many more."
HARD_PAGE_BLOCK = (
    "Blocked: browser page limit reached (10/10). Close or reuse existing pages, then retry opening this URL."
)


def _page_targets(count: int, *, start: int = 0) -> list[dict[str, object]]:
    return [
        {
            "id": f"target-{index}",
            "type": "page",
            "url": f"https://example.com/page-{index}",
        }
        for index in range(start, start + count)
    ]


def _make_cdp_list_handler(state: dict[str, object]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "GET", "path": self.path})
            parsed = urlparse(self.path)
            if parsed.path == "/json/list":
                if state.get("list_fail"):
                    self.send_response(500)
                    self.end_headers()
                    return
                list_payloads = state.get("list_payloads")
                if isinstance(list_payloads, list) and list_payloads:
                    payload = list_payloads.pop(0)
                else:
                    payload = state.get("list_payload", state.get("targets", []))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def load_module(path: Path) -> Any:
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def _start_cdp_list_server(self, state: dict[str, object]) -> str:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_list_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def _run_proxy(
        self,
        messages: list[dict[str, Any]],
        *,
        browser_url: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str]:
        if browser_url is None:
            browser_url = self._start_cdp_list_server({"requests": [], "targets": []})
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            if extra_env:
                env.update(extra_env)
            command = [
                sys.executable,
                str(PROXY),
                "--upstream-command",
                f"{sys.executable} {upstream}",
                f"--browser-url={browser_url}",
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
        self.assertEqual(len(upstream_argv), 1)
        self.assertTrue(upstream_argv[0].startswith("--browser-url=http://127.0.0.1:"), msg=upstream_argv)
        arguments = forwarded[0]["params"]["arguments"]
        self.assertEqual(arguments["url"], "https://example.com")
        self.assertIs(arguments["background"], True)

    def test_new_page_below_hint_threshold_forwards_without_page_hint(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(3)})

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
        )

        self.assertEqual(len(forwarded), 1)
        arguments = forwarded[0]["params"]["arguments"]
        self.assertEqual(arguments["url"], "https://example.com/new")
        self.assertIs(arguments["background"], True)
        self.assertNotIn("Browser pages:", json.dumps(responses, ensure_ascii=True))

    def test_new_page_registers_ttl_after_exactly_one_new_target(self) -> None:
        daemon_core = load_module(DAEMON_CORE_PATH)
        daemon_mailbox = load_module(DAEMON_MAILBOX_PATH)
        before = _page_targets(1)
        after = before + [{"id": "target-new-page", "type": "page", "url": "https://example.com/new"}]
        browser_url = self._start_cdp_list_server({"requests": [], "list_payloads": [before, before, after]})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance_root.mkdir(parents=True, exist_ok=True)
            state = daemon_core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-browser",
                main_thread_id="thr-main",
            )
            server = daemon_mailbox.DaemonMailboxServer(
                socket_path=daemon_mailbox.mailbox_socket_path(instance_root),
                local_actor_address={"role_id": "dev", "actor_id": "act-dev-browser"},
                handlers=[],
                state=state,
                now=lambda: "2026-06-24T00:00:00Z",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                extra_env={"BUDDYSWITCH_INSTANCE_ROOT": str(instance_root)},
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(len(forwarded), 1)
            self.assertIn("Browser page TTL: 600s.", json.dumps(responses, ensure_ascii=True))
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["type"], "browser.page.expired")
            self.assertEqual(schedule["payload"]["target_id"], "target-new-page")
            self.assertEqual(schedule["payload"]["target_url"], "https://example.com/new")
            self.assertEqual(schedule["payload"]["ttl_seconds"], 600)
            self.assertFalse(thread.is_alive())

    def test_new_page_reaching_hint_threshold_forwards_and_appends_page_hint(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(4)})

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
        )

        self.assertEqual(len(forwarded), 1)
        arguments = forwarded[0]["params"]["arguments"]
        self.assertIs(arguments["background"], True)
        self.assertIn(SOFT_PAGE_HINT_5, json.dumps(responses, ensure_ascii=True))

    def test_new_page_blocks_locally_at_hard_page_limit_without_forwarding(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(10)})

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertIs(response["result"]["isError"], True)
        self.assertIn(HARD_PAGE_BLOCK, response["result"]["content"][0]["text"])

    def test_new_page_reuses_exact_url_at_hard_page_limit_without_forwarding(self) -> None:
        target_url = "https://example.com/new"
        targets = _page_targets(9) + [{"id": "target-existing-page", "type": "page", "url": target_url}]
        browser_url = self._start_cdp_list_server({"requests": [], "targets": targets})

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": target_url})],
            browser_url=browser_url,
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        text = response["result"]["content"][0]["text"]
        self.assertIn("target-existing-page", text)
        self.assertIn("No new page was opened", text)

    def test_new_page_reports_page_count_verification_failure_without_forwarding(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "list_fail": True})

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertIs(response["result"]["isError"], True)
        self.assertIn("page-count", response["result"]["content"][0]["text"].lower())

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

    def test_focus_rpc_methods_are_rejected_without_forwarding(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "Page.bringToFront", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "Target.activateTarget", "params": {}},
            ]
        )

        self.assertEqual(forwarded, [])
        by_id = {response["id"]: response for response in responses}
        for request_id, method in ((1, "Page.bringToFront"), (2, "Target.activateTarget")):
            with self.subTest(method=method):
                response = by_id[request_id]
                self.assertEqual(response["error"]["code"], -32000)
                self.assertIn(method, response["error"]["message"])
                self.assertIn("non-activating", response["error"]["message"])

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
