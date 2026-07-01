#!/usr/bin/env python3
"""Shared Chrome DevTools browser-session page gate helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import sys
import subprocess
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPTS_DIR.parent
ROOT = SCRIPTS_ROOT.parent
for candidate in (SCRIPTS_ROOT, SCRIPTS_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from env import cdp_browser_lifecycle as browser_lifecycle


BROWSER_PAGE_LIMIT = 10
BROWSER_PAGE_HINT_THRESHOLD = 5
BROWSER_PAGE_HINT_TEMPLATE = "Browser pages: {count}/10. Reuse or close pages before opening many more."
BROWSER_PAGE_LIMIT_BLOCK_TEXT = (
    "Blocked: browser page limit reached (10/10). Close or reuse existing pages, then retry opening this URL."
)

BrowserPageGateKind = Literal["allow", "reuse", "block", "verification_failed"]
BrowserSessionOpenKind = Literal[
    "opened",
    "reused",
    "blocked",
    "verification_failed",
    "open_failed",
    "registration_failed",
    "invalid_request",
]


@dataclass(frozen=True)
class BrowserPageOpenGate:
    kind: BrowserPageGateKind
    target_url: str
    page_count: int | None
    page_limit: int = BROWSER_PAGE_LIMIT
    projected_page_count: int | None = None
    target_id: str | None = None
    message: str | None = None

    def hint_text(self) -> str | None:
        if self.kind != "allow" or self.projected_page_count is None:
            return None
        if self.projected_page_count < BROWSER_PAGE_HINT_THRESHOLD:
            return None
        return BROWSER_PAGE_HINT_TEMPLATE.format(count=self.projected_page_count)


@dataclass(frozen=True)
class BrowserSessionOpenResult:
    kind: BrowserSessionOpenKind
    target_url: str
    page_count: int | None
    projected_page_count: int | None = None
    target_id: str | None = None
    page_opened: bool = False
    page_reused: bool = False
    idle_refreshed: bool = False
    idle_seconds: int | None = None
    idle_expires_at: str | None = None
    message: str | None = None


class BrowserPageSnapshotError(RuntimeError):
    pass


class BrowserSessionError(RuntimeError):
    pass


def shared_root_for_instance_root(instance_root: Path) -> Path:
    root = Path(instance_root)
    if root.name.startswith("act-") and root.parent.name == "instances":
        return root.parent.parent
    raise BrowserSessionError(f"cannot derive shared root from instance root: {root}")


def launcher_env_for_instance_root(instance_root: Path, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    shared_root = shared_root_for_instance_root(Path(instance_root))
    env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
    env.setdefault("BUDDYSWITCH_SOURCE_HOME", str(shared_root.parent))
    env.setdefault("BUDDYSWITCH_REPO_ROOT", str(ROOT))
    return env


def browser_url_from_instance_payload(instance_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    port = instance_payload.get("browser_port")
    if port is None:
        return None, "browser URL is not recorded"
    if isinstance(port, bool) or not isinstance(port, int):
        return None, f"invalid browser port: {port}"
    if port < 1 or port > 65535:
        return None, f"invalid browser port: {port}"
    return f"http://127.0.0.1:{port}", None


def _read_instance_payload(instance_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((Path(instance_root) / "instance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserSessionError(f"failed to read instance browser state: {exc}") from exc
    if not isinstance(payload, dict):
        raise BrowserSessionError("failed to read instance browser state: instance JSON was not an object")
    return payload


def browser_url_from_instance_root(instance_root: Path) -> tuple[str | None, str | None]:
    return browser_url_from_instance_payload(_read_instance_payload(Path(instance_root)))


def ensure_browser_url_for_instance(*, instance_root: Path, actor_id: str) -> str:
    root = Path(instance_root)
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise BrowserSessionError("actor_id is required to ensure browser URL")
    current_url, current_reason = browser_url_from_instance_root(root)
    if current_url is None and current_reason and current_reason.startswith("invalid browser port"):
        raise BrowserSessionError(current_reason)
    override = os.environ.get("BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND")
    if override:
        command = shlex.split(override) + [str(root)]
    else:
        command = [str(ROOT / "buddyswitch-codex"), "env", "browser", "ensure", "--instance", actor_id.strip()]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=launcher_env_for_instance_root(root),
            text=True,
            capture_output=True,
            check=False,
            timeout=30.0,
        )
    except subprocess.TimeoutExpired as exc:
        raise BrowserSessionError("browser ensure timed out") from exc
    except OSError as exc:
        raise BrowserSessionError(f"browser ensure failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit status {completed.returncode}"
        raise BrowserSessionError(detail)
    browser_url, reason = browser_url_from_instance_root(root)
    if browser_url is None:
        raise BrowserSessionError(reason or "instance browser URL is missing after ensure")
    return browser_url


def _read_target_list(browser_url: str, timeout_seconds: float) -> list[Any]:
    list_url = f"{browser_url.rstrip('/')}/json/list"
    request = Request(list_url, method="GET")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise BrowserPageSnapshotError(f"Chrome DevTools returned HTTP {exc.code} for /json/list") from exc
    except (URLError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserPageSnapshotError(f"failed to read Chrome DevTools /json/list: {exc}") from exc
    if not isinstance(payload, list):
        raise BrowserPageSnapshotError("Chrome DevTools /json/list did not return a list")
    return payload


def _target_id(target: dict[str, Any]) -> str | None:
    for key in ("id", "targetId"):
        value = target.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _page_targets(targets: list[Any]) -> list[dict[str, Any]]:
    return [target for target in targets if isinstance(target, dict) and target.get("type") == "page"]


def evaluate_page_open_gate(
    browser_url: str,
    target_url: str,
    timeout_seconds: float = 3.0,
) -> BrowserPageOpenGate:
    try:
        page_targets = _page_targets(_read_target_list(browser_url, timeout_seconds))
    except BrowserPageSnapshotError as exc:
        return BrowserPageOpenGate(
            kind="verification_failed",
            target_url=target_url,
            page_count=None,
            projected_page_count=None,
            message=f"Browser page-count verification failed: {exc}",
        )

    page_count = len(page_targets)
    for target in page_targets:
        if target.get("url") == target_url:
            return BrowserPageOpenGate(
                kind="reuse",
                target_url=target_url,
                page_count=page_count,
                projected_page_count=page_count,
                target_id=_target_id(target),
                message="Browser page already open; no new page was opened.",
            )

    if page_count >= BROWSER_PAGE_LIMIT:
        return BrowserPageOpenGate(
            kind="block",
            target_url=target_url,
            page_count=page_count,
            projected_page_count=page_count,
            message=BROWSER_PAGE_LIMIT_BLOCK_TEXT,
        )

    return BrowserPageOpenGate(
        kind="allow",
        target_url=target_url,
        page_count=page_count,
        projected_page_count=page_count + 1,
    )


def _sanitize_browser_message(message: object, browser_url: str) -> str:
    text = str(message)
    if browser_url:
        text = text.replace(browser_url, "browser endpoint")
    return text


def _idle_fields(idle_result: dict[str, Any]) -> dict[str, Any]:
    idle_seconds = idle_result.get("idle_seconds")
    idle_expires_at = idle_result.get("idle_expires_at")
    return {
        "idle_refreshed": idle_result.get("idle_refreshed") is True,
        "idle_seconds": idle_seconds if isinstance(idle_seconds, int) and not isinstance(idle_seconds, bool) else None,
        "idle_expires_at": idle_expires_at if isinstance(idle_expires_at, str) and idle_expires_at.strip() else None,
    }


def open_or_reuse_page(*, instance_root: Path, browser_url: str, target_url: str) -> BrowserSessionOpenResult:
    normalized_url = target_url.strip() if isinstance(target_url, str) else ""
    if not normalized_url:
        return BrowserSessionOpenResult(
            kind="invalid_request",
            target_url="",
            page_count=None,
            message="target_url must be a non-empty string",
        )

    gate = evaluate_page_open_gate(browser_url, normalized_url)
    if gate.kind == "verification_failed":
        return BrowserSessionOpenResult(
            kind="verification_failed",
            target_url=normalized_url,
            page_count=gate.page_count,
            projected_page_count=gate.projected_page_count,
            message=_sanitize_browser_message(gate.message or "Browser page-count verification failed.", browser_url),
        )
    if gate.kind == "block":
        return BrowserSessionOpenResult(
            kind="blocked",
            target_url=normalized_url,
            page_count=gate.page_count,
            projected_page_count=gate.projected_page_count,
            message=gate.message or BROWSER_PAGE_LIMIT_BLOCK_TEXT,
        )
    if gate.kind == "reuse":
        target_id = gate.target_id
        if not isinstance(target_id, str) or not target_id.strip():
            return BrowserSessionOpenResult(
                kind="verification_failed",
                target_url=normalized_url,
                page_count=gate.page_count,
                projected_page_count=gate.projected_page_count,
                message="Browser page-count verification failed: matching page target is missing target id",
            )
        try:
            idle_result = browser_lifecycle.refresh_current_page_idle(
                instance_root=Path(instance_root),
                target_id=target_id,
                target_url=normalized_url,
            )
        except Exception as exc:
            return BrowserSessionOpenResult(
                kind="registration_failed",
                target_url=normalized_url,
                page_count=gate.page_count,
                projected_page_count=gate.projected_page_count,
                target_id=target_id,
                page_reused=True,
                message=_sanitize_browser_message(exc, browser_url),
            )
        return BrowserSessionOpenResult(
            kind="reused",
            target_url=normalized_url,
            page_count=gate.page_count,
            projected_page_count=gate.projected_page_count,
            target_id=target_id,
            page_reused=True,
            **_idle_fields(idle_result),
        )

    try:
        target_id = browser_lifecycle.create_background_page_target(
            browser_url=browser_url,
            target_url=normalized_url,
        )
    except Exception as exc:
        return BrowserSessionOpenResult(
            kind="open_failed",
            target_url=normalized_url,
            page_count=gate.page_count,
            projected_page_count=gate.projected_page_count,
            message=_sanitize_browser_message(exc, browser_url),
        )

    try:
        idle_result = browser_lifecycle.refresh_current_page_idle(
            instance_root=Path(instance_root),
            target_id=target_id,
            target_url=normalized_url,
        )
    except Exception as exc:
        close_message = ""
        try:
            close_result = browser_lifecycle.close_page_target(browser_url, target_id)
            close_message = f" Closed browser target: {json.dumps(close_result, ensure_ascii=True)}"
        except Exception as close_exc:
            close_message = f" Failed to close browser target {target_id}: {_sanitize_browser_message(close_exc, browser_url)}"
        return BrowserSessionOpenResult(
            kind="registration_failed",
            target_url=normalized_url,
            page_count=gate.page_count,
            projected_page_count=gate.projected_page_count,
            target_id=target_id,
            message=f"{_sanitize_browser_message(exc, browser_url)}{close_message}",
        )

    return BrowserSessionOpenResult(
        kind="opened",
        target_url=normalized_url,
        page_count=gate.page_count,
        projected_page_count=gate.projected_page_count,
        target_id=target_id,
        page_opened=True,
        **_idle_fields(idle_result),
    )
