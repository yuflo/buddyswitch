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
_OLD_BUDDYBOX_ROOT = "buddyswitch/content/" + "buddybox"


class BuddyboxEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _PRIVACY_MESSAGE = (
        "This is the active buddy's private local working directory. "
        "Other buddies cannot list, read, write, or delete these files. "
        "Use artifact when content must become product-readable."
    )

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

    def _assert_option(self, payload: dict[str, object], option_id: str, *, tool: str, action: str) -> dict[str, object]:
        options = payload.get("allowed_next_action_options")
        self.assertIsInstance(options, list, msg=payload)
        assert isinstance(options, list)
        matches = [row for row in options if isinstance(row, dict) and row.get("id") == option_id]
        self.assertEqual(len(matches), 1, msg=payload)
        option = matches[0]
        self.assertEqual(option.get("tool"), tool, msg=option)
        self.assertEqual(option.get("action"), action, msg=option)
        self.assertIn("mutates", option, msg=option)
        self.assertIsInstance(option.get("reason"), str, msg=option)
        self.assertTrue(str(option.get("reason", "")).strip(), msg=option)
        self.assertIsInstance(option.get("source_refs"), list, msg=option)
        self.assertIsInstance(option.get("preconditions"), list, msg=option)
        return option

    def test_buddybox_desc_returns_private_local_workspace_summary(self) -> None:
        instance_id = "inst-pm-box-desc"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        desc = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="desc",
            args={},
        )
        self.assertTrue(desc.get("ok"), msg=desc)
        self.assertEqual(desc.get("action"), "buddybox.desc")
        self.assertEqual(desc.get("active_buddy"), "pm")
        self.assertEqual(desc.get("logical_root"), "buddyswitch/local/buddybox/pm")
        self.assertEqual(desc.get("privacy_boundary"), "active-buddy-private-local-workspace")
        self.assertEqual(desc.get("message"), self._PRIVACY_MESSAGE)
        self.assertEqual(
            desc.get("available_operations"),
            ["buddybox.desc", "buddybox.list", "buddybox.read", "buddybox.write", "buddybox.delete"],
        )
        state_summary = desc.get("state_summary")
        self.assertIsInstance(state_summary, dict, msg=desc)
        assert isinstance(state_summary, dict)
        self.assertEqual(state_summary.get("file_count"), 0)
        self.assertEqual(state_summary.get("total_bytes"), 0)
        self.assertIsNone(state_summary.get("latest_update_at"))
        self.assertNotIn("files", desc)
        self.assertNotIn("content", desc)
        self.assertNotIn("content_base64", desc)
        next_actions = desc.get("allowed_next_actions")
        self.assertIsInstance(next_actions, list, msg=desc)
        assert isinstance(next_actions, list)
        self.assertGreaterEqual(len(next_actions), 3)
        next_actions_text = " ".join(str(item) for item in next_actions).lower()
        self.assertIn("buddybox.list", next_actions_text)
        self.assertIn("buddybox.write", next_actions_text)
        self.assertIn("host decides", next_actions_text)
        self.assertNotIn("only next action", next_actions_text)
        self.assertNotIn("always create artifact", next_actions_text)
        self._assert_option(desc, "inspect_private_buddybox_summaries", tool="buddybox", action="list")
        self._assert_option(desc, "write_private_buddybox_file", tool="buddybox", action="write")

    def test_buddybox_text_and_binary_lifecycle_uses_local_root(self) -> None:
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
        self.assertTrue(self._runtime_path("buddyswitch/local/buddybox/pm/prototypes/hero.html").exists())
        self.assertFalse(self._runtime_path(f"{_OLD_BUDDYBOX_ROOT}/pm/prototypes/hero.html").exists())
        self._assert_option(text_write, "confirm_private_buddybox_file", tool="buddybox", action="read")
        self._assert_option(text_write, "inspect_private_buddybox_summaries", tool="buddybox", action="list")
        promotion = self._assert_option(
            text_write,
            "promote_readable_content_when_needed",
            tool="artifact",
            action="create_revision",
        )
        self.assertIn("when", str(promotion.get("reason", "")).lower())
        self.assertNotIn("must", str(promotion.get("reason", "")).lower())

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
        self._assert_option(text_read, "replace_private_buddybox_file", tool="buddybox", action="write")
        self._assert_option(text_read, "promote_readable_content_when_needed", tool="artifact", action="create_revision")

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
        self.assertTrue(self._runtime_path("buddyswitch/local/buddybox/pm/assets/snapshot.bin").exists())

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
        for row in files:
            if not isinstance(row, dict):
                continue
            self.assertEqual(row.get("private_to_buddy"), "pm")
            self.assertNotIn("content", row)
            self.assertNotIn("content_base64", row)
            self.assertNotIn("source_ref", row)
        self._assert_option(listed, "read_private_buddybox_file", tool="buddybox", action="read")
        self._assert_option(listed, "write_private_buddybox_file", tool="buddybox", action="write")

        deleted = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"path": "pm/prototypes/hero.html"},
        )
        self.assertTrue(deleted.get("ok"), msg=deleted)
        self.assertTrue(deleted.get("deleted"), msg=deleted)

    def test_pm_cannot_read_list_write_or_delete_foreign_private_paths(self) -> None:
        dev_file = self._runtime_path("buddyswitch/local/buddybox/dev/reports/report.txt")
        dev_file.parent.mkdir(parents=True, exist_ok=True)
        dev_file.write_text("private\n", encoding="utf-8")

        instance_id = "inst-pm-box-scope"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        checks = [
            ("list", {"path": "dev", "recursive": True}),
            ("read", {"path": "dev/reports/report.txt"}),
            ("write", {"path": "dev/reports/new.txt", "content": "x"}),
            ("delete", {"path": "dev/reports/report.txt"}),
        ]
        for action, args in checks:
            with self.subTest(action=action):
                rejected = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                    action=action,
                    args=args,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")
                self.assertIn("private", str(rejected.get("why_blocked", "")).lower())
                self.assertIn("permission_boundary", rejected)
                self.assertIn("retryable", rejected)
                self.assertIn("allowed_next_actions", rejected)
                self.assertIs(rejected.get("state_changed"), False, msg=rejected)
                self._assert_option(rejected, "review_buddybox_private_boundary", tool="buddybox", action="desc")
                self._assert_option(rejected, "retry_active_buddy_private_path", tool="buddybox", action=action)
                self.assertEqual(dev_file.read_text(encoding="utf-8"), "private\n")

    def test_buddybox_rejects_symlink_escape_from_active_root(self) -> None:
        dev_file = self._runtime_path("buddyswitch/local/buddybox/dev/reports/secret.txt")
        dev_file.parent.mkdir(parents=True, exist_ok=True)
        dev_file.write_text("dev secret\n", encoding="utf-8")

        pm_link = self._runtime_path("buddyswitch/local/buddybox/pm/links/dev-secret.txt")
        pm_link.parent.mkdir(parents=True, exist_ok=True)
        pm_link.symlink_to(dev_file)

        instance_id = "inst-pm-box-symlink"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        rejected_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"path": "pm/links/dev-secret.txt"},
        )
        self.assertFalse(rejected_read.get("ok"), msg=rejected_read)
        self.assertEqual((rejected_read.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")
        self.assertNotIn("dev secret", str(rejected_read))

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
        self.assertNotIn("pm/links/dev-secret.txt", {row.get("path") for row in files if isinstance(row, dict)})

        dev_escape_dir = self._runtime_path("buddyswitch/local/buddybox/dev/escape-target")
        dev_escape_dir.mkdir(parents=True, exist_ok=True)
        pm_parent_link = self._runtime_path("buddyswitch/local/buddybox/pm/escape")
        pm_parent_link.symlink_to(dev_escape_dir, target_is_directory=True)

        rejected_write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"path": "pm/escape/new.txt", "content": "leak"},
        )
        self.assertFalse(rejected_write.get("ok"), msg=rejected_write)
        self.assertEqual((rejected_write.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")
        self.assertFalse((dev_escape_dir / "new.txt").exists())

    def test_old_content_buddybox_root_is_not_active_storage(self) -> None:
        old_path = self._runtime_path(f"{_OLD_BUDDYBOX_ROOT}/pm/legacy.txt")
        old_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.write_text("legacy\n", encoding="utf-8")
        instance_id = "inst-pm-box-legacy"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

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
        self.assertEqual(files, [])

        rejected_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"path": "pm/legacy.txt"},
        )
        self.assertFalse(rejected_read.get("ok"), msg=rejected_read)
        self.assertEqual((rejected_read.get("error") or {}).get("code"), "E_BUDDYBOX_PAYLOAD")

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

    def test_buddybox_rejects_invalid_paths_and_payloads(self) -> None:
        instance_id = "inst-pm-box-invalid"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        invalid_writes = [
            {"path": "", "content": "x"},
            {"path": "/tmp/x", "content": "x"},
            {"path": "../x", "content": "x"},
            {"path": "pm/../x", "content": "x"},
            {"path": "pm/notes.md"},
            {"path": "pm/notes.md", "content": "x", "content_base64": "eA=="},
        ]
        for payload in invalid_writes:
            with self.subTest(payload=payload):
                rejected = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                    action="write",
                    args=payload,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)

        invalid_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"path": "pm/missing.txt", "encoding": "utf16"},
        )
        self.assertFalse(invalid_read.get("ok"), msg=invalid_read)
        self.assertEqual((invalid_read.get("error") or {}).get("code"), "E_BUDDYBOX_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
