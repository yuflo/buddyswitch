"""Live child-protocol proof for the page-expiry MCP session."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import shlex
import tempfile
from unittest import mock

from tests.support.processes import ResourceLedger


class _OwnedSubprocessProxy:
    def __init__(self, module: object, ledger: ResourceLedger) -> None:
        self._module = module
        self._ledger = ledger

    def __getattr__(self, name: str) -> object:
        return getattr(self._module, name)

    def Popen(self, command: list[str], **kwargs: object) -> object:  # noqa: N802
        kwargs.pop("bufsize", None)
        return self._ledger.start_process(command, **kwargs)


def test_run_mcp_tool_waits_for_initialize_before_tool_call() -> None:
    handler = importlib.import_module("browser_page_expired_handler")
    python = os.environ["BUDDYSWITCH_PYTHON"]
    with tempfile.TemporaryDirectory() as temp_root:
        stub_path = Path(temp_root) / "staged_mcp.py"
        stub_path.write_text(
            "\n".join(
                [
                    "import json, select, sys",
                    "first = sys.stdin.readline()",
                    "if not first:",
                    "    raise SystemExit(1)",
                    "ready, _, _ = select.select([sys.stdin], [], [], 0.05)",
                    "if ready:",
                    "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': 'init', 'result': {'protocolVersion': '2024-11-05'}}) + '\\n')",
                    "    sys.stdout.flush()",
                    "    raise SystemExit(0)",
                    "init = json.loads(first)",
                    "sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': init['id'], 'result': {'protocolVersion': '2024-11-05'}}) + '\\n')",
                    "sys.stdout.flush()",
                    "for raw in sys.stdin:",
                    "    message = json.loads(raw)",
                    "    if message.get('method') == 'tools/call':",
                    "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': {'content': [{'type': 'text', 'text': '## Pages\\n2: https://example.test [selected]'}]}}) + '\\n')",
                    "        sys.stdout.flush()",
                    "        raise SystemExit(0)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        command = f"{shlex.quote(python)} {shlex.quote(str(stub_path))}"
        proxy = _OwnedSubprocessProxy(
            handler.subprocess,
            ResourceLedger.from_environment(),
        )

        with (
            mock.patch.object(handler, "subprocess", proxy),
            mock.patch.dict(
                os.environ,
                {"BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_COMMAND": command},
            ),
        ):
            message = handler._run_mcp_tool(
                "http://127.0.0.1:9444",
                "list_pages",
                {},
            )

        assert "## Pages" in handler._tool_response_text(message)
