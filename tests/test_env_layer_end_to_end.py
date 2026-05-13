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
    DESIGN_ARTIFACTS,
    DESIGN_COMMIT,
    DEV_ARTIFACTS,
    DEV_COMMIT,
    DEV_TASK_UPDATE,
    MARKET_ARTIFACTS,
    MARKET_COMMIT,
    MARKET_REQUEST,
    PM_ARTIFACTS,
    PM_COMMIT,
    PM_REQUEST,
    PM_TASK_UPDATE,
    TEST_ARTIFACTS,
    TEST_COMMIT,
    TEST_TASK_UPDATE,
    _CDPState,
    _make_cdp_handler,
)

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


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
        params: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-{instance_id}-{method.replace('.', '-')}",
                "method": method,
                "params": {**params, "instance_id": instance_id, "active_buddy": buddy},
                "deadline_ms": 35000,
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
            params={"tool": tool, "action": action, "args": args},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("protocol"), PROTOCOL)
        result = response.get("result")
        self.assertIsInstance(result, dict, msg=response)
        assert isinstance(result, dict)
        self.assertEqual(result.get("tool"), tool)
        self.env_tool_calls.append((buddy, tool, action))
        return result

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
            params={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("protocol"), PROTOCOL)
        result = response.get("result")
        self.assertIsInstance(result, dict, msg=response)
        assert isinstance(result, dict)
        return result

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

    def _update_task(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        task_id: str,
        patch: dict[str, object],
    ) -> None:
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="task",
            action="update",
            args={"task_id": task_id, **patch},
        )

    def _create_artifacts(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        context: dict[str, object],
        task_id: str,
        artifact_specs: list[dict[str, object]],
    ) -> list[str]:
        run_envelope = context["run_envelope"]
        self.assertIsInstance(run_envelope, dict)
        assert isinstance(run_envelope, dict)
        source_run_id = run_envelope["run_id"]
        self.assertIsInstance(source_run_id, str)
        artifact_ids: list[str] = []
        for spec in artifact_specs:
            kind = spec["kind"]
            self.assertIsInstance(kind, str)
            created = self._env_tool(
                buddy=buddy,
                instance_json=instance_json,
                instance_id=instance_id,
                tool="artifact",
                action="create_revision",
                args={
                    "artifact_id": f"art-{task_id}-{kind}-{source_run_id.replace('run-', '')[:8]}",
                    "task_id": task_id,
                    "kind": kind,
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "content": spec["content"],
                    "source_run_id": source_run_id,
                },
            )
            artifact_ids.append(str(created["artifact_id"]))
        return artifact_ids

    def _audit_result(
        self,
        base: dict[str, object],
        *,
        task_id: str,
        track_id: str,
        artifact_ids: list[str],
        tool_evidence: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = _clone(base)
        result["task_id"] = task_id
        result["track_id"] = track_id
        result["artifact_ids"] = artifact_ids
        if tool_evidence is not None:
            result["tool_evidence"] = tool_evidence
        return result

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

    def test_product_mode_env_tool_search_status_smoke(self) -> None:
        instance_id = "inst-dev-search-status-smoke"
        instance_json = self._instance_json(
            buddy="dev",
            instance_id=instance_id,
            browser_port=9222,
        )
        response = self._env_tool(
            buddy="dev",
            instance_json=instance_json,
            instance_id=instance_id,
            tool="search",
            action="status",
            args={},
        )
        self.assertEqual(response.get("action"), "search.status")
        self.assertEqual(response.get("native_codex_web_search"), "disabled")
        backend_status = response.get("backend_status")
        self.assertIsInstance(backend_status, dict, msg=response)
        assert isinstance(backend_status, dict)
        self.assertIn("browser", backend_status)
        self.assertIn("search_api", backend_status)
        self.assertIn("permission_boundary", response)
        self.assertIn("allowed_next_actions", response)
        self.assertIn("command_hint", response)

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
        self._update_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=task_ids["pm"],
            patch=PM_TASK_UPDATE,
        )
        pm_artifact_ids = self._create_artifacts(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            context=pm_context,
            task_id=task_ids["pm"],
            artifact_specs=PM_ARTIFACTS,
        )
        pm_persisted = self._commit(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            context=pm_context,
            result=self._audit_result(
                PM_COMMIT,
                task_id=task_ids["pm"],
                track_id=track_id,
                artifact_ids=pm_artifact_ids,
            ),
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
        market_artifact_ids = self._create_artifacts(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            context=market_context,
            task_id=task_ids["market"],
            artifact_specs=MARKET_ARTIFACTS,
        )
        market_persisted = self._commit(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            context=market_context,
            result=self._audit_result(
                MARKET_COMMIT,
                task_id=task_ids["market"],
                track_id=track_id,
                artifact_ids=market_artifact_ids,
                tool_evidence=evidence["tool_evidence"],
            ),
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
        design_artifact_ids = self._create_artifacts(
            buddy="design",
            instance_json=design_instance,
            instance_id=design_instance_id,
            context=design_context,
            task_id=task_ids["design"],
            artifact_specs=DESIGN_ARTIFACTS,
        )
        design_persisted = self._commit(
            buddy="design",
            instance_json=design_instance,
            instance_id=design_instance_id,
            context=design_context,
            result=self._audit_result(
                DESIGN_COMMIT,
                task_id=task_ids["design"],
                track_id=track_id,
                artifact_ids=design_artifact_ids,
            ),
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
        self._update_task(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            task_id=task_ids["dev"],
            patch=DEV_TASK_UPDATE,
        )
        dev_artifact_ids = self._create_artifacts(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            context=dev_context,
            task_id=task_ids["dev"],
            artifact_specs=DEV_ARTIFACTS,
        )
        dev_persisted = self._commit(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            context=dev_context,
            result=self._audit_result(
                DEV_COMMIT,
                task_id=task_ids["dev"],
                track_id=track_id,
                artifact_ids=dev_artifact_ids,
            ),
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
        self._update_task(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            task_id=task_ids["test"],
            patch=TEST_TASK_UPDATE,
        )
        test_artifact_ids = self._create_artifacts(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            context=test_context,
            task_id=task_ids["test"],
            artifact_specs=TEST_ARTIFACTS,
        )
        test_persisted = self._commit(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            context=test_context,
            result=self._audit_result(
                TEST_COMMIT,
                task_id=task_ids["test"],
                track_id=track_id,
                artifact_ids=test_artifact_ids,
            ),
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
