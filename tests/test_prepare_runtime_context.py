#!/usr/bin/env python3
"""Functional coverage for prepare.runtime_context contract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_profiles  # noqa: E402
import env_store  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"

PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"
DEV_REQUEST = "实现 landing page hero 文案和 CTA 调整"
TEST_REQUEST = "验证 landing page hero 和 CTA 行为"

REQUESTS_BY_BUDDY = {
    "market": MARKET_REQUEST,
    "pm": PM_REQUEST,
    "design": DESIGN_REQUEST,
    "dev": DEV_REQUEST,
    "test": TEST_REQUEST,
}


def _pm_commit_with_track_and_handoff() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote PRD, created track, and handed off to Market.",
        "working_notes": [
            "User asked for PRD creation and track binding in one PM turn.",
        ],
        "artifacts": [
            {
                "kind": "prd",
                "title": "AI Schedule Tool Landing Page PRD",
                "summary": "Defines MVP page scope, positioning hooks, and acceptance criteria.",
                "content": {
                    "problem": "Busy professionals need less scheduling back-and-forth.",
                    "requirements": [
                        "Hero explains the concrete value quickly.",
                        "CTA drives user to start a scheduling flow.",
                    ],
                },
            }
        ],
        "state_effects": {
            "track": {
                "action": "create",
                "track_id": "track-ai-schedule-landing-page",
                "title": "AI Schedule Tool Landing Page",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "market",
                "summary": "Cross-buddy landing page iteration for AI scheduling.",
            },
            "task": {
                "status": "done",
                "summary": "PM PRD is ready for market positioning research.",
            },
        },
        "handoff": {
            "next_buddy": "market",
            "reason": "Market should validate competitor positioning before design.",
            "context": "Use the PRD artifact plus track summary as source context.",
        },
        "contributors": {
            "skills": ["write-prd", "track-manager"],
            "agents": [],
        },
    }


class PrepareRuntimeContextTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": "instance-test",
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _prepare(
        self,
        *,
        buddy: str,
        request_text: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with patch.object(
            turn_runtime,
            "_load_product_mode_session",
            return_value=self._session(buddy=buddy, payload=payload),
        ):
            prepared = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(prepared["ok"], msg=prepared)
        return prepared

    def _buddies_by_id(self) -> dict[str, dict[str, object]]:
        manifest = env_manifest.load_manifest(MANIFEST)
        return env_manifest.buddies_by_id(manifest)

    def _manifest_buddy_order(self) -> list[str]:
        manifest = env_manifest.load_manifest(MANIFEST)
        rows = manifest.get("buddies", [])
        ordered: list[str] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                ordered.append(row["id"])
        return ordered

    def _persist_pm_track_with_handoff(self) -> dict[str, object]:
        pm_context = self._prepare(buddy="pm", request_text=PM_REQUEST)
        persisted = turn_runtime.persist_buddy_run(
            pm_context,
            result=_pm_commit_with_track_and_handoff(),
            manifest_path=MANIFEST,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        receipt = persisted["receipt"]
        self.assertIsInstance(receipt, dict, msg=persisted)
        assert isinstance(receipt, dict)
        return receipt

    def _assert_structured_source_descriptor(
        self,
        source_desc: dict[str, object],
        key: str,
    ) -> None:
        descriptor = source_desc.get(key)
        self.assertIsInstance(descriptor, dict, msg={key: descriptor})
        assert isinstance(descriptor, dict)
        for field in ("description", "content", "scope", "nullable", "decision_use"):
            self.assertIn(field, descriptor)

    def test_prepare_returns_runtime_context_for_each_buddy(self) -> None:
        buddy_order = self._manifest_buddy_order()
        for index, buddy in enumerate(buddy_order):
            switch_target = buddy_order[(index + 1) % len(buddy_order)]
            request_text = f"switch {switch_target}: {REQUESTS_BY_BUDDY[buddy]}"
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=request_text)
                self.assertEqual(payload["active_buddy"], buddy)
                self.assertEqual(payload["request_text"], request_text)

                runtime_context = payload["runtime_context"]
                self.assertIsInstance(runtime_context, dict)
                for key in (
                    "active_buddy",
                    "active_skill_ids",
                    "capability_boundary",
                    "env_tools",
                    "tool_requirements",
                    "persist_payload_hint",
                    "desc",
                    "track_lifecycle_desc",
                    "artifact_kind_desc",
                    "context_sources_desc",
                    "current_context_summary",
                ):
                    self.assertIn(key, runtime_context)

                active_buddy = runtime_context["active_buddy"]
                self.assertIsInstance(active_buddy, dict)
                self.assertEqual(active_buddy["id"], buddy)

                self.assertEqual(payload["run_envelope"]["turn_identity"]["active_buddy"], buddy)

                forbidden_router_fields = (
                    "recommended_switch",
                    "selected_skill",
                    "selected_skill_packet",
                )
                for field in forbidden_router_fields:
                    self.assertNotIn(field, payload)

    def test_prepare_runtime_context_capability_boundary_matches_manifest_and_profiles(self) -> None:
        buddy_order = self._manifest_buddy_order()
        buddies = self._buddies_by_id()

        for buddy in buddy_order:
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]

                self.assertEqual(runtime_context["active_skill_ids"], buddies[buddy]["skills"])

                boundary = runtime_context["capability_boundary"]
                self.assertEqual(boundary["allowed_artifact_kinds"], buddies[buddy]["artifact_kinds"])
                self.assertEqual(boundary["allowed_state_effects"]["task"], ["status", "summary"])

                expected_track_effects = ["create", "update", "advance", "archive"] if buddy == "pm" else []
                self.assertEqual(boundary["allowed_state_effects"]["track"], expected_track_effects)
                self.assertEqual(boundary["handoff_targets"], buddy_order)

    def test_prepare_exposes_project_scratch_and_raw_state_boundaries(self) -> None:
        required_raw_paths = {
            "buddyswitch/objects/tracks/*.json",
            "buddyswitch/objects/tasks/*.json",
            "buddyswitch/objects/artifacts/*.json",
            "buddyswitch/content/runs/*.json",
        }

        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                boundary = payload["runtime_context"]["capability_boundary"]

                project = boundary["project"]
                self.assertEqual(project["path"], "projects/app")
                self.assertEqual(project["access"], profile["project"]["access"])
                write_rule = str(project.get("write_rule", ""))
                if buddy == "dev":
                    self.assertIn("write", write_rule.lower())
                else:
                    self.assertIn("dev", write_rule.lower())

                scratch = boundary["scratch"]
                self.assertEqual(scratch["root"], f"runs/raw/{buddy}")
                self.assertEqual(scratch["access"], "write")

                raw_state = boundary["raw_state"]
                self.assertEqual(raw_state["access"], "broker-only")
                self.assertTrue(required_raw_paths.issubset(set(raw_state["paths"])))

    def test_prepare_exposes_tool_requirements_and_persist_payload_hints(self) -> None:
        required_optional = {
            "working_notes",
            "artifacts",
            "state_effects",
            "handoff",
            "contributors",
            "tool_evidence",
        }

        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]

                tool_requirements = runtime_context["tool_requirements"]
                self.assertEqual(tool_requirements["browser_cockpit"], profile["tool_capability"]["browser_cockpit"])
                self.assertEqual(
                    tool_requirements["market_research_evidence"],
                    profile["tool_capability"]["market_research_evidence"],
                )
                self.assertEqual(
                    tool_requirements["ordinary_web_fallback"],
                    profile["tool_capability"]["ordinary_web_fallback"],
                )

                hint = runtime_context["persist_payload_hint"]
                self.assertIn("execution_summary", hint["required"])
                self.assertTrue(required_optional.issubset(set(hint["optional"])))
                durable_rule = str(hint["durable_signal_rule"]).lower()
                self.assertIn("artifacts", durable_rule)
                self.assertIn("state_effects", durable_rule)
                self.assertIn("handoff", durable_rule)
                self.assertEqual(
                    hint["artifact_kind_source"],
                    "runtime_context.capability_boundary.allowed_artifact_kinds",
                )
                self.assertEqual(
                    hint["state_effect_source"],
                    "runtime_context.capability_boundary.allowed_state_effects",
                )
                self.assertEqual(
                    hint["handoff_target_source"],
                    "runtime_context.capability_boundary.handoff_targets",
                )

                if buddy == "market":
                    tool_evidence_hint = hint["tool_evidence"]
                    self.assertIn("Market", tool_evidence_hint["required_when"])
                    self.assertEqual(
                        set(tool_evidence_hint["accepted_fields"]),
                        {"browser_cockpit_token", "approved_downgrade_token"},
                    )

    def test_prepare_exposes_env_tool_hints(self) -> None:
        payload = self._prepare(buddy="dev", request_text=DEV_REQUEST)
        env_tools = payload["runtime_context"]["env_tools"]
        self.assertIn("task_manager", env_tools)
        task_manager = env_tools["task_manager"]
        self.assertEqual(task_manager["command"], "python3 scripts/env/client.py task <operation>")
        self.assertEqual(task_manager["scope"], "active-buddy runtime-enforced")
        self.assertEqual(task_manager["broker_method"], "env.tool")
        envelope = task_manager["envelope"]
        self.assertEqual(
            envelope,
            {
                "tool": "task",
                "action": "<action>",
                "args": "<object>",
            },
        )
        operations = task_manager["operations"]
        self.assertEqual(
            operations,
            ["create", "list", "get", "get_current", "set_current", "update", "archive"],
        )
        payload_fields = task_manager["payload_fields"]
        self.assertEqual(payload_fields["create"], ["title", "summary"])
        self.assertEqual(payload_fields["get"], ["task_id"])
        self.assertEqual(payload_fields["set_current"], ["task_id"])

        self.assertIn("track_manager", env_tools)
        track_manager = env_tools["track_manager"]
        self.assertEqual(track_manager["command"], "python3 scripts/env/client.py track <operation>")
        self.assertEqual(track_manager["broker_method"], "env.tool")
        self.assertEqual(
            track_manager["envelope"],
            {
                "tool": "track",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(
            track_manager["operations"],
            [
                "list",
                "get",
                "get_current",
                "create",
                "update",
                "advance",
                "archive",
                "attach_task",
                "detach_task",
            ],
        )
        track_payload_fields = track_manager["payload_fields"]
        self.assertEqual(track_payload_fields["get"], ["track_id"])
        self.assertEqual(track_payload_fields["archive"], ["track_id"])
        self.assertEqual(track_payload_fields["attach_task"], ["track_id", "task_id"])

        self.assertIn("artifact_manager", env_tools)
        artifact_manager = env_tools["artifact_manager"]
        self.assertEqual(artifact_manager["command"], "python3 scripts/env/client.py artifact <operation>")
        self.assertEqual(artifact_manager["broker_method"], "env.tool")
        self.assertEqual(
            artifact_manager["envelope"],
            {
                "tool": "artifact",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(
            artifact_manager["operations"],
            [
                "list",
                "get",
                "get_current",
                "validate_payload",
                "create_revision",
                "update_metadata",
            ],
        )
        artifact_payload_fields = artifact_manager["payload_fields"]
        self.assertEqual(artifact_payload_fields["get"], ["artifact_id"])
        self.assertEqual(
            artifact_payload_fields["create_revision"],
            ["artifact_id", "task_id", "kind", "title", "summary", "content", "source_run_id"],
        )

        self.assertIn("context_manager", env_tools)
        context_manager = env_tools["context_manager"]
        self.assertEqual(context_manager["command"], "python3 scripts/env/client.py context <operation>")
        self.assertEqual(context_manager["broker_method"], "env.tool")
        self.assertEqual(
            context_manager["envelope"],
            {
                "tool": "context",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(context_manager["operations"], ["get", "summarize", "list_sources"])
        self.assertEqual(context_manager["payload_fields"]["get"], ["context"])
        self.assertEqual(context_manager["payload_fields"]["summarize"], [])
        self.assertEqual(context_manager["payload_fields"]["list_sources"], [])

        self.assertIn("binding_manager", env_tools)
        binding_manager = env_tools["binding_manager"]
        self.assertEqual(binding_manager["command"], "python3 scripts/env/client.py binding <operation>")
        self.assertEqual(binding_manager["broker_method"], "env.tool")
        self.assertEqual(
            binding_manager["envelope"],
            {
                "tool": "binding",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(binding_manager["operations"], ["get", "set_task", "set_track", "clear"])
        self.assertEqual(binding_manager["payload_fields"]["get"], [])
        self.assertEqual(binding_manager["payload_fields"]["set_task"], ["task_id"])
        self.assertEqual(binding_manager["payload_fields"]["set_track"], ["track_id"])
        self.assertEqual(binding_manager["payload_fields"]["clear"], [])

        self.assertIn("handoff_manager", env_tools)
        handoff_manager = env_tools["handoff_manager"]
        self.assertEqual(handoff_manager["command"], "python3 scripts/env/client.py handoff <operation>")
        self.assertEqual(handoff_manager["broker_method"], "env.tool")
        self.assertEqual(
            handoff_manager["envelope"],
            {
                "tool": "handoff",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(handoff_manager["operations"], ["validate"])
        self.assertEqual(handoff_manager["payload_fields"]["validate"], ["next_buddy", "reason", "context", "track_id"])

        self.assertIn("run_manager", env_tools)
        run_manager = env_tools["run_manager"]
        self.assertEqual(run_manager["command"], "python3 scripts/env/client.py run <operation>")
        self.assertEqual(run_manager["broker_method"], "env.tool")
        self.assertEqual(
            run_manager["envelope"],
            {
                "tool": "run",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(run_manager["operations"], ["commit", "get_receipt", "get_raw", "validate_result"])
        self.assertEqual(run_manager["payload_fields"]["commit"], ["context", "result"])
        self.assertEqual(run_manager["payload_fields"]["validate_result"], ["context", "result"])
        self.assertEqual(run_manager["payload_fields"]["get_receipt"], ["run_id"])
        self.assertEqual(run_manager["payload_fields"]["get_raw"], ["run_id"])

        self.assertIn("evidence_manager", env_tools)
        evidence_manager = env_tools["evidence_manager"]
        self.assertEqual(evidence_manager["command"], "python3 scripts/env/client.py evidence <operation>")
        self.assertEqual(evidence_manager["broker_method"], "env.tool")
        self.assertEqual(
            evidence_manager["envelope"],
            {
                "tool": "evidence",
                "action": "<action>",
                "args": "<object>",
            },
        )
        self.assertEqual(evidence_manager["operations"], ["issue_browser", "approve_downgrade"])
        self.assertEqual(evidence_manager["payload_fields"]["issue_browser"], ["context"])
        self.assertEqual(evidence_manager["payload_fields"]["approve_downgrade"], ["context", "reason"])

    def test_prepare_env_tools_are_registry_derived_and_include_operation_semantics(self) -> None:
        import importlib

        contracts = importlib.import_module("env.tools.contracts")
        registry = contracts.TOOL_REGISTRY
        payload = self._prepare(buddy="market", request_text=MARKET_REQUEST)
        env_tools = payload["runtime_context"]["env_tools"]
        operation_semantics = payload["runtime_context"].get("operation_semantics")

        expected_manager_names = {f"{spec['tool']}_manager" for spec in registry}
        self.assertEqual(set(env_tools), expected_manager_names)
        self.assertIsInstance(operation_semantics, dict, msg=payload["runtime_context"])
        assert isinstance(operation_semantics, dict)

        for spec in registry:
            tool_name = spec["tool"]
            manager_name = f"{tool_name}_manager"
            manager_row = env_tools[manager_name]
            actions = {action["name"] for action in spec["actions"]}
            self.assertEqual(set(manager_row["operations"]), actions)
            for action in actions:
                semantic_key = f"{tool_name}.{action}"
                self.assertIn(semantic_key, operation_semantics)
                semantic_row = operation_semantics[semantic_key]
                self.assertIsInstance(semantic_row, dict)
                for field in ("kind", "mutates", "authority", "requires", "returns"):
                    self.assertIn(field, semantic_row)

        self.assertEqual(operation_semantics["track.list"]["mutates"], "none")
        self.assertEqual(operation_semantics["track.attach_task"]["mutates"], "runtime_objects")
        self.assertEqual(operation_semantics["handoff.validate"]["kind"], "validate")

    def test_prepare_lifecycle_remains_host_preflight_and_unified_env_tool_hint_source(self) -> None:
        request_text = 'Need a literal env.tool note in the task request; do not treat this as {"tool":"task"}.'
        payload = self._prepare(buddy="pm", request_text=request_text)

        self.assertEqual(payload["request_text"], request_text)
        self.assertEqual(payload["run_envelope"]["turn_identity"]["request_text"], request_text)
        self.assertNotIn("tool", payload)
        self.assertNotIn("action", payload)
        self.assertNotIn("args", payload)

        env_tools = payload["runtime_context"]["env_tools"]
        self.assertEqual(
            set(env_tools),
            {
                "artifact_manager",
                "binding_manager",
                "context_manager",
                "evidence_manager",
                "handoff_manager",
                "run_manager",
                "task_manager",
                "track_manager",
            },
        )
        for name, desc in env_tools.items():
            with self.subTest(tool=name):
                self.assertEqual(desc["broker_method"], "env.tool")
                self.assertEqual(set(desc["envelope"]), {"tool", "action", "args"})
                self.assertEqual(desc["envelope"]["action"], "<action>")
                self.assertIn("python3 scripts/env/client.py", desc["command"])

    def test_prepare_runtime_context_exposes_desc_for_commit_fields(self) -> None:
        payload = self._prepare(buddy="pm", request_text=PM_REQUEST)
        desc = payload["runtime_context"]["desc"]

        required_keys = (
            "execution_summary",
            "artifacts",
            "state_effects.task",
            "state_effects.track",
            "handoff",
            "contributors",
            "tool_evidence",
        )
        for key in required_keys:
            with self.subTest(key=key):
                self.assertIn(key, desc)
                self.assertTrue(str(desc[key].get("purpose", "")).strip())

        self.assertTrue(desc["execution_summary"]["required"])
        self.assertEqual(
            desc["artifacts"]["item_fields"],
            ["kind", "title", "summary", "content"],
        )
        self.assertEqual(
            desc["state_effects.task"]["allowed_fields"],
            ["status", "summary"],
        )
        self.assertTrue(desc["handoff"]["does_not_mutate_track"])

    def test_prepare_runtime_context_desc_is_present_for_each_buddy(self) -> None:
        required_keys = {
            "execution_summary",
            "artifacts",
            "state_effects.task",
            "state_effects.track",
            "handoff",
            "contributors",
            "tool_evidence",
        }
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                desc = payload["runtime_context"]["desc"]
                self.assertTrue(required_keys.issubset(set(desc)))
                self.assertTrue(all(str(desc[key].get("purpose", "")).strip() for key in required_keys))

                tool_evidence_required = desc["tool_evidence"].get("required")
                if buddy == "market":
                    self.assertIn("Market", str(tool_evidence_required))
                else:
                    self.assertFalse(tool_evidence_required)

    def test_prepare_writes_context_file_and_exposes_persist_hint(self) -> None:
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                context_save_path = payload["context_save_path"]
                self.assertIsInstance(context_save_path, str)
                self.assertTrue(context_save_path.startswith(f"runs/raw/{buddy}/"))
                self.assertFalse(Path(context_save_path).is_absolute())

                context_path = self._runtime_path(context_save_path)
                self.assertTrue(context_path.exists())

                persisted_context = json.loads(context_path.read_text(encoding="utf-8"))
                self.assertEqual(persisted_context["context_revision"], payload["context_revision"])
                self.assertEqual(persisted_context["active_buddy"], payload["active_buddy"])
                self.assertEqual(persisted_context["request_text"], payload["request_text"])
                self.assertEqual(
                    persisted_context["run_envelope"]["run_id"],
                    payload["run_envelope"]["run_id"],
                )
                self.assertEqual(persisted_context["context_save_path"], context_save_path)
                self.assertEqual(
                    persisted_context["persist_command_hint"],
                    payload["persist_command_hint"],
                )

                persist_command_hint = payload["persist_command_hint"]
                self.assertIn("python3 scripts/turn_runtime.py persist", persist_command_hint)
                self.assertIn(f"--context {context_save_path}", persist_command_hint)
                self.assertIn(f"--result runs/raw/{buddy}/persist-result.json", persist_command_hint)

                self.assertTrue(str(context_path).startswith(str(self._runtime_path(f"runs/raw/{buddy}"))))
                for forbidden_rel in ("projects/app", "buddyswitch/objects", "buddyswitch/content/runs"):
                    forbidden_root = self._runtime_path(forbidden_rel)
                    self.assertFalse(
                        context_path.resolve(strict=False).is_relative_to(forbidden_root.resolve(strict=False))
                    )
                    if forbidden_root.exists():
                        self.assertEqual(list(forbidden_root.rglob("prepare-context-*.json")), [])

    def test_prepare_exposes_track_lifecycle_desc_for_pm_and_non_pm(self) -> None:
        pm_payload = self._prepare(buddy="pm", request_text=REQUESTS_BY_BUDDY["pm"])
        pm_desc = pm_payload["runtime_context"]["track_lifecycle_desc"]
        self.assertEqual(pm_desc["owner"], "pm")
        self.assertEqual(pm_desc["allowed_actions"], ["create", "update", "advance", "archive"])
        self.assertTrue(pm_desc["non_create_requires_existing_track"])
        self.assertTrue(pm_desc["handoff_does_not_mutate_track"])
        self.assertEqual(pm_desc["current_track_source"], "current_track_id")
        self.assertIn("bind", str(pm_desc["create"]).lower())

        for buddy in ("market", "design", "dev", "test"):
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                lifecycle_desc = payload["runtime_context"]["track_lifecycle_desc"]
                self.assertEqual(lifecycle_desc["owner"], "pm")
                self.assertEqual(lifecycle_desc["allowed_actions"], [])
                self.assertTrue(lifecycle_desc["handoff_does_not_mutate_track"])
                self.assertIn("PM", str(lifecycle_desc["allowed_next_action"]))
                self.assertEqual(
                    lifecycle_desc["allowed_actions"],
                    payload["runtime_context"]["capability_boundary"]["allowed_state_effects"]["track"],
                )

    def test_prepare_exposes_artifact_kind_desc_for_active_buddy(self) -> None:
        buddies = self._buddies_by_id()
        all_manifest_kinds = {
            kind
            for buddy in buddies.values()
            for kind in buddy.get("artifact_kinds", [])
        }
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]
                allowed_kinds = runtime_context["capability_boundary"]["allowed_artifact_kinds"]
                artifact_kind_desc = runtime_context["artifact_kind_desc"]
                self.assertEqual(set(artifact_kind_desc), set(allowed_kinds))

                for kind, desc in artifact_kind_desc.items():
                    self.assertIn(kind, all_manifest_kinds)
                    self.assertTrue(str(desc.get("label", "")).strip())
                    self.assertTrue(str(desc.get("use_when", "")).strip())

    def test_prepare_exposes_structured_context_source_descriptors_for_product_work(self) -> None:
        receipt = self._persist_pm_track_with_handoff()
        market_task_id = "task-market-bound-for-source-desc"
        env_store.create_task(
            market_task_id,
            "Market Bound Source Descriptor Task",
            buddy="market",
            track_id=receipt["track_id"],
            status="active",
            summary="Bound market task for descriptor semantics.",
            initial_run_id=None,
        )
        market_context = self._prepare(
            buddy="market",
            request_text=MARKET_REQUEST,
            payload={
                "current_task_id": market_task_id,
                "current_track_id": receipt["track_id"],
            },
        )

        source_desc = market_context["runtime_context"]["context_sources_desc"]
        self.assertIsInstance(source_desc, dict, msg=market_context["runtime_context"])
        assert isinstance(source_desc, dict)
        for key in (
            "request_text",
            "task_context.task",
            "task_context.artifacts",
            "track_context.track",
            "track_context.recent_handoffs",
            "current_context_summary",
        ):
            with self.subTest(key=key):
                self.assertIn(key, source_desc)
                self._assert_structured_source_descriptor(source_desc, key)

        task_artifacts_descriptor = source_desc["task_context.artifacts"]
        assert isinstance(task_artifacts_descriptor, dict)
        self.assertEqual(task_artifacts_descriptor["content"], "full")
        self.assertEqual(
            task_artifacts_descriptor["summary_projection"],
            "runtime_context.current_context_summary.artifacts",
        )
        self.assertIn("read_prior_outputs", task_artifacts_descriptor["decision_use"])

        current_summary_descriptor = source_desc["current_context_summary"]
        assert isinstance(current_summary_descriptor, dict)
        self.assertEqual(current_summary_descriptor["content"], "summary")
        self.assertIn("first_pass_orientation", current_summary_descriptor["decision_use"])

        track_handoff_descriptor = source_desc["track_context.recent_handoffs"]
        assert isinstance(track_handoff_descriptor, dict)
        self.assertEqual(track_handoff_descriptor["scope"], "current_track_run_audits")
        self.assertIn("handoff_continuation", track_handoff_descriptor["decision_use"])

        task_artifacts = market_context["task_context"]["artifacts"]
        self.assertGreaterEqual(len(task_artifacts), 1)
        prd_artifact = next(row for row in task_artifacts if row["kind"] == "prd")
        self.assertIn("problem", prd_artifact["content"])
        compact_summary = market_context["runtime_context"]["current_context_summary"]["artifacts"]
        compact_row = next(row for row in compact_summary if row["id"] == prd_artifact["id"])
        self.assertNotIn("problem", json.dumps(compact_row, ensure_ascii=True))

    def test_market_prepare_decision_surface_marks_task_only_binding_and_candidate_track_absence(self) -> None:
        self._persist_pm_track_with_handoff()
        market_context = self._prepare(
            buddy="market",
            request_text="Continue market discovery with a fresh task-only binding.",
        )
        decision_surface = market_context["runtime_context"]["decision_surface"]
        binding_state = decision_surface["binding_state"]
        self.assertEqual(binding_state["state"], "bound_task_only")
        self.assertIsNone(binding_state["current_track_id"])
        self.assertEqual(decision_surface["active_buddy_relation"]["track_role"], "none")
        affordance_ids = {row["id"] for row in decision_surface["safe_read_affordances"]}
        self.assertIn("inspect_candidate_tracks", affordance_ids)
        for row in decision_surface["safe_read_affordances"]:
            self.assertEqual(row["mutates"], "none")
            self.assertTrue(row.get("source_refs"))

    def test_bound_market_prepare_decision_surface_marks_next_buddy_handoff_and_evidence_requirement(self) -> None:
        receipt = self._persist_pm_track_with_handoff()
        market_task_id = "task-market-bound-for-decision-surface"
        env_store.create_task(
            market_task_id,
            "Market Bound Decision Surface Task",
            buddy="market",
            track_id=receipt["track_id"],
            status="active",
            summary="Bound market task for decision surface semantics.",
            initial_run_id=None,
        )
        market_context = self._prepare(
            buddy="market",
            request_text="Continue PM handoff with bound track context.",
            payload={
                "current_task_id": market_task_id,
                "current_track_id": receipt["track_id"],
            },
        )
        decision_surface = market_context["runtime_context"]["decision_surface"]
        self.assertEqual(decision_surface["binding_state"]["state"], "bound_task_and_track")
        self.assertEqual(decision_surface["binding_state"]["current_track_id"], receipt["track_id"])
        relation = decision_surface["active_buddy_relation"]
        self.assertEqual(relation["track_role"], "next_buddy")
        self.assertTrue(relation["latest_handoff_to_active_buddy"])
        self.assertTrue(decision_surface["context_readiness"]["has_track_handoffs"])
        self.assertEqual(decision_surface["evidence_readiness"]["market_research_evidence"], "required")
        for row in decision_surface["safe_read_affordances"]:
            self.assertEqual(row["mutates"], "none")
            self.assertTrue(row.get("source_refs"))

    def test_market_prepare_decision_surface_exposes_evidence_readiness(self) -> None:
        market_context = self._prepare(buddy="market", request_text=MARKET_REQUEST)
        evidence_readiness = market_context["runtime_context"]["decision_surface"]["evidence_readiness"]
        self.assertEqual(evidence_readiness["browser_cockpit"], "required")
        self.assertEqual(evidence_readiness["market_research_evidence"], "required")

    def test_decision_surface_enum_values_cover_unbound_task_only_track_only_bound_and_stale(self) -> None:
        market_task_only = self._prepare(
            buddy="market",
            request_text="Task-only market turn for enum coverage.",
        )
        task_only_state = market_task_only["runtime_context"]["decision_surface"]["binding_state"]["state"]
        self.assertEqual(task_only_state, "bound_task_only")

        receipt = self._persist_pm_track_with_handoff()
        market_task_id = "task-market-track-only-state"
        env_store.create_task(
            market_task_id,
            "Market Track-Only State Task",
            buddy="market",
            track_id=receipt["track_id"],
            status="active",
            summary="Track-only binding state fixture.",
            initial_run_id=None,
        )
        track_only_context = self._prepare(
            buddy="market",
            request_text="Track-only state fixture.",
            payload={"current_track_id": receipt["track_id"]},
        )
        self.assertEqual(
            track_only_context["runtime_context"]["decision_surface"]["binding_state"]["state"],
            "bound_track_only",
        )

        bound_context = self._prepare(
            buddy="market",
            request_text="Fully bound state fixture.",
            payload={
                "current_task_id": market_task_id,
                "current_track_id": receipt["track_id"],
            },
        )
        self.assertEqual(
            bound_context["runtime_context"]["decision_surface"]["binding_state"]["state"],
            "bound_task_and_track",
        )
        binding_state_desc = bound_context["runtime_context"]["decision_surface"]["binding_state"]
        self.assertIn(
            "stale",
            set(binding_state_desc["enum_values"]),
        )

    def test_design_prepare_can_consume_prior_product_context(self) -> None:
        pm_context = self._prepare(buddy="pm", request_text=PM_REQUEST)
        persisted = turn_runtime.persist_buddy_run(
            pm_context,
            result=_pm_commit_with_track_and_handoff(),
            manifest_path=MANIFEST,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        receipt = persisted["receipt"]

        design_context = self._prepare(
            buddy="design",
            request_text=DESIGN_REQUEST,
            payload={
                "current_task_id": receipt["task_id"],
                "current_track_id": receipt["track_id"],
            },
        )

        source_desc = design_context["runtime_context"]["context_sources_desc"]
        self.assertIn("task_context.artifacts", source_desc)
        self.assertIn("track_context.track", source_desc)
        self.assertIn("current_context_summary", source_desc)

        task_artifacts = design_context["task_context"]["artifacts"]
        prd_artifact = next(row for row in task_artifacts if row["kind"] == "prd")
        self.assertIn("problem", prd_artifact["content"])

        track = design_context["track_context"]["track"]
        self.assertEqual(track["id"], receipt["track_id"])
        self.assertIn("Cross-buddy", track["summary"])

        compact_summary = design_context["runtime_context"]["current_context_summary"]
        compact_artifact = next(row for row in compact_summary["artifacts"] if row["id"] == prd_artifact["id"])
        self.assertNotIn("problem", json.dumps(compact_artifact, ensure_ascii=True))

    def test_market_prepare_summarizes_track_artifact_and_recent_handoff_after_pm_persist(self) -> None:
        pm_context = self._prepare(buddy="pm", request_text=PM_REQUEST)
        persisted = turn_runtime.persist_buddy_run(
            pm_context,
            result=_pm_commit_with_track_and_handoff(),
            manifest_path=MANIFEST,
        )
        self.assertTrue(persisted["ok"], msg=persisted)

        receipt = persisted["receipt"]
        market_context = self._prepare(
            buddy="market",
            request_text=MARKET_REQUEST,
            payload={
                "current_task_id": receipt["task_id"],
                "current_track_id": receipt["track_id"],
            },
        )

        runtime_context = market_context["runtime_context"]
        summary = runtime_context["current_context_summary"]

        self.assertEqual(summary["task"]["id"], receipt["task_id"])
        self.assertEqual(summary["track"]["id"], "track-ai-schedule-landing-page")

        artifacts = summary["artifacts"]
        self.assertIsInstance(artifacts, list)
        prd_artifact = None
        for artifact in artifacts:
            if artifact.get("id") == receipt["artifact_ids"][0]:
                prd_artifact = artifact
                break
        self.assertIsNotNone(prd_artifact)
        assert prd_artifact is not None
        self.assertEqual(prd_artifact["kind"], "prd")
        self.assertEqual(prd_artifact["buddy"], "pm")
        self.assertEqual(prd_artifact["task_id"], receipt["task_id"])
        self.assertNotIn("problem", json.dumps(prd_artifact, ensure_ascii=True))

        recent_handoffs = summary["recent_handoffs"]
        self.assertIsInstance(recent_handoffs, list)
        self.assertGreaterEqual(len(recent_handoffs), 1)
        handoff = recent_handoffs[0]
        self.assertEqual(handoff["run_id"], receipt["run_id"])
        self.assertEqual(handoff["next_buddy"], "market")
        self.assertIn("Market", handoff["reason"])
        self.assertIn("PRD", handoff["context"])


if __name__ == "__main__":
    unittest.main()
