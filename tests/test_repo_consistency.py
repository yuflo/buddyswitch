#!/usr/bin/env python3
"""Repository consistency checks for active track-page collaboration runtime."""

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

_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}


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
            "tests",
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

    def test_env_tool_surface_uses_track_page_actions(self) -> None:
        env_tools = turn_runtime._build_env_tools_desc()
        registry_tools = {row["tool"] for row in tool_contracts.TOOL_REGISTRY}
        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertEqual(set(env_tools), _EXPECTED_TOOLS)

        track_actions = set(tool_contracts.supported_actions("track"))
        self.assertEqual(
            track_actions,
            {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
        )
        artifact_actions = set(tool_contracts.supported_actions("artifact"))
        self.assertEqual(artifact_actions, {"get", "create_revision", "update_metadata"})

    def test_workspace_projection_contract_uses_track_page_shape(self) -> None:
        payload = json.loads((ROOT / "framework" / "contracts" / "workspace-projection.json").read_text(encoding="utf-8"))
        top = set(payload.get("top_level_key_order", []))
        self.assertIn("tracks", top)
        self.assertIn("tasks", top)
        self.assertIn("artifacts", top)
        self.assertNotIn("handoffs", top)

        track_keys = set(payload["view_shapes"]["track"]["key_order"])
        self.assertIn("outcome", track_keys)
        self.assertIn("state", track_keys)
        self.assertIn("health", track_keys)
        self.assertIn("shared_materials", track_keys)
        self.assertNotIn("task_ids", track_keys)
        self.assertNotIn("tasks", track_keys)

        task_keys = set(payload["view_shapes"]["task"]["key_order"])
        self.assertNotIn("artifact_ids", task_keys)
        self.assertNotIn("artifact" + "_slots", task_keys)

        artifact_keys = set(payload["view_shapes"]["artifact"]["key_order"])
        self.assertIn("published_to_track", artifact_keys)
        self.assertNotIn("task_id", artifact_keys)

    def test_role_contracts_teach_direct_track_material_path(self) -> None:
        for name in ("pm", "design", "dev", "market", "test"):
            path = ROOT / "framework" / "contracts" / f"{name}.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(contract=name):
                self.assertIn("track.open", text)
                self.assertNotIn("track" + ".join", text)
                self.assertNotIn("attach" + "_task", text)
                self.assertNotIn("detach" + "_task", text)
                if name == "pm":
                    self.assertIn("artifact.create_revision", text)
                    self.assertIn("track.add_material", text)
                    self.assertIn("track.add_proof", text)
                    self.assertNotIn("published_to_track", text)

    def test_runtime_buddy_agents_use_track_open_guidance(self) -> None:
        buddies = ("market", "pm", "design", "dev", "test")
        for buddy in buddies:
            path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
            text = path.read_text(encoding="utf-8").lower()
            with self.subTest(buddy=buddy):
                self.assertIn("track open --track-id", text)
                self.assertNotIn("track get --track-id", text)
                self.assertNotIn("track join", text)
                self.assertNotIn("attach" + "-task", text)
                self.assertNotIn("detach" + "-task", text)

    def test_role_rebuild_residue_scan(self) -> None:
        pattern_1 = (
            "track\\." + "join"
            + "|attach" + "_task"
            + "|detach" + "_task"
            + "|attach" + "-task"
            + "|detach" + "-task"
            + "|track" + "_task"
            + "|readable_by_current" + "_buddy"
        )
        pattern_2 = (
            "track\\." + "task_ids"
            + "|artifact\\." + "task_id"
            + "|artifact" + "_slots"
            + "|source_" + "task_id"
        )
        pattern_3 = (
            "current-task" + "-id"
            + "|task_id" + "_scope"
            + "|[Cc]ompatibility" + " facade"
        )
        hits_1 = self._scan(pattern_1)
        hits_2 = self._scan(pattern_2)
        hits_3 = self._scan(pattern_3)
        hits = hits_1 + hits_2 + hits_3
        allowed: list[str] = []
        for line in hits:
            lower = line.lower()
            if "design-handoff" in lower:
                allowed.append(line)
                continue
            if "test_role_rebuild_residue_scan" in lower:
                allowed.append(line)
                continue
            if line.startswith("tests/"):
                allowed.append(line)
                continue
            if "/docs/spec/" in lower or "/docs/memo/" in lower:
                allowed.append(line)
                continue
            if line.startswith("scripts/artifact_selection.py:"):
                allowed.append(line)
                continue
            if line.startswith("scripts/workspace_data.py:"):
                allowed.append(line)
                continue
        disallowed = [line for line in hits if line not in allowed]
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_track_artifact_publication_residue_scan(self) -> None:
        pattern = (
            "kind=prd"
            + "|content\\.prd"
            + "|track\\.join"
            + "|attach_task"
            + "|detach_task"
            + "|attach-task"
            + "|detach-task"
        )
        hits = self._scan(pattern)
        disallowed: list[str] = []
        for line in hits:
            lower = line.lower()
            if line.startswith("tests/"):
                continue
            if "/docs/spec/" in lower or "/docs/memo/" in lower or "/docs/bitter/" in lower:
                continue
            disallowed.append(line)
        self.assertEqual(disallowed, [], msg="\n".join(disallowed))

    def test_active_cli_guidance_has_no_payload_file_route(self) -> None:
        targets = [
            "AGENTS.md",
            "buddyswitch/skills",
            "framework/contracts",
            "tools/launcher/assets/buddies",
            "scripts/env/client.py",
        ]
        completed = subprocess.run(
            [
                "rg",
                "-uuu",
                "-n",
                "payload file|--payload /tmp|--payload <json-file>|--payload <file>|PAYLOAD_JSON_FILE",
                *targets,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        hits = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(hits, [], msg="\n".join(hits))


if __name__ == "__main__":
    unittest.main()
