#!/usr/bin/env python3
"""Unified response contract tests for every broker-routed env.tool."""

from __future__ import annotations

from contextlib import ExitStack
import importlib
import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tools import responses as tool_responses  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tests.test_market_browser_evidence import MARKET_REQUEST  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"

RESPONSE_SEMANTIC_CASES: dict[str, tuple[str, ...]] = {
    "task.create": ("ESC-MUT-001",),
    "task.list": ("ESC-READ-001",),
    "task.get": ("ESC-READ-001",),
    "task.get_current": ("ESC-READ-001", "ESC-NEG-005"),
    "task.set_current": ("ESC-MUT-001",),
    "task.update": ("ESC-MUT-001",),
    "task.archive": ("ESC-MUT-001",),
    "track.list": ("ESC-READ-002",),
    "track.get": ("ESC-READ-002", "ESC-HOST-001"),
    "track.join": ("ESC-MUT-002", "ESC-HOST-002"),
    "track.get_current": ("ESC-READ-002", "ESC-NEG-005"),
    "track.create": ("ESC-MUT-002",),
    "track.update": ("ESC-MUT-002", "ESC-HOST-005"),
    "track.advance": ("ESC-MUT-002",),
    "track.archive": ("ESC-MUT-002",),
    "track.attach_task": ("ESC-MUT-002",),
    "track.detach_task": ("ESC-MUT-002",),
    "artifact.list": ("ESC-READ-003",),
    "artifact.get": ("ESC-READ-003", "ESC-NEG-002"),
    "artifact.get_current": ("ESC-READ-003", "ESC-NEG-005"),
    "artifact.validate_payload": ("ESC-READ-003", "ESC-HOST-003"),
    "artifact.create_revision": ("ESC-MUT-003", "ESC-HOST-003"),
    "artifact.update_metadata": ("ESC-MUT-003",),
    "context.get": ("ESC-READ-004",),
    "context.summarize": ("ESC-READ-004", "ESC-NEG-005"),
    "context.list_sources": ("ESC-READ-004",),
    "binding.get": ("ESC-READ-004",),
    "binding.set_task": ("ESC-MUT-004",),
    "binding.set_track": ("ESC-MUT-004",),
    "binding.clear": ("ESC-MUT-004",),
    "handoff.list": ("ESC-READ-004", "ESC-NEG-005"),
    "handoff.validate": ("ESC-READ-004",),
    "handoff.create": ("ESC-MUT-004",),
    "run.commit": ("ESC-MUT-004", "ESC-HOST-003"),
    "run.get_receipt": ("ESC-READ-004",),
    "run.get_raw": ("ESC-READ-004",),
    "run.validate_result": ("ESC-READ-004", "ESC-HOST-003"),
    "evidence.issue_browser": ("ESC-MUT-004", "ESC-NEG-004"),
    "evidence.approve_downgrade": ("ESC-MUT-004",),
    "search.status": ("ESC-READ-004", "ESC-HOST-004"),
    "search.request": ("ESC-READ-004", "ESC-HOST-004"),
    "search.open_browser": ("ESC-MUT-004", "ESC-HOST-004"),
}

