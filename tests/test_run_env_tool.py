#!/usr/bin/env python3
"""Runless replacement tests for retired run env.tool surface."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_legacy_store as env_store  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402
from env.tools import router as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

_RETIRED_BUDDYBOX_FILE_ROWS_FIELD = "buddybox_" + "files"


class RunEnvToolReplacementTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        self.instance_json = self._runtime_path("instance.json")
        self.instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-runless",
                    "buddy": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _dispatch(self, *, tool: str, action: str, args: dict[str, object] | None = None, buddy: str = "pm") -> dict[str, object]:
        payload = {"tool": tool, "action": action, "args": args or {}}
        return tool_router.dispatch_env_tool_request(
            payload=payload,
            active_buddy=buddy,
            instance_id="inst-pm-runless",
            instance_json=self.instance_json,
            instance_payload={"instance_id": "inst-pm-runless", "buddy": buddy, "workspace_dir": str(self.runtime_root)},
            manifest=self.manifest,
            manifest_path=ROOT / "buddyswitch" / "manifest.toml",
        )

    def test_registry_excludes_retired_run_and_binding_tools(self) -> None:
        tools = set(tool_contracts.supported_tools())
        self.assertNotIn("run", tools)
        self.assertNotIn("binding", tools)
        self.assertIn("context", tools)
        self.assertNotIn("memory", tools)
        self.assertIn("buddybox", tools)

    def test_router_rejects_retired_run_tool(self) -> None:
        payload = self._dispatch(tool="run", action="commit")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["permission_boundary"], "env.tool")
        self.assertIn("unsupported", str(payload["error"]["message"]).lower())

    def test_context_summarize_exposes_runless_decision_surface(self) -> None:
        track = env_store.create_track("track-runless-router", "Runless Router", owner_buddy="pm")
        task = env_store.create_task("task-pm-router", "Prepare design intake", buddy="pm", track_id=track["id"])
        artifact = env_store.create_artifact_revision(
            artifact_id="art-pm-router-r1",
            title="Router PRD",
            summary="router artifact",
            body="v1",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=None,
        )
        env_store.publish_track_material(
            track_id=track["id"],
            artifact_id=artifact["id"],
            label="Router PRD",
            from_buddy="pm",
            summary="router artifact",
        )

        buddybox = self._runtime_path("buddyswitch/local/buddybox/pm")
        buddybox.mkdir(parents=True, exist_ok=True)
        (buddybox / "notes.md").write_text("# notes\n", encoding="utf-8")

        payload = self._dispatch(tool="context", action="summarize", args={})
        self.assertTrue(payload["ok"], msg=payload)
        decision_surface = payload["decision_surface"]
        self.assertEqual(decision_surface["binding_state"]["state"], "runless")
        self.assertNotIn("memory_summaries", payload)
        self.assertIn("buddybox_desc", payload)
        self.assertNotIn(_RETIRED_BUDDYBOX_FILE_ROWS_FIELD, payload)


if __name__ == "__main__":
    unittest.main()
