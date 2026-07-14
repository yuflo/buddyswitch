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

class ImessageRoutingTests(unittest.TestCase):
    def test_first_sender_message_creates_external_session_and_reuses_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            first = controller.handle_inbound_message(_row(text="hello", guid="guid-1"))
            first_delivery = controller.poll_control_delivery_once()
            second = controller.handle_inbound_message(_row(text="hello again", guid="guid-2"))
            second_delivery = controller.poll_control_delivery_once()

        self.assertEqual(first["status"], "needs_actor")
        self.assertEqual(second["status"], "needs_actor")
        self.assertEqual(first_delivery["sent"], 1)
        self.assertEqual(second_delivery["sent"], 1)
        self.assertEqual([row["external_session_key"] for row in api.created], ["imsk-1"])
        self.assertEqual([row["text"] for row in imsg.sent], [PROMPT, PROMPT])

    def test_inbound_sender_binds_external_identity_session_and_current_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(
                _row(sender="a@example.com", text="/actors", guid="guid-bind", chat_id="7")
            )
            delivery = controller.poll_control_delivery_once()
            state = controller.state_store.load()

        self.assertEqual(result["status"], "actors_list_queued")
        self.assertEqual(delivery["sent"], 1)
        self.assertEqual(api.created[0]["external_session_key"], "imsk-1")
        contact = state["contacts"]["sender:a@example.com"]
        self.assertEqual(contact["external_session_key"], "imsk-1")
        self.assertEqual(contact["external_identity_id"], "ext-fake-1")
        self.assertEqual(contact["route"], {"chat_id": "7", "sender": "a@example.com"})
        self.assertNotIn("routes", contact)

    def test_two_senders_keep_external_sessions_choices_contact_route_and_dedupe_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(sender="a@example.com", text="/actors", guid="guid-a1", chat_id="1"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(sender="b@example.com", text="/actors", guid="guid-b1", chat_id="2"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(sender="a@example.com", text="1", guid="guid-a2", chat_id="1"))
            controller.poll_control_delivery_once()
            sent = controller.handle_inbound_message(_row(sender="a@example.com", text="ping", guid="guid-a3", chat_id="1"))
            prompted = controller.handle_inbound_message(_row(sender="b@example.com", text="ping", guid="guid-b2", chat_id="2"))
            controller.poll_control_delivery_once()
            duplicate = controller.handle_inbound_message(_row(sender="a@example.com", text="ping", guid="guid-a3", chat_id="1"))
            state = controller.state_store.load()

        self.assertEqual([row["external_session_key"] for row in api.created], ["imsk-1", "imsk-2"])
        self.assertEqual(sent["status"], "delivered")
        self.assertEqual(prompted["status"], "needs_actor")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(api.sent[0]["external_session_key"], "imsk-1")
        self.assertEqual(state["contacts"]["sender:a@example.com"]["active_identity_id"], "act-market-demo")
        self.assertIn("active_identity_expires_at", state["contacts"]["sender:a@example.com"])
        self.assertNotIn("active_identity_id", state["contacts"]["sender:b@example.com"])
        self.assertNotIn("active_identity_expires_at", state["contacts"]["sender:b@example.com"])
        self.assertEqual(state["contacts"]["sender:a@example.com"]["route"], {"chat_id": "1", "sender": "a@example.com"})
        self.assertEqual(state["contacts"]["sender:b@example.com"]["route"], {"chat_id": "2", "sender": "b@example.com"})
        self.assertNotIn("routes", state["contacts"]["sender:a@example.com"])
        self.assertNotIn("routes", state["contacts"]["sender:b@example.com"])
        self.assertEqual(imsg.sent[-1]["route"], {"chat_id": "2", "sender": "b@example.com"})

    def test_actors_control_message_lists_online_actors_and_stores_snapshot(self) -> None:
        actors = [
            _actor("market", "act-market-online"),
            _actor("dev", "act-dev-offline", status="offline"),
            _actor("pm", "act-pm-online"),
        ]
        with tempfile.TemporaryDirectory() as temp_root:
            now = _fixed_now()
            controller, _api, imsg = _controller(Path(temp_root), api=_FakeBuddySwitchImApi(actors=actors), now_fn=lambda: now)

            result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            state_after_inbound = controller.state_store.load()
            delivery = controller.poll_control_delivery_once()
            state = controller.state_store.load()

        self.assertEqual(result["status"], "actors_list_queued")
        self.assertEqual(delivery["sent"], 1)
        self.assertEqual(state_after_inbound["contacts"]["sender:user-a@example.com"]["pending_actor_choices"], {})
        self.assertEqual(imsg.sent[0]["text"], "[1] market act-market-online\n[2] pm act-pm-online")
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["pending_actor_choices"],
            {"1": "act-market-online", "2": "act-pm-online"},
        )
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["pending_actor_choices_expires_at"],
            _format_test_utc(now + timedelta(seconds=imessage_channel.PENDING_ACTOR_CHOICE_SECONDS)),
        )

    def test_actors_choices_activate_only_after_actor_list_delivery_succeeds(self) -> None:
        current = [_fixed_now()]
        with tempfile.TemporaryDirectory() as temp_root:
            imsg = _RecoveringImsg(failures=1)
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg, now_fn=lambda: current[0])

            result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            state_after_inbound = controller.state_store.load()
            first_delivery = controller.poll_control_delivery_once()
            state_after_failure = controller.state_store.load()
            imsg.failures = 0
            current[0] = current[0] + timedelta(seconds=2)
            second_delivery = controller.poll_control_delivery_once()
            state_after_success = controller.state_store.load()

        contact_after_inbound = state_after_inbound["contacts"]["sender:user-a@example.com"]
        contact_after_failure = state_after_failure["contacts"]["sender:user-a@example.com"]
        contact_after_success = state_after_success["contacts"]["sender:user-a@example.com"]
        self.assertEqual(result["status"], "actors_list_queued")
        self.assertEqual(contact_after_inbound["pending_actor_choices"], {})
        self.assertEqual(contact_after_failure["pending_actor_choices"], {})
        self.assertEqual(first_delivery["sent"], 0)
        self.assertEqual(first_delivery["failed"], 0)
        self.assertEqual(first_delivery["retrying"], 1)
        self.assertEqual(second_delivery["sent"], 1)
        self.assertEqual(second_delivery["failed"], 0)
        self.assertEqual(contact_after_success["pending_actor_choices"], {"1": "act-market-demo"})
        self.assertNotIn("control_delivery", contact_after_success)

    def test_control_delivery_fails_after_three_attempts_with_error_visible(self) -> None:
        current = [_fixed_now()]
        with tempfile.TemporaryDirectory() as temp_root:
            imsg = _RecoveringImsg(failures=3)
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg, now_fn=lambda: current[0])

            result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            first_delivery = controller.poll_control_delivery_once()
            current[0] = current[0] + timedelta(seconds=2)
            second_delivery = controller.poll_control_delivery_once()
            current[0] = current[0] + timedelta(seconds=2)
            third_delivery = controller.poll_control_delivery_once()
            state_after_failure = controller.state_store.load()

        contact_after_failure = state_after_failure["contacts"]["sender:user-a@example.com"]
        self.assertEqual(result["status"], "actors_list_queued")
        self.assertEqual(first_delivery, {"ok": True, "sent": 0, "retrying": 1, "failed": 0})
        self.assertEqual(second_delivery, {"ok": True, "sent": 0, "retrying": 1, "failed": 0})
        self.assertEqual(third_delivery, {"ok": True, "sent": 0, "retrying": 0, "failed": 1})
        self.assertEqual(contact_after_failure["pending_actor_choices"], {})
        self.assertEqual(contact_after_failure["control_delivery"]["status"], "failed")
        self.assertEqual(contact_after_failure["control_delivery"]["attempts"], 3)
        self.assertEqual(contact_after_failure["control_delivery"]["last_error"], "AppleEvent timed out -1712")

    def test_numeric_selection_uses_pending_snapshot_without_posting_message(self) -> None:
        actors = [_actor("market", "act-market-first"), _actor("dev", "act-dev-second")]
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi(actors=actors)
            now = _fixed_now()
            controller, _api, imsg = _controller(Path(temp_root), api=api, now_fn=lambda: now)
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            controller.poll_control_delivery_once()
            api.actors = [_actor("design", "act-design-later")]

            result = controller.handle_inbound_message(_row(text="2", guid="guid-select"))
            state_after_inbound = controller.state_store.load()
            delivery = controller.poll_control_delivery_once()
            state = controller.state_store.load()

        self.assertEqual(result["status"], "actor_selection_queued")
        self.assertNotIn("active_identity_id", state_after_inbound["contacts"]["sender:user-a@example.com"])
        self.assertEqual(delivery["sent"], 1)
        contact = state["contacts"]["sender:user-a@example.com"]
        self.assertEqual(contact["active_identity_id"], "act-dev-second")
        self.assertEqual(
            contact["active_identity_expires_at"],
            _format_test_utc(now + timedelta(seconds=imessage_channel.ACTIVE_ACTOR_IDLE_SECONDS)),
        )
        self.assertEqual(contact["pending_actor_choices"], {})
        self.assertNotIn("pending_actor_choices_expires_at", contact)
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent[-1]["text"], "act-dev-second")

    def test_numeric_selection_activates_actor_only_after_confirmation_delivery(self) -> None:
        current = [_fixed_now()]
        with tempfile.TemporaryDirectory() as temp_root:
            imsg = _RecoveringImsg(failures=0)
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg, now_fn=lambda: current[0])
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            controller.poll_control_delivery_once()

            imsg.failures = 1
            selected = controller.handle_inbound_message(_row(text="1", guid="guid-select"))
            state_after_inbound = controller.state_store.load()
            first_delivery = controller.poll_control_delivery_once()
            state_after_failure = controller.state_store.load()
            imsg.failures = 0
            current[0] = current[0] + timedelta(seconds=2)
            second_delivery = controller.poll_control_delivery_once()
            state_after_success = controller.state_store.load()

        contact_after_inbound = state_after_inbound["contacts"]["sender:user-a@example.com"]
        contact_after_failure = state_after_failure["contacts"]["sender:user-a@example.com"]
        contact_after_success = state_after_success["contacts"]["sender:user-a@example.com"]
        self.assertEqual(selected["status"], "actor_selection_queued")
        self.assertNotIn("active_identity_id", contact_after_inbound)
        self.assertNotIn("active_identity_id", contact_after_failure)
        self.assertEqual(contact_after_failure["pending_actor_choices"], {"1": "act-market-demo"})
        self.assertEqual(first_delivery["retrying"], 1)
        self.assertEqual(second_delivery["sent"], 1)
        self.assertEqual(contact_after_success["active_identity_id"], "act-market-demo")
        self.assertEqual(contact_after_success["pending_actor_choices"], {})

    def test_numeric_without_pending_choices_is_ordinary_message_and_prompts_when_no_active_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(_row(text="2", guid="guid-number"))
            delivery = controller.poll_control_delivery_once()

        self.assertEqual(result["status"], "needs_actor")
        self.assertEqual(delivery["sent"], 1)
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent, [{"route": {"chat_id": "6", "sender": "user-a@example.com"}, "text": PROMPT}])

    def test_ordinary_message_without_active_actor_sends_minimal_actors_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(_row(text="plain message", guid="guid-plain"))
            delivery = controller.poll_control_delivery_once()

        self.assertEqual(result["status"], "needs_actor")
        self.assertEqual(delivery["sent"], 1)
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent[0]["text"], PROMPT)

    def test_ordinary_message_posts_to_active_actor_with_original_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="1", guid="guid-select"))
            controller.poll_control_delivery_once()

            result = controller.handle_inbound_message(_row(text="  hello actor  ", guid="guid-message"))

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(api.sent[0]["target_identity_id"], "act-market-demo")
        self.assertEqual(api.sent[0]["content"], "hello actor")

    def test_expired_active_actor_prompts_without_posting_message(self) -> None:
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
                            "route": {"chat_id": "6", "sender": "user-a@example.com"},
                            "active_identity_id": "act-market-demo",
                            "active_identity_expires_at": _format_test_utc(now - timedelta(seconds=1)),
                            "pending_actor_choices": {},
                            "seen_inbound_keys": [],
                            "sent_outbound_event_ids": [],
                        }
                    },
                }
            )

            result = controller.handle_inbound_message(_row(text="late ping", guid="guid-late"))
            state = controller.state_store.load()
            delivery = controller.poll_control_delivery_once()

        contact = state["contacts"]["sender:user-a@example.com"]
        self.assertEqual(result["status"], "needs_actor")
        self.assertEqual(delivery["sent"], 1)
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent, [{"route": {"chat_id": "6", "sender": "user-a@example.com"}, "text": PROMPT}])
        self.assertNotIn("active_identity_id", contact)
        self.assertNotIn("active_identity_expires_at", contact)

    def test_expired_pending_choice_is_not_used_for_numeric_selection(self) -> None:
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
                            "route": {"chat_id": "6", "sender": "user-a@example.com"},
                            "pending_actor_choices": {"1": "act-market-demo"},
                            "pending_actor_choices_expires_at": _format_test_utc(now - timedelta(seconds=1)),
                            "seen_inbound_keys": [],
                            "sent_outbound_event_ids": [],
                        }
                    },
                }
            )

            result = controller.handle_inbound_message(_row(text="1", guid="guid-stale-choice"))
            state = controller.state_store.load()
            delivery = controller.poll_control_delivery_once()

        contact = state["contacts"]["sender:user-a@example.com"]
        self.assertEqual(result["status"], "needs_actor")
        self.assertEqual(delivery["sent"], 1)
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent, [{"route": {"chat_id": "6", "sender": "user-a@example.com"}, "text": PROMPT}])
        self.assertEqual(contact["pending_actor_choices"], {})
        self.assertNotIn("pending_actor_choices_expires_at", contact)
        self.assertNotIn("active_identity_id", contact)
        self.assertNotIn("active_identity_expires_at", contact)

    def test_successful_ordinary_message_refreshes_active_actor_idle_ttl(self) -> None:
        current = [_fixed_now()]

        def now_fn() -> datetime:
            return current[0]

        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root), now_fn=now_fn)
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            controller.poll_control_delivery_once()
            controller.handle_inbound_message(_row(text="1", guid="guid-select"))
            controller.poll_control_delivery_once()
            current[0] = _fixed_now() + timedelta(minutes=10)

            result = controller.handle_inbound_message(_row(text="hello after idle", guid="guid-refresh"))
            state = controller.state_store.load()

        contact = state["contacts"]["sender:user-a@example.com"]
        self.assertEqual(result["status"], "delivered")
        self.assertEqual(api.sent[0]["target_identity_id"], "act-market-demo")
        self.assertEqual(
            contact["active_identity_expires_at"],
            _format_test_utc(current[0] + timedelta(seconds=imessage_channel.ACTIVE_ACTOR_IDLE_SECONDS)),
        )
