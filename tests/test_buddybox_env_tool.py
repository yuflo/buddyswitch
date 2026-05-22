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

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
_OLD_BUDDYBOX_ROOT = "buddyswitch/content/" + "buddybox"


class BuddyboxEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _PRIVACY_MESSAGE = (
        "This is the active buddy's private file capability. "
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
        payload: dict[str, object] = {"ok": False, "error": dict(error)}
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
        self.assertEqual(desc.get("capability"), "private_file_workspace")
        self.assertEqual(desc.get("owner_scope"), "active_buddy")
        self.assertEqual(desc.get("lifetime_scope"), "active_instance_workspace")
        self.assertEqual(desc.get("visibility"), "active_buddy_private")
        self.assertFalse(desc.get("product_readable"))
        self.assertFalse(desc.get("cross_buddy_readable"))
        self.assertFalse(desc.get("mutates_product_state"))
        self.assertEqual(desc.get("message"), self._PRIVACY_MESSAGE)
        supports = desc.get("supports")
        self.assertIsInstance(supports, list, msg=desc)
        assert isinstance(supports, list)
        self.assertIn("list_private_file_summaries", supports)
        self.assertIn("read_private_file", supports)
        self.assertNotIn("logical_root", desc)
        state_summary = desc.get("state_summary")
        self.assertIsInstance(state_summary, dict, msg=desc)
        assert isinstance(state_summary, dict)
        self.assertEqual(state_summary.get("file_count"), 0)
        self.assertEqual(state_summary.get("total_bytes"), 0)
        self.assertIsNone(state_summary.get("latest_update_at"))
        self.assertNotIn("files", desc)
        self.assertNotIn("content", desc)
        self.assertNotIn("content_base64", desc)
        affordances = desc.get("available_affordances")
        self.assertIsInstance(affordances, list, msg=desc)
        next_actions = desc.get("allowed_next_actions")
        self.assertIsInstance(next_actions, list, msg=desc)
        assert isinstance(next_actions, list)
        self.assertEqual(next_actions, [])
        next_actions_text = " ".join(str(item) for item in next_actions).lower()
        self.assertNotIn("only next action", next_actions_text)
        self.assertNotIn("always create artifact", next_actions_text)
        self._assert_option(desc, "inspect_private_buddybox_summaries", tool="buddybox", action="list")
        self._assert_option(desc, "write_private_buddybox_file", tool="buddybox", action="write")

    def test_desc_exposes_logical_name_policy_without_business_sop(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-buddybox-policy", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-buddybox-policy",
            buddy="dev",
            action="desc",
            args={},
        )
        self.assertTrue(response.get("ok"), msg=response)
        policy = response.get("logical_name_policy")
        self.assertIsInstance(policy, dict, msg=response)
        text = json.dumps(policy, ensure_ascii=True).lower()
        for snippet in ("relative", "absolute", "..", "buddy prefix"):
            self.assertIn(snippet, text)
        self.assertIn("notes/todo.md", text)
        self.assertNotIn("coordination/", text)
        self.assertNotIn("execution/", text)

    def test_buddybox_logical_name_text_binary_lifecycle(self) -> None:
        instance_id = "inst-pm-box"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        text_write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "prototypes/hero.html", "content": "<html>hero</html>"},
        )
        self.assertTrue(text_write.get("ok"), msg=text_write)
        self.assertTrue(text_write.get("state_changed"), msg=text_write)
        self.assertEqual(text_write.get("durability"), "durable")
        self.assertEqual(text_write.get("logical_name"), "prototypes/hero.html")
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
            args={"logical_name": "prototypes/hero.html"},
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
                "logical_name": "assets/snapshot.bin",
                "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
            },
        )
        self.assertTrue(binary_write.get("ok"), msg=binary_write)
        self.assertEqual(binary_write.get("logical_name"), "assets/snapshot.bin")
        self.assertTrue(self._runtime_path("buddyswitch/local/buddybox/pm/assets/snapshot.bin").exists())

        binary_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"logical_name": "assets/snapshot.bin"},
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
        self.assertIn("prototypes/hero.html", {row.get("logical_name") for row in files if isinstance(row, dict)})
        self.assertIn("assets/snapshot.bin", {row.get("logical_name") for row in files if isinstance(row, dict)})
        for row in files:
            if not isinstance(row, dict):
                continue
            self.assertEqual(row.get("private_to_buddy"), "pm")
            self.assertNotIn("content", row)
            self.assertNotIn("content_base64", row)
            self.assertNotIn("source_ref", row)
            self.assertNotIn("path", row)
        self._assert_option(listed, "read_private_buddybox_file", tool="buddybox", action="read")
        self._assert_option(listed, "write_private_buddybox_file", tool="buddybox", action="write")

        deleted = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"logical_name": "prototypes/hero.html"},
        )
        self.assertTrue(deleted.get("ok"), msg=deleted)
        self.assertTrue(deleted.get("deleted"), msg=deleted)

    def test_buddybox_rejects_legacy_path_payload_field(self) -> None:
        instance_id = "inst-pm-box-path-retired"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"path": "pm/prototypes/hero.html", "content": "x"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_PAYLOAD")

    def test_import_file_writes_private_file_without_path_exposure(self) -> None:
        instance_id = "inst-design-box-import"
        instance_json = self._instance_json(buddy="design", instance_id=instance_id)
        source = self._runtime_path("tmp/chrome-devtools/desktop.png")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"\x89PNG\r\n")

        imported = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            action="import_file",
            args={
                "logical_name": "screenshots/desktop.png",
                "source_path": str(source),
                "content_type": "image/png",
            },
        )
        self.assertTrue(imported.get("ok"), msg=imported)
        self.assertEqual(imported.get("logical_name"), "screenshots/desktop.png")
        self.assertEqual(imported.get("content_type"), "image/png")
        self.assertNotIn("source_path", imported)
        self.assertNotIn("path", imported)
        self.assertNotIn(str(source), json.dumps(imported, ensure_ascii=True))
        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"\x89PNG\r\n")

        read_back = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            action="read",
            args={"logical_name": "screenshots/desktop.png", "encoding": "base64"},
        )
        self.assertTrue(read_back.get("ok"), msg=read_back)
        self.assertEqual(read_back.get("content_base64"), "iVBORw0K")

    def test_import_file_rejects_invalid_sources_without_writing_private_file(self) -> None:
        instance_id = "inst-design-box-import-reject"
        instance_json = self._instance_json(buddy="design", instance_id=instance_id)

        directory_source = self._runtime_path("tmp/import-invalid/dir-source")
        directory_source.mkdir(parents=True, exist_ok=True)

        runtime_object_source = self._runtime_path("buddyswitch/objects/tracks/leak.txt")
        runtime_object_source.parent.mkdir(parents=True, exist_ok=True)
        runtime_object_source.write_text("leak\n", encoding="utf-8")

        runtime_local_source = self._runtime_path("buddyswitch/local/buddybox/design/private.txt")
        runtime_local_source.parent.mkdir(parents=True, exist_ok=True)
        runtime_local_source.write_text("private\n", encoding="utf-8")

        symlink_source = self._runtime_path("tmp/import-invalid/manifest-link")
        symlink_source.parent.mkdir(parents=True, exist_ok=True)
        symlink_source.symlink_to(MANIFEST)

        cases = (
            ("missing", self._runtime_path("tmp/import-invalid/missing.txt")),
            ("directory", directory_source),
            ("runtime-objects", runtime_object_source),
            ("runtime-local", runtime_local_source),
            ("symlink-outside", symlink_source),
        )

        for case_name, source_path in cases:
            logical_name = f"imports/{case_name}.txt"
            rejected = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="design",
                action="import_file",
                args={
                    "logical_name": logical_name,
                    "source_path": str(source_path),
                    "content_type": "text/plain",
                },
            )
            with self.subTest(case=case_name):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
                self.assertEqual(rejected.get("durability"), "none")
                self.assertFalse(self._runtime_path(f"buddyswitch/local/buddybox/design/{logical_name}").exists())

    def test_buddybox_rejects_buddy_prefixed_logical_names(self) -> None:
        instance_id = "inst-pm-box-prefix"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        for action, payload in (
            ("write", {"logical_name": "pm/prototypes/hero.html", "content": "x"}),
            ("write", {"logical_name": "dev/reports/report.txt", "content": "x"}),
            ("read", {"logical_name": "pm/prototypes/hero.html"}),
            ("delete", {"logical_name": "dev/reports/report.txt"}),
        ):
            with self.subTest(action=action, payload=payload):
                rejected = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                    action=action,
                    args=payload,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_LOGICAL_NAME")
                self.assertIs(rejected.get("state_changed"), False, msg=rejected)
        self.assertFalse(self._runtime_path("buddyswitch/local/buddybox/pm/prototypes/hero.html").exists())
        self.assertFalse(self._runtime_path("buddyswitch/local/buddybox/pm/dev/reports/report.txt").exists())

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
            args={"logical_name": "links/dev-secret.txt"},
        )
        self.assertFalse(rejected_read.get("ok"), msg=rejected_read)
        self.assertEqual((rejected_read.get("error") or {}).get("code"), "E_BUDDYBOX_BOUNDARY")
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
        self.assertNotIn("links/dev-secret.txt", {row.get("logical_name") for row in files if isinstance(row, dict)})

        dev_escape_dir = self._runtime_path("buddyswitch/local/buddybox/dev/escape-target")
        dev_escape_dir.mkdir(parents=True, exist_ok=True)
        pm_parent_link = self._runtime_path("buddyswitch/local/buddybox/pm/escape")
        pm_parent_link.symlink_to(dev_escape_dir, target_is_directory=True)

        rejected_write = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "escape/new.txt", "content": "leak"},
        )
        self.assertFalse(rejected_write.get("ok"), msg=rejected_write)
        self.assertEqual((rejected_write.get("error") or {}).get("code"), "E_BUDDYBOX_BOUNDARY")
        self.assertFalse((dev_escape_dir / "new.txt").exists())

    def test_buddybox_rejects_active_root_symlink_escape(self) -> None:
        dev_private_target = self._runtime_path("buddyswitch/local/buddybox/dev/private-target")
        dev_private_target.mkdir(parents=True, exist_ok=True)
        pm_root = self._runtime_path("buddyswitch/local/buddybox/pm")
        pm_root.parent.mkdir(parents=True, exist_ok=True)
        pm_root.symlink_to(dev_private_target, target_is_directory=True)

        instance_id = "inst-pm-box-root-symlink"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "leak.txt", "content": "private"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_BOUNDARY")
        self.assertFalse((dev_private_target / "leak.txt").exists())

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
            args={"logical_name": "legacy.txt"},
        )
        self.assertFalse(rejected_read.get("ok"), msg=rejected_read)
        self.assertEqual((rejected_read.get("error") or {}).get("code"), "E_BUDDYBOX_NOT_FOUND")

    def test_legacy_shared_buddybox_roots_are_unmanaged(self) -> None:
        legacy_shared = self._runtime_path("state/buddyswitch/local/buddybox/pm/legacy.txt")
        legacy_shared.parent.mkdir(parents=True, exist_ok=True)
        legacy_shared.write_text("legacy-shared\n", encoding="utf-8")
        legacy_content = self._runtime_path(f"{_OLD_BUDDYBOX_ROOT}/pm/legacy-content.txt")
        legacy_content.parent.mkdir(parents=True, exist_ok=True)
        legacy_content.write_text("legacy-content\n", encoding="utf-8")

        instance_id = "inst-pm-box-legacy-shared"
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

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"logical_name": "legacy.txt"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_NOT_FOUND")
        self.assertEqual(legacy_shared.read_text(encoding="utf-8"), "legacy-shared\n")
        self.assertEqual(legacy_content.read_text(encoding="utf-8"), "legacy-content\n")

    def test_buddybox_overwrite_and_repeat_delete_are_explicit(self) -> None:
        instance_id = "inst-pm-box-repeat"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        first = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "logs/out.txt", "content": "v1"},
        )
        self.assertTrue(first.get("ok"), msg=first)
        self.assertFalse(first.get("overwrote"), msg=first)

        second = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "logs/out.txt", "content": "v2"},
        )
        self.assertTrue(second.get("ok"), msg=second)
        self.assertTrue(second.get("overwrote"), msg=second)

        delete_once = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"logical_name": "logs/out.txt"},
        )
        self.assertTrue(delete_once.get("ok"), msg=delete_once)
        self.assertTrue(delete_once.get("deleted"), msg=delete_once)

        delete_twice = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"logical_name": "logs/out.txt"},
        )
        self.assertTrue(delete_twice.get("ok"), msg=delete_twice)
        self.assertFalse(delete_twice.get("deleted"), msg=delete_twice)
        self.assertFalse(delete_twice.get("state_changed"), msg=delete_twice)

    def test_buddybox_logical_name_boundaries_and_payloads(self) -> None:
        instance_id = "inst-pm-box-invalid"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        invalid_writes = [
            ({"logical_name": "", "content": "x"}, {"E_BUDDYBOX_LOGICAL_NAME"}),
            ({"logical_name": "/tmp/x", "content": "x"}, {"E_BUDDYBOX_LOGICAL_NAME"}),
            ({"logical_name": "../x", "content": "x"}, {"E_BUDDYBOX_LOGICAL_NAME"}),
            ({"logical_name": "notes/../../x", "content": "x"}, {"E_BUDDYBOX_LOGICAL_NAME"}),
            ({"logical_name": "notes.md"}, {"E_BUDDYBOX_PAYLOAD"}),
            ({"logical_name": "notes.md", "content": "x", "content_base64": "eA=="}, {"E_BUDDYBOX_PAYLOAD"}),
        ]
        for payload, expected_codes in invalid_writes:
            with self.subTest(payload=payload, expected_codes=sorted(expected_codes)):
                rejected = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                    action="write",
                    args=payload,
                )
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertIn((rejected.get("error") or {}).get("code"), expected_codes, msg=rejected)
                self.assertIs(rejected.get("state_changed"), False, msg=rejected)
                attempted_name = payload.get("logical_name")
                if isinstance(attempted_name, str) and attempted_name and ".." not in attempted_name and not attempted_name.startswith("/"):
                    self.assertFalse(self._runtime_path(f"buddyswitch/local/buddybox/pm/{attempted_name}").exists())

        invalid_logical_names = ["/tmp/x", "../x", "notes/../../x"]
        for action in ("read", "delete"):
            for logical_name in invalid_logical_names:
                with self.subTest(action=action, logical_name=logical_name):
                    rejected = self._dispatch(
                        instance_json=instance_json,
                        instance_id=instance_id,
                        buddy="pm",
                        action=action,
                        args={"logical_name": logical_name},
                    )
                    self.assertFalse(rejected.get("ok"), msg=rejected)
                    self.assertEqual((rejected.get("error") or {}).get("code"), "E_BUDDYBOX_LOGICAL_NAME")
                    self.assertIs(rejected.get("state_changed"), False, msg=rejected)

        invalid_read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"logical_name": "missing.txt", "encoding": "utf16"},
        )
        self.assertFalse(invalid_read.get("ok"), msg=invalid_read)
        self.assertEqual((invalid_read.get("error") or {}).get("code"), "E_BUDDYBOX_PAYLOAD")

    def test_buddybox_success_responses_expose_private_file_state_model(self) -> None:
        instance_id = "inst-pm-box-state-model"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        write_payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "state/model.txt", "content": "model"},
        )
        self.assertTrue(write_payload.get("ok"), msg=write_payload)
        self.assertEqual(write_payload.get("visibility"), "active_buddy_private")
        self.assertEqual(write_payload.get("owner_scope"), "active_buddy")
        self.assertEqual(write_payload.get("lifetime_scope"), "active_instance_workspace")
        self.assertFalse(write_payload.get("product_readable"))
        self.assertFalse(write_payload.get("cross_buddy_readable"))
        self.assertFalse(write_payload.get("mutates_product_state"))
        self.assertEqual(write_payload.get("mutated_product_objects"), [])
        self.assertEqual(write_payload.get("durability"), "durable")

        read_payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="read",
            args={"logical_name": "state/model.txt"},
        )
        self.assertTrue(read_payload.get("ok"), msg=read_payload)
        self.assertEqual(read_payload.get("visibility"), "active_buddy_private")
        self.assertEqual(read_payload.get("owner_scope"), "active_buddy")
        self.assertEqual(read_payload.get("lifetime_scope"), "active_instance_workspace")
        self.assertFalse(read_payload.get("product_readable"))
        self.assertFalse(read_payload.get("cross_buddy_readable"))
        self.assertFalse(read_payload.get("mutates_product_state"))
        self.assertEqual(read_payload.get("mutated_product_objects"), [])

        list_payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="list",
            args={"recursive": True},
        )
        self.assertTrue(list_payload.get("ok"), msg=list_payload)
        self.assertEqual(list_payload.get("visibility"), "active_buddy_private")
        self.assertEqual(list_payload.get("owner_scope"), "active_buddy")
        self.assertEqual(list_payload.get("lifetime_scope"), "active_instance_workspace")
        self.assertFalse(list_payload.get("product_readable"))
        self.assertFalse(list_payload.get("cross_buddy_readable"))
        self.assertFalse(list_payload.get("mutates_product_state"))
        self.assertEqual(list_payload.get("mutated_product_objects"), [])

        delete_payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="delete",
            args={"logical_name": "state/model.txt"},
        )
        self.assertTrue(delete_payload.get("ok"), msg=delete_payload)
        self.assertEqual(delete_payload.get("visibility"), "active_buddy_private")
        self.assertEqual(delete_payload.get("owner_scope"), "active_buddy")
        self.assertEqual(delete_payload.get("lifetime_scope"), "active_instance_workspace")
        self.assertFalse(delete_payload.get("product_readable"))
        self.assertFalse(delete_payload.get("cross_buddy_readable"))
        self.assertFalse(delete_payload.get("mutates_product_state"))
        self.assertEqual(delete_payload.get("mutated_product_objects"), [])

    def test_buddybox_operations_do_not_create_product_object_files(self) -> None:
        objects_root = self._runtime_path("buddyswitch/objects")
        self.assertFalse(objects_root.exists())

        instance_id = "inst-pm-box-no-objects-created"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        for action, payload in (
            ("write", {"logical_name": "private/run.txt", "content": "ok"}),
            ("read", {"logical_name": "private/run.txt"}),
            ("list", {"recursive": True}),
            ("delete", {"logical_name": "private/run.txt"}),
        ):
            with self.subTest(action=action):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                    action=action,
                    args=payload,
                )
                self.assertTrue(response.get("ok"), msg=response)
                self.assertFalse(response.get("mutates_product_state"), msg=response)
                self.assertEqual(response.get("mutated_product_objects"), [], msg=response)
        self.assertFalse(objects_root.exists())

    def test_buddybox_operations_do_not_mutate_product_objects(self) -> None:
        track = env_store.create_track(
            "track-pm-buddybox-product-state",
            "Buddybox Product Boundary",
            owner_buddy="pm",
        )
        task = env_store.create_task(
            "task-pm-buddybox-product-state",
            "Buddybox Product Boundary Task",
            buddy="pm",
            track_id=track["id"],
        )
        artifact = env_store.create_artifact_revision(
            artifact_id="art-pm-buddybox-product-state-r1",
            title="Buddybox Product Boundary Artifact",
            summary="seed",
            body="seed",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=track["id"],
            artifact_id=artifact["id"],
            label="Seed",
            from_buddy="pm",
            summary="seed",
        )
        object_paths = (
            env_store.track_file(track["id"]),
            env_store.task_file(task["id"]),
            env_store.artifact_file(artifact["id"]),
        )
        before = {path: path.read_text(encoding="utf-8") for path in object_paths}

        instance_id = "inst-pm-box-no-product-mutation"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        writes = [
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                action="write",
                args={"logical_name": "product-boundary/sample.txt", "content": "ok"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                action="read",
                args={"logical_name": "product-boundary/sample.txt"},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                action="list",
                args={"recursive": True},
            ),
            self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy="pm",
                action="delete",
                args={"logical_name": "product-boundary/sample.txt"},
            ),
        ]
        for payload in writes:
            self.assertTrue(payload.get("ok"), msg=payload)
            self.assertFalse(payload.get("mutates_product_state"), msg=payload)
            self.assertEqual(payload.get("mutated_product_objects"), [], msg=payload)

        after = {path: path.read_text(encoding="utf-8") for path in object_paths}
        self.assertEqual(after, before)

    def test_buddybox_success_affordances_are_structured_and_conditional(self) -> None:
        instance_id = "inst-pm-box-affordance"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "affordances/sample.txt", "content": "ok"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)

        affordances = payload.get("available_affordances")
        self.assertIsInstance(affordances, list, msg=payload)
        assert isinstance(affordances, list)
        self.assertGreaterEqual(len(affordances), 2)
        for row in affordances:
            self.assertIsInstance(row, dict, msg=row)
            assert isinstance(row, dict)
            self.assertIn("tool", row)
            self.assertIn("action", row)
            self.assertIn("effect", row)
            self.assertIn("condition", row)
            self.assertIn("mutates_product_state", row)

        artifact_rows = [row for row in affordances if isinstance(row, dict) and row.get("tool") == "artifact"]
        self.assertEqual(len(artifact_rows), 1, msg=affordances)
        self.assertEqual(artifact_rows[0].get("action"), "create_revision")
        self.assertIn("product-readable", str(artifact_rows[0].get("condition", "")).lower())

        for hint in payload.get("allowed_next_actions", []):
            lowered = str(hint).lower()
            self.assertNotIn("retry with", lowered)
            self.assertNotIn("<active_buddy>", lowered)
            self.assertNotIn("shared state", lowered)
            self.assertNotIn("must create artifact", lowered)

    def test_buddybox_rejections_are_self_correcting_without_path_guidance(self) -> None:
        instance_id = "inst-pm-box-reject-guidance"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            action="write",
            args={"logical_name": "pm/prototypes/hero.html", "content": "x"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        error = payload.get("error")
        self.assertIsInstance(error, dict, msg=payload)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_BUDDYBOX_LOGICAL_NAME")
        self.assertEqual(error.get("class"), "invalid_input")
        self.assertEqual(payload.get("boundary"), "active_buddy_private_file_capability")
        self.assertFalse(payload.get("state_changed"))
        self.assertFalse(payload.get("mutates_product_state"))
        self.assertTrue(payload.get("retryable"))
        self.assertEqual(payload.get("correctable_fields"), ["logical_name"])
        alternatives = payload.get("alternative_capabilities")
        self.assertIsInstance(alternatives, list, msg=payload)
        assert isinstance(alternatives, list)
        self.assertTrue(any(isinstance(row, dict) and row.get("tool") == "artifact" for row in alternatives))

        packed = json.dumps(payload, ensure_ascii=True).lower()
        self.assertNotIn("<active_buddy>/", packed)
        self.assertNotIn("buddyswitch/local/buddybox", packed)
        self.assertNotIn("shared state", packed)
        self.assertNotIn("directly edit", packed)


if __name__ == "__main__":
    unittest.main()
