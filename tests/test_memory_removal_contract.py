#!/usr/bin/env python3
"""Regression contract proving memory runtime surfaces are removed."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_cleanup  # noqa: E402
import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
import workspace_data  # noqa: E402
from env.services import source_refs  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
_LEGACY_HANDOFF_PRIVATE_PATHS_FIELD = "buddybox_" + "paths"


class MemoryRemovalContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, buddy: str, instance_id: str) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
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
        instance_json: Path,
        instance_id: str,
        buddy: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-memory-removal-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "tool": tool,
                    "action": action,
                    "args": args,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        payload: dict[str, object] = {
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
            payload[key] = value
        return payload

    def _copy_manifest_into_runtime(self) -> Path:
        runtime_manifest = self._runtime_path("buddyswitch/manifest.toml")
        runtime_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, runtime_manifest)
        return runtime_manifest

    def _objects_snapshot(self) -> dict[str, str]:
        objects_root = self._runtime_path("buddyswitch/objects")
        if not objects_root.exists():
            return {}
        rows: dict[str, str] = {}
        for path in sorted(objects_root.rglob("*")):
            if not path.is_file():
                continue
            rows[path.relative_to(objects_root).as_posix()] = path.read_text(encoding="utf-8")
        return rows

    def _write_old_memory_file(self, *, memory_id: str = "mem-old", buddy: str = "pm") -> None:
        memory_path = self._runtime_path(f"buddyswitch/objects/memories/{memory_id}.json")
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(
            json.dumps(
                {
                    "id": memory_id,
                    "buddy": buddy,
                    "kind": "decision",
                    "title": "Legacy memory",
                    "summary": "legacy summary",
                    "content": {"body": "legacy content"},
                    "source_refs": [],
                    "status": "active",
                    "created_at": "2026-05-15T00:00:00Z",
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_tool_registry_status_and_help_exclude_memory(self) -> None:
        self.assertNotIn("memory", tool_contracts.supported_tools())
        self.assertFalse(
            any(key.startswith("memory.") for key in tool_contracts.operation_semantics()),
            msg=tool_contracts.operation_semantics(),
        )

        status = subprocess.run(
            ["python3", str(ROOT / "scripts" / "turn_runtime.py"), "status"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(status.returncode, 0, msg=status.stderr)
        status_payload = json.loads(status.stdout)
        tools = status_payload.get("env_tools", {})
        self.assertIsInstance(tools, dict, msg=status_payload)
        assert isinstance(tools, dict)
        self.assertNotIn("memory", tools)

        client_help = subprocess.run(
            ["python3", str(ROOT / "scripts" / "env/client.py"), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(client_help.returncode, 0, msg=client_help.stderr)
        self.assertNotIn("memory", client_help.stdout)

    def test_env_tool_memory_request_is_rejected_without_state_mutation(self) -> None:
        instance_id = "inst-pm-memory-blocked"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        env_store.create_task(
            "task-pm-memory-blocked",
            "Seed task",
            buddy="pm",
            track_id=None,
            status="active",
            summary="seed",
            initial_run_id=None,
        )
        before_snapshot = self._objects_snapshot()
        response = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="memory",
            action="write",
            args={
                "kind": "decision",
                "title": "Should fail",
                "summary": "memory removed",
                "content": {"body": "blocked"},
            },
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL")
        self.assertEqual(response.get("permission_boundary"), "env.tool")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(self._objects_snapshot(), before_snapshot)
        self.assertFalse(self._runtime_path("buddyswitch/objects/memories").exists())

    def test_context_rejects_memory_kind_and_omits_memory_sections(self) -> None:
        instance_id = "inst-pm-context-memory"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        self._write_old_memory_file(memory_id="mem-old-context", buddy="pm")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="get",
            args={"memory_kind": "decision"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_CONTEXT_PAYLOAD")
        self.assertIs(rejected.get("state_changed"), False, msg=rejected)

        summary = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="summarize",
            args={},
        )
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertNotIn("memory_summaries", summary)
        current_context = summary.get("current_context_summary")
        self.assertIsInstance(current_context, dict, msg=summary)
        assert isinstance(current_context, dict)
        self.assertNotIn("memories", current_context)
        decision_surface = summary.get("decision_surface")
        self.assertIsInstance(decision_surface, dict, msg=summary)
        assert isinstance(decision_surface, dict)
        context_readiness = decision_surface.get("context_readiness")
        self.assertIsInstance(context_readiness, dict, msg=summary)
        assert isinstance(context_readiness, dict)
        self.assertNotIn("has_memories", context_readiness)

        sources = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="list_sources",
            args={},
        )
        self.assertTrue(sources.get("ok"), msg=sources)
        source_rows = sources.get("sources")
        self.assertIsInstance(source_rows, dict, msg=sources)
        assert isinstance(source_rows, dict)
        self.assertNotIn("memories", source_rows)

    def test_source_refs_reject_memory_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported source_ref type: memory"):
            source_refs.normalize_source_refs(
                [{"type": "memory", "id": "mem-old"}],
                active_buddy="pm",
            )

        with self.assertRaises(ValueError):
            env_store.validate_artifact(
                {
                    "id": "art-pm-r1",
                    "title": "Artifact",
                    "task_id": "task-pm",
                    "buddy": "pm",
                    "kind": "prd",
                    "revision": 1,
                    "supersedes_artifact_id": None,
                    "is_current": True,
                    "created_by": "pm",
                    "source_refs": [{"type": "memory", "id": "mem-old"}],
                    "summary": "seed",
                    "content": {"body": "x"},
                    "created_at": "2026-05-15T00:00:00Z",
                    "updated_at": "2026-05-15T00:00:00Z",
                }
            )

    def test_evidence_rejects_memory_target_and_accepts_artifact_target(self) -> None:
        instance_id = "inst-pm-evidence-memory"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        env_store.create_task(
            "task-pm-evidence-memory",
            "Evidence task",
            buddy="pm",
            track_id=None,
            status="active",
            summary="seed",
            initial_run_id=None,
        )
        artifact = env_store.create_artifact(
            artifact_id="art-pm-evidence-memory-r1",
            title="Evidence artifact",
            buddy="pm",
            kind="spec",
            task_id="task-pm-evidence-memory",
            summary="seed",
            content={"body": "artifact body"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        accepted = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact["id"]},
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        evidence = accepted.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=accepted)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "memory", "target_id": "mem-old"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")
        self.assertEqual(rejected.get("permission_boundary"), "evidence.target_type")
        self.assertIs(rejected.get("state_changed"), False, msg=rejected)
        self.assertNotIn("tool_evidence", rejected)

    def test_handoff_rejects_memory_ids_and_created_record_omits_memory_ids(self) -> None:
        instance_id = "inst-pm-handoff-memory"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        env_store.create_track("track-memory-removed", "Memory removal track", current_buddy="pm", next_buddy="dev")
        env_store.create_task(
            "task-pm-handoff-memory",
            "Handoff source task",
            buddy="pm",
            track_id="track-memory-removed",
            status="active",
            summary="seed",
            initial_run_id=None,
        )
        artifact = env_store.create_artifact(
            artifact_id="art-pm-handoff-memory-r1",
            title="handoff artifact",
            buddy="pm",
            kind="spec",
            task_id="task-pm-handoff-memory",
            summary="seed",
            content={"body": "artifact body"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        buddybox_path = self._runtime_path("buddyswitch/local/buddybox/pm/brief.md")
        buddybox_path.parent.mkdir(parents=True, exist_ok=True)
        buddybox_path.write_text("brief", encoding="utf-8")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="handoff",
            action="validate",
            args={
                "track_id": "track-memory-removed",
                "source_task_id": "task-pm-handoff-memory",
                "target_buddy": "dev",
                "artifact_ids": [artifact["id"]],
                "memory_ids": ["mem-old"],
                "source_refs": [{"type": "note", "label": "seed"}],
                "reason": "handoff",
                "context": "context",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_HANDOFF_PAYLOAD")
        self.assertIs(rejected.get("state_changed"), False, msg=rejected)

        created = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="handoff",
            action="create",
            args={
                "handoff_id": "handoff-pm-dev-memory-removed",
                "track_id": "track-memory-removed",
                "source_task_id": "task-pm-handoff-memory",
                "target_buddy": "dev",
                "artifact_ids": [artifact["id"]],
                "source_refs": [{"type": "note", "label": "seed"}],
                "reason": "handoff",
                "context": "context",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        handoff = created.get("handoff")
        self.assertIsInstance(handoff, dict, msg=created)
        assert isinstance(handoff, dict)
        self.assertNotIn("memory_ids", handoff)
        self.assertNotIn(_LEGACY_HANDOFF_PRIVATE_PATHS_FIELD, handoff)

        saved_handoff = self._runtime_path("buddyswitch/objects/handoffs/handoff-pm-dev-memory-removed.json")
        self.assertTrue(saved_handoff.exists())
        saved_payload = json.loads(saved_handoff.read_text(encoding="utf-8"))
        self.assertNotIn("memory_ids", saved_payload)

        old_handoff_path = self._runtime_path("buddyswitch/objects/handoffs/handoff-old-memory-ids.json")
        old_handoff_path.write_text(
            json.dumps(
                {
                    "id": "handoff-old-memory-ids",
                    "track_id": "track-memory-removed",
                    "source_buddy": "pm",
                    "target_buddy": "dev",
                    "source_task_id": "task-pm-handoff-memory",
                    "artifact_ids": [artifact["id"]],
                    "memory_ids": ["mem-old"],
                    _LEGACY_HANDOFF_PRIVATE_PATHS_FIELD: ["pm/brief.md"],
                    "source_refs": [{"type": "note", "label": "legacy handoff"}],
                    "reason": "old handoff",
                    "context": "old context",
                    "status": "active",
                    "created_at": "2026-05-15T00:00:00Z",
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        old_rows = {row["id"]: row for row in env_store.list_handoffs()}
        self.assertIn("handoff-old-memory-ids", old_rows)
        self.assertNotIn("memory_ids", old_rows["handoff-old-memory-ids"])
        self.assertNotIn(_LEGACY_HANDOFF_PRIVATE_PATHS_FIELD, old_rows["handoff-old-memory-ids"])

        dev_instance = self._instance_json(buddy="dev", instance_id="inst-dev-handoff-old-memory")
        listed = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-handoff-old-memory",
            buddy="dev",
            tool="handoff",
            action="list",
            args={"track_id": "track-memory-removed"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        listed_rows = listed.get("handoffs")
        self.assertIsInstance(listed_rows, list, msg=listed)
        assert isinstance(listed_rows, list)
        listed_old = [row for row in listed_rows if isinstance(row, dict) and row.get("id") == "handoff-old-memory-ids"]
        self.assertEqual(len(listed_old), 1, msg=listed_rows)
        self.assertNotIn("memory_ids", listed_old[0])
        self.assertNotIn(_LEGACY_HANDOFF_PRIVATE_PATHS_FIELD, listed_old[0])

    def test_workspace_projection_launcher_and_cleanup_ignore_old_memory_files(self) -> None:
        runtime_manifest = self._copy_manifest_into_runtime()

        env_store.ensure_runtime_dirs()
        self.assertFalse(self._runtime_path("buddyswitch/objects/memories").exists())
        for helper_name in (
            "create_memory",
            "get_memory",
            "list_memories",
            "update_memory",
            "validate_memory",
            "MEMORY_OBJECTS_DIR",
        ):
            self.assertFalse(hasattr(env_store, helper_name), msg=helper_name)

        self._write_old_memory_file(memory_id="mem-old-projection", buddy="pm")

        projection = workspace_data.build_workspace_data()
        self.assertNotIn("memories", projection)

        projection_contract = json.loads(
            (ROOT / "framework/contracts/workspace-projection.json").read_text(encoding="utf-8")
        )
        top_level_order = projection_contract.get("top_level_key_order", [])
        self.assertIsInstance(top_level_order, list, msg=projection_contract)
        assert isinstance(top_level_order, list)
        self.assertNotIn("memories", top_level_order)
        data_sources = projection_contract.get("data_sources", [])
        self.assertIsInstance(data_sources, list, msg=projection_contract)
        assert isinstance(data_sources, list)
        self.assertFalse(any(isinstance(item, str) and "objects/memories" in item for item in data_sources))

        cleanup_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.runtime_root,
            manifest_path=runtime_manifest,
        )
        self.assertNotIn("memory_object_ids", cleanup_plan)
        self.assertFalse(any("objects/memories" in path for path in cleanup_plan.get("delete_paths", [])))


if __name__ == "__main__":
    unittest.main()
