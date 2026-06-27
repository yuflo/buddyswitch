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
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class ImProductCoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_central_im_repo_does_not_export_legacy_actor_address_message_apis(self) -> None:
        for name in ("create_message", "save_message", "list_messages", "get_message", "delete_message"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(message_repo, name))

    def _actor_participant(self, *, role: str = "market", label: str = "target") -> dict[str, object]:
        actor_address = ActorAddress(
            role_id=role,
            actor_id=self._runtime_actor_id(role=role, label=label),
        ).to_payload()
        return {"kind": "actor", "actor_address": actor_address}

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
        participant = auth.get("participant")
        self.assertIsInstance(connection, dict, msg=auth)
        self.assertIsInstance(participant, dict, msg=auth)
        assert isinstance(connection, dict)
        assert isinstance(participant, dict)
        return created, connection, participant

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
        participant = auth.get("participant")
        connection = auth.get("connection")
        self.assertIsInstance(participant, dict, msg=auth)
        self.assertIsInstance(connection, dict, msg=auth)
        assert isinstance(participant, dict)
        assert isinstance(connection, dict)
        self.assertEqual(participant.get("kind"), "external")
        external_id = participant.get("external_id")
        self.assertIsInstance(external_id, str, msg=auth)
        assert isinstance(external_id, str)

        participant_path = self.runtime_state_root / "im" / "participants" / f"{external_id}.json"
        self.assertTrue(participant_path.is_file())
        participant_row = json.loads(participant_path.read_text(encoding="utf-8"))
        self.assertEqual(participant_row["external_id"], external_id)
        self.assertEqual(participant_row["display_name"], "local smoke")
        self.assertNotIn("client_kind", participant_row)

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

    def test_send_im_message_persists_durable_objects_when_wake_fails(self) -> None:
        _created, _connection, sender = self._external_connection()
        sender_ref = {"kind": "external", "external_id": sender["external_id"]}
        target = self._actor_participant()
        wake_calls: list[dict[str, object]] = []

        def wake_actor(payload: dict[str, object]) -> dict[str, object]:
            wake_calls.append(dict(payload))
            return {
                "wake_status": "wake_failed",
                "runtime_target": "none",
                "error": "socket unavailable",
            }

        response = message_service.send_im_message(
            sender_participant=sender,
            to=target,
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
        self.assertEqual(message["from_identity_id"], sender_ref["external_id"])
        self.assertEqual(message["to_identity_id"], target["actor_address"]["actor_id"])
        self.assertNotIn("from", message)
        self.assertNotIn("to", message)
        self.assertEqual(message["content"], "ping")
        self.assertIsNone(message["reply_to"])

        conversation_path = self.runtime_state_root / "im" / "conversations" / f"{conversation_id}.json"
        self.assertTrue(conversation_path.is_file())
        conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
        self.assertEqual(conversation["type"], "direct")
        self.assertEqual(conversation["last_message_id"], message_id)
        self.assertEqual(conversation["identity_ids"], [sender_ref["external_id"], target["actor_address"]["actor_id"]])
        self.assertNotIn("participants", conversation)

        states = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "message_states").glob("*.json"))
        ]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["message_id"], message_id)
        self.assertEqual(states[0]["owner_identity_id"], target["actor_address"]["actor_id"])
        self.assertNotIn("participant", states[0])
        self.assertEqual(states[0]["disposition"], "unseen")

        events = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "events").glob("*.json"))
        ]
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {event["visible_to_identity_id"] for event in events},
            {sender_ref["external_id"], target["actor_address"]["actor_id"]},
        )
        self.assertTrue(all("participant" not in event for event in events))
        self.assertTrue(all(event["from_identity_id"] == sender_ref["external_id"] for event in events))
        self.assertTrue(all(event["to_identity_id"] == target["actor_address"]["actor_id"] for event in events))
        self.assertTrue(all("from" not in event for event in events))
        self.assertTrue(all("to" not in event for event in events))
        self.assertTrue(all(event["message_id"] == message_id for event in events))
        self.assertTrue(all(event["conversation_id"] == conversation_id for event in events))

        self.assertEqual(len(wake_calls), 1)
        self.assertEqual(wake_calls[0]["type"], "im.message.created")
        self.assertEqual(wake_calls[0]["message_id"], message_id)
        self.assertEqual(wake_calls[0]["conversation_id"], conversation_id)
        self.assertEqual(wake_calls[0]["target_actor_address"], target["actor_address"])
        self.assertNotIn("content", wake_calls[0])

    def test_external_connection_reads_actor_reply_once_without_client_cursor(self) -> None:
        _created, connection, sender = self._external_connection()
        sender_ref = {"kind": "external", "external_id": sender["external_id"]}
        actor = self._actor_participant()
        send_response = message_service.send_im_message(
            sender_participant=sender,
            to=actor,
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        connection["last_event_id"] = send_response["event_id"]
        actor_reply = message_service.send_im_message(
            sender_participant=actor,
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

        self.assertTrue(first_read.get("ok"), msg=first_read)
        self.assertNotIn("next_cursor", first_read)
        self.assertNotIn("participant", first_read)
        self.assertEqual(len(first_read["events"]), 1)
        event = first_read["events"][0]
        self.assertEqual(event["event_id"], actor_reply["event_id"])
        self.assertEqual(event["message_id"], actor_reply["message"]["id"])
        self.assertEqual(event["visible_to_identity_id"], sender_ref["external_id"])
        self.assertEqual(event["from_identity_id"], actor["actor_address"]["actor_id"])
        self.assertEqual(event["to_identity_id"], sender_ref["external_id"])
        self.assertNotIn("participant", event)
        self.assertEqual(event["type"], "message.created")
        self.assertEqual(event["reply_to"], send_response["message"]["id"])
        self.assertEqual(second_read["events"], [])

    def test_external_connection_events_waits_for_new_visible_events_until_timeout(self) -> None:
        _created, connection, sender = self._external_connection(display_name="long poll smoke")
        sender_ref = {"kind": "external", "external_id": sender["external_id"]}
        target = self._actor_participant()
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
                    sender_participant=target,
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
        external_ref = {"kind": "external", "external_id": external["external_id"]}
        actor = self._actor_participant()
        root = message_service.send_im_message(
            sender_participant=external,
            to=actor,
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )

        reply = message_service.send_im_message(
            sender_participant=actor,
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
        self.assertEqual(reply_states[0]["owner_identity_id"], external_ref["external_id"])
        self.assertNotIn("participant", reply_states[0])
        self.assertEqual(reply_states[0]["disposition"], "unseen")

    def test_message_replies_and_disposition_are_participant_scoped(self) -> None:
        _created, _connection, external = self._external_connection()
        external_ref = {"kind": "external", "external_id": external["external_id"]}
        actor = self._actor_participant()
        root = message_service.send_im_message(
            sender_participant=external,
            to=actor,
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        reply = message_service.send_im_message(
            sender_participant=actor,
            to=external_ref,
            content="pong",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )
        _other_created, _other_connection, outsider = self._external_connection(display_name="other smoke")

        read_reply = message_service.get_im_message(
            participant=external_ref,
            message_id=reply["message"]["id"],
        )
        outsider_read = message_service.get_im_message(
            participant={"kind": "external", "external_id": outsider["external_id"]},
            message_id=reply["message"]["id"],
        )
        replies = message_service.list_im_replies(
            participant=external_ref,
            message_id=root["message"]["id"],
        )
        mark = message_service.update_im_disposition(
            participant=external_ref,
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
            / f"{reply['message']['id']}--{external['external_id']}.json"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["disposition"], "absorbed")
        self.assertEqual(state["reason"], "reply consumed by local script")
        self.assertEqual(state["owner_identity_id"], external["external_id"])

    def test_direct_conversation_read_returns_visible_messages_in_order(self) -> None:
        _created, _connection, external = self._external_connection()
        external_ref = {"kind": "external", "external_id": external["external_id"]}
        actor = self._actor_participant()
        root = message_service.send_im_message(
            sender_participant=external,
            to=actor,
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        reply = message_service.send_im_message(
            sender_participant=actor,
            to=external_ref,
            content="pong",
            reply_to=root["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )

        conversation = message_service.get_im_direct_conversation(
            participant=external_ref,
            target=actor,
            limit=20,
        )

        self.assertTrue(conversation.get("ok"), msg=conversation)
        self.assertEqual(conversation["conversation"]["id"], root["message"]["conversation_id"])
        self.assertEqual([row["id"] for row in conversation["messages"]], [root["message"]["id"], reply["message"]["id"]])


if __name__ == "__main__":
    unittest.main()
