"""Tests for runtime broker request routing and identity checks."""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import unittest
import contextlib
import importlib
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from tests.support.paths import REPO_ROOT
from tests.support.cli import pid_alive, wait_until
from tests.support.fake_cdp import FakeCdpServer, write_fake_chrome
from tests.support.processes import ResourceLedger

ROOT = REPO_ROOT

import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
import buddyswitch.runtime_kernel.client as runtime_client  # noqa: E402
from tests.support.runtime import RuntimeTestWorkspace  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
BROKER_V2_PROTOCOL = "buddyswitch-runtime-broker/v2"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


def port_accepts(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.2)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"missing required Runtime Broker V2 module: {name}") from exc


class RuntimeBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = RuntimeTestWorkspace()
        self.addCleanup(self.workspace.close)
        self.runtime_root = self.workspace.root

    @staticmethod
    def _error_boundary(response: dict[str, object]) -> str | None:
        boundary_top = response.get("permission_boundary")
        if isinstance(boundary_top, str):
            return boundary_top
        error = response.get("error")
        if not isinstance(error, dict):
            return None
        boundary = error.get("permission_boundary")
        return boundary if isinstance(boundary, str) else None

    def _instance_json(
        self,
        *,
        actor_id: str = "act-pm-example",
        role: str = "pm",
        status: str = "active",
    ) -> Path:
        actor_id = self.workspace.actor_id(role=role, label=actor_id)
        instance_root = self.workspace.instance_root(actor_id)
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": status,
                    "instance_root": str(instance_root),
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-06T00:00:00Z",
                    "updated_at": "2026-05-06T00:00:00Z",
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
        method: str,
        params: dict[str, object],
        actor_id: str = "act-pm-example",
        role: str = "pm",
        instance_json: Path,
    ) -> dict[str, object]:
        actor_id = self.workspace.actor_id(role=role, label=actor_id)
        request_params = dict(params)
        request_params.setdefault("actor_id", actor_id)
        request_params.setdefault("active_role", role)
        request: dict[str, object] = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": f"req-test-{uuid.uuid4().hex}",
            "method": method,
            "params": request_params,
            "deadline_ms": 35000,
        }
        if method == "persist":
            context = request_params.get("context")
            result = request_params.get("result")
            if isinstance(context, dict) and isinstance(result, dict):
                result_hash = runtime_client.canonical_result_hash(result)
                request["idempotency_key"] = f"persist:{result_hash}"
                request["result_hash"] = result_hash
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), BROKER_V2_PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result

        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
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

    def _write_fake_chrome(self, path: Path, argv_path: Path) -> None:
        write_fake_chrome(path, argv_path)

    def _start_parent_cdp(self, activation_path: Path | None = None) -> FakeCdpServer:
        server = FakeCdpServer(activation_path=activation_path).start()
        self.addCleanup(server.close)
        return server

    def _terminate_process(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        if not wait_until(lambda: not pid_alive(pid), timeout=2.0):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return

    def _start_fake_chrome(self, chrome_bin: Path, *, port: int, profile_dir: Path, log_file: Path) -> subprocess.Popen[str]:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as output:
            proc = ResourceLedger.from_environment().start_process(
                [
                    str(chrome_bin),
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={profile_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "about:blank",
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
            )
        self.addCleanup(self._terminate_process, proc.pid)
        self.assertTrue(wait_until(lambda: port_accepts(port), timeout=3.0), "fake Chrome endpoint did not become ready")
        return proc

    def _install_browser_contract_fakes(self, dispatcher: object) -> list[dict[str, object]]:
        calls: list[dict[str, object]] = []

        class FakeBrowserRuntimeManager:
            @staticmethod
            def acquire(**kwargs: object) -> dict[str, object]:
                calls.append({"method": "acquire", **kwargs})
                return {
                    "ok": True,
                    "browser_url": "http://127.0.0.1:9444",
                    "browser_port": 9444,
                    "state_changed": True,
                    "durability": "runtime",
                }

            @staticmethod
            def status(**kwargs: object) -> dict[str, object]:
                calls.append({"method": "status", **kwargs})
                return {
                    "ok": True,
                    "browser_port": 9444,
                    "ready": True,
                    "ownership": "owned",
                    "state_changed": False,
                    "durability": "runtime",
                }

            @staticmethod
            def release(**kwargs: object) -> dict[str, object]:
                calls.append({"method": "release", **kwargs})
                return {
                    "ok": True,
                    "handled": True,
                    "skip_reason": None,
                    "state_changed": True,
                    "durability": "runtime",
                }

        patcher_manager = patch.object(
            dispatcher,
            "browser_runtime",
            FakeBrowserRuntimeManager,
            create=True,
        )
        patcher_manager.start()
        self.addCleanup(patcher_manager.stop)
        return calls

    def test_browser_open_url_method_is_removed(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        calls = self._install_browser_contract_fakes(dispatcher)
        instance_json = self._instance_json()

        response = self._dispatch(
            method="browser.open_url",
            params={
                "target_url": "https://example.com/search?q=contract",
                "source_tool": "search.open_browser",
            },
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_RUNTIME_BROKER_PROTOCOL")
        self.assertEqual(self._error_boundary(response), "broker-protocol")
        self.assertNotIn("browser.open_url", json.dumps(response.get("allowed_next_actions", []), ensure_ascii=True))
        self.assertEqual(calls, [])

    def test_demand_ingress_special_method_is_unsupported(self) -> None:
        instance_json = self._instance_json(
            actor_id="act-market-triage",
            role="market",
        )
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["thread_id"] = "thr-main"
        instance_json.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        response = self._dispatch(
            method="demand.ingress.resolve",
            params={},
            actor_id="act-market-triage",
            role="market",
            instance_json=instance_json,
        )

        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(
            response["error"]["code"],
            "E_RUNTIME_BROKER_PROTOCOL",
        )
        dispatcher_source = (
            ROOT / "src/buddyswitch/runtime_kernel/dispatcher.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"demand.ingress.resolve"', dispatcher_source)

    def test_browser_acquire_method_has_structured_contract(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        calls = self._install_browser_contract_fakes(dispatcher)
        instance_json = self._instance_json()

        response = self._dispatch(
            method="browser.acquire",
            params={"reason": "chrome-devtools-cockpit"},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("browser_url"), "http://127.0.0.1:9444")
        self.assertEqual(response.get("browser_port"), 9444)
        self.assertEqual(response.get("state_changed"), True)
        self.assertEqual(response.get("durability"), "runtime")
        self.assertEqual([call["method"] for call in calls], ["acquire"])

    def test_browser_status_method_has_structured_contract(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        calls = self._install_browser_contract_fakes(dispatcher)
        instance_json = self._instance_json()

        response = self._dispatch(method="browser.status", params={}, instance_json=instance_json)

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("browser_port"), 9444)
        self.assertEqual(response.get("ready"), True)
        self.assertEqual(response.get("ownership"), "owned")
        self.assertEqual(response.get("state_changed"), False)
        self.assertEqual(response.get("durability"), "runtime")
        self.assertEqual([call["method"] for call in calls], ["status"])

    def test_browser_release_method_has_structured_contract(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        calls = self._install_browser_contract_fakes(dispatcher)
        instance_json = self._instance_json()

        response = self._dispatch(
            method="browser.release",
            params={"reason": "page_idle_empty"},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("handled"), True)
        self.assertIsNone(response.get("skip_reason"))
        self.assertEqual(response.get("state_changed"), True)
        self.assertEqual(response.get("durability"), "runtime")
        self.assertEqual([call["method"] for call in calls], ["release"])

    def test_broker_browser_release_refuses_unrecorded_runtime_process(self) -> None:
        actor_label = "act-pm-broker-browser-release"
        instance_json = self._instance_json(actor_id=actor_label, role="pm")
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        instance_root = Path(str(instance_payload["instance_root"]))
        port = self._start_parent_cdp().port
        instance_payload["browser_port"] = port
        instance_json.write_text(json.dumps(instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        chrome_bin = self.runtime_root / "fake-chrome.py"
        chrome_argv = self.runtime_root / "fake-chrome-argv.jsonl"
        self._write_fake_chrome(chrome_bin, chrome_argv)
        chrome_proc = self._start_fake_chrome(
            chrome_bin,
            port=port,
            profile_dir=instance_root / "browser" / "profile",
            log_file=instance_root / "browser" / "chrome.log",
        )
        (instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)

        response = self._dispatch(
            method="browser.release",
            params={"reason": "test_cleanup"},
            actor_id=actor_label,
            role="pm",
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("handled"), True)
        self.assertEqual(response.get("ownership"), "unknown")
        self.assertTrue(pid_alive(chrome_proc.pid), "release must not signal a process without an exact identity record")

    def test_browser_method_rejects_actor_mismatch(self) -> None:
        instance_json = self._instance_json()

        response = self._dispatch(
            method="browser.acquire",
            params={
                "actor_id": self.workspace.actor_id(role="pm", label="act-pm-other"),
                "reason": "chrome-devtools-cockpit",
            },
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_RUNTIME_BROKER_PERMISSION")
        self.assertEqual(self._error_boundary(response), "active-instance")

    def test_browser_open_url_is_rejected_before_url_validation(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        calls = self._install_browser_contract_fakes(dispatcher)
        instance_json = self._instance_json()

        response = self._dispatch(
            method="browser.open_url",
            params={"target_url": "javascript:alert(1)", "source_tool": "search.open_browser"},
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_RUNTIME_BROKER_PROTOCOL")
        self.assertEqual(self._error_boundary(response), "broker-protocol")
        self.assertNotIn("E_BROWSER_INVALID_URL", json.dumps(response, ensure_ascii=True))
        self.assertNotIn("browser.open_url", json.dumps(response.get("allowed_next_actions", []), ensure_ascii=True))
        self.assertEqual(calls, [])

    def test_env_tool_requests_succeed_with_matching_identity(self) -> None:
        instance_json = self._instance_json()
        before_instance = json.loads(instance_json.read_text(encoding="utf-8"))

        summarized = self._dispatch(
            method="env.tool",
            params={"tool": "context", "action": "summarize", "args": {}},
            instance_json=instance_json,
        )
        self.assertTrue(summarized["ok"], msg=summarized)
        self.assertEqual(summarized["action"], "context.summarize")

        listed_sources = self._dispatch(
            method="env.tool",
            params={
                "tool": "context",
                "action": "list_sources",
                "args": {},
            },
            instance_json=instance_json,
        )
        self.assertTrue(listed_sources["ok"], msg=listed_sources)

        after_instance = json.loads(instance_json.read_text(encoding="utf-8"))
        self.assertEqual(after_instance, before_instance)
        self.assertFalse(self.workspace.path("buddyswitch/content/runs").exists())
        self.assertFalse(self.workspace.path("runs/raw").exists())

    def test_env_tool_mutation_and_read_have_one_broker_terminal_truth(self) -> None:
        instance_json = self._instance_json()
        actor_id = str(json.loads(instance_json.read_text(encoding="utf-8"))["actor_id"])
        self.workspace.seed_active_task(
            instance_json=instance_json,
            role="pm",
            actor_id=actor_id,
            task_slug="broker-terminal-truth",
        )

        created = self._dispatch(
            method="env.tool",
            params={
                "tool": "track",
                "action": "create",
                "args": {
                    "track_id": "track-broker-terminal-truth",
                    "title": "Broker terminal truth",
                    "outcome": "Prove persisted mutation and read results agree.",
                    "now": {"next": "Read the persisted Track.", "blocker": None},
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertIs(created.get("state_changed"), True, msg=created)
        self.assertEqual(created.get("durability"), "durable", msg=created)

        opened = self._dispatch(
            method="env.tool",
            params={
                "tool": "track",
                "action": "open",
                "args": {"track_id": "track-broker-terminal-truth"},
            },
            instance_json=instance_json,
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        self.assertIs(opened.get("state_changed"), False, msg=opened)
        self.assertEqual((opened.get("track") or {}).get("id"), "track-broker-terminal-truth")

    def test_env_tool_rejects_legacy_handoff_tool_payload(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(
            method="env.tool",
            params={"tool": "handoff", "action": "list", "args": {}},
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_ENV_TOOL", msg=response)
        self.assertEqual(response.get("permission_boundary"), "env.tool", msg=response)

    def test_context_reports_direct_actor_private_writable_surface(self) -> None:
        actor_id = self.workspace.actor_id(role="pm", label="act-pm-alt-workspace")
        instance_root = self.workspace.instance_root(actor_id)
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        (workspace_dir / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "pm",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-06T00:00:00Z",
                    "updated_at": "2026-05-06T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        summarized = self._dispatch(
            method="env.tool",
            params={
                "tool": "context",
                "action": "summarize",
                "args": {},
            },
            actor_id=actor_id,
            role="pm",
            instance_json=instance_json,
        )
        self.assertTrue(summarized.get("ok"), msg=summarized)
        surfaces = summarized.get("writable_surfaces")
        self.assertIsInstance(surfaces, dict, msg=summarized)
        assert isinstance(surfaces, dict)
        persistent = surfaces.get("persistent_files")
        self.assertIsInstance(persistent, dict, msg=summarized)
        assert isinstance(persistent, dict)
        self.assertEqual(persistent.get("env"), "BUDDYSWITCH_ACTOR_PRIVATE_DIR")
        self.assertEqual(persistent.get("workspace_relative_root"), "private")
        self.assertFalse(persistent.get("mutates_product_state"))

        target = workspace_dir / "private" / "broker" / "out.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("broker\n", encoding="utf-8")
        self.assertTrue(target.exists(), msg=target)
        self.assertEqual(target.read_text(encoding="utf-8"), "broker\n")
        self.assertFalse(self.workspace.path("buddyswitch/local/private/pm/broker/out.txt").exists())
        self.assertFalse(self.workspace.path("state/buddyswitch/local/private/pm/broker/out.txt").exists())

    def test_direct_actor_private_files_use_shared_state_root(self) -> None:
        actor_id = self.workspace.actor_id(role="pm", label="act-pm-alt-workspace-lifecycle")
        instance_root = self.workspace.instance_root(actor_id)
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        (workspace_dir / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "pm",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-19T00:00:00Z",
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        target = workspace_dir / "private" / "broker" / "lifecycle.txt"
        wrong_runtime_root = self.workspace.path("state/buddyswitch/local/private/pm/broker/lifecycle.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("lifecycle\n", encoding="utf-8")
        self.assertTrue(target.exists(), msg=target)
        self.assertFalse(wrong_runtime_root.exists(), msg=wrong_runtime_root)
        self.assertEqual(target.read_text(encoding="utf-8"), "lifecycle\n")
        target.unlink()
        self.assertFalse(target.exists(), msg=target)

    def test_env_tool_requests_enter_shared_runtime_lock(self) -> None:
        instance_json = self._instance_json()
        lock_sessions: list[dict[str, object]] = []

        @contextlib.contextmanager
        def fake_lock(session: dict[str, object], **_kwargs: object):
            lock_sessions.append(session)
            yield

        with patch(
            "buddyswitch.runtime_support.turn_runtime._hold_product_runtime_lock",
            side_effect=fake_lock,
        ):
            summarized = self._dispatch(
                method="env.tool",
                params={"tool": "context", "action": "summarize", "args": {}},
                instance_json=instance_json,
            )
            self.assertTrue(summarized["ok"], msg=summarized)
            listed_sources = self._dispatch(
                method="env.tool",
                params={
                    "tool": "context",
                    "action": "list_sources",
                    "args": {},
                },
                instance_json=instance_json,
            )
            self.assertTrue(listed_sources["ok"], msg=listed_sources)

        expected_actor_id = json.loads(instance_json.read_text(encoding="utf-8"))["actor_id"]
        self.assertEqual([session["actor_id"] for session in lock_sessions], [expected_actor_id, expected_actor_id])
        self.assertTrue(all(session["instance_json"] == instance_json for session in lock_sessions))

    def test_env_tool_dispatch_does_not_publish_retired_repo_root(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        instance_json = self._instance_json()
        active_actor_id = json.loads(instance_json.read_text(encoding="utf-8"))["actor_id"]
        session = dispatcher.RuntimeBrokerSession(instance_json_path=instance_json, manifest_path=MANIFEST)
        seen_repo_roots: list[str | None] = []

        def fake_dispatch_env_tool_request(**_kwargs: object) -> dict[str, object]:
            seen_repo_roots.append(os.environ.get("BUDDYSWITCH_REPO_ROOT"))
            return {"ok": True, "tool": "context", "action": "context.summarize"}

        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-env-tool-repo-root",
            "method": "env.tool",
            "params": {
                "actor_id": active_actor_id,
                "active_role": "pm",
                "tool": "context",
                "action": "summarize",
                "args": {},
            },
            "deadline_ms": 35000,
        }

        os.environ.pop("BUDDYSWITCH_REPO_ROOT", None)
        with patch(
            "buddyswitch.runtime_kernel.dispatcher.dispatch_env_tool_request",
            side_effect=fake_dispatch_env_tool_request,
        ):
            response = dispatcher.dispatch_runtime_request(request, session)

        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(seen_repo_roots, [None])

    def test_env_tool_dispatch_accepts_projected_manifest_without_source_locator(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        instance_json = self._instance_json()
        active_actor_id = json.loads(instance_json.read_text(encoding="utf-8"))["actor_id"]
        projected_workspace = self.workspace.path("projected-runtime-workspace")
        projected_manifest = projected_workspace / "buddyswitch" / "manifest.toml"
        projected_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, projected_manifest)
        session = dispatcher.RuntimeBrokerSession(
            instance_json_path=instance_json,
            manifest_path=projected_manifest,
        )
        seen_repo_roots: list[str | None] = []

        def fake_dispatch_env_tool_request(**_kwargs: object) -> dict[str, object]:
            seen_repo_roots.append(os.environ.get("BUDDYSWITCH_REPO_ROOT"))
            return {"ok": True, "tool": "context", "action": "context.summarize"}

        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-env-tool-explicit-repo-root",
            "method": "env.tool",
            "params": {
                "actor_id": active_actor_id,
                "active_role": "pm",
                "tool": "context",
                "action": "summarize",
                "args": {},
            },
            "deadline_ms": 35000,
        }

        os.environ.pop("BUDDYSWITCH_REPO_ROOT", None)
        with patch(
            "buddyswitch.runtime_kernel.dispatcher.dispatch_env_tool_request",
            side_effect=fake_dispatch_env_tool_request,
        ):
            response = dispatcher.dispatch_runtime_request(request, session)

        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(seen_repo_roots, [None])
        self.assertFalse(hasattr(session, "repo_root_path"))

    def test_rejects_wrong_actor_id(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(
            method="prepare",
            params={"text": PM_REQUEST},
            actor_id="act-other",
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIn("actor_id mismatch", response["error"]["message"])

    def test_rejects_wrong_active_role(self) -> None:
        instance_json = self._instance_json(role="pm")
        active_actor_id = json.loads(instance_json.read_text(encoding="utf-8"))["actor_id"]
        response = self._dispatch(
            method="prepare",
            params={"text": PM_REQUEST, "actor_id": active_actor_id},
            role="market",
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIn("active_role mismatch", response["error"]["message"])

    def test_rejects_inactive_instance(self) -> None:
        instance_json = self._instance_json(status="inactive")
        response = self._dispatch(
            method="prepare",
            params={"text": PM_REQUEST},
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIn("instance is not active", response["error"]["message"])

    def test_env_tool_supports_active_instance_and_identity_checks(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-example", role="dev", status="active")
        active_actor_id = json.loads(instance_json.read_text(encoding="utf-8"))["actor_id"]

        supported = self._dispatch(
            method="env.tool",
            params={"tool": "context", "action": "summarize", "args": {}},
            instance_json=instance_json,
            actor_id="act-dev-example",
            role="dev",
        )
        self.assertTrue(supported["ok"], msg=supported)

        task_gated = self._dispatch(
            method="env.tool",
            params={
                "tool": "track",
                "action": "create",
                "args": {
                    "track_id": "track-broker-role-denied",
                    "title": "Broker Role Denied",
                    "outcome": "Denied",
                    "now": {"next": "Denied", "blocker": None},
                },
            },
            instance_json=instance_json,
            actor_id="act-dev-example",
            role="dev",
        )
        self.assertFalse(task_gated["ok"], msg=task_gated)
        self.assertEqual(task_gated["error"]["code"], "E_TASK_SYS_ACTIVE_TASK_REQUIRED")
        self.assertEqual(task_gated.get("permission_boundary"), "task_sys.active_task")
        self.assertEqual(task_gated.get("active_role"), "dev")

        wrong_instance = self._dispatch(
            method="env.tool",
            params={"tool": "context", "action": "summarize", "args": {}},
            instance_json=instance_json,
            actor_id="act-other",
            role="dev",
        )
        self.assertFalse(wrong_instance["ok"])
        self.assertEqual(self._error_boundary(wrong_instance), "active-instance")

        wrong_role = self._dispatch(
            method="env.tool",
            params={"tool": "context", "action": "summarize", "args": {}, "actor_id": active_actor_id},
            instance_json=instance_json,
            role="pm",
        )
        self.assertFalse(wrong_role["ok"])
        self.assertEqual(self._error_boundary(wrong_role), "active-role")

        inactive_instance_json = self._instance_json(actor_id="act-dev-inactive", role="dev", status="inactive")
        inactive = self._dispatch(
            method="env.tool",
            params={"tool": "context", "action": "summarize", "args": {}},
            instance_json=inactive_instance_json,
            actor_id="act-dev-inactive",
            role="dev",
        )
        self.assertFalse(inactive["ok"])
        self.assertEqual(self._error_boundary(inactive), "active-instance-status")

    def test_legacy_env_task_method_is_rejected(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-example", role="dev", status="active")
        legacy_method = "env" + ".task"
        rejected_legacy = self._dispatch(
            method=legacy_method,
            params={"action": "list", "args": {}},
            instance_json=instance_json,
            actor_id="act-dev-example",
            role="dev",
        )
        self.assertFalse(rejected_legacy["ok"])
        self.assertEqual(self._error_boundary(rejected_legacy), "broker-protocol")

    def test_runtime_broker_client_missing_socket_raises_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "",
            },
            clear=False,
        ):
            with self.assertRaises(runtime_client.RuntimeBrokerError) as raised:
                runtime_client.runtime_broker_socket_from_env()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_UNAVAILABLE")


class RuntimeBrokerServerIsolationTests(unittest.TestCase):
    def _start_server(self, dispatch_fn, *, max_workers: int = 1):
        protocol = _require_module("buddyswitch.runtime_kernel.protocol")
        server_module = _require_module("buddyswitch.runtime_kernel.server")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        config = server_module.RuntimeBrokerConfig(
            socket_path=root / "runtime-broker.sock",
            pid_file=root / "runtime-broker.pid",
            instance_json_path=root / "instance.json",
            manifest_path=MANIFEST,
            max_workers=max_workers,
        )
        broker = server_module.RuntimeBrokerServer(config=config, dispatch_fn=dispatch_fn)
        thread = threading.Thread(target=broker.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(broker.close)
        for _ in range(100):
            if config.socket_path.exists():
                break
            time.sleep(0.01)
        return protocol, config.socket_path, broker, thread

    def _request(self, protocol, socket_path: Path, request: dict[str, object]) -> dict[str, object]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(str(socket_path))
            protocol.write_message(sock, request)
            response = protocol.read_message(sock)
        return response

    def test_client_disconnect_before_response_does_not_stop_server(self) -> None:
        release = threading.Event()

        def dispatch(request):
            release.wait(timeout=2.0)
            return {"ok": True, "pong": request["request_id"]}

        protocol, socket_path, _broker, thread = self._start_server(dispatch, max_workers=1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            protocol.write_message(
                sock,
                {
                    "protocol": BROKER_V2_PROTOCOL,
                    "request_id": "req-disconnect",
                    "method": "ping",
                    "params": {},
                    "deadline_ms": 35000,
                },
            )
        release.set()
        response = self._request(
            protocol,
            socket_path,
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-ping",
                "method": "ping",
                "params": {},
                "deadline_ms": 35000,
            },
        )
        self.assertTrue(thread.is_alive())
        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["result"]["pong"], "req-ping")

    def test_malformed_request_returns_protocol_error_and_next_ping_succeeds(self) -> None:
        def dispatch(request):
            return {"ok": True, "pong": request["request_id"]}

        protocol, socket_path, _broker, thread = self._start_server(dispatch, max_workers=1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(str(socket_path))
            protocol.write_message(sock, {})
            response = protocol.read_message(sock)
            self.assertFalse(response["ok"], msg=response)
            self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PROTOCOL")

        response = self._request(
            protocol,
            socket_path,
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-after-malformed",
                "method": "ping",
                "params": {},
                "deadline_ms": 35000,
            },
        )
        self.assertTrue(thread.is_alive())
        self.assertTrue(response["ok"], msg=response)

    def test_capacity_limit_returns_busy_without_killing_server(self) -> None:
        release = threading.Event()

        def dispatch(request):
            if request["request_id"] == "req-blocking":
                release.wait(timeout=2.0)
            return {"ok": True, "request_id": request["request_id"]}

        protocol, socket_path, _broker, thread = self._start_server(dispatch, max_workers=1)

        def blocking_request() -> None:
            self._request(
                protocol,
                socket_path,
                {
                    "protocol": BROKER_V2_PROTOCOL,
                    "request_id": "req-blocking",
                    "method": "ping",
                    "params": {},
                    "deadline_ms": 35000,
                },
            )

        worker = threading.Thread(target=blocking_request, daemon=True)
        worker.start()
        time.sleep(0.05)
        busy = self._request(
            protocol,
            socket_path,
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-busy",
                "method": "ping",
                "params": {},
                "deadline_ms": 35000,
            },
        )
        self.assertFalse(busy["ok"], msg=busy)
        self.assertEqual(busy["error"]["code"], "E_RUNTIME_BROKER_BUSY")
        self.assertIs(busy["error"]["retriable"], True)
        self.assertEqual(busy["error"]["retry_after_ms"], 250)
        release.set()
        worker.join(timeout=2.0)
        self.assertTrue(thread.is_alive())


class RuntimeBrokerClientV2Tests(unittest.TestCase):
    def _serve_once(self, handler):
        protocol = _require_module("buddyswitch.runtime_kernel.protocol")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        socket_path = Path(temp.name) / "runtime-broker.sock"
        captured: list[dict[str, object]] = []

        def run() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(1)
                conn, _ = server.accept()
                with conn:
                    request = protocol.read_message(conn)
                    captured.append(request)
                    response = handler(request)
                    if response is not None:
                        protocol.write_message(conn, response)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        return protocol, socket_path, thread, captured

    def test_client_sends_v2_request_id_deadline_and_reads_result(self) -> None:
        client = _require_module("buddyswitch.runtime_kernel.client")

        def handler(request):
            return self.protocol.success_response(request["request_id"], {"ok": True, "value": 1})

        self.protocol, socket_path, thread, captured = self._serve_once(handler)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            result = client.request_runtime_broker("prepare", {"text": "Draft onboarding PRD"})
        thread.join(timeout=2.0)
        self.assertEqual(result, {"ok": True, "value": 1})
        self.assertEqual(len(captured), 1)
        outgoing = captured[0]
        self.assertEqual(outgoing["protocol"], BROKER_V2_PROTOCOL)
        self.assertRegex(outgoing["request_id"], r"^req-[0-9a-f-]+")
        self.assertEqual(outgoing["deadline_ms"], 35000)
        self.assertEqual(outgoing["method"], "prepare")
        self.assertEqual(outgoing["params"], {"text": "Draft onboarding PRD"})
        self.assertNotIn("payload", outgoing)

    def test_client_preserves_structured_error_fields(self) -> None:
        client = _require_module("buddyswitch.runtime_kernel.client")

        def handler(request):
            return self.protocol.error_response(
                request["request_id"],
                {
                    "code": "E_RUNTIME_BROKER_PERMISSION",
                    "message": "active role mismatch",
                    "retriable": False,
                    "permission_boundary": "active-role",
                },
            )

        self.protocol, socket_path, thread, _captured = self._serve_once(handler)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "market",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            with self.assertRaises(client.RuntimeBrokerError) as raised:
                client.request_runtime_broker("env.tool", {"tool": "context", "action": "summarize", "args": {}})
        thread.join(timeout=2.0)
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_PERMISSION")
        self.assertEqual(raised.exception.details.get("permission_boundary"), "active-role")
        self.assertIs(raised.exception.details.get("retriable"), False)
        self.assertRegex(raised.exception.details.get("request_id", ""), r"^req-[0-9a-f-]+")

    def test_client_retries_read_only_env_tool_once_after_transport_reset(self) -> None:
        protocol = _require_module("buddyswitch.runtime_kernel.protocol")
        client = _require_module("buddyswitch.runtime_kernel.client")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        socket_path = Path(temp.name) / "runtime-broker.sock"
        captured: list[dict[str, object]] = []

        def run() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(2)
                first, _ = server.accept()
                with first:
                    captured.append(protocol.read_message(first))
                second, _ = server.accept()
                with second:
                    request = protocol.read_message(second)
                    captured.append(request)
                    protocol.write_message(second, protocol.success_response(request["request_id"], {"ok": True}))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            result = client.request_runtime_broker(
                "env.tool",
                {"tool": "context", "action": "summarize", "args": {}},
            )
        thread.join(timeout=2.0)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(captured), 2)
        self.assertNotEqual(captured[0]["request_id"], captured[1]["request_id"])

    def test_client_does_not_retry_persist_without_idempotency_key(self) -> None:
        client = _require_module("buddyswitch.runtime_kernel.client")
        reset_error = client.RuntimeBrokerError(
            "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
            "transport reset",
            details={"retriable": True},
        )
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ), patch.object(client, "_request_once", side_effect=reset_error) as request_once:
            with self.assertRaises(client.RuntimeBrokerError):
                client.request_runtime_broker("persist", {"context": {}, "result": {}})
        self.assertEqual(request_once.call_count, 1)

    def test_client_stale_socket_reports_launcher_reopen_without_self_ensure(self) -> None:
        client = _require_module("buddyswitch.runtime_kernel.client")
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/missing-runtime-broker.sock",
            },
            clear=False,
        ):
            with self.assertRaises(client.RuntimeBrokerError) as raised:
                client.request_runtime_broker("prepare", {"text": "x"})
        self.assertIn(raised.exception.code, {"E_RUNTIME_BROKER_STALE_SOCKET", "E_RUNTIME_BROKER_UNAVAILABLE"})
        self.assertEqual(raised.exception.details.get("permission_boundary"), "product-mode-runtime-broker")
        self.assertEqual(raised.exception.details.get("stop_condition"), "stop_and_report_do_not_bypass_broker")
        self.assertEqual(raised.exception.details.get("socket_path"), "/tmp/missing-runtime-broker.sock")
        self.assertEqual(
            raised.exception.details.get("command_hint"),
            "./buddyswitch-codex instance attach act-pm-example",
        )

    def test_client_retries_read_only_env_tool_once_without_ensure(self) -> None:
        client = _require_module("buddyswitch.runtime_kernel.client")
        stale_error = client.RuntimeBrokerError(
            "E_RUNTIME_BROKER_STALE_SOCKET",
            "stale socket",
            details={"retriable": True},
        )
        ensure_name = "_ensure_runtime_broker"
        ensure_side_effect = AssertionError("client must not self-ensure broker lifecycle")
        ensure_patch = (
            patch.object(client, ensure_name, side_effect=ensure_side_effect)
            if hasattr(client, ensure_name)
            else contextlib.nullcontext()
        )

        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ), patch.object(
            client,
            "_request_once",
            side_effect=[stale_error, {"ok": True, "items": []}],
        ) as request_once, ensure_patch:
            result = client.request_runtime_broker(
                "env.tool",
                {"tool": "context", "action": "summarize", "args": {}},
            )
        self.assertEqual(result, {"ok": True, "items": []})
        self.assertEqual(request_once.call_count, 2)

    def test_client_does_not_retry_prepare_after_transport_reset(self) -> None:
        protocol = _require_module("buddyswitch.runtime_kernel.protocol")
        client = _require_module("buddyswitch.runtime_kernel.client")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        socket_path = Path(temp.name) / "runtime-broker.sock"
        captured: list[dict[str, object]] = []

        def run() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(1)
                conn, _ = server.accept()
                with conn:
                    captured.append(protocol.read_message(conn))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            with self.assertRaises(client.RuntimeBrokerError):
                client.request_runtime_broker("prepare", {"text": "x"})
        thread.join(timeout=2.0)
        self.assertEqual(len(captured), 1)

    def test_client_does_not_retry_mutating_env_tool_after_transport_reset(self) -> None:
        client = _require_module("buddyswitch.runtime_kernel.client")
        reset_error = client.RuntimeBrokerError(
            "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
            "transport reset",
            details={"retriable": True},
        )
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_ACTOR_ID": "act-pm-example",
                "BUDDYSWITCH_ROLE_ID": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ), patch.object(client, "_request_once", side_effect=reset_error) as request_once:
            with self.assertRaises(client.RuntimeBrokerError):
                client.request_runtime_broker(
                    "env.tool",
                    {"tool": "task_sys", "action": "close", "args": {"task_id": "task-missing"}},
                )
        self.assertEqual(request_once.call_count, 1)


class RuntimeBrokerPersistIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = RuntimeTestWorkspace()
        self.addCleanup(self.workspace.close)
        self.runtime_root = self.workspace.root

    def _instance_json(self) -> Path:
        instance_json = self.workspace.path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": "act-pm-example",
                    "role": "pm",
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        return instance_json

    def test_persist_without_idempotency_key_is_rejected_before_commit(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-persist",
            "method": "persist",
            "params": {"context": {}, "result": {}},
            "deadline_ms": 35000,
        }
        session = dispatcher.RuntimeBrokerSession(instance_json_path=self._instance_json(), manifest_path=MANIFEST)
        response = dispatcher.dispatch_runtime_request(request, session)
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PROTOCOL")
        self.assertIs(response["error"]["retriable"], False)


class RuntimeBrokerV2AcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = RuntimeTestWorkspace()
        self.addCleanup(self.workspace.close)
        self.runtime_root = self.workspace.root

    def test_error_envelope_preserves_extended_error_fields_from_dispatch_payload(self) -> None:
        instance_json = self.workspace.path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": "act-pm-example",
                    "role": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-error-extensions",
            "method": "env.tool",
            "params": {"actor_id": "act-pm-example", "active_role": "pm"},
            "deadline_ms": 35000,
        }
        dispatched_payload = {
            "ok": False,
            "error": {
                "code": "E_ACTOR_PRIVATE_LOGICAL_NAME",
                "message": "logical_name must be relative",
                "retriable": True,
                "class": "invalid_input",
                "boundary": "active_actor_private_file_capability",
            },
            "state_changed": False,
            "correctable_fields": ["logical_name"],
        }
        with patch("buddyswitch.runtime_kernel.broker.coordinator.dispatch_with_coordination", return_value=dispatched_payload):
            envelope = runtime_broker.dispatch_runtime_request(
                request=request,
                instance_json_path=instance_json,
                manifest_path=MANIFEST,
            )

        self.assertFalse(envelope.get("ok"), msg=envelope)
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_ACTOR_PRIVATE_LOGICAL_NAME")
        self.assertEqual(error.get("class"), "invalid_input")
        self.assertEqual(error.get("boundary"), "active_actor_private_file_capability")
        self.assertEqual(envelope.get("correctable_fields"), ["logical_name"])

    def test_active_identity_mismatch_errors_are_structured_non_retriable(self) -> None:
        dispatcher = _require_module("buddyswitch.runtime_kernel.dispatcher")
        instance_json = self.workspace.path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": "act-pm-example",
                    "role": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        session = dispatcher.RuntimeBrokerSession(instance_json_path=instance_json, manifest_path=MANIFEST)
        for request in (
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-wrong-instance",
                "method": "prepare",
                "params": {"text": PM_REQUEST, "actor_id": "act-other", "active_role": "pm"},
                "deadline_ms": 35000,
            },
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-wrong-role",
                "method": "prepare",
                "params": {"text": PM_REQUEST, "actor_id": "act-pm-example", "active_role": "market"},
                "deadline_ms": 35000,
            },
        ):
            with self.subTest(request=request["request_id"]):
                response = dispatcher.dispatch_runtime_request(request, session)
                self.assertFalse(response["ok"], msg=response)
                self.assertIs(response["error"]["retriable"], False)
                self.assertNotEqual(response["error"]["code"], "E_RUNTIME_BROKER_UNAVAILABLE")
                boundary = response.get("permission_boundary") or response["error"].get("permission_boundary")
                self.assertIn(boundary, {"active-instance", "active-role"})

    def test_runtime_broker_v2_stays_local_unix_socket_gateway(self) -> None:
        server_module = _require_module("buddyswitch.runtime_kernel.server")
        source_root = ROOT / "src" / "buddyswitch" / "runtime_kernel"
        text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(source_root.glob("*.py")))
        self.assertNotIn("grpc", text)
        self.assertNotIn("http.server", text)
        self.assertNotIn("sqlite3", text)
        self.assertIn("AF_UNIX", Path(server_module.__file__).read_text(encoding="utf-8"))
