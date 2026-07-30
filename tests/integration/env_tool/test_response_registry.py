"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)

ROOT = REPO_ROOT

import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.support import task_fixtures  # noqa: E402
from buddyswitch.env.repos import messages as message_repo  # noqa: E402
from buddyswitch.env.services import messages as message_service  # noqa: E402
from buddyswitch.env.tool_runtime import registry as tool_catalog  # noqa: E402
from buddyswitch.env.tool_runtime import results as tool_results  # noqa: E402
from buddyswitch.env.tool_runtime import context as runtime_context  # noqa: E402
import buddyswitch.env.tools.search._impl as search_impl  # noqa: E402
from buddyswitch.runtime_support import turn_runtime  # noqa: E402
from tests.integration.env_tool._response_case import EnvToolResponseCase

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolResponseRegistryTests(EnvToolResponseCase):
    def test_registry_excludes_removed_surfaces(self) -> None:
        tools = set(tool_catalog.supported_tools())
        self.assertNotIn("handoff", tools)
        self.assertNotIn("memory", tools)
        self.assertNotIn("run", tools)

    def test_context_get_and_summarize_catalog_scope(self) -> None:
        actor_id = "act-pm-context-scope"
        instance_json = self._instance_json(role="pm", actor_id=actor_id)

        full = self._dispatch(instance_json=instance_json, actor_id=actor_id, role="pm", tool="context", action="get", args={})
        summary = self._dispatch(instance_json=instance_json, actor_id=actor_id, role="pm", tool="context", action="summarize", args={})

        self._assert_success_contract(full)
        self._assert_success_contract(summary)
        self.assertIn("tool_catalog", full)
        self.assertIn("operation_semantics", full)
        demand_catalog = full["tool_catalog"]["demand_sys"]
        self.assertEqual(
            set(demand_catalog["operations"]),
            {"list", "get", "complete"},
        )
        self.assertNotIn("resolve_inbound", demand_catalog["action_semantics"])
        self.assertNotIn("demand_sys.resolve_inbound", full["operation_semantics"])
        registry_demand = tool_catalog.env_tools_description()["demand_sys"]
        for action in ("list", "get", "complete"):
            self.assertEqual(
                demand_catalog["action_semantics"][action],
                registry_demand["action_semantics"][action],
            )
        self.assertNotEqual(full.get("tool_catalog"), turn_runtime._build_env_tools_desc())
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
        self.assertIn("track.resolve_comment_thread", full.get("operation_semantics", {}))
        self.assertNotIn("comment.resolve", full.get("operation_semantics", {}))

    def test_context_projections_explain_demand_and_task_product_boundaries(self) -> None:
        actor_id = "act-dev-demand-task-semantics"
        instance_json = self._instance_json(role="dev", actor_id=actor_id)

        full = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="dev",
            tool="context",
            action="get",
            args={},
        )
        summary = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="dev",
            tool="context",
            action="summarize",
            args={},
        )

        demand = full["tool_catalog"]["demand_sys"]
        task = full["tool_catalog"]["task_sys"]
        demand_compact = summary["tool_affordances"]["demand_sys"]
        task_compact = summary["tool_affordances"]["task_sys"]

        self.assertIn("host-owned", demand["capability_boundary"].lower())
        self.assertIn("task sys never mutates a demand", task["capability_boundary"].lower())
        self.assertEqual(demand_compact["object_model"], demand["object_model"])
        self.assertEqual(task_compact["object_model"], task["object_model"])
        demand_actions = demand["action_semantics"]
        task_actions = task["action_semantics"]
        self.assertEqual(set(demand_actions), {"list", "get", "complete"})
        for action, fields in {
            "complete": ("demand_ref", "summary", "evidence_refs"),
        }.items():
            with self.subTest(tool="demand_sys", action=action):
                explained = demand_actions[action]["inputs_explained"]
                for field in fields:
                    self.assertIn(field, explained)
                    self.assertTrue(explained[field].strip())
        for field in ("demand_ref", "objective", "selection_reason"):
            self.assertIn(field, task_actions["create"]["inputs_explained"])
            self.assertTrue(task_actions["create"]["inputs_explained"][field].strip())
        self.assertNotIn("input_schemas", demand_compact)
        self.assertNotIn("action_semantics", demand_compact)
        self.assertNotIn("input_schemas", task_compact)
        self.assertNotIn("action_semantics", task_compact)

    def test_unknown_tool_rejection_contract(self) -> None:
        actor_id = "act-pm-reject"
        instance_json = self._instance_json(role="pm", actor_id=actor_id)
        payload = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="pm",
            tool="unknown",
            action="list",
            args={},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_representative_responses_match_declared_effect_classes(self) -> None:
        actor_id = "act-declared-effects"
        pm_instance = self._instance_json(role="pm", actor_id=actor_id)
        dev_instance = self._instance_json(role="dev", actor_id=f"{actor_id}-dev")

        context_read = self._dispatch(
            instance_json=dev_instance,
            actor_id=f"{actor_id}-dev",
            role="dev",
            tool="context",
            action="get",
            args={},
        )
        self._assert_success_matches_declared_action_semantics("context.get", context_read)

        track = self._dispatch(
            instance_json=pm_instance,
            actor_id=actor_id,
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-declared-effects",
                "title": "Declared Effects",
                "outcome": "Compare responses to definitions.",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self._assert_success_matches_declared_action_semantics("track.create", track)

        draft = self._dispatch(
            instance_json=dev_instance,
            actor_id=f"{actor_id}-dev",
            role="dev",
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
        source = self.runtime_root / "private" / "notes" / "effects.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("private", encoding="utf-8")
        attached = self._dispatch(
            instance_json=dev_instance,
            actor_id=f"{actor_id}-dev",
            role="dev",
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
            actor_id=f"{actor_id}-dev",
            role="dev",
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
            actor_id=f"{actor_id}-dev",
            role="dev",
            tool="search",
            action="request",
            args={"query": "BuddySwitch", "backend": "browser", "engine": "google"},
        )
        self._assert_success_matches_declared_action_semantics("search.request", search_plan)

        browser_open_removed = self._dispatch(
            instance_json=dev_instance,
            actor_id=f"{actor_id}-dev",
            role="dev",
            tool="search",
            action="open_browser",
            args={"query": "BuddySwitch", "engine": "google"},
        )
        self._assert_rejection_contract(browser_open_removed)
        self.assertEqual((browser_open_removed.get("error") or {}).get("code"), "E_ENV_TOOL", msg=browser_open_removed)
        self.assertEqual(browser_open_removed.get("permission_boundary"), "env.tool", msg=browser_open_removed)
        self.assertIn("unsupported env.tool payload.action for search: open_browser", json.dumps(browser_open_removed, ensure_ascii=True))
        self.assertNotIn("browser.open_url", json.dumps(browser_open_removed, ensure_ascii=True))

    def test_rejection_supports_canonical_field_errors(self) -> None:
        payload = tool_results.rejection(
            tool="track",
            action="track.create",
            current_identity={"id": "act-pm-response-contract", "type": "actor"},
            active_role="pm",
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
                current_identity={"id": "act-pm-response-contract", "type": "actor"},
                active_role="pm",
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

    def test_tool_result_helpers_require_current_identity(self) -> None:
        identity = {"id": "act-pm-result-helper", "type": "actor"}
        ok = tool_results.success(
            tool="context",
            action="context.summarize",
            current_identity=identity,
            active_role="pm",
            effect_summary="Returned context.",
            state_changed=False,
            durability="none",
        )
        self.assertEqual(ok.get("current_identity"), identity)
        self.assertEqual(ok.get("active_role"), "pm")

        rejection = tool_results.rejection(
            tool="context",
            action="context.summarize",
            current_identity=identity,
            active_role="pm",
            code="E_CONTEXT_PAYLOAD",
            message="limit must be a positive integer",
            permission_boundary="context.filter",
            human_summary="Context filter payload is invalid.",
            why_blocked="limit must be a positive integer",
            impact="Context stayed read-only.",
            state_changed=False,
            retryable=True,
            retry_guidance="Fix limit and retry.",
        )
        self.assertEqual(rejection.get("current_identity"), identity)
        self.assertEqual(rejection.get("active_role"), "pm")

        with self.assertRaises((TypeError, ValueError)):
            tool_results.success(
                tool="context",
                action="context.summarize",
                active_role="pm",
                effect_summary="Returned context.",
                state_changed=False,
                durability="none",
            )
        with self.assertRaises((TypeError, ValueError)):
            tool_results.rejection(
                tool="context",
                action="context.summarize",
                active_role="pm",
                code="E_CONTEXT_PAYLOAD",
                message="limit must be a positive integer",
                permission_boundary="context.filter",
                human_summary="Context filter payload is invalid.",
                why_blocked="limit must be a positive integer",
                impact="Context stayed read-only.",
                state_changed=False,
                retryable=True,
                retry_guidance="Fix limit and retry.",
            )
        with self.assertRaises(ValueError):
            tool_results.success(
                tool="context",
                action="context.summarize",
                current_identity={"type": "actor"},
                active_role="pm",
                effect_summary="Returned context.",
                state_changed=False,
                durability="none",
            )

    def test_high_friction_payload_rejections_include_field_errors(self) -> None:
        pm_actor_id = "act-pm-field-errors"
        dev_actor_id = "act-dev-field-errors"
        pm_instance_json = self._instance_json(role="pm", actor_id=pm_actor_id)
        dev_instance_json = self._instance_json(role="dev", actor_id=dev_actor_id)

        created = self._dispatch(
            instance_json=pm_instance_json,
            actor_id=pm_actor_id,
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-field-errors",
                "title": "Field Errors",
                "outcome": "Improve payload recovery.",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        draft = self._dispatch(
            instance_json=dev_instance_json,
            actor_id=dev_actor_id,
            role="dev",
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
                    actor_id=pm_actor_id,
                    role="pm",
                    tool="track",
                    action="create",
                    args={
                        "track_id": "track-field-errors-bad-now",
                        "title": "Bad now",
                        "outcome": "fail",
                        "now": "next step",
                    },
                ),
                "now",
            ),
            (
                "track.update_status.now",
                self._dispatch(
                    instance_json=pm_instance_json,
                    actor_id=pm_actor_id,
                    role="pm",
                    tool="track",
                    action="update_status",
                    args={"track_id": "track-field-errors", "state": "active", "now": {"blocker": None}},
                ),
                "now",
            ),
            (
                "track.add_update.refs",
                self._dispatch(
                    instance_json=pm_instance_json,
                    actor_id=pm_actor_id,
                    role="pm",
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
                    actor_id=dev_actor_id,
                    role="dev",
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
                    actor_id=dev_actor_id,
                    role="dev",
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
                "track.add_comment.mentioned_identity_ids",
                self._dispatch(
                    instance_json=pm_instance_json,
                    actor_id=pm_actor_id,
                    role="pm",
                    tool="track",
                    action="add_comment",
                    args={
                        "track_id": "track-field-errors",
                        "content": "check mentions",
                        "mentioned_identity_ids": "act-pm-field-errors",
                    },
                ),
                "mentioned_identity_ids",
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
