#!/usr/bin/env python3
"""Central IM product-core tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.services import messages as message_service  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class ImProductCoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _actor_participant(self, *, role: str = "market", label: str = "target") -> dict[str, object]:
        actor_address = ActorAddress(
            role_id=role,
            actor_id=self._runtime_actor_id(role=role, label=label),
        ).to_payload()
        return {"kind": "actor", "actor_address": actor_address}

    def test_register_external_participant_writes_session_without_plaintext_token(self) -> None:
        response = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )

        self.assertTrue(response.get("ok"), msg=response)
        participant = response.get("participant")
        self.assertIsInstance(participant, dict, msg=response)
        assert isinstance(participant, dict)
        self.assertEqual(participant.get("kind"), "external")
        external_id = participant.get("external_id")
        self.assertIsInstance(external_id, str, msg=response)
        assert isinstance(external_id, str)
        self.assertTrue(external_id.startswith("ext-"), msg=response)
        token = response.get("participant_token")
        self.assertIsInstance(token, str, msg=response)
        assert isinstance(token, str)
        self.assertTrue(token.startswith("impt-"), msg=response)
        self.assertEqual(response.get("event_cursor"), "imev-000000000000")

        participant_path = self.runtime_state_root / "im" / "participants" / f"{external_id}.json"
        self.assertTrue(participant_path.is_file())
        participant_row = json.loads(participant_path.read_text(encoding="utf-8"))
        self.assertEqual(participant_row["external_id"], external_id)
        self.assertEqual(participant_row["display_name"], "local smoke")

        session_files = sorted((self.runtime_state_root / "im" / "sessions").glob("*.json"))
        self.assertEqual(len(session_files), 1)
        session_text = session_files[0].read_text(encoding="utf-8")
        self.assertNotIn(token, session_text)
        session_row = json.loads(session_text)
        self.assertEqual(session_row["participant"], {"kind": "external", "external_id": external_id})
        self.assertTrue(str(session_row["token_hash"]).startswith("sha256:"))

        cursor_path = self.runtime_state_root / "im" / "cursors" / f"external--{external_id}.json"
        self.assertTrue(cursor_path.is_file())
        cursor_row = json.loads(cursor_path.read_text(encoding="utf-8"))
        self.assertEqual(cursor_row["last_event_id"], "imev-000000000000")

    def test_send_im_message_persists_durable_objects_when_wake_fails(self) -> None:
        registration = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )
        sender = registration["participant"]
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
        self.assertEqual(response.get("next_cursor"), response.get("event_id"))

        message_path = self.runtime_state_root / "im" / "messages" / f"{message_id}.json"
        self.assertTrue(message_path.is_file())
        message = json.loads(message_path.read_text(encoding="utf-8"))
        self.assertEqual(message["id"], message_id)
        self.assertEqual(message["conversation_id"], conversation_id)
        self.assertEqual(message["from"], sender_ref)
        self.assertEqual(message["to"], [target])
        self.assertEqual(message["content"], "ping")
        self.assertIsNone(message["reply_to"])

        conversation_path = self.runtime_state_root / "im" / "conversations" / f"{conversation_id}.json"
        self.assertTrue(conversation_path.is_file())
        conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
        self.assertEqual(conversation["type"], "direct")
        self.assertEqual(conversation["last_message_id"], message_id)
        self.assertEqual(conversation["participants"], [sender_ref, target])

        states = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "message_states").glob("*.json"))
        ]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["message_id"], message_id)
        self.assertEqual(states[0]["participant"], target)
        self.assertEqual(states[0]["disposition"], "unseen")

        events = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.runtime_state_root / "im" / "events").glob("*.json"))
        ]
        self.assertEqual(len(events), 2)
        self.assertEqual({event["participant"]["kind"] for event in events}, {"actor", "external"})
        self.assertTrue(all(event["message_id"] == message_id for event in events))
        self.assertTrue(all(event["conversation_id"] == conversation_id for event in events))

        self.assertEqual(len(wake_calls), 1)
        self.assertEqual(wake_calls[0]["type"], "im.message.created")
        self.assertEqual(wake_calls[0]["message_id"], message_id)
        self.assertEqual(wake_calls[0]["conversation_id"], conversation_id)
        self.assertEqual(wake_calls[0]["target_actor_address"], target["actor_address"])
        self.assertNotIn("content", wake_calls[0])

    def test_read_im_events_is_participant_scoped_and_cursor_stable(self) -> None:
        registration = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )
        sender = registration["participant"]
        sender_ref = {"kind": "external", "external_id": sender["external_id"]}
        send_response = message_service.send_im_message(
            sender_participant=sender,
            to=self._actor_participant(),
            content="ping",
            reply_to=None,
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        start_cursor = registration["event_cursor"]

        first_read = message_service.read_im_events(
            participant=sender_ref,
            cursor=start_cursor,
            limit=50,
            wait_ms=0,
        )
        second_read = message_service.read_im_events(
            participant=sender_ref,
            cursor=start_cursor,
            limit=50,
            wait_ms=0,
        )
        after_cursor_read = message_service.read_im_events(
            participant=sender_ref,
            cursor=send_response["event_id"],
            limit=50,
            wait_ms=0,
        )

        self.assertTrue(first_read.get("ok"), msg=first_read)
        self.assertEqual(first_read, second_read)
        self.assertEqual(first_read["next_cursor"], send_response["event_id"])
        self.assertEqual(len(first_read["events"]), 1)
        event = first_read["events"][0]
        self.assertEqual(event["event_id"], send_response["event_id"])
        self.assertEqual(event["participant"], sender_ref)
        self.assertEqual(event["type"], "message.created")
        self.assertEqual(event["reply_to"], None)
        self.assertEqual(after_cursor_read["events"], [])
        self.assertEqual(after_cursor_read["next_cursor"], send_response["event_id"])

    def test_reply_uses_original_direct_conversation(self) -> None:
        registration = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )
        external = registration["participant"]
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
        self.assertEqual(reply_states[0]["participant"], external_ref)
        self.assertEqual(reply_states[0]["disposition"], "unseen")

    def test_message_replies_and_disposition_are_participant_scoped(self) -> None:
        registration = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )
        external = registration["participant"]
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
        outsider = message_service.register_external_participant(
            client_kind="script",
            display_name="other smoke",
        )["participant"]

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
            / f"{reply['message']['id']}--external--{external['external_id']}.json"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["disposition"], "absorbed")
        self.assertEqual(state["reason"], "reply consumed by local script")

    def test_direct_conversation_read_returns_visible_messages_in_order(self) -> None:
        registration = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )
        external = registration["participant"]
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
