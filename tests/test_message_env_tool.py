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
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class MessageEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _OBJECT_DIRS = ("tracks", "tasks", "artifacts", "comments", "messages")

    def _normalized_actor_id(self, *, role: str, label: str) -> str:
        try:
            return ActorAddress(role_id=role, actor_id=label).actor_id
        except ValueError:
            suffix = uuid.uuid5(uuid.NAMESPACE_DNS, f"{role}:{label}").hex[:12]
            return f"act-{role}-{suffix}"

    def _actor_address(self, *, role: str, label: str) -> dict[str, str]:
        return ActorAddress(
            role_id=role,
            actor_id=self._normalized_actor_id(role=role, label=label),
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

    def _instance_json(self, *, actor_id: str, role: str, status: str = "active") -> Path:
        normalized_actor_id = self._normalized_actor_id(role=role, label=actor_id)
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "actor_id": normalized_actor_id,
                    "role": role,
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
        actor_id: str,
        role: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        normalized_actor_id = self._normalized_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-msg-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": normalized_actor_id,
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

        def fake_list_contacts(*, role_id: str | None = None) -> dict[str, object]:
            calls.append(("contacts", {"role_id": role_id}))
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
        dev_address = self._actor_address(role="dev", label="act-dev-contact")
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
        instance_json = self._instance_json(actor_id="act-pm-contacts", role="pm")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-contacts",
            role="pm",
            tool="message",
            action="contacts",
            args={"role": "dev"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(calls, [("contacts", {"role_id": "dev"})])
        self.assertEqual(response.get("count"), 1)
        contact = response.get("contacts", [])[0]
        self.assertEqual(contact["role_id"], "dev")
        self.assertEqual(contact["actor_address"], dev_address)
        self.assertEqual(contact["contact_status"], "online")
        self.assertIs(contact["sendable"], True)
        self.assertEqual(contact["last_seen_at"], "2026-05-30T00:00:00Z")

    def test_message_contacts_marks_only_active_actor_row_not_sendable(self) -> None:
        active_pm = self._actor_address(role="pm", label="act-pm-contacts-self")
        other_pm = self._actor_address(role="pm", label="act-pm-other")
        market = self._actor_address(role="market", label="act-market-contacts")
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
        instance_json = self._instance_json(actor_id="act-pm-contacts-self", role="pm")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-contacts-self",
            role="pm",
            tool="message",
            action="contacts",
            args={},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("count"), 3)
        self.assertEqual(response.get("sendable_count"), 2)
        contacts = response.get("contacts")
        self.assertIsInstance(contacts, list, msg=response)
        assert isinstance(contacts, list)
        by_instance = {
            row["actor_address"]["actor_id"]: row
            for row in contacts
            if isinstance(row, dict) and isinstance(row.get("actor_address"), dict)
        }
        active_row = by_instance[active_pm["actor_id"]]
        self.assertEqual(active_row["role_id"], "pm")
        self.assertIs(active_row["sendable"], False)
        why_not_sendable = active_row.get("why_not_sendable", "")
        self.assertIn("active actor itself", why_not_sendable)
        self.assertNotIn("same role", why_not_sendable.lower())
        other_pm_row = by_instance[other_pm["actor_id"]]
        self.assertEqual(other_pm_row["role_id"], "pm")
        self.assertIs(other_pm_row["sendable"], True)
        self.assertIs(by_instance[market["actor_id"]]["sendable"], True)
        self.assertIn("target_actor_address", " ".join(response.get("allowed_next_actions", [])))

    def test_message_contacts_rejects_unknown_role_filter(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-contacts-unknown", role="pm")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-contacts-unknown",
            role="pm",
            tool="message",
            action="contacts",
            args={"role": "ops"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["role"])
        self.assertEqual(calls, [])

    def test_message_send_rejects_to_role_field(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-design-old-send", role="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-design-old-send",
            role="design",
            tool="message",
            action="send",
            args={"to_role": "dev", "content": "Please inspect the prototype."},
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertEqual(response.get("correctable_fields"), ["to_role"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_rejects_invalid_target_actor_address_without_state_change(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-design-invalid-target", role="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-design-invalid-target",
            role="design",
            tool="message",
            action="send",
            args={
                "target_actor_address": {"role_id": "Dev", "actor_id": "act-Dev-daemon"},
                "content": "hello",
            },
        )

        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("correctable_fields"), ["target_actor_address"])
        self.assertEqual(before_state, after_state)
        self.assertEqual(calls, [])

    def test_message_send_rejects_same_actor_target_without_state_change(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-dev-self", role="dev")
        target = self._actor_address(role="dev", label="act-dev-self")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-self",
            role="dev",
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

    def test_message_send_allows_same_role_different_actor(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-source", role="pm")
        source = self._actor_address(role="pm", label="act-pm-source")
        target = self._actor_address(role="pm", label="act-pm-target")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-source",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "same role works"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "delivered")
        rows = self._message_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["from_actor_address"], source)
        self.assertEqual(rows[0]["to_actor_address"], target)
        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])

    def test_message_send_target_not_online_creates_no_message(self) -> None:
        calls = self._patch_daemon(reachability={"reachability_status": "registered_offline", "record": None})
        instance_json = self._instance_json(actor_id="act-pm-offline", role="pm")
        target = self._actor_address(role="dev", label="act-dev-offline")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-offline",
            role="pm",
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
        instance_json = self._instance_json(actor_id="act-pm-never-registered", role="pm")
        target = self._actor_address(role="dev", label="act-dev-never")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-never-registered",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "hello"},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("reachability_status"), "never_registered")
        self.assertIn("message.contacts", " ".join(response.get("allowed_next_actions", [])))

    def test_message_send_online_target_creates_actor_address_message_and_delivers_signal(self) -> None:
        calls = self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-design-success", role="design")
        source = self._actor_address(role="design", label="act-design-success")
        target = self._actor_address(role="dev", label="act-dev-success")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-design-success",
            role="design",
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
        self.assertNotIn("from_role", msg)
        self.assertNotIn("to_role", msg)

        self.assertEqual([call[0] for call in calls], ["reachability", "deliver"])
        signal = calls[1][1]["signal"]
        self.assertEqual(signal["type"], "message.available")
        self.assertEqual(signal["source_actor_address"], source)
        self.assertEqual(signal["target_actor_address"], target)
        self.assertEqual(signal["payload"], {"message_id": response.get("message_id")})
        self.assertNotIn("content", signal)
        self.assertNotIn("message", signal)
        self.assertNotIn("from_role", signal)
        self.assertNotIn("to_role", signal)

    def test_message_send_delivery_failed_cleanup_succeeded_removes_message(self) -> None:
        self._patch_daemon(delivery={"delivery_status": "delivery_failed", "signal_error": "socket gone"})
        instance_json = self._instance_json(actor_id="act-pm-cleanup", role="pm")
        target = self._actor_address(role="dev", label="act-dev-cleanup")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-cleanup",
            role="pm",
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
        instance_json = self._instance_json(actor_id="act-pm-indeterminate", role="pm")
        target = self._actor_address(role="dev", label="act-dev-indeterminate")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-indeterminate",
            role="pm",
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
        active = self._actor_address(role="dev", label="act-dev-list")
        other_dev = self._actor_address(role="dev", label="act-dev-other-list")
        pm = self._actor_address(role="pm", label="act-pm-list")
        design = self._actor_address(role="design", label="act-design-list")
        env_store.create_message(from_actor_address=pm, to_actor_address=active, content="PM to active Dev")
        env_store.create_message(from_actor_address=design, to_actor_address=active, content="Design to active Dev")
        env_store.create_message(from_actor_address=pm, to_actor_address=other_dev, content="PM to other Dev")
        env_store.create_message(from_actor_address=active, to_actor_address=pm, content="Dev sent")

        instance_json = self._instance_json(actor_id="act-dev-list", role="dev")
        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-list",
            role="dev",
            tool="message",
            action="list",
            args={},
        )

        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 2, msg=response)
        self.assertEqual({row["to_actor_address"]["actor_id"] for row in messages}, {active["actor_id"]})
        self.assertNotIn("from_role", json.dumps(messages, ensure_ascii=True))
        self.assertNotIn("to_role", json.dumps(messages, ensure_ascii=True))

    def test_message_list_filters_by_sender_role_from_actor_address(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-filter")
        pm = self._actor_address(role="pm", label="act-pm-filter")
        design = self._actor_address(role="design", label="act-design-filter")
        env_store.create_message(from_actor_address=pm, to_actor_address=active, content="PM to Dev")
        env_store.create_message(from_actor_address=design, to_actor_address=active, content="Design to Dev")

        instance_json = self._instance_json(actor_id="act-dev-filter", role="dev")
        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-filter",
            role="dev",
            tool="message",
            action="list",
            args={"role": "design"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 1, msg=response)
        self.assertEqual(messages[0]["from_actor_address"], design)

    def test_message_conversation_returns_visible_bidirectional_actor_messages(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-conversation")
        other_dev = self._actor_address(role="dev", label="act-dev-conversation-other")
        pm = self._actor_address(role="pm", label="act-pm-conversation")
        design = self._actor_address(role="design", label="act-design-conversation")
        market = self._actor_address(role="market", label="act-market-conversation")
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
        instance_json = self._instance_json(actor_id="act-dev-conversation", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation",
            role="dev",
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

    def test_message_conversation_role_selector_returns_visible_bidirectional_role_messages(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-conversation-role")
        peer = self._actor_address(role="dev", label="act-dev-conversation-peer")
        unrelated_one = self._actor_address(role="dev", label="act-dev-conversation-unrelated-one")
        unrelated_two = self._actor_address(role="dev", label="act-dev-conversation-unrelated-two")
        market = self._actor_address(role="market", label="act-market-conversation-role")
        one = message_repo.save_message(
            {
                "id": "msg-conv-role-1",
                "from_actor_address": peer,
                "to_actor_address": active,
                "content": "Dev peer to active Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:01Z",
            }
        )
        two = message_repo.save_message(
            {
                "id": "msg-conv-role-2",
                "from_actor_address": active,
                "to_actor_address": peer,
                "content": "Active Dev to dev peer",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:02Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-role-market",
                "from_actor_address": market,
                "to_actor_address": active,
                "content": "Market to active Dev",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:03Z",
            }
        )
        message_repo.save_message(
            {
                "id": "msg-conv-role-internal",
                "from_actor_address": unrelated_one,
                "to_actor_address": unrelated_two,
                "content": "Unrelated dev internal",
                "reply_to": None,
                "created_at": "2026-05-30T00:00:04Z",
            }
        )
        instance_json = self._instance_json(actor_id="act-dev-conversation-role", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation-role",
            role="dev",
            tool="message",
            action="conversation",
            args={"role": "dev"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("selector"), {"role": "dev"})
        messages = response.get("messages", [])
        self.assertEqual([row["id"] for row in messages], [one["id"], two["id"]])
        self.assertNotIn("active role", str(response.get("why_blocked", "")).lower())

    def test_message_conversation_requires_exactly_one_selector(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-conversation-selector", role="dev")
        target = self._actor_address(role="pm", label="act-pm-conversation-selector")
        for args in ({}, {"role": "pm", "target_actor_address": target}):
            with self.subTest(args=args):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-conversation-selector",
                    role="dev",
                    tool="message",
                    action="conversation",
                    args=args,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
                self.assertEqual(set(response.get("correctable_fields", [])), {"target_actor_address", "role"})

    def test_message_conversation_rejects_old_direction_fields(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-conversation-old-fields", role="dev")
        for field, value in (("box", "inbox"), ("to_role", "pm"), ("from_role", "pm")):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-conversation-old-fields",
                    role="dev",
                    tool="message",
                    action="conversation",
                    args={"role": "pm", field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
                self.assertEqual(response.get("correctable_fields"), [field])

    def test_message_conversation_applies_latest_limit_then_returns_chronological(self) -> None:
        active = self._actor_address(role="dev", label="act-dev-conversation-limit")
        pm = self._actor_address(role="pm", label="act-pm-conversation-limit")
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
        instance_json = self._instance_json(actor_id="act-dev-conversation-limit", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-conversation-limit",
            role="dev",
            tool="message",
            action="conversation",
            args={"role": "pm", "limit": 3},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual([row["id"] for row in response.get("messages", [])], [row["id"] for row in rows[2:5]])

    def test_message_send_reply_to_accepts_same_visible_actor_conversation_pair(self) -> None:
        self._patch_daemon()
        dev = self._actor_address(role="dev", label="act-dev-reply")
        pm = self._actor_address(role="pm", label="act-pm-reply")
        seed = env_store.create_message(from_actor_address=pm, to_actor_address=dev, content="Hello from PM")
        instance_json = self._instance_json(actor_id="act-dev-reply", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-reply",
            role="dev",
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
        dev = self._actor_address(role="dev", label="act-dev-cross")
        pm = self._actor_address(role="pm", label="act-pm-cross")
        design = self._actor_address(role="design", label="act-design-cross")
        seed = env_store.create_message(from_actor_address=design, to_actor_address=pm, content="Design to PM")
        instance_json = self._instance_json(actor_id="act-dev-cross", role="dev")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-dev-cross",
            role="dev",
            tool="message",
            action="send",
            args={"target_actor_address": pm, "content": "bad", "reply_to": seed["id"]},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reply_to_scope")
        self.assertEqual(self._message_rows(), [seed])

    def test_message_send_rejects_blank_content(self) -> None:
        self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-blank", role="pm")
        target = self._actor_address(role="dev", label="act-dev-blank")

        response = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-blank",
            role="pm",
            tool="message",
            action="send",
            args={"target_actor_address": target, "content": "   "},
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_rejects_broadcast_recipient_and_status_payload_fields(self) -> None:
        self._patch_daemon()
        instance_json = self._instance_json(actor_id="act-pm-extra-fields", role="pm")
        target = self._actor_address(role="dev", label="act-dev-extra-fields")
        for field, value in (("broadcast", True), ("recipients", ["dev"]), ("status", "unread")):
            with self.subTest(field=field):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-pm-extra-fields",
                    role="pm",
                    tool="message",
                    action="send",
                    args={"target_actor_address": target, "content": "x", field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("correctable_fields"), [field])

    def test_message_list_rejects_product_binding_and_status_fields(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-message-bindings", role="dev")
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
                    actor_id="act-dev-message-bindings",
                    role="dev",
                    tool="message",
                    action="list",
                    args={field: value},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")

    def test_message_storage_boundary_has_no_role_level_fields(self) -> None:
        source = (ROOT / "scripts" / "env" / "repos" / "messages.py").read_text(encoding="utf-8")
        self.assertNotIn("from_role", source)
        self.assertNotIn("to_role", source)

    def test_message_edit_delete_and_read_receipt_actions_are_unsupported(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-unsup", role="dev")
        for action in ("edit", "update", "delete", "mark_read", "read"):
            with self.subTest(action=action):
                response = self._dispatch(
                    instance_json=instance_json,
                    actor_id="act-dev-unsup",
                    role="dev",
                    tool="message",
                    action=action,
                    args={},
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertIn("E_ENV_TOOL", response.get("error", {}).get("code", ""))


if __name__ == "__main__":
    unittest.main()
