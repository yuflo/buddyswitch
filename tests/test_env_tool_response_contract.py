#!/usr/bin/env python3
"""Runless response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
import threading
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402
from env.tools import responses as tool_responses  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolResponseContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, buddy: str, instance_id: str, browser_port: object = None) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": browser_port,
                    "updated_at": "2026-05-15T00:00:00Z",
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

    def _start_cdp_server(self) -> tuple[HTTPServer, int]:
        class Handler(BaseHTTPRequestHandler):
            def do_PUT(self) -> None:  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"id":"target-search"}')

            def log_message(self, _format: str, *_args: object) -> None:
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 5)
        return server, int(server.server_port)

    def _assert_rejection_contract(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("permission_boundary"), str, msg=payload)
        self.assertIsInstance(payload.get("why_blocked"), str, msg=payload)
        self.assertIsInstance(payload.get("impact"), str, msg=payload)
        self.assertIsInstance(payload.get("retryable"), bool, msg=payload)
        self.assertIsInstance(payload.get("retry_guidance"), str, msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)

    def _assert_success_contract(self, payload: dict[str, object]) -> None:
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("effect_summary"), str, msg=payload)
        self.assertIsInstance(payload.get("state_changed"), bool, msg=payload)
        self.assertIsInstance(payload.get("durability"), str, msg=payload)

    def _seed_track_task_artifact(self, instance_json: Path, instance_id: str, buddy: str = "pm") -> tuple[str, str, str]:
        track_id = f"track-{buddy}-response-seed"
        task_id = f"task-{buddy}-response-seed"
        artifact_id = f"art-{buddy}-response-seed-r1"
        track = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
            tool="track",
            action="create",
            args={"track_id": track_id, "title": "seed", "summary": "seed"},
        )
        self.assertTrue(track.get("ok"), msg=track)
        task = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
            tool="task",
            action="create",
            args={"task_id": task_id, "title": "seed", "summary": "seed", "track_id": track_id},
        )
        self.assertTrue(task.get("ok"), msg=task)
        artifact = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": artifact_id,
                "task_id": task_id,
                "kind": "prd",
                "title": "seed",
                "summary": "seed",
                "content": {"body": "seed artifact body"},
            },
        )
        self.assertTrue(artifact.get("ok"), msg=artifact)
        return track_id, task_id, artifact_id

    def test_next_action_options_are_conditional_affordances_not_workflow_steps(self) -> None:
        good = tool_responses.next_action_option(
            tool="artifact",
            action="create_revision",
            reason="Use when the host decides to write a validated artifact.",
        )
        for key in ("tool", "action", "mutates", "preconditions", "reason", "source_refs"):
            self.assertIn(key, good, msg=good)

        for bad_reason in (
            "must create artifact next",
            "always create artifact after validation",
            "only next action is artifact.create_revision",
            "after writing a PRD, hand off to Design",
            "market research should always start with browser",
            "if the user says prototype, call buddybox.write",
        ):
            with self.subTest(reason=bad_reason):
                with self.assertRaises(ValueError):
                    tool_responses.next_action_option(
                        tool="artifact",
                        action="create_revision",
                        reason=bad_reason,
                    )

    def test_context_get_and_summarize_explain_catalog_scope(self) -> None:
        instance_id = "inst-pm-context-scope"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        full = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="get",
            args={},
        )
        summary = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="summarize",
            args={},
        )
        self._assert_success_contract(full)
        self._assert_success_contract(summary)
        self.assertIn("tool_catalog", full)
        self.assertIn("operation_semantics", full)
        self.assertNotIn("tool_catalog", summary)
        self.assertNotIn("operation_semantics", summary)
        self.assertIn("full", str(full.get("effect_summary", "")).lower())
        self.assertIn("catalog", str(full.get("effect_summary", "")).lower())
        self.assertIn("compact", str(summary.get("effect_summary", "")).lower())
        self.assertTrue(
            "not full catalog" in str(summary.get("read_scope", "")).lower()
            or "compact" in str(summary.get("read_scope", "")).lower()
        )

    def test_read_and_validation_successes_explain_return_level_and_no_state_change(self) -> None:
        instance_id = "inst-pm-read-validation"
        _, port = self._start_cdp_server()
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id, browser_port=port)
        track_id, task_id, artifact_id = self._seed_track_task_artifact(instance_json, instance_id, "pm")
        handoff = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="handoff",
            action="create",
            args={
                "track_id": track_id,
                "source_task_id": task_id,
                "target_buddy": "dev",
                "artifact_ids": [artifact_id],
                "source_refs": [{"type": "artifact", "id": artifact_id}],
                "reason": "seed",
                "context": "seed",
            },
        )
        self.assertTrue(handoff.get("ok"), msg=handoff)
        write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "response/read.txt", "content": "seed"},
        )
        self.assertTrue(write.get("ok"), msg=write)

        checks = [
            ("task", "list", {}, ("summary",)),
            ("task", "get", {"task_id": task_id}, ("artifact id", "artifact ids")),
            ("track", "get", {"track_id": track_id}, ("artifact summaries",)),
            ("artifact", "list", {"track_id": track_id}, ("summary",)),
            ("artifact", "get", {"artifact_id": artifact_id}, ("full",)),
            ("artifact", "validate_payload", {"task_id": task_id, "kind": "prd", "title": "v", "content": {"body": "x"}}, ("validation", "validated")),
            ("handoff", "list", {"track_id": track_id}, ("record",)),
            ("handoff", "validate", {"track_id": track_id, "source_task_id": task_id, "target_buddy": "dev", "artifact_ids": [artifact_id], "source_refs": [{"type": "artifact", "id": artifact_id}], "reason": "r", "context": "c"}, ("validation", "validated")),
            ("buddybox", "list", {}, ("summary",)),
            ("buddybox", "read", {"logical_name": "response/read.txt"}, ("content",)),
            ("context", "get", {}, ("catalog",)),
            ("context", "summarize", {}, ("compact",)),
            ("search", "status", {}, ("metadata",)),
            ("search", "request", {"query": "seed query", "backend": "browser", "engine": "google"}, ("target url",)),
        ]
        for tool, action, args, tokens in checks:
            payload = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool=tool,
                action=action,
                args=args,
            )
            with self.subTest(action=f"{tool}.{action}"):
                self._assert_success_contract(payload)
                self.assertFalse(payload.get("state_changed"), msg=payload)
                self.assertEqual(payload.get("durability"), "none", msg=payload)
                effect_summary = str(payload.get("effect_summary", "")).lower()
                self.assertTrue(any(token in effect_summary for token in tokens), msg=payload)
                self.assertIsInstance(payload.get("read_scope"), str, msg=payload)
        artifact_list = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": track_id},
        )
        self.assertTrue(artifact_list.get("ok"), msg=artifact_list)
        rows = artifact_list.get("artifacts")
        self.assertIsInstance(rows, list, msg=artifact_list)
        assert isinstance(rows, list)
        self.assertTrue(rows)
        self.assertNotIn("content", rows[0], msg=rows[0])
        artifact_get = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertTrue(artifact_get.get("ok"), msg=artifact_get)
        self.assertIn("content", artifact_get.get("artifact", {}), msg=artifact_get)

    def test_mutating_successes_explain_changed_state_plane_and_durability(self) -> None:
        instance_id = "inst-pm-mutating"
        server, port = self._start_cdp_server()
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id, browser_port=port)
        track_id, task_id, artifact_id = self._seed_track_task_artifact(instance_json, instance_id, "pm")

        rows = [
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="task",
                action="update",
                args={"task_id": task_id, "summary": "updated"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="track",
                action="join",
                args={"track_id": track_id, "task_id": task_id},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="artifact",
                action="update_metadata",
                args={"artifact_id": artifact_id, "summary": "meta"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="handoff",
                action="create",
                args={
                    "track_id": track_id,
                    "source_task_id": task_id,
                    "target_buddy": "dev",
                    "artifact_ids": [artifact_id],
                    "source_refs": [{"type": "artifact", "id": artifact_id}],
                    "reason": "handoff",
                    "context": "handoff",
                },
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="buddybox",
                action="write",
                args={"logical_name": "response/mutating.txt", "content": "1"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="evidence",
                action="issue_browser",
                args={"target_type": "artifact", "target_id": artifact_id},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="search",
                action="open_browser",
                args={"query": "mutating search", "engine": "google"},
            ),
        ]
        server.shutdown()

        for payload in rows:
            with self.subTest(action=payload.get("action")):
                self._assert_success_contract(payload)
                self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
                action = str(payload.get("action"))
                durability = str(payload.get("durability"))
                if action == "track.join" and payload.get("state_changed") is False:
                    self.assertEqual(durability, "none", msg=payload)
                    self.assertEqual(payload.get("state_changes", [{}])[0].get("change"), "relation_reused", msg=payload)
                elif action.startswith("buddybox."):
                    self.assertTrue(payload.get("state_changed"), msg=payload)
                    self.assertEqual(durability, "active_instance_local", msg=payload)
                    self.assertFalse(payload.get("mutates_product_state"), msg=payload)
                elif action.startswith("evidence."):
                    self.assertTrue(payload.get("state_changed"), msg=payload)
                    self.assertEqual(durability, "transient token", msg=payload)
                    self.assertFalse(payload.get("mutates_product_state"), msg=payload)
                elif action == "search.open_browser":
                    self.assertTrue(payload.get("state_changed"), msg=payload)
                    self.assertEqual(durability, "browser_session", msg=payload)
                    self.assertFalse(payload.get("mutates_product_state"), msg=payload)
                else:
                    self.assertTrue(payload.get("state_changed"), msg=payload)
                    self.assertEqual(durability, "durable", msg=payload)

    def test_rejections_explain_correction_or_atomic_alternative(self) -> None:
        instance_id = "inst-rejection-recovery"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        track_id, task_id, artifact_id = self._seed_track_task_artifact(instance_json, instance_id, "pm")
        cases = [
            ("task", "create", {}, {"title"}),
            ("artifact", "create_revision", {"kind": "prd", "title": "x", "content": {"body": "x"}}, {"task_id"}),
            ("handoff", "validate", {"track_id": track_id, "source_task_id": task_id, "artifact_ids": [artifact_id], "reason": "r", "context": "c"}, {"target_buddy"}),
            ("context", "get", {"unknown": 1}, {"unknown"}),
            ("search", "request", {"query": "x"}, {"backend"}),
            ("buddybox", "write", {"logical_name": "x.txt", "content": "x", "content_base64": "eA=="}, {"content", "content_base64"}),
        ]
        for tool, action, args, expected_fields in cases:
            payload = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool=tool,
                action=action,
                args=args,
            )
            with self.subTest(action=f"{tool}.{action}"):
                self._assert_rejection_contract(payload)
                self.assertFalse(payload.get("state_changed"), msg=payload)
                self.assertTrue(
                    isinstance(payload.get("correctable_fields"), list)
                    or isinstance(payload.get("alternative_capabilities"), list),
                    msg=payload,
                )
                fields = payload.get("correctable_fields", [])
                if isinstance(fields, list):
                    self.assertTrue(
                        expected_fields.intersection(set(str(row) for row in fields)),
                        msg=payload,
                    )

    def test_allowed_next_action_options_are_conditional_affordances(self) -> None:
        instance_id = "inst-conditional-options"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id, browser_port=9222)
        track_id, task_id, artifact_id = self._seed_track_task_artifact(instance_json, instance_id, "pm")
        calls = [
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="buddybox",
                action="write",
                args={"logical_name": "conditional/a.txt", "content": "x"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="artifact",
                action="validate_payload",
                args={"task_id": task_id, "kind": "prd", "title": "v", "content": {"body": "x"}},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="handoff",
                action="validate",
                args={"track_id": track_id, "source_task_id": task_id, "target_buddy": "dev", "artifact_ids": [artifact_id], "source_refs": [{"type": "artifact", "id": artifact_id}], "reason": "r", "context": "c"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool="search",
                action="request",
                args={"query": "conditional", "backend": "browser", "engine": "google"},
            ),
        ]
        for payload in calls:
            with self.subTest(action=payload.get("action")):
                self._assert_success_contract(payload)
                options = payload.get("allowed_next_action_options")
                self.assertIsInstance(options, list, msg=payload)
                assert isinstance(options, list)
                self.assertTrue(options, msg=payload)
                for row in options:
                    self.assertIsInstance(row, dict, msg=row)
                    assert isinstance(row, dict)
                    for key in ("tool", "action", "mutates", "preconditions", "reason", "source_refs"):
                        self.assertIn(key, row, msg=row)
                    reason = str(row.get("reason", "")).lower()
                    self.assertNotIn("must", reason)
                    self.assertNotIn("always", reason)
                    self.assertNotIn("only next action", reason)

    def test_success_responses_cover_read_write_and_target_scoped_evidence(self) -> None:
        instance_id = "inst-pm-response"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        context_summary = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="summarize",
            args={},
        )
        self.assertTrue(context_summary.get("ok"), msg=context_summary)
        self.assertFalse(context_summary.get("state_changed"), msg=context_summary)
        self.assertEqual(context_summary.get("durability"), "none")

        created_task = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-pm-response", "title": "Response task", "summary": "seed"},
        )
        self.assertTrue(created_task.get("ok"), msg=created_task)
        self.assertTrue(created_task.get("state_changed"), msg=created_task)
        self.assertEqual(created_task.get("durability"), "durable")

        written_file = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "prototypes/response.html", "content": "<html>ok</html>"},
        )
        self.assertTrue(written_file.get("ok"), msg=written_file)
        self.assertTrue(written_file.get("state_changed"), msg=written_file)
        self.assertEqual(written_file.get("durability"), "active_instance_local")
        options = written_file.get("allowed_next_action_options")
        self.assertIsInstance(options, list, msg=written_file)
        assert isinstance(options, list)
        option_pairs = {
            (row.get("tool"), row.get("action"))
            for row in options
            if isinstance(row, dict)
        }
        self.assertIn(("buddybox", "read"), option_pairs)
        self.assertIn(("artifact", "create_revision"), option_pairs)
        for row in options:
            if not isinstance(row, dict):
                continue
            self.assertIn("mutates", row, msg=row)
            self.assertIn("reason", row, msg=row)
            self.assertIn("source_refs", row, msg=row)

        created_artifact = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-response",
                "kind": "prd",
                "title": "Response PRD",
                "summary": "seed",
                "content": {"body": "prd"},
                "source_refs": [
                    {"type": "note", "label": "response-seed"},
                    {"type": "buddybox", "logical_name": "prototypes/response.html"},
                ],
            },
        )
        self.assertTrue(created_artifact.get("ok"), msg=created_artifact)
        self.assertTrue(created_artifact.get("state_changed"), msg=created_artifact)
        artifact_id = str(created_artifact.get("artifact_id"))

        issued_evidence = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertTrue(issued_evidence.get("ok"), msg=issued_evidence)
        self.assertTrue(issued_evidence.get("state_changed"), msg=issued_evidence)
        self.assertEqual(issued_evidence.get("durability"), "transient token")
        evidence = issued_evidence.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=issued_evidence)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertNotIn("run_id", evidence)

    def test_rejections_expose_machine_readable_recovery_contract(self) -> None:
        pm_instance = self._instance_json(buddy="pm", instance_id="inst-pm-reject")
        design_instance = self._instance_json(buddy="design", instance_id="inst-design-reject")

        missing_task = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={"kind": "prd", "title": "bad", "content": {"body": "x"}},
        )
        self._assert_rejection_contract(missing_task)
        self.assertEqual((missing_task.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

        traversal = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "../escape.txt", "content": "x"},
        )
        self._assert_rejection_contract(traversal)
        self.assertEqual((traversal.get("error") or {}).get("code"), "E_BUDDYBOX_LOGICAL_NAME")

        created_pm_task = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-pm-reject", "title": "Owned task", "summary": "seed"},
        )
        self.assertTrue(created_pm_task.get("ok"), msg=created_pm_task)
        created_pm_artifact = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-reject-r1",
                "task_id": "task-pm-reject",
                "kind": "spec",
                "title": "Owned artifact",
                "summary": "seed",
                "content": {"body": "pm"},
            },
        )
        self.assertTrue(created_pm_artifact.get("ok"), msg=created_pm_artifact)

        foreign_update = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-reject",
            buddy="design",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-reject-r1", "summary": "overwrite"},
        )
        self._assert_rejection_contract(foreign_update)
        self.assertEqual((foreign_update.get("error") or {}).get("code"), "E_ARTIFACT_BUDDY_SCOPE")

        bad_target = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "run", "target_id": "run-old"},
        )
        self._assert_rejection_contract(bad_target)
        self.assertEqual((bad_target.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")

    def test_registry_and_response_hints_exclude_run_and_binding(self) -> None:
        supported = set(tool_contracts.supported_tools())
        self.assertNotIn("run", supported)
        self.assertNotIn("binding", supported)

        all_actions = {
            f"{tool}.{action}"
            for tool in tool_contracts.supported_tools()
            for action in tool_contracts.supported_actions(tool)
        }
        self.assertNotIn("task.get_current", all_actions)
        self.assertNotIn("track.get_current", all_actions)

        instance_id = "inst-pm-hints"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        sample = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={"kind": "prd", "title": "bad", "content": {"body": "x"}},
        )
        self._assert_rejection_contract(sample)

        for hint in sample.get("allowed_next_actions", []):
            if not isinstance(hint, str):
                continue
            lowered = hint.lower()
            self.assertNotIn("run.", lowered)
            self.assertNotIn("binding.", lowered)
            self.assertNotIn("runs/raw", lowered)
            self.assertNotIn("content/runs", lowered)


if __name__ == "__main__":
    unittest.main()
