"""Black-box process proof for explicit ToolHost selection isolation."""

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


class ToolRuntimeProcessTests(unittest.TestCase):
    def _run_python(self, script: str) -> subprocess.CompletedProcess[str]:
        return run_process(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_registry_catalog_projects_exact_application_registrations(self) -> None:
        completed = self._run_python(
            """
import json
import sys

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime import registry

application = activate_application()
before = set(sys.modules)
registry.env_tools_description()
registry.operation_semantics()
loaded_by_projection = sorted(
    name
    for name in set(sys.modules) - before
    if name.endswith("._impl") and ".private.adapters.tool." in name
)
print(json.dumps({
    "application": sorted(row.definition.id for row in application.tools),
    "registry": sorted(registry.supported_tools()),
    "loaded_by_projection": loaded_by_projection,
}))
"""
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(set(payload["application"]), EXPECTED_TOOLS)
        self.assertEqual(set(payload["registry"]), EXPECTED_TOOLS)
        self.assertEqual(payload["loaded_by_projection"], [])

    def test_selected_implementation_failure_isolated_from_other_tools(self) -> None:
        completed = self._run_python(
            """
import importlib.abc
import json
import sys
from pathlib import Path

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime.registry import dispatch_env_tool_request

root = Path.cwd()
activate_application()

class BlockMessageImpl(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "buddyswitch.modules.communication.private.adapters.tool._impl":
            raise RuntimeError("blocked message _impl import")
        return None

sys.meta_path.insert(0, BlockMessageImpl())
base = {
    "active_role": "dev",
    "actor_id": "act-dev-tool-isolation",
    "instance_json": root / "tmp-instance.json",
    "instance_payload": {
        "actor_id": "act-dev-tool-isolation",
        "role": "dev",
        "workspace_dir": str(root),
    },
}
context = dispatch_env_tool_request(
    payload={"tool": "context", "action": "list_sources", "args": {}},
    **base,
)
message = dispatch_env_tool_request(
    payload={"tool": "message", "action": "list", "args": {}},
    **base,
)
print(json.dumps({"context": context, "message": message}, sort_keys=True))
"""
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        context = payload["context"]
        message = payload["message"]
        self.assertTrue(context.get("ok"), msg=context)
        self.assertFalse(message.get("ok"), msg=message)
        self.assertEqual(
            (message.get("error") or {}).get("code"),
            "E_ENV_TOOL_DISPATCH",
        )
        self.assertIs(message.get("state_changed"), False)
        self.assertIn("permission_boundary", message)
        self.assertIn("why_blocked", message)
        self.assertIn("retry_guidance", message)
        self.assertIn("allowed_next_actions", message)
