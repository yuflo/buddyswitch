#!/usr/bin/env python3
"""Shared Chrome DevTools browser lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPTS_DIR.parent
for candidate in (SCRIPTS_DIR, SCRIPTS_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from cdp_background_page import (  # noqa: E402
    CdpTargetError,
    _browser_version,
    _connect_websocket,
    _read_server_frame,
    _send_client_frame,
)
from env.tool_runtime import daemon_client  # noqa: E402


BROWSER_PAGE_TTL_SECONDS = 600
BROWSER_PAGE_EXPIRY_POLICY = "auto_close"
BROWSER_PAGE_EXPIRED_TRIGGER = "browser.page.expired"


class BrowserLifecycleError(RuntimeError):
    pass


def _target_id(target: dict[str, Any]) -> str | None:
    for key in ("id", "targetId"):
        value = target.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _page_targets(targets: list[Any]) -> list[dict[str, Any]]:
    return [target for target in targets if isinstance(target, dict) and target.get("type") == "page"]


def read_page_targets(browser_url: str, timeout_seconds: float = 3.0) -> list[dict[str, Any]]:
    list_url = f"{browser_url.rstrip('/')}/json/list"
    request = Request(list_url, method="GET")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise BrowserLifecycleError(f"Chrome DevTools returned HTTP {exc.code} for /json/list") from exc
    except (URLError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserLifecycleError(f"failed to read Chrome DevTools /json/list: {exc}") from exc
    if not isinstance(payload, list):
        raise BrowserLifecycleError("Chrome DevTools /json/list did not return a list")
    return _page_targets(payload)


def new_page_target_id(before_targets: list[Any], after_targets: list[Any]) -> str | None:
    before_ids = {
        target_id
        for target in _page_targets(before_targets)
        for target_id in [_target_id(target)]
        if target_id is not None
    }
    new_ids = [
        target_id
        for target in _page_targets(after_targets)
        for target_id in [_target_id(target)]
        if target_id is not None and target_id not in before_ids
    ]
    if len(new_ids) != 1:
        return None
    return new_ids[0]


def _send_browser_command(
    browser_url: str,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        version = _browser_version(browser_url, timeout_seconds)
        websocket_url = version.get("webSocketDebuggerUrl")
        if not isinstance(websocket_url, str) or not websocket_url.strip():
            raise BrowserLifecycleError("Chrome DevTools /json/version is missing webSocketDebuggerUrl")
        sock, buffer = _connect_websocket(websocket_url.strip(), timeout_seconds)
    except (CdpTargetError, OSError) as exc:
        raise BrowserLifecycleError(str(exc)) from exc
    try:
        request = {"id": 1, "method": method, "params": dict(params)}
        _send_client_frame(sock, json.dumps(request, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
        while True:
            opcode, payload = _read_server_frame(sock, timeout_seconds, buffer)
            if opcode == 0x8:
                raise BrowserLifecycleError("browser websocket closed before command response")
            if opcode == 0x9:
                _send_client_frame(sock, payload)
                continue
            if opcode != 0x1:
                continue
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BrowserLifecycleError("browser websocket returned invalid JSON") from exc
            if not isinstance(message, dict) or message.get("id") != 1:
                continue
            if "error" in message:
                error = message.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    raise BrowserLifecycleError(error["message"])
                raise BrowserLifecycleError(json.dumps(error, ensure_ascii=True))
            result = message.get("result")
            if not isinstance(result, dict):
                raise BrowserLifecycleError("browser command response missing result object")
            return result
    except CdpTargetError as exc:
        raise BrowserLifecycleError(str(exc)) from exc
    finally:
        try:
            sock.close()
        except OSError:
            pass


def close_page_target(browser_url: str, target_id: str, timeout_seconds: float = 3.0) -> dict[str, str]:
    if not isinstance(target_id, str) or not target_id.strip():
        raise BrowserLifecycleError("target_id must be a non-empty string")
    normalized_target_id = target_id.strip()
    targets = read_page_targets(browser_url, timeout_seconds=timeout_seconds)
    if normalized_target_id not in {_target_id(target) for target in targets}:
        return {"status": "already_gone", "target_id": normalized_target_id}
    _send_browser_command(
        browser_url,
        "Target.closeTarget",
        {"targetId": normalized_target_id},
        timeout_seconds,
    )
    return {"status": "closed", "target_id": normalized_target_id}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def register_browser_page_ttl(
    *,
    instance_root: Path,
    target_id: str,
    target_url: str,
    ttl_seconds: int = BROWSER_PAGE_TTL_SECONDS,
    expiry_policy: str = BROWSER_PAGE_EXPIRY_POLICY,
) -> dict[str, Any]:
    if not isinstance(target_id, str) or not target_id.strip():
        raise BrowserLifecycleError("target_id must be a non-empty string")
    if not isinstance(target_url, str) or not target_url.strip():
        raise BrowserLifecycleError("target_url must be a non-empty string")
    if expiry_policy not in {"auto_close", "notify"}:
        raise BrowserLifecycleError(f"unsupported expiry_policy: {expiry_policy}")
    now = _utc_now()
    payload = {
        "target_id": target_id.strip(),
        "target_url": target_url.strip(),
        "ttl_seconds": ttl_seconds,
        "expiry_policy": expiry_policy,
    }
    daemon_client.schedule_trigger(
        instance_root=Path(instance_root),
        delay_seconds=ttl_seconds,
        trigger_type=BROWSER_PAGE_EXPIRED_TRIGGER,
        payload=payload,
        source_context={"owner": "browser"},
    )
    return {
        "ttl_registered": True,
        "ttl_seconds": ttl_seconds,
        "expires_at": _format_utc(now + timedelta(seconds=ttl_seconds)),
        "expiry_policy": expiry_policy,
    }
