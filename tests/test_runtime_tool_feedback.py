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
        self.assertFalse(payload.get("state_changed"), msg=payload)

    def test_buddybox_traversal_rejection_has_structured_feedback(self) -> None:
        payload = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "../escape.txt", "content": "x"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "logical-name")
        self.assertFalse(payload["state_changed"])

    def test_artifact_owner_scope_rejection_has_structured_feedback(self) -> None:
        env_store.create_artifact(
            artifact_id="art-pm-owner-scope-r1",
            title="Owner scope",
            kind="spec",
            summary="pm private",
            content={"body": "private"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        payload = self._dispatch(
            buddy="design",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-owner-scope-r1", "summary": "rewrite"},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual(payload["permission_boundary"], "artifact.buddy_scope")

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

    def test_rejections_expose_impact_retry_and_recovery_fields_across_boundaries(self) -> None:
        payload_cases = [
            self._dispatch(
                buddy="pm",
                tool="task",
                action="create",
                args={"summary": "missing title"},
            ),
            self._dispatch(
                buddy="design",
                tool="track",
                action="create",
                args={"track_id": "x", "title": "x"},
            ),
            self._dispatch(
                buddy="pm",
                tool="context",
                action="get",
                args={"unknown_filter": 1},
            ),
            self._dispatch(
                buddy="pm",
                tool="evidence",
                action="issue_browser",
                args={"target_type": "run", "target_id": "old"},
            ),
        ]
        for payload in payload_cases:
            with self.subTest(action=payload.get("action")):
                self._assert_rejection_contract(payload)
                self.assertTrue(
                    isinstance(payload.get("correctable_fields"), list)
                    or isinstance(payload.get("alternative_capabilities"), list),
                    msg=payload,
                )

    def test_track_archived_scope_rejections_expose_recovery_contract(self) -> None:
        env_store.create_track(
            "track-feedback-foreign",
            "Foreign scope track",
            owner_buddy="pm",
            outcome="feedback scope",
            appetite="1 day",
            now={"next": "archive", "blocker": None},
        )
        env_store.update_track("track-feedback-foreign", {"archived_at": env_store.now_iso()})
        for action in ("open", "update_now", "add_update", "add_material", "add_proof"):
            args: dict[str, object] = {"track_id": "track-feedback-foreign"}
            if action == "update_now":
                args["state"] = "blocked"
            elif action == "add_update":
                args.update({"summary": "blocked", "kind": "blocker"})
            elif action in {"add_material", "add_proof"}:
                args.update(
                    {
                        "title": "Artifact",
                        "kind": "track-note",
                        "label": "Artifact",
                        "summary": "seed",
                        "content": {"body": "seed"},
                    }
                )
            payload = self._dispatch(
                buddy="dev",
                tool="track",
                action=action,
                args=args,
            )
            with self.subTest(action=action):
                self._assert_rejection_contract(payload)
                self.assertEqual(payload.get("permission_boundary"), "track.lifecycle_status", msg=payload)
                self.assertIn("track_id", payload.get("correctable_fields", []), msg=payload)
                next_actions = payload.get("allowed_next_actions")
                self.assertIsInstance(next_actions, list, msg=payload)
                assert isinstance(next_actions, list)
                action_text = "\n".join(str(item).lower() for item in next_actions)
                self.assertIn("track.list", action_text)


if __name__ == "__main__":
    unittest.main()
