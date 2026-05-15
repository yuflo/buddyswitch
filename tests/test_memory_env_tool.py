#!/usr/bin/env python3
"""Runless memory env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class MemoryEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-memory-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "tool": "memory",
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

    def test_memory_owner_lifecycle_write_get_list_update_archive(self) -> None:
        instance_id = "inst-pm-memory"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        written = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={
                "kind": "decision",
                "title": "Landing CTA Decision",
                "summary": "Use one CTA verb.",
                "content": {"body": "Use one CTA button text across hero and pricing."},
                "source_refs": [{"type": "note", "label": "pm workshop"}],
            },
        )
        self.assertTrue(written.get("ok"), msg=written)
        self.assertTrue(written.get("state_changed"), msg=written)
        self.assertEqual(written.get("durability"), "durable")
        memory_id = written.get("memory_id")
        self.assertIsInstance(memory_id, str, msg=written)
        assert isinstance(memory_id, str)

        fetched = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="get",
            args={"memory_id": memory_id},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        memory = fetched.get("memory")
        self.assertIsInstance(memory, dict, msg=fetched)
        assert isinstance(memory, dict)
        self.assertEqual(memory.get("id"), memory_id)
        self.assertEqual(memory.get("kind"), "decision")
        self.assertEqual(memory.get("content"), {"body": "Use one CTA button text across hero and pricing."})

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="list",
            args={"kind": "decision", "status": "active"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        memories = listed.get("memories")
        self.assertIsInstance(memories, list, msg=listed)
        assert isinstance(memories, list)
        self.assertIn(memory_id, {row.get("id") for row in memories if isinstance(row, dict)})

        updated = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="update",
            args={
                "memory_id": memory_id,
                "summary": "Use one CTA verb and keep it stable.",
                "source_refs": [{"type": "note", "label": "pm workshop v2"}],
            },
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertTrue(updated.get("state_changed"), msg=updated)
        self.assertEqual((updated.get("memory") or {}).get("summary"), "Use one CTA verb and keep it stable.")

        archived = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="archive",
            args={"memory_id": memory_id},
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertTrue(archived.get("state_changed"), msg=archived)
        self.assertEqual((archived.get("memory") or {}).get("status"), "archived")

        archived_again = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="archive",
            args={"memory_id": memory_id},
        )
        self.assertTrue(archived_again.get("ok"), msg=archived_again)
        self.assertFalse(archived_again.get("state_changed"), msg=archived_again)

    def test_memory_permission_boundaries_cross_buddy_update_and_read(self) -> None:
        pm_instance = self._instance_json(buddy="pm", instance_id="inst-pm-memory-owner")
        created = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-memory-owner",
            buddy="pm",
            action="write",
            args={
                "kind": "fact",
                "title": "PM fact",
                "summary": "Owned by PM",
                "content": {"body": "PM-only details"},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        memory_id = str(created.get("memory_id"))

        design_instance = self._instance_json(buddy="design", instance_id="inst-design-memory")
        denied_update = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-memory",
            buddy="design",
            action="update",
            args={"memory_id": memory_id, "summary": "try overwrite"},
        )
        self.assertFalse(denied_update.get("ok"), msg=denied_update)
        self.assertEqual((denied_update.get("error") or {}).get("code"), "E_MEMORY_BUDDY_SCOPE")
        self.assertEqual(denied_update.get("permission_boundary"), "memory.buddy_scope")

        denied_get = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-memory",
            buddy="design",
            action="get",
            args={"memory_id": memory_id},
        )
        self.assertFalse(denied_get.get("ok"), msg=denied_get)
        self.assertEqual((denied_get.get("error") or {}).get("code"), "E_MEMORY_READ_SCOPE")
        self.assertEqual(denied_get.get("permission_boundary"), "memory.read_scope")

    def test_memory_rejects_invalid_kind_status_and_missing_fields(self) -> None:
        instance_id = "inst-pm-memory-invalid"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        bad_kind = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={
                "kind": "transcript",
                "title": "Bad kind",
                "summary": "bad",
                "content": {"body": "x"},
            },
        )
        self.assertFalse(bad_kind.get("ok"), msg=bad_kind)
        self.assertEqual((bad_kind.get("error") or {}).get("code"), "E_MEMORY_KIND")
        self.assertEqual(bad_kind.get("permission_boundary"), "memory.kind")

        missing_content = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={
                "kind": "decision",
                "title": "Missing content",
                "summary": "bad",
            },
        )
        self.assertFalse(missing_content.get("ok"), msg=missing_content)
        self.assertEqual((missing_content.get("error") or {}).get("code"), "E_MEMORY_PAYLOAD")

        created = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={
                "kind": "decision",
                "title": "Good",
                "summary": "ok",
                "content": {"body": "ok"},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        memory_id = str(created.get("memory_id"))

        bad_status = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="update",
            args={"memory_id": memory_id, "status": "deleted"},
        )
        self.assertFalse(bad_status.get("ok"), msg=bad_status)
        self.assertEqual((bad_status.get("error") or {}).get("code"), "E_MEMORY_STATUS")
        self.assertEqual(bad_status.get("permission_boundary"), "memory.status")


if __name__ == "__main__":
    unittest.main()
