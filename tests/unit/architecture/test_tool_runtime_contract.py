"""Architecture tests for black-box env.tool runtime."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from buddyswitch.application.build import build_application
from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

FINAL_TOOL_RUNTIME_ROOT = ROOT / "src" / "buddyswitch" / "foundation" / "tool_runtime"
FINAL_DAEMON_CLIENT = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "client.py"
FINAL_ROLE_POLICY = ROOT / "src" / "buddyswitch" / "application" / "role_authority.py"
RETIRED_TOOL_RUNTIME_ROOT = ROOT / "src" / "buddyswitch" / "env" / "tool_runtime"
RETIRED_TOOL_PACKAGE_ROOT = ROOT / "src" / "buddyswitch" / "env" / "tools"


SHIPPED_TOOLS: dict[str, set[str]] = {
    "artifact": {"attach_file", "create_revision", "get", "get_attachment", "list", "list_attachments", "update_metadata"},
    "context": {"get", "list_sources", "summarize"},
    "demand_sys": {
        "complete",
        "get",
        "list",
        "resolve_inbound",
    },
    "evidence": {"approve_downgrade", "issue_browser"},
    "message": {"contacts", "conversation", "get", "list", "send"},
    "search": {"request", "status"},
    "task_sys": {"create", "list", "get", "cancel"},
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
EXPLICIT_COMPONENT_TOOL_IDS = frozenset(
    registration.definition.id
    for registration in build_application().tools
)
class ToolRuntimeArchitectureTests(unittest.TestCase):
    def test_foundation_toolhost_is_the_single_final_physical_owner(self) -> None:
        expected_runtime_files = {
            "__init__.py",
            "auth_feedback.py",
            "client.py",
            "context.py",
            "definition.py",
            "mcp_server.py",
            "native_mcp.py",
            "registry.py",
            "results.py",
        }
        actual_runtime_files = {
            path.name for path in FINAL_TOOL_RUNTIME_ROOT.glob("*.py")
        }

        self.assertEqual(actual_runtime_files, expected_runtime_files)
        self.assertTrue(FINAL_DAEMON_CLIENT.is_file())
        self.assertTrue(FINAL_ROLE_POLICY.is_file())
        self.assertFalse(RETIRED_TOOL_RUNTIME_ROOT.exists())
        self.assertFalse(RETIRED_TOOL_PACKAGE_ROOT.exists())
        self.assertFalse((ROOT / "src/buddyswitch/env/client.py").exists())
        self.assertFalse(
            (ROOT / "src/buddyswitch/launcher/env_tool_mcp_server.py").exists()
        )

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("src/buddyswitch/foundation/tool_runtime/definition.py", readme)
        self.assertNotIn("src/buddyswitch/env/tool_runtime", readme)

    def test_toolhost_exports_only_production_earned_contracts(self) -> None:
        from buddyswitch.foundation import tool_runtime
        from buddyswitch.foundation.tool_runtime import context
        from buddyswitch.foundation.tool_runtime import definition
        from buddyswitch.foundation.tool_runtime import native_mcp
        from buddyswitch.foundation.tool_runtime import registry
        from buddyswitch.foundation.tool_runtime import results
        from buddyswitch.application import role_authority

        self.assertEqual(set(tool_runtime.__all__), set())
        self.assertEqual(set(context.__all__), {"InvocationFact", "ToolContext"})
        self.assertEqual(
            set(definition.__all__),
            {
                "ActionDefinition",
                "AuthorizationDecision",
                "MUTATES_NONE",
                "MUTATES_RUNTIME_OBJECTS",
                "TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED",
                "TASK_REQUIREMENT_FREE",
                "ToolAuthorizer",
                "ToolDefinition",
                "ToolRegistration",
                "validate_definition",
                "validate_registration",
            },
        )
        self.assertEqual(
            set(registry.__all__),
            {
                "action_mutates",
                "compact_tool_affordances",
                "configure_active_task_probe",
                "configure_authorizer",
                "configure_role_runtime_resolver",
                "configure_tool_registrations",
                "dispatch_env_tool_request",
                "env_tools_description",
                "get_action_definition",
                "get_definition",
                "operation_semantics",
                "role_action_summary",
                "supported_actions",
                "supported_tools",
                "tool_catalog_errors",
            },
        )
        self.assertEqual(
            set(native_mcp.__all__),
            {
                "bound_capability_env",
                "encode_native_tool_name",
                "list_native_tool_specs",
                "resolve_native_tool_name",
            },
        )
        self.assertEqual(
            set(results.__all__),
            {"alternative_capability", "next_action_option", "rejection", "success"},
        )
        self.assertTrue(hasattr(role_authority, "RoleAuthority"))

        for module, names in (
            (
                context,
                (
                    "ActorDirectoryAccess",
                    "ActorIdentityProfile",
                    "IdentityRef",
                    "SignalDeliveryAccess",
                    "default_manifest_path",
                ),
            ),
            (
                definition,
                (
                    "MUTATES_BROKER_TOKEN",
                    "MUTATES_BROWSER_SESSION",
                    "MUTATES_RUNTIME_FILES",
                    "ToolInvoke",
                ),
            ),
            (
                registry,
                (
                    "_action_spec_row",
                    "load_definition",
                    "payload_fields_for_action",
                    "semantic_contract_errors",
                ),
            ),
            (results, ("follow_up_affordance", "tool_affordance")),
            (
                role_authority,
                (
                    "COMMON_ROLE_PERMISSIONS",
                    "ROLE_PERMISSION_ADDITIONS",
                    "allowed_permissions_for_role",
                    "allowed_roles_for_permission",
                ),
            ),
        ):
            for name in names:
                with self.subTest(module=module.__name__, name=name):
                    self.assertFalse(hasattr(module, name))

        success_parameters = inspect.signature(results.success).parameters
        for unearned_parameter in (
            "active_actor",
            "allowed_next_action_options",
            "binding_changed",
            "follow_up_affordances",
            "validation_only",
        ):
            with self.subTest(unearned_parameter=unearned_parameter):
                self.assertNotIn(unearned_parameter, success_parameters)

        rejection_parameters = inspect.signature(results.rejection).parameters
        for unearned_parameter in ("error_class", "mutates_product_state"):
            with self.subTest(unearned_rejection_parameter=unearned_parameter):
                self.assertNotIn(unearned_parameter, rejection_parameters)

        registry_source = (FINAL_TOOL_RUNTIME_ROOT / "registry.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("runtime load errors", registry_source)

    def test_foundation_toolhost_has_no_discovery_component_or_role_import(self) -> None:
        self.assertTrue(FINAL_TOOL_RUNTIME_ROOT.is_dir())
        violations: list[str] = []
        forbidden_import_prefixes = (
            "buddyswitch.env.tool_runtime",
            "buddyswitch.env.tools",
            "buddyswitch.modules",
            "buddyswitch.application.role_authority",
        )
        for path in sorted(FINAL_TOOL_RUNTIME_ROOT.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            relative = path.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(forbidden_import_prefixes):
                            violations.append(
                                f"{relative}:{node.lineno}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith(forbidden_import_prefixes):
                        violations.append(
                            f"{relative}:{node.lineno}: from {module} import ..."
                        )
            for retired_term in (
                "discover_tool_ids",
                "pkgutil.iter_modules",
                "importlib.import_module",
                "buddyswitch.env.tools",
            ):
                if retired_term in source:
                    violations.append(f"{relative}: contains {retired_term}")

        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_application_injects_role_authority_and_adapters_use_narrow_context(self) -> None:
        application_source = (
            ROOT / "src/buddyswitch/application/build.py"
        ).read_text(encoding="utf-8")
        artifact_source = (
            ROOT / "src/buddyswitch/modules/artifact/private/state/artifacts.py"
        ).read_text(encoding="utf-8")
        evidence_source = (
            ROOT / "src/buddyswitch/modules/evidence/private/adapters/tool/_impl.py"
        ).read_text(encoding="utf-8")

        self.assertIn("registry.configure_authorizer(application.role_authority.authorize)", application_source)
        self.assertIn("registry.configure_role_runtime_resolver(application.role_host.runtime)", application_source)
        self.assertIn("context.actor_private_root", artifact_source)
        self.assertNotIn("context.repos", artifact_source)
        self.assertIn("context.now()", evidence_source)
        self.assertNotIn("context.repos", evidence_source)

    def test_component_tools_are_explicitly_contributed_exactly_once(self) -> None:
        from buddyswitch.foundation.tool_runtime import registry

        application = build_application()
        tool_ids = [registration.definition.id for registration in application.tools]
        self.assertEqual(set(tool_ids), set(SHIPPED_TOOLS))
        self.assertEqual(len(tool_ids), len(set(tool_ids)))
        self.assertEqual(registry.supported_tools(), set(SHIPPED_TOOLS))
        for registration in application.tools:
            tool_id = registration.definition.id
            self.assertEqual(registration.definition.id, tool_id)
            self.assertTrue(callable(registration.invoke))
            self.assertEqual(
                {action.name for action in registration.definition.actions},
                SHIPPED_TOOLS[tool_id],
            )

    def test_invalid_and_duplicate_registrations_fail_without_replacing_catalog(self) -> None:
        from buddyswitch.foundation.tool_runtime import registry
        from buddyswitch.foundation.tool_runtime.definition import ToolRegistration

        registration = build_application().tools[0]
        before = registry.supported_tools()
        with self.assertRaisesRegex(ValueError, "duplicate explicit tool registration"):
            registry.configure_tool_registrations((registration, registration))
        with self.assertRaisesRegex(ValueError, "must be callable"):
            registry.configure_tool_registrations(
                (
                    ToolRegistration(
                        definition=registration.definition,
                        invoke=None,  # type: ignore[arg-type]
                    ),
                )
            )
        self.assertEqual(registry.supported_tools(), before)

    def test_registry_projects_catalog_semantics_payload_fields_and_cli_actions_from_definitions(self) -> None:
        from buddyswitch.foundation.tool_runtime import registry

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
                self.assertIn(f"{tool}.{action}", semantics)
    def test_definition_validation_rejects_incomplete_input_contracts(self) -> None:
        from buddyswitch.foundation.tool_runtime.definition import ActionDefinition
        from buddyswitch.foundation.tool_runtime.definition import MUTATES_NONE
        from buddyswitch.foundation.tool_runtime.definition import TASK_REQUIREMENT_FREE
        from buddyswitch.foundation.tool_runtime.definition import ToolDefinition
        from buddyswitch.foundation.tool_runtime.definition import validate_definition

        def _definition_for(schema: dict[str, object]) -> ToolDefinition:
            return ToolDefinition(
                id="probe",
                title="Probe",
                description="Probe validation.",
                scope="probe scope",
                capability_boundary="probe boundary",
                object_model="Probe objects are test-only validation rows.",
                use_when=("testing",),
                do_not_use_when=("not for runtime use",),
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
                        use_when=("testing",),
                        do_not_use_when=("not for runtime use",),
                    ),
                ),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"probe\.ping\.input_schema\.required must be a list",
        ):
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

        with self.assertRaisesRegex(
            ValueError,
            r"probe\.ping\.input_schema\.properties\.title\.description must be a non-empty string",
        ):
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

        with self.assertRaisesRegex(
            ValueError,
            r"probe\.ping\.input_schema\.properties\.now\.additionalProperties must be false",
        ):
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

        with self.assertRaisesRegex(
            ValueError,
            r"probe\.ping\.input_schema\.properties\.refs\.items must be an object",
        ):
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

        with self.assertRaisesRegex(
            ValueError,
            r"probe\.ping\.input_schema\.properties\.status\.enum must be a non-empty list",
        ):
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
