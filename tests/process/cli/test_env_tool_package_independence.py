"""Process proof for explicit-only Foundation ToolHost registration."""

from __future__ import annotations

import json
import subprocess
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.python import PYTHON


ROOT = REPO_ROOT
EXPECTED_TOOLS = {
    "artifact",
    "context",
    "demand_sys",
    "evidence",
    "message",
    "search",
    "task_sys",
    "track",
}


class ExplicitToolRegistrationProcessTests(unittest.TestCase):
    def _run_python(self, script: str) -> subprocess.CompletedProcess[str]:
        return run_process(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_application_catalog_is_explicit_and_projection_loads_no_tool_impl(self) -> None:
        completed = self._run_python(
            """
import json
import sys

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime import registry

activate_application()
before = set(sys.modules)
tools = sorted(registry.supported_tools())
registry.env_tools_description()
registry.operation_semantics()
registry.compact_tool_affordances()
registry.tool_catalog_errors()
loaded_by_projection = sorted(
    name
    for name in set(sys.modules) - before
    if name.endswith("._impl")
    and ".private.adapters.tool." in name
)
print(json.dumps({"tools": tools, "loaded_by_projection": loaded_by_projection}))
"""
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(set(payload["tools"]), EXPECTED_TOOLS)
        self.assertEqual(payload["loaded_by_projection"], [])

    def test_explicit_probe_registration_drives_catalog_schema_and_dispatch(self) -> None:
        completed = self._run_python(
            """
import json
from pathlib import Path

from buddyswitch.foundation.tool_runtime import registry, results
from buddyswitch.foundation.tool_runtime.definition import (
    ActionDefinition,
    MUTATES_NONE,
    TASK_REQUIREMENT_FREE,
    ToolDefinition,
    ToolRegistration,
)
from buddyswitch.runtime_support import role_auth

definition = ToolDefinition(
    id="probe",
    title="Probe",
    description="Explicit registration probe.",
    scope="test-only probe",
    capability_boundary="test-only explicit registration",
    object_model="Probe rows exist only for this process proof.",
    use_when=("testing explicit registration",),
    do_not_use_when=("running product work",),
    actions=(
        ActionDefinition(
            name="ping",
            title="probe.ping",
            description="Echo one probe message.",
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
            authority="test-only",
            visibility="test-only",
            durability="none",
            result_content_level="probe row",
            success_effect="Returns one probe echo without mutation.",
            failure_state_guarantee="Rejected probes do not mutate state.",
            reads=("probe payload",),
            writes=(),
            does_not_write=("runtime objects",),
            use_when=("testing explicit registration",),
            do_not_use_when=("running product work",),
        ),
    ),
)

def invoke(*, action, args, context):
    return results.success(
        tool="probe",
        action=f"probe.{action}",
        current_identity=context.current_identity.to_payload(),
        active_role=context.role_id,
        effect_summary="Probe ping succeeded.",
        state_changed=False,
        durability="none",
        extra={"echo": args.get("message")},
    )

registry.configure_authorizer(role_auth.authorize)
registry.configure_tool_registrations(
    (ToolRegistration(definition=definition, invoke=invoke),)
)
response = registry.dispatch_env_tool_request(
    payload={"tool": "probe", "action": "ping", "args": {"message": "hello"}},
    active_role="dev",
    actor_id="act-dev-explicit-probe",
    instance_json=Path("instance.json"),
    instance_payload={"workspace_dir": str(Path.cwd())},
    manifest={"roles": [{"id": "dev"}]},
)
print(json.dumps({
    "tools": sorted(registry.supported_tools()),
    "actions": sorted(registry.supported_actions("probe")),
    "fields": registry.env_tools_description()["probe"]["payload_fields"]["ping"],
    "response": response,
}, sort_keys=True))
"""
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["tools"], ["probe"])
        self.assertEqual(payload["actions"], ["ping"])
        self.assertEqual(payload["fields"], ["message"])
        self.assertTrue(payload["response"].get("ok"), msg=payload)
        self.assertEqual(payload["response"].get("echo"), "hello")
