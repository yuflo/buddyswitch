#!/usr/bin/env python3
"""Repository consistency checks for current collaboration runtime contract."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import turn_runtime  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402

_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search"}


class RepoConsistencyTests(unittest.TestCase):
    def _scan(self, pattern: str) -> list[str]:
        targets = [
            "README.md",
            "AGENTS.md",
            "scripts",
            "buddyswitch",
            "tools/launcher/assets/buddies",
            "framework/contracts",
            "framework/schemas",
            "framework/console/app.js",
        ]
        completed = subprocess.run(
            ["rg", "-uuu", "-n", pattern, *targets, "-g", "!**/__pycache__/**", "-g", "!**/*.pyc"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        return [line for line in completed.stdout.splitlines() if line.strip()]

    def test_env_tool_surface_excludes_handoff(self) -> None:
        env_tools = turn_runtime._build_env_tools_desc()
        registry_tools = {row["tool"] for row in tool_contracts.TOOL_REGISTRY}
        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertEqual(set(env_tools), _EXPECTED_TOOLS)

        op = tool_contracts.operation_semantics()
        self.assertNotIn("track.advance", op)
        self.assertFalse(any(key.startswith("handoff.") for key in op))

    def test_workspace_projection_contract_excludes_handoffs(self) -> None:
        payload = json.loads((ROOT / "framework" / "contracts" / "workspace-projection.json").read_text(encoding="utf-8"))
        top = set(payload.get("top_level_key_order", []))
        self.assertNotIn("handoffs", top)
        self.assertIn("tracks", top)
        self.assertIn("tasks", top)
        self.assertIn("artifacts", top)

        sources = payload.get("data_sources", [])
        self.assertIsInstance(sources, list)
        self.assertFalse(any("handoffs" in str(row) for row in sources))

        track_shape = payload["view_shapes"]["track"]
        self.assertIn("owner_buddy", track_shape["key_order"])
        self.assertNotIn("current_buddy", track_shape["key_order"])
        self.assertNotIn("next_buddy", track_shape["key_order"])

    def test_role_contracts_exclude_handoff_runtime_object_and_track_advance(self) -> None:
        for name in ("pm", "design", "dev", "market", "test"):
            path = ROOT / "framework" / "contracts" / f"{name}.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(contract=name):
                self.assertNotIn("objects/handoffs", text)
                self.assertNotIn("track.advance", text)
                self.assertNotIn("next_buddy", text)

    def test_active_runtime_guidance_excludes_handoff_tool(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("handoff.*", readme)
        self.assertNotIn("handoff_id", readme)
        self.assertNotIn("objects/handoffs", readme)
        self.assertNotIn("objects/handoffs", agents)

    def test_runtime_buddy_agents_templates_exclude_handoff_wording(self) -> None:
        buddies = ("market", "pm", "design", "dev", "test")
        for buddy in buddies:
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(buddy=buddy):
                self.assertNotIn("handoff", text)
                self.assertNotIn("next handoff target", text)

    def test_track_collaboration_cleanup_residue_scan(self) -> None:
        hits = self._scan(r"handoff|next_buddy|current_buddy|track\.advance|readable_by_current_buddy")
        allowed: list[str] = []
        for line in hits:
            lower = line.lower()
            if "design-handoff" in lower:
                allowed.append(line)
                continue
            if "track-collaboration-cleanup" in lower:
                allowed.append(line)
                continue
            if "test_track_collaboration_cleanup_residue_scan" in lower:
                allowed.append(line)
                continue
        disallowed = [line for line in hits if line not in allowed]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_handoff_service_module_is_removed(self) -> None:
        self.assertFalse((ROOT / "scripts" / "env" / "services" / "handoffs.py").exists())


if __name__ == "__main__":
    unittest.main()
