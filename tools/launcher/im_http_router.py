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

import external_im_session  # noqa: E402


JsonResponse = tuple[int, dict[str, Any]]


class ImHttpRouter:
    def __init__(
        self,
        *,
        actor_lister: Callable[[str | None], list[dict[str, Any]]],
        wake_actor: Callable[[dict[str, Any]], dict[str, Any]],
        im_session: Any | None = None,
    ) -> None:
        self._session = im_session or external_im_session.ExternalImSession(
            actor_lister=actor_lister,
            wake_actor=wake_actor,
        )

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
            result = self._session.create_connection(display_name=str(payload.get("display_name") or ""))
            return (200 if result.get("ok") is True else 400), result
        if not route.startswith("/api/im/"):
            return _not_found()
        if not _is_authenticated_im_route(normalized_method, route):
            return _not_found()

        auth = self._authenticate(headers)
        if auth.get("ok") is not True:
            return 401, auth
        connection = auth["connection"]

        if normalized_method == "GET" and route == "/api/im/actors":
            return 200, self._session.list_actors(role_id=_first_query_value(query, "role_id"))

        if normalized_method == "POST" and route == "/api/im/messages":
            try:
                payload = _json_body(body)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": str(exc)}}
            if "from" in payload:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "from is derived from authentication"}}
            result = self._session.send_message(
                connection=connection,
                target_identity_id=payload.get("target_identity_id"),
                content=str(payload.get("content") or ""),
                reply_to=payload.get("reply_to") if payload.get("reply_to") is not None else None,
            )
            return (200 if result.get("ok") is True else 400), result

        if normalized_method == "GET" and route == "/api/im/events":
            if "cursor" in query:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "cursor is internal to the connection"}}
            result = self._session.read_events(
                connection=connection,
                limit=_int_query_value(query, "limit", 50),
                wait_ms=_int_query_value(query, "wait_ms", 0),
            )
            return 200, result

        if normalized_method == "POST" and route == "/api/im/events/ack":
            try:
                payload = _json_body(body)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                return 400, {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": str(exc)}}
            result = self._session.ack_event(
                connection=connection,
                event_id=str(payload.get("event_id") or ""),
            )
            return (200 if result.get("ok") is True else 400), result

        if normalized_method == "GET" and route == "/api/im/conversations/direct":
            result = self._session.get_direct_conversation(
                connection=connection,
                identity_id=_first_query_value(query, "identity_id"),
                limit=_int_query_value(query, "limit", 20),
            )
            return _status_for_direct_conversation(result), result

        message_prefix = "/api/im/messages/"
        if route.startswith(message_prefix):
            suffix = route[len(message_prefix) :]
            if normalized_method == "GET" and suffix.endswith("/replies"):
                message_id = suffix[: -len("/replies")]
                result = self._session.list_replies(connection=connection, message_id=message_id)
                return (200 if result.get("ok") is True else 404), result
            if normalized_method == "PATCH" and suffix.endswith("/disposition"):
                message_id = suffix[: -len("/disposition")]
                payload = _json_body(body)
                result = self._session.update_disposition(
                    connection=connection,
                    message_id=message_id,
                    disposition=str(payload.get("disposition") or ""),
                    reason=payload.get("reason") if payload.get("reason") is not None else None,
                )
                return (200 if result.get("ok") is True else 400), result
            if normalized_method == "GET" and "/" not in suffix:
                result = self._session.get_message(connection=connection, message_id=suffix)
                return (200 if result.get("ok") is True else 404), result

        return _not_found()

    def _authenticate(self, headers: Mapping[str, str] | None) -> dict[str, Any]:
        auth_value = ""
        if headers is not None:
            auth_value = headers.get("Authorization") or headers.get("authorization") or ""
        prefix = "Bearer "
        if not auth_value.startswith(prefix):
            return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "Authorization: Bearer connection_key is required"}}
        return self._session.authenticate(auth_value[len(prefix) :])


def _json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


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


def _status_for_direct_conversation(result: dict[str, Any]) -> int:
    if result.get("ok") is True:
        return 200
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    if error.get("code") == "E_IM_NOT_FOUND":
        return 404
    return 400


def _is_authenticated_im_route(method: str, route: str) -> bool:
    if method == "GET" and route in {"/api/im/actors", "/api/im/events", "/api/im/conversations/direct"}:
        return True
    if method == "POST" and route in {"/api/im/messages", "/api/im/events/ack"}:
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
