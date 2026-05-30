#!/usr/bin/env python3
"""Runless Market evidence tests and shared CDP helper fixtures."""

from __future__ import annotations

import json
import socket
import subprocess
import threading
import sys
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"
DEV_REQUEST = "实现 landing page hero 文案和 CTA 调整"
TEST_REQUEST = "验证 landing page hero 和 CTA 行为"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class _CDPState:
    """Shared fake CDP state used by multiple test modules."""

    def __init__(
        self,
        *,
        version_ok: bool,
        pages: list[dict[str, object]] | None = None,
        allow_put_new_about_blank: bool = False,
        allow_get_new_about_blank: bool = False,
    ) -> None:
        self.version_ok = version_ok
        self.pages = list(pages or [])
        self.allow_put_new_about_blank = allow_put_new_about_blank
        self.allow_get_new_about_blank = allow_get_new_about_blank
        self.calls: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def record_call(self, *, method: str, path: str, query: str) -> None:
        with self._lock:
            self.calls.append({"method": method, "path": path, "query": query})

    def snapshot_calls(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self.calls)

    def has_usable_page(self) -> bool:
        for page in self.pages:
            if not isinstance(page, dict):
                continue
            if page.get("type") != "page":
                continue
            raw_url = page.get("url")
            if not isinstance(raw_url, str):
                continue
            normalized = raw_url.strip().lower()
            if normalized == "about:blank":
                return True
            if normalized.startswith("chrome://") or normalized.startswith("chrome-untrusted://") or normalized.startswith("devtools://"):
                continue
            return True
        return False


def _make_cdp_handler(state: _CDPState) -> type[BaseHTTPRequestHandler]:
    class _CDPHandler(BaseHTTPRequestHandler):
        def _handle(self, method: str) -> None:
            path = self.path
            query = ""
            if "?" in self.path:
                path, query = self.path.split("?", 1)
            state.record_call(method=method, path=path, query=query)

            if path == "/json/version":
                if state.version_ok:
                    body = b'{"Browser":"test"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(503)
                self.end_headers()
                return

            if path == "/json/list":
                body = json.dumps(state.pages, ensure_ascii=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/json/new" and query == "about:blank":
                if method == "PUT" and state.allow_put_new_about_blank:
                    if not state.has_usable_page():
                        state.pages.append({"id": "target-about-blank", "type": "page", "url": "about:blank"})
                    body = b'{"id":"target-about-blank"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if method == "GET" and state.allow_get_new_about_blank:
                    body = b'{"id":"target-about-blank"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(405)
                self.end_headers()
                return

            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_PUT(self) -> None:  # noqa: N802
            self._handle("PUT")

        def log_message(self, *_args: object) -> None:
            return

    return _CDPHandler


class MarketBrowserEvidenceTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, buddy: str = "market", instance_id: str = "inst-market") -> Path:
        instance_id = self._runtime_instance_id(buddy=buddy, label=instance_id)
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_id = self._runtime_instance_id(buddy=buddy, label=instance_id)
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-market-evidence-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "tool": tool,
                    "action": action,
                    "args": args,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        payload: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
        return payload

    def _seed_market_task_and_artifact(self, *, instance_id: str = "inst-market") -> tuple[str, str]:
        track = env_store.create_track("track-market-evidence", "Market Evidence", owner_buddy="market")
        task_id = "task-market-evidence"
        self._write_taskbox_task(
            instance_id=instance_id,
            buddy="market",
            task_id=task_id,
            title="Market evidence task",
            track_id=track["id"],
        )
        artifact = env_store.create_artifact_revision(
            artifact_id="art-market-evidence-r1",
            title="Market Evidence Brief",
            summary="seed",
            body="market",
            template="brief",
            supersedes_artifact_id=None,
            created_by="market",
            authors=["market"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=track["id"],
            artifact_id=artifact["id"],
            label="Market Evidence Brief",
            from_buddy="market",
            summary="seed",
        )
        return task_id, artifact["id"]

    def test_market_evidence_requires_artifact_target(self) -> None:
        instance_json = self._instance_json(instance_id="inst-market-target")
        _, artifact_id = self._seed_market_task_and_artifact(instance_id="inst-market-target")

        missing_target = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-target",
            buddy="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact"},
        )
        self.assertFalse(missing_target.get("ok"), msg=missing_target)
        self.assertEqual((missing_target.get("error") or {}).get("code"), "E_EVIDENCE_PAYLOAD")

        wrong_type = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-target",
            buddy="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "run", "target_id": "run-old"},
        )
        self.assertFalse(wrong_type.get("ok"), msg=wrong_type)
        self.assertEqual((wrong_type.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")

        ok_issue = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-target",
            buddy="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertTrue(ok_issue.get("ok"), msg=ok_issue)

    def test_browser_evidence_cli_target_type_is_artifact_only(self) -> None:
        help_result = subprocess.run(
            ["python3", "scripts/browser_evidence.py", "issue", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, msg=help_result.stderr)
        self.assertIn("artifact", help_result.stdout)
        self.assertNotIn("memory", help_result.stdout)

        rejected = subprocess.run(
            [
                "python3",
                "scripts/browser_evidence.py",
                "issue",
                "--target-type",
                "memory",
                "--target-id",
                "mem-old",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(rejected.returncode, 2, msg=rejected.stdout + rejected.stderr)
        self.assertIn("invalid choice", rejected.stderr)

    def test_market_artifact_write_with_browser_evidence_is_runless(self) -> None:
        instance_id = "inst-market-write"
        instance_json = self._instance_json(instance_id=instance_id)
        _, artifact_id = self._seed_market_task_and_artifact(instance_id=instance_id)

        issued = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertTrue(issued.get("ok"), msg=issued)
        token = issued.get("tool_evidence")
        self.assertIsInstance(token, dict, msg=issued)
        assert isinstance(token, dict)

        created = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="market",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-market-evidence-r2",
                "title": "Market update",
                "summary": "runless evidence ref",
                "template": "brief",
                "body": "updated",
                "supersedes_artifact_id": artifact_id,
                "source_refs": [
                    {"type": "artifact", "id": artifact_id},
                    {"type": "note", "label": f"evidence:{token.get('token_id')}"},
                ],
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertTrue(created.get("state_changed"), msg=created)
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())
        self.assertFalse(self._runtime_path("runs/raw").exists())

    def test_approved_downgrade_records_reason_on_target_token(self) -> None:
        instance_json = self._instance_json(instance_id="inst-market-downgrade")
        _, artifact_id = self._seed_market_task_and_artifact(instance_id="inst-market-downgrade")

        approved = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-market-downgrade",
            buddy="market",
            tool="evidence",
            action="approve_downgrade",
            args={
                "target_type": "artifact",
                "target_id": artifact_id,
                "reason": "Browser unavailable; user approved fallback.",
            },
        )
        self.assertTrue(approved.get("ok"), msg=approved)
        evidence = approved.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=approved)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertEqual(evidence.get("reason"), "Browser unavailable; user approved fallback.")
        self.assertNotIn("run_id", evidence)


if __name__ == "__main__":
    unittest.main()
