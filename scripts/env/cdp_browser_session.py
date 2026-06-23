#!/usr/bin/env python3
"""Shared Chrome DevTools browser-session page gate helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


BROWSER_PAGE_LIMIT = 16
BROWSER_PAGE_HINT_THRESHOLD = 8
BROWSER_PAGE_HINT_TEMPLATE = "Browser pages: {count}/16. Reuse or close pages before opening many more."
BROWSER_PAGE_LIMIT_BLOCK_TEXT = (
    "Blocked: browser page limit reached (16/16). Close or reuse existing pages, then retry opening this URL."
)

BrowserPageGateKind = Literal["allow", "reuse", "block", "verification_failed"]


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


class BrowserPageSnapshotError(RuntimeError):
    pass


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
