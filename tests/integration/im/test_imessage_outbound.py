"""iMessage outbound delivery and durable message-link contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.launcher import imessage_channel

from tests.integration.im._imessage_fakes import (
    _FailingImsg,
    _actor_reply_identity,
    _controller,
)


def _bound_state(*, route: bool = True) -> dict[str, Any]:
    contact: dict[str, Any] = {
        "external_session_key": "imsk-1",
        "external_identity_id": "ext-fake-1",
        "seen_inbound_keys": [],
        "message_links": {},
    }
    if route:
        contact["route"] = {"chat_id": "9", "sender": "user-a@example.com"}
    return {
        "schema_version": imessage_channel.SCHEMA_VERSION,
        "contacts": {"sender:user-a@example.com": contact},
    }


def _add_actor_event(api: Any, *, event_id: str, message_id: str, content: str = "pong") -> None:
    api.events_by_key["imsk-1"] = [
        {
            "event_id": event_id,
            "message_id": message_id,
            "reply_to": "msg-inbound" if content == "pong" else None,
            **_actor_reply_identity(),
        }
    ]
    api.messages[message_id] = {
        "id": message_id,
        "content": content,
        "reply_to": "msg-inbound" if content == "pong" else None,
        **_actor_reply_identity(),
    }


class ImessageOutboundTests(unittest.TestCase):
    def test_actor_event_persists_exact_guid_message_link_before_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")

            result = controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(result, {"ok": True, "sent": 1})
        self.assertEqual(
            imsg.sent,
            [
                {
                    "route": {"chat_id": "9", "sender": "user-a@example.com"},
                    "text": "[Message From act-market-demo]\n\npong",
                }
            ],
        )
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["message_links"],
            {
                "out-guid-1": {
                    "message_id": "msg-actor-1",
                    "event_id": "imev-actor-1",
                }
            },
        )
        self.assertEqual(api.ack_calls, [{"external_session_key": "imsk-1", "event_id": "imev-actor-1"}])

    def test_ack_retry_uses_message_link_without_duplicate_imessage_send(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")
            api.ack_failures["imev-actor-1"] = [
                {"ok": False, "error": {"code": "E_ACK", "message": "temporary ack failure"}}
            ]

            first = controller.poll_outbound_once(wait_ms=0)
            second = controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(len(imsg.sent), 1)
        self.assertEqual(
            api.ack_calls,
            [
                {"external_session_key": "imsk-1", "event_id": "imev-actor-1"},
                {"external_session_key": "imsk-1", "event_id": "imev-actor-1"},
            ],
        )
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["message_links"]["out-guid-1"]["message_id"],
            "msg-actor-1",
        )

    def test_imessage_send_failure_creates_no_link_and_does_not_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root), imsg=_FailingImsg(fail_on_call=1))
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")

            with self.assertRaises(imessage_channel.ChannelError):
                controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["message_links"], {})
        self.assertEqual(api.ack_calls, [])

    def test_outbound_event_without_contact_route_is_not_read_or_acked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state(route=False))
            _add_actor_event(api, event_id="imev-no-route", message_id="msg-no-route")

            result = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(result["sent"], 0)
        self.assertEqual(imsg.sent, [])
        self.assertEqual(api.fetched_message_ids, [])
        self.assertEqual(api.ack_calls, [])

    def test_message_fetch_failure_creates_no_link_and_does_not_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state())
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-missing",
                    "message_id": "msg-missing",
                    **_actor_reply_identity(),
                }
            ]

            result = controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(result["sent"], 0)
        self.assertEqual(imsg.sent, [])
        self.assertEqual(api.fetched_message_ids, ["msg-missing"])
        self.assertEqual(api.ack_calls, [])
        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["message_links"], {})

    def test_proactive_actor_message_uses_same_visible_envelope_and_link_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state())
            _add_actor_event(
                api,
                event_id="imev-proactive-1",
                message_id="msg-proactive-1",
                content="proactive hello",
            )

            result = controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(result["sent"], 1)
        self.assertEqual(imsg.sent[-1]["text"], "[Message From act-market-demo]\n\nproactive hello")
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["message_links"]["out-guid-1"],
            {"message_id": "msg-proactive-1", "event_id": "imev-proactive-1"},
        )
