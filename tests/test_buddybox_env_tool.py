#!/usr/bin/env python3
"""Runless buddybox env.tool integration tests."""

from __future__ import annotations

import base64
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


class BuddyboxEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
                "request_id": f"req-buddybox-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "tool": "buddybox",
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

    def test_buddybox_text_and_binary_lifecycle(self) -> None:
        instance_id = "inst-pm-box"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        text_write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"path": "pm/prototypes/hero.html", "content": "<html>hero</html>"},
        )
        self.assertTrue(text_write.get("ok"), msg=text_write)
        self.assertTrue(text_write.get("state_changed"), msg=text_write)
        self.assertEqual(text_write.get("durability"), "durable")
        self.assertEqual(text_write.get("path"), "pm/prototypes/hero.html")

        text_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"path": "pm/prototypes/hero.html"},
        )
        self.assertTrue(text_read.get("ok"), msg=text_read)
        self.assertEqual(text_read.get("encoding"), "utf-8")
        self.assertEqual(text_read.get("content"), "<html>hero</html>")

        raw_bytes = b"\x00\x01\xff\x10"
        binary_write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={
                "path": "pm/assets/snapshot.bin",
                "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
            },
        )
        self.assertTrue(binary_write.get("ok"), msg=binary_write)
        self.assertEqual(binary_write.get("path"), "pm/assets/snapshot.bin")

        binary_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"path": "pm/assets/snapshot.bin"},
        )
        self.assertTrue(binary_read.get("ok"), msg=binary_read)
        self.assertEqual(binary_read.get("encoding"), "base64")
        self.assertEqual(
            base64.b64decode(str(binary_read.get("content_base64")).encode("ascii")),
            raw_bytes,
        )

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="list",
            args={"recursive": True},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        files = listed.get("files")
        self.assertIsInstance(files, list, msg=listed)
        assert isinstance(files, list)
        self.assertIn("pm/prototypes/hero.html", {row.get("path") for row in files if isinstance(row, dict)})
        self.assertIn("pm/assets/snapshot.bin", {row.get("path") for row in files if isinstance(row, dict)})

        deleted = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"path": "pm/prototypes/hero.html"},
        )
        self.assertTrue(deleted.get("ok"), msg=deleted)
        self.assertTrue(deleted.get("deleted"), msg=deleted)

    def test_buddybox_rejects_path_traversal_and_foreign_owner_scope(self) -> None:
        instance_id = "inst-pm-box-scope"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        for bad_path in ("", "/tmp/x.txt", "../x.txt", "pm/../../x.txt"):
            with self.subTest(path=bad_path):
                rejected = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                    action="write",
                    args={"path": bad_path, "content": "x"},
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")

        foreign_write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"path": "dev/report.txt", "content": "x"},
        )
        self.assertFalse(foreign_write.get("ok"), msg=foreign_write)
        self.assertEqual((foreign_write.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")
        self.assertEqual(foreign_write.get("permission_boundary"), "buddybox.owner_scope")

        foreign_delete = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"path": "dev/report.txt"},
        )
        self.assertFalse(foreign_delete.get("ok"), msg=foreign_delete)
        self.assertEqual((foreign_delete.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")

    def test_buddybox_overwrite_and_repeat_delete_are_explicit(self) -> None:
        instance_id = "inst-pm-box-repeat"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        first = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"path": "pm/logs/out.txt", "content": "v1"},
        )
        self.assertTrue(first.get("ok"), msg=first)
        self.assertFalse(first.get("overwrote"), msg=first)

        second = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"path": "pm/logs/out.txt", "content": "v2"},
        )
        self.assertTrue(second.get("ok"), msg=second)
        self.assertTrue(second.get("overwrote"), msg=second)

        delete_once = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"path": "pm/logs/out.txt"},
        )
        self.assertTrue(delete_once.get("ok"), msg=delete_once)
        self.assertTrue(delete_once.get("deleted"), msg=delete_once)

        delete_twice = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"path": "pm/logs/out.txt"},
        )
        self.assertTrue(delete_twice.get("ok"), msg=delete_twice)
        self.assertFalse(delete_twice.get("deleted"), msg=delete_twice)
        self.assertFalse(delete_twice.get("state_changed"), msg=delete_twice)


if __name__ == "__main__":
    unittest.main()
