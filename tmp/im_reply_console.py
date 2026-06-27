#!/usr/bin/env python3
"""Interactive external-user Central IM smoke console."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

try:
    import readline
except Exception:  # pragma: no cover - depends on local Python build.
    readline = None  # type: ignore[assignment]


def request_json(
    *,
    base_url: str,
    method: str,
    path: str,
    connection_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if connection_key:
        headers["Authorization"] = f"Bearer {connection_key}"
    request = Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            parsed = json.loads(exc.read().decode("utf-8"))
        except Exception:
            parsed = {"ok": False, "error": {"message": str(exc)}}
    except (URLError, TimeoutError) as exc:
        parsed = {"ok": False, "error": {"message": str(exc)}}
    if not isinstance(parsed, dict):
        return {"ok": False, "error": {"message": "server returned non-object JSON"}}
    return parsed


def require_ok(payload: dict[str, Any], action: str) -> dict[str, Any]:
    if payload.get("ok") is True:
        return payload
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    message = error.get("message") if isinstance(error.get("message"), str) else f"{action} failed"
    raise RuntimeError(message)


def actor_label(participant: dict[str, Any]) -> str:
    address = participant.get("actor_address") if isinstance(participant.get("actor_address"), dict) else {}
    role_id = address.get("role_id") if isinstance(address.get("role_id"), str) else ""
    actor_id = address.get("actor_id") if isinstance(address.get("actor_id"), str) else ""
    return f"{role_id}/{actor_id}" if role_id and actor_id else "actor"


def discover_actors(base_url: str, connection_key: str, role: str | None) -> list[dict[str, str]]:
    query = f"?{urlencode({'role_id': role})}" if role else ""
    payload = require_ok(
        request_json(base_url=base_url, method="GET", path=f"/api/im/actors{query}", connection_key=connection_key),
        "actor discovery",
    )
    actors: list[dict[str, str]] = []
    for row in payload.get("actors") if isinstance(payload.get("actors"), list) else []:
        if not isinstance(row, dict) or row.get("reachability_status") != "online":
            continue
        participant = row.get("participant") if isinstance(row.get("participant"), dict) else {}
        address = participant.get("actor_address") if isinstance(participant.get("actor_address"), dict) else {}
        role_id = address.get("role_id")
        actor_id = address.get("actor_id")
        if isinstance(role_id, str) and isinstance(actor_id, str) and role_id and actor_id:
            actors.append({"role_id": role_id, "actor_id": actor_id})
    return actors


def choose_actor(base_url: str, connection_key: str, role: str | None, actor_id: str | None) -> dict[str, str]:
    if role and actor_id:
        return {"role_id": role, "actor_id": actor_id}

    actors = discover_actors(base_url, connection_key, role)
    if actor_id:
        actors = [actor for actor in actors if actor["actor_id"] == actor_id]
    if len(actors) == 1:
        return actors[0]
    if not actors:
        raise RuntimeError("no matching online actor found")

    print("online actors:")
    for index, actor in enumerate(actors, start=1):
        print(f"  {index}. {actor['role_id']}/{actor['actor_id']}")
    while True:
        raw = input("select actor number: ").strip()
        try:
            selected = int(raw)
        except ValueError:
            print("enter a number from the list")
            continue
        if 1 <= selected <= len(actors):
            return actors[selected - 1]
        print("enter a number from the list")


def locked_print(print_lock: threading.Lock, text: str, *, preserve_input: bool = False) -> None:
    with print_lock:
        if preserve_input and readline is not None and sys.stdin.isatty() and sys.stdout.isatty():
            sys.stdout.write("\r\033[2K")
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")
            readline.redisplay()
        else:
            sys.stdout.write(text)
        sys.stdout.flush()


def poll_replies(
    *,
    base_url: str,
    connection_key: str,
    stop_event: threading.Event,
    print_lock: threading.Lock,
) -> None:
    while not stop_event.is_set():
        query = urlencode({"wait_ms": "15000"})
        payload = request_json(
            base_url=base_url,
            method="GET",
            path=f"/api/im/events?{query}",
            connection_key=connection_key,
            timeout=20.0,
        )
        if payload.get("ok") is not True:
            time.sleep(1.0)
            continue
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        for event in events:
            if not isinstance(event, dict) or event.get("type") != "message.created":
                continue
            message_id = event.get("message_id")
            if not isinstance(message_id, str) or not message_id:
                continue
            message_payload = request_json(
                base_url=base_url,
                method="GET",
                path=f"/api/im/messages/{quote(message_id)}",
                connection_key=connection_key,
            )
            if message_payload.get("ok") is not True:
                continue
            message = message_payload.get("message") if isinstance(message_payload.get("message"), dict) else {}
            sender = message.get("from") if isinstance(message.get("from"), dict) else {}
            if sender.get("kind") != "actor":
                continue
            content = message.get("content") if isinstance(message.get("content"), str) else ""
            reply_to = message.get("reply_to") if isinstance(message.get("reply_to"), str) else ""
            suffix = f" reply_to={reply_to}" if reply_to else ""
            locked_print(print_lock, f"[reply] {actor_label(sender)}{suffix}: {content}\n", preserve_input=True)


def load_profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_profile(path: Path, connection_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"connection_key": connection_key}, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def create_connection(base_url: str, profile_path: Path) -> str:
    created = require_ok(
        request_json(
            base_url=base_url,
            method="POST",
            path="/api/im/connections",
            payload={"display_name": "IM reply console"},
        ),
        "connection creation",
    )
    connection_key = str(created["connection_key"])
    save_profile(profile_path, connection_key)
    return connection_key


def load_or_create_connection(base_url: str, profile_path: Path) -> str:
    profile = load_profile(profile_path)
    connection_key = profile.get("connection_key")
    if isinstance(connection_key, str) and connection_key.startswith("imck-"):
        return connection_key
    return create_connection(base_url, profile_path)


def run(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile).expanduser()
    connection_key = load_or_create_connection(args.base_url, profile_path)
    try:
        target = choose_actor(args.base_url, connection_key, args.role, args.actor_id)
    except RuntimeError as exc:
        if "connection_key is invalid" not in str(exc):
            raise
        connection_key = create_connection(args.base_url, profile_path)
        target = choose_actor(args.base_url, connection_key, args.role, args.actor_id)
    print_lock = threading.Lock()
    print(f"target actor: {target['role_id']}/{target['actor_id']}")
    print(f"connection profile: {profile_path}")
    print("type a message and press Enter. commands: /quit, /help")

    stop_event = threading.Event()
    poller = threading.Thread(
        target=poll_replies,
        kwargs={
            "base_url": args.base_url,
            "connection_key": connection_key,
            "stop_event": stop_event,
            "print_lock": print_lock,
        },
        daemon=True,
    )
    poller.start()
    try:
        while True:
            try:
                text = input("> ")
            except EOFError:
                break
            if text.strip() == "/quit":
                break
            if text.strip() == "/help":
                print("commands: /quit exits; every other non-empty line sends a message")
                continue
            if not text.strip():
                continue
            try:
                sent = require_ok(
                    request_json(
                        base_url=args.base_url,
                        method="POST",
                        path="/api/im/messages",
                        connection_key=connection_key,
                        payload={
                            "to": {
                                "kind": "actor",
                                "actor_address": target,
                            },
                            "content": text,
                        },
                    ),
                    "send",
                )
            except RuntimeError as exc:
                locked_print(print_lock, f"[error] {exc}\n")
                continue
            message = sent.get("message") if isinstance(sent.get("message"), dict) else {}
            locked_print(
                print_lock,
                "[sent] "
                + str(message.get("id") or "")
                + f" delivery={sent.get('delivery_status')} wake={sent.get('wake_status')}\n",
            )
    finally:
        stop_event.set()
        poller.join(timeout=1.0)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="External-user Central IM reply smoke console.")
    parser.add_argument("--actor-id", help="Target actor id. Optional when exactly one online actor is discoverable.")
    parser.add_argument("--role", help="Target actor role id. Optional when exactly one online actor is discoverable.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="BuddySwitch web base URL.")
    parser.add_argument(
        "--profile",
        default=str(Path(__file__).with_name(".im_reply_console_profile.json")),
        help="Connection profile file. Stores only connection_key.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
