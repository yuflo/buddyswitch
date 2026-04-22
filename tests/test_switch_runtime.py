#!/usr/bin/env python3
"""Regression tests for task-centric BuddySwitch resolve/persist runtime."""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import textwrap
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import switch_runtime  # noqa: E402
import workspace_data  # noqa: E402
import runtime_store.projections as workspace_projections  # noqa: E402
from env_store import create_artifact, create_task, create_track, get_task, get_track, require_id, validate_artifact, validate_track  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

EXPECTED_MARKET_HOST_EXECUTION = {
    "execution_mode": "browser-cockpit-native",
    "browser_mode": "headed-only",
    "browser_profile": "shared-browser",
    "browser_executor": "chrome-devtools-cockpit",
    "discovery_mode": "browser-native",
    "login_policy": "mandatory-takeover",
    "fallback_policy": "no-silent-degrade",
    "session_continuity": "shared-cockpit",
    "evidence_capture_level": "medium",
}

EXPECTED_MARKET_TOOL_SCOPE = {
    "profile": "market-browser-native",
    "mode": "allowlist",
    "allowed_tool_servers": ["chrome-devtools-cockpit"],
    "downgrade_policy": "user-approved-one-off",
    "temporary_allowed_tool_servers": ["web"],
    "downgrade_reason": "browser-native-blocked",
}

RESOLVE_CONTEXT_RESPONSE_KEY_ORDER = [
    "ok",
    "context_revision",
    "switch",
    "buddy",
    "authority",
    "task_resolution",
    "run_envelope",
    "task_context",
    "track_context",
    "inputs",
    "skills",
    "warnings",
]

RESOLVE_CONTEXT_PACKET_ERA_FIELDS = [
    "invocation",
    "skill_cards",
    "eligible_skills",
    "implicit_skill_id",
    "track_artifact_index",
    "run_instructions",
    "run_instructions_by_skill",
    "artifact_selection_by_skill",
]

PERSIST_SKILL_RESULT_RESPONSE_KEY_ORDER = [
    "ok",
    "receipt",
    "refreshed_context",
]

PERSIST_SKILL_RESULT_PACKET_ERA_FIELDS = [
    "skill_id",
    "task_id",
    "artifact_id",
    "artifact_ids",
    "run_id",
    "paths",
    "writes",
]


def _contains_key_recursive(payload: object, forbidden_key: str) -> bool:
    if isinstance(payload, dict):
        if forbidden_key in payload:
            return True
        return any(_contains_key_recursive(value, forbidden_key) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_key_recursive(item, forbidden_key) for item in payload)
    return False


class RuntimeKernelFacadeTests(unittest.TestCase):
    def test_runtime_kernel_package_exports_entrypoints(self) -> None:
        import runtime_kernel

        self.assertTrue(callable(runtime_kernel.resolve_switch_request))
        self.assertTrue(callable(runtime_kernel.persist_skill_result_request))
        self.assertFalse(hasattr(runtime_kernel, "persist_switch_request"))
        self.assertFalse(hasattr(runtime_kernel, "prepare_execution_request"))

    def test_runtime_kernel_resolve_entrypoint_defaults_manifest(self) -> None:
        import runtime_kernel

        sentinel = {"ok": True, "delegate": "resolve-kernel"}
        with patch.object(switch_runtime, "_build_resolve_context", return_value=sentinel) as mock_delegate:
            payload = runtime_kernel.resolve_switch_request("switch dev: keep cli stable")

        self.assertIs(payload, sentinel)
        mock_delegate.assert_called_once_with(
            "switch dev: keep cli stable",
            manifest_path=switch_runtime.DEFAULT_MANIFEST,
        )

    def test_runtime_kernel_persist_skill_result_entrypoint_defaults_manifest(self) -> None:
        import runtime_kernel

        context = {"ok": True}
        result = {"execution_summary": "ok", "artifact_content": {"done": True}}
        sentinel = {"ok": True, "delegate": "persist-skill-result-kernel"}
        with patch.object(
            switch_runtime,
            "_persist_skill_result",
            return_value=sentinel,
        ) as mock_delegate:
            payload = runtime_kernel.persist_skill_result_request(
                context,
                skill_id="implement-task",
                result=result,
            )

        self.assertIs(payload, sentinel)
        mock_delegate.assert_called_once_with(
            context,
            skill_id="implement-task",
            result=result,
            manifest_path=switch_runtime.DEFAULT_MANIFEST,
        )

    def test_runtime_kernel_resolve_facade_delegates(self) -> None:
        sentinel = {"ok": True, "delegate": "resolve"}
        with patch("runtime_kernel.resolve.resolve_switch_request", return_value=sentinel) as mock_delegate:
            payload = switch_runtime.resolve_switch("switch dev: keep cli stable")

        self.assertIs(payload, sentinel)
        mock_delegate.assert_called_once_with(
            "switch dev: keep cli stable",
            manifest_path=switch_runtime.DEFAULT_MANIFEST,
        )

    def test_prepare_execution_payload_surface_is_retired(self) -> None:
        self.assertFalse(hasattr(switch_runtime, "prepare_execution_payload"))

    def test_persist_switch_public_facade_is_retired(self) -> None:
        self.assertFalse(hasattr(switch_runtime, "persist_switch"))

    def test_runtime_kernel_persist_skill_result_facade_delegates(self) -> None:
        context = {"ok": True}
        result = {"execution_summary": "ok", "artifact_content": {"done": True}}
        sentinel = {"ok": True, "delegate": "persist-skill-result"}
        with patch("runtime_kernel.persist.persist_skill_result_request", return_value=sentinel) as mock_delegate:
            payload = switch_runtime.persist_skill_result(
                context,
                skill_id="implement-task",
                result=result,
            )

        self.assertIs(payload, sentinel)
        mock_delegate.assert_called_once_with(
            context,
            skill_id="implement-task",
            result=result,
            manifest_path=switch_runtime.DEFAULT_MANIFEST,
        )

    def test_cmd_resolve_returns_runtime_error_payload_on_oserror(self) -> None:
        args = argparse.Namespace(
            text="switch dev: keep cli stable",
            manifest=switch_runtime.DEFAULT_MANIFEST,
        )

        stdout = io.StringIO()
        with patch.object(switch_runtime, "resolve_switch", side_effect=OSError("disk full")):
            with redirect_stdout(stdout):
                exit_code = switch_runtime._cmd_resolve(args)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_RUNTIME_RESOLVE")
        self.assertIn("disk full", payload["error"]["message"])


class WorkspaceProjectionFacadeTests(unittest.TestCase):
    def test_workspace_data_build_workspace_data_facade_delegates_to_runtime_store_projection(self) -> None:
        sentinel = {"generated_at": "2026-04-21T00:00:00+08:00"}
        with patch(
            "runtime_store.projections.build_workspace_projection",
            return_value=sentinel,
        ) as mock_delegate:
            payload = workspace_data.build_workspace_data()

        self.assertIs(payload, sentinel)
        mock_delegate.assert_called_once_with()

    def test_workspace_data_runtime_store_projection_assembles_without_workspace_legacy_builder(self) -> None:
        with patch.object(
            workspace_data,
            "_legacy_build_workspace_data",
            side_effect=AssertionError("legacy workspace assembly should not be called"),
            create=True,
        ):
            payload = workspace_projections.build_workspace_projection()

        self.assertIsInstance(payload, dict)
        self.assertIn("generated_at", payload)
        self.assertIn("tracks", payload)
        self.assertIn("tasks", payload)
        self.assertIn("artifacts", payload)
        self.assertIn("run_audits", payload)


