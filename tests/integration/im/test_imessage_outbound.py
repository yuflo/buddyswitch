"""iMessage channel product-logic tests."""

from __future__ import annotations

import json
import queue
import sys
import tempfile
import unittest
import re
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import mock

from tests.support.paths import REPO_ROOT
from tests.support.cli import wait_until

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from tools.launcher import imessage_channel  # noqa: E402


PROMPT = "Send /actors to choose an actor."



from tests.integration.im._imessage_fakes import (
    _BlockingReadApi,
    _FakeBuddySwitchImApi,
    _FakeImsg,
    _FailingImsg,
    _LateReplyApi,
    _QueueImsg,
    _RecoveringImsg,
    _UnavailableImsg,
    _actor,
    _actor_reply_identity,
    _controller,
    _fixed_now,
    _format_test_utc,
    _row,
    _schema_v4_state,
)

class ImessageOutboundTests(unittest.TestCase):
    def test_outbound_delivery_ignores_active_actor_ttl(self) -> None:
        now = _fixed_now()
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root), now_fn=lambda: now)
            controller.state_store.save(
                {
                    "schema_version": imessage_channel.SCHEMA_VERSION,
                    "contacts": {
                        "sender:user-a@example.com": {
                            "external_session_key": "imsk-1",
                            "external_identity_id": "ext-fake-1",
                            "route": {"chat_id": "9", "sender": "user-a@example.com"},
                            "active_identity_id": "act-market-demo",
                            "active_identity_expires_at": _format_test_utc(now - timedelta(minutes=30)),
                            "pending_actor_choices": {},
                            "seen_inbound_keys": [],
                            "sent_outbound_event_ids": [],
                        }
                    },
                }
            )
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-late-outbound",
                    "message_id": "msg-late-outbound",
                    "reply_to": None,
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-late-outbound"] = {
                "id": "msg-late-outbound",
                "content": "still delivered",
                "reply_to": None,
                **_actor_reply_identity(),
            }

            result = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(
            imsg.sent,
            [{"route": {"chat_id": "9", "sender": "user-a@example.com"}, "text": "[Message From act-market-demo]\n\nstill delivered"}],
        )
        self.assertEqual(api.acked, [{"external_session_key": "imsk-1", "event_id": "imev-late-outbound"}])

    def test_actor_reply_uses_contact_route_not_reply_to_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "unrelated-reply-id",
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-reply-1"] = {
                "id": "msg-reply-1",
                "content": "pong",
                "reply_to": "unrelated-reply-id",
                **_actor_reply_identity(),
            }

            first = controller.poll_outbound_once(wait_ms=0)
            second = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(
            imsg.sent[-1],
            {"route": {"chat_id": "9", "sender": "user-a@example.com"}, "text": "[Message From act-market-demo]\n\npong"},
        )
        self.assertEqual(api.ack_calls, [{"external_session_key": "imsk-1", "event_id": "imev-reply-1"}])
        self.assertEqual(api.acked, [{"external_session_key": "imsk-1", "event_id": "imev-reply-1"}])

    def test_actor_proactive_external_message_uses_contact_route_without_reply_to(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.poll_control_delivery_once()
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-proactive-1",
                    "message_id": "msg-proactive-1",
                    "reply_to": None,
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-proactive-1"] = {
                "id": "msg-proactive-1",
                "content": "proactive hello",
                "reply_to": None,
                **_actor_reply_identity(),
            }

            result = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(
            imsg.sent[-1],
            {
                "route": {"chat_id": "9", "sender": "user-a@example.com"},
                "text": "[Message From act-market-demo]\n\nproactive hello",
            },
        )
        self.assertEqual(api.ack_calls, [{"external_session_key": "imsk-1", "event_id": "imev-proactive-1"}])

    def test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root), imsg=_FailingImsg(fail_on_call=3))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "unrelated-reply-id",
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-reply-1"] = {
                "id": "msg-reply-1",
                "content": "pong",
                "reply_to": "unrelated-reply-id",
                **_actor_reply_identity(),
            }

            with self.assertRaises(imessage_channel.ChannelError):
                controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["sent_outbound_event_ids"], [])
        self.assertEqual(api.ack_calls, [])

    def test_poll_outbound_retries_ack_without_duplicate_imessage_after_ack_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "unrelated-reply-id",
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-reply-1"] = {
                "id": "msg-reply-1",
                "content": "pong",
                "reply_to": "unrelated-reply-id",
                **_actor_reply_identity(),
            }
            api.ack_failures["imev-reply-1"] = [
                {"ok": False, "error": {"code": "E_ACK", "message": "temporary ack failure"}}
            ]

            first = controller.poll_outbound_once(wait_ms=0)
            second = controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        reply_sends = [row for row in imsg.sent if row["text"] == "[Message From act-market-demo]\n\npong"]
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(len(reply_sends), 1)
        self.assertEqual(
            api.ack_calls,
            [
                {"external_session_key": "imsk-1", "event_id": "imev-reply-1"},
                {"external_session_key": "imsk-1", "event_id": "imev-reply-1"},
            ],
        )
        self.assertEqual(api.acked, [{"external_session_key": "imsk-1", "event_id": "imev-reply-1"}])
        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["sent_outbound_event_ids"], ["imev-reply-1"])

    def test_outbound_event_without_contact_route_is_not_acked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(
                {
                    "schema_version": imessage_channel.SCHEMA_VERSION,
                    "contacts": {
                        "sender:user-a@example.com": {
                            "external_session_key": "imsk-1",
                            "external_identity_id": "ext-fake-1",
                            "pending_actor_choices": {},
                            "seen_inbound_keys": [],
                            "sent_outbound_event_ids": [],
                        }
                    },
                }
            )
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-no-route",
                    "message_id": "msg-no-route",
                    "reply_to": None,
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-no-route"] = {
                "id": "msg-no-route",
                "content": "cannot route",
                "reply_to": None,
                **_actor_reply_identity(),
            }

            result = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(result["sent"], 0)
        self.assertEqual(imsg.sent, [])
        self.assertEqual(api.ack_calls, [])
        self.assertEqual(api.acked, [])

    def test_poll_outbound_does_not_ack_when_message_fetch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="hello", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-missing-message",
                    "message_id": "msg-missing",
                    "reply_to": "msg-in-1",
                    **_actor_reply_identity(),
                }
            ]

            result = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(result["sent"], 0)
        self.assertEqual(imsg.sent, [])
        self.assertEqual(api.fetched_message_ids, ["msg-missing"])
        self.assertEqual(api.ack_calls, [])

