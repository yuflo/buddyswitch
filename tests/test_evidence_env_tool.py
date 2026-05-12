#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool evidence env tool operations."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tests.test_market_browser_evidence import (  # noqa: E402
    MARKET_REQUEST,
    _CDPState,
    _make_cdp_handler,
)

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"
INSTANCE_ID = "inst-market-evidence-example"
ENV_CLIENT = ROOT / "scripts" / "env" / "client.py"


class EvidenceEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = INSTANCE_ID,
        buddy: str = "market",
        status: str = "active",
        browser_port: int | None = None,
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": browser_port,
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = INSTANCE_ID,
        buddy: str = "market",
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": "env.tool",
                "payload": {"tool": "evidence", "action": action, "args": args},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _prepare_market(self, *, instance_json: Path, instance_id: str = INSTANCE_ID) -> dict[str, object]:
        prepared = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": "market",
                "method": "prepare",
                "payload": {"text": MARKET_REQUEST},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertTrue(prepared.get("ok"), msg=prepared)
        payload = prepared.get("payload")
        self.assertIsInstance(payload, dict, msg=prepared)
        assert isinstance(payload, dict)
        return payload

    def _start_cdp_server(self, state: _CDPState) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = HTTPServer(("127.0.0.1", port), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)
        return port

    def _evidence_token_paths(self, instance_json: Path) -> list[Path]:
        root = instance_json.parent / "runtime" / "evidence-tokens"
        return sorted(root.glob("*/*.json")) if root.exists() else []

    def test_issue_browser_succeeds_through_env_tool_and_writes_scoped_token(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
        )
        port = self._start_cdp_server(state)
        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)

        response = self._dispatch(
            action="issue_browser",
            args={"context": context},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "evidence")
        self.assertEqual(response.get("action"), "evidence.issue_browser")
        tool_evidence = response.get("tool_evidence")
        self.assertIsInstance(tool_evidence, dict, msg=response)
        assert isinstance(tool_evidence, dict)
        token = tool_evidence.get("browser_cockpit_token")
        self.assertIsInstance(token, str, msg=response)
        assert isinstance(token, str)

        token_paths = self._evidence_token_paths(instance_json)
        self.assertEqual(len(token_paths), 1)
        token_record = json.loads(token_paths[0].read_text(encoding="utf-8"))
        self.assertEqual(token_record["token"], token)
        self.assertEqual(token_record["mode"], "browser-cockpit-preflight")
        self.assertEqual(token_record["instance_id"], INSTANCE_ID)
        self.assertEqual(token_record["buddy_id"], "market")
        self.assertEqual(token_record["task_id"], context["current_task_id"])
        self.assertEqual(token_record["track_id"], context["current_track_id"])
        self.assertEqual(token_record["context_revision"], context["context_revision"])
        self.assertEqual(token_record["run_id"], context["run_envelope"]["run_id"])
        self.assertEqual(response["feedback"]["token_scope"]["run_id"], context["run_envelope"]["run_id"])

    def test_approve_downgrade_requires_reason_and_writes_no_token(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)

        response = self._dispatch(
            action="approve_downgrade",
            args={"context": context, "reason": " "},
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("reason", response.get("error", {}).get("message", ""))
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_stale_context_revision_rejects_before_writing_token(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        context["context_revision"] = "ctx-stale"
        context["run_envelope"]["sequence"] = 1

        response = self._dispatch(
            action="approve_downgrade",
            args={"context": context, "reason": "User explicitly approved a one-off downgrade."},
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "prepare.context_revision")
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_live_broker_evidence_cli_uses_env_tool_and_returns_structured_rejection(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        context["context_revision"] = "ctx-stale"
        context_path = self._runtime_path("tmp/stale-context.json")
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(json.dumps(context, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        socket_path = self._runtime_path("runtime/runtime-broker.socket")
        pid_path = self._runtime_path("runtime/runtime-broker.pid")
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        broker_env = os.environ.copy()
        broker_env.update(
            {
                "BUDDYSWITCH_SHARED_ROOT": str(self.runtime_root),
                "BUDDYSWITCH_STATE_ROOT": str(self.runtime_root),
            }
        )
        broker = subprocess.Popen(
            [
                "python3",
                str(ROOT / "scripts" / "runtime_kernel" / "broker.py"),
                "serve",
                "--socket",
                str(socket_path),
                "--pid-file",
                str(pid_path),
                "--instance-json",
                str(instance_json),
                "--manifest",
                str(MANIFEST),
            ],
            cwd=ROOT,
            env=broker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if socket_path.exists():
                    break
                if broker.poll() is not None:
                    break
                time.sleep(0.05)
            if broker.poll() is not None:
                stderr = broker.stderr.read() if broker.stderr else "broker exited"
                self.fail(stderr)
            self.assertTrue(socket_path.exists(), "broker socket was not created")

            client_env = os.environ.copy()
            client_env.update(
                {
                    "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
                    "BUDDYSWITCH_INSTANCE_ID": INSTANCE_ID,
                    "BUDDYSWITCH_ACTIVE_BUDDY": "market",
                }
            )
            completed = subprocess.run(
                [
                    "python3",
                    str(ENV_CLIENT),
                    "evidence",
                    "approve-downgrade",
                    "--context",
                    str(context_path),
                    "--reason",
                    "User explicitly approved a one-off downgrade.",
                ],
                cwd=ROOT,
                env=client_env,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )
        finally:
            broker.terminate()
            try:
                broker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=5)

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("tool"), "evidence")
        self.assertEqual(payload.get("action"), "evidence.approve_downgrade")
        self.assertEqual(payload.get("permission_boundary"), "prepare.context_revision")
        self.assertEqual(self._evidence_token_paths(instance_json), [])


if __name__ == "__main__":
    unittest.main()