CASE_ID_TEST_REFS: dict[str, tuple[str, ...]] = {
    "ESC-READ-001": (
        "tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_read_responses_include_semantic_no_state_change_and_artifact_boundary",
    ),
    "ESC-READ-002": (
        "tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_read_responses_include_semantic_orientation_scope",
    ),
    "ESC-READ-003": (
        "tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_read_and_validation_responses_explain_scope_and_state",
    ),
    "ESC-READ-004": (
        "tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_binding_handoff_run_read_and_validate_responses_are_semantic_and_non_mutating",
    ),
    "ESC-MUT-001": (
        "tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_mutation_responses_describe_actual_state_changes",
    ),
    "ESC-MUT-002": (
        "tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_mutation_responses_describe_lifecycle_join_and_membership_impacts",
    ),
    "ESC-MUT-003": (
        "tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_write_responses_describe_revision_and_metadata_impacts",
    ),
    "ESC-MUT-004": (
        "tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_binding_handoff_run_evidence_search_mutations_describe_durable_impact",
    ),
    "ESC-HOST-001": (
        "tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_runtime_env_tool_semantics_support_direct_source_intake_decision",
    ),
    "ESC-HOST-002": (
        "tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_join_recovery_response_explains_safe_next_step_and_impact",
    ),
    "ESC-HOST-003": (
        "tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_artifact_validate_create_and_run_validate_commit_explain_state_impact",
    ),
    "ESC-HOST-004": (
        "tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_search_browser_semantics_mark_open_world_and_browser_session_effect",
    ),
    "ESC-HOST-005": (
        "tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_non_pm_lifecycle_rejection_explains_authority_without_service_code",
    ),
    "ESC-NEG-002": (
        "tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_collaboration_critical_rejections_include_no_leak_recovery_fields",
    ),
    "ESC-NEG-004": (
        "tests/test_search_env_tool.py::SearchEnvToolTests::test_browser_and_search_dependency_rejections_include_semantic_impact",
    ),
    "ESC-NEG-005": (
        "tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_empty_runtime_state_read_responses_explain_no_state_change",
    ),
}

SEMANTIC_ASSERTION_TEST_ACTIONS: dict[str, tuple[str, ...]] = {
    "tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_read_responses_include_semantic_no_state_change_and_artifact_boundary": (
        "task.get",
        "task.get_current",
    ),
    "tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_read_responses_include_semantic_orientation_scope": (
        "track.get",
        "track.get_current",
        "track.list",
    ),
    "tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_read_and_validation_responses_explain_scope_and_state": (
        "artifact.create_revision",
        "artifact.get",
        "artifact.get_current",
        "artifact.list",
        "artifact.validate_payload",
    ),
    "tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_binding_handoff_run_read_and_validate_responses_are_semantic_and_non_mutating": (
        "context.get",
        "context.list_sources",
        "context.summarize",
        "handoff.list",
        "handoff.validate",
    ),
    "tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_mutation_responses_describe_actual_state_changes": (
        "task.archive",
        "task.create",
        "task.get",
        "task.get_current",
        "task.list",
        "task.set_current",
        "task.update",
    ),
    "tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_mutation_responses_describe_lifecycle_join_and_membership_impacts": (
        "track.advance",
        "track.archive",
        "track.attach_task",
        "track.create",
        "track.detach_task",
        "track.join",
        "track.update",
    ),
    "tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_write_responses_describe_revision_and_metadata_impacts": (
        "artifact.create_revision",
        "artifact.update_metadata",
    ),
    "tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_collaboration_critical_rejections_include_no_leak_recovery_fields": (
        "artifact.get",
    ),
    "tests/test_search_env_tool.py::SearchEnvToolTests::test_browser_and_search_dependency_rejections_include_semantic_impact": (
        "search.open_browser",
        "search.request",
    ),
    "tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_empty_runtime_state_read_responses_explain_no_state_change": (
        "context.summarize",
    ),
    "tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_duplicate_and_ambiguous_mutations_explain_no_state_change_and_recovery": (
        "track.join",
    ),
    "tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_missing_payload_rejections_name_required_field_and_preserve_state": (
        "artifact.get",
        "evidence.approve_downgrade",
        "run.get_receipt",
        "search.request",
        "task.get",
        "track.get",
    ),
    "tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_read_and_validation_success_responses_include_effect_semantics": (
        "artifact.list",
        "binding.get",
        "context.list_sources",
        "evidence.approve_downgrade",
        "handoff.validate",
        "run.commit",
        "run.get_raw",
        "run.get_receipt",
        "run.validate_result",
        "search.status",
        "task.list",
        "track.list",
    ),
    "tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_read_and_validation_rejections_include_feedback_semantics": (
        "artifact.get",
        "binding.set_task",
        "context.get",
        "evidence.approve_downgrade",
        "handoff.validate",
        "run.get_raw",
        "run.get_receipt",
        "search.request",
        "task.get",
        "track.get",
    ),
    "tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_mutating_success_responses_include_actual_impact_semantics": (
        "artifact.create_revision",
        "binding.set_task",
        "run.commit",
        "task.create",
        "track.create",
    ),
    "tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_pm_can_set_track_binding_and_clear_active_instance_binding": (
        "binding.clear",
        "binding.set_track",
    ),
    "tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle": (
        "handoff.create",
    ),
    "tests/test_evidence_env_tool.py::EvidenceEnvToolTests::test_issue_browser_succeeds_through_env_tool_and_writes_scoped_token": (
        "evidence.issue_browser",
    ),
}


