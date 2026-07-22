"""Product-neutral host runtime facts exposed to daemon handlers."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import app_server  # noqa: E402
import actor_session  # noqa: E402
import daemon_contracts  # noqa: E402


class DaemonRuntime:
    def __init__(self, *, context: daemon_contracts.DaemonContext) -> None:
        self.context = context

    def parent_activity(self) -> dict[str, Any]:
        try:
            result = app_server.thread_read(
                self.context.socket_path,
                self.context.main_thread_id,
                include_turns=False,
            )
            thread = result.get("thread")
            if not isinstance(thread, dict):
                raise app_server.AppServerProtocolError("thread/read did not return a thread object")
            status_kind = app_server._thread_status_kind(thread.get("status"))
            if status_kind == "idle":
                return {"status": "idle", "active_turn_id": None}
            if status_kind == "active":
                return {
                    "status": "running",
                    "active_turn_id": app_server.active_turn_id(
                        self.context.socket_path,
                        self.context.main_thread_id,
                    ),
                }
            raise app_server.AppServerUnavailableError(
                f"thread {self.context.main_thread_id} is not active or idle"
            )
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

    def input_actor(self, text: str) -> dict[str, Any]:
        return dict(
            actor_session.input_actor_turn(
                socket_path=self.context.socket_path,
                instance_json=self.context.instance_json,
                thread_id=self.context.main_thread_id,
                text=text,
                permissions=self.context.permissions,
            )
        )
