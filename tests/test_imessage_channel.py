#!/usr/bin/env python3
"""iMessage channel product-logic tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
import re
import sqlite3
import subprocess
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
        self.events_by_key: dict[str, list[dict[str, Any]]] = {}
        self.messages: dict[str, dict[str, Any]] = {}

    def create_connection(self, *, display_name: str) -> dict[str, Any]:
        connection_key = f"imck-{len(self.created) + 1}"
        self.created.append({"display_name": display_name, "connection_key": connection_key})
        return {"ok": True, "connection_key": connection_key}

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
        }

    def read_events(self, *, connection_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        return {"ok": True, "events": list(self.events_by_key.get(connection_key, []))}

    def get_message(self, *, connection_key: str, message_id: str) -> dict[str, Any]:
        return {"ok": True, "message": dict(self.messages[message_id])}


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


class _FailingImsg(_FakeImsg):
    def __init__(self, *, fail_on_call: int) -> None:
        super().__init__()
        self.fail_on_call = fail_on_call

    def send(self, *, route: dict[str, Any], text: str) -> None:
        self.sent.append({"route": dict(route), "text": text})
        if len(self.sent) < self.fail_on_call:
            return
        raise imessage_channel.ChannelError("iMessage send status failed")


def _actor(role_id: str, identity_id: str, *, status: str = "online") -> dict[str, Any]:
    return {
        "identity": {"id": identity_id, "type": "actor"},
        "identity_id": identity_id,
        "role_id": role_id,
        "reachability_status": status,
    }


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
) -> tuple[imessage_channel.ImessageChannelController, _FakeBuddySwitchImApi, _FakeImsg]:
    api = api or _FakeBuddySwitchImApi()
    imsg = imsg or _FakeImsg()
    config = imessage_channel.ChannelConfig(
        server="http://127.0.0.1:8765",
        state_path=temp_root / "state.json",
    )
    return imessage_channel.ImessageChannelController(config=config, api=api, imsg=imsg), api, imsg


class ImessageChannelTests(unittest.TestCase):
    def test_default_state_path_uses_imessage_channel_schema_v2(self) -> None:
        config = imessage_channel.ChannelConfig(server="http://127.0.0.1:8765")
        self.assertEqual(config.effective_state_path().parts[-2:], ("imessage-channel", "state.json"))

        with tempfile.TemporaryDirectory() as temp_root:
            store = imessage_channel.ImessageChannelStateStore(Path(temp_root) / "state.json")
            self.assertEqual(store.load(), {"schema_version": 2, "contacts": {}})

    def test_first_sender_message_creates_connection_and_reuses_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            first = controller.handle_inbound_message(_row(text="hello", guid="guid-1"))
            second = controller.handle_inbound_message(_row(text="hello again", guid="guid-2"))

        self.assertEqual(first["status"], "needs_actor")
        self.assertEqual(second["status"], "needs_actor")
        self.assertEqual([row["connection_key"] for row in api.created], ["imck-1"])
        self.assertEqual([row["text"] for row in imsg.sent], [PROMPT, PROMPT])

    def test_two_senders_keep_connections_choices_routes_and_dedupe_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(sender="a@example.com", text="/actors", guid="guid-a1", chat_id="1"))
            controller.handle_inbound_message(_row(sender="b@example.com", text="/actors", guid="guid-b1", chat_id="2"))
            controller.handle_inbound_message(_row(sender="a@example.com", text="1", guid="guid-a2", chat_id="1"))
            sent = controller.handle_inbound_message(_row(sender="a@example.com", text="ping", guid="guid-a3", chat_id="1"))
            prompted = controller.handle_inbound_message(_row(sender="b@example.com", text="ping", guid="guid-b2", chat_id="2"))
            duplicate = controller.handle_inbound_message(_row(sender="a@example.com", text="ping", guid="guid-a3", chat_id="1"))
            state = controller.state_store.load()

        self.assertEqual([row["connection_key"] for row in api.created], ["imck-1", "imck-2"])
        self.assertEqual(sent["status"], "delivered")
        self.assertEqual(prompted["status"], "needs_actor")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(api.sent[0]["connection_key"], "imck-1")
        self.assertEqual(state["contacts"]["sender:a@example.com"]["active_actor_id"], "act-market-demo")
        self.assertNotIn("active_actor_id", state["contacts"]["sender:b@example.com"])
        self.assertIn("msg-in-1", state["contacts"]["sender:a@example.com"]["routes"])
        self.assertEqual(state["contacts"]["sender:b@example.com"]["routes"], {})
        self.assertEqual(imsg.sent[-1]["route"], {"chat_id": "2", "sender": "b@example.com"})

    def test_actors_control_message_lists_online_actors_and_stores_snapshot(self) -> None:
        actors = [
            _actor("market", "act-market-online"),
            _actor("dev", "act-dev-offline", status="offline"),
            _actor("pm", "act-pm-online"),
        ]
        with tempfile.TemporaryDirectory() as temp_root:
            controller, _api, imsg = _controller(Path(temp_root), api=_FakeBuddySwitchImApi(actors=actors))

            result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            state = controller.state_store.load()

        self.assertEqual(result["status"], "actors_listed")
        self.assertEqual(imsg.sent[0]["text"], "[1] market act-market-online\n[2] pm act-pm-online")
        self.assertEqual(
            state["contacts"]["sender:user-a@example.com"]["pending_actor_choices"],
            {"1": "act-market-online", "2": "act-pm-online"},
        )

    def test_numeric_selection_uses_pending_snapshot_without_posting_message(self) -> None:
        actors = [_actor("market", "act-market-first"), _actor("dev", "act-dev-second")]
        with tempfile.TemporaryDirectory() as temp_root:
            api = _FakeBuddySwitchImApi(actors=actors)
            controller, _api, imsg = _controller(Path(temp_root), api=api)
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            api.actors = [_actor("design", "act-design-later")]

            result = controller.handle_inbound_message(_row(text="2", guid="guid-select"))
            state = controller.state_store.load()

        self.assertEqual(result["status"], "actor_selected")
        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["active_actor_id"], "act-dev-second")
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent[-1]["text"], "act-dev-second")

    def test_numeric_without_pending_choices_is_ordinary_message_and_prompts_when_no_active_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(_row(text="2", guid="guid-number"))

        self.assertEqual(result["status"], "needs_actor")
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent, [{"route": {"chat_id": "6", "sender": "user-a@example.com"}, "text": PROMPT}])

    def test_ordinary_message_without_active_actor_sends_minimal_actors_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))

            result = controller.handle_inbound_message(_row(text="plain message", guid="guid-plain"))

        self.assertEqual(result["status"], "needs_actor")
        self.assertEqual(api.sent, [])
        self.assertEqual(imsg.sent[0]["text"], PROMPT)

    def test_ordinary_message_posts_to_active_actor_with_original_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
            controller.handle_inbound_message(_row(text="1", guid="guid-select"))

            result = controller.handle_inbound_message(_row(text="  hello actor  ", guid="guid-message"))

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(api.sent[0]["target_identity_id"], "act-market-demo")
        self.assertEqual(api.sent[0]["content"], "hello actor")

    def test_actor_reply_is_prefixed_and_sent_to_recorded_route_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, imsg = _controller(Path(temp_root))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
            api.events_by_key["imck-1"] = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "msg-in-1",
                    "from_identity_id": "act-market-demo",
                }
            ]
            api.messages["msg-reply-1"] = {
                "id": "msg-reply-1",
                "content": "pong",
                "reply_to": "msg-in-1",
                "from_identity_id": "act-market-demo",
            }

            first = controller.poll_outbound_once(wait_ms=0)
            second = controller.poll_outbound_once(wait_ms=0)

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(
            imsg.sent[-1],
            {"route": {"chat_id": "9", "sender": "user-a@example.com"}, "text": "[Message From act-market-demo]\n\npong"},
        )

    def test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, api, _imsg = _controller(Path(temp_root), imsg=_FailingImsg(fail_on_call=3))
            controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
            controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
            controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
            api.events_by_key["imck-1"] = [
                {
                    "event_id": "imev-reply-1",
                    "message_id": "msg-reply-1",
                    "reply_to": "msg-in-1",
                    "from_identity_id": "act-market-demo",
                }
            ]
            api.messages["msg-reply-1"] = {
                "id": "msg-reply-1",
                "content": "pong",
                "reply_to": "msg-in-1",
                "from_identity_id": "act-market-demo",
            }

            with self.assertRaises(imessage_channel.ChannelError):
                controller.poll_outbound_once(wait_ms=0)
            state = controller.state_store.load()

        self.assertEqual(state["contacts"]["sender:user-a@example.com"]["sent_outbound_event_ids"], [])

    def test_worker_stop_terminates_watch_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            controller, _api, imsg = _controller(Path(temp_root))
            worker = imessage_channel.ImessageChannelWorker(controller)

            worker.stop()

        self.assertTrue(imsg.stopped)


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
        self.assertNotIn("env.repos.messages", source)
        self.assertNotIn("send_im_message", source)
        self.assertNotIn("send_external_connection_message", source)
        self.assertNotIn("read_external_connection_events", source)

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
            ROOT / "docs" / "spec",
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

    def test_channel_semantics_stay_out_of_web_http_and_core(self) -> None:
        forbidden_terms = ("pending_actor_choices", "active_actor_id", "[Message From")
        paths = [
            ROOT / "tools" / "launcher" / "web_management.py",
            ROOT / "tools" / "launcher" / "im_http_router.py",
            ROOT / "scripts" / "env" / "services",
            ROOT / "scripts" / "env" / "repos",
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
