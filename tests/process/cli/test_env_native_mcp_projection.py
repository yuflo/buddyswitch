"""Tests for Codex-native MCP projection of BuddySwitch env tools."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path


from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT

from buddyswitch.foundation.tool_runtime import registry  # noqa: E402
from tests.support.python import PYTHON  # noqa: E402


class EnvNativeMcpProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.native_mcp = importlib.import_module("buddyswitch.foundation.tool_runtime.native_mcp")

    def test_projection_covers_every_registry_action_with_matching_schema(self) -> None:
        specs = self.native_mcp.list_native_tool_specs()
        by_name = {spec["name"]: spec for spec in specs}
        expected_count = 0

        for tool in sorted(registry.supported_tools()):
            definition = registry.get_definition(tool)
            for action in definition.actions:
                expected_count += 1
                name = f"{tool}__{action.name}"
                with self.subTest(action=name):
                    self.assertIn(name, by_name)
                    self.assertEqual(self.native_mcp.resolve_native_tool_name(name), (tool, action.name))
                    self.assertEqual(by_name[name]["inputSchema"], action.input_schema)
                    self.assertNotIn("outputSchema", by_name[name])
                    description = by_name[name]["description"]
                    for token in (
                        definition.title,
                        action.title,
                        action.description,
                        action.required_permission,
                        action.mutates,
                        action.visibility,
                        action.durability,
                        action.success_effect,
                        action.failure_state_guarantee,
                    ):
                        self.assertIn(token, description)
                    self.assertNotIn("scripts/env/client.py", description)
                    self.assertTrue(any(row in description for row in action.use_when), msg=description)
                    self.assertTrue(any(row in description for row in action.do_not_use_when), msg=description)

        self.assertEqual(len(specs), expected_count)
        self.assertNotIn("task__get", by_name)
        self.assertEqual(
            {name for name in by_name if name.startswith("demand_sys__")},
            {
                "demand_sys__list",
                "demand_sys__get",
                "demand_sys__resolve_inbound",
                "demand_sys__complete",
            },
        )
        self.assertFalse(any(name.startswith("demand__") for name in by_name))
        self.assertNotIn("demand", registry.supported_tools())
        self.assertNotIn("demand_triage__resolve", by_name)

    def test_demand_and_task_specs_expose_actor_contract_shape_and_boundaries(self) -> None:
        by_name = {
            spec["name"]: spec
            for spec in self.native_mcp.list_native_tool_specs()
        }

        demand_resolve = by_name["demand_sys__resolve_inbound"]
        task_create = by_name["task_sys__create"]
        self.assertEqual(
            set(demand_resolve["inputSchema"]["properties"]),
            {"decision", "reason", "demand_ref", "description", "detail", "reply_content"},
        )
        self.assertEqual(
            demand_resolve["inputSchema"]["properties"]["decision"]["enum"],
            ["no_action_needed", "handled", "create", "merge_intake", "revise", "cancel"],
        )
        self.assertEqual(
            set(task_create["inputSchema"]["properties"]),
            {"demand_ref", "objective", "selection_reason"},
        )
        for tool in (demand_resolve, task_create):
            self.assertTrue(tool["description"].strip())
            for field_schema in tool["inputSchema"]["properties"].values():
                self.assertTrue(field_schema["description"].strip())

        # These two exclusions are stable product boundaries, not prose snapshots.
        self.assertIn(
            "isolated",
            demand_resolve["description"].lower(),
        )
        self.assertIn(
            "does not mutate, satisfy, or reprioritize a Demand",
            task_create["description"],
        )

    def test_projection_loads_no_private_tool_implementations_or_services(self) -> None:
        script = """
import json
import sys
from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime import native_mcp

activate_application()
before = set(sys.modules)
native_mcp.list_native_tool_specs()
loaded = sorted(set(sys.modules) - before)
print(json.dumps({
    "private_impl": [name for name in loaded if name.endswith("._impl") and ".private.adapters.tool." in name],
    "domain": [name for name in loaded if name.startswith("buddyswitch.env.domain.")],
    "repos": [name for name in loaded if name.startswith("buddyswitch.env.repos.")],
    "runtime_services": [
        name for name in loaded
        if name.startswith("buddyswitch.foundation.runtime_broker.server")
        or name.startswith("buddyswitch.foundation.runtime_broker.broker")
        or name.startswith("tools.launcher")
    ],
}, ensure_ascii=True))
"""
        completed = run_process(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["private_impl"], [])
        self.assertEqual(payload["domain"], [])
        self.assertEqual(payload["repos"], [])
        self.assertEqual(payload["runtime_services"], [])

    def test_projection_uses_explicit_registration_as_its_only_catalog_input(self) -> None:
        from buddyswitch.foundation.tool_runtime.definition import (
            ActionDefinition,
            TASK_REQUIREMENT_FREE,
            ToolDefinition,
            ToolRegistration,
        )

        definition = ToolDefinition(
            id="probe",
            title="Probe Tool",
            description="Explicit native projection probe.",
            scope="test-only",
            capability_boundary="Reads temporary probe data only.",
            object_model="Temporary probe object.",
            use_when=("testing explicit projection",),
            do_not_use_when=("running product work",),
            actions=(
                ActionDefinition(
                    name="inspect",
                    title="Inspect Probe",
                    description="Inspect temporary probe state.",
                    input_schema={
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "probe_id": {
                                "type": "string",
                                "description": "Probe id to inspect.",
                            }
                        },
                        "required": ["probe_id"],
                    },
                    output_schema={"$ref": "ToolResult"},
                    kind="read",
                    task_requirement=TASK_REQUIREMENT_FREE,
                    mutates="none",
                    required_permission="none",
                    authority="test-only",
                    visibility="test-only",
                    durability="none",
                    result_content_level="summary",
                    success_effect="Returns temporary probe details.",
                    failure_state_guarantee="No runtime state changes on failure.",
                    reads=("temporary probe data",),
                    writes=(),
                    does_not_write=("runtime objects",),
                    use_when=("testing explicit projection",),
                    do_not_use_when=("running product work",),
                ),
            ),
        )
        registry.configure_tool_registrations(
            (ToolRegistration(definition=definition, invoke=lambda **_kwargs: {}),)
        )
        try:
            names = {spec["name"] for spec in self.native_mcp.list_native_tool_specs()}
        finally:
            from buddyswitch.application.build import activate_application

            activate_application()

        self.assertEqual(names, {"probe__inspect"})

        projection_source = (ROOT / "src/buddyswitch/foundation/tool_runtime/native_mcp.py").read_text(encoding="utf-8")
        server_path = ROOT / "src/buddyswitch/foundation/tool_runtime/mcp_server.py"
        server_source = server_path.read_text(encoding="utf-8") if server_path.exists() else ""
        combined = projection_source + "\n" + server_source
        for forbidden in (
            "SHIPPED_TOOLS",
            "task__current",
            "message__send",
            "native_manifest",
            "tool_pack",
            "discover_tool_ids",
        ):
            self.assertNotIn(forbidden, combined)
