#!/usr/bin/env python3
"""Web-user actor adapter for direct actor messages."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_mailbox  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tools.message import _impl as message_impl  # noqa: E402
from env.tool_runtime import actor_profile  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402
from env_manifest import DEFAULT_MANIFEST, load_manifest  # noqa: E402


WEB_USER_ACTOR_ADDRESS = {"role_id": "user", "actor_id": "act-user-local"}
SINK_START_TIMEOUT_SECONDS = 2.0


def _shared_root() -> Path:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        return Path(raw_shared_root.strip()).expanduser().resolve(strict=False)
    return Path.home() / ".codex-buddyswitch"


def _web_user_instance_json() -> Path:
    raw_path = os.environ.get("BUDDYSWITCH_WEB_USER_INSTANCE_JSON")
    if isinstance(raw_path, str) and raw_path.strip():
        return Path(raw_path.strip()).expanduser().resolve(strict=False)
    return _shared_root() / "state" / "runtime" / "web-user-actor" / "instance.json"


def _run_with_shared_state_root(action: Any) -> dict[str, Any]:
    previous_state_root = os.environ.get("BUDDYSWITCH_STATE_ROOT")
    previous_actor_id = os.environ.get("BUDDYSWITCH_ACTOR_ID")
    had_state_root = "BUDDYSWITCH_STATE_ROOT" in os.environ
    had_actor_id = "BUDDYSWITCH_ACTOR_ID" in os.environ
    os.environ["BUDDYSWITCH_STATE_ROOT"] = str(_shared_root() / "state")
    os.environ["BUDDYSWITCH_ACTOR_ID"] = WEB_USER_ACTOR_ADDRESS["actor_id"]
    runtime_files.refresh_runtime_roots_from_env()
    try:
        return action()
    finally:
        if had_state_root and previous_state_root is not None:
            os.environ["BUDDYSWITCH_STATE_ROOT"] = previous_state_root
        else:
            os.environ.pop("BUDDYSWITCH_STATE_ROOT", None)
        if had_actor_id and previous_actor_id is not None:
            os.environ["BUDDYSWITCH_ACTOR_ID"] = previous_actor_id
        else:
            os.environ.pop("BUDDYSWITCH_ACTOR_ID", None)
        runtime_files.refresh_runtime_roots_from_env()


def _web_user_tool_context() -> runtime_context.ToolContext:
    address = actor_profile.ActorAddress.from_payload(WEB_USER_ACTOR_ADDRESS)
    instance_json = _web_user_instance_json()
    instance_payload = {
        "actor_id": address.actor_id,
        "role": address.role_id,
        "status": "active",
        "workspace_dir": str(_shared_root()),
    }
    record = actor_profile.runtime_actor_record_from_dispatch(
        actor_id=address.actor_id,
        role_id=address.role_id,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    return runtime_context.ToolContext.from_actor_profile(
        actor_profile=actor_profile.resolve_actor_profile(record),
        instance_json=instance_json,
        instance_payload=instance_payload,
        manifest=load_manifest(DEFAULT_MANIFEST),
        manifest_path=DEFAULT_MANIFEST,
    )


def send_web_user_message(
    *,
    target_actor_address: dict[str, Any],
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    def action() -> dict[str, Any]:
        context = _web_user_tool_context()
        args: dict[str, Any] = {
            "target_actor_address": target_actor_address,
            "content": content,
        }
        if reply_to is not None:
            args["reply_to"] = reply_to
        return message_impl.send_message_from_actor(
            args=args,
            context=context,
            source_actor_address=WEB_USER_ACTOR_ADDRESS,
            active_actor=dict(WEB_USER_ACTOR_ADDRESS),
            active_role="user",
            require_active_role_manifest=False,
            action="message.send",
        )

    return _run_with_shared_state_root(action)


def web_user_mailbox_socket_path(shared_root: Path | None = None) -> Path:
    root = Path(shared_root).expanduser().resolve(strict=False) if shared_root is not None else _shared_root()
    socket_path = root / "run" / "web-user-actor" / "mailbox.sock"
    if len(str(socket_path).encode("utf-8")) < 100:
        return socket_path
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return Path("/tmp") / f"buddyswitch-web-user-mailbox-{digest}.sock"


def web_user_sink_dispatcher(trigger: Any) -> dict[str, Any]:
    trigger_type = getattr(trigger, "type", None)
    if trigger_type != "message.available":
        return {
            "accepted": True,
            "handled_count": 0,
            "matched_count": 0,
            "handling_status": "ignored",
        }
    payload = getattr(trigger, "payload", None)
    message_id = payload.get("message_id") if isinstance(payload, dict) else None
    if not isinstance(message_id, str) or not message_id.strip():
        return {
            "accepted": True,
            "handled_count": 0,
            "matched_count": 1,
            "handling_status": "failed",
            "handling_error": "message_id is required",
        }
    return {
        "accepted": True,
        "handled_count": 1,
        "matched_count": 1,
        "handling_status": "acknowledged",
    }


def build_web_user_sink_server(*, socket_path: Path | None = None) -> daemon_mailbox.DaemonMailboxServer:
    return daemon_mailbox.DaemonMailboxServer(
        socket_path=socket_path or web_user_mailbox_socket_path(),
        local_actor_address=WEB_USER_ACTOR_ADDRESS,
        handlers=[],
        trigger_dispatcher=web_user_sink_dispatcher,
    )


class WebUserActorRuntime:
    def __init__(
        self,
        *,
        socket_path: Path | None = None,
        register_actor: Any = None,
        unregister_actor: Any = None,
    ) -> None:
        self.socket_path = socket_path or web_user_mailbox_socket_path()
        self.server = build_web_user_sink_server(socket_path=self.socket_path)
        self.thread: threading.Thread | None = None
        self.register_result: dict[str, Any] | None = None
        self._register_actor = register_actor or register_web_user_actor
        self._unregister_actor = unregister_actor or unregister_web_user_actor

    def start(self) -> "WebUserActorRuntime":
        if self.thread is not None and self.thread.is_alive():
            return self
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.thread = thread
        deadline = time.monotonic() + SINK_START_TIMEOUT_SECONDS
        while not self.socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not self.socket_path.exists():
            self.close()
            raise RuntimeError(f"web-user mailbox socket did not become ready: {self.socket_path}")
        try:
            self.register_result = self._register_actor(socket_path=self.socket_path)
        except Exception:
            self.close()
            raise
        return self

    def close(self) -> None:
        try:
            if self.register_result is not None:
                try:
                    self._unregister_actor()
                finally:
                    self.register_result = None
        finally:
            self.server.close()
            thread = self.thread
            if thread is not None:
                thread.join(timeout=2)
            self.thread = None


def register_web_user_actor(
    *,
    socket_path: Path | None = None,
    central_socket_path: Path | None = None,
) -> dict[str, Any]:
    chosen_socket = socket_path or web_user_mailbox_socket_path()
    return daemon_client.register_actor(
        actor_address=WEB_USER_ACTOR_ADDRESS,
        endpoint={"kind": "daemon_mailbox_socket", "socket_path": str(chosen_socket)},
        heartbeat={"kind": "central_daemon_rpc"},
        status="online",
        socket_path=central_socket_path,
    )


def unregister_web_user_actor(*, central_socket_path: Path | None = None) -> dict[str, Any]:
    return daemon_client.unregister_actor(
        actor_address=WEB_USER_ACTOR_ADDRESS,
        socket_path=central_socket_path,
    )
