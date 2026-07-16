"""Architecture tests for black-box env.tool runtime."""

from __future__ import annotations

import ast
import importlib
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"


SHIPPED_TOOLS: dict[str, set[str]] = {
    "artifact": {"attach_file", "create_revision", "get", "get_attachment", "list", "list_attachments", "update_metadata"},
    "context": {"get", "list_sources", "summarize"},
    "evidence": {"approve_downgrade", "issue_browser"},
    "message": {"contacts", "conversation", "get", "list", "mark", "send"},
    "search": {"request", "status"},
    "task_sys": {"list", "get", "close", "cancel", "need_parent"},
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




class ToolRuntimeArchitectureTests(unittest.TestCase):
    def _tool_dir(self, tool: str) -> Path:
        return ROOT / "scripts" / "env" / "tools" / tool
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
    def test_legacy_env_tools_runtime_surfaces_are_removed(self) -> None:
        tools_root = ROOT / "scripts" / "env" / "tools"
        for file_name in sorted(LEGACY_SHARED_RUNTIME_FILES):
            self.assertFalse((tools_root / file_name).exists(), msg=f"legacy shared file still exists: {file_name}")
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            for file_name in sorted(LEGACY_TOOL_PUBLIC_FILES):
                self.assertFalse((package_dir / file_name).exists(), msg=f"legacy file still exists: {package_dir / file_name}")
