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

class ImessageWorkerTests(unittest.TestCase):
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
                wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
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
                wait_until(lambda: len(imsg.sent) >= 1, timeout=1),
                "first actor list send was not attempted",
            )
            imsg.send = original_send  # type: ignore[method-assign]
            imsg.push(_row(text="/actors", guid="guid-actors-2", chat_id="9"))
            self.assertTrue(
                wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
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
                wait_until(lambda: any(row["text"] == "[Message From act-market-demo]\n\npong" for row in imsg.sent), timeout=1),
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
                wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
                "initial actor list was not sent",
            )
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")

            imsg.push(_row(text="1", guid="guid-select", chat_id="9"))
            imsg.push(_row(text="ping", guid="guid-message", chat_id="9"))
            imsg.push(_row(text="/actors", guid="guid-actors-2", chat_id="9"))
            self.assertTrue(
                wait_until(
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
                wait_until(lambda: any(row["text"] == "[Message From act-market-demo]\n\npong" for row in imsg.sent), timeout=1),
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
