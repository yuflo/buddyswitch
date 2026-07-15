"""Tests for the BuddySwitch local web management API."""

from __future__ import annotations

import importlib
import inspect
import io
import json
import os
import sys
import threading
import tempfile
import time
import unittest
from collections.abc import Mapping
from unittest import mock
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

from tests.support.runtime import RuntimeWorkspaceTestCase


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
WEB_MANAGEMENT_PATH = ROOT / "tools" / "launcher" / "web_management.py"
WEB_MANAGEMENT = importlib.import_module("web_management")
NO_PROXY_OPENER = build_opener(ProxyHandler({}))

from env.services import messages as message_service  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402
import actor_capability  # noqa: E402


def save_test_actor_identity_profile(*, actor_id: str, role_id: str) -> None:
    identity_repo.save_actor_identity_profile(
        {
            "identity": {"id": actor_id, "type": "actor"},
            "role_id": role_id,
        }
    )


def _restore_env_value(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def wait_for_condition(predicate: Callable[[], bool], *, timeout_seconds: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def wait_for_operation_status(
    service: object,
    operation_id: str,
    expected_status: str,
    *,
    timeout_seconds: float = 2.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, payload = service.handle_api("GET", f"/api/operations/{operation_id}", b"")
        assert status == 200
        last_payload = payload
        operation = payload["operation"]
        if operation["status"] == expected_status:
            return operation
        time.sleep(0.01)
    raise AssertionError(f"operation {operation_id} did not reach {expected_status}: {last_payload!r}")


def active_status(actor_id: str, thread_id: str, thread_status: str) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "role": "pm",
        "status": "active",
        "workspace_dir": f"/tmp/shared/instances/{actor_id}/workspace",
        "browser_port": 9222,
        "updated_at": "2026-05-25T10:00:00Z",
        "thread_id": thread_id,
        "app_server": {"healthy": True},
        "daemon": {"connected": True},
        "runtime_broker": {"connected": True},
        "thread": {"status": thread_status, "raw": {}},
    }


def write_web_capability_instance(
    shared_root: Path,
    *,
    actor_id: str = "act-pm-demo",
    role: str = "pm",
    capability_config: dict[str, object] | None = None,
) -> Path:
    instance_root = shared_root / "instances" / actor_id
    instance_root.mkdir(parents=True, exist_ok=True)
    instance_json = instance_root / "instance.json"
    instance_json.write_text(
        json.dumps(
            {
                "actor_id": actor_id,
                "role": role,
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(instance_root / "workspace"),
                "thread_id": "thread-main",
                "browser_port": 9222,
                "updated_at": "2026-07-08T00:00:00Z",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    default_capability_config = {
        "schema_version": 1,
        "catalog_version": 1,
        "parent": {"level": "balanced", "model": "gpt-5.6-terra", "effort": "high"},
        "side": {"level": "fast", "model": "gpt-5.6-luna", "effort": "xhigh"},
    }
    payload = capability_config if capability_config is not None else default_capability_config
    (instance_root / "capability-config.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return instance_json


OPEN_TUI_HEADERS = {
    "Content-Type": "application/json",
    "X-BuddySwitch-Web": "1",
    "Host": "127.0.0.1:8765",
    "Origin": "http://127.0.0.1:8765",
}


class FakeTerminalOpener:
    def __init__(self, error: Exception | None = None) -> None:
        self.commands: list[str] = []
        self.error = error

    def open(self, command: str) -> None:
        self.commands.append(command)
        if self.error is not None:
            raise self.error


def host_control_error(
    code: str,
    message: str,
    *,
    returncode: int = 1,
    timed_out: bool = False,
) -> WEB_MANAGEMENT.host_control_module.HostControlError:
    return WEB_MANAGEMENT.host_control_module.HostControlError(
        code,
        message,
        returncode=returncode,
        timed_out=timed_out,
    )


def copy_host_payload(payload: object) -> object:
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, list):
        return [dict(row) if isinstance(row, dict) else row for row in payload]
    return payload


class RecordingHostControl:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.roles_response: list[dict[str, object]] = [
            {"id": "pm", "label": "PM", "scope": "product"}
        ]
        self.list_instances_response: list[dict[str, object]] = []
        self.status_response: dict[str, object] = active_status("act-pm-demo", "thread-main", "idle")
        self.stop_response: dict[str, object] = {"actor_id": "act-pm-demo", "status": "inactive"}
        self.responses: dict[tuple[str, tuple[object, ...]], object] = {}
        self.errors: dict[tuple[str, tuple[object, ...]], WEB_MANAGEMENT.host_control_module.HostControlError] = {}
        self.blockers: dict[tuple[str, tuple[object, ...]], threading.Event] = {}

    def set_response(self, operation: str, args: tuple[object, ...], response: object) -> None:
        self.responses[(operation, args)] = response

    def set_error(
        self,
        operation: str,
        args: tuple[object, ...],
        error: WEB_MANAGEMENT.host_control_module.HostControlError,
    ) -> None:
        self.errors[(operation, args)] = error

    def block(self, operation: str, args: tuple[object, ...], event: threading.Event) -> None:
        self.blockers[(operation, args)] = event

    def _record(self, operation: str, args: tuple[object, ...], fallback: object) -> object:
        key = (operation, args)
        self.calls.append(key)
        blocker = self.blockers.get(key)
        if blocker is not None:
            blocker.wait(timeout=5)
        error = self.errors.get(key)
        if error is not None:
            raise error
        if key in self.responses:
            return copy_host_payload(self.responses[key])
        if callable(fallback):
            return copy_host_payload(fallback())
        return copy_host_payload(fallback)

    def roles(self) -> list[dict[str, object]]:
        return self._record("roles", (), self.roles_response)  # type: ignore[return-value]

    def start(self, role_id: str) -> dict[str, object]:
        actor_id = f"act-{role_id}-demo"
        return self._record(
            "start",
            (role_id,),
            {
                "actor_id": actor_id,
                "role": role_id,
                "workspace_dir": f"/tmp/shared/instances/{actor_id}/workspace",
                "project_workspace_dir": "/tmp/shared/projects/app",
                "instance_record": f"/tmp/shared/instances/{actor_id}/instance.json",
            },
        )  # type: ignore[return-value]

    def list_instances(self, role_id: str | None = None) -> list[dict[str, object]]:
        return self._record("list_instances", (role_id,), self.list_instances_response)  # type: ignore[return-value]

    def status(self, actor_id: str) -> dict[str, object]:
        return self._record("status", (actor_id,), self.status_response)  # type: ignore[return-value]

    def clear(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "clear",
            (actor_id,),
            {"actor_id": actor_id, "previous_thread_id": "thread-old", "thread_id": "thread-new"},
        )  # type: ignore[return-value]

    def resume(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "resume",
            (actor_id,),
            {"actor_id": actor_id, "thread_id": "thread-main", "status": "active"},
        )  # type: ignore[return-value]

    def stop(self, actor_id: str) -> dict[str, object]:
        return self._record("stop", (actor_id,), self.stop_response)  # type: ignore[return-value]

    def delete(self, actor_id: str) -> dict[str, object]:
        return self._record("delete", (actor_id,), {"actor_id": actor_id, "deleted": True})  # type: ignore[return-value]

    def interrupt(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "interrupt",
            (actor_id,),
            {"actor_id": actor_id, "thread_id": "thread-main", "turn_id": "turn-main"},
        )  # type: ignore[return-value]

    def compact(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "compact",
            (actor_id,),
            {"actor_id": actor_id, "thread_id": "thread-main", "started": True},
        )  # type: ignore[return-value]

    def capabilities_get(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "capabilities_get",
            (actor_id,),
            lambda: WEB_MANAGEMENT.host_control_module.HostControl(repo_root=ROOT).capabilities_get(actor_id),
        )  # type: ignore[return-value]

    def capabilities_set(self, actor_id: str, parent: str, side: str) -> dict[str, object]:
        return self._record(
            "capabilities_set",
            (actor_id, parent, side),
            lambda: WEB_MANAGEMENT.host_control_module.HostControl(repo_root=ROOT).capabilities_set(actor_id, parent, side),
        )  # type: ignore[return-value]


class WebManagementServerTestCase(unittest.TestCase):
    def _start_server(
        self,
        host_control: RecordingHostControl | None = None,
        *,
        terminal_opener: Callable[[str], None] | None = None,
        platform_name: str | None = None,
    ) -> tuple[RecordingHostControl, str]:
        control = host_control or RecordingHostControl()
        service_kwargs: dict[str, object] = {}
        if terminal_opener is not None:
            service_kwargs["terminal_opener"] = terminal_opener
        if platform_name is not None:
            service_kwargs["platform_name"] = platform_name
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=control,
            **service_kwargs,
        )
        server = WEB_MANAGEMENT.create_server("127.0.0.1", 0, service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return control, f"http://127.0.0.1:{server.server_port}"

    @staticmethod
    def _request_json(
        base_url: str,
        *,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        raw_body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, object]]:
        request_headers = dict(headers or {})
        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        elif raw_body is not None:
            data = raw_body
        request = Request(base_url + quote(path, safe="/:?=&"), data=data, headers=request_headers, method=method)
        try:
            with NO_PROXY_OPENER.open(request, timeout=5) as response:
                return int(response.status), json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return int(exc.code), json.loads(exc.read().decode("utf-8"))

    @staticmethod
    def _request_text(base_url: str, *, method: str, path: str) -> tuple[int, str]:
        request = Request(base_url + quote(path, safe="/:?=&"), method=method)
        try:
            with NO_PROXY_OPENER.open(request, timeout=5) as response:
                return int(response.status), response.read().decode("utf-8")
        except HTTPError as exc:
            return int(exc.code), exc.read().decode("utf-8")

    def _wait_for_http_operation_status(
        self,
        base_url: str,
        operation_id: str,
        expected_status: str,
        *,
        timeout_seconds: float = 2.0,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout_seconds
        last_payload: dict[str, object] | None = None
        while time.monotonic() < deadline:
            status, payload = self._request_json(base_url, method="GET", path=f"/api/operations/{operation_id}")
            self.assertEqual(status, 200)
            last_payload = payload
            operation = payload["operation"]
            if operation["status"] == expected_status:
                return operation
            time.sleep(0.01)
        raise AssertionError(f"operation {operation_id} did not reach {expected_status}: {last_payload!r}")

__all__ = [name for name in globals() if not name.startswith('__')]
