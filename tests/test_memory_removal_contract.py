#!/usr/bin/env python3
"""Regression contract proving memory and handoff runtime surfaces are removed."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

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

    def test_tool_registry_status_and_help_exclude_memory_and_handoff(self) -> None:
        self.assertNotIn("memory", tool_contracts.supported_tools())
        self.assertNotIn("handoff", tool_contracts.supported_tools())
        self.assertFalse(any(key.startswith("memory.") for key in tool_contracts.operation_semantics()))
        self.assertFalse(any(key.startswith("handoff.") for key in tool_contracts.operation_semantics()))

        status = subprocess.run(
            ["python3", str(ROOT / "scripts" / "turn_runtime.py"), "status"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(status.returncode, 0, msg=status.stderr)
        tools = json.loads(status.stdout).get("env_tools", {})
        self.assertNotIn("memory", tools)
        self.assertNotIn("handoff", tools)

    def test_env_tool_memory_or_handoff_request_is_rejected(self) -> None:
        instance_id = "inst-pm-surface-blocked"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        for tool in ("memory", "handoff"):
            response = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                tool=tool,
                action="list",
                args={},
            )
            with self.subTest(tool=tool):
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_source_refs_reject_memory_and_handoff_type(self) -> None:
        for ref_type in ("memory", "handoff"):
            with self.subTest(ref_type=ref_type):
                with self.assertRaisesRegex(ValueError, "unsupported source_ref type"):
                    source_refs.normalize_source_refs(
                        [{"type": ref_type, "id": "old"}],
                        active_buddy="pm",
                    )

    def test_workspace_projection_and_cleanup_ignore_old_memory_files(self) -> None:
        runtime_manifest = self._copy_manifest_into_runtime()
        self._write_old_memory_file(memory_id="mem-old-projection", buddy="pm")

        projection = workspace_data.build_workspace_data()
        self.assertNotIn("memories", projection)
        self.assertNotIn("handoffs", projection)

        cleanup_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.runtime_root,
            manifest_path=runtime_manifest,
        )
        self.assertNotIn("memory_object_ids", cleanup_plan)
        self.assertNotIn("handoff_object_ids", cleanup_plan)


if __name__ == "__main__":
    unittest.main()
