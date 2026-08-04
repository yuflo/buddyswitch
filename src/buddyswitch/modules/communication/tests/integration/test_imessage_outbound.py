"""iMessage outbound delivery and durable message-link contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from buddyswitch.modules.communication.private.adapters.web import (
    imessage_channel,
)

from ._imessage_fakes import (
    _FailingImsg,
    _FakeImsg,
    _actor_reply_identity,
    _controller,
)


SENDER_KEY = "sender:user-a@example.com"


class _MutableClock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


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

            result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(result["status"], "delivered")
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

            first = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            second = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(first["status"], "delivered")
        self.assertEqual(second["status"], "ack_retried")
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

    def test_send_failure_persists_retry_without_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            clock = _MutableClock()
            controller, api, _imsg = _controller(
                Path(temp_root),
                imsg=_FailingImsg(fail_on_call=1),
                clock=clock,
            )
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")

            result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(result["status"], "retry_scheduled")
        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["message_links"], {})
        self.assertEqual(
            state["contacts"][SENDER_KEY]["outbound_retry"],
            {
                "event_id": "imev-actor-1",
                "message_id": "msg-actor-1",
                "first_failed_at": 1_000.0,
                "next_attempt_at": 1_001.0,
                "attempts": 1,
                "last_error": "imessage_send_failed",
            },
        )
        self.assertEqual(api.ack_calls, [])

    def test_retry_deadline_is_never_extended_beyond_two_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            clock = _MutableClock()
            failing_imsg = _FailingImsg(fail_on_call=1)
            controller, api, _imsg = _controller(
                Path(temp_root),
                imsg=failing_imsg,
                clock=clock,
            )
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-deadline", message_id="msg-deadline")
            controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            clock.advance(119)
            controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            retry = controller.state_store.load()["contacts"][SENDER_KEY]["outbound_retry"]
            clock.advance(1)

            eligible_at_deadline = controller.outbound_contact_keys()
            with mock.patch("sys.stderr"):
                terminal = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)

        self.assertLessEqual(retry["next_attempt_at"], 1_120.0)
        self.assertIn(SENDER_KEY, eligible_at_deadline)
        self.assertEqual(terminal["status"], "delivery_failed")
        self.assertEqual(len(failing_imsg.sent), 2)

    def test_retry_is_ineligible_until_next_attempt_at(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            clock = _MutableClock()
            controller, api, _imsg = _controller(
                Path(temp_root),
                imsg=_FailingImsg(fail_on_call=1),
                clock=clock,
            )
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")

            controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            before_due = controller.outbound_contact_keys()
            clock.advance(1)
            at_due = controller.outbound_contact_keys()

        self.assertNotIn(SENDER_KEY, before_due)
        self.assertIn(SENDER_KEY, at_due)

    def test_restart_resumes_due_retry_and_persists_link_before_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            clock = _MutableClock()
            first, api, _imsg = _controller(root, imsg=_FailingImsg(fail_on_call=1), clock=clock)
            first.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")
            first.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            clock.advance(1)

            restarted, _api, succeeding_imsg = _controller(root, api=api, imsg=_FakeImsg(), clock=clock)
            result = restarted.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = restarted.state_store.load()

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(len(succeeding_imsg.sent), 1)
        self.assertIsNone(state["contacts"][SENDER_KEY]["outbound_retry"])
        self.assertEqual(api.ack_calls[-1]["event_id"], "imev-actor-1")

    def test_two_minute_failure_is_persisted_alerted_and_acked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            clock = _MutableClock()
            failing_imsg = _FailingImsg(fail_on_call=1)
            controller, api, _imsg = _controller(Path(temp_root), imsg=failing_imsg, clock=clock)
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")
            controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            clock.advance(120)

            with mock.patch("sys.stderr") as stderr:
                result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(result["status"], "delivery_failed")
        self.assertEqual(len(failing_imsg.sent), 1)
        self.assertIsNone(state["contacts"][SENDER_KEY]["outbound_retry"])
        self.assertEqual(
            state["contacts"][SENDER_KEY]["last_delivery_failure"]["event_id"],
            "imev-actor-1",
        )
        self.assertEqual(api.ack_calls[-1]["event_id"], "imev-actor-1")
        alert = "".join(str(call) for call in stderr.write.call_args_list)
        self.assertIn("delivery_failed", alert)
        self.assertNotIn("user-a@example.com", alert)

    def test_terminal_alert_and_state_never_persist_transport_exception_details(self) -> None:
        sensitive_error = (
            "user-a@example.com imsk-1 chat_id=9 secret-message-content"
        )
        with tempfile.TemporaryDirectory() as temp_root:
            clock = _MutableClock()
            failing_imsg = _FailingImsg(
                fail_on_call=1,
                error_message=sensitive_error,
            )
            controller, api, _imsg = _controller(
                Path(temp_root),
                imsg=failing_imsg,
                clock=clock,
            )
            controller.state_store.save(_bound_state())
            _add_actor_event(
                api,
                event_id="imev-sensitive",
                message_id="msg-sensitive",
                content="secret-message-content",
            )
            controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            retry = controller.state_store.load()["contacts"][SENDER_KEY]["outbound_retry"]
            clock.advance(120)

            with mock.patch("sys.stderr") as stderr:
                controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            failure = controller.state_store.load()["contacts"][SENDER_KEY]["last_delivery_failure"]

        alert = "".join(str(call) for call in stderr.write.call_args_list)
        self.assertEqual(retry["last_error"], "imessage_send_failed")
        self.assertEqual(failure["last_error"], "imessage_send_failed")
        for secret in (
            "user-a@example.com",
            "imsk-1",
            "chat_id=9",
            "secret-message-content",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, alert)
                self.assertNotIn(secret, str(failure))

    def test_terminal_failure_ack_retry_never_resends_imessage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            clock = _MutableClock()
            failing_imsg = _FailingImsg(fail_on_call=1)
            controller, api, _imsg = _controller(Path(temp_root), imsg=failing_imsg, clock=clock)
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-actor-1", message_id="msg-actor-1")
            controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            clock.advance(120)
            api.ack_failures["imev-actor-1"] = [
                {"ok": False, "error": {"code": "E_ACK", "message": "temporary ack failure"}}
            ]
            with mock.patch("sys.stderr"):
                terminal = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
                ack_retry = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)

        self.assertEqual(terminal["status"], "delivery_failed")
        self.assertEqual(ack_retry["status"], "ack_retried")
        self.assertEqual(len(failing_imsg.sent), 1)
        self.assertEqual(len(api.ack_calls), 2)

    def test_outbound_event_without_contact_route_is_not_read_or_acked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state(route=False))
            _add_actor_event(api, event_id="imev-no-route", message_id="msg-no-route")

            result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)

        self.assertEqual(result["status"], "contact_unavailable")
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

            result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(result["status"], "retry_scheduled")
        self.assertEqual(imsg.sent, [])
        self.assertEqual(api.fetched_message_ids, ["msg-missing"])
        self.assertEqual(api.ack_calls, [])
        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["message_links"], {})

    def test_message_fetch_exception_persists_retry_without_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.state_store.save(_bound_state())
            _add_actor_event(api, event_id="imev-fetch-error", message_id="msg-fetch-error")

            with mock.patch.object(
                api,
                "get_message",
                side_effect=imessage_channel.ChannelError("network error imsk-1"),
            ):
                result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(result["status"], "retry_scheduled")
        self.assertEqual(imsg.sent, [])
        self.assertEqual(api.ack_calls, [])
        self.assertEqual(
            state["contacts"][SENDER_KEY]["outbound_retry"]["last_error"],
            "message_fetch_failed",
        )

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

            result = controller.deliver_outbound_contact_once(sender_key=SENDER_KEY)
            state = controller.state_store.load()

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(imsg.sent[-1]["text"], "[Message From act-market-demo]\n\nproactive hello")
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["message_links"]["out-guid-1"],
            {"message_id": "msg-proactive-1", "event_id": "imev-proactive-1"},
        )
