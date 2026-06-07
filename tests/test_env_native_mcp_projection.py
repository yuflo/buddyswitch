#!/usr/bin/env python3
"""Tests for Codex-native MCP projection of BuddySwitch env tools."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import registry  # noqa: E402


class EnvNativeMcpProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        registry.clear_cache()
        self.native_mcp = importlib.import_module("env.tool_runtime.native_mcp")

    def tearDown(self) -> None:
        registry.clear_cache()

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
                    self.assertEqual(self.native_mcp.decode_native_tool_name(name), (tool, action.name))
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

    def test_projection_loads_no_private_tool_implementations_or_services(self) -> None:
        script = """
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from env.tool_runtime import native_mcp

native_mcp.list_native_tool_specs()
loaded = sorted(sys.modules)
print(json.dumps({
    "private_impl": [name for name in loaded if name.startswith("env.tools.") and "._impl" in name],
    "domain": [name for name in loaded if name.startswith("env.domain.")],
    "repos": [name for name in loaded if name.startswith("env.repos.")],
    "runtime_services": [
        name for name in loaded
        if name.startswith("runtime_kernel.server")
        or name.startswith("runtime_kernel.broker")
        or name.startswith("tools.launcher")
    ],
}, ensure_ascii=True))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
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

    def test_projection_discovers_new_tool_package_without_central_manifest(self) -> None:
        import env.tools  # noqa: WPS433

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_tools = Path(temp_dir) / "env" / "tools"
            probe_dir = temp_tools / "probe"
            probe_dir.mkdir(parents=True)
            (probe_dir / "__init__.py").write_text('"""Probe env tool package."""\n', encoding="utf-8")
            (probe_dir / "tool.py").write_text(
                textwrap.dedent(
                    '''
                    from __future__ import annotations

                    from typing import Any

                    from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition

                    DEFINITION = ToolDefinition(
                        id="probe",
                        title="Probe Tool",
                        description="Temporary probe tool used to verify registry discovery.",
                        scope="test-only",
                        capability_boundary="Reads temporary probe data only.",
                        object_model="Temporary probe object.",
                        use_when=("Use to prove native projection discovers new tool packages.",),
                        do_not_use_when=("Do not use outside projection tests.",),
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
                                required_permission="probe.inspect",
                                authority="test-only",
                                visibility="active-role",
                                durability="none",
                                result_content_level="summary",
                                success_effect="Returns temporary probe details.",
                                failure_state_guarantee="No runtime state changes on failure.",
                                reads=("temporary probe data",),
                                writes=(),
                                does_not_write=("runtime objects",),
                                preconditions=("probe package is present on env.tools path",),
                                returns=("probe summary",),
                                use_when=("Use when verifying dynamic native discovery.",),
                                do_not_use_when=("Do not use in product flows.",),
                            ),
                        ),
                    )
                    validate_definition(DEFINITION)

                    def invoke(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
                        return {"ok": True, "tool": "probe", "action": f"probe.{action}", "args": args}
                    '''
                ).lstrip(),
                encoding="utf-8",
            )

            original_path = list(env.tools.__path__)
            try:
                env.tools.__path__.insert(0, str(temp_tools))
                registry.clear_cache()
                names = {spec["name"] for spec in self.native_mcp.list_native_tool_specs()}
            finally:
                env.tools.__path__[:] = original_path
                registry.clear_cache()

        self.assertIn("probe__inspect", names)

        projection_source = (ROOT / "scripts/env/tool_runtime/native_mcp.py").read_text(encoding="utf-8")
        server_path = ROOT / "tools/launcher/env_tool_mcp_server.py"
        server_source = server_path.read_text(encoding="utf-8") if server_path.exists() else ""
        combined = projection_source + "\n" + server_source
        for forbidden in ("SHIPPED_TOOLS", "task__current", "message__send", "native_manifest", "tool_pack"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
