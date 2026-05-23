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

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class RunlessRuntimeContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_runtime_dispatcher_integration_surface_avoids_env_store_import(self) -> None:
        dispatcher_source = (ROOT / "scripts" / "runtime_kernel" / "dispatcher.py").read_text(encoding="utf-8")
        self.assertNotIn("import env_store", dispatcher_source)
        self.assertNotIn("from env_store import", dispatcher_source)

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
        self._write_taskbox_task(
            instance_id="inst-pm-runless",
            buddy="pm",
            task_id=task_id,
            title="Runless Task",
            summary="runless contract seed",
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
        tools = tool_catalog.supported_tools()
        self.assertNotIn("memory", tools)
        self.assertIn("buddybox", tools)
        self.assertNotIn("run", tools)
        self.assertNotIn("binding", tools)

    def test_status_exposes_env_tools_catalog(self) -> None:
        completed = subprocess.run(
            ["python3", str(ROOT / "scripts" / "turn_runtime.py"), "status"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        env_tools = payload.get("env_tools")
        self.assertIsInstance(env_tools, dict, msg=payload)
        assert isinstance(env_tools, dict)
        self.assertIn("buddybox", env_tools)
        self.assertIn("context", env_tools)
        buddybox = env_tools["buddybox"]
        self.assertIsInstance(buddybox, dict, msg=payload)
        assert isinstance(buddybox, dict)
        self.assertIn("action_semantics", buddybox)
        self.assertIn("write", buddybox["action_semantics"])
        self.assertIn("inputs_explained", buddybox["action_semantics"]["write"])
        operations = buddybox.get("operations")
        self.assertIsInstance(operations, list, msg=buddybox)
        assert isinstance(operations, list)
        self.assertNotIn("search", operations)
        context_catalog = env_tools["context"]
        self.assertIsInstance(context_catalog, dict, msg=payload)
        assert isinstance(context_catalog, dict)
        context_ops = context_catalog.get("operations")
        self.assertIsInstance(context_ops, list, msg=context_catalog)
        assert isinstance(context_ops, list)
        self.assertEqual(set(context_ops), {"get", "summarize", "list_sources"})
        context_semantics = context_catalog.get("action_semantics")
        self.assertIsInstance(context_semantics, dict, msg=context_catalog)
        assert isinstance(context_semantics, dict)
        self.assertIn("summarize", context_semantics)
        summarize_semantics = context_semantics["summarize"]
        self.assertIsInstance(summarize_semantics, dict, msg=context_semantics)
        assert isinstance(summarize_semantics, dict)
        self.assertIn("inputs_explained", summarize_semantics)
        self.assertIn("success_means", summarize_semantics)
        self.assertEqual(env_tools, tool_catalog.env_tools_description())

    def test_context_get_exposes_full_input_schemas(self) -> None:
        instance_json = self._instance_json()
        payload = self._dispatch(
            tool="context",
            action="get",
            args={},
            instance_json=instance_json,
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        catalog_row = payload.get("tool_catalog")
        self.assertIsInstance(catalog_row, dict, msg=payload)
        assert isinstance(catalog_row, dict)
        self.assertEqual(catalog_row, tool_catalog.env_tools_description())
        track_create = catalog_row["track"]["input_schemas"]["create"]
        self.assertEqual(track_create.get("type"), "object")
        now_schema = track_create["properties"]["now"]
        self.assertEqual(now_schema.get("type"), "object")
        self.assertEqual(now_schema.get("required"), ["next"])
        self.assertEqual(now_schema["properties"]["next"]["type"], "string")

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
        self.assertFalse(hasattr(env_store, "validate_handoff_record"))

    def test_artifact_create_revision_requires_v1_payload_without_source_run(self) -> None:
        instance_json = self._instance_json()

        missing_required_body = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "title": "Runless Artifact",
                "summary": "seed",
                "template": "brief",
            },
            instance_json=instance_json,
        )
        self.assertFalse(missing_required_body.get("ok"), msg=missing_required_body)
        self.assertEqual(missing_required_body.get("action"), "artifact.create_revision")
        self.assertEqual((missing_required_body.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

        retired_shape = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-runless",
                "kind": "prd",
                "title": "Runless Artifact",
                "summary": "seed",
                "content": {"body": "..."},
            },
            instance_json=instance_json,
        )
        self.assertFalse(retired_shape.get("ok"), msg=retired_shape)
        self.assertEqual((retired_shape.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

        created = self._dispatch(
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-runless-r1",
                "title": "Runless Artifact",
                "summary": "seed",
                "template": "brief",
                "body": "...",
                "source_refs": [{"type": "note", "label": "runless seed"}],
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact = created.get("artifact")
        self.assertIsInstance(artifact, dict, msg=created)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("template"), "brief")
        self.assertEqual(artifact.get("body"), "...")
        self.assertEqual(artifact.get("status"), "draft")
        self.assertIsNone(artifact.get("published_to_track"))
        self.assertNotIn("task_id", artifact)
        self.assertNotIn("kind", artifact)
        self.assertNotIn("content", artifact)
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

    def test_env_client_buddybox_help_exposes_desc_subcommand(self) -> None:
        buddybox_help = subprocess.run(
            ["python3", "scripts/env/client.py", "buddybox", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("desc", buddybox_help.stdout)

        desc_help = subprocess.run(
            ["python3", "scripts/env/client.py", "buddybox", "desc", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("usage:", desc_help.stdout.lower())

    def test_env_client_buddybox_file_subcommands_use_payload_json(self) -> None:
        for operation in ("list", "read", "delete"):
            with self.subTest(operation=operation):
                completed = subprocess.run(
                    ["python3", "scripts/env/client.py", "buddybox", operation, "--help"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                help_text = completed.stdout.lower()
                self.assertIn("--payload", help_text)
                self.assertNotIn("--path", help_text)
                self.assertNotIn("--logical-name", help_text)


if __name__ == "__main__":
    unittest.main()
