#!/usr/bin/env python3
"""Local iMessage bridge adapter for the External IM HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib import error, request

HELPER_DIR = Path(__file__).resolve().parent
SCRIPTS = HELPER_DIR.parents[1] / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from env.repos import runtime_files  # noqa: E402


SCHEMA_VERSION = 1
DEFAULT_DISPLAY_NAME = "BuddySwitch iMessage"
DEFAULT_REPLY_WAIT_MS = 30000


class BridgeError(RuntimeError):
    """Raised when the iMessage bridge cannot safely continue."""


@dataclass(frozen=True)
class BridgeConfig:
    server: str
    target_identity_id: str
    allow_senders: tuple[str, ...]
    state_path: Path | None = None
    display_name: str = DEFAULT_DISPLAY_NAME
    imsg_bin: str = "imsg"

    def effective_state_path(self) -> Path:
        if self.state_path is not None:
            return self.state_path
        return runtime_files.LOCAL_ROOT / "imessage-bridge" / "state.json"


class BridgeStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _default_state()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeError(f"invalid iMessage bridge state: {exc}") from exc
        if not isinstance(payload, dict):
            raise BridgeError("invalid iMessage bridge state: root must be an object")
        state = _default_state()
        state.update(payload)
        state["seen_inbound_keys"] = _string_list(state.get("seen_inbound_keys"))
        state["sent_outbound_event_ids"] = _string_list(state.get("sent_outbound_event_ids"))
        routes = state.get("message_routes")
        state["message_routes"] = routes if isinstance(routes, dict) else {}
        return state

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass


class BuddySwitchImApi:
    def __init__(self, server: str) -> None:
        self.server = server.rstrip("/")
        self._opener = request.build_opener(request.ProxyHandler({}))

    def create_connection(self, *, display_name: str) -> dict[str, Any]:
        return self._request("POST", "/api/im/connections", {"display_name": display_name}, connection_key=None)

    def list_actors(self, *, connection_key: str) -> dict[str, Any]:
        return self._request("GET", "/api/im/actors", None, connection_key=connection_key)

    def send_message(
        self,
        *,
        connection_key: str,
        target_identity_id: str,
        content: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/im/messages",
            {
                "target_identity_id": target_identity_id,
                "content": content,
                "reply_to": reply_to,
            },
            connection_key=connection_key,
        )

    def read_events(self, *, connection_key: str, limit: int, wait_ms: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/im/events?limit={limit}&wait_ms={wait_ms}",
            None,
            connection_key=connection_key,
            timeout_seconds=_request_timeout_seconds(wait_ms=wait_ms),
        )

    def get_message(self, *, connection_key: str, message_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/im/messages/{message_id}", None, connection_key=connection_key)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        connection_key: str | None,
        timeout_seconds: float = 30,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if connection_key:
            headers["Authorization"] = f"Bearer {connection_key}"
        req = request.Request(f"{self.server}{path}", data=body, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed_error = json.loads(raw)
            except json.JSONDecodeError:
                raise BridgeError(f"BuddySwitch API failed with HTTP {exc.code}: {raw}") from exc
            if isinstance(parsed_error, dict):
                return parsed_error
            raise BridgeError(f"BuddySwitch API failed with HTTP {exc.code}: {raw}") from exc
        except OSError as exc:
            raise BridgeError(f"BuddySwitch API unavailable: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BridgeError(f"BuddySwitch API returned invalid JSON: {raw}") from exc
        if not isinstance(parsed, dict):
            raise BridgeError("BuddySwitch API returned non-object JSON")
        return parsed


def _request_timeout_seconds(*, wait_ms: int) -> float:
    wait_seconds = max(wait_ms, 0) / 1000
    return max(30, wait_seconds + 5)


class CommandImsgClient:
    def __init__(self, imsg_bin: str = "imsg") -> None:
        self.imsg_bin = imsg_bin

    def status(self) -> None:
        result = subprocess.run(
            [self.imsg_bin, "status"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "imsg status failed"
            raise BridgeError(detail)

    def watch_messages(self) -> Iterator[dict[str, Any]]:
        process = subprocess.Popen(
            [self.imsg_bin, "watch", "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
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

    def send(self, *, route: dict[str, Any], text: str) -> None:
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
            raise BridgeError("outbound iMessage route is missing chat or sender")
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "imsg send failed"
            raise BridgeError(detail)


class ImessageBridge:
    def __init__(
        self,
        *,
        config: BridgeConfig,
        api: Any | None = None,
        imsg: Any | None = None,
        state_store: BridgeStateStore | None = None,
    ) -> None:
        self.config = config
        self.api = api or BuddySwitchImApi(config.server)
        self.imsg = imsg or CommandImsgClient(config.imsg_bin)
        self.state_store = state_store or BridgeStateStore(config.effective_state_path())
        self.state = self.state_store.load()

    def ensure_ready(self) -> dict[str, Any]:
        self.imsg.status()
        connection_key = self._connection_key()
        actors = self.api.list_actors(connection_key=connection_key)
        if not _actor_is_reachable(actors, self.config.target_identity_id):
            raise BridgeError(f"target actor is not reachable: {self.config.target_identity_id}")
        self.state["target_identity_id"] = self.config.target_identity_id
        self.state["allowed_senders"] = sorted(_normalize_sender(row) for row in self.config.allow_senders)
        self._save()
        return {"ok": True, "connection_key": connection_key}

    def handle_inbound_message(self, row: dict[str, Any]) -> dict[str, Any]:
        if _truthy(row.get("is_from_me")):
            return {"ok": True, "status": "ignored_from_me"}
        sender = _sender_from_row(row)
        if not sender or _normalize_sender(sender) not in set(self.state.get("allowed_senders") or []):
            return {"ok": True, "status": "ignored_sender"}
        content = _content_from_row(row)
        if not content:
            return {"ok": True, "status": "ignored_empty"}
        inbound_key = _inbound_key(row)
        seen = set(_string_list(self.state.get("seen_inbound_keys")))
        if inbound_key in seen:
            return {"ok": True, "status": "duplicate"}

        connection_key = self._connection_key()
        response = self.api.send_message(
            connection_key=connection_key,
            target_identity_id=self.config.target_identity_id,
            content=content,
            reply_to=None,
        )
        if response.get("ok") is not True:
            raise BridgeError(str((response.get("error") or {}).get("message") or "BuddySwitch send failed"))
        message = response.get("message") if isinstance(response.get("message"), dict) else {}
        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise BridgeError("BuddySwitch send response did not include message.id")
        seen.add(inbound_key)
        self.state["seen_inbound_keys"] = sorted(seen)
        routes = self._message_routes()
        routes[message_id] = _route_from_row(row, sender=sender)
        self.state["message_routes"] = routes
        self._save()
        return {"ok": True, "status": "delivered", "message_id": message_id}

    def poll_outbound_once(self, *, wait_ms: int = 0, limit: int = 50) -> dict[str, Any]:
        connection_key = self._connection_key()
        events = self.api.read_events(connection_key=connection_key, limit=limit, wait_ms=wait_ms)
        if events.get("ok") is not True:
            raise BridgeError(str((events.get("error") or {}).get("message") or "BuddySwitch events read failed"))
        sent_event_ids = set(_string_list(self.state.get("sent_outbound_event_ids")))
        sent_count = 0
        for event in events.get("events") if isinstance(events.get("events"), list) else []:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("event_id") or "")
            if not event_id or event_id in sent_event_ids:
                continue
            message_id = str(event.get("message_id") or "")
            if not message_id:
                continue
            fetched = self.api.get_message(connection_key=connection_key, message_id=message_id)
            if fetched.get("ok") is not True or not isinstance(fetched.get("message"), dict):
                continue
            message = fetched["message"]
            reply_to = str(message.get("reply_to") or event.get("reply_to") or "")
            route = self._message_routes().get(reply_to)
            content = str(message.get("content") or "").strip()
            if not route or not content:
                continue
            self.imsg.send(route=route, text=content)
            sent_event_ids.add(event_id)
            sent_count += 1
        if sent_count:
            self.state["sent_outbound_event_ids"] = sorted(sent_event_ids)
            self._save()
        return {"ok": True, "sent": sent_count}

    def run_forever(self, *, reply_wait_ms: int = DEFAULT_REPLY_WAIT_MS) -> None:
        self.ensure_ready()
        for row in self.imsg.watch_messages():
            self.handle_inbound_message(row)
            self.poll_outbound_once(wait_ms=max(reply_wait_ms, 0))

    def _connection_key(self) -> str:
        existing = self.state.get("connection_key")
        if isinstance(existing, str) and existing.strip():
            return existing.strip()
        created = self.api.create_connection(display_name=self.config.display_name)
        if created.get("ok") is not True:
            raise BridgeError(str((created.get("error") or {}).get("message") or "connection creation failed"))
        connection_key = created.get("connection_key")
        if not isinstance(connection_key, str) or not connection_key.strip():
            raise BridgeError("connection creation did not return connection_key")
        self.state["connection_key"] = connection_key.strip()
        self._save()
        return connection_key.strip()

    def _message_routes(self) -> dict[str, dict[str, Any]]:
        routes = self.state.get("message_routes")
        if not isinstance(routes, dict):
            routes = {}
            self.state["message_routes"] = routes
        normalized: dict[str, dict[str, Any]] = {}
        for key, value in routes.items():
            if isinstance(key, str) and isinstance(value, dict):
                normalized[key] = dict(value)
        return normalized

    def _save(self) -> None:
        self.state["schema_version"] = SCHEMA_VERSION
        self.state_store.save(self.state)


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "connection_key": None,
        "target_identity_id": None,
        "allowed_senders": [],
        "seen_inbound_keys": [],
        "sent_outbound_event_ids": [],
        "message_routes": {},
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(row) for row in value if isinstance(row, (str, int)) and str(row)]


def _normalize_sender(value: Any) -> str:
    text = str(value or "").strip()
    return text.lower() if "@" in text else text


def _actor_is_reachable(payload: dict[str, Any], target_identity_id: str) -> bool:
    actors = payload.get("actors") if isinstance(payload.get("actors"), list) else []
    blocked_statuses = {"offline", "registered_offline", "inactive", "unreachable", "target_not_online"}
    for row in actors:
        if not isinstance(row, dict) or row.get("identity_id") != target_identity_id:
            continue
        status = row.get("reachability_status")
        return not (isinstance(status, str) and status in blocked_statuses)
    return False


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


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


def _inbound_key(row: dict[str, Any]) -> str:
    guid = row.get("guid")
    if isinstance(guid, str) and guid.strip():
        return f"guid:{guid.strip()}"
    for field in ("rowid", "row_id", "id"):
        value = row.get(field)
        if isinstance(value, (str, int)) and str(value).strip():
            return f"{field}:{str(value).strip()}"
    raise BridgeError("inbound iMessage row is missing guid or rowid")


def _route_from_row(row: dict[str, Any], *, sender: str) -> dict[str, Any]:
    route: dict[str, Any] = {"sender": sender}
    for field in ("chat_id", "chat_identifier", "chat_guid"):
        value = row.get(field)
        if isinstance(value, (str, int)) and str(value).strip():
            route[field] = str(value).strip()
    return route


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BuddySwitch iMessage adapter")
    subparsers = parser.add_subparsers(dest="command", required=True)
    bridge = subparsers.add_parser("bridge", help="Run the local iMessage bridge")
    bridge.add_argument("--server", required=True)
    bridge.add_argument("--target-identity-id", required=True)
    bridge.add_argument("--allow-sender", action="append", default=[])
    bridge.add_argument("--state-path", type=Path)
    bridge.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    bridge.add_argument("--imsg-bin", default="imsg")
    bridge.add_argument("--poll-once", action="store_true")
    bridge.add_argument("--wait-ms", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv if argv is not None else sys.argv[1:]))
    if args.command != "bridge":
        raise BridgeError(f"unsupported command: {args.command}")
    if not args.allow_sender:
        raise BridgeError("imessage bridge requires at least one --allow-sender")
    config = BridgeConfig(
        server=args.server,
        target_identity_id=args.target_identity_id,
        allow_senders=tuple(args.allow_sender),
        state_path=args.state_path,
        display_name=args.display_name,
        imsg_bin=args.imsg_bin,
    )
    bridge = ImessageBridge(config=config)
    bridge.ensure_ready()
    if args.poll_once:
        print(json.dumps(bridge.poll_outbound_once(wait_ms=max(args.wait_ms, 0)), ensure_ascii=True))
        return 0
    bridge.run_forever()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BridgeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
