"""External IM Session application-boundary tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from env.repos import identities as identity_repo  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402
from tools.launcher import external_im_session  # noqa: E402


class ExternalImSessionTests(RuntimeWorkspaceTestCase):
    def _actor_identity(self, *, role: str = "market", label: str = "target") -> dict[str, str]:
        identity_id = self._runtime_actor_id(role=role, label=label)
        identity_repo.save_actor_identity_profile(
            {
                "identity": {"id": identity_id, "type": "actor"},
                "role_id": role,
            }
        )
        return {"identity": {"id": identity_id, "type": "actor"}, "identity_id": identity_id, "role_id": role}

    def _session(
        self,
        actor_rows: list[dict[str, Any]],
        *,
        handling_calls: list[dict[str, Any]] | None = None,
    ) -> external_im_session.ExternalImSession:
        def list_actors(role_id: str | None) -> list[dict[str, Any]]:
            if role_id is None:
                return actor_rows
            return [row for row in actor_rows if row.get("role_id") == role_id]

        def handle_actor(payload: dict[str, Any]) -> dict[str, Any]:
            if handling_calls is not None:
                handling_calls.append(dict(payload))
            return {"actor_handling_status": "submitted", "runtime_target": "parent", "error": None}

        def check_actor_reachability(*, target_identity_id: str) -> dict[str, Any]:
            for row in actor_rows:
                if row.get("identity_id") == target_identity_id:
                    status = row.get("status") if isinstance(row.get("status"), str) else "online"
                    return {
                        "reachability_status": "online" if status == "online" else "registered_offline",
                        "target_identity_id": target_identity_id,
                        "record": dict(row),
                    }
            return {
                "reachability_status": "never_registered",
                "target_identity_id": target_identity_id,
                "record": None,
            }

        return external_im_session.ExternalImSession(
            actor_lister=list_actors,
            actor_reachability_checker=check_actor_reachability,
            actor_delivery_handler=handle_actor,
        )

    def _external_session(self, session: external_im_session.ExternalImSession) -> tuple[str, dict[str, Any], dict[str, Any]]:
        created = session.create_external_session(display_name="local smoke")
        self.assertTrue(created.get("ok"), msg=created)
        external_session_key = created.get("external_session_key")
        self.assertIsInstance(external_session_key, str, msg=created)
        assert isinstance(external_session_key, str)
        auth = session.authenticate_external_session_key(external_session_key)
        self.assertTrue(auth.get("ok"), msg=auth)
        external_session = auth.get("external_session")
        identity = auth.get("identity")
        self.assertIsInstance(external_session, dict, msg=auth)
        self.assertIsInstance(identity, dict, msg=auth)
        assert isinstance(external_session, dict)
        assert isinstance(identity, dict)
        return external_session_key, external_session, identity

    def test_session_create_auth_send_event_and_conversation_flow(self) -> None:
        actor_identity = self._actor_identity()
        handling_calls: list[dict[str, Any]] = []
        session = self._session(
            [{**actor_identity, "status": "online"}],
            handling_calls=handling_calls,
        )
        _key, external_session, identity = self._external_session(session)

        actors = session.list_actors(role_id="market")
        self.assertEqual(actors["count"], 1)
        self.assertEqual(actors["actors"][0]["identity"], actor_identity["identity"])
        self.assertNotIn("actor_address", actors["actors"][0])

        sent = session.send_message(
            external_session=external_session,
            target_identity_id=actor_identity["identity_id"],
            content="ping",
            reply_to=None,
        )
        self.assertTrue(sent.get("ok"), msg=sent)
        self.assertEqual(sent["actor_handling_status"], "submitted")
        self.assertNotIn("wake_" + "status", sent)
        self.assertEqual(
            handling_calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": actor_identity["identity_id"],
                    "message_id": sent["message"]["id"],
                    "conversation_id": sent["message"]["conversation_id"],
                    "event_id": sent["event_id"],
                }
            ],
        )
        message_id = sent["message"]["id"]

        fetched = session.get_message(external_session=external_session, message_id=message_id)
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched["message"]["content"], "ping")

        actor_reply = message_service.send_im_reply(
            sender_identity=actor_identity["identity"],
            content="pong",
            reply_to=message_id,
        )
        self.assertTrue(actor_reply.get("ok"), msg=actor_reply)
        reply_id = actor_reply["message"]["id"]

        events = session.read_events(external_session=external_session, limit=50, wait_ms=0)
        self.assertTrue(events.get("ok"), msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply_id])
        self.assertNotIn("next_cursor", events)

        replies = session.list_replies(external_session=external_session, message_id=message_id)
        self.assertTrue(replies.get("ok"), msg=replies)
        self.assertEqual([row["id"] for row in replies["replies"]], [reply_id])

        self.assertFalse(hasattr(session, "update_" + "disposition"))

        conversation = session.get_direct_conversation(
            external_session=external_session,
            identity_id=actor_identity["identity_id"],
            limit=20,
        )
        self.assertTrue(conversation.get("ok"), msg=conversation)
        self.assertEqual([row["id"] for row in conversation["messages"]], [message_id, reply_id])

    def test_session_list_actors_returns_identity_projection_and_ignores_invalid_rows(self) -> None:
        market = self._actor_identity(role="market", label="valid")
        dev = self._actor_identity(role="dev", label="valid")
        session = self._session(
            [
                {**market, "status": "online"},
                {**dev, "status": "idle"},
                {"identity_id": "", "role_id": "bad", "status": "online"},
                {"status": "online"},
            ]
        )

        actors = session.list_actors(role_id=None)

        self.assertEqual(actors["count"], 2)
        self.assertEqual(
            [row["identity_id"] for row in actors["actors"]],
            [market["identity_id"], dev["identity_id"]],
        )
        self.assertEqual(actors["actors"][1]["reachability_status"], "idle")
        self.assertTrue(all("actor_address" not in row for row in actors["actors"]))

    def test_session_rejects_missing_or_unreachable_actor_identity(self) -> None:
        session = self._session([])
        _key, external_session, _identity = self._external_session(session)

        missing = session.send_message(
            external_session=external_session,
            target_identity_id="",
            content="ping",
            reply_to=None,
        )
        unreachable = session.send_message(
            external_session=external_session,
            target_identity_id="act-market-missing",
            content="ping",
            reply_to=None,
        )

        self.assertFalse(missing.get("ok"), msg=missing)
        self.assertEqual(missing["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("target_identity_id", missing["error"]["message"])
        self.assertFalse(unreachable.get("ok"), msg=unreachable)
        self.assertEqual(unreachable["error"]["code"], "E_IM_TARGET")
        self.assertIn("actor identity profile not found", unreachable["error"]["message"])

    def test_session_list_and_send_reject_offline_actor_rows(self) -> None:
        offline_actor = self._actor_identity(role="market", label="offline")
        session = self._session([{**offline_actor, "status": "offline"}])
        _key, external_session, _identity = self._external_session(session)

        actors = session.list_actors(role_id=None)
        sent = session.send_message(
            external_session=external_session,
            target_identity_id=offline_actor["identity_id"],
            content="ping",
            reply_to=None,
        )

        self.assertEqual(actors["actors"], [])
        self.assertFalse(sent.get("ok"), msg=sent)
        self.assertEqual(sent["error"]["code"], "E_IM_TARGET")
        self.assertIn("not online", sent["error"]["message"])

    def test_session_reads_actor_reply_once_without_client_cursor(self) -> None:
        actor_identity = self._actor_identity()
        session = self._session([{**actor_identity, "status": "online"}])
        _key, external_session, identity = self._external_session(session)
        initial_cursor = external_session["last_event_id"]
        sent = session.send_message(
            external_session=external_session,
            target_identity_id=actor_identity["identity_id"],
            content="ping",
            reply_to=None,
        )
        self.assertTrue(sent.get("ok"), msg=sent)
        self.assertEqual(external_session["last_event_id"], initial_cursor)
        actor_reply = message_service.send_im_reply(
            sender_identity=actor_identity["identity"],
            content="pong",
            reply_to=sent["message"]["id"],
        )
        self.assertTrue(actor_reply.get("ok"), msg=actor_reply)

        first = session.read_events(external_session=external_session, limit=50, wait_ms=0)
        second = session.read_events(external_session=external_session, limit=50, wait_ms=0)
        ack = session.ack_event(external_session=external_session, event_id=actor_reply["event_id"])
        third = session.read_events(external_session=external_session, limit=50, wait_ms=0)

        self.assertEqual([event["message_id"] for event in first["events"]], [actor_reply["message"]["id"]])
        self.assertEqual([event["message_id"] for event in second["events"]], [actor_reply["message"]["id"]])
        self.assertTrue(ack.get("ok"), msg=ack)
        self.assertEqual(third["events"], [])

    def test_external_delivery_is_external_session_read_ack_not_actor_processing(self) -> None:
        actor_identity = self._actor_identity()
        session = self._session([{**actor_identity, "status": "online"}])
        _key, external_session, identity = self._external_session(session)
        sent = session.send_message(
            external_session=external_session,
            target_identity_id=actor_identity["identity_id"],
            content="ping",
            reply_to=None,
        )
        self.assertTrue(sent.get("ok"), msg=sent)
        actor_reply = message_service.send_im_reply(
            sender_identity=actor_identity["identity"],
            content="pong",
            reply_to=sent["message"]["id"],
        )
        self.assertTrue(actor_reply.get("ok"), msg=actor_reply)

        events = session.read_events(external_session=external_session, limit=50, wait_ms=0)
        ack = session.ack_event(external_session=external_session, event_id=actor_reply["event_id"])

        self.assertEqual([event["message_id"] for event in events["events"]], [actor_reply["message"]["id"]])
        self.assertTrue(ack.get("ok"), msg=ack)
        self.assertNotIn("actor_handling_status", events)
        self.assertNotIn("task_sys", str(events))

    def test_session_reply_uses_reply_wrapper_without_explicit_target_identity(self) -> None:
        actor_identity = self._actor_identity(role="market", label="reply-wrapper")
        handling_calls: list[dict[str, Any]] = []
        session = self._session(
            [{**actor_identity, "status": "online"}],
            handling_calls=handling_calls,
        )
        _key, external_session, identity = self._external_session(session)
        root = message_service.send_im_message(
            sender_identity=actor_identity["identity"],
            target_identity=identity,
            content="ping from actor",
        )

        reply = session.send_message(
            external_session=external_session,
            target_identity_id=None,
            content="pong from external",
            reply_to=root["message"]["id"],
        )

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["target_identity"], actor_identity["identity"])
        self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
        self.assertEqual(reply["actor_handling_status"], "submitted")
        self.assertEqual(
            handling_calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": actor_identity["identity_id"],
                    "message_id": reply["message"]["id"],
                    "conversation_id": reply["message"]["conversation_id"],
                    "event_id": reply["event_id"],
                }
            ],
        )
