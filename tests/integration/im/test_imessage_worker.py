"""iMessage worker concurrency and lifecycle contracts."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.support.cli import wait_until
from buddyswitch.launcher import imessage_channel

from tests.integration.im._imessage_fakes import (
    _BlockingActorSendApi,
    _ControlledBlockingReadApi,
    _ControlledSendImsg,
    _FakeBuddySwitchImApi,
    _LateReplyApi,
    _QueueImsg,
    _actor_reply_identity,
    _controller,
    _row,
)


def _bound_contacts_state(count: int) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    contacts: dict[str, dict[str, Any]] = {}
    bindings: list[tuple[str, str]] = []
    for index in range(count):
        sender_key = f"sender:user-{index:02d}@example.com"
        external_session_key = f"imsk-{index + 1}"
        contacts[sender_key] = {
            "external_session_key": external_session_key,
            "external_identity_id": f"ext-fake-{index + 1}",
            "route": {"chat_id": str(index + 1), "sender": f"user-{index:02d}@example.com"},
            "seen_inbound_keys": [],
            "message_links": {},
        }
        bindings.append((sender_key, external_session_key))
    return {"schema_version": imessage_channel.SCHEMA_VERSION, "contacts": contacts}, bindings


def _add_outbound_event(
    api: _FakeBuddySwitchImApi,
    *,
    external_session_key: str,
    suffix: str,
    content: str,
) -> None:
    event_id = f"imev-{suffix}"
    message_id = f"msg-{suffix}"
    api.events_by_key.setdefault(external_session_key, []).append(
        {
            "event_id": event_id,
            "message_id": message_id,
            **_actor_reply_identity(),
        }
    )
    api.messages[message_id] = {
        "id": message_id,
        "content": content,
        **_actor_reply_identity(),
    }


class ImessageWorkerTests(unittest.TestCase):
    def test_start_failure_does_not_create_threads_or_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, _api, _imsg = _controller(Path(temp_root))
            with mock.patch.object(controller, "prepare", side_effect=imessage_channel.ChannelError("not ready")):
                worker = imessage_channel.ImessageChannelWorker(controller)
                with self.assertRaisesRegex(imessage_channel.ChannelError, "not ready"):
                    worker.start()

        self.assertEqual(worker._threads, [])
        self.assertIsNone(worker._outbound_executor)
        self.assertEqual(worker._in_flight_contact_keys, set())

    def test_second_thread_start_failure_cleans_first_thread_and_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(controller)
            self.addCleanup(worker.stop)
            original_start = threading.Thread.start
            start_calls = 0

            def fail_second_start(thread: threading.Thread) -> None:
                nonlocal start_calls
                start_calls += 1
                if start_calls == 2:
                    raise RuntimeError("second thread did not start")
                original_start(thread)

            with mock.patch.object(threading.Thread, "start", new=fail_second_start):
                with self.assertRaisesRegex(RuntimeError, "second thread did not start"):
                    worker.start()

        self.assertEqual(worker._threads, [])
        self.assertIsNone(worker._outbound_executor)
        self.assertEqual(worker._in_flight_contact_keys, set())
        self.assertTrue(imsg.stopped)

    def test_configured_worker_count_is_hard_capped_at_four(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg(blocked_chat_ids={"1", "2", "3", "4", "5"})
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(5)
            controller.state_store.save(state)
            for index, (_sender_key, external_session_key) in enumerate(bindings):
                _add_outbound_event(
                    api,
                    external_session_key=external_session_key,
                    suffix=f"hard-cap-{index}",
                    content=f"hard cap {index}",
                )
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=99,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)
            self.addCleanup(imsg.release_all)

            self.assertTrue(wait_until(lambda: imsg.active_sends >= 4, timeout=1))
            self.assertEqual(worker.max_outbound_workers, 4)
            self.assertEqual(imsg.active_sends, 4)
            self.assertEqual(len(imsg.started_sends), 4)
            imsg.release_all()
            worker.stop()

    def test_unexpected_delivery_exception_releases_contact_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, _api, _imsg = _controller(Path(temp_root))
            state, bindings = _bound_contacts_state(1)
            controller.state_store.save(state)
            attempts = 0

            def fail_delivery(*, sender_key: str) -> dict[str, Any]:
                nonlocal attempts
                attempts += 1
                raise RuntimeError(f"boom for {sender_key}")

            with mock.patch.object(controller, "deliver_outbound_contact_once", side_effect=fail_delivery):
                worker = imessage_channel.ImessageChannelWorker(
                    controller,
                    max_outbound_workers=1,
                    outbound_scan_interval_seconds=0.001,
                )
                with mock.patch("sys.stderr"):
                    worker.start()
                    self.addCleanup(worker.stop)
                    self.assertTrue(wait_until(lambda: attempts >= 2, timeout=1))
                    self.assertTrue(
                        wait_until(lambda: bindings[0][0] not in worker._in_flight_contact_keys, timeout=1),
                        "failed delivery kept the contact permanently reserved",
                    )
                    worker.stop()

    def test_blocked_inbound_api_for_contact_a_does_not_block_outbound_contact_b(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _BlockingActorSendApi(blocked_external_session_key="imsk-1")
            imsg = _ControlledSendImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(2)
            controller.state_store.save(state)
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=2,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)
            self.addCleanup(api.release_actor_send.set)

            imsg.push(
                _row(
                    sender="user-00@example.com",
                    text="@act-market-demo hold A",
                    guid="guid-block-a",
                    chat_id="1",
                )
            )
            self.assertTrue(api.actor_send_started.wait(timeout=1), "contact A did not enter blocked HTTP send")
            _add_outbound_event(
                api,
                external_session_key=bindings[1][1],
                suffix="ready-b-during-inbound",
                content="ready B during inbound",
            )

            self.assertTrue(
                wait_until(
                    lambda: any(row["text"].endswith("ready B during inbound") for row in imsg.sent),
                    timeout=0.25,
                ),
                "contact B outbound delivery was blocked by contact A inbound HTTP work",
            )
            api.release_actor_send.set()
            worker.stop()

    def test_silent_contact_does_not_delay_ready_contact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(2)
            controller.state_store.save(state)
            _add_outbound_event(
                api,
                external_session_key=bindings[1][1],
                suffix="ready-b",
                content="ready B",
            )
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=1,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)

            self.assertTrue(
                wait_until(lambda: any(row["text"].endswith("ready B") for row in imsg.sent), timeout=1),
                "ready contact was not reached after a silent contact",
            )
            worker.stop()

    def test_blocked_contact_send_does_not_block_other_contact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg(blocked_chat_ids={"1"})
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(2)
            controller.state_store.save(state)
            _add_outbound_event(api, external_session_key=bindings[0][1], suffix="blocked-a", content="blocked A")
            _add_outbound_event(api, external_session_key=bindings[1][1], suffix="ready-b", content="ready B")
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=2,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)
            self.addCleanup(imsg.release_all)

            self.assertTrue(imsg.send_started_by_chat_id.setdefault("1", threading.Event()).wait(timeout=1))
            self.assertTrue(
                wait_until(lambda: any(row["text"].endswith("ready B") for row in imsg.sent), timeout=1),
                "contact B was blocked behind contact A's iMessage send",
            )
            imsg.release_all()
            worker.stop()

    def test_retry_failure_does_not_block_other_contact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg()
            controller, _api, _imsg = _controller(
                Path(temp_root),
                api=api,
                imsg=imsg,
                clock=lambda: 1_000.0,
            )
            state, bindings = _bound_contacts_state(2)
            state["contacts"][bindings[0][0]]["outbound_retry"] = {
                "event_id": "imev-retry-a",
                "message_id": "msg-retry-a",
                "first_failed_at": 1_000.0,
                "next_attempt_at": 1_030.0,
                "attempts": 1,
                "last_error": "imessage_send_failed",
            }
            controller.state_store.save(state)
            _add_outbound_event(
                api,
                external_session_key=bindings[1][1],
                suffix="ready-b-during-retry",
                content="ready B during retry",
            )
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=1,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)

            self.assertTrue(
                wait_until(
                    lambda: any(row["text"].endswith("ready B during retry") for row in imsg.sent),
                    timeout=1,
                ),
                "contact B was blocked by contact A's retry delay",
            )
            self.assertNotIn(bindings[0][0], controller.outbound_contact_keys())
            worker.stop()

    def test_same_contact_never_has_two_events_in_flight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg(blocked_chat_ids={"1"})
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(1)
            controller.state_store.save(state)
            _add_outbound_event(api, external_session_key=bindings[0][1], suffix="fifo-1", content="first")
            _add_outbound_event(api, external_session_key=bindings[0][1], suffix="fifo-2", content="second")
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=4,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)
            self.addCleanup(imsg.release_all)

            self.assertTrue(imsg.send_started_by_chat_id.setdefault("1", threading.Event()).wait(timeout=1))
            self.assertFalse(
                wait_until(lambda: len(imsg.started_sends) > 1, timeout=0.1),
                "second event for the same contact started before the first completed",
            )
            imsg.release_all()
            self.assertTrue(wait_until(lambda: len(imsg.sent) == 2, timeout=1))
            self.assertEqual([row["text"].rsplit("\n", 1)[-1] for row in imsg.sent], ["first", "second"])
            worker.stop()

    def test_outbound_scheduler_never_exceeds_four_active_sends(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg(blocked_chat_ids={"1", "2", "3", "4", "5"})
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(5)
            controller.state_store.save(state)
            for index, (_sender_key, external_session_key) in enumerate(bindings):
                _add_outbound_event(
                    api,
                    external_session_key=external_session_key,
                    suffix=f"bounded-{index}",
                    content=f"bounded {index}",
                )
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=4,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)
            self.addCleanup(imsg.release_all)

            self.assertTrue(wait_until(lambda: imsg.active_sends == 4, timeout=1))
            self.assertEqual(imsg.max_active_sends, 4)
            self.assertEqual(len(imsg.started_sends), 4)
            imsg.release_by_chat_id["1"].set()
            self.assertTrue(wait_until(lambda: len(imsg.started_sends) == 5, timeout=1))
            self.assertLessEqual(imsg.max_active_sends, 4)
            imsg.release_all()
            worker.stop()

    def test_round_robin_reaches_contacts_after_the_first_four(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi()
            imsg = _ControlledSendImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            state, bindings = _bound_contacts_state(8)
            controller.state_store.save(state)
            _add_outbound_event(
                api,
                external_session_key=bindings[-1][1],
                suffix="tail",
                content="tail contact",
            )
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=4,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()
            self.addCleanup(worker.stop)

            self.assertTrue(
                wait_until(lambda: any(row["text"].endswith("tail contact") for row in imsg.sent), timeout=1),
                "round-robin scheduler starved a tail contact",
            )
            worker.stop()

    def test_worker_processes_actors_while_outbound_poll_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            api = _ControlledBlockingReadApi(blocked_external_session_keys={"imsk-1"})
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="seed route", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=1,
                outbound_scan_interval_seconds=0.001,
            )
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
            api = _ControlledBlockingReadApi(blocked_external_session_keys={"imsk-1"})
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
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=1,
                outbound_scan_interval_seconds=0.001,
            )
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
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                outbound_scan_interval_seconds=0.001,
            )
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
            api = _ControlledBlockingReadApi(blocked_external_session_keys={"imsk-1"})
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
            controller.handle_inbound_message(_row(text="seed route", guid="guid-seed", chat_id="9"))
            imsg.sent.clear()
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                max_outbound_workers=1,
                outbound_scan_interval_seconds=0.001,
            )
            worker.start()

            self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
            self.assertTrue(api.read_started.wait(timeout=1), "outbound read did not start")
            api.release_read.set()
            worker.stop()

        self.assertTrue(imsg.stopped)
        self.assertTrue(all(not thread.is_alive() for thread in worker._threads))
        self.assertIsNone(worker._outbound_executor)
        self.assertEqual(worker._in_flight_contact_keys, set())
