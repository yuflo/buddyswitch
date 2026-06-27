#!/usr/bin/env python3
"""HTTP projection for the BuddySwitch Central IM contract."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, urlsplit

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from env.services import messages as message_service  # noqa: E402


JsonResponse = tuple[int, dict[str, Any]]


class ImHttpRouter:
    def __init__(
        self,
        *,
        actor_lister: Callable[[str | None], list[dict[str, Any]]],
        wake_actor: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._actor_lister = actor_lister
        self._wake_actor = wake_actor

    def handle(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str] | None,
    ) -> JsonResponse:
        parsed = urlsplit(path)
        route = parsed.path
        query = parse_qs(parsed.query)
        normalized_method = method.upper()
        if normalized_method == "POST" and route == "/api/im/connections":
            try:
                payload = _json_body(body)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": str(exc)}}
            result = message_service.create_external_connection(display_name=str(payload.get("display_name") or ""))
            return (200 if result.get("ok") is True else 400), result
        if not route.startswith("/api/im/"):
            return _not_found()
        if not _is_authenticated_im_route(normalized_method, route):
            return _not_found()

        auth = self._authenticate(headers)
        if auth.get("ok") is not True:
            return 401, auth
        participant = auth["participant"]
        connection = auth["connection"]

        if normalized_method == "GET" and route == "/api/im/actors":
            role_id = _first_query_value(query, "role_id")
            actors = []
            for row in self._actor_lister(role_id):
                actor_address = row.get("actor_address") if isinstance(row, dict) else None
                if not isinstance(actor_address, dict):
                    continue
                status = row.get("status") if isinstance(row.get("status"), str) else "online"
                actors.append(
                    {
                        "participant": {"kind": "actor", "actor_address": dict(actor_address)},
                        "reachability_status": status,
                    }
                )
            return 200, {"ok": True, "actors": actors, "count": len(actors)}

        if normalized_method == "POST" and route == "/api/im/messages":
            try:
                payload = _json_body(body)
                target = _object_field(payload, "to")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": str(exc)}}
            if "from" in payload:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "from is derived from authentication"}}
            result = message_service.send_external_connection_message(
                connection=connection,
                to=target,
                content=str(payload.get("content") or ""),
                reply_to=payload.get("reply_to") if payload.get("reply_to") is not None else None,
                wake_actor=self._wake_actor,
            )
            return (200 if result.get("ok") is True else 400), result

        if normalized_method == "GET" and route == "/api/im/events":
            if "cursor" in query:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "cursor is internal to the connection"}}
            result = message_service.read_external_connection_events(
                connection=connection,
                limit=_int_query_value(query, "limit", 50),
                wait_ms=_int_query_value(query, "wait_ms", 0),
            )
            return 200, result

        if normalized_method == "GET" and route == "/api/im/conversations/direct":
            kind = _first_query_value(query, "kind") or ""
            if kind != "actor":
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "kind=actor is required"}}
            role_id = _first_query_value(query, "role_id") or ""
            actor_id = _first_query_value(query, "actor_id") or ""
            result = message_service.get_im_direct_conversation(
                participant=participant,
                target={"kind": "actor", "actor_address": {"role_id": role_id, "actor_id": actor_id}},
                limit=_int_query_value(query, "limit", 20),
            )
            return (200 if result.get("ok") is True else 404), result

        message_prefix = "/api/im/messages/"
        if route.startswith(message_prefix):
            suffix = route[len(message_prefix) :]
            if normalized_method == "GET" and suffix.endswith("/replies"):
                message_id = suffix[: -len("/replies")]
                result = message_service.list_im_replies(participant=participant, message_id=message_id)
                return (200 if result.get("ok") is True else 404), result
            if normalized_method == "PATCH" and suffix.endswith("/disposition"):
                message_id = suffix[: -len("/disposition")]
                payload = _json_body(body)
                result = message_service.update_im_disposition(
                    participant=participant,
                    message_id=message_id,
                    disposition=str(payload.get("disposition") or ""),
                    reason=payload.get("reason") if payload.get("reason") is not None else None,
                )
                return (200 if result.get("ok") is True else 400), result
            if normalized_method == "GET" and "/" not in suffix:
                result = message_service.get_im_message(participant=participant, message_id=suffix)
                return (200 if result.get("ok") is True else 404), result

        return _not_found()

    def _authenticate(self, headers: Mapping[str, str] | None) -> dict[str, Any]:
        auth_value = ""
        if headers is not None:
            auth_value = headers.get("Authorization") or headers.get("authorization") or ""
        prefix = "Bearer "
        if not auth_value.startswith(prefix):
            return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "Authorization: Bearer connection_key is required"}}
        return message_service.authenticate_external_connection_key(auth_value[len(prefix) :])


def _json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _object_field(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if not values:
        return None
    return values[0]


def _int_query_value(query: dict[str, list[str]], name: str, default: int) -> int:
    raw = _first_query_value(query, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _is_authenticated_im_route(method: str, route: str) -> bool:
    if method == "GET" and route in {"/api/im/actors", "/api/im/events", "/api/im/conversations/direct"}:
        return True
    if method == "POST" and route == "/api/im/messages":
        return True
    message_prefix = "/api/im/messages/"
    if not route.startswith(message_prefix):
        return False
    suffix = route[len(message_prefix) :]
    if method == "GET" and suffix.endswith("/replies"):
        return True
    if method == "PATCH" and suffix.endswith("/disposition"):
        return True
    return method == "GET" and "/" not in suffix


def _not_found() -> JsonResponse:
    return 404, {"ok": False, "error": {"code": "NOT_FOUND", "message": "API route not found."}}


if __name__ == "__main__":
    raise SystemExit("im_http_router is not a standalone command")
