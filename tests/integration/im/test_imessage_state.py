"""iMessage channel state and startup contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.launcher import imessage_channel

from tests.integration.im._imessage_fakes import (
    _QueueImsg,
    _UnavailableImsg,
    _controller,
    _current_state,
)


class ImessageStateTests(unittest.TestCase):
    def test_schema_6_state_without_retry_fields_normalizes_to_current_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            store = imessage_channel.ImessageChannelStateStore(state_path)
            store.save(
                {
                    "schema_version": imessage_channel.SCHEMA_VERSION,
                    "contacts": {
                        "sender:user@example.com": {
                            "external_session_key": "imsk-1",
                            "external_identity_id": "ext-1",
                            "route": {"chat_id": "9", "sender": "user@example.com"},
                            "seen_inbound_keys": [],
                            "message_links": {},
                        }
                    },
                }
            )

            contact = store.load()["contacts"]["sender:user@example.com"]

        self.assertIsNone(contact["outbound_retry"])
        self.assertIsNone(contact["last_delivery_failure"])

    def test_invalid_retry_payload_is_discarded_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            store = imessage_channel.ImessageChannelStateStore(state_path)
            store.save(
                {
                    "schema_version": imessage_channel.SCHEMA_VERSION,
                    "contacts": {
                        "sender:user@example.com": {
                            "external_session_key": "imsk-1",
                            "external_identity_id": "ext-1",
                            "route": {"chat_id": "9", "sender": "user@example.com"},
                            "seen_inbound_keys": [],
                            "message_links": {},
                            "outbound_retry": {
                                "event_id": "imev-1",
                                "message_id": "msg-1",
                                "first_failed_at": -1,
                                "next_attempt_at": 0,
                                "attempts": 0,
                                "last_error": "bad",
                            },
                        }
                    },
                }
            )

            contact = store.load()["contacts"]["sender:user@example.com"]

        self.assertIsNone(contact["outbound_retry"])

    def test_retry_with_unrecognized_error_detail_is_discarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": imessage_channel.SCHEMA_VERSION,
                        "contacts": {
                            "sender:user@example.com": {
                                "external_session_key": "imsk-1",
                                "external_identity_id": "ext-1",
                                "route": {"chat_id": "9", "sender": "user@example.com"},
                                "seen_inbound_keys": [],
                                "message_links": {},
                                "outbound_retry": {
                                    "event_id": "imev-1",
                                    "message_id": "msg-1",
                                    "first_failed_at": 1_000.0,
                                    "next_attempt_at": 1_001.0,
                                    "attempts": 1,
                                    "last_error": "user@example.com secret content",
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            contact = imessage_channel.ImessageChannelStateStore(state_path).load()["contacts"][
                "sender:user@example.com"
            ]

        self.assertIsNone(contact["outbound_retry"])
    def test_default_state_path_uses_current_imessage_channel_schema(self) -> None:
        config = imessage_channel.ChannelConfig(server="http://127.0.0.1:8765")
        self.assertEqual(config.effective_state_path().parts[-2:], ("imessage-channel", "state.json"))

        with tempfile.TemporaryDirectory() as temp_root:
            store = imessage_channel.ImessageChannelStateStore(Path(temp_root) / "state.json")
            self.assertEqual(store.load(), {"schema_version": 6, "contacts": {}})

    def test_schema_v5_state_is_rejected_without_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            state_path.write_text(json.dumps({"schema_version": 5, "contacts": {}}), encoding="utf-8")
            store = imessage_channel.ImessageChannelStateStore(state_path)

            with self.assertRaisesRegex(imessage_channel.ChannelStateError, "schema is retired"):
                store.load()

    def test_current_state_normalizes_only_current_contact_transport_fields(self) -> None:
        payload = _current_state()
        contact = payload["contacts"]["sender:user-a@example.com"]
        contact.update(
            {
                "active_identity_id": "act-retired",
                "pending_actor_choices": {"1": "act-retired"},
                "sent_outbound_event_ids": ["imev-retired"],
            }
        )
        contact["message_links"]["INVALID"] = {"message_id": "", "event_id": "imev-invalid"}

        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            normalized = imessage_channel.ImessageChannelStateStore(state_path).load()

        normalized_contact = normalized["contacts"]["sender:user-a@example.com"]
        self.assertEqual(
            normalized_contact,
            {
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
                "outbound_retry": None,
                "last_delivery_failure": None,
            },
        )

    def test_state_save_uses_runtime_atomic_json_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            store = imessage_channel.ImessageChannelStateStore(state_path)

            with mock.patch.object(
                imessage_channel.runtime_files,
                "write_json_object",
                wraps=imessage_channel.runtime_files.write_json_object,
            ) as atomic_write:
                store.save({"schema_version": 6, "contacts": {}})

        atomic_write.assert_called_once_with(state_path, {"schema_version": 6, "contacts": {}})

    def test_state_save_wraps_atomic_writer_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            store = imessage_channel.ImessageChannelStateStore(Path(temp_root) / "state.json")

            with mock.patch.object(
                imessage_channel.runtime_files,
                "write_json_object",
                side_effect=OSError("disk full"),
            ), self.assertRaisesRegex(
                imessage_channel.ChannelStateError,
                "failed to save iMessage channel state: disk full",
            ):
                store.save({"schema_version": 6, "contacts": {}})

    def test_worker_rejects_unsupported_state_before_starting_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            state_path.write_text(json.dumps({"schema_version": 5, "contacts": {}}), encoding="utf-8")
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                outbound_scan_interval_seconds=0.001,
            )
            self.addCleanup(worker.stop)

            with self.assertRaisesRegex(imessage_channel.ChannelError, "schema is retired"):
                worker.start()

            self.assertEqual(worker._threads, [])
            self.assertFalse(imsg.watch_started.is_set())

    def test_worker_rejects_unavailable_imsg_before_starting_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            imsg = _UnavailableImsg()
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(
                controller,
                outbound_scan_interval_seconds=0.001,
            )
            self.addCleanup(worker.stop)

            with self.assertRaisesRegex(imessage_channel.ChannelError, "imsg unavailable"):
                worker.start()

            self.assertEqual(imsg.status_calls, 1)
            self.assertEqual(worker._threads, [])
            self.assertFalse(imsg.watch_started.is_set())


class ImessageForwardResidueTests(unittest.TestCase):
    def test_channel_source_contains_no_retired_selection_or_parallel_delivery_state(self) -> None:
        source = Path(imessage_channel.__file__).read_text(encoding="utf-8")

        for retired in (
            "active_identity_id",
            "pending_actor_choices",
            "poll_control_delivery_once",
            "MIGRATABLE_STATE_VERSION",
            "_migrate_schema_v4_state",
            "sent_outbound_event_ids",
            "_is_numeric_choice",
            "DEFAULT_REPLY_WAIT_MS",
            "poll_outbound_once",
            "reply_wait_ms",
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, source)

        self.assertNotIn("reply_to_text", source)
