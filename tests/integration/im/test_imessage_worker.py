"""iMessage worker concurrency and lifecycle contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.support.cli import wait_until
from tools.launcher import imessage_channel

from tests.integration.im._imessage_fakes import (
    _BlockingReadApi,
    _LateReplyApi,
    _QueueImsg,
    _actor_reply_identity,
    _controller,
    _row,
)


class ImessageWorkerTests(unittest.TestCase):
    def test_worker_processes_actors_while_outbound_poll_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingReadApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="seed route", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=30000)
            worker.start()
            self.addCleanup(api.release_read.set)
            self.addCleanup(worker.stop)

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")
            imsg.push(_row(text="/actors", guid="guid-actors", chat_id="9"))

            self.assertTrue(
                wait_until(lambda: any(row["text"] == "@act-market-demo (market)" for row in imsg.sent), timeout=1),
                "actor list was not sent while outbound read was blocked",
            )
            api.release_read.set()
            worker.stop()

        self.assertTrue(imsg.stopped)

    def test_worker_keeps_processing_after_direct_actors_response_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingReadApi()
            imsg = _QueueImsg()
            original_send = imsg.send
            failures = {"remaining": 1}

            def fail_first_send(*, route: dict[str, Any], text: str) -> Any:
                if failures["remaining"] > 0:
                    failures["remaining"] -= 1
                    imsg.sent.append({"route": dict(route), "text": text})
                    raise imessage_channel.ChannelError("AppleEvent timed out -1712")
                return original_send(route=route, text=text)

            imsg.send = fail_first_send  # type: ignore[method-assign]
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=30000)
            with mock.patch("sys.stderr"):
                worker.start()
                self.addCleanup(api.release_read.set)
                self.addCleanup(worker.stop)
                self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
                imsg.push(_row(text="/actors", guid="guid-actors-1", chat_id="9"))
                self.assertTrue(wait_until(lambda: len(imsg.sent) >= 1, timeout=1))
                imsg.push(_row(text="/actors", guid="guid-actors-2", chat_id="9"))
                self.assertTrue(
                    wait_until(
                        lambda: any(row["text"] == "@act-market-demo (market)" for row in imsg.sent[1:]),
                        timeout=1,
                    ),
                    "second actor list was not delivered after the first direct send failed",
                )
                api.release_read.set()
                worker.stop()

        self.assertTrue(imsg.stopped)
        self.assertEqual(
            [row["external_session_key"] for row in api.created],
            ["imsk-1"],
            "a failed direct response must not orphan the contact's external session",
        )

    def test_worker_delivers_late_actor_message_without_new_inbound_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _LateReplyApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="seed route", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
            worker.start()
            self.addCleanup(worker.stop)

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.first_read.wait(timeout=1), "first outbound poll did not happen")
            api.events_by_key["imsk-1"] = [
                {
                    "event_id": "imev-actor-1",
                    "message_id": "msg-actor-1",
                    **_actor_reply_identity(),
                }
            ]
            api.messages["msg-actor-1"] = {
                "id": "msg-actor-1",
                "content": "pong",
                **_actor_reply_identity(),
            }

            self.assertTrue(
                wait_until(
                    lambda: any(row["text"] == "[Message From act-market-demo]\n\npong" for row in imsg.sent),
                    timeout=1,
                ),
                "late actor message was not delivered",
            )
            worker.stop()

        self.assertTrue(imsg.stopped)

    def test_worker_stop_terminates_watch_and_outbound_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingReadApi()
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="seed route", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=30000)
            worker.start()

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")
            api.release_read.set()
            worker.stop()

        self.assertTrue(imsg.stopped)
        self.assertTrue(all(not thread.is_alive() for thread in worker._threads))
