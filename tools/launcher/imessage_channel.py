"""Local iMessage channel product logic for the External IM HTTP API."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib import error, request

HELPER_DIR = Path(__file__).resolve().parent
SCRIPTS = HELPER_DIR.parents[1] / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from env.repos import runtime_files  # noqa: E402


SCHEMA_VERSION = 6
DEFAULT_DISPLAY_NAME = "BuddySwitch iMessage"
DEFAULT_USAGE_PROMPT = "Use /actors, @actor-id <message>, or Reply to an actor message."
DEFAULT_NO_ACTORS_PROMPT = "No reachable actors."
DEFAULT_REPLY_UNAVAILABLE_PROMPT = "This message cannot be replied to."
DEFAULT_REPLY_FAILED_PROMPT = "Reply failed. Reply to a newer actor message or use @actor-id."
DEFAULT_REPLY_WAIT_MS = 30000
IMSG_STATUS_TIMEOUT_SECONDS = 5.0


class ChannelError(RuntimeError):
    """Raised when the iMessage channel cannot safely continue."""


class ChannelStateError(ChannelError):
    """Raised when persisted iMessage channel state cannot be used safely."""


@dataclass(frozen=True)
class ChannelConfig:
    server: str
    state_path: Path | None = None
    display_name: str = DEFAULT_DISPLAY_NAME
    imsg_bin: str = "imsg"

    def effective_state_path(self) -> Path:
        if self.state_path is not None:
            return self.state_path
        return runtime_files.LOCAL_ROOT / "imessage-channel" / "state.json"


@dataclass(frozen=True)
class _MessageSendStatus:
    rowid: int
    guid: str
    error: int
    is_sent: int
    is_delivered: int
    is_finished: int


@dataclass(frozen=True)
class ImessageSendReceipt:
    guid: str


@dataclass(frozen=True)
class _ListActors:
    pass


@dataclass(frozen=True)
class _SendToActor:
    target_identity_id: str
    content: str


@dataclass(frozen=True)
class _InvalidTopLevel:
    pass


_TopLevelCommand = _ListActors | _SendToActor | _InvalidTopLevel


@dataclass(frozen=True)
class _NativeReply:
    anchor_guid: str
    body: str


@dataclass(frozen=True)
class _TopLevel:
    command: _TopLevelCommand


_ParsedInboundMessage = _NativeReply | _TopLevel


class ImessageChannelStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _default_state()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChannelStateError(f"invalid iMessage channel state: {exc}") from exc
        if not isinstance(payload, dict):
            raise ChannelStateError("invalid iMessage channel state: root must be an object")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ChannelStateError("iMessage channel state schema is retired; reset the channel state file")
        contacts_payload = payload.get("contacts")
        contacts: dict[str, dict[str, Any]] = {}
        if isinstance(contacts_payload, dict):
            for key, value in contacts_payload.items():
                if isinstance(key, str) and isinstance(value, dict):
                    contacts[key] = _normalize_contact(value)
        return {"schema_version": SCHEMA_VERSION, "contacts": contacts}

    def save(self, state: dict[str, Any]) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "contacts": state.get("contacts") if isinstance(state.get("contacts"), dict) else {},
        }
        try:
            runtime_files.write_json_object(self.path, payload)
        except (OSError, TypeError, ValueError) as exc:
            raise ChannelStateError(f"failed to save iMessage channel state: {exc}") from exc
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass


class BuddySwitchImApi:
    def __init__(self, server: str) -> None:
        self.server = server.rstrip("/")
        self._opener = request.build_opener(request.ProxyHandler({}))

    def create_external_session(self, *, display_name: str) -> dict[str, Any]:
        return self._request("POST", "/api/im/external-sessions", {"display_name": display_name}, external_session_key=None)

    def list_actors(self, *, external_session_key: str) -> dict[str, Any]:
        return self._request("GET", "/api/im/actors", None, external_session_key=external_session_key)

    def send_to_actor(
        self,
        *,
        external_session_key: str,
        target_identity_id: str,
        content: str,
    ) -> dict[str, Any]:
        return self._post_message(
            external_session_key=external_session_key,
            payload={"target_identity_id": target_identity_id, "content": content},
        )

    def reply_to_message(
        self,
        *,
        external_session_key: str,
        reply_to: str,
        content: str,
    ) -> dict[str, Any]:
        return self._post_message(
            external_session_key=external_session_key,
            payload={"reply_to": reply_to, "content": content},
        )

    def _post_message(self, *, external_session_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/im/messages",
            payload,
            external_session_key=external_session_key,
        )

    def read_events(self, *, external_session_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/im/events?limit={limit}&wait_ms={wait_ms}",
            None,
            external_session_key=external_session_key,
            timeout_seconds=_request_timeout_seconds(wait_ms=wait_ms),
        )

    def ack_event(self, *, external_session_key: str, event_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/im/events/ack",
            {"event_id": event_id},
            external_session_key=external_session_key,
        )

    def get_message(self, *, external_session_key: str, message_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/im/messages/{message_id}", None, external_session_key=external_session_key)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        external_session_key: str | None,
        timeout_seconds: float = 30,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if external_session_key:
            headers["Authorization"] = f"Bearer {external_session_key}"
        req = request.Request(f"{self.server}{path}", data=body, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed_error = json.loads(raw)
            except json.JSONDecodeError:
                raise ChannelError(f"BuddySwitch API failed with HTTP {exc.code}: {raw}") from exc
            if isinstance(parsed_error, dict):
                return parsed_error
            raise ChannelError(f"BuddySwitch API failed with HTTP {exc.code}: {raw}") from exc
        except OSError as exc:
            raise ChannelError(f"BuddySwitch API unavailable: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ChannelError(f"BuddySwitch API returned invalid JSON: {raw}") from exc
        if not isinstance(parsed, dict):
            raise ChannelError("BuddySwitch API returned non-object JSON")
        return parsed


def _request_timeout_seconds(*, wait_ms: int) -> float:
    wait_seconds = max(wait_ms, 0) / 1000
    return max(30, wait_seconds + 5)


class CommandImsgClient:
    def __init__(
        self,
        imsg_bin: str = "imsg",
        *,
        messages_db_path: Path | None = None,
        send_status_timeout_seconds: float = 3.0,
        send_status_poll_interval_seconds: float = 0.2,
        subprocess_run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        send_status_poll_hook: Callable[[], None] | None = None,
    ) -> None:
        self.imsg_bin = imsg_bin
        self.messages_db_path = messages_db_path or Path.home() / "Library" / "Messages" / "chat.db"
        self.send_status_timeout_seconds = max(send_status_timeout_seconds, 0)
        self.send_status_poll_interval_seconds = max(send_status_poll_interval_seconds, 0.01)
        self._subprocess_run = subprocess_run or subprocess.run
        self._send_status_poll_hook = send_status_poll_hook
        self._watch_process: subprocess.Popen[str] | None = None

    def status(self) -> None:
        try:
            result = self._subprocess_run(
                [self.imsg_bin, "status"],
                text=True,
                capture_output=True,
                check=False,
                timeout=IMSG_STATUS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ChannelError("iMessage status check timed out") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "imsg status failed"
            raise ChannelError(detail)

    def watch_messages(self) -> Iterator[dict[str, Any]]:
        process = subprocess.Popen(
            [self.imsg_bin, "watch", "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._watch_process = process
        assert process.stdout is not None
        for line in process.stdout:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload

    def send(self, *, route: dict[str, Any], text: str) -> ImessageSendReceipt:
        command = [self.imsg_bin, "send", "--text", text]
        if route.get("chat_id"):
            command.extend(["--chat-id", str(route["chat_id"])])
        elif route.get("chat_identifier"):
            command.extend(["--chat-identifier", str(route["chat_identifier"])])
        elif route.get("chat_guid"):
            command.extend(["--chat-guid", str(route["chat_guid"])])
        elif route.get("sender"):
            command.extend(["--to", str(route["sender"])])
        else:
            raise ChannelError("outbound iMessage route is missing chat or sender")
        before_rowid = self._latest_outbound_rowid(route)
        result = self._subprocess_run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "imsg send failed"
            raise ChannelError(detail)
        status = self._confirm_send_status(route=route, after_rowid=before_rowid)
        if not status.guid:
            raise ChannelError("iMessage send confirmation did not include guid")
        return ImessageSendReceipt(guid=status.guid)

    def stop(self) -> None:
        process = self._watch_process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _latest_outbound_rowid(self, route: dict[str, Any]) -> int:
        query, params = _send_status_query(route=route, after_rowid=0, max_only=True)
        try:
            with _open_messages_db(self.messages_db_path) as db:
                row = db.execute(query, params).fetchone()
        except sqlite3.Error as exc:
            raise ChannelError(f"iMessage send status verification failed before send: {exc}") from exc
        if row is None:
            return 0
        return int(row[0] or 0)

    def _confirm_send_status(self, *, route: dict[str, Any], after_rowid: int) -> _MessageSendStatus:
        deadline = time.monotonic() + self.send_status_timeout_seconds
        last_status: _MessageSendStatus | None = None
        while True:
            status = self._latest_send_status(route=route, after_rowid=after_rowid)
            if status is not None:
                last_status = status
                if status.error == 0 and status.is_sent == 1:
                    return status
                if status.error != 0:
                    raise ChannelError(_send_status_error(status))
            if self._send_status_poll_hook is not None:
                self._send_status_poll_hook()
            if time.monotonic() >= deadline:
                break
            time.sleep(self.send_status_poll_interval_seconds)
        if last_status is not None:
            raise ChannelError(_send_status_error(last_status))
        raise ChannelError("iMessage send status row not found after command submission")

    def _latest_send_status(self, *, route: dict[str, Any], after_rowid: int) -> _MessageSendStatus | None:
        query, params = _send_status_query(route=route, after_rowid=after_rowid, max_only=False)
        try:
            with _open_messages_db(self.messages_db_path) as db:
                row = db.execute(query, params).fetchone()
        except sqlite3.Error as exc:
            raise ChannelError(f"iMessage send status verification failed after send: {exc}") from exc
        if row is None:
            return None
        return _MessageSendStatus(
            rowid=int(row[0] or 0),
            guid=str(row[1] or ""),
            error=int(row[2] or 0),
            is_sent=int(row[3] or 0),
            is_delivered=int(row[4] or 0),
            is_finished=int(row[5] or 0),
        )


def _open_messages_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise sqlite3.OperationalError(f"messages database not found: {path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)


def _send_status_query(*, route: dict[str, Any], after_rowid: int, max_only: bool) -> tuple[str, tuple[Any, ...]]:
    if max_only:
        select = "SELECT COALESCE(MAX(message.ROWID), 0)"
        suffix = ""
    else:
        select = (
            "SELECT message.ROWID, message.guid, COALESCE(message.error, 0), "
            "COALESCE(message.is_sent, 0), COALESCE(message.is_delivered, 0), "
            "COALESCE(message.is_finished, 0)"
        )
        suffix = " ORDER BY message.ROWID DESC LIMIT 1"

    if route.get("chat_id"):
        return (
            f"""
            {select}
            FROM message
            JOIN chat_message_join ON chat_message_join.message_id = message.ROWID
            WHERE chat_message_join.chat_id = ?
              AND message.ROWID > ?
              AND COALESCE(message.is_from_me, 0) = 1
            {suffix}
            """,
            (str(route["chat_id"]), after_rowid),
        )
    if route.get("chat_identifier"):
        return (
            f"""
            {select}
            FROM message
            JOIN chat_message_join ON chat_message_join.message_id = message.ROWID
            JOIN chat ON chat.ROWID = chat_message_join.chat_id
            WHERE chat.chat_identifier = ?
              AND message.ROWID > ?
              AND COALESCE(message.is_from_me, 0) = 1
            {suffix}
            """,
            (str(route["chat_identifier"]), after_rowid),
        )
    if route.get("chat_guid"):
        return (
            f"""
            {select}
            FROM message
            JOIN chat_message_join ON chat_message_join.message_id = message.ROWID
            JOIN chat ON chat.ROWID = chat_message_join.chat_id
            WHERE chat.guid = ?
              AND message.ROWID > ?
              AND COALESCE(message.is_from_me, 0) = 1
            {suffix}
            """,
            (str(route["chat_guid"]), after_rowid),
        )
    if route.get("sender"):
        sender = _normalize_sender(route["sender"])
        return (
            f"""
            {select}
            FROM message
            JOIN handle ON handle.ROWID = message.handle_id
            WHERE message.ROWID > ?
              AND COALESCE(message.is_from_me, 0) = 1
              AND (
                LOWER(handle.id) = LOWER(?)
                OR LOWER(COALESCE(handle.uncanonicalized_id, '')) = LOWER(?)
              )
            {suffix}
            """,
            (after_rowid, sender, sender),
        )
    raise ChannelError("outbound iMessage route is missing chat or sender")


def _send_status_error(status: _MessageSendStatus) -> str:
    return (
        "iMessage send failed "
        f"rowid={status.rowid} guid={status.guid} error={status.error} "
        f"is_sent={status.is_sent} is_delivered={status.is_delivered} is_finished={status.is_finished}"
    )


class ImessageChannelController:
    def __init__(
        self,
        *,
        config: ChannelConfig,
        api: Any | None = None,
        imsg: Any | None = None,
        state_store: ImessageChannelStateStore | None = None,
    ) -> None:
        self.config = config
        self.api = api or BuddySwitchImApi(config.server)
        self.imsg = imsg or CommandImsgClient(config.imsg_bin)
        self.state_store = state_store or ImessageChannelStateStore(config.effective_state_path())
        self._state_lock = threading.RLock()

    def prepare(self) -> None:
        with self._state_lock:
            self.state_store.load()
        self.imsg.status()

    def handle_inbound_message(self, row: dict[str, Any]) -> dict[str, Any]:
        if _truthy(row.get("is_from_me")):
            return {"ok": True, "status": "ignored_from_me"}
        sender = _sender_from_row(row)
        if not sender:
            return {"ok": True, "status": "ignored_sender"}
        content = _content_from_row(row)
        if not content:
            return {"ok": True, "status": "ignored_empty"}
        parsed = _parse_inbound_message(row)

        with self._state_lock:
            state = self.state_store.load()
            contact = self._contact(state, sender)
            route = _route_from_row(row, sender=sender)
            _set_contact_route(contact, route)
            external_session_key, _external_identity_id, binding_created = self._external_session_binding(contact)
            if binding_created:
                self.state_store.save(state)
            inbound_key = _inbound_key(row)
            if inbound_key in set(_string_list(contact.get("seen_inbound_keys"))):
                self.state_store.save(state)
                return {"ok": True, "status": "duplicate"}
            match parsed:
                case _NativeReply(anchor_guid=anchor_guid, body=reply_content):
                    return self._handle_native_reply(
                        state,
                        contact,
                        external_session_key,
                        route,
                        content=reply_content,
                        anchor_guid=anchor_guid,
                        inbound_key=inbound_key,
                    )
                case _TopLevel(command=_ListActors()):
                    return self._handle_actors(
                        state,
                        contact,
                        external_session_key,
                        route,
                        inbound_key=inbound_key,
                    )
                case _TopLevel(
                    command=_SendToActor(target_identity_id=target_identity_id, content=message_content)
                ):
                    return self._handle_actor_send(
                        state,
                        contact,
                        external_session_key,
                        target_identity_id=target_identity_id,
                        content=message_content,
                        inbound_key=inbound_key,
                    )
                case _TopLevel(command=_InvalidTopLevel()):
                    return self._send_terminal_feedback(
                        state,
                        contact,
                        route=route,
                        text=DEFAULT_USAGE_PROMPT,
                        inbound_key=inbound_key,
                        status="invalid_message",
                    )
            raise ChannelError(f"unsupported parsed iMessage message: {type(parsed).__name__}")

    def poll_outbound_once(self, *, wait_ms: int = 0, limit: int = 50) -> dict[str, Any]:
        with self._state_lock:
            state = self.state_store.load()
            poll_targets = [
                (sender_key, _contact_external_session_key(contact))
                for sender_key, contact in _contacts(state).items()
                if _contact_external_session_key(contact) and _contact_external_identity_id(contact) and _contact_route(contact)
            ]
        sent_count = 0
        for sender_key, external_session_key in poll_targets:
            events = self.api.read_events(external_session_key=external_session_key, limit=limit, wait_ms=wait_ms)
            if events.get("ok") is not True:
                raise ChannelError(str((events.get("error") or {}).get("message") or "BuddySwitch events read failed"))
            with self._state_lock:
                state = self.state_store.load()
                contact = _contacts(state).get(sender_key)
                if not isinstance(contact, dict):
                    continue
                route = _contact_route(contact)
                if route is None:
                    continue
                contact_sent_count = 0
                for event in events.get("events") if isinstance(events.get("events"), list) else []:
                    if not isinstance(event, dict):
                        continue
                    event_id = str(event.get("event_id") or "")
                    message_id = str(event.get("message_id") or "")
                    if not event_id or not message_id:
                        continue
                    if _message_link_for_event(contact, event_id) is not None:
                        self._ack_outbound_event(external_session_key=external_session_key, event_id=event_id)
                        continue
                    fetched = self.api.get_message(external_session_key=external_session_key, message_id=message_id)
                    if fetched.get("ok") is not True or not isinstance(fetched.get("message"), dict):
                        continue
                    message = fetched["message"]
                    content = str(message.get("content") or "").strip()
                    actor_id = _actor_id_for_reply(event, message)
                    if not content or not actor_id:
                        continue
                    receipt = self.imsg.send(route=route, text=f"[Message From {actor_id}]\n\n{content}")
                    guid = str(getattr(receipt, "guid", "") or "").strip()
                    if not guid:
                        raise ChannelError("iMessage send receipt did not include guid")
                    _save_message_link(
                        contact,
                        guid=guid,
                        message_id=message_id,
                        event_id=event_id,
                    )
                    contact_sent_count += 1
                    self.state_store.save(state)
                    self._ack_outbound_event(external_session_key=external_session_key, event_id=event_id)
                if contact_sent_count:
                    sent_count += contact_sent_count
        return {"ok": True, "sent": sent_count}

    def _ack_outbound_event(self, *, external_session_key: str, event_id: str) -> bool:
        result = self.api.ack_event(external_session_key=external_session_key, event_id=event_id)
        return result.get("ok") is True

    def _handle_actors(
        self,
        state: dict[str, Any],
        contact: dict[str, Any],
        external_session_key: str,
        route: dict[str, Any],
        *,
        inbound_key: str,
    ) -> dict[str, Any]:
        payload = self.api.list_actors(external_session_key=external_session_key)
        if payload.get("ok") is not True:
            raise ChannelError(str((payload.get("error") or {}).get("message") or "actor list failed"))
        lines: list[str] = []
        for actor in payload.get("actors") if isinstance(payload.get("actors"), list) else []:
            if not isinstance(actor, dict):
                continue
            actor_id = str(actor.get("identity_id") or "")
            role_id = str(actor.get("role_id") or "")
            if not actor_id or not role_id:
                continue
            lines.append(f"@{actor_id} ({role_id})")
        self.imsg.send(
            route=route,
            text="\n".join(lines) if lines else DEFAULT_NO_ACTORS_PROMPT,
        )
        _mark_inbound_seen(contact, inbound_key)
        self.state_store.save(state)
        return {"ok": True, "status": "actors_listed", "count": len(lines)}

    def _handle_actor_send(
        self,
        state: dict[str, Any],
        contact: dict[str, Any],
        external_session_key: str,
        *,
        target_identity_id: str,
        content: str,
        inbound_key: str,
    ) -> dict[str, Any]:
        response = self.api.send_to_actor(
            external_session_key=external_session_key,
            target_identity_id=target_identity_id,
            content=content,
        )
        if response.get("ok") is not True:
            raise ChannelError(str((response.get("error") or {}).get("message") or "BuddySwitch send failed"))
        message = response.get("message") if isinstance(response.get("message"), dict) else {}
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise ChannelError("BuddySwitch send response did not include message.id")
        _mark_inbound_seen(contact, inbound_key)
        self.state_store.save(state)
        return {"ok": True, "status": "delivered", "message_id": message_id}

    def _handle_native_reply(
        self,
        state: dict[str, Any],
        contact: dict[str, Any],
        external_session_key: str,
        route: dict[str, Any],
        *,
        content: str,
        anchor_guid: str,
        inbound_key: str,
    ) -> dict[str, Any]:
        message_id = _message_id_for_imessage_guid(contact, anchor_guid)
        if not message_id:
            return self._send_terminal_feedback(
                state,
                contact,
                route=route,
                text=DEFAULT_REPLY_UNAVAILABLE_PROMPT,
                inbound_key=inbound_key,
                status="reply_unavailable",
            )
        response = self.api.reply_to_message(
            external_session_key=external_session_key,
            reply_to=message_id,
            content=content,
        )
        if response.get("ok") is not True:
            return self._send_terminal_feedback(
                state,
                contact,
                route=route,
                text=DEFAULT_REPLY_FAILED_PROMPT,
                inbound_key=inbound_key,
                status="reply_failed",
            )
        message = response.get("message") if isinstance(response.get("message"), dict) else {}
        reply_message_id = str(message.get("id") or "").strip()
        if not reply_message_id:
            raise ChannelError("BuddySwitch reply response did not include message.id")
        _mark_inbound_seen(contact, inbound_key)
        self.state_store.save(state)
        return {"ok": True, "status": "replied", "message_id": reply_message_id, "reply_to": message_id}

    def _send_terminal_feedback(
        self,
        state: dict[str, Any],
        contact: dict[str, Any],
        *,
        route: dict[str, Any],
        text: str,
        inbound_key: str,
        status: str,
    ) -> dict[str, Any]:
        self.imsg.send(route=route, text=text)
        _mark_inbound_seen(contact, inbound_key)
        self.state_store.save(state)
        return {"ok": True, "status": status}

    def _contact(self, state: dict[str, Any], sender: str) -> dict[str, Any]:
        contacts = _contacts(state)
        key = _sender_key(sender)
        if key not in contacts:
            contacts[key] = _default_contact()
        return contacts[key]

    def _external_session_binding(self, contact: dict[str, Any]) -> tuple[str, str, bool]:
        existing_key = _contact_external_session_key(contact)
        existing_identity = _contact_external_identity_id(contact)
        if existing_key and existing_identity:
            return existing_key, existing_identity, False
        created = self.api.create_external_session(display_name=self.config.display_name)
        if created.get("ok") is not True:
            raise ChannelError(str((created.get("error") or {}).get("message") or "external session creation failed"))
        external_session_key = str(created.get("external_session_key") or "").strip()
        identity = created.get("identity")
        external_identity_id = str(identity.get("id") or "").strip() if isinstance(identity, dict) else ""
        identity_type = str(identity.get("type") or "").strip() if isinstance(identity, dict) else ""
        if not external_session_key:
            raise ChannelError("external session creation did not return external_session_key")
        if not external_identity_id or identity_type != "external":
            raise ChannelError("external session creation did not return external identity")
        contact["external_session_key"] = external_session_key
        contact["external_identity_id"] = external_identity_id
        return external_session_key, external_identity_id, True


class ImessageChannelWorker:
    def __init__(self, controller: ImessageChannelController, *, reply_wait_ms: int = DEFAULT_REPLY_WAIT_MS) -> None:
        self.controller = controller
        self.reply_wait_ms = reply_wait_ms
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self.controller.prepare()
        self._stop_event.clear()
        self._threads = [
            threading.Thread(target=self._run_with_error_capture, args=("inbound", self.run_forever), daemon=True),
            threading.Thread(target=self._run_with_error_capture, args=("outbound", self.run_outbound_forever), daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def run_forever(self) -> None:
        for row in self.controller.imsg.watch_messages():
            if self._stop_event.is_set():
                break
            try:
                self.controller.handle_inbound_message(row)
            except Exception as exc:
                print(f"iMessage channel inbound message failed: {exc}", file=sys.stderr, flush=True)
                continue

    def run_outbound_forever(self) -> None:
        wait_ms = max(self.reply_wait_ms, 0)
        while not self._stop_event.is_set():
            try:
                self.controller.poll_outbound_once(wait_ms=wait_ms)
            except Exception as exc:
                print(f"iMessage channel outbound poll failed: {exc}", file=sys.stderr, flush=True)
            self._stop_event.wait(0.01)

    def stop(self) -> None:
        self._stop_event.set()
        stopper = getattr(self.controller.imsg, "stop", None)
        if callable(stopper):
            stopper()
        for thread in self._threads:
            if thread.is_alive() and threading.current_thread() is not thread:
                thread.join(timeout=5)

    def _run_with_error_capture(self, loop_name: str, runner: Callable[[], None]) -> None:
        try:
            runner()
        except Exception as exc:  # pragma: no cover - defensive background guard
            print(f"iMessage channel {loop_name} worker stopped: {exc}", file=sys.stderr, flush=True)


def _default_state() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "contacts": {}}


def _default_contact() -> dict[str, Any]:
    return {
        "seen_inbound_keys": [],
        "message_links": {},
    }


def _normalize_contact(payload: dict[str, Any]) -> dict[str, Any]:
    contact = _default_contact()
    external_session_key = payload.get("external_session_key")
    if isinstance(external_session_key, str) and external_session_key.strip():
        contact["external_session_key"] = external_session_key.strip()
    external_identity_id = payload.get("external_identity_id")
    if isinstance(external_identity_id, str) and external_identity_id.strip():
        contact["external_identity_id"] = external_identity_id.strip()
    route = payload.get("route")
    if isinstance(route, dict) and _valid_route(route):
        contact["route"] = dict(route)
    contact["seen_inbound_keys"] = _string_list(payload.get("seen_inbound_keys"))
    contact["message_links"] = _normalize_message_links(payload.get("message_links"))
    return contact


def _normalize_message_links(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    links: dict[str, dict[str, str]] = {}
    for raw_guid, raw_link in value.items():
        guid = str(raw_guid).strip() if isinstance(raw_guid, str) else ""
        if not guid or not isinstance(raw_link, dict):
            continue
        message_id = str(raw_link.get("message_id") or "").strip()
        event_id = str(raw_link.get("event_id") or "").strip()
        if message_id and event_id:
            links[guid] = {"message_id": message_id, "event_id": event_id}
    return links


def _contacts(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    contacts = state.get("contacts")
    if not isinstance(contacts, dict):
        contacts = {}
        state["contacts"] = contacts
    return contacts


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(row) for row in value if isinstance(row, (str, int)) and str(row)]


def _sender_key(sender: str) -> str:
    return f"sender:{_normalize_sender(sender)}"


def _normalize_sender(value: Any) -> str:
    text = str(value or "").strip()
    return text.lower() if "@" in text else text


def _sender_from_row(row: dict[str, Any]) -> str:
    for field in ("sender", "sender_handle", "from", "handle", "phone", "email"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _content_from_row(row: dict[str, Any]) -> str:
    for field in ("text", "content", "body", "message"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_inbound_message(row: dict[str, Any]) -> _ParsedInboundMessage:
    content = _content_from_row(row)
    raw_anchor = row.get("thread_originator_guid")
    anchor_guid = raw_anchor.strip() if isinstance(raw_anchor, str) else ""
    match anchor_guid:
        case "":
            return _TopLevel(command=_parse_top_level_command(content))
        case _:
            return _NativeReply(anchor_guid=anchor_guid, body=content)


def _parse_top_level_command(content: str) -> _TopLevelCommand:
    match content.split(maxsplit=1):
        case ["/actors"]:
            return _ListActors()
        case [head, body] if head.startswith("@") and len(head) > 1 and body.strip():
            return _SendToActor(target_identity_id=head[1:], content=body.strip())
        case _:
            return _InvalidTopLevel()


def _route_from_row(row: dict[str, Any], *, sender: str) -> dict[str, Any]:
    route: dict[str, Any] = {"sender": _normalize_sender(sender)}
    for field in ("chat_id", "chat_identifier", "chat_guid"):
        value = row.get(field)
        if isinstance(value, (str, int)) and str(value).strip():
            route[field] = str(value).strip()
    return route


def _valid_route(route: dict[str, Any]) -> bool:
    return any(route.get(field) for field in ("chat_id", "chat_identifier", "chat_guid", "sender"))


def _contact_route(contact: dict[str, Any]) -> dict[str, Any] | None:
    value = contact.get("route")
    return dict(value) if isinstance(value, dict) and _valid_route(value) else None


def _set_contact_route(contact: dict[str, Any], route: dict[str, Any]) -> None:
    if not _valid_route(route):
        raise ChannelError("iMessage contact route is missing chat or sender")
    contact["route"] = dict(route)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _message_id_for_imessage_guid(contact: dict[str, Any], guid: str) -> str:
    links = _normalize_message_links(contact.get("message_links"))
    link = links.get(guid)
    if not isinstance(link, dict):
        return ""
    return str(link.get("message_id") or "").strip()


def _message_link_for_event(contact: dict[str, Any], event_id: str) -> dict[str, str] | None:
    for link in _normalize_message_links(contact.get("message_links")).values():
        if link.get("event_id") == event_id:
            return dict(link)
    return None


def _save_message_link(
    contact: dict[str, Any],
    *,
    guid: str,
    message_id: str,
    event_id: str,
) -> None:
    links = _normalize_message_links(contact.get("message_links"))
    links[guid] = {"message_id": message_id, "event_id": event_id}
    contact["message_links"] = links


def _mark_inbound_seen(contact: dict[str, Any], inbound_key: str) -> None:
    seen = set(_string_list(contact.get("seen_inbound_keys")))
    seen.add(inbound_key)
    contact["seen_inbound_keys"] = sorted(seen)


def _contact_external_session_key(contact: dict[str, Any]) -> str:
    value = contact.get("external_session_key")
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _contact_external_identity_id(contact: dict[str, Any]) -> str:
    value = contact.get("external_identity_id")
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _inbound_key(row: dict[str, Any]) -> str:
    guid = row.get("guid")
    if isinstance(guid, str) and guid.strip():
        return f"guid:{guid.strip()}"
    for field in ("rowid", "row_id", "id"):
        value = row.get(field)
        if isinstance(value, (str, int)) and str(value).strip():
            return f"{field}:{str(value).strip()}"
    raise ChannelError("inbound iMessage row is missing guid or rowid")


def _actor_id_for_reply(event: dict[str, Any], message: dict[str, Any]) -> str:
    for payload in (event, message):
        sender_identity = payload.get("sender_identity")
        if isinstance(sender_identity, dict):
            value = sender_identity.get("id")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


if __name__ == "__main__":
    raise SystemExit("imessage_channel is not a standalone command")
