#!/usr/bin/env python3
"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from env.tool_runtime import results as tool_results  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


def _make_cdp_handler(state: dict[str, object]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "PUT", "path": self.path})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id":"target-search"}')

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


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
        instance_id = self._runtime_instance_id(buddy=buddy, label=instance_id)
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

    def _start_cdp_server(self, state: dict[str, object]) -> tuple[HTTPServer, threading.Thread, int]:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 5)
        return server, thread, int(server.server_port)

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

    def _assert_success_matches_declared_action_semantics(self, action_key: str, payload: dict[str, object]) -> None:
        self._assert_success_contract(payload)
        semantics = tool_catalog.operation_semantics()[action_key]
        self.assertEqual(payload.get("durability"), semantics["durability"], msg=payload)
        if semantics["durability"] == "none":
            self.assertFalse(payload.get("state_changed"), msg=payload)
        else:
            self.assertTrue(payload.get("state_changed"), msg=payload)
            self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
            self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        if semantics["mutates"] == "runtime_objects":
            self.assertTrue(payload.get("created_ids") or payload.get("updated_ids") or payload.get("state_changes"), msg=payload)
        if semantics["mutates"] == "runtime_files":
            self.assertIn("private_file", json.dumps(payload.get("state_changes", [])), msg=payload)
        if semantics["mutates"] == "broker_token":
            self.assertFalse(payload.get("mutates_product_state"), msg=payload)
            self.assertIn("token", json.dumps(payload.get("state_changes", [])), msg=payload)

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
        self.assertEqual(summary.get("tool_affordances"), tool_catalog.compact_tool_affordances())
        self.assertIn("candidate_artifacts", summary)
        self.assertIn("candidate_tasks", summary)
        self.assertIn("capability_snapshot", summary)
        capability_snapshot = summary.get("capability_snapshot")
        self.assertIsInstance(capability_snapshot, dict, msg=summary)
        assert isinstance(capability_snapshot, dict)
        preview = capability_snapshot.get("runtime_policy_preview")
        self.assertIsInstance(preview, dict, msg=summary)
        assert isinstance(preview, dict)
        old_keys = (
            "role_" + "authority_" + "source",
            "allowed_" + "actions",
            "denied_" + "actions",
            "denied_" + "action_" + "details",
            "allowed_" + "action_" + "permissions",
        )
        self.assertEqual(preview.get("active_role"), "pm")
        self.assertEqual(preview.get("source"), "env.tool role-action policy")
        self.assertIs(preview.get("not_authorization_boundary"), True)
        self.assertIs(preview.get("not_execution_result"), True)
        for old_key in old_keys:
            self.assertNotIn(old_key, capability_snapshot)
        self.assertNotIn("object_" + "permissions", json.dumps(capability_snapshot, ensure_ascii=True))
        self.assertIn("open_comment_threads", summary)
        self.assertIn("recent_updates", summary)
        self.assertIsInstance(summary.get("candidate_artifacts"), list, msg=summary)
        self.assertIsInstance(summary.get("candidate_tasks"), list, msg=summary)
        self.assertIsInstance(summary.get("open_comment_threads"), list, msg=summary)
        self.assertIsInstance(summary.get("recent_updates"), list, msg=summary)
        for row in summary.get("candidate_artifacts", []):
            if isinstance(row, dict):
                self.assertNotIn("body", row, msg=row)
        dumped = json.dumps(summary, ensure_ascii=True)
        self.assertNotIn('"properties":', dumped)
        self.assertNotIn('"required":', dumped)
        self.assertNotIn('"additionalProperties":', dumped)
        self.assertIn("comment.resolve", full.get("operation_semantics", {}))
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

    def test_artifact_template_permission_rejection_uses_structured_contract(self) -> None:
        instance_id = "inst-pm-template-contract"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-template-contract-denied",
                "title": "Wrong template",
                "summary": "deny",
                "template": "design",
                "body": "pm cannot write design",
            },
        )

        self._assert_rejection_contract(rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.template_permission")
        self.assertEqual(rejected.get("correctable_fields"), ["template"])
        self.assertEqual(rejected.get("durability"), "none")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)

    def test_artifact_attach_file_inline_blob_rejection_uses_structured_contract(self) -> None:
        instance_id = "inst-design-attach-contract"
        instance_json = self._instance_json(buddy="design", instance_id=instance_id)
        created = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-design-attach-contract",
                "title": "Design handoff",
                "summary": "seed",
                "template": "design",
                "body": "# Handoff",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-design-attach-contract",
                "filename": "desktop.png",
                "source_path": str(self._runtime_path(f"instances/{instance_id}/workspace/buddybox/screenshots/desktop.png")),
                "content_base64": "aGVsbG8=",
            },
        )

        self._assert_rejection_contract(rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")

    def test_representative_responses_match_declared_effect_classes(self) -> None:
        instance_id = "inst-declared-effects"
        pm_instance = self._instance_json(buddy="pm", instance_id=instance_id)
        dev_instance = self._instance_json(buddy="dev", instance_id=f"{instance_id}-dev")

        context_read = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="context",
            action="get",
            args={},
        )
        self._assert_success_matches_declared_action_semantics("context.get", context_read)

        track = self._dispatch(
            instance_json=pm_instance,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-declared-effects",
                "title": "Declared Effects",
                "outcome": "Compare responses to definitions.",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self._assert_success_matches_declared_action_semantics("track.create", track)

        draft = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-declared-effects-r1",
                "title": "Evidence target",
                "summary": "target",
                "template": "note",
                "body": "body",
            },
        )
        self.assertTrue(draft.get("ok"), msg=draft)
        source = self.runtime_root / "buddybox" / "notes" / "effects.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("private", encoding="utf-8")
        attached = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-declared-effects-r1",
                "filename": "effects.txt",
                "source_path": str(source),
                "content_type": "text/plain",
            },
        )
        self._assert_success_matches_declared_action_semantics("artifact.attach_file", attached)
        self.assertTrue(attached.get("state_changed"), msg=attached)

        token = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": "art-declared-effects-r1"},
        )
        self._assert_success_matches_declared_action_semantics("evidence.issue_browser", token)

        dev_payload = json.loads(dev_instance.read_text(encoding="utf-8"))
        dev_payload["browser_port"] = 9222
        dev_instance.write_text(json.dumps(dev_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        search_plan = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="search",
            action="request",
            args={"query": "BuddySwitch", "backend": "browser", "engine": "google"},
        )
        self._assert_success_matches_declared_action_semantics("search.request", search_plan)

        cdp_state: dict[str, object] = {"requests": []}
        _server, _thread, browser_port = self._start_cdp_server(cdp_state)
        dev_payload["browser_port"] = browser_port
        dev_instance.write_text(json.dumps(dev_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        browser_open = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="search",
            action="open_browser",
            args={"query": "BuddySwitch", "engine": "google"},
        )
        self._assert_success_matches_declared_action_semantics("search.open_browser", browser_open)
        self.assertFalse(browser_open.get("mutates_product_state"), msg=browser_open)
        self.assertEqual(browser_open.get("page_opened"), True, msg=browser_open)

        no_browser_instance = self._instance_json(buddy="dev", instance_id=f"{instance_id}-dev-no-browser")
        browser_rejection = self._dispatch(
            instance_json=no_browser_instance,
            instance_id=f"{instance_id}-dev-no-browser",
            buddy="dev",
            tool="search",
            action="open_browser",
            args={"query": "BuddySwitch", "engine": "google"},
        )
        self._assert_rejection_contract(browser_rejection)
        self.assertIn("browser", str(browser_rejection.get("why_blocked", "")).lower())

    def test_publication_success_responses_describe_object_mutations(self) -> None:
        instance_id = "inst-pm-mutation-response"
        pm_instance = self._instance_json(buddy="pm", instance_id=instance_id)
        track = self._dispatch(
            instance_json=pm_instance,
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

        test_instance = self._instance_json(buddy="test", instance_id=instance_id)
        proof_draft = self._dispatch(
            instance_json=test_instance,
            instance_id=instance_id,
            buddy="test",
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
            instance_json=test_instance,
            instance_id=instance_id,
            buddy="test",
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

    def test_request_write_and_rejection_paths_follow_canonical_contract(self) -> None:
        instance_id = "inst-request-response"
        pm_instance = self._instance_json(buddy="pm", instance_id=instance_id)
        dev_instance = self._instance_json(buddy="dev", instance_id=f"{instance_id}-dev")

        track = self._dispatch(
            instance_json=pm_instance,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-request-response",
                "title": "Request Response",
                "outcome": "Validate request response contracts.",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track.get("ok"), msg=track)

        created = self._dispatch(
            instance_json=pm_instance,
            instance_id=instance_id,
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": "track-request-response",
                "to_buddy": "dev",
                "title": "Implement",
                "summary": "Implement request response coverage.",
                "target_refs": [{"type": "track", "id": "track-request-response"}],
            },
        )
        self._assert_write_success_contract(created)
        self.assertIsInstance(created.get("created_ids"), list, msg=created)
        assert isinstance(created.get("created_ids"), list)
        request_id = str(created["created_ids"][0])

        unauthorized = self._dispatch(
            instance_json=pm_instance,
            instance_id=instance_id,
            buddy="pm",
            tool="request",
            action="accept",
            args={"request_id": request_id},
        )
        self._assert_rejection_contract(unauthorized)

        accepted = self._dispatch(
            instance_json=dev_instance,
            instance_id=f"{instance_id}-dev",
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": request_id},
        )
        self._assert_write_success_contract(accepted)

    def test_rejection_supports_canonical_field_errors(self) -> None:
        payload = tool_results.rejection(
            tool="track",
            action="track.create",
            active_buddy="pm",
            code="E_TRACK_PAYLOAD",
            message="now must be an object",
            permission_boundary="request-payload",
            human_summary="Track request payload is invalid.",
            why_blocked="now must be an object",
            impact="No track state changed.",
            state_changed=False,
            retryable=True,
            retry_guidance="Fix now and retry.",
            field_errors=[
                {
                    "path": "now",
                    "message": "now must be an object with required next and optional blocker",
                    "expected": {"next": "non-empty string", "blocker": "string|null"},
                    "example": {"next": "Set up PM coordination.", "blocker": None},
                }
            ],
        )
        self.assertEqual(payload["field_errors"][0]["path"], "now")

        with self.assertRaises(ValueError):
            tool_results.rejection(
                tool="track",
                action="track.create",
                active_buddy="pm",
                code="E_TRACK_PAYLOAD",
                message="now must be an object",
                permission_boundary="request-payload",
                human_summary="Track request payload is invalid.",
                why_blocked="now must be an object",
                impact="No track state changed.",
                state_changed=False,
                retryable=True,
                retry_guidance="Fix now and retry.",
                extra={"field_errors": []},
            )

    def test_high_friction_payload_rejections_include_field_errors(self) -> None:
        pm_instance_id = "inst-pm-field-errors"
        dev_instance_id = "inst-dev-field-errors"
        pm_instance_json = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        dev_instance_json = self._instance_json(buddy="dev", instance_id=dev_instance_id)

        created = self._dispatch(
            instance_json=pm_instance_json,
            instance_id=pm_instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-field-errors",
                "title": "Field Errors",
                "outcome": "Improve payload recovery.",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        draft = self._dispatch(
            instance_json=dev_instance_json,
            instance_id=dev_instance_id,
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-field-errors-r1",
                "title": "Field Errors Draft",
                "summary": "seed",
                "template": "note",
                "body": "body",
            },
        )
        self.assertTrue(draft.get("ok"), msg=draft)

        cases = [
            (
                "track.create.now",
                self._dispatch(
                    instance_json=pm_instance_json,
                    instance_id=pm_instance_id,
                    buddy="pm",
                    tool="track",
                    action="create",
                    args={
                        "track_id": "track-field-errors-bad-now",
                        "title": "Bad now",
                        "outcome": "fail",
                        "appetite": "1 day",
                        "now": "next step",
                    },
                ),
                "now",
            ),
            (
                "track.update_now.now",
                self._dispatch(
                    instance_json=pm_instance_json,
                    instance_id=pm_instance_id,
                    buddy="pm",
                    tool="track",
                    action="update_now",
                    args={"track_id": "track-field-errors", "now": {"blocker": None}},
                ),
                "now",
            ),
            (
                "track.add_update.refs",
                self._dispatch(
                    instance_json=pm_instance_json,
                    instance_id=pm_instance_id,
                    buddy="pm",
                    tool="track",
                    action="add_update",
                    args={
                        "track_id": "track-field-errors",
                        "kind": "progress",
                        "summary": "bad refs",
                        "refs": {"id": "art-example-r1"},
                    },
                ),
                "refs",
            ),
            (
                "artifact.create_revision.source_refs",
                self._dispatch(
                    instance_json=dev_instance_json,
                    instance_id=dev_instance_id,
                    buddy="dev",
                    tool="artifact",
                    action="create_revision",
                    args={
                        "title": "Bad refs",
                        "template": "brief",
                        "body": "body",
                        "source_refs": "oops",
                    },
                ),
                "source_refs",
            ),
            (
                "artifact.attach_file.source_path",
                self._dispatch(
                    instance_json=dev_instance_json,
                    instance_id=dev_instance_id,
                    buddy="dev",
                    tool="artifact",
                    action="attach_file",
                    args={
                        "artifact_id": "art-field-errors-r1",
                        "filename": "field-errors.txt",
                    },
                ),
                "source_path",
            ),
            (
                "comment.add.mentions",
                self._dispatch(
                    instance_json=pm_instance_json,
                    instance_id=pm_instance_id,
                    buddy="pm",
                    tool="comment",
                    action="add",
                    args={
                        "target_type": "track",
                        "target_id": "track-field-errors",
                        "content": "check mentions",
                        "mentions": "pm",
                    },
                ),
                "mentions",
            ),
        ]

        for name, payload, expected_path in cases:
            with self.subTest(case=name):
                self._assert_rejection_contract(payload)
                self.assertIs(payload.get("state_changed"), False, msg=payload)
                self.assertEqual(payload.get("durability"), "none", msg=payload)
                field_errors = payload.get("field_errors")
                self.assertIsInstance(field_errors, list, msg=payload)
                assert isinstance(field_errors, list)
                self.assertTrue(field_errors, msg=payload)
                normalized_paths = {
                    row.get("path")
                    for row in field_errors
                    if isinstance(row, dict)
                }
                self.assertIn(expected_path, normalized_paths, msg=payload)


if __name__ == "__main__":
    unittest.main()
