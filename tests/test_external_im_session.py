#!/usr/bin/env python3
"""External IM Session application-boundary tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from env.services import messages as message_service  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tools.launcher import external_im_session  # noqa: E402


class ExternalImSessionTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _actor_address(self, *, role: str = "market", label: str = "target") -> dict[str, str]:
        return ActorAddress(
            role_id=role,
            actor_id=self._runtime_actor_id(role=role, label=label),
        ).to_payload()

    def _session(
        self,
        actor_rows: list[dict[str, Any]],
        *,
        wake_calls: list[dict[str, Any]] | None = None,
    ) -> external_im_session.ExternalImSession:
        def list_actors(role_id: str | None) -> list[dict[str, Any]]:
            if role_id is None:
                return actor_rows
            return [row for row in actor_rows if (row.get("actor_address") or {}).get("role_id") == role_id]

        def wake_actor(payload: dict[str, Any]) -> dict[str, Any]:
            if wake_calls is not None:
                wake_calls.append(dict(payload))
            return {"wake_status": "submitted", "runtime_target": "parent", "error": None}

        return external_im_session.ExternalImSession(actor_lister=list_actors, wake_actor=wake_actor)

    def _connection(self, session: external_im_session.ExternalImSession) -> tuple[str, dict[str, Any], dict[str, Any]]:
        created = session.create_connection(display_name="local smoke")
        self.assertTrue(created.get("ok"), msg=created)
        key = created.get("connection_key")
        self.assertIsInstance(key, str, msg=created)
        assert isinstance(key, str)
        auth = session.authenticate(key)
        self.assertTrue(auth.get("ok"), msg=auth)
        connection = auth.get("connection")
        participant = auth.get("participant")
        self.assertIsInstance(connection, dict, msg=auth)
        self.assertIsInstance(participant, dict, msg=auth)
        assert isinstance(connection, dict)
        assert isinstance(participant, dict)
        return key, connection, participant

    def test_session_create_auth_send_event_conversation_and_disposition_flow(self) -> None:
        actor_address = self._actor_address()
        wake_calls: list[dict[str, Any]] = []
        session = self._session(
            [{"actor_address": actor_address, "status": "online"}],
            wake_calls=wake_calls,
        )
        _key, connection, participant = self._connection(session)

        actors = session.list_actors(role_id="market")
        self.assertEqual(actors["count"], 1)
        self.assertEqual(actors["actors"][0]["identity"], {"id": actor_address["actor_id"], "type": "actor"})
        self.assertNotIn("actor_address", actors["actors"][0])

        sent = session.send_message(
            connection=connection,
            target_identity_id=actor_address["actor_id"],
            content="ping",
            reply_to=None,
        )
        self.assertTrue(sent.get("ok"), msg=sent)
        self.assertEqual(sent["wake_status"], "submitted")
        self.assertEqual(len(wake_calls), 1)
        message_id = sent["message"]["id"]

        fetched = session.get_message(connection=connection, message_id=message_id)
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched["message"]["content"], "ping")

        actor_reply = message_service.send_im_message(
            sender_participant={"kind": "actor", "actor_address": actor_address},
            to=participant,
            content="pong",
            reply_to=message_id,
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )
        self.assertTrue(actor_reply.get("ok"), msg=actor_reply)
        reply_id = actor_reply["message"]["id"]

        events = session.read_events(connection=connection, limit=50, wait_ms=0)
        self.assertTrue(events.get("ok"), msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply_id])
        self.assertNotIn("next_cursor", events)

        replies = session.list_replies(connection=connection, message_id=message_id)
        self.assertTrue(replies.get("ok"), msg=replies)
        self.assertEqual([row["id"] for row in replies["replies"]], [reply_id])

        marked = session.update_disposition(
            connection=connection,
            message_id=reply_id,
            disposition="absorbed",
            reason="handled",
        )
        self.assertTrue(marked.get("ok"), msg=marked)
        self.assertEqual(marked["disposition"], "absorbed")

        conversation = session.get_direct_conversation(
            connection=connection,
            identity_id=actor_address["actor_id"],
            limit=20,
        )
        self.assertTrue(conversation.get("ok"), msg=conversation)
        self.assertEqual([row["id"] for row in conversation["messages"]], [message_id, reply_id])

    def test_session_list_actors_returns_identity_projection_and_ignores_invalid_rows(self) -> None:
        market = self._actor_address(role="market", label="valid")
        dev = self._actor_address(role="dev", label="valid")
        session = self._session(
            [
                {"actor_address": market, "status": "online"},
                {"actor_address": dev, "status": "idle"},
                {"actor_address": {"actor_id": "", "role_id": "bad"}, "status": "online"},
                {"status": "online"},
            ]
        )

        actors = session.list_actors(role_id=None)

        self.assertEqual(actors["count"], 2)
        self.assertEqual(
            [row["identity_id"] for row in actors["actors"]],
            [market["actor_id"], dev["actor_id"]],
        )
        self.assertEqual(actors["actors"][1]["reachability_status"], "idle")
        self.assertTrue(all("actor_address" not in row for row in actors["actors"]))

    def test_session_rejects_missing_or_unreachable_actor_identity(self) -> None:
        session = self._session([])
        _key, connection, _participant = self._connection(session)

        missing = session.send_message(
            connection=connection,
            target_identity_id="",
            content="ping",
            reply_to=None,
        )
        unreachable = session.send_message(
            connection=connection,
            target_identity_id="act-market-missing",
            content="ping",
            reply_to=None,
        )

        self.assertFalse(missing.get("ok"), msg=missing)
        self.assertEqual(missing["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("target_identity_id", missing["error"]["message"])
        self.assertFalse(unreachable.get("ok"), msg=unreachable)
        self.assertEqual(unreachable["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("not a reachable actor identity", unreachable["error"]["message"])

    def test_session_list_and_send_reject_offline_actor_rows(self) -> None:
        offline_actor = self._actor_address(role="market", label="offline")
        session = self._session([{"actor_address": offline_actor, "status": "offline"}])
        _key, connection, _participant = self._connection(session)

        actors = session.list_actors(role_id=None)
        sent = session.send_message(
            connection=connection,
            target_identity_id=offline_actor["actor_id"],
            content="ping",
            reply_to=None,
        )

        self.assertEqual(actors["actors"], [])
        self.assertFalse(sent.get("ok"), msg=sent)
        self.assertEqual(sent["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("not a reachable actor identity", sent["error"]["message"])

    def test_session_reads_actor_reply_once_without_client_cursor(self) -> None:
        actor_address = self._actor_address()
        session = self._session([{"actor_address": actor_address, "status": "online"}])
        _key, connection, participant = self._connection(session)
        sent = session.send_message(
            connection=connection,
            target_identity_id=actor_address["actor_id"],
            content="ping",
            reply_to=None,
        )
        self.assertTrue(sent.get("ok"), msg=sent)
        actor_reply = message_service.send_im_message(
            sender_participant={"kind": "actor", "actor_address": actor_address},
            to=participant,
            content="pong",
            reply_to=sent["message"]["id"],
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
        )
        self.assertTrue(actor_reply.get("ok"), msg=actor_reply)

        first = session.read_events(connection=connection, limit=50, wait_ms=0)
        second = session.read_events(connection=connection, limit=50, wait_ms=0)

        self.assertEqual([event["message_id"] for event in first["events"]], [actor_reply["message"]["id"]])
        self.assertEqual(second["events"], [])


if __name__ == "__main__":
    unittest.main()
