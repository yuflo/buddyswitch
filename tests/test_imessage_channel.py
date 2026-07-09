#!/usr/bin/env python3
"""iMessage channel product-logic tests."""

from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from tools.launcher import imessage_channel  # noqa: E402


PROMPT = "Send /actors to choose an actor."


class _FakeBuddySwitchImApi:
    def __init__(self, *, actors: list[dict[str, Any]] | None = None) -> None:
        self.actors = actors if actors is not None else [_actor("market", "act-market-demo")]
        self.created: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self.ack_calls: list[dict[str, Any]] = []
        self.acked: list[dict[str, Any]] = []
        self.ack_failures: dict[str, list[dict[str, Any]]] = {}
        self.fetched_message_ids: list[str] = []
        self.events_by_key: dict[str, list[dict[str, Any]]] = {}
        self.messages: dict[str, dict[str, Any]] = {}

    def create_external_session(self, *, display_name: str) -> dict[str, Any]:
        external_session_key = f"imsk-{len(self.created) + 1}"
        self.created.append({"display_name": display_name, "external_session_key": external_session_key})
        return {
            "ok": True,
            "external_session_key": external_session_key,
            "identity": {"id": f"ext-fake-{len(self.created)}", "type": "external"},
        }

    def list_actors(self, *, external_session_key: str) -> dict[str, Any]:
        return {"ok": True, "actors": list(self.actors), "count": len(self.actors)}

    def send_message(
        self,
        *,
        external_session_key: str,
        target_identity_id: str,
        content: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        message_id = f"msg-in-{len(self.sent) + 1}"
        self.sent.append(
            {
                "external_session_key": external_session_key,
                "target_identity_id": target_identity_id,
                "content": content,
                "reply_to": reply_to,
                "message_id": message_id,
            }
        )
        return {
            "ok": True,
            "message": {"id": message_id, "conversation_id": "conv-fake", "reply_to": reply_to},
            "event_id": f"imev-in-{len(self.sent)}",
        }

    def read_events(self, *, external_session_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        acked_ids = {row["event_id"] for row in self.acked if row["external_session_key"] == external_session_key}
        return {
            "ok": True,
            "events": [
                dict(row)
                for row in self.events_by_key.get(external_session_key, [])
                if str(row.get("event_id") or "") not in acked_ids
            ],
        }

    def get_message(self, *, external_session_key: str, message_id: str) -> dict[str, Any]:
        self.fetched_message_ids.append(message_id)
        if message_id not in self.messages:
            return {"ok": False, "error": {"code": "E_IM_NOT_FOUND", "message": "message not found"}}
        return {"ok": True, "message": dict(self.messages[message_id])}

    def ack_event(self, *, external_session_key: str, event_id: str) -> dict[str, Any]:
        self.ack_calls.append({"external_session_key": external_session_key, "event_id": event_id})
        failures = self.ack_failures.get(event_id)
        if failures:
            return failures.pop(0)
        self.acked.append({"external_session_key": external_session_key, "event_id": event_id})
        return {"ok": True, "event_id": event_id}


class _BlockingReadApi(_FakeBuddySwitchImApi):
    def __init__(self) -> None:
        super().__init__()
        self.read_started = threading.Event()
        self.release_read = threading.Event()

    def read_events(self, *, external_session_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        self.read_started.set()
        self.release_read.wait(timeout=2)
        return super().read_events(external_session_key=external_session_key, limit=limit, wait_ms=wait_ms)


class _LateReplyApi(_FakeBuddySwitchImApi):
    def __init__(self) -> None:
        super().__init__()
        self.first_read = threading.Event()
        self.read_calls = 0

    def read_events(self, *, external_session_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        self.read_calls += 1
        if self.read_calls == 1:
            self.first_read.set()
            return {"ok": True, "events": []}
        return super().read_events(external_session_key=external_session_key, limit=limit, wait_ms=wait_ms)


class _FakeImsg:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.stopped = False

    def status(self) -> None:
        return None

    def send(self, *, route: dict[str, Any], text: str) -> None:
        self.sent.append({"route": dict(route), "text": text})

    def stop(self) -> None:
        self.stopped = True


class _QueueImsg(_FakeImsg):
    def __init__(self) -> None:
        super().__init__()
        self.rows: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self.watch_started = threading.Event()

    def push(self, row: dict[str, Any]) -> None:
        self.rows.put(row)

    def watch_messages(self) -> Any:
        self.watch_started.set()
        while not self.stopped:
            try:
                row = self.rows.get(timeout=0.02)
            except queue.Empty:
                continue
            if row is None:
                break
            yield row

    def stop(self) -> None:
        super().stop()
        self.rows.put(None)


class _FailingImsg(_FakeImsg):
    def __init__(self, *, fail_on_call: int) -> None:
        super().__init__()
        self.fail_on_call = fail_on_call

    def send(self, *, route: dict[str, Any], text: str) -> None:
        self.sent.append({"route": dict(route), "text": text})
        if len(self.sent) < self.fail_on_call:
            return
        raise imessage_channel.ChannelError("iMessage send status failed")


class _RecoveringImsg(_FakeImsg):
    def __init__(self, *, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def send(self, *, route: dict[str, Any], text: str) -> None:
        self.sent.append({"route": dict(route), "text": text})
        if self.failures > 0:
            self.failures -= 1
            raise imessage_channel.ChannelError("AppleEvent timed out -1712")


def _actor(role_id: str, identity_id: str, *, status: str = "online") -> dict[str, Any]:
    return {
        "identity": {"id": identity_id, "type": "actor"},
        "identity_id": identity_id,
        "role_id": role_id,
        "reachability_status": status,
    }


def _actor_reply_identity(identity_id: str = "act-market-demo") -> dict[str, Any]:
    return {"sender_identity": {"id": identity_id, "type": "actor"}}


def _row(
    *,
    sender: str = "user-a@example.com",
    text: str,
    guid: str,
    chat_id: str = "6",
    is_from_me: bool = False,
) -> dict[str, Any]:
    return {
        "guid": guid,
        "chat_id": chat_id,
        "is_from_me": is_from_me,
        "sender": sender,
        "text": text,
    }


def _controller(
    temp_root: Path,
    *,
    api: _FakeBuddySwitchImApi | None = None,
    imsg: _FakeImsg | None = None,
    now_fn: Any | None = None,
) -> tuple[imessage_channel.ImessageChannelController, _FakeBuddySwitchImApi, _FakeImsg]:
    api = api or _FakeBuddySwitchImApi()
    imsg = imsg or _FakeImsg()
    config = imessage_channel.ChannelConfig(
        server="http://127.0.0.1:8765",
        state_path=temp_root / "state.json",
    )
    kwargs: dict[str, Any] = {"config": config, "api": api, "imsg": imsg}
    if now_fn is not None:
        kwargs["now_fn"] = now_fn
    return imessage_channel.ImessageChannelController(**kwargs), api, imsg


def _fixed_now() -> datetime:
    return datetime(2026, 7, 8, 4, 0, 0, tzinfo=timezone.utc)


def _format_test_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _wait_until(predicate: Any, *, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class ImessageChannelTests(unittest.TestCase):
    def test_default_state_path_uses_imessage_channel_schema_v5(self) -> None:
        config = imessage_channel.ChannelConfig(server="http://127.0.0.1:8765")
        self.assertEqual(config.effective_state_path().parts[-2:], ("imessage-channel", "state.json"))

        with tempfile.TemporaryDirectory() as temp_root:
            store = imessage_channel.ImessageChannelStateStore(Path(temp_root) / "state.json")
            self.assertEqual(store.load(), {"schema_version": 5, "contacts": {}})

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

    def test_worker_processes_actors_while_outbound_poll_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingReadApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="hello", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=30000)
            worker.start()
            self.addCleanup(api.release_read.set)
            self.addCleanup(worker.stop)

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")
            imsg.push(_row(text="/actors", guid="guid-actors", chat_id="9"))

            self.assertTrue(
                _wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
                "actor list was not sent while outbound read was blocked",
            )
            api.release_read.set()
            worker.stop()

        self.assertTrue(imsg.stopped)

    def test_worker_keeps_processing_after_actors_response_send_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _QueueImsg()
            original_send = imsg.send
            failures = {"remaining": 1}

            def fail_first_send(*, route: dict[str, Any], text: str) -> None:
                imsg.sent.append({"route": dict(route), "text": text})
                if failures["remaining"] > 0:
                    failures["remaining"] -= 1
                    raise imessage_channel.ChannelError("AppleEvent timed out -1712")

            imsg.send = fail_first_send  # type: ignore[method-assign]
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
            worker.start()
            self.addCleanup(worker.stop)

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            imsg.push(_row(text="/actors", guid="guid-actors-1", chat_id="9"))
            self.assertTrue(
                _wait_until(lambda: len(imsg.sent) >= 1, timeout=1),
                "first actor list send was not attempted",
            )
            imsg.send = original_send  # type: ignore[method-assign]
            imsg.push(_row(text="/actors", guid="guid-actors-2", chat_id="9"))
            self.assertTrue(
                _wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
                "second actor list was not delivered after first send failure",
            )
            worker.stop()

        self.assertTrue(imsg.stopped)

    def test_worker_delivers_late_reply_without_new_inbound_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _LateReplyApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
            worker.start()
            self.addCleanup(worker.stop)

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.first_read.wait(timeout=1), "first outbound poll did not happen")
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

            self.assertTrue(
                _wait_until(lambda: any(row["text"] == "[Message From act-market-demo]\n\npong" for row in imsg.sent), timeout=1),
                "late actor reply was not sent without another inbound iMessage",
            )
            worker.stop()

        self.assertTrue(imsg.stopped)

    def test_worker_keeps_control_prompt_prompt_while_delayed_reply_returns_once_to_same_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingReadApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=30000)
            worker.start()
            self.addCleanup(api.release_read.set)
            self.addCleanup(worker.stop)

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            imsg.push(_row(text="/actors", guid="guid-actors-1", chat_id="9"))
            self.assertTrue(
                _wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
                "initial actor list was not sent",
            )
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")

            imsg.push(_row(text="1", guid="guid-select", chat_id="9"))
            imsg.push(_row(text="ping", guid="guid-message", chat_id="9"))
            imsg.push(_row(text="/actors", guid="guid-actors-2", chat_id="9"))
            self.assertTrue(
                _wait_until(
                    lambda: sum(1 for row in imsg.sent if row["text"] == "[1] market act-market-demo") >= 2,
                    timeout=1,
                ),
                "actor list was not prompt while outbound read was blocked",
            )
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": None,
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-reply-1"] = {
                "id": "msg-reply-1",
                "content": "pong",
                "reply_to": None,
                **_actor_reply_identity(),
            }
            api.release_read.set()

            self.assertTrue(
                _wait_until(lambda: any(row["text"] == "[Message From act-market-demo]\n\npong" for row in imsg.sent), timeout=1),
                "delayed actor reply was not sent",
            )
            worker.stop()

        reply_sends = [row for row in imsg.sent if row["text"] == "[Message From act-market-demo]\n\npong"]
        self.assertEqual(reply_sends, [{"route": {"chat_id": "9", "sender": "user-a@example.com"}, "text": "[Message From act-market-demo]\n\npong"}])
        self.assertTrue(imsg.stopped)

    def test_worker_stop_terminates_watch_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingReadApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="hello", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=30000)
            worker.start()

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")
            api.release_read.set()

            worker.stop()

        self.assertTrue(imsg.stopped)
        threads = getattr(worker, "_threads", [getattr(worker, "_thread", None)])
        self.assertTrue(all(thread is None or not thread.is_alive() for thread in threads))


class CommandImsgClientSendStatusTests(unittest.TestCase):
    def test_send_accepts_route_scoped_successful_message_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            db_path = Path(temp_root) / "chat.db"
            _create_chat_db(db_path, chat_id=3212)
            commands: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                _insert_outbound_message(db_path, rowid=2, chat_id=3212, error_code=0, is_sent=1, is_finished=0)
                return subprocess.CompletedProcess(command, 0, stdout='{"status":"sent"}', stderr="")

            client = imessage_channel.CommandImsgClient(
                imsg_bin="imsg",
                messages_db_path=db_path,
                send_status_timeout_seconds=0.1,
                send_status_poll_interval_seconds=0.01,
                subprocess_run=fake_run,
            )

            client.send(route={"chat_id": "3212", "sender": "hblouis@icloud.com"}, text="hello")

        self.assertEqual(commands[0][:5], ["imsg", "send", "--text", "hello", "--chat-id"])

    def test_send_rejects_failed_message_row_after_successful_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            db_path = Path(temp_root) / "chat.db"
            _create_chat_db(db_path, chat_id=3212)

            def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
                _insert_outbound_message(db_path, rowid=2, chat_id=3212, error_code=22, is_sent=0, is_finished=1)
                return subprocess.CompletedProcess(command, 0, stdout='{"status":"sent"}', stderr="")

            client = imessage_channel.CommandImsgClient(
                imsg_bin="imsg",
                messages_db_path=db_path,
                send_status_timeout_seconds=0.1,
                send_status_poll_interval_seconds=0.01,
                subprocess_run=fake_run,
            )

            with self.assertRaisesRegex(imessage_channel.ChannelError, "error=22"):
                client.send(route={"chat_id": "3212", "sender": "hblouis@icloud.com"}, text="hello")

    def test_send_keeps_polling_transient_finished_unsent_row_without_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            db_path = Path(temp_root) / "chat.db"
            _create_chat_db(db_path, chat_id=3212)
            poll_count = 0

            def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
                _insert_outbound_message(db_path, rowid=2, chat_id=3212, error_code=0, is_sent=0, is_finished=1)
                return subprocess.CompletedProcess(command, 0, stdout='{"status":"sent"}', stderr="")

            def mark_sent_after_first_poll() -> None:
                nonlocal poll_count
                poll_count += 1
                if poll_count == 1:
                    _update_message_send_state(db_path, rowid=2, error_code=0, is_sent=1, is_delivered=1, is_finished=1)

            client = imessage_channel.CommandImsgClient(
                imsg_bin="imsg",
                messages_db_path=db_path,
                send_status_timeout_seconds=0.1,
                send_status_poll_interval_seconds=0.01,
                subprocess_run=fake_run,
                send_status_poll_hook=mark_sent_after_first_poll,
            )

            client.send(route={"chat_id": "3212", "sender": "hblouis@icloud.com"}, text="hello")

        self.assertEqual(poll_count, 1)


class ImessageChannelResidueTests(unittest.TestCase):
    def test_channel_source_does_not_import_central_im_internals(self) -> None:
        source = (ROOT / "tools" / "launcher" / "imessage_channel.py").read_text(encoding="utf-8")

        self.assertNotIn("env.services.messages", source)
        self.assertNotIn("env.services.im_delivery", source)
        self.assertNotIn("env.repos.messages", source)
        self.assertNotIn("send_im_message", source)
        self.assertNotIn("send_external_session_message", source)
        self.assertNotIn("read_external_session_events", source)
        self.assertNotIn("ack_external_session_event", source)

    def test_channel_source_has_no_retired_per_message_route_model(self) -> None:
        source = (ROOT / "tools" / "launcher" / "imessage_channel.py").read_text(encoding="utf-8")

        self.assertNotIn("_contact_" + "routes", source)
        self.assertNotIn("contact[" + '"routes"' + "]", source)
        self.assertNotIn("contact.get(" + '"routes"' + ")", source)
        self.assertNotRegex(source, r"\[[^\]]*message_id[^\]]*\]\s*=\s*route")
        self.assertNotIn(".get(" + "reply_to" + ")", source)
        self.assertIsNone(re.search(r"message\.get\(\"reply_to\"\)[\s\S]{0,120}route", source))
        self.assertIsNone(re.search(r"event\.get\(\"reply_to\"\)[\s\S]{0,120}route", source))

    def test_no_retired_imessage_surface(self) -> None:
        retired_terms = (
            "target" + "-identity-id",
            "allow" + "-sender",
            "allowed" + "_senders",
            "buddyswitch-codex imessage " + "bridge",
            "imessage" + "-bridge",
            "IMESSAGE" + "_BRIDGE",
            "imessage" + "_bridge.py",
            "test_imessage" + "_bridge.py",
        )
        live_paths = [
            ROOT / "buddyswitch-codex",
            ROOT / "tools" / "launcher",
            ROOT / "tests",
        ]
        hits: list[str] = []
        for path in live_paths:
            files = [path] if path.is_file() else [row for row in path.rglob("*") if row.is_file()]
            for file_path in files:
                if "__pycache__" in file_path.parts:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                for term in retired_terms:
                    if term in text:
                        hits.append(f"{file_path.relative_to(ROOT)}: contains {term}")
        self.assertEqual(hits, [])

    def test_selected_actor_ttl_source_uses_expiry_helpers_not_permanent_paths(self) -> None:
        source = (ROOT / "tools" / "launcher" / "imessage_channel.py").read_text(encoding="utf-8")

        for required_term in (
            "active_identity_expires_at",
            "pending_actor_choices_expires_at",
            "ACTIVE_ACTOR_IDLE_SECONDS",
            "PENDING_ACTOR_CHOICE_SECONDS",
        ):
            self.assertIn(required_term, source)

        retired_paths = (
            "SCHEMA_VERSION = " + "3",
            "SCHEMA_VERSION = " + "4",
            "contact" + '["active_identity_id"] = selected',
            "contact" + '.get("pending_actor_choices")',
            "def _active_identity_id" + "(contact: dict[str, Any]) -> str",
        )
        hits = [pattern for pattern in retired_paths if pattern in source]
        self.assertEqual(hits, [])

    def test_control_handlers_do_not_send_imessage_synchronously(self) -> None:
        source = (ROOT / "tools" / "launcher" / "imessage_channel.py").read_text(encoding="utf-8")
        handler_names = ("_handle_actors", "_handle_numeric_choice", "_handle_ordinary_message")
        hits: list[str] = []
        for handler_name in handler_names:
            match = re.search(rf"def {handler_name}\([\s\S]*?\n    def ", source)
            if match is None:
                hits.append(f"{handler_name}: missing")
                continue
            body = match.group(0)
            if "self.imsg.send" in body:
                hits.append(f"{handler_name}: synchronous imsg send")
        self.assertEqual(hits, [])

    def test_channel_semantics_stay_out_of_web_http_and_core(self) -> None:
        forbidden_terms = (
            "control_delivery",
            "CONTROL_DELIVERY_MAX_ATTEMPTS",
            "CONTROL_KIND_ACTOR_CHOICES",
            "pending_actor_choices",
            "active_actor_id",
            "[Message From",
            "active_identity_expires_at",
            "pending_actor_choices_expires_at",
            "ACTIVE_ACTOR_IDLE_SECONDS",
            "PENDING_ACTOR_CHOICE_SECONDS",
        )
        paths = [
            ROOT / "tools" / "launcher" / "web_management.py",
            ROOT / "tools" / "launcher" / "im_http_router.py",
            ROOT / "scripts" / "env" / "services",
            ROOT / "scripts" / "env" / "repos",
            ROOT / "scripts" / "env" / "tool_runtime",
        ]
        hits: list[str] = []
        for path in paths:
            files = [path] if path.is_file() else [row for row in path.rglob("*.py") if row.is_file()]
            for file_path in files:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"""["']/actors["']""", text):
                    hits.append(f"{file_path.relative_to(ROOT)}: contains iMessage actors control literal")
                for term in forbidden_terms:
                    if term in text:
                        hits.append(f"{file_path.relative_to(ROOT)}: contains {term}")
        self.assertEqual(hits, [])

    def test_worker_source_no_longer_uses_serial_inbound_outbound_loop(self) -> None:
        source = (ROOT / "tools" / "launcher" / "imessage_channel.py").read_text(encoding="utf-8")

        self.assertIn("def run_outbound_forever", source)
        self.assertIsNone(
            re.search(
                r"handle_inbound_message\(row\)\s*\n\s*self\.controller\.poll_outbound_once\(",
                source,
            )
        )

    def test_live_surfaces_do_not_teach_serial_reply_wait_semantics(self) -> None:
        patterns = (
            re.compile(r"poll_outbound_once\(wait_ms=.*reply_wait_ms"),
            re.compile(r"handle_inbound_message\(row\).*poll_outbound_once"),
            re.compile(r"waits? for the actor reply before", re.IGNORECASE),
            re.compile("serial " + "iMessage", re.IGNORECASE),
        )
        live_roots = [
            ROOT / "tools" / "launcher",
            ROOT / "tests",
        ]
        hits: list[str] = []
        for path in live_roots:
            files = [path] if path.is_file() else [row for row in path.rglob("*") if row.is_file()]
            for file_path in files:
                if "__pycache__" in file_path.parts:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if "re.compile" in line:
                        continue
                    for pattern in patterns:
                        if pattern.search(line):
                            hits.append(f"{file_path.relative_to(ROOT)}:{line_number}: {line.strip()}")
        self.assertEqual(hits, [])

