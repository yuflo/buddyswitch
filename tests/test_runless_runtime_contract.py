#!/usr/bin/env python3
"""Regression contract for runless BuddySwitch runtime architecture."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class RunlessRuntimeContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-pm-runless",
        buddy: str = "pm",
        status: str = "active",
    ) -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-14T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(
        self,
        *,
        tool: str,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-pm-runless",
        buddy: str = "pm",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-runless-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": tool,
                "action": action,
                "args": args,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        response: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            response[key] = value
        return response

    def _seed_pm_task(self, task_id: str) -> None:
        env_store.create_task(
            task_id,
            "Runless Task",
            buddy="pm",
            track_id=None,
            status="active",
            summary="runless contract seed",
            initial_run_id=None,
        )

    def test_instance_record_contains_execution_identity_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shell = (
                f"BUDDYSWITCH_SHARED_ROOT={tmp}/shared "
                f"BUDDYSWITCH_SOURCE_HOME={tmp}/home "
                "bash -lc '"
                "source tools/launcher/env.sh; "
                "buddyswitch_env_init; "
                "buddyswitch_env_bind_instance inst-pm-runless; "
                "buddyswitch_instance_activate inst-pm-runless pm active >/dev/null; "
                "cat \"$BUDDYSWITCH_INSTANCE_JSON\"'"
            )
            completed = subprocess.run(
                shell,
                cwd=ROOT,
                shell=True,
                text=True,
                capture_output=True,
                check=True,
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(
            set(payload),
            {
                "instance_id",
                "buddy",
                "status",
                "workspace_dir",
                "browser_port",
                "updated_at",
            },
        )

    def test_context_discovery_writes_no_run_reservation_or_run_content(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(
            tool="context",
            action="summarize",
            args={},
            instance_json=instance_json,
        )
        self.assertTrue(response.get("ok"), msg=response)
        for field in (
            "run_envelope",
            "context_revision",
            "persist_command_hint",
            "current_binding",
            "current_task_id",
            "current_track_id",
        ):
            with self.subTest(field=field):
                self.assertNotIn(field, response)
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs/reserved").exists())
        self.assertFalse(self._runtime_path("runs/raw").exists())

    def test_tool_registry_exposes_runless_tools_and_excludes_memory_run_and_binding(self) -> None:
        tools = tool_contracts.supported_tools()
        self.assertNotIn("memory", tools)
        self.assertIn("buddybox", tools)
        self.assertNotIn("run", tools)
        self.assertNotIn("binding", tools)

    def test_task_artifact_records_reject_run_fields(self) -> None:
        with self.assertRaises(ValueError):
            env_store.validate_task(
                {
                    "id": "task-pm-runless",
                    "buddy": "pm",
                    "title": "Runless Task",
                    "summary": "seed",
                    "status": "active",
                    "track_id": None,
                    "artifact_ids": [],
                    "artifact_slots": {},
                    "run_ids": ["run-pm-old"],
                    "latest_run_id": "run-pm-old",
                    "created_at": "2026-05-14T00:00:00Z",
                    "updated_at": "2026-05-14T00:00:00Z",
                }
            )
        with self.assertRaises(ValueError):
            env_store.validate_artifact(
                {
                    "id": "art-pm-runless-r1",
                    "task_id": "task-pm-runless",
                    "buddy": "pm",
                    "kind": "prd",
                    "title": "Runless Artifact",
                    "summary": "seed",
                    "content": {"body": "..."},
                    "revision": 1,
                    "supersedes_artifact_id": None,
                    "is_current": True,
                    "source_run_id": "run-pm-old",
                    "created_at": "2026-05-14T00:00:00Z",
                    "updated_at": "2026-05-14T00:00:00Z",
                }
            )
        with self.assertRaises(ValueError):
            env_store.validate_handoff_record(
                {
                    "id": "handoff-pm-design-old",
                    "source_buddy": "pm",
                    "target_buddy": "design",
                    "track_id": "track-demo",
                    "source_task_id": "task-pm-runless",
                    "source_run_id": "run-pm-old",
                    "artifact_ids": [],
                    "historical_artifact_ids": [],
                    "reason": "seed",
                    "context": "seed",
                    "status": "active",
                    "created_at": "2026-05-14T00:00:00Z",
                    "updated_at": "2026-05-14T00:00:00Z",
                }
            )

    def test_artifact_create_revision_requires_explicit_task_id_without_source_run(self) -> None:
        instance_json = self._instance_json()
        self._seed_pm_task("task-pm-runless")

        missing_task = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "kind": "prd",
                "title": "Runless Artifact",
                "summary": "seed",
                "content": {"body": "..."},
            },
            instance_json=instance_json,
        )
        self.assertFalse(missing_task.get("ok"), msg=missing_task)
        self.assertEqual(missing_task.get("action"), "artifact.create_revision")
        self.assertEqual((missing_task.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

        created = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-runless",
                "kind": "prd",
                "title": "Runless Artifact",
                "summary": "seed",
                "content": {"body": "..."},
                "source_refs": [{"type": "note", "label": "runless seed"}],
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact = created.get("artifact")
        self.assertIsInstance(artifact, dict, msg=created)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("task_id"), "task-pm-runless")
        self.assertNotIn("source_run_id", artifact)

    def test_env_client_help_exposes_runless_resources(self) -> None:
        completed = subprocess.run(
            ["python3", "scripts/env/client.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        help_text = completed.stdout
        self.assertNotIn("memory", help_text)
        self.assertIn("buddybox", help_text)
        self.assertNotIn("binding", help_text)
        self.assertNotIn(" run ", f" {help_text} ")
        self.assertNotIn("get-current", help_text)
        self.assertNotIn("set-current", help_text)


if __name__ == "__main__":
    unittest.main()
