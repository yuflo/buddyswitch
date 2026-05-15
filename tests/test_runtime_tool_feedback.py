#!/usr/bin/env python3
"""Runless structured feedback tests for env.tool rejections and recoveries."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_store  # noqa: E402
from env.tools import router as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class RuntimeToolFeedbackTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_payload = {
            "instance_id": "inst-feedback-runless",
            "buddy": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9444,
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-feedback-runless",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def _assert_rejection_contract(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload["ok"])
        self.assertIn("permission_boundary", payload)
        self.assertIn("why_blocked", payload)
        self.assertIn("impact", payload)
        self.assertIn("retryable", payload)
        self.assertIn("retry_guidance", payload)
        self.assertIn("allowed_next_actions", payload)

    def test_buddybox_traversal_rejection_has_structured_feedback(self) -> None:
        payload = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"path": "../escape.txt", "content": "x"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "buddybox.owner_scope")
        self.assertFalse(payload["state_changed"])

    def test_memory_owner_scope_rejection_has_structured_feedback(self) -> None:
        env_store.create_memory(
            memory_id="mem-pm-owner-scope",
            buddy="pm",
            kind="decision",
            title="Owner scope",
            summary="pm private",
            content={"body": "private"},
            source_refs=None,
        )
        payload = self._dispatch(
            buddy="design",
            tool="memory",
            action="update",
            args={"memory_id": "mem-pm-owner-scope", "summary": "rewrite"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "memory.buddy_scope")

    def test_evidence_target_rejection_has_structured_feedback(self) -> None:
        payload = self._dispatch(
            buddy="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "request-payload")

    def test_search_request_requires_explicit_backend(self) -> None:
        payload = self._dispatch(
            buddy="market",
            tool="search",
            action="request",
            args={"query": "onboarding competitors"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "request-payload")
        self.assertIn("backend", payload["why_blocked"].lower())


if __name__ == "__main__":
    unittest.main()
