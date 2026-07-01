#!/usr/bin/env python3
"""Architecture tests for black-box env.tool runtime."""

from __future__ import annotations

import ast
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

SHIPPED_TOOLS: dict[str, set[str]] = {
    "artifact": {"attach_file", "create_revision", "get", "get_attachment", "list", "list_attachments", "update_metadata"},
    "context": {"get", "list_sources", "summarize"},
    "evidence": {"approve_downgrade", "issue_browser"},
    "message": {"contacts", "conversation", "get", "list", "mark", "send"},
    "search": {"open_browser", "request", "status"},
    "task_sys": {"list", "get", "close", "need_parent"},
    "track": {
        "add_comment",
        "add_material",
        "add_proof",
        "add_update",
        "archive",
        "create",
        "list",
        "list_comments",
        "open",
        "resolve_comment_thread",
        "update_requirements",
        "update_status",
    },
}

LEGACY_SHARED_RUNTIME_FILES = {
    "catalog.py",
    "cli_helpers.py",
    "discovery.py",
    "dispatch.py",
    "model.py",
    "responses.py",
    "router.py",
}

LEGACY_TOOL_PUBLIC_FILES = {"contract.py", "semantics.py", "handlers.py", "cli.py", "service.py"}
FORBIDDEN_IMPORT_PREFIXES = ("env.repos", "env.domain", "env_manifest", "runtime_kernel")
FORBIDDEN_ENV_TOOLS_RUNTIME_IMPORTS = {
    f"env.tools.{name}"
    for name in (
        "catalog",
        "dispatch",
        "router",
        "responses",
        "model",
        "discovery",
        "cli_helpers",
    )
}


