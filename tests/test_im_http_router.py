#!/usr/bin/env python3
"""Central IM HTTP contract tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from env.services import messages as message_service  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tools.launcher import im_http_router  # noqa: E402


class ImHttpRouterTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _actor_identity(self) -> dict[str, str]:
        identity_id = self._runtime_actor_id(role="market", label="target")
        return {"identity": {"id": identity_id, "type": "actor"}, "identity_id": identity_id, "role_id": "market"}

    def test_external_http_contract_send_events_get_and_mark(self) -> None:
        actor_identity = self._actor_identity()
        handling_calls: list[dict[str, object]] = []
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda role_id: [
                {
                    **actor_identity,
                    "status": "online",
                    "last_seen_at": "2026-06-25T00:00:00Z",
                }
            ]
            if role_id in {None, "market"}
            else [],
            actor_message_handler=lambda payload: handling_calls.append(dict(payload)) or {"actor_handling_status": "submitted"},
        )

        status, created = router.handle(
            "POST",
            "/api/im/connections",
            json.dumps({"display_name": "local smoke"}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200)
        self.assertTrue(created["ok"], msg=created)
        key = created["connection_key"]
        self.assertTrue(key.startswith("imck-"))
        self.assertNotIn("participant", created)
        self.assertNotIn("participant_" + "token", created)
        self.assertNotIn("event_" + "cursor", created)

        auth = message_service.authenticate_external_connection_key(key)
        self.assertTrue(auth["ok"], msg=auth)

        status, session = router.handle(
            "GET",
            "/api/im/session",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(session["ok"], msg=session)
        self.assertEqual(session["identity"], auth["identity"])
        self.assertNotIn("connection_key", session)
        self.assertNotIn("participant", session)
        self.assertNotIn("participant_" + "token", session)
        self.assertNotIn("event_" + "cursor", session)

        old_route = "/api/im/" + "external-" + "partici" + "pants"
        status, old_registration = router.handle("POST", old_route, b"{}", {})
        self.assertEqual(status, 404)
        self.assertFalse(old_registration["ok"])

        status, actors = router.handle(
            "GET",
            "/api/im/actors?role_id=market",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(actors["count"], 1)
        self.assertEqual(actors["actors"][0]["identity"], actor_identity["identity"])
        self.assertEqual(actors["actors"][0]["identity_id"], actor_identity["identity_id"])
        self.assertEqual(actors["actors"][0]["role_id"], "market")
        self.assertNotIn("participant", actors["actors"][0])
        self.assertNotIn("actor_address", actors["actors"][0])

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "target_identity_id": actor_identity["identity_id"],
                    "content": "ping",
                    "reply_to": None,
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["actor_handling_status"], "submitted")
        self.assertNotIn("wake_" + "status", sent)
        self.assertNotIn("next_cursor", sent)
        message_id = sent["message"]["id"]
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

        status, events = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(events["events"], [])
        self.assertNotIn("next_cursor", events)

        status, cursor_rejected = router.handle(
            "GET",
            "/api/im/events?" + "cursor" + "=imev-old&wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 400)
        self.assertFalse(cursor_rejected["ok"])
        self.assertEqual(cursor_rejected["error"]["code"], "E_IM_PAYLOAD")

        status, non_visible_ack = router.handle(
            "POST",
            "/api/im/events/ack",
            json.dumps({"event_id": "imev-not-visible"}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 400)
        self.assertFalse(non_visible_ack["ok"])

        status, message = router.handle(
            "GET",
            f"/api/im/messages/{message_id}",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(message["message"]["content"], "ping")

        actor_reply = message_service.send_im_message(
            sender_identity=actor_identity,
            to=auth["identity"],
            content="pong",
            reply_to=message_id,
        )
        reply_id = actor_reply["message"]["id"]

        status, reply_events = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual([event["message_id"] for event in reply_events["events"]], [reply_id])

        status, repeated = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual([event["message_id"] for event in repeated["events"]], [reply_id])

        status, acked = router.handle(
            "POST",
            "/api/im/events/ack",
            json.dumps({"event_id": actor_reply["event_id"]}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(acked["ok"], msg=acked)

        status, after_ack = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(after_ack["events"], [])

        status, mark = router.handle(
            "PATCH",
            f"/api/im/messages/{reply_id}/disposition",
            json.dumps({"disposition": "absorbed", "reason": "consumed"}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(mark["disposition"], "absorbed")

        status, conversation = router.handle(
            "GET",
            f"/api/im/conversations/direct?identity_id={actor_identity['identity_id']}&limit=20",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=conversation)
        self.assertEqual([row["id"] for row in conversation["messages"]], [message_id, reply_id])

        status, missing_identity = router.handle(
            "GET",
            "/api/im/conversations/direct?limit=20",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 400)
        self.assertFalse(missing_identity["ok"])
        self.assertEqual(missing_identity["error"]["message"], "identity_id is required")

    def test_old_messages_send_route_is_not_im_contract(self) -> None:
        router = im_http_router.ImHttpRouter(actor_lister=lambda _role_id: [])

        old_route = "/api/messages" + "/send"
        status, payload = router.handle("POST", old_route, b'{"actor_id":"act-x","content":"hi"}', {})

        self.assertEqual(status, 404)
        self.assertFalse(payload["ok"])

    def test_message_send_payload_errors_return_json_400(self) -> None:
        router = im_http_router.ImHttpRouter(actor_lister=lambda _role_id: [])
        status, created = router.handle(
            "POST",
            "/api/im/connections",
            json.dumps({"display_name": "local smoke"}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200)
        key = created["connection_key"]

        status, payload = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps({"content": "missing target"}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("target_identity_id", payload["error"]["message"])

        status, payload = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "target_identity_id": "act-market-missing",
                    "content": "bad target",
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("target_identity_id", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
