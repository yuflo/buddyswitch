#!/usr/bin/env python3
"""Architecture tests for per-tool independent env.tool packages."""

from __future__ import annotations

import ast
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

SHIPPED_TOOLS = {
    "task",
    "track",
    "artifact",
    "buddybox",
    "context",
    "evidence",
    "message",
    "comment",
    "search",
}
REQUIRED_TOOL_FILES = {"__init__.py", "contract.py", "semantics.py", "cli.py", "handlers.py", "service.py"}


class EnvToolPackageIndependenceTests(unittest.TestCase):
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

    def test_shipped_tool_packages_own_required_files(self) -> None:
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            with self.subTest(tool=tool):
                self.assertTrue(package_dir.is_dir(), msg=f"missing tool package dir: {package_dir}")
                present = {path.name for path in package_dir.iterdir() if path.is_file()}
                self.assertTrue(REQUIRED_TOOL_FILES.issubset(present), msg=f"{tool} files: {sorted(present)}")
                for required in sorted(REQUIRED_TOOL_FILES):
                    file_path = package_dir / required
                    self.assertGreater(file_path.stat().st_size, 0, msg=f"empty required file: {file_path}")

    def test_no_central_tool_ownership_tables_remain(self) -> None:
        contracts_py = ROOT / "scripts" / "env" / "tools" / "contracts.py"
        semantics_py = ROOT / "scripts" / "env" / "tools" / "semantics.py"
        dispatch_py = ROOT / "scripts" / "env" / "tools" / "dispatch.py"
        client_py = ROOT / "scripts" / "env" / "client.py"

        self.assertFalse(contracts_py.exists(), msg=str(contracts_py))
        self.assertFalse(semantics_py.exists(), msg=str(semantics_py))

        dispatch_source = dispatch_py.read_text(encoding="utf-8")
        self.assertNotIn("HANDLER_SPECS_BY_TOOL", dispatch_source)

        client_source = client_py.read_text(encoding="utf-8")
        for tool in sorted(SHIPPED_TOOLS):
            self.assertNotIn(f"_dispatch_{tool}", client_source)

        tool_root = ROOT / "scripts" / "env" / "tools"
        violations: list[str] = []
        for path in sorted(tool_root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            if "TOOL_REGISTRY" in source:
                violations.append(f"{rel}: contains TOOL_REGISTRY")
            if "_CAPABILITIES" in source:
                violations.append(f"{rel}: contains _CAPABILITIES")
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_tool_packages_do_not_import_sibling_tool_packages(self) -> None:
        violations: list[str] = []
        for tool in sorted(SHIPPED_TOOLS):
            package_dir = self._tool_dir(tool)
            if not package_dir.is_dir():
                violations.append(f"missing package dir: {package_dir.relative_to(ROOT)}")
                continue
            for path in sorted(package_dir.rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                rel = path.relative_to(ROOT).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("env.tools."):
                                parts = alias.name.split(".")
                                if len(parts) >= 3:
                                    other = parts[2]
                                    if other in SHIPPED_TOOLS and other != tool:
                                        violations.append(f"{rel}:{node.lineno}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module == "env.tools":
                            for alias in node.names:
                                other = alias.name
                                if other in SHIPPED_TOOLS and other != tool:
                                    violations.append(f"{rel}:{node.lineno}: from env.tools import {other}")
                        elif module.startswith("env.tools."):
                            parts = module.split(".")
                            if len(parts) >= 3:
                                other = parts[2]
                                if other in SHIPPED_TOOLS and other != tool:
                                    violations.append(f"{rel}:{node.lineno}: from {module} import ...")
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_public_imports_do_not_load_tool_services(self) -> None:
        script = """
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import env.client
import env.tools.catalog
import env.tools.dispatch
import env.tools.router

loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith(".service"))
print(json.dumps(loaded))
"""
        completed = self._run_python(script)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(json.loads(completed.stdout), [])

    def test_catalog_projection_does_not_load_services_repos_or_domains(self) -> None:
        script = """
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from env.tools import catalog

tools = sorted(catalog.supported_tools())
for tool in tools:
    catalog.supported_actions(tool)
catalog.env_tools_description()
catalog.operation_semantics()
catalog.compact_tool_affordances()
catalog.semantic_contract_errors()

loaded_services = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith(".service"))
loaded_repos = sorted(name for name in sys.modules if name.startswith("env.repos."))
loaded_domains = sorted(name for name in sys.modules if name.startswith("env.domain."))
print(json.dumps({"tools": tools, "services": loaded_services, "repos": loaded_repos, "domains": loaded_domains}))
"""
        completed = self._run_python(script)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(set(payload["tools"]), SHIPPED_TOOLS)
        self.assertEqual(payload["services"], [])
        self.assertEqual(payload["repos"], [])
        self.assertEqual(payload["domains"], [])

    def test_local_probe_tool_package_is_discovered_without_central_edits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            probe_root = Path(temp_dir) / "env_tools_probe"
            package = probe_root / "probe"
            package.mkdir(parents=True, exist_ok=True)

            (package / "__init__.py").write_text('"""probe tool."""\n', encoding="utf-8")
            (package / "contract.py").write_text(
                textwrap.dedent(
                    """
                    TOOL_ID = "probe"
                    TOOL_SPEC = {
                        "tool": TOOL_ID,
                        "cli_resource": "probe",
                        "command": "python3 scripts/env/client.py probe ping",
                        "scope": "probe tool",
                        "actions": [
                            {
                                "name": "ping",
                                "payload_fields": ["message"],
                                "kind": "read",
                                "mutates": "none",
                                "required_permission": "none",
                                "authority": "probe",
                                "preconditions": [],
                                "returns": ["echo"],
                            }
                        ],
                    }
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (package / "semantics.py").write_text(
                textwrap.dedent(
                    """
                    CAPABILITY = {
                        "title": "Probe",
                        "plain_description": "Probe tool",
                        "use_when": ["testing package discovery"],
                        "do_not_use_when": [],
                        "capability_boundary": "test only",
                    }

                    ACTION_SEMANTICS = {
                        "ping": {
                            "title": "probe.ping",
                            "plain_description": "Probe ping",
                            "use_when": ["testing"],
                            "do_not_use_when": [],
                            "inputs_explained": {"message": "echo payload"},
                            "side_effects": {
                                "mutates": "none",
                                "writes": [],
                                "does_not_write": [],
                                "durability": "none",
                                "idempotency": "idempotent read",
                            },
                            "risk_hints": {
                                "read_only": True,
                                "destructive": False,
                                "idempotent": True,
                                "open_world": False,
                                "requires_human_approval": False,
                                "external_effect": False,
                            },
                            "success_means": "Echo returned.",
                            "common_failures": [],
                        }
                    }
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (package / "handlers.py").write_text(
                'HANDLER_SPECS = {"ping": ("env.tools.probe.service", "probe_ping")}\n',
                encoding="utf-8",
            )
            (package / "cli.py").write_text(
                textwrap.dedent(
                    """
                    import argparse

                    TOOL_ID = "probe"


                    def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
                        parser = subparsers.add_parser("probe", help="Probe operations")
                        probe_sub = parser.add_subparsers(dest="operation", required=True)
                        ping = probe_sub.add_parser("ping", help="Probe ping")
                        ping.add_argument("--message")
                        ping.set_defaults(_env_tool=TOOL_ID, _env_action="ping", _env_payload_builder=_payload)


                    def _payload(args: argparse.Namespace) -> dict[str, str]:
                        payload = {}
                        if isinstance(getattr(args, "message", None), str):
                            payload["message"] = args.message
                        return payload
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (package / "service.py").write_text(
                textwrap.dedent(
                    """
                    def probe_ping(*, args, context):
                        return {
                            "ok": True,
                            "tool": "probe",
                            "action": "probe.ping",
                            "state_changed": False,
                            "echo": args.get("message"),
                        }
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            script = f"""
import importlib
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import env.tools
env.tools.__path__.append({str(probe_root)!r})
importlib.invalidate_caches()

from env.tools import catalog
from env.tools.router import dispatch_env_tool_request

result = dispatch_env_tool_request(
    payload={{"tool": "probe", "action": "ping", "args": {{"message": "hello"}}}},
    active_buddy="dev",
    instance_id="inst-probe",
    instance_json=Path("instance.json"),
    instance_payload={{"instance_id": "inst-probe", "buddy": "dev", "workspace_dir": str(root)}},
    manifest={{"buddies": []}},
    manifest_path=None,
)

print(
    json.dumps(
        {{
            "tools": sorted(catalog.supported_tools()),
            "actions": sorted(catalog.supported_actions("probe")),
            "fields": catalog.env_tools_description()["probe"]["payload_fields"]["ping"],
            "response": result,
        }},
        sort_keys=True,
    )
)
"""
            completed = self._run_python(script)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertIn("probe", payload["tools"])
            self.assertEqual(payload["actions"], ["ping"])
            self.assertEqual(payload["fields"], ["message"])
            self.assertTrue(payload["response"].get("ok"), msg=payload)
            self.assertEqual(payload["response"].get("echo"), "hello")

    def test_broken_non_selected_tool_metadata_is_reported_without_blocking_healthy_tool(self) -> None:
        script = f"""
import importlib.abc
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import env_manifest

class BlockMessageContract(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "env.tools.message.contract":
            raise RuntimeError("blocked message contract import")
        return None

sys.meta_path.insert(0, BlockMessageContract())

from env.tools import catalog
from env.tools.router import dispatch_env_tool_request

manifest_path = Path({str(ROOT / "buddyswitch" / "manifest.toml")!r})
instance_json = root / "tmp" / "independence-instance.json"
instance_json.parent.mkdir(parents=True, exist_ok=True)
instance_json.write_text(
    json.dumps(
        {{
            "instance_id": "inst-independence",
            "buddy": "dev",
            "status": "active",
            "workspace_dir": str(root),
            "browser_port": None,
        }},
        ensure_ascii=True,
    ) + "\\n",
    encoding="utf-8",
)
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))

task_result = dispatch_env_tool_request(
    payload={{"tool": "task", "action": "list", "args": {{}}}},
    active_buddy="dev",
    instance_id="inst-independence",
    instance_json=instance_json,
    instance_payload=instance_payload,
    manifest=env_manifest.load_manifest(manifest_path),
    manifest_path=manifest_path,
)
message_result = dispatch_env_tool_request(
    payload={{"tool": "message", "action": "list", "args": {{}}}},
    active_buddy="dev",
    instance_id="inst-independence",
    instance_json=instance_json,
    instance_payload=instance_payload,
    manifest=env_manifest.load_manifest(manifest_path),
    manifest_path=manifest_path,
)
print(
    json.dumps(
        {{
            "errors": catalog.tool_catalog_errors(),
            "task": task_result,
            "message": message_result,
        }},
        sort_keys=True,
    )
)
"""
        completed = self._run_python(script)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        errors = payload.get("errors", [])
        self.assertTrue(any(isinstance(row, dict) and row.get("tool") == "message" for row in errors), msg=payload)
        task = payload.get("task", {})
        self.assertTrue(task.get("ok"), msg=payload)
        message = payload.get("message", {})
        self.assertFalse(message.get("ok"), msg=payload)
        self.assertIn((message.get("error") or {}).get("code"), {"E_ENV_TOOL_DISPATCH", "E_ENV_TOOL_CATALOG"})
        self.assertIs(message.get("state_changed"), False)


if __name__ == "__main__":
    unittest.main()
