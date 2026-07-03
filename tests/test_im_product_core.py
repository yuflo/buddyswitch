#!/usr/bin/env python3
"""Central IM product-core tests."""

from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.services import messages as message_service  # noqa: E402
from env.repos import messages as message_repo  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class ImProductCoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_central_im_repo_does_not_export_legacy_actor_address_message_apis(self) -> None:
        for name in ("create_message", "save_message", "list_messages", "get_message", "delete_message"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(message_repo, name))

    def _actor_identity(self, *, role: str = "market", label: str = "target") -> dict[str, object]:
        identity_id = self._runtime_actor_id(role=role, label=label)
        return {"identity": {"id": identity_id, "type": "actor"}, "identity_id": identity_id, "role_id": role}

    def _external_connection(
        self,
        *,
        display_name: str = "local smoke",
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        created = message_service.create_external_connection(display_name=display_name)
        self.assertTrue(created.get("ok"), msg=created)
        connection_key = created.get("connection_key")
        self.assertIsInstance(connection_key, str, msg=created)
        assert isinstance(connection_key, str)
        auth = message_service.authenticate_external_connection_key(connection_key)
        self.assertTrue(auth.get("ok"), msg=auth)
        connection = auth.get("connection")
        identity = auth.get("identity")
        self.assertIsInstance(connection, dict, msg=auth)
        self.assertIsInstance(identity, dict, msg=auth)
        assert isinstance(connection, dict)
        assert isinstance(identity, dict)
        return created, connection, identity

    def test_create_external_connection_returns_only_connection_key_and_persists_internal_state(self) -> None:
        response = message_service.create_external_connection(display_name="local smoke")

        self.assertTrue(response.get("ok"), msg=response)
        connection_key = response.get("connection_key")
        self.assertIsInstance(connection_key, str, msg=response)
        assert isinstance(connection_key, str)
        self.assertTrue(connection_key.startswith("imck-"), msg=response)
        self.assertNotIn("participant", response)
        self.assertNotIn("participant_" + "token", response)
        self.assertNotIn("event_" + "cursor", response)
        self.assertNotIn("client_kind", response)

        auth = message_service.authenticate_external_connection_key(connection_key)
        self.assertTrue(auth.get("ok"), msg=auth)
        identity = auth.get("identity")
        connection = auth.get("connection")
        self.assertIsInstance(identity, dict, msg=auth)
        self.assertIsInstance(connection, dict, msg=auth)
        assert isinstance(identity, dict)
        assert isinstance(connection, dict)
        self.assertEqual(identity.get("type"), "external")
        external_id = identity.get("id")
        self.assertIsInstance(external_id, str, msg=auth)
        assert isinstance(external_id, str)

        profile_path = self.runtime_state_root / "buddyswitch" / "objects" / "identities" / "externals" / f"{external_id}.json"
        self.assertTrue(profile_path.is_file())
        profile_row = json.loads(profile_path.read_text(encoding="utf-8"))
        self.assertEqual(profile_row["identity"], {"id": external_id, "type": "external"})
        self.assertEqual(profile_row["display_name"], "local smoke")

        connection_files = sorted((self.runtime_state_root / "im" / "connections").glob("*.json"))
        self.assertEqual(len(connection_files), 1)
        connection_text = connection_files[0].read_text(encoding="utf-8")
        self.assertNotIn(connection_key, connection_text)
        connection_row = json.loads(connection_text)
        self.assertEqual(connection_row["identity_id"], external_id)
        self.assertNotIn("participant", connection_row)
        self.assertEqual(connection_row["display_name"], "local smoke")
        self.assertEqual(connection_row["last_event_id"], "imev-000000000000")
        self.assertTrue(str(connection_row["connection_key_hash"]).startswith("sha256:"))
        self.assertEqual(auth["identity"], {"id": external_id, "type": "external"})

    def test_list_im_actor_contacts_projects_online_runtime_rows_without_actor_address(self) -> None:
        market = self._actor_identity(role="market", label="act-market-contact")
        dev = self._actor_identity(role="dev", label="act-dev-contact")

        response = message_service.list_im_actor_contacts(
            [
                {"identity_id": market["identity_id"], "role_id": market["role_id"], "status": "online"},
                {"identity_id": dev["identity_id"], "role_id": dev["role_id"], "status": "idle"},
                {"identity_id": "", "role_id": "bad", "status": "online"},
                {"identity_id": market["identity_id"], "role_id": market["role_id"], "status": "offline"},
                {"status": "online"},
            ],
            role_id=None,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(
            response,
            {
                "ok": True,
                "actors": [
                    {
                        "identity": market["identity"],
                        "identity_id": market["identity_id"],
                        "role_id": "market",
                        "reachability_status": "online",
                    },
                    {
                        "identity": dev["identity"],
                        "identity_id": dev["identity_id"],
                        "role_id": "dev",
                        "reachability_status": "idle",
                    },
                ],
                "count": 2,
            },
        )
        self.assertTrue(all("actor_address" not in row for row in response["actors"]))

    def test_actor_directed_target_rejects_external_identity_without_mutating_state(self) -> None:
        _created, _connection, external = self._external_connection()
        external_id = str(external["id"])
        before = {
            name: sorted(path.name for path in (self.runtime_state_root / "im" / name).glob("*.json"))
            for name in ("conversations", "messages", "events", "message_states")
        }

        response = message_service.actor_identity_for_current_send_target(
            [],
            external_id,
            field="target_identity_id",
            active_identity_id=self._runtime_actor_id(role="dev", label="act-dev-active"),
        )

        after = {
            name: sorted(path.name for path in (self.runtime_state_root / "im" / name).glob("*.json"))
            for name in ("conversations", "messages", "events", "message_states")
        }
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_IM_PAYLOAD")
        self.assertIn("not a reachable actor identity", response.get("error", {}).get("message", ""))
        self.assertEqual(after, before)

    def test_send_im_message_persists_durable_objects_when_wake_fails(self) -> None:
        _created, _connection, sender = self._external_connection()
        sender_ref = sender
        target = self._actor_identity()
        wake_calls: list[dict[str, object]] = []

        def wake_actor(payload: dict[str, object]) -> dict[str, object]:
            wake_calls.append(dict(payload))
            return {
                "wake_status": "wake_failed",
                "runtime_target": "none",
                "error": "socket unavailable",
            }

        response = message_service.send_im_message(
            sender_identity=sender,
            to=target,
            target_role_id=str(target["role_id"]),
            content="  ping  ",
            reply_to=None,
            wake_actor=wake_actor,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "accepted")
        self.assertEqual(response.get("wake_status"), "wake_failed")
        message_ref = response.get("message")
        self.assertIsInstance(message_ref, dict, msg=response)
        assert isinstance(message_ref, dict)
        message_id = message_ref["id"]
        conversation_id = message_ref["conversation_id"]
        self.assertEqual(message_ref.get("reply_to"), None)

        message_path = self.runtime_state_root / "im" / "messages" / f"{message_id}.json"
        self.assertTrue(message_path.is_file())
        message = json.loads(message_path.read_text(encoding="utf-8"))
        self.assertEqual(message["id"], message_id)
        self.assertEqual(message["conversation_id"], conversation_id)
        self.assertEqual(message["sender_identity"], sender_ref)
        self.assertEqual(message["target_identity"], target["identity"])
        self.assertNotIn("from_identity_id", message)
        self.assertNotIn("to_identity_id", message)
        self.assertNotIn("from", message)
        self.assertNotIn("to", message)
        self.assertEqual(message["content"], "ping")
        self.assertIsNone(message["reply_to"])

        conversation_path = self.runtime_state_root / "im" / "conversations" / f"{conversation_id}.json"
        self.assertTrue(conversation_path.is_file())
        conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
        self.assertEqual(conversation["type"], "direct")
        self.assertEqual(conversation["last_message_id"], message_id)
        self.assertEqual(conversation["identity_ids"], [sender_ref["id"], target["identity_id"]])
        self.assertNotIn("participants", conversation)

        states = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "message_states").glob("*.json"))
        ]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["message_id"], message_id)
        self.assertEqual(states[0]["owner_identity_id"], target["identity_id"])
        self.assertNotIn("participant", states[0])
        self.assertEqual(states[0]["disposition"], "unseen")

        events = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "events").glob("*.json"))
        ]
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {event["visible_to_identity_id"] for event in events},
            {sender_ref["id"], target["identity_id"]},
        )
        self.assertTrue(all("participant" not in event for event in events))
        self.assertTrue(all(event["sender_identity"] == sender_ref for event in events))
        self.assertTrue(all(event["target_identity"] == target["identity"] for event in events))
        self.assertTrue(all("from_identity_id" not in event for event in events))
        self.assertTrue(all("to_identity_id" not in event for event in events))
        self.assertTrue(all("from" not in event for event in events))
        self.assertTrue(all("to" not in event for event in events))
        self.assertTrue(all(event["message_id"] == message_id for event in events))
        self.assertTrue(all(event["conversation_id"] == conversation_id for event in events))

        self.assertEqual(len(wake_calls), 1)
        self.assertEqual(wake_calls[0]["type"], "im.message.created")
        self.assertEqual(wake_calls[0]["message_id"], message_id)
        self.assertEqual(wake_calls[0]["conversation_id"], conversation_id)
        self.assertEqual(wake_calls[0]["target_identity_id"], target["identity_id"])
        self.assertEqual(wake_calls[0]["target_role_id"], target["role_id"])
        self.assertNotIn("content", wake_calls[0])

    def test_external_connection_reads_actor_reply_once_without_client_cursor(self) -> None:
        _created, connection, sender = self._external_connection()
        sender_ref = sender
        actor = self._actor_identity()
        initial_cursor = connection["last_event_id"]
        send_response = message_service.send_external_connection_message(
            connection=connection,
            to=actor,
            content="ping",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        self.assertEqual(connection["last_event_id"], initial_cursor)
        actor_reply = message_service.send_im_message(
            sender_identity=actor,
            to=sender_ref,
            content="pong",
            reply_to=send_response["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )
        first_read = message_service.read_external_connection_events(
            connection=connection,
            wait_ms=0,
        )
        second_read = message_service.read_external_connection_events(
            connection=connection,
            wait_ms=0,
        )
        ack = message_service.ack_external_connection_event(
            connection=connection,
            event_id=actor_reply["event_id"],
        )
        third_read = message_service.read_external_connection_events(
            connection=connection,
            wait_ms=0,
        )

        self.assertTrue(first_read.get("ok"), msg=first_read)
        self.assertNotIn("next_cursor", first_read)
        self.assertNotIn("participant", first_read)
        self.assertEqual(len(first_read["events"]), 1)
        event = first_read["events"][0]
        self.assertEqual(event["event_id"], actor_reply["event_id"])
        self.assertEqual(event["message_id"], actor_reply["message"]["id"])
        self.assertEqual(event["visible_to_identity_id"], sender_ref["id"])
        self.assertEqual(event["sender_identity"], actor["identity"])
        self.assertEqual(event["target_identity"], sender_ref)
        self.assertNotIn("from_identity_id", event)
        self.assertNotIn("to_identity_id", event)
        self.assertNotIn("participant", event)
        self.assertEqual(event["type"], "message.created")
        self.assertEqual(event["reply_to"], send_response["message"]["id"])
        self.assertEqual([row["event_id"] for row in second_read["events"]], [actor_reply["event_id"]])
        self.assertTrue(ack.get("ok"), msg=ack)
        self.assertEqual(connection["last_event_id"], actor_reply["event_id"])
        self.assertEqual(third_read["events"], [])

    def test_external_connection_ack_rejects_non_visible_event_without_advancing_cursor(self) -> None:
        _created_a, connection_a, _sender_a = self._external_connection(display_name="sender a")
        _created_b, _connection_b, sender_b = self._external_connection(display_name="sender b")
        actor = self._actor_identity()
        before = connection_a["last_event_id"]
        actor_reply = message_service.send_im_message(
            sender_identity=actor,
            to=sender_b,
            content="private pong",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )

        ack = message_service.ack_external_connection_event(
            connection=connection_a,
            event_id=actor_reply["event_id"],
        )

        self.assertFalse(ack.get("ok"), msg=ack)
        self.assertEqual(ack["error"]["code"], "E_IM_SCOPE")
        self.assertEqual(connection_a["last_event_id"], before)

    def test_external_connection_ack_rejects_out_of_order_consumable_event(self) -> None:
        _created, connection, sender = self._external_connection()
        sender_ref = sender
        actor = self._actor_identity()
        root = message_service.send_external_connection_message(
            connection=connection,
            to=actor,
            content="ping",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        before = connection["last_event_id"]
        first_reply = message_service.send_im_message(
            sender_identity=actor,
            to=sender_ref,
            content="pong one",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )
        second_reply = message_service.send_im_message(
            sender_identity=actor,
            to=sender_ref,
            content="pong two",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )

        read = message_service.read_external_connection_events(connection=connection, wait_ms=0)
        ack = message_service.ack_external_connection_event(
            connection=connection,
            event_id=second_reply["event_id"],
        )

        self.assertEqual(
            [row["event_id"] for row in read["events"]],
            [first_reply["event_id"], second_reply["event_id"]],
        )
        self.assertFalse(ack.get("ok"), msg=ack)
        self.assertEqual(ack["error"]["code"], "E_IM_CURSOR")
        self.assertEqual(connection["last_event_id"], before)

    def test_external_connection_events_waits_for_new_visible_events_until_timeout(self) -> None:
        _created, connection, sender = self._external_connection(display_name="long poll smoke")
        sender_ref = sender
        target = self._actor_identity()
        root = message_service.send_external_connection_message(
            connection=connection,
            to=target,
            content="ping before wait",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        created: list[dict[str, object]] = []

        def create_message_later() -> None:
            time.sleep(0.05)
            created.append(
                message_service.send_im_message(
                    sender_identity=target,
                    to=sender_ref,
                    content="pong after wait",
                    reply_to=root["message"]["id"],
                    wake_actor=lambda _payload: {"wake_status": "not_applicable"},
                )
            )

        thread = threading.Thread(target=create_message_later)
        thread.start()
        self.addCleanup(thread.join, 1)

        started_at = time.monotonic()
        events = message_service.read_external_connection_events(
            connection=connection,
            wait_ms=500,
        )
        elapsed = time.monotonic() - started_at
        thread.join(timeout=1)

        self.assertTrue(events.get("ok"), msg=events)
        self.assertEqual(len(created), 1)
        self.assertLess(elapsed, 0.45)
        self.assertEqual([event["message_id"] for event in events["events"]], [created[0]["message"]["id"]])
        self.assertNotIn("next_cursor", events)

    def test_reply_uses_original_direct_conversation(self) -> None:
        _created, _connection, external = self._external_connection()
        external_ref = external
        actor = self._actor_identity()
        root = message_service.send_im_message(
            sender_identity=external,
            to=actor,
            target_role_id=str(actor["role_id"]),
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )

        reply = message_service.send_im_message(
            sender_identity=actor,
            to=external_ref,
            content="pong",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
        self.assertEqual(reply["message"]["conversation_id"], root["message"]["conversation_id"])
        conversation_files = sorted((self.runtime_state_root / "im" / "conversations").glob("*.json"))
        self.assertEqual(len(conversation_files), 1)
        states = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "message_states").glob("*.json"))
        ]
        reply_states = [row for row in states if row["message_id"] == reply["message"]["id"]]
        self.assertEqual(len(reply_states), 1)
        self.assertEqual(reply_states[0]["owner_identity_id"], external_ref["id"])
        self.assertNotIn("participant", reply_states[0])
        self.assertEqual(reply_states[0]["disposition"], "unseen")

    def test_message_replies_and_disposition_are_participant_scoped(self) -> None:
        _created, _connection, external = self._external_connection()
        external_ref = external
        actor = self._actor_identity()
        root = message_service.send_im_message(
            sender_identity=external,
            to=actor,
            target_role_id=str(actor["role_id"]),
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        reply = message_service.send_im_message(
            sender_identity=actor,
            to=external_ref,
            content="pong",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )
        _other_created, _other_connection, outsider = self._external_connection(display_name="other smoke")

        read_reply = message_service.get_im_message(
            identity=external_ref,
            message_id=reply["message"]["id"],
        )
        outsider_read = message_service.get_im_message(
            identity=outsider["id"],
            message_id=reply["message"]["id"],
        )
        replies = message_service.list_im_replies(
            identity=external_ref,
            message_id=root["message"]["id"],
        )
        mark = message_service.update_im_disposition(
            identity=external_ref,
            message_id=reply["message"]["id"],
            disposition="absorbed",
            reason="reply consumed by local script",
        )

        self.assertTrue(read_reply.get("ok"), msg=read_reply)
        self.assertEqual(read_reply["message"]["content"], "pong")
        self.assertEqual(read_reply["message"]["reply_to"], root["message"]["id"])
        self.assertFalse(outsider_read.get("ok"), msg=outsider_read)
        self.assertEqual(outsider_read["error"]["code"], "E_IM_SCOPE")
        self.assertTrue(replies.get("ok"), msg=replies)
        self.assertEqual([row["id"] for row in replies["replies"]], [reply["message"]["id"]])
        self.assertTrue(mark.get("ok"), msg=mark)
        self.assertIs(mark["state_changed"], True)
        self.assertEqual(mark["disposition"], "absorbed")
        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{reply['message']['id']}--{external['id']}.json"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["disposition"], "absorbed")
        self.assertEqual(state["reason"], "reply consumed by local script")
        self.assertEqual(state["owner_identity_id"], external["id"])

    def test_direct_conversation_read_returns_visible_messages_in_order(self) -> None:
        _created, _connection, external = self._external_connection()
        external_ref = external
        actor = self._actor_identity()
        root = message_service.send_im_message(
            sender_identity=external,
            to=actor,
            target_role_id=str(actor["role_id"]),
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        reply = message_service.send_im_message(
            sender_identity=actor,
            to=external_ref,
            content="pong",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )

        conversation = message_service.get_im_direct_conversation(
            identity=external_ref,
            target=actor,
            limit=20,
        )

        self.assertTrue(conversation.get("ok"), msg=conversation)
        self.assertEqual(conversation["conversation"]["id"], root["message"]["conversation_id"])
        self.assertEqual([row["id"] for row in conversation["messages"]], [root["message"]["id"], reply["message"]["id"]])


if __name__ == "__main__":
    unittest.main()
