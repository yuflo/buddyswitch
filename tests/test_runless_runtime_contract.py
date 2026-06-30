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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
import runtime_kernel.lifecycle as runtime_lifecycle  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class RunlessRuntimeContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    @staticmethod
    def _json_log_events(path: Path) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        if not path.exists():
            return events
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("event"), str):
                events.append(payload)
        return events

    def test_runtime_dispatcher_integration_surface_avoids_env_store_import(self) -> None:
        dispatcher_source = (ROOT / "scripts" / "runtime_kernel" / "dispatcher.py").read_text(encoding="utf-8")
        self.assertNotIn("import env_store", dispatcher_source)
        self.assertNotIn("from env_store import", dispatcher_source)

    def _instance_json(
        self,
        *,
        actor_id: str = "act-pm-runless",
        role: str = "pm",
        status: str = "active",
    ) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self._instance_root(actor_id)
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = instance_root / "instance.json"
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": status,
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "updated_at": "2026-05-14T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task_for_instance(
            instance_json=path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-runless",
        )
        return path

    def _dispatch(
        self,
        *,
        tool: str,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        actor_id: str = "act-pm-runless",
        role: str = "pm",
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-runless-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": actor_id,
                "active_role": role,
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
        self._write_task_sys_task(
            actor_id="act-pm-runless",
            role="pm",
            task_slug=task_id,
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
                "buddyswitch_env_bind_instance act-pm-runless; "
                "buddyswitch_instance_activate act-pm-runless pm active >/dev/null; "
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
                "actor_id",
                "role",
                "status",
                "instance_root",
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
        self.assertNotIn("actor_private", tools)
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
        self.assertNotIn("actor_private", env_tools)
        self.assertIn("context", env_tools)
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

    def test_runtime_broker_lifecycle_writes_breadcrumb_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = runtime_lifecycle.BrokerPaths(
                socket_path=root / "runtime-broker.sock",
                pid_file=root / "runtime-broker.pid",
                marker_file=root / "runtime-broker.socket",
                log_file=root / "runtime-broker.log",
            )

            def fake_start(*_args: object, **_kwargs: object) -> dict[str, object]:
                paths.pid_file.write_text("999999\n", encoding="utf-8")
                paths.socket_path.write_text("socket\n", encoding="utf-8")
                return {"ok": True, "pid": 999999}

            def fake_ping(*_args: object, **_kwargs: object) -> dict[str, object]:
                return {
                    "ok": True,
                    "result": {
                        "protocol": PROTOCOL,
                        "actor_id": "act-pm-runless",
                        "active_role": "pm",
                        "pid": 999999,
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": True,
                    },
                }

            with patch.object(runtime_lifecycle, "_socket_is_unix", return_value=True), patch.object(
                runtime_lifecycle,
                "pid_is_live",
                side_effect=lambda pid: pid == 999999,
            ), patch.object(runtime_lifecycle, "start_broker_process", side_effect=fake_start), patch.object(
                runtime_lifecycle,
                "ping_broker",
                side_effect=fake_ping,
            ):
                result = runtime_lifecycle.ensure_broker(
                    paths,
                    instance_json_path=root / "instance.json",
                    manifest_path=MANIFEST,
                    expected_actor_id="act-pm-runless",
                    expected_active_role="pm",
                    startup_timeout_seconds=0.05,
                )

            self.assertTrue(result["ok"], msg=result)
            with patch.object(runtime_lifecycle, "pid_is_live", return_value=False):
                runtime_lifecycle.stop_broker(paths)

            events = self._json_log_events(paths.log_file)
            event_names = [event["event"] for event in events]
            self.assertIn("runtime_broker_start_requested", event_names)
            self.assertIn("runtime_broker_ready", event_names)
            self.assertIn("runtime_broker_stop_requested", event_names)
            ready = next(event for event in events if event["event"] == "runtime_broker_ready")
            self.assertEqual(ready["service"], "runtime_broker")
            self.assertEqual(ready["actor_id"], "act-pm-runless")

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
                    "role": "pm",
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
                    "role": "pm",
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
        self.assertNotIn("status", artifact)
        self.assertNotIn("published_to_track", artifact)
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
        self.assertNotIn("actor_private", help_text)
        self.assertNotIn("binding", help_text)
        self.assertNotIn(" run ", f" {help_text} ")
        self.assertNotIn("get-current", help_text)
        self.assertNotIn("set-current", help_text)

    def test_env_client_actor_private_is_not_registered(self) -> None:
        completed = subprocess.run(
            ["python3", "scripts/env/client.py", "actor_private", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("invalid choice", completed.stderr)


if __name__ == "__main__":
    unittest.main()
