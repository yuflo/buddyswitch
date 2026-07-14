"""Runless replacement tests for retired run env.tool surface."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import env_manifest  # noqa: E402
import env_legacy_store as env_store  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

_RETIRED_ACTOR_PRIVATE_FILE_ROWS_FIELD = "actor_private_" + "files"


class RunEnvToolReplacementTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        self.actor_id = self._runtime_actor_id(role="pm", label="act-pm-runless")
        self.instance_json = self._runtime_path("instance.json")
        self.instance_json.write_text(
            json.dumps(
                {
                    "actor_id": self.actor_id,
                    "role": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _dispatch(self, *, tool: str, action: str, args: dict[str, object] | None = None, role: str = "pm") -> dict[str, object]:
        payload = {"tool": tool, "action": action, "args": args or {}}
        actor_id = self._runtime_actor_id(role=role, label="act-pm-runless")
        return tool_router.dispatch_env_tool_request(
            payload=payload,
            active_role=role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload={"actor_id": actor_id, "role": role, "workspace_dir": str(self.runtime_root)},
            manifest=self.manifest,
            manifest_path=ROOT / "buddyswitch" / "manifest.toml",
        )

    def test_registry_excludes_retired_run_and_binding_tools(self) -> None:
        tools = set(tool_catalog.supported_tools())
        self.assertNotIn("run", tools)
        self.assertNotIn("binding", tools)
        self.assertIn("context", tools)
        self.assertNotIn("memory", tools)
        self.assertNotIn("actor_private", tools)

    def test_router_rejects_retired_run_tool(self) -> None:
        payload = self._dispatch(tool="run", action="commit")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["permission_boundary"], "env.tool")
        self.assertIn("unsupported", str(payload["error"]["message"]).lower())

    def test_context_summarize_exposes_runless_decision_surface(self) -> None:
        track = env_store.create_track(
            "track-runless-router",
            "Runless Router",
            owner_actor={"actor_id": "act-pm-runless", "role_id": "pm"},
            outcome="Runless router outcome",
            now={"next": "seed", "blocker": None},
        )
        self._write_task_sys_task(
            actor_id="act-pm-runless",
            role="pm",
            task_slug="task-pm-router",
            title="Prepare design intake",
            track_id=track["id"],
        )
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
            from_role="pm",
            summary="router artifact",
        )

        actor_private = self._runtime_path("actor_private")
        actor_private.mkdir(parents=True, exist_ok=True)
        (actor_private / "notes.md").write_text("# notes\n", encoding="utf-8")

        payload = self._dispatch(tool="context", action="summarize", args={})
        self.assertTrue(payload["ok"], msg=payload)
        decision_surface = payload["decision_surface"]
        self.assertEqual(decision_surface["binding_state"]["state"], "runless")
        self.assertNotIn("memory_summaries", payload)
        surfaces = payload.get("writable_surfaces")
        self.assertIsInstance(surfaces, dict, msg=payload)
        assert isinstance(surfaces, dict)
        persistent = surfaces.get("persistent_files")
        self.assertIsInstance(persistent, dict, msg=payload)
        assert isinstance(persistent, dict)
        self.assertEqual(persistent.get("env"), "BUDDYSWITCH_ACTOR_PRIVATE_DIR")
        self.assertEqual(persistent.get("workspace_relative_root"), "private")
        self.assertFalse(persistent.get("mutates_product_state"))
        self.assertNotIn("actor_private_desc", payload)
        self.assertNotIn(_RETIRED_ACTOR_PRIVATE_FILE_ROWS_FIELD, payload)
