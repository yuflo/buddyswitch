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

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

import buddyswitch.foundation.runtime_broker.broker as runtime_broker  # noqa: E402
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo  # noqa: E402
from tests.support.python import PYTHON  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
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


from tests.support.processes import run_process

class MarketEvidenceHarness(RuntimeWorkspaceTestCase):
    def _instance_json(self, *, role: str = "market", actor_id: str = "act-market") -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        path = self._runtime_path(f"instances/{actor_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
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
        self._seed_active_task_for_instance(
            instance_json=path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-market-evidence",
        )
        return path
    def _dispatch(self, *, instance_json: Path, actor_id: str, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-market-evidence-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "actor_id": actor_id,
                    "active_role": role,
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
    def _seed_market_artifact(self, *, actor_id: str = "act-market") -> str:
        actual_actor_id = self._runtime_actor_id(role="market", label=actor_id)
        actor = {"actor_id": actual_actor_id, "role_id": "market"}
        artifact = artifact_repo.create_artifact_revision(
            artifact_id="art-market-evidence-r1",
            title="Market Evidence Brief",
            summary="seed",
            body="market",
            template="brief",
            supersedes_artifact_id=None,
            created_by_identity=actor["actor_id"],
            author_identities=[actor["actor_id"]],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        artifact = artifact_repo.update_artifact(str(artifact["id"]), {"is_current": True})
        return artifact["id"]

__all__ = [name for name in globals() if not name.startswith('__')]
