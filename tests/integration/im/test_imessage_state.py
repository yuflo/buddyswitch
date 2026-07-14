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

class ImessageStateTests(unittest.TestCase):
    def test_default_state_path_uses_imessage_channel_schema_v5(self) -> None:
        config = imessage_channel.ChannelConfig(server="http://127.0.0.1:8765")
        self.assertEqual(config.effective_state_path().parts[-2:], ("imessage-channel", "state.json"))

        with tempfile.TemporaryDirectory() as temp_root:
            store = imessage_channel.ImessageChannelStateStore(Path(temp_root) / "state.json")
            self.assertEqual(store.load(), {"schema_version": 5, "contacts": {}})

    def test_schema_v4_state_migrates_binding_and_clears_unconfirmed_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            state_path.write_text(json.dumps(_schema_v4_state()), encoding="utf-8")
            store = imessage_channel.ImessageChannelStateStore(state_path)

            try:
                migrated = store.load()
            except imessage_channel.ChannelError as exc:
                self.fail(f"schema v4 state was not migrated: {exc}")
            saved = json.loads(state_path.read_text(encoding="utf-8"))

        contact = migrated["contacts"]["sender:user-a@example.com"]
        self.assertEqual(migrated, saved)
        self.assertEqual(migrated["schema_version"], 5)
        self.assertEqual(contact["external_session_key"], "imsk-existing")
        self.assertEqual(contact["external_identity_id"], "ext-existing")
        self.assertEqual(contact["route"], {"chat_id": "9", "sender": "user-a@example.com"})
        self.assertEqual(contact["seen_inbound_keys"], ["guid:seen"])
        self.assertEqual(contact["sent_outbound_event_ids"], ["imev-sent"])
        self.assertEqual(contact["pending_actor_choices"], {})
        self.assertNotIn("active_identity_id", contact)
        self.assertNotIn("active_identity_expires_at", contact)
        self.assertNotIn("pending_actor_choices_expires_at", contact)
        self.assertNotIn("control_delivery", contact)

    def test_state_save_uses_runtime_atomic_json_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            store = imessage_channel.ImessageChannelStateStore(state_path)

            with mock.patch.object(
                imessage_channel.runtime_files,
                "write_json_object",
                wraps=imessage_channel.runtime_files.write_json_object,
            ) as atomic_write:
                store.save({"schema_version": 5, "contacts": {}})

        atomic_write.assert_called_once_with(state_path, {"schema_version": 5, "contacts": {}})

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
                store.save({"schema_version": 5, "contacts": {}})

    def test_worker_rejects_unsupported_state_before_starting_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state_path = Path(temp_root) / "state.json"
            state_path.write_text(json.dumps({"schema_version": 3, "contacts": {}}), encoding="utf-8")
            imsg = _QueueImsg()
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
            self.addCleanup(worker.stop)

            with mock.patch("sys.stderr"), self.assertRaisesRegex(
                imessage_channel.ChannelError,
                "schema is retired",
            ):
                worker.start()

            self.assertEqual(worker._threads, [])
            self.assertFalse(imsg.watch_started.is_set())

    def test_worker_rejects_unavailable_imsg_before_starting_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            imsg = _UnavailableImsg()
            controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg)
            worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
            self.addCleanup(worker.stop)

            with mock.patch("sys.stderr"), self.assertRaisesRegex(
                imessage_channel.ChannelError,
                "imsg unavailable",
            ):
                worker.start()

            self.assertEqual(imsg.status_calls, 1)
            self.assertEqual(worker._threads, [])
            self.assertFalse(imsg.watch_started.is_set())

    def test_worker_start_migrates_schema_v4_from_default_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            local_root = Path(temp_root) / "buddyswitch" / "local"
            state_path = local_root / "imessage-channel" / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps(_schema_v4_state()), encoding="utf-8")
            imsg = _QueueImsg()

            with mock.patch.object(imessage_channel.runtime_files, "LOCAL_ROOT", local_root):
                config = imessage_channel.ChannelConfig(server="http://127.0.0.1:8765")
                controller = imessage_channel.ImessageChannelController(
                    config=config,
                    api=_FakeBuddySwitchImApi(),
                    imsg=imsg,
                )
                worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
                self.addCleanup(worker.stop)
                with mock.patch("sys.stderr"):
                    worker.start()
                    saved = json.loads(state_path.read_text(encoding="utf-8"))
                    worker.stop()

        contact = saved["contacts"]["sender:user-a@example.com"]
        self.assertEqual(saved["schema_version"], 5)
        self.assertEqual(contact["external_session_key"], "imsk-existing")
        self.assertEqual(contact["external_identity_id"], "ext-existing")
        self.assertEqual(contact["pending_actor_choices"], {})
        self.assertNotIn("active_identity_id", contact)
