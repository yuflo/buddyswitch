#!/usr/bin/env python3
"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tools import catalog as tool_catalog  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolResponseContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _ACTION_PLACEHOLDERS = {
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "unknown",
        "placeholder",
    }

    @staticmethod
    def _meaningful_text_entries(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        rows: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in EnvToolResponseContractTests._ACTION_PLACEHOLDERS:
                continue
            rows.append(normalized)
        return rows

    @staticmethod
    def _meaningful_tool_action_options(value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        rows: list[dict[str, str]] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            action = entry.get("action")
            if isinstance(tool, str) and tool.strip() and isinstance(action, str) and action.strip():
                rows.append({"tool": tool.strip(), "action": action.strip()})
        return rows

    def _assert_actionable_next_guidance(self, payload: dict[str, object]) -> None:
        meaningful_next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        meaningful_next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        has_next_actions = len(meaningful_next_actions) > 0
        has_next_options = len(meaningful_next_options) > 0
        self.assertTrue(has_next_actions or has_next_options, msg=payload)

    def _instance_json(self, *, buddy: str, instance_id: str) -> Path:
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
                    "updated_at": "2026-05-18T00:00:00Z",
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
        instance_json: Path,
        instance_id: str,
        buddy: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-response-{uuid.uuid4().hex}",
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

    def _assert_rejection_contract(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("permission_boundary"), str, msg=payload)
        self.assertTrue(str(payload.get("permission_boundary", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("why_blocked"), str, msg=payload)
        self.assertTrue(str(payload.get("why_blocked", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("impact"), str, msg=payload)
        self.assertTrue(str(payload.get("impact", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("retryable"), bool, msg=payload)
        self.assertIsInstance(payload.get("retry_guidance"), str, msg=payload)
        self.assertTrue(str(payload.get("retry_guidance", "")).strip(), msg=payload)
        self.assertIn("allowed_next_actions", payload, msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)
        if "allowed_next_action_options" in payload:
            self.assertIsInstance(payload.get("allowed_next_action_options"), list, msg=payload)
        next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        self.assertTrue(
            bool(next_actions) or bool(next_options),
            msg=payload,
        )
        self.assertEqual(payload.get("state_changed"), False, msg=payload)
        self.assertEqual(payload.get("durability"), "none", msg=payload)

    def _assert_success_contract(self, payload: dict[str, object]) -> None:
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("effect_summary"), str, msg=payload)
        self.assertIsInstance(payload.get("state_changed"), bool, msg=payload)
        self.assertIsInstance(payload.get("durability"), str, msg=payload)

    def _assert_write_success_contract(self, payload: dict[str, object]) -> None:
        self._assert_success_contract(payload)
        self.assertTrue(payload.get("state_changed"), msg=payload)
        self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
        self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        self.assertNotEqual(payload.get("durability"), "none", msg=payload)
        self._assert_actionable_next_guidance(payload)

    def test_registry_excludes_removed_surfaces(self) -> None:
        tools = set(tool_catalog.supported_tools())
        self.assertNotIn("handoff", tools)
        self.assertNotIn("memory", tools)
        self.assertNotIn("run", tools)

    def test_context_get_and_summarize_catalog_scope(self) -> None:
        instance_id = "inst-pm-context-scope"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        full = self._dispatch(instance_json=instance_json, instance_id=instance_id, buddy="pm", tool="context", action="get", args={})
        summary = self._dispatch(instance_json=instance_json, instance_id=instance_id, buddy="pm", tool="context", action="summarize", args={})

        self._assert_success_contract(full)
        self._assert_success_contract(summary)
        expected_tool_catalog = tool_catalog.env_tools_description()
        expected_operation_semantics = tool_catalog.operation_semantics()
        self.assertIn("tool_catalog", full)
        self.assertIn("operation_semantics", full)
        self.assertEqual(full.get("tool_catalog"), expected_tool_catalog)
        self.assertEqual(full.get("tool_catalog"), turn_runtime._build_env_tools_desc())
        self.assertEqual(full.get("operation_semantics"), expected_operation_semantics)
        self.assertNotIn("tool_catalog", summary)
        self.assertNotIn("operation_semantics", summary)
        self.assertNotIn("comment.resolve", full.get("operation_semantics", {}))
        self.assertNotIn("comment.reopen", full.get("operation_semantics", {}))

    def test_unknown_tool_rejection_contract(self) -> None:
        instance_id = "inst-pm-reject"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="unknown",
            action="list",
            args={},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_track_and_artifact_success_contract(self) -> None:
        instance_id = "inst-pm-success"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        track = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-response",
                "title": "Response",
                "outcome": "Response outcome",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self._assert_write_success_contract(track)

        artifact = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-response-r1",
                "title": "Title",
                "summary": "Summary",
                "template": "brief",
                "body": "x",
            },
        )
        self._assert_write_success_contract(artifact)
        self.assertTrue((artifact.get("artifact") or {}).get("id"))
        self.assertEqual((artifact.get("artifact") or {}).get("status"), "draft")
        self.assertIsNone((artifact.get("artifact") or {}).get("published_to_track"))
        self.assertEqual((artifact.get("artifact") or {}).get("currentness"), "draft")
        self.assertIn("track.add_material", "\n".join(str(x) for x in artifact.get("allowed_next_actions", [])))
        self.assertIn("track.add_proof", "\n".join(str(x) for x in artifact.get("allowed_next_actions", [])))

        published = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-response",
                "artifact_id": "art-response-r1",
                "label": "Brief",
                "summary": "published",
            },
        )
        self._assert_write_success_contract(published)
        self.assertEqual(set(published.get("updated_ids", [])), {"track-response", "art-response-r1"})
        changes = {row.get("change") for row in published.get("state_changes", []) if isinstance(row, dict)}
        self.assertIn("published_material", changes)
        self.assertIn("material_added", changes)

    def test_publication_success_responses_describe_object_mutations(self) -> None:
        instance_id = "inst-pm-mutation-response"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        track = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-mutation-response",
                "title": "Mutation response",
                "outcome": "outcome",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track.get("ok"), msg=track)

        proof_draft = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-proof-response-r1",
                "title": "proof",
                "summary": "pass",
                "template": "proof",
                "body": "pass",
            },
        )
        self.assertTrue(proof_draft.get("ok"), msg=proof_draft)

        proof = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-mutation-response",
                "artifact_id": "art-proof-response-r1",
                "label": "Smoke",
                "summary": "pass",
            },
        )
        self._assert_write_success_contract(proof)
        self.assertEqual(set(proof.get("updated_ids", [])), {"track-mutation-response", "art-proof-response-r1"})
        changes = {row.get("change") for row in proof.get("state_changes", []) if isinstance(row, dict)}
        self.assertIn("published_proof", changes)
        self.assertIn("proof_added", changes)
        self.assertIn("update_added", changes)


if __name__ == "__main__":
    unittest.main()