def _build_action_semantic_assertion_test_refs() -> dict[str, tuple[str, ...]]:
    by_action: dict[str, set[str]] = {}
    for ref, actions in SEMANTIC_ASSERTION_TEST_ACTIONS.items():
        for action in actions:
            by_action.setdefault(action, set()).add(ref)
    return {action: tuple(sorted(refs)) for action, refs in by_action.items()}


ACTION_SEMANTIC_ASSERTION_TEST_REFS = _build_action_semantic_assertion_test_refs()


def _pm_result() -> dict[str, object]:
    return {
        "execution_summary": "PM validated env tool response contracts.",
    }


class EnvToolResponseContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _resolve_test_ref(self, ref: str) -> tuple[type[unittest.TestCase], str]:
        parts = ref.split("::")
        self.assertEqual(len(parts), 3, msg=f"invalid test ref format: {ref}")
        file_path, class_name, test_name = parts
        self.assertTrue(file_path.endswith(".py"), msg=f"invalid test file path in ref: {ref}")
        module_name = file_path[:-3].replace("/", ".")
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name, None)
        self.assertIsNotNone(cls, msg=ref)
        assert cls is not None
        self.assertTrue(isinstance(cls, type) and issubclass(cls, unittest.TestCase), msg=ref)
        method = getattr(cls, test_name, None)
        self.assertTrue(callable(method), msg=ref)
        return cls, test_name

    def _run_semantic_assertion_test_and_capture_actions(self, ref: str) -> set[str]:
        from env.tools import dispatch as tool_dispatch
        from env.tools import router as tool_router

        cls, test_name = self._resolve_test_ref(ref)
        case = cls(methodName=test_name)
        observed_actions: set[str] = set()
        dispatch_registered_env_tool = tool_dispatch.dispatch_registered_env_tool

        def _capture_dispatch(
            *,
            tool: str,
            action: str,
            args: dict[str, object],
            active_buddy: str,
            instance_id: str,
            instance_json: Path,
            instance_payload: dict[str, object],
            manifest: dict[str, object],
            manifest_path: Path | None = None,
        ) -> dict[str, object]:
            observed_actions.add(f"{tool}.{action}")
            return dispatch_registered_env_tool(
                tool=tool,
                action=action,
                args=args,
                active_buddy=active_buddy,
                instance_id=instance_id,
                instance_json=instance_json,
                instance_payload=instance_payload,
                manifest=manifest,
                manifest_path=manifest_path,
            )

        result = unittest.TestResult()
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    tool_dispatch,
                    "dispatch_registered_env_tool",
                    _capture_dispatch,
                )
            )
            stack.enter_context(
                patch.object(
                    tool_router,
                    "dispatch_registered_env_tool",
                    _capture_dispatch,
                )
            )
            case.run(result)

        failures = [output for _, output in result.failures]
        errors = [output for _, output in result.errors]
        skipped = [reason for _, reason in result.skipped]
        if failures or errors or skipped:
            detail_rows: list[str] = []
            if failures:
                detail_rows.append("failures:\n" + "\n".join(failures))
            if errors:
                detail_rows.append("errors:\n" + "\n".join(errors))
            if skipped:
                detail_rows.append("skipped:\n" + "\n".join(skipped))
            self.fail(f"semantic assertion test ref did not pass: {ref}\n" + "\n".join(detail_rows))
        self.assertEqual(result.testsRun, 1, msg=ref)
        return observed_actions

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
        for key in (
            "ok",
            "tool",
            "action",
            "active_buddy",
            "effect_summary",
            "state_changed",
            "durability",
            "allowed_next_actions",
        ):
            self.assertIn(key, response)
        self.assertEqual(response.get("tool"), tool)
        self.assertEqual(response.get("action"), f"{tool}.{action}")
        self.assertEqual(response.get("active_buddy"), buddy)
        self.assertIsInstance(response.get("effect_summary"), str, msg=response)
        self.assertTrue(str(response.get("effect_summary")).strip(), msg=response)
        self.assertIsInstance(response.get("state_changed"), bool, msg=response)
        self.assertIsInstance(response.get("durability"), str, msg=response)
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def _assert_rejection_contract(self, response: dict[str, object], *, tool: str, action: str, buddy: str) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        for key in (
            "ok",
            "tool",
            "action",
            "active_buddy",
            "permission_boundary",
            "human_summary",
            "why_blocked",
            "impact",
            "state_changed",
            "retryable",
            "retry_guidance",
            "allowed_next_actions",
        ):
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
        self.assertIsInstance(response.get("human_summary"), str, msg=response)
        self.assertIsInstance(response.get("why_blocked"), str, msg=response)
        self.assertIsInstance(response.get("impact"), str, msg=response)
        self.assertIs(response.get("state_changed"), False, msg=response)
        self.assertIsInstance(response.get("retryable"), bool, msg=response)
        self.assertIsInstance(response.get("retry_guidance"), str, msg=response)
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

    def test_response_helpers_require_success_effect_semantics(self) -> None:
        with self.assertRaises(ValueError):
            tool_responses.success(
                tool="task",
                action="task.list",
                active_buddy="dev",
                effect_summary="",
                state_changed=False,
                durability="none",
                allowed_next_actions=["next"],
            )
        with self.assertRaises(ValueError):
            tool_responses.success(
                tool="task",
                action="task.list",
                active_buddy="dev",
                effect_summary="Listed readable tasks.",
                state_changed="false",
                durability="none",
                allowed_next_actions=["next"],
            )
        with self.assertRaises(ValueError):
            tool_responses.success(
                tool="task",
                action="task.list",
                active_buddy="dev",
                effect_summary="Listed readable tasks.",
                state_changed=False,
                durability="",
                allowed_next_actions=["next"],
            )
        payload = tool_responses.success(
            tool="task",
            action="task.list",
            active_buddy="dev",
            effect_summary="Listed readable tasks with no mutation.",
            state_changed=False,
            durability="none",
            read_scope="active-buddy tasks and readable relation summaries",
            allowed_next_actions=["Use task.get"],
        )
        self.assertTrue(payload["ok"])
        self.assertIn("effect_summary", payload)
        self.assertIn("state_changed", payload)
        self.assertIn("durability", payload)

    def test_response_helpers_require_rejection_impact_semantics(self) -> None:
        with self.assertRaises(ValueError):
            tool_responses.rejection(
                tool="task",
                action="task.get",
                active_buddy="dev",
                code="E_TASK_PAYLOAD",
                message="task_id is required",
                permission_boundary="request-payload",
                human_summary="",
                why_blocked="task_id is required",
                impact="No state changed.",
                state_changed=False,
                retryable=True,
                retry_guidance="Set task_id and retry.",
                allowed_next_actions=["Use task.list"],
            )
        with self.assertRaises(ValueError):
            tool_responses.rejection(
                tool="task",
                action="task.get",
                active_buddy="dev",
                code="E_TASK_PAYLOAD",
                message="task_id is required",
                permission_boundary="request-payload",
                human_summary="Task id is required.",
                why_blocked="task_id is required",
                impact="No state changed.",
                state_changed="false",
                retryable=True,
                retry_guidance="Set task_id and retry.",
                allowed_next_actions=["Use task.list"],
            )
        payload = tool_responses.rejection(
            tool="task",
            action="task.get",
            active_buddy="dev",
            code="E_TASK_PAYLOAD",
            message="task_id is required",
            permission_boundary="request-payload",
            human_summary="Task id is missing.",
            why_blocked="payload.task_id is required for task.get.",
            impact="No state changed before rejection.",
            state_changed=False,
            retryable=True,
            retry_guidance="Set task_id from task.list and retry.",
            allowed_next_actions=["Use task.list"],
        )
        self.assertFalse(payload["ok"])
        self.assertIn("human_summary", payload)
        self.assertIn("why_blocked", payload)
        self.assertIn("impact", payload)
        self.assertIn("retry_guidance", payload)

    def test_response_helpers_reject_extra_overriding_canonical_fields(self) -> None:
        with self.assertRaises(ValueError):
            tool_responses.success(
                tool="task",
                action="task.list",
                active_buddy="dev",
                effect_summary="Listed readable tasks.",
                state_changed=False,
                durability="none",
                allowed_next_actions=["Use task.get"],
                extra={"effect_summary": "override"},
            )
        with self.assertRaises(ValueError):
            tool_responses.rejection(
                tool="task",
                action="task.get",
                active_buddy="dev",
                code="E_TASK_PAYLOAD",
                message="task_id is required",
                permission_boundary="request-payload",
                human_summary="Task id missing.",
                why_blocked="task_id is required",
                impact="No state changed.",
                state_changed=False,
                retryable=True,
                retry_guidance="Set task_id and retry.",
                allowed_next_actions=["Use task.list"],
                extra={"retryable": False},
            )

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

    def test_missing_payload_rejections_name_required_field_and_preserve_state(self) -> None:
        def snapshot_json_files() -> dict[str, str]:
            rows: dict[str, str] = {}
            for path in sorted(self.runtime_root.rglob("*.json")):
                rows[str(path.relative_to(self.runtime_root))] = path.read_text(encoding="utf-8")
            return rows

        dev_instance_id = "inst-dev-missing-payload-contract"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")
        market_instance_id = "inst-market-missing-payload-contract"
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
            ("run", "get_receipt", {}, dev_instance, dev_instance_id, "dev"),
            (
                "evidence",
                "approve_downgrade",
                {"context": market_context},
                market_instance,
                market_instance_id,
                "market",
            ),
            ("search", "request", {"query": "missing backend"}, dev_instance, dev_instance_id, "dev"),
        ]

        for tool, action, args, instance_json, instance_id, buddy in cases:
            with self.subTest(tool=tool, action=action):
                before = snapshot_json_files()
                response = self._dispatch(
                    tool=tool,
                    action=action,
                    args=args,
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self._assert_rejection_contract(response, tool=tool, action=action, buddy=buddy)
                self.assertTrue(response.get("retryable"), msg=response)
                self.assertEqual(snapshot_json_files(), before)

    def test_read_and_validation_success_responses_include_effect_semantics(self) -> None:
        self.test_each_env_tool_has_success_response_with_canonical_machine_readable_fields()

        pm_instance_id = "inst-pm-read-success-contract"
        pm_instance = self._instance_json(instance_id=pm_instance_id, buddy="pm")
        pm_context = self._prepare(
            text="Validate read-only run surfaces.",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        committed = self._dispatch(
            tool="run",
            action="commit",
            args={"context": pm_context, "result": _pm_result()},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(committed, tool="run", action="commit", buddy="pm")
        receipt = committed.get("receipt")
        self.assertIsInstance(receipt, dict, msg=committed)
        assert isinstance(receipt, dict)
        run_id = receipt.get("run_id")
        self.assertIsInstance(run_id, str, msg=committed)
        assert isinstance(run_id, str)

        run_receipt = self._dispatch(
            tool="run",
            action="get_receipt",
            args={"run_id": run_id},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(run_receipt, tool="run", action="get_receipt", buddy="pm")

        run_raw = self._dispatch(
            tool="run",
            action="get_raw",
            args={"run_id": run_id},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(run_raw, tool="run", action="get_raw", buddy="pm")

    def test_read_and_validation_rejections_include_feedback_semantics(self) -> None:
        self.test_each_env_tool_has_rejection_response_with_canonical_machine_readable_fields()
        self.test_missing_payload_rejections_name_required_field_and_preserve_state()

        dev_instance_id = "inst-dev-read-reject-contract"
        dev_instance = self._instance_json(instance_id=dev_instance_id, buddy="dev")
        run_raw_rejection = self._dispatch(
            tool="run",
            action="get_raw",
            args={},
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            buddy="dev",
        )
        self._assert_rejection_contract(run_raw_rejection, tool="run", action="get_raw", buddy="dev")

    def test_mutating_success_responses_include_actual_impact_semantics(self) -> None:
        self.test_task_mutation_semantic_contract_smoke()
        self.test_track_mutation_semantic_contract_smoke()
        self.test_artifact_mutation_semantic_contract_smoke()
        self.test_binding_handoff_run_mutation_semantic_contract_smoke()

    def test_task_mutation_semantic_contract_smoke(self) -> None:
        instance_id = "inst-dev-mut-task-contract"
        instance_json = self._instance_json(instance_id=instance_id, buddy="dev")
        created = self._dispatch(
            tool="task",
            action="create",
            args={"task_id": "task-mut-contract", "title": "Mut Contract Task"},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="dev",
        )
        self._assert_success_contract(created, tool="task", action="create", buddy="dev")
        self.assertTrue(created.get("state_changed"), msg=created)
        self.assertIn(created.get("durability"), {"runtime_object", "runtime_object+instance_binding", "instance_binding"}, msg=created)

    def test_track_mutation_semantic_contract_smoke(self) -> None:
        instance_id = "inst-pm-mut-track-contract"
        instance_json = self._instance_json(instance_id=instance_id, buddy="pm")
        created = self._dispatch(
            tool="track",
            action="create",
            args={
                "track_id": "track-mut-contract",
                "title": "Mut Contract Track",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "dev",
            },
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
        )
        self._assert_success_contract(created, tool="track", action="create", buddy="pm")
        self.assertTrue(created.get("state_changed"), msg=created)

    def test_artifact_mutation_semantic_contract_smoke(self) -> None:
        pm_instance_id = "inst-pm-mut-artifact-contract"
        pm_instance = self._instance_json(instance_id=pm_instance_id, buddy="pm")
        context = self._prepare(
            text="Prepare artifact mutation contract context.",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        created_task = self._dispatch(
            tool="task",
            action="create",
            args={"task_id": "task-pm-mut-artifact", "title": "PM Artifact Task"},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(created_task, tool="task", action="create", buddy="pm")
        source_run_id = str(context["run_envelope"]["run_id"])
        artifact_create = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-mut-contract-r1",
                "task_id": "task-pm-mut-artifact",
                "kind": "prd",
                "title": "Mutation Contract Artifact",
                "summary": "mutation",
                "content": {"body": "mutation"},
                "source_run_id": source_run_id,
            },
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(artifact_create, tool="artifact", action="create_revision", buddy="pm")
        self.assertTrue(artifact_create.get("state_changed"), msg=artifact_create)

    def test_binding_handoff_run_mutation_semantic_contract_smoke(self) -> None:
        pm_instance_id = "inst-pm-mut-binding-run-contract"
        pm_instance = self._instance_json(instance_id=pm_instance_id, buddy="pm")
        context = self._prepare(
            text="Prepare binding and run mutation context.",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        created_task = self._dispatch(
            tool="task",
            action="create",
            args={"task_id": "task-pm-mut-binding", "title": "PM Binding Task"},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(created_task, tool="task", action="create", buddy="pm")
        set_binding = self._dispatch(
            tool="binding",
            action="set_task",
            args={"task_id": "task-pm-mut-binding"},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(set_binding, tool="binding", action="set_task", buddy="pm")
        self.assertTrue(set_binding.get("state_changed"), msg=set_binding)

        committed = self._dispatch(
            tool="run",
            action="commit",
            args={"context": context, "result": _pm_result()},
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            buddy="pm",
        )
        self._assert_success_contract(committed, tool="run", action="commit", buddy="pm")

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

    def test_all_registered_actions_have_at_least_one_response_semantics_case(self) -> None:
        from env.tools import contracts as tool_contracts

        registered_actions = {
            f"{spec['tool']}.{action['name']}"
            for spec in tool_contracts.TOOL_REGISTRY
            for action in spec["actions"]
        }

        self.assertEqual(set(RESPONSE_SEMANTIC_CASES), registered_actions)
        referenced_case_ids = {case_id for case_ids in RESPONSE_SEMANTIC_CASES.values() for case_id in case_ids}
        self.assertEqual(set(CASE_ID_TEST_REFS), referenced_case_ids)

        for action_key, case_ids in sorted(RESPONSE_SEMANTIC_CASES.items()):
            with self.subTest(action=action_key):
                self.assertIsInstance(case_ids, tuple)
                self.assertGreaterEqual(len(case_ids), 1)
                for case_id in case_ids:
                    self.assertIsInstance(case_id, str)
                    self.assertTrue(case_id.startswith("ESC-"), msg=case_id)
                    self.assertTrue(case_id.strip(), msg=case_id)
                    self.assertIn(case_id, CASE_ID_TEST_REFS, msg=f"missing testcase binding for {case_id}")
                    refs = CASE_ID_TEST_REFS[case_id]
                    self.assertIsInstance(refs, tuple)
                    self.assertGreaterEqual(len(refs), 1)
                    for ref in refs:
                        with self.subTest(case_id=case_id, ref=ref):
                            self._resolve_test_ref(ref)

        self.assertEqual(
            ACTION_SEMANTIC_ASSERTION_TEST_REFS,
            _build_action_semantic_assertion_test_refs(),
        )
        self.assertEqual(set(ACTION_SEMANTIC_ASSERTION_TEST_REFS), registered_actions)

        observed_by_ref: dict[str, set[str]] = {}
        for ref, declared_actions_tuple in sorted(SEMANTIC_ASSERTION_TEST_ACTIONS.items()):
            with self.subTest(semantic_ref=ref):
                declared_actions = set(declared_actions_tuple)
                self.assertGreaterEqual(len(declared_actions), 1, msg=ref)
                self.assertTrue(declared_actions.issubset(registered_actions), msg=ref)
                observed_actions = self._run_semantic_assertion_test_and_capture_actions(ref)
                observed_by_ref[ref] = observed_actions
                missing_actions = sorted(declared_actions - observed_actions)
                self.assertFalse(
                    missing_actions,
                    msg=f"{ref} did not execute declared actions: {missing_actions}; observed={sorted(observed_actions)}",
                )

        for action_key, refs in sorted(ACTION_SEMANTIC_ASSERTION_TEST_REFS.items()):
            with self.subTest(action_proof=action_key):
                self.assertGreaterEqual(len(refs), 1, msg=action_key)
                observed_refs = [ref for ref in refs if action_key in observed_by_ref.get(ref, set())]
                self.assertTrue(
                    observed_refs,
                    msg=f"{action_key} has no real semantic assertion coverage run; refs={refs}",
                )


if __name__ == "__main__":
    unittest.main()
