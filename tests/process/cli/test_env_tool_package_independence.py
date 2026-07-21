"""Architecture tests for black-box env.tool package independence."""

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

from env.tool_runtime import registry as tool_registry  # noqa: E402
from tests.support.python import PYTHON  # noqa: E402

SHIPPED_TOOLS = {
    "task_sys",
    "demand_sys",
    "track",
    "artifact",
    "context",
    "evidence",
    "message",
    "search",
}
REQUIRED_TOOL_FILES = {"__init__.py", "tool.py", "_impl.py"}
RETIRED_TOOL_FILES = {"contract.py", "semantics.py", "cli.py", "handlers.py", "service.py"}
RETIRED_SHARED_RUNTIME_FILES = {"catalog.py", "cli_helpers.py", "discovery.py", "dispatch.py", "model.py", "responses.py", "router.py"}


class EnvToolPackageIndependenceTests(unittest.TestCase):
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

    def test_shipped_tool_packages_own_black_box_required_files(self) -> None:
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            with self.subTest(tool=tool):
                self.assertTrue(package_dir.is_dir(), msg=f"missing tool package dir: {package_dir}")
                present = {path.name for path in package_dir.iterdir() if path.is_file()}
                self.assertTrue(REQUIRED_TOOL_FILES.issubset(present), msg=f"{tool} files: {sorted(present)}")
                for retired in sorted(RETIRED_TOOL_FILES):
                    self.assertFalse((package_dir / retired).exists(), msg=f"retired file still exists: {package_dir / retired}")

    def test_no_legacy_shared_runtime_files_remain(self) -> None:
        shared_root = ROOT / "scripts" / "env" / "tools"
        for name in sorted(RETIRED_SHARED_RUNTIME_FILES):
            self.assertFalse((shared_root / name).exists(), msg=f"retired shared runtime file exists: {name}")

    def test_tool_packages_do_not_import_sibling_tools_or_host_forbidden_modules(self) -> None:
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
                            if name.startswith(("env.repos", "env.domain", "env_manifest", "runtime_kernel")):
                                violations.append(f"{rel}:{node.lineno}: import {name}")
                            if name.startswith("env.tools."):
                                parts = name.split(".")
                                if len(parts) >= 3 and parts[2] in SHIPPED_TOOLS and parts[2] != tool:
                                    violations.append(f"{rel}:{node.lineno}: import sibling tool {name}")
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module.startswith(("env.repos", "env.domain", "env_manifest", "runtime_kernel")):
                            violations.append(f"{rel}:{node.lineno}: from {module} import ...")
                        if module == "env.tools":
                            for alias in node.names:
                                if alias.name in SHIPPED_TOOLS and alias.name != tool:
                                    violations.append(f"{rel}:{node.lineno}: from env.tools import {alias.name}")
                        if module.startswith("env.tools."):
                            parts = module.split(".")
                            if len(parts) >= 3 and parts[2] in SHIPPED_TOOLS and parts[2] != tool:
                                violations.append(f"{rel}:{node.lineno}: from {module} import ...")
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_registry_projection_does_not_load_private_impl_repos_or_domains(self) -> None:
        script = """
import json
import sys
from env.tool_runtime import registry

tools = sorted(registry.supported_tools())
for tool in tools:
    registry.supported_actions(tool)
registry.env_tools_description()
registry.operation_semantics()
registry.compact_tool_affordances()
registry.tool_catalog_errors()

loaded_impl = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith("._impl"))
loaded_repos = sorted(name for name in sys.modules if name.startswith("env.repos."))
loaded_domains = sorted(name for name in sys.modules if name.startswith("env.domain."))
print(json.dumps({"tools": tools, "impl": loaded_impl, "repos": loaded_repos, "domains": loaded_domains}))
"""
        completed = self._run_python(script)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(set(payload["tools"]), SHIPPED_TOOLS)
        self.assertEqual(payload["impl"], [])
        self.assertEqual(payload["repos"], [])
        self.assertEqual(payload["domains"], [])

    def test_local_probe_tool_package_is_discovered_without_central_edits(self) -> None:
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
                        scope="probe tool",
                        capability_boundary="test only",
                        object_model="Probe objects are test-only package discovery rows.",
                        use_when=("testing package discovery",),
                        do_not_use_when=("you need runtime mutation",),
                        actions=(
                            ActionDefinition(
                                name="ping",
                                title="probe.ping",
                                description="Probe ping",
                                    input_schema={
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": [],
                                        "properties": {"message": {"type": "string", "description": "Probe message."}},
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
                                success_effect="Returns one probe ping response without mutation.",
                                failure_state_guarantee="Rejected probe reads do not mutate runtime state.",
                                reads=("probe payload",),
                                writes=(),
                                does_not_write=("runtime objects",),
                                use_when=("you need probe ping",),
                                do_not_use_when=("you need durable runtime mutation",),
                            ),
                        ),
                    )


                    def invoke(*, action, args, context):
                        return results.success(
                            tool="probe",
                            action="probe.ping",
                            active_actor=context.active_actor.to_payload(),
                            active_role=context.active_role,
                            effect_summary="Probe ping success.",
                            state_changed=False,
                            durability="none",
                            extra={"echo": args.get("message")},
                        )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (probe_root / "_impl.py").write_text('"""probe private implementation placeholder."""\n', encoding="utf-8")

            script = f"""
import importlib
import json
import sys
from pathlib import Path

root = Path.cwd()
import env.tools
from env.tool_runtime import registry

probe_root = Path({str(Path(temp_dir) / "env" / "tools")!r})
env.tools.__path__.append(str(probe_root))
importlib.invalidate_caches()
registry.clear_cache()

result = registry.dispatch_env_tool_request(
    payload={{"tool": "probe", "action": "ping", "args": {{"message": "hello"}}}},
    active_role="dev",
    actor_id="act-dev-000000000003",
    instance_json=Path("instance.json"),
    instance_payload={{"actor_id": "act-dev-000000000003", "role": "dev", "workspace_dir": str(root)}},
    manifest={{"roles": [{{"id": "dev"}}]}},
    manifest_path=None,
)
print(json.dumps({{
    "tools": sorted(registry.supported_tools()),
    "actions": sorted(registry.supported_actions("probe")),
    "fields": registry.env_tools_description()["probe"]["payload_fields"]["ping"],
    "response": result,
}}, sort_keys=True))
"""
            completed = self._run_python(script)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertIn("probe", payload["tools"])
            self.assertEqual(payload["actions"], ["ping"])
            self.assertEqual(payload["fields"], ["message"])
            self.assertTrue(payload["response"].get("ok"), msg=payload)
            self.assertEqual(payload["response"].get("echo"), "hello")
