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
from env.repos import identities as identity_repo  # noqa: E402
from env.repos import messages as message_repo  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class ImProductCoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_central_im_repo_does_not_export_legacy_actor_address_message_apis(self) -> None:
        for name in ("create_message", "save_message", "list_messages", "get_message", "delete_message"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(message_repo, name))

    def _actor_identity(self, *, role: str = "market", label: str = "target") -> dict[str, object]:
        identity_id = self._runtime_actor_id(role=role, label=label)
        identity_repo.save_actor_identity_profile(
            {"identity": {"id": identity_id, "type": "actor"}, "role_id": role}
        )
        return {"identity": {"id": identity_id, "type": "actor"}, "identity_id": identity_id, "role_id": role}

    def _external_session(
        self,
        *,
        display_name: str = "local smoke",
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        created = message_service.create_external_session(display_name=display_name)
        self.assertTrue(created.get("ok"), msg=created)
        external_session_key = created.get("external_session_key")
        self.assertIsInstance(external_session_key, str, msg=created)
        assert isinstance(external_session_key, str)
        auth = message_service.authenticate_external_session_key(external_session_key)
        self.assertTrue(auth.get("ok"), msg=auth)
        external_session = auth.get("external_session")
        identity = auth.get("identity")
        self.assertIsInstance(external_session, dict, msg=auth)
        self.assertIsInstance(identity, dict, msg=auth)
        assert isinstance(external_session, dict)
        assert isinstance(identity, dict)
        return created, external_session, identity

    def test_create_external_session_returns_only_session_key_and_persists_internal_state(self) -> None:
        response = message_service.create_external_session(display_name="local smoke")

        self.assertTrue(response.get("ok"), msg=response)
        external_session_key = response.get("external_session_key")
        self.assertIsInstance(external_session_key, str, msg=response)
        assert isinstance(external_session_key, str)
        self.assertTrue(external_session_key.startswith("imsk-"), msg=response)
        self.assertNotIn("connection_key", response)
        self.assertNotIn("external_connection", response)
        self.assertNotIn("connection", response)

        auth = message_service.authenticate_external_session_key(external_session_key)
        self.assertTrue(auth.get("ok"), msg=auth)
        identity = auth.get("identity")
        external_session = auth.get("external_session")
        self.assertIsInstance(identity, dict, msg=auth)
        self.assertIsInstance(external_session, dict, msg=auth)
        assert isinstance(identity, dict)
        assert isinstance(external_session, dict)
        self.assertEqual(identity.get("type"), "external")
        external_id = identity.get("id")
        self.assertIsInstance(external_id, str, msg=auth)
        assert isinstance(external_id, str)

        profile_path = self.runtime_state_root / "buddyswitch" / "objects" / "identities" / "externals" / f"{external_id}.json"
        self.assertTrue(profile_path.is_file())
        profile_row = json.loads(profile_path.read_text(encoding="utf-8"))
        self.assertEqual(profile_row["identity"], {"id": external_id, "type": "external"})
        self.assertEqual(profile_row["display_name"], "local smoke")

        session_files = sorted((self.runtime_state_root / "im" / "external_sessions").glob("*.json"))
        self.assertEqual(len(session_files), 1)
        session_text = session_files[0].read_text(encoding="utf-8")
        self.assertNotIn(external_session_key, session_text)
        session_row = json.loads(session_text)
        self.assertEqual(session_row["identity_id"], external_id)
        self.assertEqual(session_row["display_name"], "local smoke")
        self.assertEqual(session_row["last_event_id"], "imev-000000000000")
        self.assertTrue(str(session_row["external_session_key_hash"]).startswith("sha256:"))
        self.assertNotIn("connection_key_hash", session_row)
        self.assertNotIn("connection", session_row)
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

    def test_resolve_im_send_target_accepts_external_identity_without_actor_reachability(self) -> None:
        actor = self._actor_identity(role="dev", label="act-dev-resolve-external")
        _created, _external_session, external = self._external_session()
        calls: list[dict[str, object]] = []

        def check_actor_reachability(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            self.fail("external target resolution must not query actor reachability")

        response = message_service.resolve_im_send_target(
            sender_identity=actor["identity"],
            target_identity_id=external["id"],
            actor_reachability_checker=check_actor_reachability,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["target_identity"], external)
        self.assertEqual(calls, [])

    def test_resolve_im_send_target_accepts_existing_online_actor_identity(self) -> None:
        sender = self._actor_identity(role="dev", label="act-dev-resolve-actor-source")
        target = self._actor_identity(role="market", label="act-market-resolve-actor-target")
        target_id = str(target["identity_id"])
        calls: list[dict[str, object]] = []

        def check_actor_reachability(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return {
                "reachability_status": "online",
                "target_identity_id": target_id,
                "record": {"identity_id": target_id},
            }

        response = message_service.resolve_im_send_target(
            sender_identity=sender["identity"],
            target_identity_id=target_id,
            actor_reachability_checker=check_actor_reachability,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["target_identity"], {"id": target_id, "type": "actor"})
        self.assertEqual(calls, [{"target_identity_id": target_id}])

    def test_resolve_im_send_target_rejects_offline_actor_without_writing_im_state(self) -> None:
        sender = self._actor_identity(role="dev", label="act-dev-resolve-offline-source")
        target = self._actor_identity(role="market", label="act-market-resolve-offline-target")
        target_id = str(target["identity_id"])
        before = {
            name: sorted(path.name for path in (self.runtime_state_root / "im" / name).glob("*.json"))
            for name in ("conversations", "messages", "events", "message_states")
        }

        response = message_service.resolve_im_send_target(
            sender_identity=sender["identity"],
            target_identity_id=target_id,
            actor_reachability_checker=lambda **_kwargs: {
                "reachability_status": "registered_offline",
                "target_identity_id": target_id,
                "record": {"identity_id": target_id},
            },
        )

        after = {
            name: sorted(path.name for path in (self.runtime_state_root / "im" / name).glob("*.json"))
            for name in ("conversations", "messages", "events", "message_states")
        }
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_IM_TARGET")
        self.assertIn("not online", response.get("error", {}).get("message", ""))
        self.assertEqual(after, before)

    def test_im_repository_rejects_unknown_row_fields_without_writing_files(self) -> None:
        sender = {"id": "act-pm-repo", "type": "actor"}
        target = {"id": "act-dev-repo", "type": "actor"}

        def snapshot() -> list[str]:
            im_root = self.runtime_state_root / "im"
            if not im_root.exists():
                return []
            return sorted(str(path.relative_to(im_root)) for path in im_root.rglob("*.json"))

        cases = [
            (
                "conversation",
                lambda: message_repo.save_im_conversation(
                    {
                        "id": "conv-unknown",
                        "type": "direct",
                        "identity_ids": [sender["id"], target["id"]],
                        "created_at": "2026-07-07T00:00:00Z",
                        "updated_at": "2026-07-07T00:00:00Z",
                        "last_message_id": "msg-unknown",
                        "last_sequence": 1,
                        "debug_payload": {"unexpected": True},
                    }
                ),
            ),
            (
                "message",
                lambda: message_repo.save_im_message(
                    {
                        "id": "msg-unknown",
                        "conversation_id": "conv-unknown",
                        "sender_identity": sender,
                        "target_identity": target,
                        "content": "unknown",
                        "reply_to": None,
                        "created_at": "2026-07-07T00:00:00Z",
                        "sequence": 1,
                        "debug_payload": {"unexpected": True},
                    }
                ),
            ),
            (
                "state",
                lambda: message_repo.save_im_message_state(
                    {
                        "message_id": "msg-unknown-state",
                        "owner_identity_id": target["id"],
                        "disposition": "unseen",
                        "reason": None,
                        "processed_by": None,
                        "updated_at": "2026-07-07T00:00:00Z",
                        "debug_payload": {"unexpected": True},
                    }
                ),
            ),
            (
                "event",
                lambda: message_repo.save_im_event(
                    {
                        "event_id": "imev-unknown",
                        "type": "message.created",
                        "message_id": "msg-unknown",
                        "conversation_id": "conv-unknown",
                        "sender_identity": sender,
                        "target_identity": target,
                        "visible_to_identity_id": target["id"],
                        "reply_to": None,
                        "created_at": "2026-07-07T00:00:00Z",
                        "sequence": 1,
                        "debug_payload": {"unexpected": True},
                    }
                ),
            ),
        ]

        for name, call in cases:
            with self.subTest(name=name):
                before = snapshot()
                with self.assertRaisesRegex(ValueError, "unknown IM field"):
                    call()
                self.assertEqual(snapshot(), before)

    def test_send_im_message_persists_durable_objects_without_actor_handling_contract(self) -> None:
        _created, _external_session, sender = self._external_session()
        sender_ref = sender
        target = self._actor_identity()

        response = message_service.send_im_message(
            sender_identity=sender,
            target_identity=target["identity"],
            content="  ping  ",
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "accepted")
        self.assertNotIn("wake_" + "status", response)
        self.assertNotIn("target_" + "role_id", response)
        self.assertNotIn("wake_" + "actor", response)
        message_ref = response.get("message")
        self.assertIsInstance(message_ref, dict, msg=response)
        assert isinstance(message_ref, dict)
        message_id = message_ref["id"]
        conversation_id = message_ref["conversation_id"]
        self.assertEqual(message_ref.get("reply_to"), None)
        self.assertIsInstance(response.get("event_id"), str)

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

    def test_send_im_reply_normalizes_original_sender_to_target_identity_and_marks_replied(self) -> None:
        _created, _external_session, external = self._external_session()
        actor = self._actor_identity(role="dev", label="act-dev-reply-wrapper")
        root = message_service.send_im_message(
            sender_identity=external,
            target_identity=actor["identity"],
            content="ping",
        )

        reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            reply_to=root["message"]["id"],
            content="pong",
            actor_reachability_checker=lambda *, target_identity_id: {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            },
        )

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["target_identity"], external)
        self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
        self.assertEqual(reply["message"]["conversation_id"], root["message"]["conversation_id"])
        self.assertEqual(reply["original_message_id"], root["message"]["id"])
        self.assertEqual(reply["original_final_disposition"], "replied")
        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{root['message']['id']}--{actor['identity_id']}.json"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["disposition"], "replied")

    def test_send_im_reply_rejects_non_processable_source_message_without_write(self) -> None:
        _created, _external_session, external = self._external_session()
        actor = self._actor_identity(role="dev", label="act-dev-reply-processed")
        root = message_service.send_im_message(
            sender_identity=external,
            target_identity=actor["identity"],
            content="ping",
        )

        before_messages = sorted(path.name for path in (self.runtime_state_root / "im" / "messages").glob("*.json"))
        before_events = sorted(path.name for path in (self.runtime_state_root / "im" / "events").glob("*.json"))

        for disposition in ("absorbed", "replied"):
            with self.subTest(disposition=disposition):
                mark = message_service.update_im_disposition(
                    identity=actor["identity"],
                    message_id=root["message"]["id"],
                    disposition=disposition,
                    reason=f"already {disposition}",
                )
                self.assertTrue(mark.get("ok"), msg=mark)

                reply = message_service.send_im_reply(
                    sender_identity=actor["identity"],
                    reply_to=root["message"]["id"],
                    content="pong",
                    actor_reachability_checker=lambda *, target_identity_id: {
                        "reachability_status": "online",
                        "target_identity_id": target_identity_id,
                        "record": {"identity_id": target_identity_id},
                    },
                )

                self.assertFalse(reply.get("ok"), msg=reply)
                self.assertEqual(reply["error"]["code"], "E_IM_REPLY_TARGET")
                self.assertIn("processable inbound message", reply["error"]["message"])
                self.assertEqual(
                    sorted(path.name for path in (self.runtime_state_root / "im" / "messages").glob("*.json")),
                    before_messages,
                )
                self.assertEqual(
                    sorted(path.name for path in (self.runtime_state_root / "im" / "events").glob("*.json")),
                    before_events,
                )

    def test_send_im_reply_rejects_message_not_addressed_to_sender(self) -> None:
        sender = self._actor_identity(role="pm", label="act-pm-reply-guard")
        intended = self._actor_identity(role="dev", label="act-dev-reply-guard")
        outsider = self._actor_identity(role="test", label="act-test-reply-guard")
        root = message_service.send_im_message(
            sender_identity=sender["identity"],
            target_identity=intended["identity"],
            content="private request",
        )
        before_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))

        reply = message_service.send_im_reply(
            sender_identity=outsider["identity"],
            reply_to=root["message"]["id"],
            content="bad reply",
            actor_reachability_checker=lambda *, target_identity_id: {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            },
        )

        self.assertFalse(reply.get("ok"), msg=reply)
        self.assertEqual(reply["error"]["code"], "E_IM_REPLY_TARGET")
        after_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))
        self.assertEqual(after_messages, before_messages)

    def test_send_im_reply_to_offline_actor_rejects_before_write(self) -> None:
        source = self._actor_identity(role="pm", label="act-pm-offline-reply")
        active = self._actor_identity(role="dev", label="act-dev-offline-reply")
        root = message_service.send_im_message(
            sender_identity=source["identity"],
            target_identity=active["identity"],
            content="need reply",
        )
        before_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))

        reply = message_service.send_im_reply(
            sender_identity=active["identity"],
            reply_to=root["message"]["id"],
            content="reply",
            actor_reachability_checker=lambda *, target_identity_id: {
                "reachability_status": "offline",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            },
        )

        self.assertFalse(reply.get("ok"), msg=reply)
        self.assertEqual(reply["error"]["code"], "E_IM_TARGET")
        after_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))
        self.assertEqual(after_messages, before_messages)

    def test_send_im_message_returns_final_target_identity_for_explicit_and_reply_to_targets(self) -> None:
        _created, external_session, external = self._external_session(display_name="target identity response")
        actor = self._actor_identity(role="market", label="act-market-target-response")
        pm = self._actor_identity(role="pm", label="act-pm-target-response")
        dev = self._actor_identity(role="dev", label="act-dev-target-response")

        external_root = message_service.send_external_session_message(
            external_session=external_session,
            target_identity=actor["identity"],
            content="ping",
        )
        actor_external_reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong",
            reply_to=external_root["message"]["id"],
        )
        actor_root = message_service.send_im_message(
            sender_identity=pm["identity"],
            target_identity=dev["identity"],
            content="handoff",
        )
        actor_reply = message_service.send_im_reply(
            sender_identity=dev["identity"],
            content="received",
            reply_to=actor_root["message"]["id"],
            actor_reachability_checker=lambda *, target_identity_id: {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            },
        )

        self.assertTrue(external_root.get("ok"), msg=external_root)
        self.assertTrue(actor_external_reply.get("ok"), msg=actor_external_reply)
        self.assertTrue(actor_root.get("ok"), msg=actor_root)
        self.assertTrue(actor_reply.get("ok"), msg=actor_reply)
        self.assertEqual(external_root["target_identity"], actor["identity"])
        self.assertEqual(actor_external_reply["target_identity"], external)
        self.assertEqual(actor_root["target_identity"], dev["identity"])
        self.assertEqual(actor_reply["target_identity"], pm["identity"])

    def test_external_session_reads_actor_reply_once_without_client_cursor(self) -> None:
        _created, external_session, sender = self._external_session()
        sender_ref = sender
        actor = self._actor_identity()
        initial_cursor = external_session["last_event_id"]
        send_response = message_service.send_external_session_message(
            external_session=external_session,
            target_identity=actor["identity"],
            content="ping",
        )
        self.assertEqual(external_session["last_event_id"], initial_cursor)
        actor_reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong",
            reply_to=send_response["message"]["id"],
        )
        first_read = message_service.read_external_session_events(
            external_session=external_session,
            wait_ms=0,
        )
        second_read = message_service.read_external_session_events(
            external_session=external_session,
            wait_ms=0,
        )
        ack = message_service.ack_external_session_event(
            external_session=external_session,
            event_id=actor_reply["event_id"],
        )
        third_read = message_service.read_external_session_events(
            external_session=external_session,
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
        self.assertEqual(external_session["last_event_id"], actor_reply["event_id"])
        self.assertEqual(third_read["events"], [])

    def test_external_session_send_requires_canonical_target_identity_only(self) -> None:
        _created, external_session, _sender = self._external_session()
        actor = self._actor_identity()

        response = message_service.send_external_session_message(
            external_session=external_session,
            target_identity=actor["identity"],
            content="ping",
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("delivery_status"), "accepted")
        self.assertNotIn("wake_" + "status", response)
        self.assertNotIn("target_" + "role_id", response)
        with self.assertRaises(TypeError):
            message_service.send_external_session_message(
                external_session=external_session,
                to=actor,
                content="old shape",
            )

    def test_external_session_ack_rejects_non_visible_event_without_advancing_cursor(self) -> None:
        _created_a, external_session_a, _sender_a = self._external_session(display_name="sender a")
        _created_b, _external_session_b, sender_b = self._external_session(display_name="sender b")
        actor = self._actor_identity()
        before = external_session_a["last_event_id"]
        actor_reply = message_service.send_im_message(
            sender_identity=actor["identity"],
            target_identity=sender_b,
            content="private pong",
        )

        ack = message_service.ack_external_session_event(
            external_session=external_session_a,
            event_id=actor_reply["event_id"],
        )

        self.assertFalse(ack.get("ok"), msg=ack)
        self.assertEqual(ack["error"]["code"], "E_IM_SCOPE")
        self.assertEqual(external_session_a["last_event_id"], before)

    def test_external_session_ack_rejects_out_of_order_consumable_event(self) -> None:
        _created, external_session, sender = self._external_session()
        sender_ref = sender
        actor = self._actor_identity()
        first_root = message_service.send_external_session_message(
            external_session=external_session,
            target_identity=actor["identity"],
            content="ping",
        )
        second_root = message_service.send_external_session_message(
            external_session=external_session,
            target_identity=actor["identity"],
            content="ping again",
        )
        before = external_session["last_event_id"]
        first_reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong one",
            reply_to=first_root["message"]["id"],
        )
        second_reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong two",
            reply_to=second_root["message"]["id"],
        )

        read = message_service.read_external_session_events(external_session=external_session, wait_ms=0)
        ack = message_service.ack_external_session_event(
            external_session=external_session,
            event_id=second_reply["event_id"],
        )

        self.assertEqual(
            [row["event_id"] for row in read["events"]],
            [first_reply["event_id"], second_reply["event_id"]],
        )
        self.assertFalse(ack.get("ok"), msg=ack)
        self.assertEqual(ack["error"]["code"], "E_IM_CURSOR")
        self.assertEqual(external_session["last_event_id"], before)

    def test_external_session_events_waits_for_new_visible_events_until_timeout(self) -> None:
        _created, external_session, sender = self._external_session(display_name="long poll smoke")
        sender_ref = sender
        target = self._actor_identity()
        root = message_service.send_external_session_message(
            external_session=external_session,
            target_identity=target["identity"],
            content="ping before wait",
        )
        created: list[dict[str, object]] = []

        def create_message_later() -> None:
            time.sleep(0.05)
            created.append(
                message_service.send_im_reply(
                    sender_identity=target["identity"],
                    content="pong after wait",
                    reply_to=root["message"]["id"],
                )
            )

        thread = threading.Thread(target=create_message_later)
        thread.start()
        self.addCleanup(thread.join, 1)

        started_at = time.monotonic()
        events = message_service.read_external_session_events(
            external_session=external_session,
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
        _created, _external_session, external = self._external_session()
        external_ref = external
        actor = self._actor_identity()
        root = message_service.send_im_message(
            sender_identity=external,
            target_identity=actor["identity"],
            content="ping",
        )

        reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong",
            reply_to=root["message"]["id"],
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
        _created, _external_session, external = self._external_session()
        external_ref = external
        actor = self._actor_identity()
        root = message_service.send_im_message(
            sender_identity=external,
            target_identity=actor["identity"],
            content="ping",
        )
        reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong",
            reply_to=root["message"]["id"],
        )
        _other_created, _other_external_session, outsider = self._external_session(display_name="other smoke")

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
        _created, _external_session, external = self._external_session()
        external_ref = external
        actor = self._actor_identity()
        root = message_service.send_im_message(
            sender_identity=external,
            target_identity=actor["identity"],
            content="ping",
        )
        reply = message_service.send_im_reply(
            sender_identity=actor["identity"],
            content="pong",
            reply_to=root["message"]["id"],
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