def _create_chat_db(path: Path, *, chat_id: int) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                guid TEXT,
                text TEXT,
                error INTEGER,
                is_sent INTEGER,
                is_delivered INTEGER,
                is_finished INTEGER,
                is_from_me INTEGER
            );
            CREATE TABLE chat (
                ROWID INTEGER PRIMARY KEY,
                chat_identifier TEXT,
                guid TEXT
            );
            CREATE TABLE chat_message_join (
                chat_id INTEGER,
                message_id INTEGER
            );
            """
        )
        db.execute("INSERT INTO chat (ROWID, chat_identifier, guid) VALUES (?, ?, ?)", (chat_id, "chat@example.com", "chat-guid"))
        db.execute(
            "INSERT INTO message (ROWID, guid, text, error, is_sent, is_delivered, is_finished, is_from_me) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "old-guid", "old", 0, 1, 1, 1, 1),
        )
        db.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)", (chat_id, 1))


def _insert_outbound_message(
    path: Path,
    *,
    rowid: int,
    chat_id: int,
    error_code: int,
    is_sent: int,
    is_finished: int,
) -> None:
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO message (ROWID, guid, text, error, is_sent, is_delivered, is_finished, is_from_me) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rowid, f"guid-{rowid}", None, error_code, is_sent, 0, is_finished, 1),
        )
        db.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)", (chat_id, rowid))


def _update_message_send_state(
    path: Path,
    *,
    rowid: int,
    error_code: int,
    is_sent: int,
    is_delivered: int,
    is_finished: int,
) -> None:
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE message SET error = ?, is_sent = ?, is_delivered = ?, is_finished = ? WHERE ROWID = ?",
            (error_code, is_sent, is_delivered, is_finished, rowid),
        )


if __name__ == "__main__":
    unittest.main()