class EnvStoreRetiredFieldTests(unittest.TestCase):
    def test_validate_track_rejects_legacy_artifact_ids_field(self) -> None:
        payload = {
            "id": "track-legacy-field",
            "title": "Legacy Field Track",
            "status": "active",
            "current_buddy": "pm",
            "next_buddy": None,
            "task_ids": [],
            "artifact_ids": ["art-old-link"],
            "summary": "",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        with self.assertRaisesRegex(ValueError, "track.artifact_ids is retired"):
            validate_track(payload)

    def test_validate_artifact_rejects_legacy_track_id_field(self) -> None:
        payload = {
            "id": "art-legacy-field",
            "title": "Legacy Artifact",
            "task_id": "task-dev-legacy",
            "track_id": "track-legacy-field",
            "buddy": "dev",
            "skill_id": "implement-task",
            "source_run_id": "run-legacy-field",
            "summary": "",
            "content": {},
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        with self.assertRaisesRegex(ValueError, "artifact.track_id is retired"):
            validate_artifact(payload)


class RuntimeWriteBoundaryTests(unittest.TestCase):
    def test_repo_root_create_task_requires_runtime_workspace(self) -> None:
        task_id = f"task-dev-write-guard-{uuid.uuid4().hex[:8]}"
        with self.assertRaisesRegex(
            ValueError,
            r"BuddySwitch runtime writes are blocked in the source checkout.*\./buddyswitch-codex start",
        ):
            create_task(
                task_id,
                "Repo Root Guard",
                buddy="dev",
                initial_run_id="run-write-guard",
            )


class ResolveRuntimeTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()
        super().tearDown()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(self._runtime_path(repo_path))

    def test_resolve_context_surface_freezes_public_shape(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(list(payload.keys()), RESOLVE_CONTEXT_RESPONSE_KEY_ORDER)
        self.assertEqual(payload["task_resolution"]["task_id"], payload["task_context"]["task"]["id"])
        self.assertEqual(payload["run_envelope"]["status"], "reserved")
        self.assertIsNone(payload["run_envelope"]["previous_run_id"])
        for field in RESOLVE_CONTEXT_PACKET_ERA_FIELDS:
            self.assertNotIn(field, payload)
        self.assertFalse(_contains_key_recursive(payload, "selected_skill_packet"))

    def test_single_skill_buddy_returns_resolve_context(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(
            list(payload["switch"].keys()),
            ["raw_text", "buddy_id", "demand", "task_id", "track_id"],
        )
        self.assertEqual(payload["switch"]["buddy_id"], "dev")
        self.assertEqual(payload["switch"]["demand"], "Implement the approved onboarding improvements in projects/app")
        self.assertEqual(payload["authority"]["buddy_id"], "dev")
        self.assertIn("permissions", payload["authority"])
        self.assertIsInstance(payload["authority"]["permissions"], list)
        self.assertEqual(list(payload["authority"].keys()), ["buddy_id", "permissions"])
        self.assertIsInstance(payload["inputs"], list)
        self.assertEqual(payload["skills"][0]["id"], "implement-task")
        self.assertEqual(payload["task_resolution"]["mode"], "create")
        self.assertEqual(payload["task_resolution"]["task_id"], payload["task_context"]["task"]["id"])
        self.assertEqual(payload["run_envelope"]["status"], "reserved")
        self.assertEqual(payload["warnings"], [])
        self.assertNotIn("eligible_skills", payload)
        self.assertNotIn("run_instructions", payload)
        card = payload["skills"][0]
        self.assertEqual(card["instruction_path"], "buddyswitch/skills/dev/implement-task/SKILL.md")
        self.assertEqual(card["output_slot"], "implementation-report")
        self.assertEqual(card["input_slots"], ["prd", "task"])
        self.assertNotIn("default_artifact_kind", card)
        self.assertNotIn("auto_summary", card)

    def test_resolve_create_mode_materializes_task_before_persist(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        task_id = payload["task_resolution"]["task_id"]
        self.assertIsInstance(task_id, str)
        self.assertTrue(task_id)
        self._remember(f"buddyswitch/objects/tasks/{task_id}.json")

        stored_task = get_task(task_id)
        self.assertIsNotNone(stored_task)
        self.assertEqual(stored_task["run_ids"], [])
        self.assertIsNone(stored_task["latest_run_id"])

    def test_design_buddy_resolves_shape_prototype_skill(self) -> None:
        payload = switch_runtime.resolve_switch("switch design: Shape the landing-page prototype")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["switch"]["buddy_id"], "design")
        self.assertEqual([skill["id"] for skill in payload["skills"]], ["shape-prototype"])
        self.assertEqual(payload["skills"][0]["output_slot"], "design-handoff")

        task_id = payload["task_resolution"]["task_id"]
        self.assertIsInstance(task_id, str)
        self.assertTrue(task_id)
        self._remember(f"buddyswitch/objects/tasks/{task_id}.json")

    def test_design_buddy_reuses_previous_design_handoff_input(self) -> None:
        create_track("track-design-review", "Design Review")
        self._remember("buddyswitch/objects/tracks/track-design-review.json")

        first_context = switch_runtime.resolve_switch(
            "switch design -> track-design-review: Shape the landing-page prototype"
        )
        first_payload = switch_runtime.persist_skill_result(
            first_context,
            skill_id="shape-prototype",
            result={
                "execution_summary": "Shaped the landing-page prototype and packaged the handoff.",
                "working_notes": ["Focused the first pass on information architecture and CTA flow."],
                "deliverables_or_changed_files": [".sandbox/design/task-design-landing-page/index.html"],
                "artifact_content": {
                    "prototype_kind": "page-map-plus-key-pages",
                    "page_map": ["home", "pricing", "demo-request", "confirmation"],
                    "primary_user_flow": ["home -> demo-request -> confirmation"],
                    "preview": {
                        "sandbox_root": ".sandbox/design/task-design-landing-page",
                        "entry_file": "index.html",
                    },
                    "handoff": {
                        "pm": ["Keep the first CTA above the fold."],
                        "dev": ["Implement hero, proof strip, and CTA flow first."],
                        "test": ["Verify the primary CTA path and top-level navigation labels."],
                    },
                    "open_questions": ["Do enterprise visitors need a separate trust section?"],
                },
            },
        )

        self._remember(first_payload["receipt"]["paths"]["run"])
        self._remember(first_payload["receipt"]["paths"]["task"])
        self._remember(first_payload["receipt"]["paths"]["artifacts"][0])
        self._remember(first_payload["receipt"]["paths"]["track"])

        follow_up = switch_runtime.resolve_switch(
            "switch design -> track-design-review: refine the prototype handoff"
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"]) for item in follow_up["inputs"]],
            [("design-handoff", first_payload["receipt"]["artifact_id"])],
        )

    def test_track_manager_skill_card_omits_output_slot_and_compat_fields(self) -> None:
        payload = switch_runtime.resolve_switch("switch pm: manage the active track")

        self.assertTrue(payload["ok"])
        card = next(card for card in payload["skills"] if card["id"] == "track-manager")
        self.assertFalse(card["produces_artifact"])
        self.assertNotIn("output_slot", card)
        self.assertNotIn("default_artifact_kind", card)
        self.assertNotIn("auto_summary", card)

    def test_multi_skill_market_buddy_returns_no_implicit_skill(self) -> None:
        payload = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["switch"]["buddy_id"], "market")
        self.assertEqual(payload["inputs"], [])
        self.assertNotIn("invocation", payload)
        self.assertNotIn("implicit_skill_id", payload)
        self.assertNotIn("eligible_skills", payload)
        self.assertNotIn("skill_cards", payload)
        self.assertNotIn("track_artifact_index", payload)

        expected_market_skills = [
            "research-scan",
            "pmf-recon",
            "customer-discovery",
            "positioning-copy",
            "channel-discovery",
            "launch-prep",
        ]
        ids = [card["id"] for card in payload["skills"] if isinstance(card, dict) and "id" in card]
        with self.subTest("skills_order"):
            self.assertEqual(ids, expected_market_skills)

        skill_cards_by_id = {
            card["id"]: card for card in payload["skills"] if isinstance(card, dict) and "id" in card
        }
        with self.subTest("research_scan_output_slot"):
            self.assertIn("research-scan", skill_cards_by_id)
            self.assertEqual(skill_cards_by_id.get("research-scan", {}).get("output_slot"), "market-scan")

        with self.subTest("pmf_recon_contract"):
            self.assertIn("pmf-recon", skill_cards_by_id)
            pmf_card = skill_cards_by_id.get("pmf-recon", {})
            self.assertEqual(
                pmf_card.get("instruction_path"),
                "buddyswitch/skills/market/pmf-recon/SKILL.md",
            )
            self.assertEqual(pmf_card.get("output_slot"), "pmf-report")
            self.assertEqual(
                pmf_card.get("input_slots"),
                ["research-question", "links", "prior-artifacts"],
            )
            self.assertEqual(
                pmf_card.get("host_execution"),
                EXPECTED_MARKET_HOST_EXECUTION,
            )
            self.assertEqual(
                pmf_card.get("tool_scope"),
                EXPECTED_MARKET_TOOL_SCOPE,
            )
            self.assertEqual(
                pmf_card.get("host_execution"),
                EXPECTED_MARKET_HOST_EXECUTION,
            )

    def test_pm_skill_card_uses_explicit_market_inputs(self) -> None:
        pm_payload = switch_runtime.resolve_switch(
            "switch pm: Draft the PRD for a validated market opportunity"
        )

        pm_card = next(card for card in pm_payload["skills"] if card["id"] == "write-prd")

        self.assertEqual(
            pm_card["input_slots"],
            [
                "market-scan",
                "pmf-report",
                "customer-discovery",
                "positioning-brief",
                "channel-plan",
                "launch-prep",
                "requirements",
                "track",
            ],
        )
        self.assertEqual(pm_payload["inputs"], [])

    def test_skill_card_uses_package_metadata_for_description_and_objects(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            package_root = Path(temp_dir) / "demo-skill"
            package_root.mkdir()
            (package_root / "skill.toml").write_text(
                textwrap.dedent(
                    """\
                    id = "demo-skill"
                    buddy = "pm"
                    description = "Demo skill package."
                    objects = ["task", "artifact"]
                    produces_artifact = true
                    output_slot = "prd"
                    input_slots = ["research-report"]
                    output_schema = "framework/schemas/pm/write-prd.json"
                    produces = ["prd"]
                    consumes = ["research-report"]
                    side_effect_level = "medium"
                    required_tools = []
                    required_env = []
                    allowed_task_kinds = ["definition"]
                    """
                ),
                encoding="utf-8",
            )
            (package_root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    # demo-skill

                    ## Purpose
                    - Define product scope.

                    ## Use when
                    - The task is about product definition.

                    ## Do not use when
                    - The task is implementation or testing.

                    ## Inputs
                    - Research and scope context.

                    ## Outputs
                    - A structured PRD result.

                    ## Verification
                    - Confirm scope and open questions.

                    ## Examples
                    - `switch pm: define scope`

                    ## Counterexamples
                    - `switch dev: implement scope`

                    ## Gotchas
                    - Keep scope narrow.
                    """
                ),
                encoding="utf-8",
            )
            manifest_path = Path(temp_dir) / "manifest.toml"
            manifest_path.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[adapters]]
                    id = "codex"
                    path = "scripts/codex_router.py"
                    description = "Demo router."

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )

            payload = switch_runtime.resolve_switch("switch pm: define scope", manifest_path=manifest_path)

        self.assertTrue(payload["ok"])
        skill_card = payload["skills"][0]
        self.assertEqual(skill_card["description"], "Demo skill package.")
        self.assertEqual(skill_card["objects"], ["task", "artifact"])
        self.assertNotIn("default_artifact_kind", skill_card)
        self.assertNotIn("auto_summary", skill_card)

    def test_resolve_reuses_explicit_task(self) -> None:
        task = create_task(
            "task-dev-resolve-reuse",
            "Resolve Reuse",
            buddy="dev",
            initial_run_id="run-seed-reuse",
        )
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        payload = switch_runtime.resolve_switch("switch dev(task-dev-resolve-reuse): continue implementation")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_resolution"]["mode"], "reuse")
        self.assertEqual(payload["task_resolution"]["task_id"], "task-dev-resolve-reuse")
        self.assertEqual(payload["task_context"]["task"]["id"], "task-dev-resolve-reuse")

    def test_resolve_rejects_task_buddy_mismatch(self) -> None:
        task = create_task(
            "task-market-forbidden",
            "Market task",
            buddy="market",
            initial_run_id="run-seed-market",
        )
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        with self.assertRaisesRegex(ValueError, "belongs to buddy"):
            switch_runtime.resolve_switch("switch dev(task-market-forbidden): continue implementation")

    def test_resolve_rejects_legacy_markdown_output_requests(self) -> None:
        with self.assertRaisesRegex(ValueError, "Derived markdown outputs are retired"):
            switch_runtime.resolve_switch(
                "switch dev: Implement onboarding and write to artifacts/demo.md"
            )

    def test_resolve_inputs_include_latest_track_artifact_from_history(self) -> None:
        track = create_track("track-index-resolve", "Track Index Resolve")
        task = create_task(
            "task-pm-index-resolve",
            "PM Index Resolve",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-index-resolve",
        )
        first_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd",
            title="PM PRD V1",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-v1",
            summary="First requirement summary.",
            content={"problem": "v1"},
        )
        second_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd-2",
            title="PM PRD V2",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-v2",
            summary="Second requirement summary.",
            content={"problem": "v2"},
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{first_artifact['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{second_artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch dev -> track-index-resolve: continue implementation"
        )

        self.assertEqual(
            [(item["slot"], item["artifact_id"], item["revision"]) for item in payload["inputs"]],
            [("prd", "art-task-pm-index-resolve-prd-2", 2)],
        )
        self.assertNotIn("track_artifact_index", payload)

    def test_resolve_inputs_expose_current_artifacts_by_slot(self) -> None:
        track = create_track("track-index-resolve-slot", "Track Index Resolve Slot")
        dev_task = create_task(
            "task-dev-slot-aware",
            "Dev Slot Aware",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-seed-dev-slot-aware",
        )
        task = create_task(
            "task-pm-index-resolve-slot",
            "PM Index Resolve Slot",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-index-resolve-slot",
        )
        first_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd-r1",
            title="PM PRD V1",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-slot-v1",
            summary="First requirement summary.",
            content={"problem": "v1"},
        )
        second_artifact = create_artifact(
            artifact_id="art-task-pm-index-resolve-prd-r2",
            title="PM PRD V2",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-index-resolve-slot-v2",
            summary="Second requirement summary.",
            content={"problem": "v2"},
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{dev_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{first_artifact['id']}.json")
        self._remember(f"buddyswitch/objects/artifacts/{second_artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch dev(task-dev-slot-aware) -> track-index-resolve-slot: continue implementation"
        )

        self.assertNotIn("track_artifact_index", payload)
        self.assertEqual(
            [(item["slot"], item["artifact_id"], item["revision"]) for item in payload["inputs"]],
            [("prd", "art-task-pm-index-resolve-prd-r2", 2)],
        )
        selected = payload["inputs"][0]
        self.assertEqual(selected["task_id"], "task-pm-index-resolve-slot")
        self.assertEqual(selected["buddy"], "pm")
        self.assertEqual(selected["selection_reason"], "current artifact for required upstream slot")

    def test_resolve_inputs_empty_when_track_has_no_matching_artifacts(self) -> None:
        track = create_track("track-empty-artifacts", "Track Empty Artifacts")
        task = create_task(
            "task-pm-empty-artifacts",
            "PM Empty Artifacts",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-empty-artifacts",
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch dev -> track-empty-artifacts: implement according to current track inputs"
        )

        self.assertTrue(payload["ok"])
        self.assertNotIn("track_artifact_index", payload)
        self.assertEqual(payload["inputs"], [])

    def test_resolve_pm_surfaces_write_prd_selection_for_multi_skill_track_handoff(self) -> None:
        track = create_track("track-pm-market-handoff", "PM Market Handoff")
        market_task = create_task(
            "task-market-pm-handoff",
            "Market PM Handoff",
            buddy="market",
            track_id=track["id"],
            initial_run_id="run-seed-market-pm-handoff",
        )
        market_artifacts = [
            create_artifact(
                artifact_id="art-task-market-pm-handoff-market-scan-r1",
                title="Market Scan PM Handoff",
                buddy="market",
                skill_id="research-scan",
                slot="market-scan",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-market-scan-r1",
                summary="Current market scan for PM handoff.",
                content={"research_question": "What should PM scope next?"},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-pmf-report-r1",
                title="PMF Report PM Handoff",
                buddy="market",
                skill_id="pmf-recon",
                slot="pmf-report",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-pmf-report-r1",
                summary="Current PMF report for PM handoff.",
                content={"conclusion": "Proceed with scoped PM work."},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-customer-discovery-r1",
                title="Customer Discovery PM Handoff",
                buddy="market",
                skill_id="customer-discovery",
                slot="customer-discovery",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-customer-discovery-r1",
                summary="Current customer discovery for PM handoff.",
                content={"recommended_next_step": {"action": "Scope the product surface."}},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-positioning-brief-r1",
                title="Positioning Brief PM Handoff",
                buddy="market",
                skill_id="positioning-copy",
                slot="positioning-brief",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-positioning-brief-r1",
                summary="Current positioning brief for PM handoff.",
                content={"positioning_statement": "Confidence before code."},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-channel-plan-r1",
                title="Channel Plan PM Handoff",
                buddy="market",
                skill_id="channel-discovery",
                slot="channel-plan",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-channel-plan-r1",
                summary="Current channel plan for PM handoff.",
                content={"channels": ["communities"]},
            ),
            create_artifact(
                artifact_id="art-task-market-pm-handoff-launch-prep-r1",
                title="Launch Prep PM Handoff",
                buddy="market",
                skill_id="launch-prep",
                slot="launch-prep",
                task_id=market_task["id"],
                source_run_id="run-market-pm-handoff-launch-prep-r1",
                summary="Current launch prep for PM handoff.",
                content={"launch_goal": {"primary_goal": "Validate demand", "timebox": "14 days"}},
            ),
        ]
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{market_task['id']}.json")
        for artifact in market_artifacts:
            self._remember(f"buddyswitch/objects/artifacts/{artifact['id']}.json")

        payload = switch_runtime.resolve_switch(
            "switch pm -> track-pm-market-handoff: draft the PRD from the active market evidence"
        )

        self.assertEqual(payload["switch"]["buddy_id"], "pm")
        self.assertEqual(payload["task_resolution"]["mode"], "create")
        self.assertEqual(payload["inputs"], [])
        self.assertEqual(
            [card["id"] for card in payload["skills"]],
            ["write-prd", "track-manager"],
        )
        write_prd_skill = next(card for card in payload["skills"] if card["id"] == "write-prd")
        self.assertEqual(
            write_prd_skill["input_slots"],
            [
                "market-scan",
                "pmf-report",
                "customer-discovery",
                "positioning-brief",
                "channel-plan",
                "launch-prep",
                "requirements",
                "track",
            ],
        )
        self.assertNotIn("artifact_selection_by_skill", payload)
        self.assertNotIn("run_instructions_by_skill", payload)
        self.assertNotIn("track_artifact_index", payload)


class ExecutionPreparationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_market_resolve_skills_expose_host_execution_without_packet_surface(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate whether indie developers need a lightweight demand-validation workflow before building"
        )

        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["inputs"], [])
        self.assertNotIn("skill_cards", resolved)
        self.assertFalse(_contains_key_recursive(resolved, "selected_skill_packet"))

        skills_by_id = {card["id"]: card for card in resolved["skills"]}
        expected_market_skills = [
            "research-scan",
            "pmf-recon",
            "customer-discovery",
            "positioning-copy",
            "channel-discovery",
            "launch-prep",
        ]
        self.assertEqual(sorted(skills_by_id.keys()), sorted(expected_market_skills))
        for skill_id in expected_market_skills:
            with self.subTest(skill_id=skill_id):
                card = skills_by_id[skill_id]
                self.assertEqual(card["host_execution"], EXPECTED_MARKET_HOST_EXECUTION)
                self.assertEqual(card["tool_scope"], EXPECTED_MARKET_TOOL_SCOPE)


class WorkspaceDataTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()
        super().tearDown()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(self._runtime_path(repo_path))

    def test_artifact_view_uses_object_path_only(self) -> None:
        artifact = {
            "id": "art-task-centric",
            "title": "Task-Centric Artifact",
            "task_id": "task-dev-one",
            "buddy": "dev",
            "skill_id": "implement-task",
            "slot": "implementation-report",
            "revision": 1,
            "supersedes_artifact_id": None,
            "is_current": True,
            "source_run_id": "run-test",
            "summary": "Canonical summary",
            "content": {"task_summary": "ok"},
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }

        view = workspace_projections.build_artifact_view(artifact)
        self.assertFalse(view["missing"])
        self.assertEqual(view["object_path"], "buddyswitch/objects/artifacts/art-task-centric.json")

    def test_task_view_projects_current_artifacts_by_slot(self) -> None:
        task = {
            "id": "task-dev-one",
            "buddy": "dev",
            "title": "Dev Task",
            "status": "active",
            "track_id": "track-dev-one",
            "artifact_ids": ["art-prd", "art-impl"],
            "artifact_slots": {
                "prd": {"current_artifact_id": "art-prd", "revision_count": 2},
                "implementation-report": {"current_artifact_id": "art-impl", "revision_count": 1},
            },
            "run_ids": ["run-seed"],
            "latest_run_id": "run-seed",
            "summary": "Task summary",
            "created_at": "2026-04-12T10:00:00+08:00",
            "updated_at": "2026-04-12T10:00:00+08:00",
        }
        artifact_map = {
            "art-prd": {
                "id": "art-prd",
                "slot": "prd",
                "updated_at": "2026-04-12T10:05:00+08:00",
            },
            "art-impl": {
                "id": "art-impl",
                "slot": "implementation-report",
                "updated_at": "2026-04-12T10:06:00+08:00",
            },
        }

        view = workspace_projections.build_task_view(task, artifact_map)

        self.assertEqual(sorted(view["current_artifacts"].keys()), ["implementation-report", "prd"])
        self.assertEqual(view["current_artifacts"]["prd"]["id"], "art-prd")
        self.assertNotIn("latest_artifact", view)

    def test_projection_build_track_views_prefers_latest_task_and_artifact_updates(self) -> None:
        tracks = [
            {
                "id": "track-dev-one",
                "title": "Track One",
                "status": "active",
                "current_buddy": "dev",
                "next_buddy": "test",
                "task_ids": ["task-dev-one", "task-missing"],
                "summary": "",
                "updated_at": "2026-04-12T10:00:00+08:00",
            }
        ]
        task_map = {
            "task-dev-one": {
                "id": "task-dev-one",
                "updated_at": "2026-04-12T10:10:00+08:00",
                "current_artifacts": {
                    "implementation-report": {
                        "id": "art-impl",
                        "updated_at": "2026-04-12T10:20:00+08:00",
                    }
                },
            }
        }
        rows = workspace_projections.build_track_views(tracks, task_map, artifact_map={})

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["updated_at"], "2026-04-12T10:20:00+08:00")
        self.assertEqual(rows[0]["missing_task_ids"], ["task-missing"])

    def test_build_workspace_projection_exposes_standalone_tasks(self) -> None:
        track = create_track("track-workspace-linked", "Linked Track")
        tracked_task = create_task(
            "task-dev-workspace-linked",
            "Tracked Task",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-seed-workspace-linked",
        )
        standalone_task = create_task(
            "task-market-standalone-workspace",
            "Standalone Market Task",
            buddy="market",
            initial_run_id="run-seed-standalone-workspace",
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{tracked_task['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{standalone_task['id']}.json")

        payload = workspace_projections.build_workspace_projection()

        self.assertIn("standalone_tasks", payload)
        standalone_ids = [task["id"] for task in payload["standalone_tasks"]]
        self.assertIn("task-market-standalone-workspace", standalone_ids)
        self.assertNotIn("task-dev-workspace-linked", standalone_ids)

    def test_scan_run_audits_includes_reference_switches(self) -> None:
        run_id = f"run-workspace-audit-{uuid.uuid4().hex[:8]}"
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "timestamp": "2026-04-12T20:10:00+08:00",
                    "switch": {
                        "buddy": "dev",
                        "task_id": "task-dev-audit-123abc",
                        "track_id": "track-audit",
                        "demand": "implement scope",
                    },
                    "resolved_task_id": "task-dev-audit-123abc",
                    "effective_track_id": "track-audit",
                    "skill_id": "implement-task",
                    "artifact_ids": ["art-audit"],
                    "task_title": "Audit Task Title",
                    "track_title": "Audit Track Title",
                    "reference_switches": {
                        "continue_current_task": "switch dev(task-dev-audit-123abc): <demand>"
                    },
                    "related_run_ids": ["run-prior-a", "run-prior-b"],
                    "recommended_switch": "switch dev(task-dev-audit-123abc): <demand>",
                    "execution_summary": "ok",
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._remember(f"buddyswitch/content/runs/{run_id}.json")

        rows = workspace_projections.scan_run_audits()
        row = next((item for item in rows if item.get("run_id") == run_id), None)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["task_title"], "Audit Task Title")
        self.assertEqual(row["track_title"], "Audit Track Title")
        self.assertEqual(
            row["reference_switches"]["continue_current_task"],
            "switch dev(task-dev-audit-123abc): <demand>",
        )
        self.assertEqual(row["related_run_ids"], ["run-prior-a", "run-prior-b"])
        self.assertEqual(row["recommended_switch"], "switch dev(task-dev-audit-123abc): <demand>")
        self.assertNotIn("suggested_next_switch", row)


class PersistRuntimeTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.created_paths: list[Path] = []

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.exists():
                path.unlink()
        super().tearDown()

    def _remember(self, repo_path: str) -> None:
        self.created_paths.append(self._runtime_path(repo_path))

    def _remember_persisted_paths(self, payload: dict[str, object]) -> None:
        paths = payload.get("paths")
        if not isinstance(paths, dict):
            receipt = payload.get("receipt")
            if isinstance(receipt, dict):
                candidate_paths = receipt.get("paths")
                if isinstance(candidate_paths, dict):
                    paths = candidate_paths
        if not isinstance(paths, dict):
            return
        run_path = paths.get("run")
        task_path = paths.get("task")
        artifact_paths = paths.get("artifacts")
        track_path = paths.get("track")
        if isinstance(run_path, str):
            self._remember(run_path)
        if isinstance(task_path, str):
            self._remember(task_path)
        if isinstance(track_path, str):
            self._remember(track_path)
        if isinstance(artifact_paths, list):
            for item in artifact_paths:
                if isinstance(item, str):
                    self._remember(item)

    def _persist_receipt(
        self,
        context: dict[str, object],
        *,
        skill_id: str,
        result: dict[str, object],
    ) -> dict[str, object]:
        payload = switch_runtime.persist_skill_result(
            context,
            skill_id=skill_id,
            result=result,
        )
        self.assertEqual(list(payload.keys()), PERSIST_SKILL_RESULT_RESPONSE_KEY_ORDER)
        for field in PERSIST_SKILL_RESULT_PACKET_ERA_FIELDS:
            self.assertNotIn(field, payload)
        receipt = payload.get("receipt")
        self.assertIsInstance(receipt, dict)
        assert isinstance(receipt, dict)
        return receipt

    def _assert_generated_task_id(self, task_id: object, buddy: str) -> None:
        self.assertIsInstance(task_id, str)
        assert isinstance(task_id, str)
        prefix = f"task-{buddy}-"
        self.assertTrue(task_id.startswith(prefix))
        self.assertGreater(len(task_id), len(prefix))
        require_id(task_id, "task id")

    def _artifact_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": ["Scoped the edits to onboarding CTA behavior."],
            "deliverables_or_changed_files": ["projects/app/src/example.ts"],
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": ["projects/app/src/example.ts"],
                "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
                "verification_runs": [{"command": "npm test", "result": "passed", "notes": "Targeted unit coverage."}],
                "known_limitations": ["No production build was executed in this test."],
            },
        }

    def _design_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Shaped the landing-page prototype and packaged the handoff.",
            "working_notes": ["Focused the first pass on information architecture and CTA flow."],
            "deliverables_or_changed_files": [".sandbox/design/task-design-landing-page/index.html"],
            "artifact_content": {
                "prototype_kind": "page-map-plus-key-pages",
                "page_map": ["home", "pricing", "demo-request", "confirmation"],
                "primary_user_flow": ["home -> demo-request -> confirmation"],
                "preview": {
                    "sandbox_root": ".sandbox/design/task-design-landing-page",
                    "entry_file": "index.html",
                },
                "handoff": {
                    "pm": ["Keep the first CTA above the fold."],
                    "dev": ["Implement hero, proof strip, and CTA flow first."],
                    "test": ["Verify the primary CTA path and top-level navigation labels."],
                },
                "open_questions": ["Do enterprise visitors need a separate trust section?"],
            },
        }

    def _market_evidence(
        self,
        *,
        source_id: str,
        url: str,
        source_type: str,
        accessed_at: str,
        claim_excerpt: str,
        page_title: str,
        query_or_filter_used: str,
        interaction_steps_summary: str,
        screenshot_ref_or_snapshot_ref: str,
        auth_state: str = "public",
    ) -> dict[str, str]:
        return {
            "source_id": source_id,
            "url": url,
            "source_type": source_type,
            "accessed_at": accessed_at,
            "claim_excerpt": claim_excerpt,
            "page_title": page_title,
            "auth_state": auth_state,
            "query_or_filter_used": query_or_filter_used,
            "interaction_steps_summary": interaction_steps_summary,
            "screenshot_ref_or_snapshot_ref": screenshot_ref_or_snapshot_ref,
        }

    def _pmf_recon_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Completed a narrow PMF recon pass for the idea.",
            "working_notes": ["Focused on evidence-backed pain signals only."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Do indie developers show credible demand for AI companion live spaces?",
                "research_strategy": {
                    "depth": "quick",
                    "rationale": "Cover the new persist path with a minimal valid payload.",
                    "collection_mode": "Targeted secondary research",
                    "initial_hypotheses": ["Developers struggle to validate demand before building."],
                    "source_category_targets": ["forums", "founder communities"],
                },
                "channel_plan": ["Founder forums", "Indie hacker communities"],
                "iteration_log": [
                    {
                        "round": 1,
                        "focus": "Demand discovery",
                        "sources_checked": ["https://example.com/source-1"],
                        "evidence_captured": "Found repeated mentions of weak feedback loops.",
                        "synthesis": "Pain centers on confidence in what to build next.",
                        "next_adjustment": "Probe willingness to try lightweight validation tools.",
                    }
                ],
                "evidence": [
                    {
                        **self._market_evidence(
                            source_id="src-1",
                            url="https://example.com/source-1",
                            source_type="forum-thread",
                            accessed_at="2026-04-14T10:00:00+08:00",
                            claim_excerpt="I keep building without enough real demand signals.",
                            page_title="Founders discussing weak validation loops",
                            query_or_filter_used="site search: demand validation founders",
                            interaction_steps_summary="Opened thread, expanded replies, and captured the clearest demand-validation complaint.",
                            screenshot_ref_or_snapshot_ref="snapshot://pmf-recon-src-1",
                        ),
                        "segment": "indie developers",
                        "pain_category": "demand-validation",
                        "confidence": "medium",
                    }
                ],
                "source_traceability": [
                    {
                        "conclusion": "Early demand validation remains a recurring pain point.",
                        "source_ids": ["src-1"],
                    }
                ],
                "assumptions_used": ["Public founder discussions are directionally useful for this check."],
                "candidate_icps": [
                    {
                        "segment": "Indie developers launching early products",
                        "pain_summary": "Need faster feedback on whether a concept is worth pursuing.",
                        "why_now_or_why_this_segment": "They operate with limited time and budget.",
                    }
                ],
                "strongest_pain_signals": ["Low confidence in what to build", "Weak user feedback volume"],
                "existing_alternatives": [
                    {
                        "name": "Manual interviews",
                        "type": "service",
                        "gaps": ["Slow to schedule", "Hard to maintain cadence"],
                    }
                ],
                "why_current_solutions_fall_short": ["They are too manual for continuous lightweight validation."],
                "pmf_confidence": {
                    "level": "medium",
                    "rationale": "Evidence suggests real pain, but paid demand remains unproven.",
                },
                "recommended_next_step": {
                    "action": "interviews",
                    "rationale": "Direct interviews are the fastest next step to validate urgency.",
                },
                "suggested_interview_angles": ["Current validation workflow", "Signals that would change roadmap decisions"],
                "risks_and_unknowns": ["Willingness to pay is still unclear."],
                "conclusion": "There is enough evidence to continue with direct customer discovery.",
            },
        }

    def _customer_discovery_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Prepared a customer discovery brief from public market evidence.",
            "working_notes": ["Kept the interview scope narrow and evidence-backed."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Which indie developers should be prioritized for early interviews?",
                "target_segments": [
                    {
                        "segment": "Indie developers validating new SaaS ideas",
                        "pain_context": "They lack confidence in what to validate before building.",
                        "why_this_segment": "They can act quickly on structured interview plans.",
                    }
                ],
                "interview_goals": [
                    "Validate the most urgent demand-validation pain",
                    "Learn how developers currently gather customer signals",
                ],
                "recruiting_criteria": {
                    "must_have": ["Recently evaluated or launched a new product idea"],
                    "nice_to_have": ["Shares validation lessons in public communities"],
                    "exclude_if": ["Has no recent product-validation experience"],
                },
                "interview_guide": [
                    {
                        "section": "Current workflow",
                        "goal": "Understand how validation happens today.",
                        "prompts": ["Walk me through the last time you validated a product idea."],
                    }
                ],
                "hypotheses_to_test": ["Developers default to ad-hoc validation because structured options feel too heavy."],
                "evidence": [
                    self._market_evidence(
                        source_id="src-disc-1",
                        url="https://example.com/discovery-source",
                        source_type="forum-thread",
                        accessed_at="2026-04-15T10:00:00+08:00",
                        claim_excerpt="I keep guessing what users want because I do not have a repeatable discovery process.",
                        page_title="Founder thread on repeatable discovery habits",
                        query_or_filter_used="forum search: repeatable discovery process",
                        interaction_steps_summary="Opened discovery thread, read the top responses, and captured the repeated process complaint.",
                        screenshot_ref_or_snapshot_ref="snapshot://customer-discovery-src-disc-1",
                    )
                ],
                "source_traceability": [
                    {
                        "conclusion": "Interview prompts should focus on current validation habits before solution reactions.",
                        "source_ids": ["src-disc-1"],
                    }
                ],
                "patterns_and_insights": ["Discovery pain is strongest around repeatability and prioritization."],
                "risks_and_unknowns": ["Recruiting may skew toward public builders rather than quieter but similar buyers."],
                "recommended_next_step": {
                    "action": "Recruit five interviews with recent indie launches.",
                    "rationale": "This is enough to test whether the workflow pain is urgent and repeated.",
                },
                "conclusion": "The next customer discovery round should center on repeatable validation habits and switching triggers.",
            },
        }

    def _positioning_copy_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Converted market evidence into a positioning brief for first-touch messaging.",
            "working_notes": ["Kept the message house tied to observed pains and alternatives."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "What positioning should an early demand-validation tool use for indie developers?",
                "target_audience": {
                    "primary": "Indie developers validating SaaS ideas",
                    "context": "They are juggling build decisions with weak user feedback.",
                    "trigger": "They need faster confidence before committing to development work.",
                },
                "status_quo_and_alternatives": [
                    {
                        "option": "Manual interviews and community posts",
                        "type": "workflow",
                        "why_it_persists": "It is familiar and low-cost to start.",
                        "limitations": ["Feedback arrives slowly", "Signals are hard to compare over time"],
                    }
                ],
                "differentiated_capabilities": ["Turns demand signals into a repeatable evidence log", "Keeps early validation lightweight for solo builders"],
                "value_claims": [
                    {
                        "claim": "Validate product ideas with a lighter process than manual outreach alone.",
                        "audience_value": "Developers get faster confidence about what to test next.",
                        "evidence_basis": ["src-pos-1"],
                    }
                ],
                "positioning_statement": "For indie developers validating new SaaS ideas, BuddySwitch keeps demand discovery structured without turning it into a heavy research project.",
                "message_house": {
                    "core_message": "Structured demand discovery for builders who move fast.",
                    "supporting_points": ["Capture repeatable evidence, not vague impressions", "Focus on the sharpest pain before building"],
                },
                "homepage_angles": [
                    {
                        "angle": "Confidence before code",
                        "headline_direction": "Know what is worth building before you build it.",
                        "why_it_might_work": "It speaks directly to the repeated uncertainty found in public founder discussions.",
                    }
                ],
                "evidence": [
                    self._market_evidence(
                        source_id="src-pos-1",
                        url="https://example.com/positioning-source",
                        source_type="forum-thread",
                        accessed_at="2026-04-15T10:10:00+08:00",
                        claim_excerpt="I need clearer proof of demand before I spend another weekend building.",
                        page_title="Founder post about confidence before building",
                        query_or_filter_used="community filter: validation confidence",
                        interaction_steps_summary="Filtered to recent founder posts and captured the strongest confidence-before-building quote.",
                        screenshot_ref_or_snapshot_ref="snapshot://positioning-src-pos-1",
                    )
                ],
                "source_traceability": [
                    {
                        "conclusion": "First-touch copy should emphasize confidence and speed rather than feature depth.",
                        "source_ids": ["src-pos-1"],
                    }
                ],
                "risks_and_unknowns": ["Positioning still assumes confidence is a stronger hook than speed for this segment."],
                "conclusion": "The strongest positioning angle is structured confidence before development effort.",
            },
        }

    def _channel_discovery_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Ranked believable early channels for the first market experiment.",
            "working_notes": ["Kept the experiment plan constrained to one primary and one backup channel."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "Which acquisition channel should be tested first for this indie developer audience?",
                "candidate_channels": [
                    {
                        "channel": "Founder communities",
                        "why_it_is_plausible": "The target audience already discusses validation pain there.",
                        "constraints": ["Requires direct founder participation"],
                    }
                ],
                "selection_criteria": ["Reach the right builders quickly", "Earn trust through context-rich posts"],
                "channel_scores": [
                    {
                        "channel": "Founder communities",
                        "scores": {
                            "reachability": 4,
                            "credibility": 4,
                            "speed": 4,
                            "cost": 5,
                            "signal_quality": 4,
                        },
                        "summary": "Strong fit because the audience already shares validation pain openly in these spaces.",
                    }
                ],
                "recommended_primary_channel": {
                    "channel": "Founder communities",
                    "why": "It offers the best balance of trust, speed, and direct feedback for this audience.",
                    "preconditions": ["Prepare a concrete founder post with one clear CTA"],
                },
                "recommended_secondary_channel": {
                    "channel": "Indie developer newsletters",
                    "why": "Useful backup if community reach stalls after the first test.",
                    "preconditions": ["Find newsletter operators who already cover validation workflows"],
                },
                "experiment_plan": {
                    "goal": "Generate qualified conversations about current validation workflow pain.",
                    "offer": "A lightweight demand-discovery workflow preview.",
                    "audience": "Indie developers validating new SaaS ideas",
                    "steps": ["Publish a founder post", "Collect replies", "Follow up with respondents"],
                    "timebox": "7 days",
                    "success_signal": "At least five qualified responses from builders in scope",
                },
                "kill_signals": ["No qualified replies after two well-placed posts", "Replies focus on unrelated founder problems"],
                "evidence": [
                    self._market_evidence(
                        source_id="src-chan-1",
                        url="https://example.com/channel-source",
                        source_type="community-post",
                        accessed_at="2026-04-15T10:20:00+08:00",
                        claim_excerpt="Founders here swap validation tactics and ask for concrete feedback loops all the time.",
                        page_title="Community thread sharing validation tactics",
                        query_or_filter_used="community browse: validation workflow",
                        interaction_steps_summary="Opened the community thread, compared reply volume, and noted repeated requests for feedback loops.",
                        screenshot_ref_or_snapshot_ref="snapshot://channel-src-chan-1",
                    )
                ],
                "source_traceability": [
                    {
                        "conclusion": "Founder communities are the most credible first channel because they already host the target pain discussion.",
                        "source_ids": ["src-chan-1"],
                    }
                ],
                "risks_and_unknowns": ["The same audience may saturate quickly if the message is too generic."],
                "conclusion": "Start with founder communities and keep a newsletter outreach backup ready.",
            },
        }

    def _launch_prep_result(self) -> dict[str, object]:
        return {
            "execution_summary": "Prepared a launch brief for the first feedback-oriented release.",
            "working_notes": ["Kept the feedback loop explicit before any broader announcement."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "research_question": "How should the first launch be staged to maximize useful feedback?",
                "launch_goal": {
                    "primary_goal": "Collect qualified feedback from early indie developer prospects.",
                    "timebox": "10 days",
                    "secondary_goal": "Test whether the positioning angle drives replies.",
                },
                "target_audience": {
                    "primary": "Indie developers validating SaaS ideas",
                    "why_now": "They are already searching for faster ways to validate before building.",
                    "reach_notes": "Reach them through founder communities and direct follow-up threads.",
                },
                "selected_channel": {
                    "channel": "Founder communities",
                    "reason": "This is where the target audience already discusses validation pain openly.",
                    "constraints": ["Needs concise founder-led copy and a manual reply workflow"],
                },
                "launch_assets": [
                    {
                        "asset": "Validation landing page",
                        "purpose": "Explain the workflow and collect interested replies.",
                        "owner": "founder",
                        "notes": "Keep the CTA focused on feedback, not signups alone.",
                    }
                ],
                "instrumentation_plan": {
                    "signals_to_track": ["Replies", "Qualified conversations", "Landing page CTA clicks"],
                    "capture_method": "Manual tracking sheet with daily updates",
                    "review_cadence": "Daily during the first 10 days",
                },
                "feedback_collection_plan": {
                    "collection_methods": ["Reply form", "Direct email follow-up"],
                    "follow_up_path": "Invite qualified responders into short follow-up calls",
                    "response_owner": "founder",
                },
                "success_signals": ["Five qualified conversations", "Consistent resonance with the confidence-before-code angle"],
                "failure_signals": ["Traffic without replies", "Replies that do not describe the target pain"],
                "evidence": [
                    self._market_evidence(
                        source_id="src-launch-1",
                        url="https://example.com/launch-source",
                        source_type="community-post",
                        accessed_at="2026-04-15T10:30:00+08:00",
                        claim_excerpt="Founders respond when the ask is specific and the feedback loop is obvious.",
                        page_title="Launch thread showing response patterns",
                        query_or_filter_used="community sort: top launch discussions",
                        interaction_steps_summary="Reviewed launch discussion patterns and captured the clearest response-shape quote.",
                        screenshot_ref_or_snapshot_ref="snapshot://launch-src-launch-1",
                    )
                ],
                "source_traceability": [
                    {
                        "conclusion": "The launch should lead with a narrow feedback ask and an explicit follow-up path.",
                        "source_ids": ["src-launch-1"],
                    }
                ],
                "risks_and_unknowns": ["The founder may not have enough time to sustain fast follow-up without a strict daily cadence."],
                "conclusion": "A narrow, feedback-led launch is the right first release shape for this market test.",
            },
        }

    def test_persist_skill_result_surface_freezes_public_shape(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        payload = switch_runtime.persist_skill_result(
            resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(list(payload.keys()), PERSIST_SKILL_RESULT_RESPONSE_KEY_ORDER)
        self.assertEqual(payload["receipt"]["run_id"], resolved["run_envelope"]["run_id"])
        self.assertEqual(
            payload["refreshed_context"]["run_envelope"]["previous_run_id"],
            payload["receipt"]["run_id"],
        )
        self.assertEqual(payload["refreshed_context"]["run_envelope"]["status"], "reserved")
        for field in PERSIST_SKILL_RESULT_PACKET_ERA_FIELDS:
            self.assertNotIn(field, payload)

    def test_persist_skill_result_re_resolves_skill_definition_from_manifest(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        tampered_context = deepcopy(resolved)
        tampered_context["skills"][0]["output_schema"] = "framework/schemas/pm/write-prd.json"

        payload = switch_runtime.persist_skill_result(
            tampered_context,
            skill_id="implement-task",
            result=self._artifact_result(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["receipt"]["skill_id"], "implement-task")

    def test_design_persist_creates_design_handoff_artifact(self) -> None:
        context = switch_runtime.resolve_switch("switch design: Shape the landing-page prototype")

        payload = switch_runtime.persist_skill_result(
            context,
            skill_id="shape-prototype",
            result=self._design_result(),
        )

        self._remember(payload["receipt"]["paths"]["run"])
        self._remember(payload["receipt"]["paths"]["task"])
        self._remember(payload["receipt"]["paths"]["artifacts"][0])

        artifact_json = json.loads(
            self._runtime_path(payload["receipt"]["paths"]["artifacts"][0]).read_text(encoding="utf-8")
        )

        self.assertEqual(payload["receipt"]["skill_id"], "shape-prototype")
        self.assertEqual(artifact_json["buddy"], "design")
        self.assertEqual(artifact_json["slot"], "design-handoff")
        self.assertEqual(artifact_json["source_run_id"], payload["receipt"]["run_id"])

    def test_persist_skill_result_rejects_stale_context_revision(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        stale_context = deepcopy(resolved)
        stale_context["context_revision"] = "ctx-stale"

        with self.assertRaisesRegex(ValueError, "context_revision"):
            switch_runtime.persist_skill_result(
                stale_context,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

    def test_track_manager_schema_rejects_read_and_list_actions(self) -> None:
        schema = json.loads((ROOT / "framework/schemas/pm/track-manager.json").read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["track_operation"]["properties"]["action"]["enum"],
            ["create", "update", "advance", "archive"],
        )

        for action in ("read", "list"):
            resolved = switch_runtime.resolve_switch("switch pm: manage the active track")
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "result payload failed schema validation"):
                    switch_runtime.persist_skill_result(
                        resolved,
                        skill_id="track-manager",
                        result={
                            "execution_summary": f"Tried to {action} tracks.",
                            "working_notes": [],
                            "deliverables_or_changed_files": [],
                            "track_operation": {
                                "action": action,
                                "track_id": "track-schema-action-test",
                            },
                        },
                    )

    def test_persist_skill_result_rejects_tampered_buddy_without_writes(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        tampered_context = deepcopy(resolved)
        tampered_context["buddy"]["id"] = "pm"
        tampered_context["switch"]["buddy_id"] = "pm"
        tampered_context["switch"]["buddy"] = "pm"

        task_id = resolved["task_context"]["task"]["id"]
        task_path = self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        track_dir = self._runtime_path("buddyswitch/objects/tracks")
        before_task_contents = task_path.read_text(encoding="utf-8")
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }
        before_track_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in track_dir.glob("track-*.json")
        }

        with self.assertRaisesRegex(ValueError, "buddy"):
            switch_runtime.persist_skill_result(
                tampered_context,
                skill_id="track-manager",
                result={
                    "execution_summary": "Reviewed track state without mutating it.",
                    "working_notes": ["Validation should fail before any runtime writes."],
                    "deliverables_or_changed_files": [],
                    "track_operation": {"action": "list"},
                },
            )

        self.assertEqual(task_path.read_text(encoding="utf-8"), before_task_contents)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in track_dir.glob("track-*.json")
            },
            before_track_contents,
        )

    def test_persist_skill_result_rejects_tampered_track_id_even_with_recomputed_fingerprint(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        create_track("track-tampered-target", "Tampered Target")
        self._remember("buddyswitch/objects/tracks/track-tampered-target.json")

        tampered_context = deepcopy(resolved)
        tampered_context["switch"]["track_id"] = "track-tampered-target"
        tampered_context["run_envelope"]["switch_fingerprint"] = switch_runtime._derive_switch_fingerprint(  # type: ignore[attr-defined]
            tampered_context["switch"]
        )

        task_id = resolved["task_context"]["task"]["id"]
        task_path = self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        track_dir = self._runtime_path("buddyswitch/objects/tracks")
        before_task_contents = task_path.read_text(encoding="utf-8")
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }
        before_track_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in track_dir.glob("track-*.json")
        }

        with self.assertRaisesRegex(ValueError, "reserved envelope"):
            switch_runtime.persist_skill_result(
                tampered_context,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

        self.assertEqual(task_path.read_text(encoding="utf-8"), before_task_contents)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in track_dir.glob("track-*.json")
            },
            before_track_contents,
        )

    def test_persist_skill_result_rejects_tampered_demand_even_with_recomputed_fingerprint(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        tampered_context = deepcopy(resolved)
        tampered_context["switch"]["demand"] = "Ship a completely different demand without re-resolving."
        tampered_context["run_envelope"]["switch_fingerprint"] = switch_runtime._derive_switch_fingerprint(  # type: ignore[attr-defined]
            tampered_context["switch"]
        )

        task_id = resolved["task_context"]["task"]["id"]
        task_path = self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_task_contents = task_path.read_text(encoding="utf-8")
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }

        with self.assertRaisesRegex(ValueError, "reserved envelope"):
            switch_runtime.persist_skill_result(
                tampered_context,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

        self.assertEqual(task_path.read_text(encoding="utf-8"), before_task_contents)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )

    def test_persist_skill_result_rejects_reused_reserved_run_id_without_writes(self) -> None:
        first_resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        first_payload = switch_runtime.persist_skill_result(
            first_resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember(first_payload["receipt"]["paths"]["run"])
        self._remember(first_payload["receipt"]["paths"]["task"])
        self._remember(first_payload["receipt"]["paths"]["artifacts"][0])

        second_resolved = switch_runtime.resolve_switch(
            "switch dev: Refine the onboarding analytics instrumentation"
        )
        tampered_context = deepcopy(second_resolved)
        tampered_context["run_envelope"]["run_id"] = first_payload["receipt"]["run_id"]

        second_task_id = second_resolved["task_context"]["task"]["id"]
        second_task_path = self._runtime_path(f"buddyswitch/objects/tasks/{second_task_id}.json")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_second_task_contents = second_task_path.read_text(encoding="utf-8")
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }

        with self.assertRaisesRegex(ValueError, "run_id already exists"):
            switch_runtime.persist_skill_result(
                tampered_context,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

        self.assertEqual(second_task_path.read_text(encoding="utf-8"), before_second_task_contents)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )

    def test_derive_cli_persist_skill_id_returns_only_skill_from_context(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        skill_id = switch_runtime._derive_cli_persist_skill_id(  # type: ignore[attr-defined]
            resolved,
            requested_skill_id=None,
        )

        self.assertEqual(skill_id, "implement-task")

    def test_derive_cli_persist_skill_id_rejects_unspecified_multi_skill_context(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )

        with self.assertRaisesRegex(
            ValueError,
            "skill_id is required unless resolve_context exposes exactly one available skill",
        ):
            switch_runtime._derive_cli_persist_skill_id(  # type: ignore[attr-defined]
                resolved,
                requested_skill_id=None,
            )

    def test_persist_creates_task_and_run_bound_artifact(self) -> None:
        resolved = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
        receipt = self._persist_receipt(
            resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )

        self.assertEqual(receipt["skill_id"], "implement-task")
        self._assert_generated_task_id(receipt["task_id"], buddy="dev")
        self.assertEqual(receipt["artifact_ids"], [receipt["artifact_id"]])
        self.assertIn("task_title", receipt)
        self.assertIsNone(receipt["track_title"])
        self.assertIn("reference_switches", receipt)
        self.assertEqual(
            receipt["reference_switches"]["continue_current_task"],
            f"switch dev({receipt['task_id']}): <demand>",
        )
        self.assertEqual(receipt["related_run_ids"], [])
        self.assertEqual(receipt["recommended_switch"], receipt["reference_switches"]["continue_current_task"])
        self._remember_persisted_paths(receipt)

        artifact_json = json.loads(self._runtime_path(receipt["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
        task_json = json.loads(self._runtime_path(receipt["paths"]["task"]).read_text(encoding="utf-8"))
        run_json = json.loads(self._runtime_path(receipt["paths"]["run"]).read_text(encoding="utf-8"))

        self.assertEqual(artifact_json["task_id"], receipt["task_id"])
        self.assertEqual(artifact_json["source_run_id"], receipt["run_id"])
        self.assertIn(receipt["run_id"], task_json["run_ids"])
        self.assertNotIn("latest_artifact_id", task_json)
        self.assertEqual(
            task_json["artifact_slots"][artifact_json["slot"]]["current_artifact_id"],
            receipt["artifact_id"],
        )
        self.assertEqual(run_json["resolved_task_id"], receipt["task_id"])
        self.assertEqual(run_json["artifact_ids"], [receipt["artifact_id"]])
        self.assertEqual(run_json["switch"]["demand"], resolved["switch"]["demand"])
        self.assertEqual(run_json["task_title"], receipt["task_title"])
        self.assertEqual(run_json["track_title"], receipt["track_title"])
        self.assertEqual(run_json["reference_switches"], receipt["reference_switches"])
        self.assertEqual(run_json["related_run_ids"], receipt["related_run_ids"])
        self.assertEqual(run_json["recommended_switch"], receipt["recommended_switch"])
        self.assertNotIn("suggested_next_switch", run_json)
        self.assertNotIn("artifact_content", run_json)
        self.assertFalse(
            switch_runtime._reserved_run_path(receipt["run_id"]).exists()  # type: ignore[attr-defined]
        )

    def test_persist_uses_reserved_run_id_from_resolve_context(self) -> None:
        resolved = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
        reserved_run_id = resolved["run_envelope"]["run_id"]

        receipt = self._persist_receipt(
            resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(receipt)

        self.assertEqual(receipt["run_id"], reserved_run_id)

    def test_persist_rejects_reused_reserved_run_id_without_writes(self) -> None:
        first_resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        first_payload = self._persist_receipt(
            first_resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(first_payload)

        second_resolved = switch_runtime.resolve_switch(
            "switch dev: Refine the onboarding analytics instrumentation"
        )
        tampered_resolved = deepcopy(second_resolved)
        tampered_resolved["run_envelope"]["run_id"] = first_payload["run_id"]

        second_task_id = second_resolved["task_context"]["task"]["id"]
        second_task_path = self._runtime_path(f"buddyswitch/objects/tasks/{second_task_id}.json")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_second_task_contents = second_task_path.read_text(encoding="utf-8")
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }

        with self.assertRaisesRegex(ValueError, "run_id already exists"):
            switch_runtime.persist_skill_result(
                tampered_resolved,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

        self.assertEqual(second_task_path.read_text(encoding="utf-8"), before_second_task_contents)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )

    def test_persist_multi_skill_market_requires_explicit_skill_id(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )
        task_dir = self._runtime_path("buddyswitch/objects/tasks")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        before_tasks = {path.name for path in task_dir.glob("task-*.json")}
        before_artifacts = {path.name for path in artifact_dir.glob("art-*.json")}
        before_runs = {path.name for path in run_dir.glob("run-*.json")}
        before_task_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in task_dir.glob("task-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }

        with self.assertRaisesRegex(
            ValueError,
            "skill_id is required",
        ):
            switch_runtime.persist_skill_result(
                resolved,
                skill_id="",
                result=self._pmf_recon_result(),
            )

        self.assertEqual({path.name for path in task_dir.glob("task-*.json")}, before_tasks)
        self.assertEqual({path.name for path in artifact_dir.glob("art-*.json")}, before_artifacts)
        self.assertEqual({path.name for path in run_dir.glob("run-*.json")}, before_runs)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in task_dir.glob("task-*.json")
            },
            before_task_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )

    def test_persist_multi_skill_market_with_pmf_recon_persists_run_bound_artifact(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate an AI tool idea for indie developers"
        )

        receipt = self._persist_receipt(
            resolved,
            skill_id="pmf-recon",
            result=self._pmf_recon_result(),
        )

        self.assertEqual(receipt["skill_id"], "pmf-recon")
        self._assert_generated_task_id(receipt["task_id"], buddy="market")
        self.assertEqual(receipt["artifact_ids"], [receipt["artifact_id"]])
        self.assertIn("task_title", receipt)
        self.assertIsNone(receipt["track_title"])
        self.assertIn("reference_switches", receipt)
        self.assertEqual(
            receipt["reference_switches"]["continue_current_task"],
            f"switch market({receipt['task_id']}): <demand>",
        )
        self.assertEqual(receipt["related_run_ids"], [])
        self.assertEqual(receipt["recommended_switch"], receipt["reference_switches"]["continue_current_task"])
        self._remember_persisted_paths(receipt)

        artifact_json = json.loads(self._runtime_path(receipt["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
        task_json = json.loads(self._runtime_path(receipt["paths"]["task"]).read_text(encoding="utf-8"))
        run_json = json.loads(self._runtime_path(receipt["paths"]["run"]).read_text(encoding="utf-8"))

        self.assertEqual(artifact_json["task_id"], receipt["task_id"])
        self.assertEqual(artifact_json["source_run_id"], receipt["run_id"])
        self.assertEqual(artifact_json["skill_id"], "pmf-recon")
        self.assertEqual(artifact_json["slot"], "pmf-report")
        self.assertEqual(
            artifact_json["content"]["research_question"],
            self._pmf_recon_result()["artifact_content"]["research_question"],
        )
        self.assertIn(receipt["run_id"], task_json["run_ids"])
        self.assertEqual(
            task_json["artifact_slots"][artifact_json["slot"]]["current_artifact_id"],
            receipt["artifact_id"],
        )
        self.assertEqual(run_json["resolved_task_id"], receipt["task_id"])
        self.assertEqual(run_json["artifact_ids"], [receipt["artifact_id"]])
        self.assertEqual(run_json["skill_id"], "pmf-recon")
        self.assertEqual(run_json["switch"]["demand"], resolved["switch"]["demand"])
        self.assertEqual(run_json["task_title"], receipt["task_title"])
        self.assertEqual(run_json["track_title"], receipt["track_title"])
        self.assertEqual(run_json["reference_switches"], receipt["reference_switches"])
        self.assertEqual(run_json["related_run_ids"], receipt["related_run_ids"])
        self.assertEqual(run_json["recommended_switch"], receipt["recommended_switch"])
        self.assertNotIn("artifact_content", run_json)

    def test_create_mode_resolve_materializes_task_id_and_persist_reuses_it(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        self.assertEqual(resolved["task_resolution"]["mode"], "create")
        self.assertIsInstance(resolved["task_resolution"]["task_id"], str)
        self.assertTrue(resolved["task_resolution"]["task_id"])
        self.assertIsInstance(resolved["task_resolution"]["create_token"], str)
        self.assertTrue(resolved["task_resolution"]["create_token"])
        self.assertEqual(resolved["switch"]["task_id"], resolved["task_resolution"]["task_id"])

        task_id = resolved["task_resolution"]["task_id"]
        assert isinstance(task_id, str)
        task_before = get_task(task_id)
        self.assertIsNotNone(task_before)
        assert isinstance(task_before, dict)
        self.assertEqual(task_before["run_ids"], [])
        self.assertIsNone(task_before["latest_run_id"])

        payload = switch_runtime.persist_skill_result(
            resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(payload)

        self.assertEqual(payload["receipt"]["task_id"], task_id)

        run_json = json.loads(self._runtime_path(payload["receipt"]["paths"]["run"]).read_text(encoding="utf-8"))
        self.assertEqual(run_json["resolved_task_id"], task_id)
        self.assertEqual(run_json["switch"]["task_id"], task_id)

    def test_persist_skill_result_rejects_tampered_switch_task_id_without_writes(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        malformed_switch = deepcopy(resolved)
        malformed_switch["switch"]["task_id"] = "task-dev-prefilled-from-switch"
        task_id = resolved["task_context"]["task"]["id"]
        task_path = self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_task_contents = task_path.read_text(encoding="utf-8")
        before_run_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in run_dir.glob("run-*.json")
        }
        before_artifact_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in artifact_dir.glob("art-*.json")
        }

        with self.assertRaisesRegex(
            ValueError,
            "switch.task_id mismatch",
        ):
            switch_runtime.persist_skill_result(
                malformed_switch,
                skill_id="implement-task",
                result=self._artifact_result(),
            )
        self.assertEqual(task_path.read_text(encoding="utf-8"), before_task_contents)
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in run_dir.glob("run-*.json")
            },
            before_run_contents,
        )
        self.assertEqual(
            {
                path.name: path.read_text(encoding="utf-8")
                for path in artifact_dir.glob("art-*.json")
            },
            before_artifact_contents,
        )

    def test_create_mode_persist_retry_same_resolved_payload_fails_closed(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        task_dir = self._runtime_path("buddyswitch/objects/tasks")
        run_dir = self._runtime_path("buddyswitch/content/runs")
        artifact_dir = self._runtime_path("buddyswitch/objects/artifacts")
        before_tasks = {path.name for path in task_dir.glob("task-*.json")}
        before_runs = {path.name for path in run_dir.glob("run-*.json")}
        before_artifacts = {path.name for path in artifact_dir.glob("art-*.json")}

        first_payload = self._persist_receipt(
            resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(first_payload)
        after_first_tasks = {path.name for path in task_dir.glob("task-*.json")}
        after_first_runs = {path.name for path in run_dir.glob("run-*.json")}
        after_first_artifacts = {path.name for path in artifact_dir.glob("art-*.json")}

        self.assertEqual(len(after_first_tasks), len(before_tasks))
        self.assertEqual(len(after_first_runs), len(before_runs) + 1)
        self.assertEqual(len(after_first_artifacts), len(before_artifacts) + 1)

        with self.assertRaisesRegex(ValueError, "context_revision mismatch"):
            switch_runtime.persist_skill_result(
                resolved,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

        self.assertEqual({path.name for path in task_dir.glob("task-*.json")}, after_first_tasks)
        self.assertEqual({path.name for path in run_dir.glob("run-*.json")}, after_first_runs)
        self.assertEqual({path.name for path in artifact_dir.glob("art-*.json")}, after_first_artifacts)

    def test_create_mode_downstream_failure_surfaces_created_task_id(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        create_token = resolved["task_resolution"]["create_token"]
        expected_task_id = switch_runtime._derive_task_id("dev", "", create_token=create_token)
        self._remember(f"buddyswitch/objects/tasks/{expected_task_id}.json")

        with patch("switch_runtime._persist_artifact_skill", side_effect=ValueError("downstream persist failed")):
            with self.assertRaisesRegex(
                ValueError,
                rf"downstream persist failed .*created task_id: {expected_task_id}",
            ):
                switch_runtime.persist_skill_result(
                    resolved,
                    skill_id="implement-task",
                    result=self._artifact_result(),
                )

    def test_create_mode_downstream_oserror_surfaces_created_task_id(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        create_token = resolved["task_resolution"]["create_token"]
        expected_task_id = switch_runtime._derive_task_id("dev", "", create_token=create_token)
        self._remember(f"buddyswitch/objects/tasks/{expected_task_id}.json")

        with patch("switch_runtime._persist_artifact_skill", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(
                OSError,
                rf"disk full .*created task_id: {expected_task_id}; recover with switch dev\({expected_task_id}\): <demand>",
            ):
                switch_runtime.persist_skill_result(
                    resolved,
                    skill_id="implement-task",
                    result=self._artifact_result(),
                )

    def test_create_mode_downstream_oserror_with_explicit_track_surfaces_track_aware_recovery(self) -> None:
        track = create_track("track-dev-recovery-hint", "Track Dev Recovery Hint")
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")

        resolved = switch_runtime.resolve_switch(
            "switch dev -> track-dev-recovery-hint: Implement the approved onboarding improvements in projects/app"
        )
        create_token = resolved["task_resolution"]["create_token"]
        expected_task_id = switch_runtime._derive_task_id("dev", "", create_token=create_token)
        self._remember(f"buddyswitch/objects/tasks/{expected_task_id}.json")

        with patch("switch_runtime._persist_artifact_skill", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(
                OSError,
                rf"disk full .*created task_id: {expected_task_id}; recover with switch dev\({expected_task_id}\) -> track-dev-recovery-hint: <demand>",
            ):
                switch_runtime.persist_skill_result(
                    resolved,
                    skill_id="implement-task",
                    result=self._artifact_result(),
                )
    def test_cmd_persist_create_mode_downstream_oserror_returns_runtime_error_payload(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        create_token = resolved["task_resolution"]["create_token"]
        expected_task_id = switch_runtime._derive_task_id("dev", "", create_token=create_token)
        self._remember(f"buddyswitch/objects/tasks/{expected_task_id}.json")

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            resolved_path = temp_root / "resolved.json"
            result_path = temp_root / "result.json"
            resolved_path.write_text(json.dumps(resolved, ensure_ascii=True), encoding="utf-8")
            result_path.write_text(json.dumps(self._artifact_result(), ensure_ascii=True), encoding="utf-8")

            args = argparse.Namespace(
                resolved=str(resolved_path),
                result=str(result_path),
                skill_id=None,
                manifest=switch_runtime.DEFAULT_MANIFEST,
            )

            stdout = io.StringIO()
            with patch("switch_runtime._persist_artifact_skill", side_effect=OSError("disk full")):
                with redirect_stdout(stdout):
                    exit_code = switch_runtime._cmd_persist(args)

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_RUNTIME_PERSIST")
        message = payload["error"]["message"]
        self.assertIn("disk full", message)
        self.assertIn(f"created task_id: {expected_task_id}", message)
        self.assertIn(f"recover with switch dev({expected_task_id}): <demand>", message)

    def test_cmd_persist_uses_persist_skill_result_surface(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        self._remember(f"buddyswitch/objects/tasks/{resolved['task_resolution']['task_id']}.json")

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            resolved_path = temp_root / "resolved.json"
            result_path = temp_root / "result.json"
            resolved_path.write_text(json.dumps(resolved, ensure_ascii=True), encoding="utf-8")
            result_path.write_text(json.dumps(self._artifact_result(), ensure_ascii=True), encoding="utf-8")

            args = argparse.Namespace(
                resolved=str(resolved_path),
                result=str(result_path),
                skill_id="implement-task",
                manifest=switch_runtime.DEFAULT_MANIFEST,
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = switch_runtime._cmd_persist(args)

        payload = json.loads(stdout.getvalue())
        if payload.get("ok"):
            self._remember_persisted_paths(payload)

        self.assertEqual(exit_code, 0)
        self.assertEqual(list(payload.keys()), PERSIST_SKILL_RESULT_RESPONSE_KEY_ORDER)
        self.assertEqual(payload["receipt"]["run_id"], resolved["run_envelope"]["run_id"])
        self.assertEqual(
            payload["refreshed_context"]["run_envelope"]["previous_run_id"],
            payload["receipt"]["run_id"],
        )
        for field in PERSIST_SKILL_RESULT_PACKET_ERA_FIELDS:
            self.assertNotIn(field, payload)

    def test_persist_skill_result_reports_refresh_failure_without_hiding_committed_writes(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )

        with patch("switch_runtime._build_resolve_context", side_effect=OSError("disk full during refresh reserve")):
            payload = switch_runtime.persist_skill_result(
                resolved,
                skill_id="implement-task",
                result=self._artifact_result(),
            )

        self._remember_persisted_paths(payload)

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["refreshed_context"]["ok"])
        self.assertEqual(payload["refreshed_context"]["error"]["code"], "E_RUNTIME_REFRESH_CONTEXT")
        self.assertIn("disk full during refresh reserve", payload["refreshed_context"]["error"]["message"])
        receipt = payload["receipt"]
        run_json = json.loads(self._runtime_path(receipt["paths"]["run"]).read_text(encoding="utf-8"))
        self.assertEqual(run_json["resolved_task_id"], receipt["task_id"])
        self.assertFalse(
            switch_runtime._reserved_run_path(receipt["run_id"]).exists()  # type: ignore[attr-defined]
        )

    def test_persist_new_market_skills_with_explicit_slots(self) -> None:
        cases = [
            ("customer-discovery", self._customer_discovery_result, "customer-discovery", "interview_goals"),
            ("positioning-copy", self._positioning_copy_result, "positioning-brief", "positioning_statement"),
            ("channel-discovery", self._channel_discovery_result, "channel-plan", "experiment_plan"),
            ("launch-prep", self._launch_prep_result, "launch-prep", "launch_goal"),
        ]

        for skill_id, result_factory, expected_slot, content_key in cases:
            with self.subTest(skill_id=skill_id):
                resolved = switch_runtime.resolve_switch(
                    "switch market: Continue the market evidence handoff for the current opportunity"
                )

                receipt = self._persist_receipt(
                    resolved,
                    skill_id=skill_id,
                    result=result_factory(),
                )
                self._remember_persisted_paths(receipt)

                artifact_json = json.loads(self._runtime_path(receipt["paths"]["artifacts"][0]).read_text(encoding="utf-8"))
                run_json = json.loads(self._runtime_path(receipt["paths"]["run"]).read_text(encoding="utf-8"))

                self.assertEqual(receipt["skill_id"], skill_id)
                self.assertEqual(artifact_json["slot"], expected_slot)
                self.assertIn(content_key, artifact_json["content"])
                self.assertEqual(run_json["skill_id"], skill_id)
                self.assertEqual(run_json["artifact_ids"], [receipt["artifact_id"]])
    def test_persist_reuses_task_and_binds_to_track(self) -> None:
        track = create_track("track-dev-binding", "Track Binding")
        task = create_task("task-dev-binding", "Task Binding", buddy="dev", initial_run_id="run-seed-binding")
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        resolved = switch_runtime.resolve_switch("switch dev(task-dev-binding) -> track-dev-binding: continue implementation")
        receipt = self._persist_receipt(
            resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(receipt)

        self.assertEqual(receipt["task_id"], "task-dev-binding")
        self.assertEqual(receipt["track_id"], "track-dev-binding")
        self.assertEqual(receipt["track_title"], "Track Binding")
        self.assertIn("continue_current_task_in_track", receipt["reference_switches"])
        self.assertNotIn("handoff_to_next_buddy", receipt["reference_switches"])
        self.assertEqual(receipt["recommended_switch"], receipt["reference_switches"]["continue_current_task_in_track"])
        track_after = get_track("track-dev-binding")
        self.assertIsNotNone(track_after)
        self.assertIn("task-dev-binding", track_after["task_ids"])

    def test_persist_artifact_skill_requires_output_slot_without_legacy_fallback(self) -> None:
        track = create_track("track-legacy-output-slot", "Track Legacy Output Slot")
        task = create_task(
            "task-dev-legacy-output-slot",
            "Task Legacy Output Slot",
            buddy="dev",
            track_id=track["id"],
            initial_run_id="run-seed-legacy-output-slot",
        )
        self._remember(f"buddyswitch/objects/tracks/{track['id']}.json")
        self._remember(f"buddyswitch/objects/tasks/{task['id']}.json")

        resolved = switch_runtime.resolve_switch(
            "switch dev(task-dev-legacy-output-slot) -> track-legacy-output-slot: continue implementation"
        )
        skill = {
            "id": "legacy-output-slot-skill",
            "runtime": {
                "default_artifact_kind": "legacy-kind",
                "produces_artifact": True,
                "input_slots": ["task"],
                "output_schema": "framework/schemas/dev/implement-task.json",
            },
        }

        try:
            payload = switch_runtime._persist_artifact_skill(  # type: ignore[attr-defined]
                resolved=resolved,
                skill=skill,
                result=self._artifact_result(),
                run_id="run-legacy-output-slot",
                task=task,
                effective_track_id=track["id"],
            )
        except ValueError as exc:
            self.assertRegex(str(exc), "non-empty output_slot")
        else:
            self._remember_persisted_paths(payload)
            self.fail("Expected _persist_artifact_skill to reject missing output_slot")

    def test_track_manager_create_track_binds_current_task(self) -> None:
        resolved = switch_runtime.resolve_switch("switch pm: create new track and set ownership")
        result = {
            "execution_summary": "Created the requested track.",
            "working_notes": ["Reserved PM as the initial owner."],
            "deliverables_or_changed_files": [],
            "track_operation": {
                "action": "create",
                "track_id": "track-task-manager-create",
                "title": "Track Task Manager Create",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "dev",
                "summary": "Initial track creation.",
            },
        }
        receipt = self._persist_receipt(
            resolved,
            skill_id="track-manager",
            result=result,
        )
        self._remember_persisted_paths(receipt)

        self.assertEqual(receipt["skill_id"], "track-manager")
        self.assertEqual(receipt["track_action"], "create")
        self.assertEqual(receipt["track_id"], "track-task-manager-create")
        self.assertEqual(receipt["track_title"], "Track Task Manager Create")
        self.assertIn("handoff_to_next_buddy", receipt["reference_switches"])
        self.assertEqual(
            receipt["reference_switches"]["handoff_to_next_buddy"],
            "switch dev -> track-task-manager-create: <demand>",
        )
        self.assertEqual(receipt["recommended_switch"], receipt["reference_switches"]["handoff_to_next_buddy"])
        task_json = get_task(receipt["task_id"])
        self.assertIsNotNone(task_json)
        self.assertEqual(task_json["track_id"], "track-task-manager-create")
        track_json = json.loads(self._runtime_path(receipt["paths"]["track"]).read_text(encoding="utf-8"))
        self.assertIn(receipt["task_id"], track_json["task_ids"])

    def test_persist_skill_result_track_creation_binds_task_and_track_ids_together(self) -> None:
        context = switch_runtime.resolve_switch("switch pm: create a landing page track")

        payload = switch_runtime.persist_skill_result(
            context,
            skill_id="track-manager",
            result={
                "execution_summary": "Created a landing-page track.",
                "working_notes": [],
                "deliverables_or_changed_files": [],
                "track_operation": {
                    "action": "create",
                    "track_id": "track-landing-page",
                    "title": "Landing Page",
                    "status": "active",
                    "current_buddy": "pm",
                    "next_buddy": "design",
                    "summary": "Track for landing-page definition and prototype handoff.",
                },
            },
        )

        self._remember(payload["receipt"]["paths"]["run"])
        self._remember(payload["receipt"]["paths"]["task"])
        self._remember(payload["receipt"]["paths"]["track"])

        task = get_task(payload["receipt"]["task_id"])
        track = get_track("track-landing-page")

        self.assertIsNotNone(task)
        self.assertIsNotNone(track)
        self.assertEqual(task["track_id"], "track-landing-page")
        self.assertIn(task["id"], track["task_ids"])

    def test_persist_related_runs_surface_previous_task_runs(self) -> None:
        first_resolved = switch_runtime.resolve_switch(
            "switch dev: Implement the approved onboarding improvements in projects/app"
        )
        first_payload = self._persist_receipt(
            first_resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(first_payload)

        second_resolved = switch_runtime.resolve_switch(
            f"switch dev({first_payload['task_id']}): continue onboarding improvements"
        )
        second_payload = self._persist_receipt(
            second_resolved,
            skill_id="implement-task",
            result=self._artifact_result(),
        )
        self._remember_persisted_paths(second_payload)

        self.assertIn(first_payload["run_id"], second_payload["related_run_ids"])

    def test_execute_alias_is_not_registered(self) -> None:
        parser = switch_runtime.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["execute", "--resolved", "resolved.json", "--result", "result.json"])

    def test_prepare_execution_command_is_removed(self) -> None:
        parser = switch_runtime.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    ["prepare-execution", "--resolved", "resolved.json", "--skill-id", "implement-task"]
                )


if __name__ == "__main__":
    unittest.main()
