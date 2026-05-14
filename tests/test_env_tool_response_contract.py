#!/usr/bin/env python3
"""Unified response contract tests for every broker-routed env.tool."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tests.test_market_browser_evidence import MARKET_REQUEST  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


def _pm_result() -> dict[str, object]:
    return {
        "execution_summary": "PM validated env tool response contracts.",
    }


class EnvToolResponseContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str,
        buddy: str,
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
        tool: str,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-env-contract-{uuid.uuid4().hex}",
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
            payload = envelope.get("result")
            self.assertIsInstance(payload, dict, msg=envelope)
            assert isinstance(payload, dict)
            return payload
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

    def _prepare(self, *, text: str, instance_json: Path, instance_id: str, buddy: str) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-prepare-contract-{uuid.uuid4().hex}",
                "method": "prepare",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "text": text,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        self.assertTrue(envelope.get("ok"), msg=envelope)
        response = envelope.get("result")
        self.assertIsInstance(response, dict, msg=envelope)
        assert isinstance(response, dict)
        self.assertTrue(response.get("ok"), msg=response)
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else response
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

    def _assert_success_contract(self, response: dict[str, object], *, tool: str, action: str, buddy: str) -> None:
        self.assertTrue(response.get("ok"), msg=response)
        for key in ("ok", "tool", "action", "active_buddy", "allowed_next_actions"):
            self.assertIn(key, response)
        self.assertEqual(response.get("tool"), tool)
        self.assertEqual(response.get("action"), f"{tool}.{action}")
        self.assertEqual(response.get("active_buddy"), buddy)
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def _assert_rejection_contract(self, response: dict[str, object], *, tool: str, action: str, buddy: str) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        for key in ("ok", "tool", "action", "active_buddy", "permission_boundary", "allowed_next_actions"):
            self.assertIn(key, response)
        self.assertEqual(response.get("tool"), tool)
        self.assertEqual(response.get("action"), f"{tool}.{action}")
        self.assertEqual(response.get("active_buddy"), buddy)
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertIsInstance(error.get("code"), str, msg=response)
        self.assertIsInstance(error.get("message"), str, msg=response)
        self.assertIsInstance(response.get("permission_boundary"), str, msg=response)
        self.assertNotIn("permission_boundary", error)
        self.assertNotIn("allowed_next_actions", error)
        self.assertNotIn("command_hint", error)
        self.assertNotIn("stop_condition", error)
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def _assert_structured_options(self, response: dict[str, object]) -> None:
        self.assertIn("allowed_next_action_options", response)
        options = response["allowed_next_action_options"]
        self.assertIsInstance(options, list, msg=response)
        assert isinstance(options, list)
        self.assertGreaterEqual(len(options), 1, msg=response)
        for row in options:
            self.assertIsInstance(row, dict, msg=response)
            assert isinstance(row, dict)
            for key in ("id", "tool", "action", "mutates", "preconditions", "reason", "source_refs"):
                self.assertIn(key, row)

    def test_each_env_tool_has_success_response_with_canonical_machine_readable_fields(self) -> None:
        dev_instance_id = "inst-dev-response-contract"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")
        pm_instance_id = "inst-pm-response-contract"
        pm_instance = self._instance_json(instance_id=pm_instance_id, buddy="pm")
        market_instance_id = "inst-market-response-contract"
        market_instance = self._instance_json(instance_id=market_instance_id, buddy="market")
        pm_context = self._prepare(
            text="Write a compact response contract PRD.",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        market_context = self._prepare(
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )
        env_store.create_track(
            "track-dev-response-contract",
            "Dev Response Contract",
            status="active",
            current_buddy="dev",
            next_buddy="test",
            summary="response contract seed",
        )
        env_store.create_task(
            "task-dev-response-contract",
            "Dev Response Contract Task",
            buddy="dev",
            track_id="track-dev-response-contract",
            status="active",
            summary="seed",
            initial_run_id=None,
        )
        env_store.create_artifact(
            artifact_id="art-dev-response-contract-r1",
            title="Dev Response Artifact",
            buddy="dev",
            kind="implementation-report",
            task_id="task-dev-response-contract",
            source_run_id="run-dev-response-contract-r1",
            summary="seed",
            content={"body": "seed"},
        )

        cases = [
            ("task", "list", {}, dev_instance, dev_instance_id, "dev"),
            ("track", "list", {}, dev_instance, dev_instance_id, "dev"),
            ("artifact", "list", {"track_id": "track-dev-response-contract"}, dev_instance, dev_instance_id, "dev"),
            ("binding", "get", {}, dev_instance, dev_instance_id, "dev"),
            ("context", "list_sources", {}, dev_instance, dev_instance_id, "dev"),
            (
                "handoff",
                "validate",
                {
                    "track_id": "track-dev-response-contract",
                    "source_task_id": "task-dev-response-contract",
                    "source_run_id": "run-dev-response-contract-r1",
                    "target_buddy": "test",
                    "artifact_ids": ["art-dev-response-contract-r1"],
                    "reason": "Continue implementation.",
                    "context": "Use existing context.",
                },
                dev_instance,
                dev_instance_id,
                "dev",
            ),
            ("run", "validate_result", {"context": pm_context, "result": _pm_result()}, pm_instance, pm_instance_id, "pm"),
            (
                "evidence",
                "approve_downgrade",
                {"context": market_context, "reason": "User explicitly approved non-browser fallback."},
                market_instance,
                market_instance_id,
                "market",
            ),
            ("search", "status", {}, dev_instance, dev_instance_id, "dev"),
        ]

        for tool, action, args, instance_json, instance_id, buddy in cases:
            with self.subTest(tool=tool, action=action):
                response = self._dispatch(
                    tool=tool,
                    action=action,
                    args=args,
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self._assert_success_contract(response, tool=tool, action=action, buddy=buddy)

    def test_each_env_tool_has_rejection_response_with_canonical_machine_readable_fields(self) -> None:
        dev_instance_id = "inst-dev-rejection-contract"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")
        market_instance_id = "inst-market-rejection-contract"
        market_instance = self._instance_json(instance_id=market_instance_id, buddy="market")
        market_context = self._prepare(
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )

        cases = [
            ("task", "get", {}, dev_instance, dev_instance_id, "dev"),
            ("track", "get", {}, dev_instance, dev_instance_id, "dev"),
            ("artifact", "get", {}, dev_instance, dev_instance_id, "dev"),
            ("binding", "set_task", {}, dev_instance, dev_instance_id, "dev"),
            ("context", "get", {"context": "not an object"}, dev_instance, dev_instance_id, "dev"),
            ("handoff", "validate", {}, dev_instance, dev_instance_id, "dev"),
            ("run", "get_receipt", {}, dev_instance, dev_instance_id, "dev"),
            ("evidence", "approve_downgrade", {"context": market_context}, market_instance, market_instance_id, "market"),
            ("search", "request", {"query": "x"}, dev_instance, dev_instance_id, "dev"),
        ]

        for tool, action, args, instance_json, instance_id, buddy in cases:
            with self.subTest(tool=tool, action=action):
                response = self._dispatch(
                    tool=tool,
                    action=action,
                    args=args,
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self._assert_rejection_contract(response, tool=tool, action=action, buddy=buddy)

    def test_decision_critical_rejections_include_structured_next_action_options(self) -> None:
        dev_instance_id = "inst-dev-option-contract"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")
        market_instance_id = "inst-market-option-contract"
        market_instance = self._instance_json(instance_id=market_instance_id, buddy="market")
        market_context = self._prepare(
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )

        cases = [
            ("context", "get", {"context": "not an object"}, dev_instance, dev_instance_id, "dev", False),
            ("track", "get_current", {}, dev_instance, dev_instance_id, "dev", True),
            ("handoff", "validate", {}, dev_instance, dev_instance_id, "dev", False),
            (
                "evidence",
                "approve_downgrade",
                {"context": market_context},
                market_instance,
                market_instance_id,
                "market",
                False,
            ),
        ]
        for tool, action, args, instance_json, instance_id, buddy, expect_ok in cases:
            with self.subTest(tool=tool, action=action):
                response = self._dispatch(
                    tool=tool,
                    action=action,
                    args=args,
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self.assertEqual(bool(response.get("ok")), expect_ok, msg=response)
                self._assert_structured_options(response)

    def test_response_helpers_do_not_emit_legacy_mirrored_fields(self) -> None:
        dev_instance_id = "inst-dev-mirror-contract"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")
        response = self._dispatch(
            tool="context",
            action="get",
            args={"context": "not an object"},
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            buddy="dev",
        )
        self.assertFalse(response.get("ok"), msg=response)
        payload_text = json.dumps(response, ensure_ascii=True, sort_keys=True)
        self.assertNotIn("recommended_" + "route", payload_text)
        self.assertNotIn("selected_" + "track", payload_text)
        self.assertNotIn("next_" + "workflow_step", payload_text)
        self.assertNotIn("must_call_" + "next", payload_text)

    def test_collaboration_critical_rejections_include_no_leak_recovery_fields(self) -> None:
        env_store.create_track(
            "track-no-leak",
            "No Leak Track",
            status="active",
            current_buddy="pm",
            next_buddy="design",
            summary="Cross-buddy no-leak rejection contract.",
        )
        env_store.create_task(
            "task-pm-no-leak",
            "PM Secret Task",
            buddy="pm",
            track_id="track-no-leak",
            status="active",
            summary="Contains protected upstream artifact content.",
            initial_run_id=None,
        )
        env_store.create_artifact(
            artifact_id="art-pm-no-leak-prd-r1",
            title="PM No Leak PRD",
            buddy="pm",
            kind="prd",
            task_id="task-pm-no-leak",
            source_run_id="run-pm-no-leak-r1",
            summary="secret-prd-summary",
            content={"secret": "full body must not appear"},
        )
        instance_id = "inst-dev-no-leak-contract"
        instance_json = self._instance_json(instance_id=instance_id, buddy="dev")
        response = self._dispatch(
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-no-leak-prd-r1"},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="dev",
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "artifact")
        self.assertEqual(response.get("action"), "artifact.get")
        self.assertEqual(response.get("active_buddy"), "dev")
        self.assertEqual(response.get("artifact_id"), "art-pm-no-leak-prd-r1")
        for key in (
            "why",
            "permission_boundary",
            "relation",
            "missing_preconditions",
            "next_actions",
            "command_hint",
            "no_content_leak",
        ):
            self.assertIn(key, response)
        self.assertTrue(response.get("no_content_leak"))
        payload_text = json.dumps(response, ensure_ascii=True, sort_keys=True)
        self.assertNotIn("full body must not appear", payload_text)
        self.assertNotIn('"content":', payload_text)
        self.assertNotIn("preview", payload_text)
        self.assertNotIn("buddyswitch/objects", payload_text)

    def test_next_actions_reference_registered_tools_and_command_hints_use_env_client(self) -> None:
        from env.tools import contracts as tool_contracts

        env_store.create_track(
            "track-next-actions",
            "Next Actions Track",
            status="active",
            current_buddy="pm",
            next_buddy="design",
            summary="next action validation",
        )
        env_store.create_task(
            "task-pm-next-actions",
            "PM Next Actions Task",
            buddy="pm",
            track_id="track-next-actions",
            status="active",
            summary="seed for blocked artifact read",
            initial_run_id=None,
        )
        env_store.create_artifact(
            artifact_id="art-pm-next-actions-prd-r1",
            title="PM Next Actions PRD",
            buddy="pm",
            kind="prd",
            task_id="task-pm-next-actions",
            source_run_id="run-pm-next-actions-r1",
            summary="blocked for dev before join",
            content={"secret": "hidden"},
        )
        env_store.create_task(
            "task-dev-next-actions-a",
            "Dev Join Candidate A",
            buddy="dev",
            track_id="track-next-actions",
            status="active",
            summary="ambiguous join candidate a",
            initial_run_id=None,
        )
        env_store.create_task(
            "task-dev-next-actions-b",
            "Dev Join Candidate B",
            buddy="dev",
            track_id="track-next-actions",
            status="active",
            summary="ambiguous join candidate b",
            initial_run_id=None,
        )
        instance_id = "inst-dev-next-actions-contract"
        instance_json = self._instance_json(instance_id=instance_id, buddy="dev")

        responses = [
            self._dispatch(
                tool="artifact",
                action="get",
                args={"artifact_id": "art-pm-next-actions-prd-r1"},
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="dev",
            ),
            self._dispatch(
                tool="track",
                action="join",
                args={"track_id": "track-next-actions"},
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="dev",
            ),
            self._dispatch(
                tool="handoff",
                action="validate",
                args={},
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="dev",
            ),
            self._dispatch(
                tool="run",
                action="validate_result",
                args={},
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="dev",
            ),
        ]

        for response in responses:
            with self.subTest(action=response.get("action")):
                next_actions = response.get("next_actions")
                self.assertIsInstance(next_actions, list, msg=response)
                assert isinstance(next_actions, list)
                self.assertTrue(next_actions, msg=response)
                for row in next_actions:
                    self.assertIsInstance(row, dict, msg=response)
                    assert isinstance(row, dict)
                    tool = row.get("tool")
                    action = row.get("action")
                    self.assertIsInstance(tool, str, msg=response)
                    self.assertIsInstance(action, str, msg=response)
                    assert isinstance(tool, str)
                    assert isinstance(action, str)
                    self.assertIsNotNone(tool_contracts.get_action_spec(tool, action), msg=response)
                hint = response.get("command_hint")
                self.assertIsInstance(hint, str, msg=response)
                assert isinstance(hint, str)
                self.assertTrue(hint.startswith("python3 scripts/env/client.py "), msg=response)
                self.assertNotIn("buddyswitch/objects", hint)
                self.assertNotIn("buddyswitch/content/runs", hint)
                self.assertNotIn("runs/raw", hint)


if __name__ == "__main__":
    unittest.main()
