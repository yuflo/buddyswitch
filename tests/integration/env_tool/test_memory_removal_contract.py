"""Regression contract proving memory and handoff runtime surfaces are removed."""

from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.runtime_support import env_cleanup  # noqa: E402
from buddyswitch.env.repos import artifacts as artifact_repo
from buddyswitch.env.repos import runtime_files
from buddyswitch.env.repos import track_comments as track_comment_repo
from buddyswitch.env.repos import tracks as track_repo
from tests.support import object_builders
import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from buddyswitch.env.domain import source_refs  # noqa: E402
from buddyswitch.env.tool_runtime import registry as tool_catalog  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class MemoryRemovalContractTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        super().tearDown()

    def _runtime_path(self, repo_path: str) -> Path:
        return self.runtime_root / repo_path

    def _state_path(self, repo_path: str) -> Path:
        return self.runtime_root / repo_path

    @staticmethod
    def _runtime_actor_id(*, role: str, label: str) -> str:
        if label.startswith(f"act-{role}-"):
            suffix = label.removeprefix(f"act-{role}-")
            if len(suffix) == 12 and all(char in "0123456789abcdef" for char in suffix):
                return label
        digest = hashlib.sha1(f"{role}:{label}".encode("utf-8")).hexdigest()[:12]
        return f"act-{role}-{digest}"

    def _instance_json(self, *, role: str, actor_id: str) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        path = self._runtime_path(f"instances/{actor_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
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
        actor_id: str,
        role: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-memory-removal-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "actor_id": actor_id,
                    "active_role": role,
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
        runtime_manifest = self._runtime_path("catalog/manifest.toml")
        runtime_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, runtime_manifest)
        return runtime_manifest

    def _write_old_memory_file(self, *, memory_id: str = "mem-old", role: str = "pm") -> None:
        memory_path = self._state_path(f"buddyswitch/objects/memories/{memory_id}.json")
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(
            json.dumps(
                {
                    "id": memory_id,
                    "role": role,
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

    def test_tool_registry_excludes_memory_and_handoff(self) -> None:
        self.assertNotIn("memory", tool_catalog.supported_tools())
        self.assertNotIn("handoff", tool_catalog.supported_tools())
        self.assertFalse(any(key.startswith("memory.") for key in tool_catalog.operation_semantics()))
        self.assertFalse(any(key.startswith("handoff.") for key in tool_catalog.operation_semantics()))

    def test_env_tool_memory_or_handoff_request_is_rejected(self) -> None:
        actor_id = "act-pm-surface-blocked"
        instance_json = self._instance_json(role="pm", actor_id=actor_id)

        for tool in ("memory", "handoff"):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_id,
                role="pm",
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
                        active_role="pm",
                        current_identity={"id": "act-pm-source-ref", "type": "actor"},
                    )

    def test_cleanup_ignores_old_memory_files(self) -> None:
        runtime_manifest = self._copy_manifest_into_runtime()
        self._write_old_memory_file(memory_id="mem-old-projection", role="pm")

        cleanup_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.runtime_root,
            manifest_path=runtime_manifest,
        )
        self.assertNotIn("memory_object_ids", cleanup_plan)
        self.assertNotIn("handoff_object_ids", cleanup_plan)
