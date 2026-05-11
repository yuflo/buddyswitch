#!/usr/bin/env python3
"""Unified response contract tests for every broker-routed env.tool."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tests.test_market_browser_evidence import MARKET_REQUEST  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"


def _pm_result() -> dict[str, object]:
    return {
        "execution_summary": "PM validated env tool response contracts.",
        "artifacts": [
            {
                "kind": "prd",
                "title": "Response Contract PRD",
                "summary": "Defines env tool response shape requirements.",
                "content": {"requirements": ["Every env tool returns machine-readable feedback."]},
            }
        ],
    }


class EnvToolResponseContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str,
        buddy: str,
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
                    "browser_port": None,
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
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": "env.tool",
                "payload": {"tool": tool, "action": action, "args": args},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _prepare(self, *, text: str, instance_json: Path, instance_id: str, buddy: str) -> dict[str, object]:
        response = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": "prepare",
                "payload": {"text": text},
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertTrue(response.get("ok"), msg=response)
        payload = response.get("payload")
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

    def _assert_success_contract(self, response: dict[str, object], *, tool: str, action: str, buddy: str) -> None:
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), tool)
        self.assertEqual(response.get("action"), f"{tool}.{action}")
        self.assertEqual(response.get("active_buddy"), buddy)
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def _assert_rejection_contract(self, response: dict[str, object], *, tool: str, action: str, buddy: str) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), tool)
        self.assertEqual(response.get("action"), f"{tool}.{action}")
        self.assertEqual(response.get("active_buddy"), buddy)
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertIsInstance(error.get("code"), str, msg=response)
        self.assertIsInstance(error.get("message"), str, msg=response)
        self.assertIsInstance(response.get("permission_boundary"), str, msg=response)
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def test_each_env_tool_has_success_response_with_required_machine_readable_fields(self) -> None:
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

        cases = [
            ("task", "list", {}, dev_instance, dev_instance_id, "dev"),
            ("track", "list", {}, dev_instance, dev_instance_id, "dev"),
            ("artifact", "list", {}, dev_instance, dev_instance_id, "dev"),
            ("binding", "get", {}, dev_instance, dev_instance_id, "dev"),
            ("context", "list_sources", {}, dev_instance, dev_instance_id, "dev"),
            (
                "handoff",
                "validate",
                {"next_buddy": "dev", "reason": "Continue implementation.", "context": "Use existing context."},
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

    def test_each_env_tool_has_rejection_response_with_required_machine_readable_fields(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
