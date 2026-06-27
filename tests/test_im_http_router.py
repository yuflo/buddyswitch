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

from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tools.launcher import im_http_router  # noqa: E402


class ImHttpRouterTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _actor_address(self) -> dict[str, str]:
        return ActorAddress(
            role_id="market",
            actor_id=self._runtime_actor_id(role="market", label="target"),
        ).to_payload()

    def test_external_http_contract_send_events_get_and_mark(self) -> None:
        actor_address = self._actor_address()
        wake_calls: list[dict[str, object]] = []
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda role_id: [
                {
                    "actor_address": actor_address,
                    "status": "online",
                    "last_seen_at": "2026-06-25T00:00:00Z",
                }
            ]
            if role_id == "market"
            else [],
            wake_actor=lambda payload: wake_calls.append(dict(payload)) or {"wake_status": "submitted"},
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

        old_route = "/api/im/" + "external-" + "participants"
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
        self.assertEqual(actors["actors"][0]["participant"], {"kind": "actor", "actor_address": actor_address})

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "to": {"kind": "actor", "actor_address": actor_address},
                    "content": "ping",
                    "reply_to": None,
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["wake_status"], "submitted")
        self.assertNotIn("next_cursor", sent)
        message_id = sent["message"]["id"]
        self.assertEqual(len(wake_calls), 1)
        self.assertEqual(wake_calls[0]["type"], "im.message.created")
        self.assertNotIn("content", wake_calls[0])

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

        status, message = router.handle(
            "GET",
            f"/api/im/messages/{message_id}",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(message["message"]["content"], "ping")

        auth = message_service.authenticate_external_connection_key(key)
        self.assertTrue(auth["ok"], msg=auth)
        actor_reply = message_service.send_im_message(
            sender_participant={"kind": "actor", "actor_address": actor_address},
            to=auth["participant"],
            content="pong",
            reply_to=message_id,
            wake_actor=lambda _payload: {"wake_status": "not_applicable"},
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
        self.assertEqual(repeated["events"], [])

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
            f"/api/im/conversations/direct?kind=actor&role_id=market&actor_id={actor_address['actor_id']}&limit=20",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=conversation)
        self.assertEqual([row["id"] for row in conversation["messages"]], [message_id, reply_id])

    def test_old_messages_send_route_is_not_im_contract(self) -> None:
        router = im_http_router.ImHttpRouter(actor_lister=lambda _role_id: [], wake_actor=lambda _payload: {})

        old_route = "/api/messages" + "/send"
        status, payload = router.handle("POST", old_route, b'{"actor_id":"act-x","content":"hi"}', {})

        self.assertEqual(status, 404)
        self.assertFalse(payload["ok"])

    def test_message_send_payload_errors_return_json_400(self) -> None:
        router = im_http_router.ImHttpRouter(actor_lister=lambda _role_id: [], wake_actor=lambda _payload: {})
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
        self.assertIn("to", payload["error"]["message"])

        status, payload = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "to": {"kind": "actor", "actor_address": {"role_id": "market"}},
                    "content": "bad target",
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_IM_PAYLOAD")
        self.assertIn("actor_address", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
