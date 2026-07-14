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
        db.execute(
            "INSERT INTO chat (ROWID, chat_identifier, guid) VALUES (?, ?, ?)",
            (chat_id, "chat@example.com", "chat-guid"),
        )
        db.execute(
            "INSERT INTO message (ROWID, guid, text, error, is_sent, is_delivered, is_finished, is_from_me) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "old-guid", "old", 0, 1, 1, 1, 1),
        )
        db.execute(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            (chat_id, 1),
        )


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
            "INSERT INTO message (ROWID, guid, text, error, is_sent, is_delivered, is_finished, is_from_me) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rowid, f"guid-{rowid}", None, error_code, is_sent, 0, is_finished, 1),
        )
        db.execute(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            (chat_id, rowid),
        )


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


class CommandImsgClientTests(unittest.TestCase):
    def test_status_uses_bounded_timeout_and_wraps_expiry(self) -> None:
        calls: list[dict[str, Any]] = []

        def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append({"command": command, **kwargs})
            raise subprocess.TimeoutExpired(command, timeout=kwargs.get("timeout"))

        client = imessage_channel.CommandImsgClient(imsg_bin="imsg", subprocess_run=fake_run)

        try:
            with self.assertRaisesRegex(imessage_channel.ChannelError, "iMessage status check timed out"):
                client.status()
        except subprocess.TimeoutExpired as exc:
            self.fail(f"status timeout was not wrapped as ChannelError: {exc}")

        self.assertEqual(calls[0]["command"], ["imsg", "status"])
        self.assertEqual(calls[0]["timeout"], imessage_channel.IMSG_STATUS_TIMEOUT_SECONDS)

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
