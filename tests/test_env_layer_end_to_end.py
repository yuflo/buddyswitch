#!/usr/bin/env python3
"""Phase 8 end-to-end env.tool collaboration loop coverage."""

from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tests.test_turn_integration import (  # noqa: E402
    DESIGN_COMMIT,
    DEV_COMMIT,
    MARKET_COMMIT,
    MARKET_REQUEST,
    PM_COMMIT,
    PM_REQUEST,
    TEST_COMMIT,
    _CDPState,
    _make_cdp_handler,
)

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"


def _clone(payload: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(payload))


class EnvLayerEndToEndTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.env_tool_calls: list[tuple[str, str, str]] = []

    def _instance_json(
        self,
        *,
        buddy: str,
        instance_id: str,
        browser_port: int | None = None,
    ) -> Path:
        path = self._runtime_path(f"{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
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
        return path

    def _dispatch(
        self,
        *,
        buddy: str,
        method: str,
        payload: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": method,
                "payload": payload,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _env_tool(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        response = self._dispatch(
            buddy=buddy,
            method="env.tool",
            payload={"tool": tool, "action": action, "args": args},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), tool)
        self.env_tool_calls.append((buddy, tool, action))
        return response

    def _prepare(
        self,
        *,
        buddy: str,
        text: str,
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        response = self._dispatch(
            buddy=buddy,
            method="prepare",
            payload={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response.get("ok"), msg=response)
        payload = response.get("payload")
        self.assertIsInstance(payload, dict, msg=response)
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

    def _create_tracked_task(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        task_id: str,
        track_id: str,
        title: str,
    ) -> None:
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="task",
            action="create",
            args={"task_id": task_id, "title": title, "summary": f"{buddy} phase task."},
        )
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="track",
            action="attach_task",
            args={"track_id": track_id, "task_id": task_id},
        )
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="binding",
            action="set_task",
            args={"task_id": task_id},
        )

    def _commit(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        context: dict[str, object],
        result: dict[str, object],
    ) -> dict[str, object]:
        response = self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="run",
            action="commit",
            args={"context": context, "result": result},
        )
        receipt = response.get("receipt")
        self.assertIsInstance(receipt, dict, msg=response)
        return response

    def test_full_buddy_loop_uses_env_tool_and_persists_state(self) -> None:
        track_id = "track-phase8-env-layer-loop"
        task_ids = {
            "pm": "task-pm-phase8-loop",
            "market": "task-market-phase8-loop",
            "design": "task-design-phase8-loop",
            "dev": "task-dev-phase8-loop",
            "test": "task-test-phase8-loop",
        }

        pm_instance_id = "inst-pm-phase8-loop"
        pm_instance = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        self._env_tool(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": "Phase 8 Env Layer Loop",
                "summary": "End-to-end env.tool collaboration loop.",
                "current_buddy": "pm",
                "next_buddy": "market",
            },
        )
        self._create_tracked_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=task_ids["pm"],
            track_id=track_id,
            title="PM PRD",
        )
        pm_context = self._prepare(
            buddy="pm",
            text=PM_REQUEST,
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        pm_result = _clone(PM_COMMIT)
        pm_result["state_effects"] = {"task": PM_COMMIT["state_effects"]["task"]}
        pm_persisted = self._commit(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            context=pm_context,
            result=pm_result,
        )

        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
            allow_put_new_about_blank=False,
            allow_get_new_about_blank=False,
        )
        browser_port = self._start_cdp_server(state)

        market_instance_id = "inst-market-phase8-loop"
        market_instance = self._instance_json(
            buddy="market",
            instance_id=market_instance_id,
            browser_port=browser_port,
        )
        self._create_tracked_task(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            task_id=task_ids["market"],
            track_id=track_id,
            title="Market research",
        )
        market_context = self._prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        evidence = self._env_tool(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            tool="evidence",
            action="issue_browser",
            args={"context": market_context},
        )
        token_scope = evidence["feedback"]["token_scope"]
        self.assertEqual(token_scope["run_id"], market_context["run_envelope"]["run_id"])
        self.assertEqual(token_scope["instance_id"], market_instance_id)
        self.assertEqual(token_scope["buddy_id"], "market")
        market_result = _clone(MARKET_COMMIT)
        market_result["tool_evidence"] = evidence["tool_evidence"]
        market_persisted = self._commit(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            context=market_context,
            result=market_result,
        )

        design_instance_id = "inst-design-phase8-loop"
        design_instance = self._instance_json(buddy="design", instance_id=design_instance_id)
        self._create_tracked_task(
            buddy="design",
            instance_json=design_instance,
            instance_id=design_instance_id,
            task_id=task_ids["design"],
            track_id=track_id,
            title="Design handoff",
        )
        design_context = self._prepare(
            buddy="design",
            text="Shape the landing page handoff.",
            instance_json=design_instance,
            instance_id=design_instance_id,
        )
        design_persisted = self._commit(
            buddy="design",
            instance_json=design_instance,
            instance_id=design_instance_id,
            context=design_context,
            result=_clone(DESIGN_COMMIT),
        )

        dev_instance_id = "inst-dev-phase8-loop"
        dev_instance = self._instance_json(buddy="dev", instance_id=dev_instance_id)
        self._create_tracked_task(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            task_id=task_ids["dev"],
            track_id=track_id,
            title="Dev implementation",
        )
        dev_context = self._prepare(
            buddy="dev",
            text="Implement the landing page.",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
        )
        dev_persisted = self._commit(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            context=dev_context,
            result=_clone(DEV_COMMIT),
        )

        test_instance_id = "inst-test-phase8-loop"
        test_instance = self._instance_json(buddy="test", instance_id=test_instance_id)
        self._create_tracked_task(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            task_id=task_ids["test"],
            track_id=track_id,
            title="Test report",
        )
        test_context = self._prepare(
            buddy="test",
            text="Smoke test the landing page.",
            instance_json=test_instance,
            instance_id=test_instance_id,
        )
        test_result = _clone(TEST_COMMIT)
        test_result["state_effects"] = {
            "task": {
                "status": "done",
                "summary": "Test report completed and ready for PM review.",
            },
        }
        test_persisted = self._commit(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            context=test_context,
            result=test_result,
        )

        receipts = [
            ("pm", pm_persisted["receipt"]),
            ("market", market_persisted["receipt"]),
            ("design", design_persisted["receipt"]),
            ("dev", dev_persisted["receipt"]),
            ("test", test_persisted["receipt"]),
        ]
        expected_handoffs = {
            "pm": "market",
            "market": "design",
            "design": "dev",
            "dev": "test",
            "test": "pm",
        }
        for buddy, receipt in receipts:
            self.assertEqual(receipt["task_id"], task_ids[buddy])
            self.assertEqual(receipt["track_id"], track_id)
            handoff = receipt.get("handoff")
            self.assertIsInstance(handoff, dict, msg=receipt)
            assert isinstance(handoff, dict)
            self.assertEqual(handoff.get("next_buddy"), expected_handoffs[buddy])
            run_path = self._runtime_path(f"buddyswitch/content/runs/{receipt['run_id']}.json")
            self.assertTrue(run_path.exists())
            run = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(run["buddy_id"], buddy)
            self.assertEqual(run["track_id"], track_id)
            if buddy == "market":
                self.assertEqual(run["tool_evidence"]["kind"], "browser-cockpit-preflight")

        track = env_store.get_track(track_id)
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(set(track["task_ids"]), set(task_ids.values()))

        index = env_store.build_track_artifact_index(track_id)
        self.assertIsNotNone(index)
        assert index is not None
        current = {
            artifact["kind"]: artifact
            for task in index["tasks"]
            for artifact in task["artifacts"]
            if artifact.get("is_current")
        }
        self.assertEqual(
            set(current),
            {"prd", "market-scan", "design-handoff", "implementation-report", "test-report"},
        )
        self.assertEqual(current["prd"]["source_buddy"], "pm")
        self.assertEqual(current["market-scan"]["source_buddy"], "market")
        self.assertEqual(current["design-handoff"]["source_buddy"], "design")
        self.assertEqual(current["implementation-report"]["source_buddy"], "dev")
        self.assertEqual(current["test-report"]["source_buddy"], "test")

        for buddy, task_id in task_ids.items():
            task = env_store.get_task(task_id)
            self.assertIsNotNone(task)
            assert task is not None
            self.assertEqual(task["buddy"], buddy)
            self.assertEqual(task["track_id"], track_id)
        self.assertEqual(env_store.get_task(task_ids["dev"])["status"], "done")
        self.assertEqual(env_store.get_task(task_ids["test"])["status"], "done")

        required_calls = {
            ("pm", "track", "create"),
            ("pm", "task", "create"),
            ("pm", "track", "attach_task"),
            ("pm", "binding", "set_task"),
            ("pm", "run", "commit"),
            ("market", "evidence", "issue_browser"),
            ("market", "run", "commit"),
            ("design", "run", "commit"),
            ("dev", "run", "commit"),
            ("test", "run", "commit"),
        }
        self.assertTrue(required_calls.issubset(set(self.env_tool_calls)))


if __name__ == "__main__":
    unittest.main()
