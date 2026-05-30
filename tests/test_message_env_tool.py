#!/usr/bin/env python3
"""Message env.tool integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.repos import messages as message_repo  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class MessageEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _OBJECT_DIRS = ("tracks", "tasks", "artifacts", "comments", "messages")

    def _normalized_instance_id(self, *, buddy: str, label: str) -> str:
        try:
            return RuntimeActorAddress(buddy_id=buddy, instance_id=label).instance_id
        except ValueError:
            suffix = uuid.uuid5(uuid.NAMESPACE_DNS, f"{buddy}:{label}").hex[:12]
            return f"inst-{buddy}-{suffix}"

    def _actor_address(self, *, buddy: str, label: str) -> dict[str, str]:
        return RuntimeActorAddress(
            buddy_id=buddy,
            instance_id=self._normalized_instance_id(buddy=buddy, label=label),
        ).to_payload()

    def _objects_state(self) -> dict[str, dict[str, object]]:
        snapshot: dict[str, dict[str, object]] = {}
        for object_dir in self._OBJECT_DIRS:
            root = self._runtime_path(f"buddyswitch/objects/{object_dir}")
            files: dict[str, str] = {}
            if root.is_dir():
                for path in sorted(root.glob("*.json")):
                    files[path.name] = path.read_text(encoding="utf-8")
            snapshot[object_dir] = {
                "exists": root.exists(),
                "files": files,
            }
        return snapshot

    def _message_rows(self) -> list[dict[str, object]]:
        root = self._runtime_path("buddyswitch/objects/messages")
        rows: list[dict[str, object]] = []
        if root.is_dir():
            for path in sorted(root.glob("*.json")):
                rows.append(json.loads(path.read_text(encoding="utf-8")))
        return rows

    def _assert_non_message_dirs_unchanged(
        self,
        before: dict[str, dict[str, object]],
        after: dict[str, dict[str, object]],
    ) -> None:
        for object_dir in ("tracks", "tasks", "artifacts", "comments"):
            self.assertEqual(before[object_dir], after[object_dir], msg=object_dir)

    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        normalized_instance_id = self._normalized_instance_id(buddy=buddy, label=instance_id)
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": normalized_instance_id,
                    "buddy": buddy,
                    "status": status,
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
        normalized_instance_id = self._normalized_instance_id(buddy=buddy, label=instance_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-msg-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": normalized_instance_id,
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

    def _patch_daemon(
        self,
        *,
        contacts: dict[str, object] | None = None,
        reachability: dict[str, object] | None = None,
        delivery: dict[str, object] | None = None,
    ) -> list[tuple[str, dict[str, object]]]:
        calls: list[tuple[str, dict[str, object]]] = []
        original_list_contacts = runtime_context.daemon_client.list_contacts
        original_check_reachability = runtime_context.daemon_client.check_reachability
        original_deliver_signal = runtime_context.daemon_client.deliver_signal

        def fake_list_contacts(*, buddy_id: str | None = None) -> dict[str, object]:
            calls.append(("contacts", {"buddy_id": buddy_id}))
            if contacts is not None:
                return contacts
            return {"contacts": [], "count": 0}

        def fake_check_reachability(*, target_actor_address: dict[str, object]) -> dict[str, object]:
            calls.append(("reachability", {"target_actor_address": target_actor_address}))
            if reachability is not None:
                return dict(reachability, target_actor_address=target_actor_address)
            return {
                "reachability_status": "online",
                "target_actor_address": target_actor_address,
                "record": {"actor_address": target_actor_address, "status": "online"},
            }

        def fake_deliver_signal(*, signal: dict[str, object]) -> dict[str, object]:
            calls.append(("deliver", {"signal": signal}))
            if delivery is not None:
                return delivery
            return {
                "delivery_status": "delivered",
                "handling_status": "handled",
                "signal": signal,
            }

        def restore() -> None:
            runtime_context.daemon_client.list_contacts = original_list_contacts
            runtime_context.daemon_client.check_reachability = original_check_reachability
            runtime_context.daemon_client.deliver_signal = original_deliver_signal

        runtime_context.daemon_client.list_contacts = fake_list_contacts
        runtime_context.daemon_client.check_reachability = fake_check_reachability
        runtime_context.daemon_client.deliver_signal = fake_deliver_signal
        self.addCleanup(restore)
        return calls

    def test_message_contacts_lists_online_actor_contacts(self) -> None:
        dev_address = self._actor_address(buddy="dev", label="inst-dev-contact")
        calls = self._patch_daemon(
            contacts={
                "contacts": [
                    {
                        "actor_address": dev_address,
                        "status": "online",
                        "last_seen_at": "2026-05-30T00:00:00Z",
                    }
                ],
                "count": 1,
            }
        )
        instance_json = self._instance_json(instance_id="inst-pm-contacts", buddy="pm")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-contacts",
            buddy="pm",
            tool="message",
            action="contacts",
            args={"buddy": "dev"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(calls, [("contacts", {"buddy_id": "dev"})])
        self.assertEqual(response.get("count"), 1)
        contact = response.get("contacts", [])[0]
        self.assertEqual(contact["buddy_id"], "dev")
        self.assertEqual(contact["actor_address"], dev_address)
        self.assertEqual(contact["contact_status"], "online")
        self.assertIs(contact["sendable"], True)
        self.assertEqual(contact["last_seen_at"], "2026-05-30T00:00:00Z")

    def test_message_contacts_marks_active_buddy_rows_not_sendable(self) -> None:
        active_pm = self._actor_address(buddy="pm", label="inst-pm-contacts-self")
        other_pm = self._actor_address(buddy="pm", label="inst-pm-other")
        market = self._actor_address(buddy="market", label="inst-market-contacts")
        self._patch_daemon(
            contacts={
                "contacts": [
                    {"actor_address": active_pm, "status": "online"},
                    {"actor_address": other_pm, "status": "online"},
                    {"actor_address": market, "status": "online"},
                ],
                "count": 3,
            }
        )
        instance_json = self._instance_json(instance_id="inst-pm-contacts-self", buddy="pm")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-contacts-self",
            buddy="pm",
            tool="message",
            action="contacts",
            args={},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("count"), 3)
        self.assertEqual(response.get("sendable_count"), 1)
        contacts = response.get("contacts")
        self.assertIsInstance(contacts, list, msg=response)
        assert isinstance(contacts, list)
        by_instance = {
            row["actor_address"]["instance_id"]: row
            for row in contacts
            if isinstance(row, dict) and isinstance(row.get("actor_address"), dict)
        }
        for address in (active_pm, other_pm):
            row = by_instance[address["instance_id"]]
            self.assertEqual(row["buddy_id"], "pm")
            self.assertIs(row["sendable"], False)
            self.assertIn("same buddy_id", row.get("why_not_sendable", ""))
        self.assertIs(by_instance[market["instance_id"]]["sendable"], True)
        self.assertIn("target_actor_address", " ".join(response.get("allowed_next_actions", [])))

    def test_message_contacts_rejects_unknown_buddy_filter(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-pm-contacts-unknown", buddy="pm")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-contacts-unknown",
            buddy="pm",
            tool="message",
            action="contacts",
            args={"buddy": "ops"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["buddy"])
        self.assertEqual(calls, [])

    def test_message_send_rejects_to_buddy_field(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-design-old-send", buddy="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-old-send",
            buddy="design",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "Please inspect the prototype."},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["to_buddy"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_rejects_invalid_target_actor_address_without_state_change(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-design-invalid-target", buddy="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-invalid-target",
            buddy="design",
            tool="message",
            action="send",
            args={
                "target_actor_address": {"buddy_id": "Dev", "instance_id": "inst-Dev-daemon"},
                "content": "hello",
            },
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("correctable_fields"), ["target_actor_address"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_rejects_same_buddy_target_without_state_change(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-dev-self", buddy="dev")
        target = self._actor_address(buddy="dev", label="inst-dev-other")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-self",
            buddy="dev",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "self"},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.self_send")
        self.assertEqual(response.get("correctable_fields"), ["target_actor_address"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_target_not_online_creates_no_message(self) -> None:
        calls = self._patch_daemon(reachability={"reachability_status": "registered_offline", "record": None})
        instance_json = self._instance_json(instance_id="inst-pm-offline", buddy="pm")
        target = self._actor_address(buddy="dev", label="inst-dev-offline")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-offline",
            buddy="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reachability")
        self.assertEqual(response.get("reachability_status"), "registered_offline")
        self.assertEqual(response.get("durability"), "none")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(before_state, after_state)
        self.assertEqual([call[0] for call in calls], ["reachability"])

    def test_message_send_never_registered_guides_contacts_refresh(self) -> None:
        self._patch_daemon(reachability={"reachability_status": "never_registered", "record": None})
        instance_json = self._instance_json(instance_id="inst-pm-never-registered", buddy="pm")
        target = self._actor_address(buddy="dev", label="inst-dev-never")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-never-registered",
            buddy="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("reachability_status"), "never_registered")
        self.assertIn("message.contacts", " ".join(response.get("allowed_next_actions", [])))

    def test_message_send_online_target_creates_actor_address_message_and_delivers_signal(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-design-success", buddy="design")
        source = self._actor_address(buddy="design", label="inst-design-success")
        target = self._actor_address(buddy="dev", label="inst-dev-success")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-success",
            buddy="design",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "Please inspect the prototype."},
        )

        after_state = self._objects_state()
        self.assertTrue(response.get("ok"), msg=response)
        self._assert_non_message_dirs_unchanged(before_state, after_state)
        self.assertEqual(response.get("delivery_status"), "delivered")
        self.assertEqual(response.get("created_ids"), [response.get("message_id")])
        rows = self._message_rows()
        self.assertEqual(len(rows), 1)
        msg = rows[0]
        self.assertEqual(msg["from_actor_address"], source)
        self.assertEqual(msg["to_actor_address"], target)
        self.assertEqual(msg["content"], "Please inspect the prototype.")
        self.assertNotIn("from_buddy", msg)
        self.assertNotIn("to_buddy", msg)

        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])
        signal = calls[1][1]["signal"]
        self.assertEqual(signal["type"], "message.available")
        self.assertEqual(signal["source_actor_address"], source)
        self.assertEqual(signal["target_actor_address"], target)
        self.assertEqual(signal["payload"], {"message_id": response.get("message_id")})
        self.assertNotIn("content", signal)
        self.assertNotIn("message", signal)
        self.assertNotIn("from_buddy", signal)
        self.assertNotIn("to_buddy", signal)

    def test_message_send_delivery_failed_cleanup_succeeded_removes_message(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        instance_json = self._instance_json(instance_id="inst-pm-cleanup", buddy="pm")
        target = self._actor_address(buddy="dev", label="inst-dev-cleanup")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-cleanup",
            buddy="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "cleaned")
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(response.get("durability"), "none")
        self.assertIs(response.get("retryable"), True)
        self.assertEqual(before_state, after_state)

    def test_message_send_delivery_failed_cleanup_failed_reports_indeterminate(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        original_delete = getattr(message_repo, "delete_message", None)

        def fail_delete(_message_id: str) -> None:
            raise OSError("unlink failed")

        def restore_delete() -> None:
            if original_delete is None:
                delattr(message_repo, "delete_message")
            else:
                message_repo.delete_message = original_delete

        message_repo.delete_message = fail_delete
        self.addCleanup(restore_delete)
        instance_json = self._instance_json(instance_id="inst-pm-indeterminate", buddy="pm")
        target = self._actor_address(buddy="dev", label="inst-dev-indeterminate")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-indeterminate",
            buddy="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_SEND_INDETERMINATE")
        self.assertEqual(response.get("delivery_status"), "delivery_failed")
        self.assertEqual(response.get("cleanup_status"), "failed")
        self.assertIs(response.get("state_changed"), True)
        self.assertEqual(response.get("durability"), "uncertain")
        self.assertIs(response.get("retryable"), False)
        self.assertIsInstance(response.get("message_id"), str)
        self.assertIn("Do not blindly retry", response.get("retry_guidance", ""))

    def test_message_list_returns_only_messages_to_current_actor_address(self) -> None:
        active = self._actor_address(buddy="dev", label="inst-dev-list")
        other_dev = self._actor_address(buddy="dev", label="inst-dev-other-list")
        pm = self._actor_address(buddy="pm", label="inst-pm-list")
        design = self._actor_address(buddy="design", label="inst-design-list")
        env_store.create_message(from_actor_address=pm, to_actor_address=active, content="PM to active Dev")
        env_store.create_message(from_actor_address=design, to_actor_address=active, content="Design to active Dev")
        env_store.create_message(from_actor_address=pm, to_actor_address=other_dev, content="PM to other Dev")
        env_store.create_message(from_actor_address=active, to_actor_address=pm, content="Dev sent")

        instance_json = self._instance_json(instance_id="inst-dev-list", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-list",
            buddy="dev",
            tool="message",
            action="list",
            args={},
        )

        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 2, msg=response)
        self.assertEqual({row["to_actor_address"]["instance_id"] for row in messages}, {active["instance_id"]})
        self.assertNotIn("from_buddy", json.dumps(messages, ensure_ascii=True))
        self.assertNotIn("to_buddy", json.dumps(messages, ensure_ascii=True))

    def test_message_list_filters_by_sender_buddy_from_actor_address(self) -> None:
        active = self._actor_address(buddy="dev", label="inst-dev-filter")
        pm = self._actor_address(buddy="pm", label="inst-pm-filter")
        design = self._actor_address(buddy="design", label="inst-design-filter")
        env_store.create_message(from_actor_address=pm, to_actor_address=active, content="PM to Dev")
        env_store.create_message(from_actor_address=design, to_actor_address=active, content="Design to Dev")

        instance_json = self._instance_json(instance_id="inst-dev-filter", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-filter",
            buddy="dev",
            tool="message",
            action="list",
            args={"buddy": "design"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 1, msg=response)
        self.assertEqual(messages[0]["from_actor_address"], design)

    def test_message_conversation_returns_visible_bidirectional_actor_messages(self) -> None:
        active = self._actor_address(buddy="dev", label="inst-dev-conversation")
        other_dev = self._actor_address(buddy="dev", label="inst-dev-conversation-other")
        pm = self._actor_address(buddy="pm", label="inst-pm-conversation")
        design = self._actor_address(buddy="design", label="inst-design-conversation")
        market = self._actor_address(buddy="market", label="inst-market-conversation")
        first = message_repo.save_message(
            {
                "id": "msg-conv-visible-1",
                "from_actor_address": pm,
                "to_actor_address": active,
                "content": "PM to active Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        second = message_repo.save_message(
            {
                "id": "msg-conv-visible-2",
                "from_actor_address": active,
                "to_actor_address": pm,
                "content": "Dev to PM",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:02Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-visible-other-dev",
                "from_actor_address": pm,
                "to_actor_address": other_dev,
                "content": "PM to other Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:03Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-visible-design",
                "from_actor_address": design,
                "to_actor_address": pm,
                "content": "Design to PM",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:04Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-visible-market",
                "from_actor_address": market,
                "to_actor_address": active,
                "content": "Market to Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:05Z",
            }
        )
        instance_json = self._instance_json(instance_id="inst-dev-conversation", buddy="dev")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-conversation",
            buddy="dev",
            tool="message",
            action="conversation",
            args={"target_actor_address": pm},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("read_scope"), "active actor visible direct conversation messages")
        self.assertEqual(response.get("selector"), {"target_actor_address": pm})
        messages = response.get("messages")
        self.assertIsInstance(messages, list, msg=response)
        assert isinstance(messages, list)
        self.assertEqual([row["id"] for row in messages], [first["id"], second["id"]])
        self.assertEqual(response.get("count"), 2)
        self.assertEqual({row["content"] for row in messages}, {"PM to active Dev", "Dev to PM"})

    def test_message_conversation_buddy_selector_returns_visible_bidirectional_buddy_messages(self) -> None:
        active = self._actor_address(buddy="dev", label="inst-dev-conversation-buddy")
        pm_one = self._actor_address(buddy="pm", label="inst-pm-conversation-one")
        pm_two = self._actor_address(buddy="pm", label="inst-pm-conversation-two")
        design = self._actor_address(buddy="design", label="inst-design-conversation-buddy")
        one = message_repo.save_message(
            {
                "id": "msg-conv-buddy-1",
                "from_actor_address": pm_one,
                "to_actor_address": active,
                "content": "PM one",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        two = message_repo.save_message(
            {
                "id": "msg-conv-buddy-2",
                "from_actor_address": active,
                "to_actor_address": pm_two,
                "content": "PM two",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:02Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-buddy-design",
                "from_actor_address": design,
                "to_actor_address": active,
                "content": "Design",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:03Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-buddy-internal",
                "from_actor_address": pm_one,
                "to_actor_address": pm_two,
                "content": "PM internal",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:04Z",
            }
        )
        instance_json = self._instance_json(instance_id="inst-dev-conversation-buddy", buddy="dev")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-conversation-buddy",
            buddy="dev",
            tool="message",
            action="conversation",
            args={"buddy": "pm"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("selector"), {"buddy": "pm"})
        messages = response.get("messages", [])
        self.assertEqual([row["id"] for row in messages], [one["id"], two["id"]])

    def test_message_conversation_requires_exactly_one_selector(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-conversation-selector", buddy="dev")
        target = self._actor_address(buddy="pm", label="inst-pm-conversation-selector")
        for args in ({}, {"buddy": "pm", "target_actor_address": target}):
            with self.subTest(args=args):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-conversation-selector",
                    buddy="dev",
                    tool="message",
                    action="conversation",
                    args=args,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
                self.assertEqual(set(response.get("correctable_fields", [])), {"target_actor_address", "buddy"})

    def test_message_conversation_rejects_old_direction_fields(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-conversation-old-fields", buddy="dev")
        for field, value in (("box", "inbox"), ("to_buddy", "pm"), ("from_buddy", "pm")):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-conversation-old-fields",
                    buddy="dev",
                    tool="message",
                    action="conversation",
                    args={"buddy": "pm", field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
                self.assertEqual(response.get("correctable_fields"), [field])

    def test_message_conversation_applies_latest_limit_then_returns_chronological(self) -> None:
        active = self._actor_address(buddy="dev", label="inst-dev-conversation-limit")
        pm = self._actor_address(buddy="pm", label="inst-pm-conversation-limit")
        rows = []
        for index in range(5):
            row = message_repo.save_message(
                {
                    "id": f"msg-conv-limit-{index}",
                    "from_actor_address": pm if index % 2 == 0 else active,
                    "to_actor_address": active if index % 2 == 0 else pm,
                    "content": f"message {index}",
                    "reply_to": None,
                    "created_at": f"2026-05-30T00:00:0{index}Z",
                }
            )
            rows.append(row)
        instance_json = self._instance_json(instance_id="inst-dev-conversation-limit", buddy="dev")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-conversation-limit",
            buddy="dev",
            tool="message",
            action="conversation",
            args={"buddy": "pm", "limit": 3},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual([row["id"] for row in response.get("messages", [])], [row["id"] for row in rows[2:5]])

    def test_message_send_reply_to_accepts_same_visible_actor_conversation_pair(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(buddy="dev", label="inst-dev-reply")
        pm = self._actor_address(buddy="pm", label="inst-pm-reply")
        seed = env_store.create_message(from_actor_address=pm, to_actor_address=dev, content="Hello from PM")
        instance_json = self._instance_json(instance_id="inst-dev-reply", buddy="dev")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-reply",
            buddy="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "ack", "reply_to": seed["id"]},
        )

        self.assertTrue(response.get("ok"), msg=response)
        rows = self._message_rows()
        reply = next(row for row in rows if row["id"] == response["message_id"])
        self.assertEqual(reply["reply_to"], seed["id"])

    def test_message_send_reply_to_requires_same_visible_actor_conversation_pair(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(buddy="dev", label="inst-dev-cross")
        pm = self._actor_address(buddy="pm", label="inst-pm-cross")
        design = self._actor_address(buddy="design", label="inst-design-cross")
        seed = env_store.create_message(from_actor_address=design, to_actor_address=pm, content="Design to PM")
        instance_json = self._instance_json(instance_id="inst-dev-cross", buddy="dev")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cross",
            buddy="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "bad", "reply_to": seed["id"]},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reply_to_scope")
        self.assertEqual(self._message_rows(), [seed])

    def test_message_send_rejects_blank_content(self) -> None:
        self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-pm-blank", buddy="pm")
        target = self._actor_address(buddy="dev", label="inst-dev-blank")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-blank",
            buddy="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "   "},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_rejects_broadcast_recipient_and_status_payload_fields(self) -> None:
        self._patch_daemon()
        instance_json = self._instance_json(instance_id="inst-pm-extra-fields", buddy="pm")
        target = self._actor_address(buddy="dev", label="inst-dev-extra-fields")
        for field, value in (("broadcast", True), ("recipients", ["dev"]), ("status", "unread")):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-pm-extra-fields",
                    buddy="pm",
                    tool="message",
                    action="send",
                    args={"target_actor_address": target, "content": "x", field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("correctable_fields"), [field])

    def test_message_list_rejects_product_binding_and_status_fields(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-message-bindings", buddy="dev")
        for field, value in (
            ("track_id", "track-x"),
            ("artifact_id", "art-x"),
            ("request_id", "req-x"),
            ("refs", []),
            ("status", "unread"),
        ):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-message-bindings",
                    buddy="dev",
                    tool="message",
                    action="list",
                    args={field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")

    def test_message_storage_boundary_has_no_buddy_level_fields(self) -> None:
        source = (ROOT / "scripts" / "env" / "repos" / "messages.py").read_text(encoding="utf-8")
        self.assertNotIn("from_buddy", source)
        self.assertNotIn("to_buddy", source)

    def test_message_edit_delete_and_read_receipt_actions_are_unsupported(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-unsup", buddy="dev")
        for action in ("edit", "update", "delete", "mark_read", "read"):
            with self.subTest(action=action):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-unsup",
                    buddy="dev",
                    tool="message",
                    action=action,
                    args={},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertIn("E_ENV_TOOL", response.get("error", {}).get("code", ""))


if __name__ == "__main__":
    unittest.main()
