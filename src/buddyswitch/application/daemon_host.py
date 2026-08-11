"""Concrete App/Actor host capability supplied to Foundation Daemon."""

from __future__ import annotations

from types import TracebackType
from pathlib import Path
import sys
from typing import Any

from buddyswitch.foundation.daemon import contracts
from buddyswitch.launcher import actor_session, app_server


class AppNotificationClient:
    def __init__(self, context: contracts.DaemonContext) -> None:
        self._client = app_server.AppServerClient(
            context.socket_path,
            timeout_seconds=app_server.DEFAULT_RPC_TIMEOUT_SECONDS,
            client_name="buddyswitch_daemon",
            client_title="BuddySwitch Daemon",
        )

    def __enter__(self) -> "AppNotificationClient":
        try:
            self._client.__enter__()
        except app_server.AppServerError as exc:
            raise contracts.DaemonHostError(str(exc)) from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.__exit__(exc_type, exc, traceback)

    def bind(self, context: contracts.DaemonContext) -> None:
        try:
            result = self._client.request(
                "thread/resume",
                {
                    "threadId": context.main_thread_id,
                    "cwd": str(context.workspace_dir),
                    "runtimeWorkspaceRoots": [
                        str(context.workspace_dir),
                        str(context.project_workspace_dir),
                    ],
                    "permissions": context.permissions,
                    "excludeTurns": True,
                },
            )
        except app_server.AppServerError as exc:
            raise contracts.DaemonHostError(str(exc)) from exc
        thread = result.get("thread")
        if not isinstance(thread, dict) or thread.get("id") != context.main_thread_id:
            raise contracts.DaemonHostError(
                f"thread/resume returned unexpected thread id for {context.actor_id}"
            )

    def read_notification(self) -> dict[str, Any]:
        try:
            return dict(self._client.read_notification())
        except app_server.AppServerTimeoutError as exc:
            raise contracts.DaemonHostTimeout(str(exc)) from exc
        except app_server.AppServerError as exc:
            raise contracts.DaemonHostError(str(exc)) from exc


class AppActorDaemonHost:
    maintenance_interval_seconds = app_server.DEFAULT_RPC_TIMEOUT_SECONDS

    def resolve_socket_path(self, *, actor_id: str, instance_root: Path) -> Path:
        return app_server.effective_socket_path(
            actor_id,
            instance_root,
            app_server.marker_file(instance_root),
        )

    def notification_client(
        self,
        context: contracts.DaemonContext,
    ) -> AppNotificationClient:
        return AppNotificationClient(context)

    def instance_daemon_command(self, instance_json: Path) -> list[str]:
        return [
            sys.executable,
            "-m",
            "buddyswitch.application.entrypoints.instance_daemon",
            "run",
            "--instance-json",
            str(instance_json),
        ]

    def parent_activity(self, context: contracts.DaemonContext) -> dict[str, Any]:
        try:
            result = app_server.thread_read(
                context.socket_path,
                context.main_thread_id,
                include_turns=False,
            )
            thread = result.get("thread")
            if not isinstance(thread, dict):
                raise app_server.AppServerProtocolError(
                    "thread/read did not return a thread object"
                )
            status_kind = app_server._thread_status_kind(thread.get("status"))
            if status_kind == "idle":
                return {"status": "idle", "active_turn_id": None}
            if status_kind == "active":
                return {
                    "status": "running",
                    "active_turn_id": app_server.active_turn_id(
                        context.socket_path,
                        context.main_thread_id,
                    ),
                }
            raise app_server.AppServerUnavailableError(
                f"thread {context.main_thread_id} is not active or idle"
            )
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

    def input_actor(
        self,
        context: contracts.DaemonContext,
        text: str,
    ) -> dict[str, Any]:
        return dict(
            actor_session.input_actor_turn(
                socket_path=context.socket_path,
                instance_json=context.instance_json,
                thread_id=context.main_thread_id,
                text=text,
                permissions=context.permissions,
            )
        )
