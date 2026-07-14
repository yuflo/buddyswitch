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


class _UnavailableImsg(_QueueImsg):
    def __init__(self) -> None:
        super().__init__()
        self.status_calls = 0

    def status(self) -> None:
        self.status_calls += 1
        raise imessage_channel.ChannelError("imsg unavailable")


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


def _schema_v4_state() -> dict[str, Any]:
    return {
        "schema_version": 4,
        "contacts": {
            "sender:user-a@example.com": {
                "external_session_key": "imsk-existing",
                "external_identity_id": "ext-existing",
                "route": {"chat_id": "9", "sender": "user-a@example.com"},
                "active_identity_id": "act-market-demo",
                "active_identity_expires_at": "2026-07-10T12:30:00Z",
                "pending_actor_choices": {"1": "act-market-demo"},
                "pending_actor_choices_expires_at": "2026-07-10T12:05:00Z",
                "seen_inbound_keys": ["guid:seen"],
                "sent_outbound_event_ids": ["imev-sent"],
            }
        },
    }
