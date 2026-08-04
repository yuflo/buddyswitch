"""iMessage channel product-logic tests."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
from pathlib import Path
from typing import Any, Callable

from buddyswitch.modules.communication.private.adapters.web import (
    imessage_channel,
)  # noqa: E402


@dataclass(frozen=True)
class _FakeSendReceipt:
    guid: str


class _FakeBuddySwitchImApi:
    def __init__(self, *, actors: list[dict[str, Any]] | None = None) -> None:
        self.actors = actors if actors is not None else [_actor("market", "act-market-demo")]
        self.created: list[dict[str, Any]] = []
        self.sent_to_actor: list[dict[str, Any]] = []
        self.replies: list[dict[str, Any]] = []
        self.reply_results: list[dict[str, Any]] = []
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

    def send_to_actor(
        self,
        *,
        external_session_key: str,
        target_identity_id: str,
        content: str,
    ) -> dict[str, Any]:
        message_id = f"msg-in-{len(self.sent_to_actor) + 1}"
        self.sent_to_actor.append(
            {
                "external_session_key": external_session_key,
                "target_identity_id": target_identity_id,
                "content": content,
                "message_id": message_id,
            }
        )
        return {
            "ok": True,
            "message": {"id": message_id, "conversation_id": "conv-fake", "reply_to": None},
            "event_id": f"imev-in-{len(self.sent_to_actor)}",
        }

    def reply_to_message(
        self,
        *,
        external_session_key: str,
        reply_to: str,
        content: str,
    ) -> dict[str, Any]:
        self.replies.append(
            {
                "external_session_key": external_session_key,
                "reply_to": reply_to,
                "content": content,
            }
        )
        if self.reply_results:
            return self.reply_results.pop(0)
        return {
            "ok": True,
            "message": {
                "id": f"msg-reply-{len(self.replies)}",
                "conversation_id": "conv-fake",
                "reply_to": reply_to,
            },
            "event_id": f"imev-reply-{len(self.replies)}",
        }

    def read_events(self, *, external_session_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        acked_ids = {row["event_id"] for row in self.acked if row["external_session_key"] == external_session_key}
        available = [
            dict(row)
            for row in self.events_by_key.get(external_session_key, [])
            if str(row.get("event_id") or "") not in acked_ids
        ]
        return {
            "ok": True,
            "events": available[:limit],
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


class _ControlledBlockingReadApi(_FakeBuddySwitchImApi):
    def __init__(self, *, blocked_external_session_keys: set[str]) -> None:
        super().__init__()
        self.blocked_external_session_keys = set(blocked_external_session_keys)
        self.read_started = threading.Event()
        self.release_read = threading.Event()

    def read_events(self, *, external_session_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        if external_session_key in self.blocked_external_session_keys:
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


class _BlockingActorSendApi(_FakeBuddySwitchImApi):
    def __init__(self, *, blocked_external_session_key: str) -> None:
        super().__init__()
        self.blocked_external_session_key = blocked_external_session_key
        self.actor_send_started = threading.Event()
        self.release_actor_send = threading.Event()

    def send_to_actor(
        self,
        *,
        external_session_key: str,
        target_identity_id: str,
        content: str,
    ) -> dict[str, Any]:
        if external_session_key == self.blocked_external_session_key:
            self.actor_send_started.set()
            self.release_actor_send.wait(timeout=2)
        return super().send_to_actor(
            external_session_key=external_session_key,
            target_identity_id=target_identity_id,
            content=content,
        )


class _FakeImsg:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.stopped = False

    def status(self) -> None:
        return None

    def send(self, *, route: dict[str, Any], text: str) -> _FakeSendReceipt:
        self.sent.append({"route": dict(route), "text": text})
        return _FakeSendReceipt(guid=f"out-guid-{len(self.sent)}")

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


class _ControlledSendImsg(_QueueImsg):
    def __init__(self, *, blocked_chat_ids: set[str] | None = None) -> None:
        super().__init__()
        self.blocked_chat_ids = set(blocked_chat_ids or set())
        self.release_by_chat_id = {
            chat_id: threading.Event() for chat_id in self.blocked_chat_ids
        }
        self.send_started_by_chat_id: dict[str, threading.Event] = {}
        self.started_sends: list[dict[str, Any]] = []
        self.active_sends = 0
        self.max_active_sends = 0
        self._send_lock = threading.Lock()

    def send(self, *, route: dict[str, Any], text: str) -> _FakeSendReceipt:
        chat_id = str(route.get("chat_id") or "")
        with self._send_lock:
            started = self.send_started_by_chat_id.setdefault(chat_id, threading.Event())
            self.started_sends.append({"route": dict(route), "text": text})
            self.active_sends += 1
            self.max_active_sends = max(self.max_active_sends, self.active_sends)
        started.set()
        try:
            release = self.release_by_chat_id.get(chat_id)
            if release is not None:
                release.wait(timeout=2)
            with self._send_lock:
                self.sent.append({"route": dict(route), "text": text})
                return _FakeSendReceipt(guid=f"out-guid-{len(self.sent)}")
        finally:
            with self._send_lock:
                self.active_sends -= 1

    def release_all(self) -> None:
        for release in self.release_by_chat_id.values():
            release.set()


class _UnavailableImsg(_QueueImsg):
    def __init__(self) -> None:
        super().__init__()
        self.status_calls = 0

    def status(self) -> None:
        self.status_calls += 1
        raise imessage_channel.ChannelError("imsg unavailable")


class _FailingImsg(_FakeImsg):
    def __init__(self, *, fail_on_call: int, error_message: str = "iMessage send status failed") -> None:
        super().__init__()
        self.fail_on_call = fail_on_call
        self.error_message = error_message

    def send(self, *, route: dict[str, Any], text: str) -> _FakeSendReceipt:
        self.sent.append({"route": dict(route), "text": text})
        if len(self.sent) < self.fail_on_call:
            return _FakeSendReceipt(guid=f"out-guid-{len(self.sent)}")
        raise imessage_channel.ChannelError(self.error_message)


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
    reply_to_guid: str | None = None,
    thread_originator_guid: str | None = None,
    reply_to_text: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "guid": guid,
        "chat_id": chat_id,
        "is_from_me": is_from_me,
        "sender": sender,
        "text": text,
    }
    if reply_to_guid is not None:
        row["reply_to_guid"] = reply_to_guid
    if thread_originator_guid is not None:
        row["thread_originator_guid"] = thread_originator_guid
    if reply_to_text is not None:
        row["reply_to_text"] = reply_to_text
    return row


def _controller(
    temp_root: Path,
    *,
    api: _FakeBuddySwitchImApi | None = None,
    imsg: _FakeImsg | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[imessage_channel.ImessageChannelController, _FakeBuddySwitchImApi, _FakeImsg]:
    api = api or _FakeBuddySwitchImApi()
    imsg = imsg or _FakeImsg()
    config = imessage_channel.ChannelConfig(
        server="http://127.0.0.1:8765",
        state_path=temp_root / "state.json",
    )
    return (
        imessage_channel.ImessageChannelController(
            config=config,
            api=api,
            imsg=imsg,
            clock=clock,
        ),
        api,
        imsg,
    )


def _current_state() -> dict[str, Any]:
    return {
        "schema_version": 6,
        "contacts": {
            "sender:user-a@example.com": {
                "external_session_key": "imsk-existing",
                "external_identity_id": "ext-existing",
                "route": {"chat_id": "9", "sender": "user-a@example.com"},
                "seen_inbound_keys": ["guid:seen"],
                "message_links": {
                    "ACTOR-BUBBLE-GUID": {
                        "message_id": "msg-actor-1",
                        "event_id": "imev-actor-1",
                    }
                },
            }
        },
    }