class BlackBoxToolRuntimeTests(unittest.TestCase):
    def _tool_dir(self, tool: str) -> Path:
        return ROOT / "scripts" / "env" / "tools" / tool

    def _run_python(self, script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_shipped_tools_expose_single_public_entrypoint(self) -> None:
        for tool, expected_actions in sorted(SHIPPED_TOOLS.items()):
            with self.subTest(tool=tool):
                package_dir = self._tool_dir(tool)
                self.assertTrue(package_dir.is_dir(), msg=f"missing tool package: {package_dir}")
                self.assertTrue((package_dir / "tool.py").exists(), msg=f"missing tool.py for {tool}")
                for file_name in sorted(LEGACY_TOOL_PUBLIC_FILES):
                    self.assertFalse((package_dir / file_name).exists(), msg=f"legacy file still exists: {package_dir / file_name}")

                module = importlib.import_module(f"env.tools.{tool}.tool")
                definition = getattr(module, "DEFINITION", None)
                invoke = getattr(module, "invoke", None)
                self.assertTrue(callable(invoke), msg=f"{tool}.tool.invoke must be callable")
                self.assertIsNotNone(definition, msg=f"{tool}.tool.DEFINITION missing")
                self.assertEqual(getattr(definition, "id", None), tool)

                actions = getattr(definition, "actions", ())
                names = {getattr(row, "name", None) for row in actions}
                self.assertEqual(names, expected_actions)
                for action in actions:
                    input_schema = getattr(action, "input_schema", None)
                    self.assertIsInstance(input_schema, dict, msg=action)
                    self.assertEqual(input_schema.get("type"), "object", msg=action)
                    self.assertIs(input_schema.get("additionalProperties"), False, msg=action)
                    self.assertIsInstance(input_schema.get("properties"), dict, msg=action)

                    output_schema = getattr(action, "output_schema", None)
                    self.assertIsInstance(output_schema, dict, msg=action)
                    if "$ref" in output_schema:
                        self.assertEqual(output_schema, {"$ref": "ToolResult"})
                    else:
                        self.assertEqual(output_schema.get("type"), "object", msg=action)

    def test_registry_catalog_loads_definitions_without_private_implementations(self) -> None:
        script = """
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from env.tool_runtime import registry

registry.supported_tools()
registry.env_tools_description()
registry.operation_semantics()

loaded_private = sorted(
    name for name in sys.modules
    if name.startswith("env.tools.") and "._impl" in name
)
loaded_repos = sorted(name for name in sys.modules if name.startswith("env.repos."))
loaded_domains = sorted(name for name in sys.modules if name.startswith("env.domain."))
loaded_runtime = sorted(name for name in sys.modules if name.startswith("runtime_kernel."))
print(json.dumps({
    "loaded_private": loaded_private,
    "loaded_repos": loaded_repos,
    "loaded_domains": loaded_domains,
    "loaded_runtime": loaded_runtime,
}))
"""
        completed = self._run_python(script)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["loaded_private"], [])
        self.assertEqual(payload["loaded_repos"], [])
        self.assertEqual(payload["loaded_domains"], [])
        self.assertEqual(payload["loaded_runtime"], [])

    def test_tool_packages_import_only_runtime_sdk_and_local_modules(self) -> None:
        violations: list[str] = []
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            for path in sorted(package_dir.rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                rel = path.relative_to(ROOT).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.name
                            if name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                                violations.append(f"{rel}:{node.lineno}: import {name}")
                            if name in FORBIDDEN_ENV_TOOLS_RUNTIME_IMPORTS:
                                violations.append(f"{rel}:{node.lineno}: import {name}")
                            if name.startswith("env.tools."):
                                parts = name.split(".")
                                if len(parts) >= 3 and parts[2] in SHIPPED_TOOLS and parts[2] != tool:
                                    violations.append(f"{rel}:{node.lineno}: import sibling tool {name}")
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                            violations.append(f"{rel}:{node.lineno}: from {module} import ...")
                        if module in FORBIDDEN_ENV_TOOLS_RUNTIME_IMPORTS:
                            violations.append(f"{rel}:{node.lineno}: from {module} import ...")
                        if module == "env.tools":
                            for alias in node.names:
                                if alias.name in SHIPPED_TOOLS and alias.name != tool:
                                    violations.append(f"{rel}:{node.lineno}: from env.tools import sibling {alias.name}")
                        if module.startswith("env.tools."):
                            parts = module.split(".")
                            if len(parts) >= 3 and parts[2] in SHIPPED_TOOLS and parts[2] != tool:
                                violations.append(f"{rel}:{node.lineno}: from sibling tool module {module} import ...")
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_tool_packages_mutate_state_only_through_tool_context(self) -> None:
        violations: list[str] = []
        blocked_literals = (
            "workspace_dir",
            "BUDDYSWITCH_STATE_ROOT",
            "buddyswitch/objects",
            "buddyswitch/local/actor_private",
        )
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            for path in sorted(package_dir.rglob("*.py")):
                source = path.read_text(encoding="utf-8")
                rel = path.relative_to(ROOT).as_posix()
                tree = ast.parse(source, filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            if node.func.attr in {"write_text", "write_bytes", "unlink"}:
                                violations.append(f"{rel}:{node.lineno}: direct path mutation via .{node.func.attr}()")
                        if isinstance(node.func, ast.Name) and node.func.id == "open":
                            mode = None
                            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                                mode = node.args[1].value
                            for keyword in node.keywords:
                                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                                    mode = keyword.value.value
                            if isinstance(mode, str) and any(flag in mode for flag in ("w", "a", "x")):
                                violations.append(f"{rel}:{node.lineno}: open() write mode is not allowed")
                if path.name == "_impl.py":
                    for literal in blocked_literals:
                        if literal in source:
                            violations.append(f"{rel}: contains forbidden storage literal: {literal}")
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_registry_projects_catalog_semantics_payload_fields_and_cli_actions_from_definitions(self) -> None:
        from env.tool_runtime import registry

        tools_desc = registry.env_tools_description()
        semantics = registry.operation_semantics()
        for tool in sorted(registry.supported_tools()):
            definition = registry.get_definition(tool)
            actions = {action.name for action in definition.actions}
            self.assertEqual(set(tools_desc[tool]["operations"]), actions)
            for action in sorted(actions):
                action_def = registry.get_action_definition(tool, action)
                expected_fields = [name for name in (action_def.input_schema.get("properties") or {}) if isinstance(name, str)]
                self.assertEqual(tools_desc[tool]["payload_fields"][action], expected_fields)
                self.assertEqual(
                    set(registry.payload_fields_for_action(tool, action)),
                    set(expected_fields),
                )
                self.assertIn(f"{tool}.{action}", semantics)

    def test_definition_validation_rejects_incomplete_input_contracts(self) -> None:
        from env.tool_runtime.definition import ActionDefinition
        from env.tool_runtime.definition import MUTATES_NONE
        from env.tool_runtime.definition import TASK_REQUIREMENT_FREE
        from env.tool_runtime.definition import ToolDefinition
        from env.tool_runtime.definition import validate_definition

        def _definition_for(schema: dict[str, object]) -> ToolDefinition:
            return ToolDefinition(
                id="probe",
                title="Probe",
                description="Probe validation.",
                scope="probe scope",
                capability_boundary="probe boundary",
                object_model="Probe objects are test-only validation rows.",
                use_when=("testing",),
                do_not_use_when=(),
                actions=(
                    ActionDefinition(
                        name="ping",
                        title="probe.ping",
                        description="Probe action.",
                        input_schema=schema,
                        output_schema={"$ref": "ToolResult"},
                        kind="read",
                        mutates=MUTATES_NONE,
                        task_requirement=TASK_REQUIREMENT_FREE,
                        required_permission="none",
                        authority="probe",
                        visibility="test-only probe",
                        durability="none",
                        result_content_level="probe row",
                        success_effect="Returns one probe row without mutation.",
                        failure_state_guarantee="Rejected probe reads do not mutate runtime state.",
                        reads=("probe payload",),
                        writes=(),
                        does_not_write=("runtime objects",),
                    ),
                ),
            )

        with self.assertRaises(ValueError):
            validate_definition(
                _definition_for(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string", "description": "Title."},
                        },
                    }
                )
            )

        with self.assertRaises(ValueError):
            validate_definition(
                _definition_for(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title"],
                        "properties": {
                            "title": {"type": "string"},
                        },
                    }
                )
            )

        with self.assertRaises(ValueError):
            validate_definition(
                _definition_for(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title"],
                        "properties": {
                            "title": {"type": "string", "description": "Title."},
                            "now": {
                                "type": "object",
                                "description": "Now payload.",
                                "required": ["next"],
                            },
                        },
                    }
                )
            )

        with self.assertRaises(ValueError):
            validate_definition(
                _definition_for(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title"],
                        "properties": {
                            "title": {"type": "string", "description": "Title."},
                            "refs": {
                                "type": "array",
                                "description": "Reference rows.",
                            },
                        },
                    }
                )
            )

        with self.assertRaises(ValueError):
            validate_definition(
                _definition_for(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["status"],
                        "properties": {
                            "status": {
                                "type": "string",
                                "description": "Task status.",
                            },
                        },
                    }
                )
            )

    def test_probe_tool_add_and_delete_use_only_tool_py_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            probe_root = Path(temp_dir) / "env" / "tools" / "probe"
            probe_root.mkdir(parents=True, exist_ok=True)
            (probe_root / "__init__.py").write_text('"""probe tool."""\n', encoding="utf-8")
            (probe_root / "tool.py").write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    from env.tool_runtime.definition import ActionDefinition, MUTATES_NONE, TASK_REQUIREMENT_FREE, ToolDefinition
                    from env.tool_runtime import results

                    DEFINITION = ToolDefinition(
                        id="probe",
                        title="Probe",
                        description="Probe tool",
                        scope="probe",
                        capability_boundary="probe boundary",
                        object_model="Probe objects are test-only validation rows.",
                        use_when=("testing",),
                        do_not_use_when=("you need durable runtime object mutation",),
                        actions=(
                            ActionDefinition(
                                name="ping",
                                title="probe.ping",
                                description="Echo payload message",
                                input_schema={
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["message"],
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "description": "Message to echo.",
                                        }
                                    },
                                },
                                output_schema={"$ref": "ToolResult"},
                                kind="read",
                                mutates=MUTATES_NONE,
                                task_requirement=TASK_REQUIREMENT_FREE,
                                required_permission="none",
                                authority="probe",
                                visibility="test-only probe",
                                durability="none",
                                result_content_level="probe row",
                                success_effect="Echoes one probe payload message without mutation.",
                                failure_state_guarantee="Rejected probe reads do not mutate runtime state.",
                                reads=("probe payload",),
                                writes=(),
                                does_not_write=("runtime objects",),
                                use_when=("echo one test payload",),
                                do_not_use_when=("you need runtime object mutation",),
                            ),
                        ),
                    )

                    def invoke(*, action, args, context):
                        if action != "ping":
                            raise ValueError(f"unsupported action: {action}")
                        return results.success(
                            tool="probe",
                            action="probe.ping",
                            active_actor=context.active_actor.to_payload(),
                            active_role=context.active_role,
                            effect_summary="Probe echoed one payload message.",
                            state_changed=False,
                            durability="none",
                            extra={"echo": args.get("message")},
                        )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (probe_root / "_impl.py").write_text(
                "def invoke(*, action, args, context):\n    raise AssertionError('probe tool should call tool.py invoke directly')\n",
                encoding="utf-8",
            )

            script = f"""
import importlib
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from env.tool_runtime import registry
import env.tools

probe_root = Path({str(Path(temp_dir) / "env" / "tools")!r})
env.tools.__path__.append(str(probe_root))
importlib.invalidate_caches()
registry.clear_cache()

supported_before = sorted(registry.supported_tools())
description = registry.env_tools_description().get("probe", {{}})
payload = registry.dispatch_env_tool_request(
    payload={{"tool": "probe", "action": "ping", "args": {{"message": "hello"}}}},
    active_role="dev",
    actor_id="act-dev-000000000002",
    instance_json=Path("instance.json"),
    instance_payload={{"actor_id": "act-dev-000000000002", "role": "dev", "workspace_dir": str(root)}},
    manifest={{"roles": [{{"id": "dev"}}]}},
    manifest_path=None,
)

env.tools.__path__.remove(str(probe_root))
importlib.invalidate_caches()
registry.clear_cache()
supported_after = sorted(registry.supported_tools())

print(json.dumps({{
    "supported_before": supported_before,
    "supported_after": supported_after,
    "probe_fields": description.get("payload_fields", {{}}).get("ping"),
    "response": payload,
}}, sort_keys=True))
"""
            completed = self._run_python(script)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertIn("probe", payload["supported_before"])
            self.assertNotIn("probe", payload["supported_after"])
            self.assertEqual(payload["probe_fields"], ["message"])
            self.assertTrue(payload["response"].get("ok"), msg=payload)
            self.assertEqual(payload["response"].get("echo"), "hello")

    def test_broken_non_selected_private_impl_does_not_block_selected_tool(self) -> None:
        script = """
import importlib.abc
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from env.tool_runtime.registry import dispatch_env_tool_request
import env_manifest

manifest = env_manifest.load_manifest(root / "buddyswitch" / "manifest.toml")

class BlockMessageImpl(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "env.tools.message._impl":
            raise RuntimeError("blocked message _impl import")
        return None

sys.meta_path.insert(0, BlockMessageImpl())

base = {
    "active_role": "dev",
    "actor_id": "act-dev-000000000001",
    "instance_json": root / "tmp-instance.json",
    "instance_payload": {
        "actor_id": "act-dev-000000000001",
        "role": "dev",
        "workspace_dir": str(root),
    },
    "manifest": manifest,
    "manifest_path": root / "buddyswitch" / "manifest.toml",
}
context = dispatch_env_tool_request(payload={"tool": "context", "action": "list_sources", "args": {}}, **base)
message = dispatch_env_tool_request(payload={"tool": "message", "action": "list", "args": {}}, **base)
print(json.dumps({"context": context, "message": message}, sort_keys=True))
"""
        completed = self._run_python(script)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        context = payload["context"]
        message = payload["message"]
        self.assertTrue(context.get("ok"), msg=context)
        self.assertFalse(message.get("ok"), msg=message)
        self.assertEqual((message.get("error") or {}).get("code"), "E_ENV_TOOL_DISPATCH")
        self.assertIs(message.get("state_changed"), False)
        self.assertIn("permission_boundary", message)
        self.assertIn("why_blocked", message)
        self.assertIn("retry_guidance", message)
        self.assertIn("allowed_next_actions", message)

    def test_legacy_env_tools_runtime_surfaces_are_removed(self) -> None:
        tools_root = ROOT / "scripts" / "env" / "tools"
        for file_name in sorted(LEGACY_SHARED_RUNTIME_FILES):
            self.assertFalse((tools_root / file_name).exists(), msg=f"legacy shared file still exists: {file_name}")
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            for file_name in sorted(LEGACY_TOOL_PUBLIC_FILES):
                self.assertFalse((package_dir / file_name).exists(), msg=f"legacy file still exists: {package_dir / file_name}")


if __name__ == "__main__":
    unittest.main()
