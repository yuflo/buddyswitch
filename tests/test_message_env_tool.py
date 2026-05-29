#!/usr/bin/env python3
"""Message env.tool integration tests."""

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

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tool_runtime import daemon_presence  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class MessageEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _OBJECT_DIRS = ("tracks", "tasks", "artifacts", "comments", "messages")

    def setUp(self) -> None:
        super().setUp()
        daemon_presence.clear_registry()

    def _normalized_instance_id(self, *, buddy: str, label: str) -> str:
        try:
            return RuntimeActorAddress(buddy_id=buddy, instance_id=label).instance_id
        except ValueError:
            suffix = uuid.uuid5(uuid.NAMESPACE_DNS, f"{buddy}:{label}").hex[:12]
            return f"inst-{buddy}-{suffix}"

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

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
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

    def _register_online_actor(
        self,
        *,
        buddy: str,
        label: str,
        endpoint: dict[str, object],
    ) -> RuntimeActorAddress:
        address = RuntimeActorAddress(
            buddy_id=buddy,
            instance_id=self._normalized_instance_id(buddy=buddy, label=label),
        )
        daemon_presence.register_online_actor(actor_address=address, endpoint=endpoint)
        return address

    def _read_jsonl_events(self, path: Path) -> list[dict[str, object]]:
        if not path.exists():
            return []
        rows: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
        return rows

    def test_send_message_creates_inbox_message_for_target_buddy(self):
        instance_json = self._instance_json(instance_id="inst-design-msg", buddy="design")
        before_state = self._objects_state()
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-msg",
            buddy="design",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "Please inspect the prototype."},
        )
        after_state = self._objects_state()
        self.assertTrue(response.get("ok"), msg=response)
        self._assert_non_message_dirs_unchanged(before_state, after_state)
        self.assertNotEqual(before_state["messages"], after_state["messages"])
        self.assertIn("message_id", response)
        self.assertIn("message", response)
        self.assertEqual(response.get("notification_status"), "skipped_offline")
        msg = response["message"]
        self.assertEqual(msg["from_buddy"], "design")
        self.assertEqual(msg["to_buddy"], "dev")
        self.assertEqual(msg["content"], "Please inspect the prototype.")
        self.assertIsNone(msg["reply_to"])
        self.assertIsInstance(msg["created_at"], str)
        self.assertNotIn("status", msg)

    def test_message_send_online_target_records_reference_only_notification_event(self):
        event_path = self._runtime_path("dev-message-events.jsonl")
        target_address = self._register_online_actor(
            buddy="dev",
            label="inst-dev-online-message-target",
            endpoint={"kind": "daemon_state_file", "path": str(event_path)},
        )
        instance_json = self._instance_json(instance_id="inst-design-online-msg", buddy="design")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-online-msg",
            buddy="design",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "The reference-only notification should be available."},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("notification_status"), "delivered")
        events = self._read_jsonl_events(event_path)
        self.assertEqual(len(events), 1, msg=events)
        event = events[0]
        self.assertEqual(event["type"], "message.available")
        self.assertEqual(event["message_id"], response["message_id"])
        self.assertEqual(event["to_actor_address"], target_address.to_payload())
        self.assertEqual(
            event["from_actor_address"],
            {
                "buddy_id": "design",
                "instance_id": self._normalized_instance_id(buddy="design", label="inst-design-online-msg"),
            },
        )
        for forbidden_field in ("content", "message", "from_buddy", "to_buddy"):
            self.assertNotIn(forbidden_field, event)

    def test_message_send_delivery_failure_keeps_durable_message(self):
        self._register_online_actor(
            buddy="dev",
            label="inst-dev-delivery-failure",
            endpoint={"kind": "failing", "message": "target daemon socket closed"},
        )
        instance_json = self._instance_json(instance_id="inst-design-delivery-failure", buddy="design")
        before_state = self._objects_state()

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-delivery-failure",
            buddy="design",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "Durable write must survive delivery failure."},
        )
        after_state = self._objects_state()

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("notification_status"), "delivery_failed")
        self.assertIn("target daemon socket closed", response.get("notification_error", ""))
        self.assertIn("message_id", response)
        self.assertNotEqual(before_state["messages"], after_state["messages"])
        self.assertIsNotNone(env_store.get_message(response["message_id"]))

    def test_message_send_ambiguous_online_actor_keeps_message_without_event(self):
        first_event_path = self._runtime_path("dev-first-events.jsonl")
        second_event_path = self._runtime_path("dev-second-events.jsonl")
        self._register_online_actor(
            buddy="dev",
            label="inst-dev-ambiguous-one",
            endpoint={"kind": "daemon_state_file", "path": str(first_event_path)},
        )
        self._register_online_actor(
            buddy="dev",
            label="inst-dev-ambiguous-two",
            endpoint={"kind": "daemon_state_file", "path": str(second_event_path)},
        )
        instance_json = self._instance_json(instance_id="inst-pm-ambiguous-msg", buddy="pm")

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-ambiguous-msg",
            buddy="pm",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "Do not choose between multiple online dev actors."},
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("notification_status"), "ambiguous_online_actor")
        self.assertIn("message_id", response)
        self.assertIsNotNone(env_store.get_message(response["message_id"]))
        self.assertEqual(self._read_jsonl_events(first_event_path), [])
        self.assertEqual(self._read_jsonl_events(second_event_path), [])

    def test_message_list_returns_only_messages_to_active_buddy(self):
        # Seed messages from different buddies to dev
        env_store.create_message(from_buddy="design", to_buddy="dev", content="Design to Dev")
        env_store.create_message(from_buddy="pm", to_buddy="dev", content="PM to Dev")
        env_store.create_message(from_buddy="dev", to_buddy="design", content="Dev to Design")
        env_store.create_message(from_buddy="market", to_buddy="pm", content="Market to PM")

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
        to_buddies = {m["to_buddy"] for m in messages}
        self.assertEqual(to_buddies, {"dev"})
        # Dev's sent message should not appear
        from_buddies = {m["from_buddy"] for m in messages}
        self.assertNotIn("dev", from_buddies)
        # PM-only message should not be in dev's inbox
        pm_to_pm_ids = {m["id"] for m in messages if m.get("to_buddy") == "pm"}
        self.assertEqual(len(pm_to_pm_ids), 0)

    def test_message_list_filters_by_sender_buddy(self):
        env_store.create_message(from_buddy="design", to_buddy="dev", content="D1")
        env_store.create_message(from_buddy="pm", to_buddy="dev", content="D2")

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
        self.assertGreater(len(messages), 0)
        for msg in messages:
            self.assertEqual(msg["from_buddy"], "design")

    def test_message_list_q_filters_active_buddy_inbox_only(self):
        env_store.create_message(from_buddy="pm", to_buddy="dev", content="Need Wukong proof asset")
        env_store.create_message(from_buddy="design", to_buddy="dev", content="Hero screenshot ready")
        env_store.create_message(from_buddy="market", to_buddy="pm", content="Wukong not in dev inbox")
        env_store.create_message(from_buddy="dev", to_buddy="design", content="Wukong sent by dev")

        instance_json = self._instance_json(instance_id="inst-dev-message-q", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-message-q",
            buddy="dev",
            tool="message",
            action="list",
            args={"q": "wukong"},
        )
        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 1, msg=response)
        self.assertEqual(messages[0]["from_buddy"], "pm")
        self.assertEqual(messages[0]["to_buddy"], "dev")
        self.assertIn("Wukong", messages[0]["content"])

    def test_message_list_limit_bounds_active_buddy_inbox(self):
        env_store.create_message(from_buddy="pm", to_buddy="dev", content="one")
        env_store.create_message(from_buddy="design", to_buddy="dev", content="two")
        env_store.create_message(from_buddy="market", to_buddy="dev", content="three")

        instance_json = self._instance_json(instance_id="inst-dev-message-limit", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-message-limit",
            buddy="dev",
            tool="message",
            action="list",
            args={"limit": 2},
        )
        self.assertTrue(response.get("ok"), msg=response)
        messages = response.get("messages", [])
        self.assertEqual(len(messages), 2, msg=response)
        self.assertEqual(response.get("discovery_summary", {}).get("count"), 2)

    def test_message_list_rejects_product_binding_fields(self):
        instance_json = self._instance_json(instance_id="inst-dev-message-bindings", buddy="dev")
        for field, value in (
            ("track_id", "track-x"),
            ("artifact_id", "art-x"),
            ("request_id", "req-x"),
            ("refs", []),
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
                self.assertIn(field, json.dumps(response, ensure_ascii=True))

    def test_message_list_rejects_status_filter(self):
        instance_json = self._instance_json(instance_id="inst-dev-status", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-status",
            buddy="dev",
            tool="message",
            action="list",
            args={"status": "unread"},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_list_is_read_only(self):
        env_store.create_message(from_buddy="design", to_buddy="dev", content="Design to Dev")
        instance_json = self._instance_json(instance_id="inst-dev-ro", buddy="dev")
        before_state = self._objects_state()

        # List twice and verify no state change
        response1 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-ro",
            buddy="dev",
            tool="message",
            action="list",
            args={},
        )
        response2 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-ro",
            buddy="dev",
            tool="message",
            action="list",
            args={},
        )
        after_state = self._objects_state()
        self.assertTrue(response1.get("ok"), msg=response1)
        self.assertTrue(response2.get("ok"), msg=response2)
        self.assertIs(response1.get("state_changed"), False)
        self.assertEqual(before_state, after_state)
        for row in response1.get("messages", []):
            self.assertNotIn("status", row)
            self.assertNotIn("read_at", row)

    def test_message_send_rejects_self_send(self):
        instance_json = self._instance_json(instance_id="inst-dev-self", buddy="dev")
        before_state = self._objects_state()
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-self",
            buddy="dev",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "self"},
        )
        after_state = self._objects_state()
        self.assertFalse(response.get("ok"), msg=response)
        boundary = response.get("permission_boundary")
        self.assertEqual(boundary, "message.self_send")
        self.assertEqual(before_state, after_state)

    def test_message_send_rejects_unknown_target_buddy(self):
        instance_json = self._instance_json(instance_id="inst-dev-unknown", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-unknown",
            buddy="dev",
            tool="message",
            action="send",
            args={"to_buddy": "ops", "content": "hello"},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_rejects_blank_content(self):
        instance_json = self._instance_json(instance_id="inst-pm-blank", buddy="pm")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-blank",
            buddy="pm",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "   "},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_rejects_broadcast_payload_fields(self):
        instance_json = self._instance_json(instance_id="inst-pm-bc", buddy="pm")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-bc",
            buddy="pm",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "x", "broadcast": True},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_rejects_recipients_field(self):
        instance_json = self._instance_json(instance_id="inst-pm-recip", buddy="pm")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-recip",
            buddy="pm",
            tool="message",
            action="send",
            args={"to_buddy": "dev", "content": "x", "recipients": ["dev", "design"]},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertIn("E_MESSAGE_PAYLOAD", response.get("error", {}).get("code", ""))

    def test_message_send_reply_to_accepts_same_visible_conversation_pair(self):
        # PM sends to Dev
        seed = env_store.create_message(from_buddy="pm", to_buddy="dev", content="Hello from PM")
        instance_json = self._instance_json(instance_id="inst-dev-reply", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-reply",
            buddy="dev",
            tool="message",
            action="send",
            args={"to_buddy": "pm", "content": "ack", "reply_to": seed["id"]},
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["message"]["reply_to"], seed["id"])

    def test_message_send_reply_to_requires_same_visible_conversation_pair(self):
        # Design sends to PM (not visible to dev)
        seed = env_store.create_message(from_buddy="design", to_buddy="pm", content="Design to PM")
        instance_json = self._instance_json(instance_id="inst-dev-cross", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-cross",
            buddy="dev",
            tool="message",
            action="send",
            args={"to_buddy": "pm", "content": "bad", "reply_to": seed["id"]},
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "message.reply_to_scope")

    def test_message_edit_delete_actions_are_unsupported(self):
        instance_json = self._instance_json(instance_id="inst-dev-unsup", buddy="dev")
        for action in ("edit", "update", "delete"):
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

    def test_message_status_fields_are_rejected(self):
        instance_json = self._instance_json(instance_id="inst-dev-status-rej", buddy="dev")
        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-status-rej",
            buddy="dev",
            tool="message",
            action="send",
            args={"to_buddy": "pm", "content": "x", "status": "unread"},
        )
        self.assertFalse(response.get("ok"), msg=response)

    def test_message_read_receipt_actions_are_unsupported(self):
        instance_json = self._instance_json(instance_id="inst-dev-rr", buddy="dev")
        for action in ("mark_read", "read"):
            with self.subTest(action=action):
                response = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-dev-rr",
                    buddy="dev",
                    tool="message",
                    action=action,
                    args={},
                )
                self.assertFalse(response.get("ok"), msg=response)


if __name__ == "__main__":
    unittest.main()
