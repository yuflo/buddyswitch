#!/usr/bin/env python3
"""iMessage bridge adapter tests."""

from __future__ import annotations

import os
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from tools.launcher import imessage_bridge  # noqa: E402


class _FakeBuddySwitchImApi:
    def __init__(self, *, actors: list[dict[str, Any]] | None = None) -> None:
        self.actors = actors if actors is not None else [_actor("act-market-demo")]
        self.created: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.messages: dict[str, dict[str, Any]] = {}

    def create_connection(self, *, display_name: str) -> dict[str, Any]:
        self.created.append({"display_name": display_name})
        return {"ok": True, "connection_key": "imck-fake"}

    def list_actors(self, *, connection_key: str) -> dict[str, Any]:
        return {"ok": True, "actors": list(self.actors), "count": len(self.actors)}

    def send_message(
        self,
        *,
        connection_key: str,
        target_identity_id: str,
        content: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        message_id = f"msg-in-{len(self.sent) + 1}"
        self.sent.append(
            {
                "connection_key": connection_key,
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
            "delivery_status": "accepted",
            "wake_status": "submitted",
        }

    def read_events(self, *, connection_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        return {"ok": True, "events": list(self.events)}

    def get_message(self, *, connection_key: str, message_id: str) -> dict[str, Any]:
        return {"ok": True, "message": dict(self.messages[message_id])}


class _DelayedReplyApi(_FakeBuddySwitchImApi):
    def __init__(self) -> None:
        super().__init__()
        self.read_wait_ms: list[int] = []
        self.messages["msg-reply-1"] = {"id": "msg-reply-1", "content": "pong", "reply_to": "msg-in-1"}

    def read_events(self, *, connection_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        self.read_wait_ms.append(wait_ms)
        if wait_ms <= 0:
            return {"ok": True, "events": []}
        return {
            "ok": True,
            "events": [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "msg-in-1",
                }
            ],
        }


class _FakeImsg:
    def __init__(self) -> None:
        self.status_calls = 0
        self.sent: list[dict[str, Any]] = []

    def status(self) -> None:
        self.status_calls += 1

    def send(self, *, route: dict[str, Any], text: str) -> None:
        self.sent.append({"route": dict(route), "text": text})


class _FakeHttpResponse:
    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok":true,"events":[]}'


class _RecordingOpener:
    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def open(self, _req: object, *, timeout: float) -> _FakeHttpResponse:
        self.timeouts.append(timeout)
        return _FakeHttpResponse()


class _WatchOnceImsg(_FakeImsg):
    def watch_messages(self) -> Any:
        yield {
            "rowid": 21,
            "guid": "guid-21",
            "chat_id": 8,
            "is_from_me": False,
            "sender": "+15551234567",
            "text": "please reply",
        }


def _actor(identity_id: str, *, status: str = "online") -> dict[str, Any]:
    return {
        "identity": {"id": identity_id, "type": "actor"},
        "identity_id": identity_id,
        "role_id": "market",
        "reachability_status": status,
    }


def _bridge(
    temp_root: Path,
    *,
    api: _FakeBuddySwitchImApi | None = None,
    imsg: _FakeImsg | None = None,
    allow_senders: tuple[str, ...] = ("+15551234567",),
) -> tuple[imessage_bridge.ImessageBridge, _FakeBuddySwitchImApi, _FakeImsg]:
    api = api or _FakeBuddySwitchImApi()
    imsg = imsg or _FakeImsg()
    config = imessage_bridge.BridgeConfig(
        server="http://127.0.0.1:8765",
        target_identity_id="act-market-demo",
        allow_senders=allow_senders,
        state_path=temp_root / "imessage-state.json",
    )
    return imessage_bridge.ImessageBridge(config=config, api=api, imsg=imsg), api, imsg


class ImessageBridgeTests(unittest.TestCase):
    def test_api_client_bypasses_environment_proxy_for_local_server(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true,"connection_key":"imck-local"}')

            def log_message(self, _format: str, *_args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        proxy_vars = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy")
        previous_proxy_env = {name: os.environ.get(name) for name in proxy_vars}
        try:
            thread.start()
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:1"
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:1"
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
            os.environ.pop("NO_PROXY", None)
            os.environ.pop("no_proxy", None)

            api = imessage_bridge.BuddySwitchImApi(f"http://127.0.0.1:{server.server_port}")
            result = api.create_connection(display_name="Bridge")
        finally:
            for name, value in previous_proxy_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            server.shutdown()
            server.server_close()

        self.assertEqual(result["connection_key"], "imck-local")

    def test_events_request_timeout_exceeds_long_poll_wait_window(self) -> None:
        opener = _RecordingOpener()
        original_build_opener = imessage_bridge.request.build_opener
        try:
            imessage_bridge.request.build_opener = lambda *_args, **_kwargs: opener  # type: ignore[method-assign]
            api = imessage_bridge.BuddySwitchImApi("http://127.0.0.1:8765")
            result = api.read_events(connection_key="imck-local", limit=50, wait_ms=30000)
        finally:
            imessage_bridge.request.build_opener = original_build_opener  # type: ignore[method-assign]

        self.assertTrue(result["ok"])
        self.assertEqual(len(opener.timeouts), 1)
        self.assertGreater(opener.timeouts[0], 30)

    def test_bridge_fails_fast_when_target_actor_is_not_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bridge, _api, _imsg = _bridge(Path(temp_root), api=_FakeBuddySwitchImApi(actors=[]))

            with self.assertRaises(imessage_bridge.BridgeError) as raised:
                bridge.ensure_ready()

        self.assertIn("target actor is not reachable", str(raised.exception))

    def test_inbound_ignores_messages_from_me(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bridge, api, _imsg = _bridge(Path(temp_root))
            bridge.ensure_ready()

            result = bridge.handle_inbound_message(
                {"rowid": 1, "guid": "guid-1", "is_from_me": True, "sender": "+15551234567", "text": "hello"}
            )

        self.assertEqual(result["status"], "ignored_from_me")
        self.assertEqual(api.sent, [])

    def test_inbound_rejects_sender_not_in_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bridge, api, _imsg = _bridge(Path(temp_root), allow_senders=("+15551234567",))
            bridge.ensure_ready()

            result = bridge.handle_inbound_message(
                {"rowid": 1, "guid": "guid-1", "is_from_me": False, "sender": "+15550000000", "text": "hello"}
            )

        self.assertEqual(result["status"], "ignored_sender")
        self.assertEqual(api.sent, [])

    def test_inbound_dedupes_by_rowid_or_guid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bridge, api, _imsg = _bridge(Path(temp_root))
            bridge.ensure_ready()
            row = {
                "rowid": 9,
                "guid": "guid-9",
                "chat_id": 4,
                "is_from_me": False,
                "sender": "+15551234567",
                "text": "hello",
            }

            first = bridge.handle_inbound_message(dict(row))
            second = bridge.handle_inbound_message(dict(row))

        self.assertEqual(first["status"], "delivered")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(len(api.sent), 1)

    def test_inbound_posts_allowlisted_text_to_api_im_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bridge, api, _imsg = _bridge(Path(temp_root))
            bridge.ensure_ready()

            result = bridge.handle_inbound_message(
                {
                    "rowid": 10,
                    "guid": "guid-10",
                    "chat_id": 5,
                    "is_from_me": False,
                    "sender": "+15551234567",
                    "text": "ping from phone",
                }
            )

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(api.sent[0]["connection_key"], "imck-fake")
        self.assertEqual(api.sent[0]["target_identity_id"], "act-market-demo")
        self.assertEqual(api.sent[0]["content"], "ping from phone")

    def test_outbound_sends_actor_reply_once_and_records_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            bridge, api, imsg = _bridge(Path(temp_root))
            bridge.ensure_ready()
            inbound = bridge.handle_inbound_message(
                {
                    "rowid": 11,
                    "guid": "guid-11",
                    "chat_id": 6,
                    "is_from_me": False,
                    "sender": "+15551234567",
                    "text": "ping",
                }
            )
            self.assertEqual(inbound["status"], "delivered")
            api.events = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "msg-in-1",
                    "from_identity_id": "act-market-demo",
                    "to_identity_id": "ext-fake",
                }
            ]
            api.messages["msg-reply-1"] = {"id": "msg-reply-1", "content": "pong", "reply_to": "msg-in-1"}

            first = bridge.poll_outbound_once(wait_ms=0)
            second = bridge.poll_outbound_once(wait_ms=0)

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(imsg.sent, [{"route": {"chat_id": "6", "sender": "+15551234567"}, "text": "pong"}])

    def test_run_forever_waits_for_async_actor_reply_after_inbound(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _DelayedReplyApi()
            imsg = _WatchOnceImsg()
            bridge, _api, _imsg = _bridge(Path(temp_root), api=api, imsg=imsg)

            bridge.run_forever()

        self.assertEqual(api.read_wait_ms, [30000])
        self.assertEqual(imsg.sent, [{"route": {"chat_id": "8", "sender": "+15551234567"}, "text": "pong"}])

    def test_restart_does_not_resend_recorded_outbound_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            first_bridge, api, first_imsg = _bridge(root)
            first_bridge.ensure_ready()
            first_bridge.handle_inbound_message(
                {
                    "rowid": 12,
                    "guid": "guid-12",
                    "chat_id": 7,
                    "is_from_me": False,
                    "sender": "+15551234567",
                    "text": "ping",
                }
            )
            api.events = [{"event_id": "imev-reply-2", "message_id": "msg-reply-2", "reply_to": "msg-in-1"}]
            api.messages["msg-reply-2"] = {"id": "msg-reply-2", "content": "pong", "reply_to": "msg-in-1"}
            first_bridge.poll_outbound_once(wait_ms=0)

            second_imsg = _FakeImsg()
            second_bridge, _same_api, _imsg = _bridge(root, api=api, imsg=second_imsg)
            second_bridge.ensure_ready()
            result = second_bridge.poll_outbound_once(wait_ms=0)

        self.assertEqual(first_imsg.sent, [{"route": {"chat_id": "7", "sender": "+15551234567"}, "text": "pong"}])
        self.assertEqual(result["sent"], 0)
        self.assertEqual(second_imsg.sent, [])

    def test_bridge_source_does_not_import_central_im_internals(self) -> None:
        source = (ROOT / "tools" / "launcher" / "imessage_bridge.py").read_text(encoding="utf-8")

        self.assertNotIn("env.services.messages", source)
        self.assertNotIn("env.repos.messages", source)
        self.assertNotIn("send_im_message", source)
        self.assertNotIn("send_external_connection_message", source)
        self.assertNotIn("read_external_connection_events", source)


if __name__ == "__main__":
    unittest.main()
