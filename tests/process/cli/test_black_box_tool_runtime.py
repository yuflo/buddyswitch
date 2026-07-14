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

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from tests.support.python import PYTHON  # noqa: E402

SHIPPED_TOOLS: dict[str, set[str]] = {
    "artifact": {"attach_file", "create_revision", "get", "get_attachment", "list", "list_attachments", "update_metadata"},
    "context": {"get", "list_sources", "summarize"},
    "evidence": {"approve_downgrade", "issue_browser"},
    "message": {"contacts", "conversation", "get", "list", "mark", "send"},
    "search": {"request", "status"},
    "task_sys": {"list", "get", "update_task_analysis", "close", "need_parent"},
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




class ToolRuntimeProcessTests(unittest.TestCase):
    def _tool_dir(self, tool: str) -> Path:
        return ROOT / "scripts" / "env" / "tools" / tool
    def _run_python(self, script: str) -> subprocess.CompletedProcess[str]:
        return run_process(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    def test_registry_catalog_loads_definitions_without_private_implementations(self) -> None:
        script = """
import json
import sys
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
    def test_broken_non_selected_private_impl_does_not_block_selected_tool(self) -> None:
        script = """
import importlib.abc
import json
import sys
from pathlib import Path

root = Path.cwd()

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
from pathlib import Path

root = Path.cwd()

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

