"""Actor instance daemon state, dispatch, recovery, and lifecycle."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from types import MappingProxyType
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent

from buddyswitch.foundation.daemon import contracts  # noqa: E402
from buddyswitch.foundation.daemon import mailbox  # noqa: E402
from buddyswitch.foundation.daemon import runtime as daemon_runtime  # noqa: E402
from buddyswitch.foundation.daemon import state as daemon_state  # noqa: E402
from buddyswitch.foundation.daemon import triggers  # noqa: E402
from buddyswitch.foundation.process_runtime import event_log  # noqa: E402
from buddyswitch.foundation.identity.model import ACTOR_ID_PATTERN, ROLE_ID_PATTERN  # noqa: E402
import buddyswitch.foundation.identity.profiles as identity_profiles  # noqa: E402
import buddyswitch.foundation.state.runtime as state_runtime  # noqa: E402
from buddyswitch.foundation.daemon import client as daemon_client  # noqa: E402
import buddyswitch.foundation.process_runtime.process_identity as process_identity  # noqa: E402


DAEMON_STOP_GRACE_SECONDS = 2.0
DAEMON_POLL_SECONDS = 0.05
DAEMON_READY_TIMEOUT_SECONDS = 5.0
DAEMON_READY_POLL_SECONDS = 0.05


def daemon_runtime_dir(instance_root: Path) -> Path:
    return instance_root / "runtime" / "daemon"


def daemon_pid_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "daemon.pid"


def daemon_pid_identity_file(instance_root: Path) -> Path:
    return process_identity.identity_file(daemon_pid_file(instance_root))


def daemon_log_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "daemon.log"


def _append_daemon_event(context: "contracts.DaemonContext", event: str, **fields: Any) -> None:
    event_log.append_event(
        daemon_log_file(context.instance_root),
        service="daemon",
        event=event,
        actor_id=context.actor_id,
        **fields,
    )


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_text_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")


def _read_pid(path: Path) -> int | None:
    raw = _read_text_file(path)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _remove_path(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _terminate_record(record: process_identity.RecordedProcess) -> bool:
    if not process_identity.is_running(record):
        process_identity.reap_if_child(record.pid)
        return True
    os.kill(record.pid, signal.SIGTERM)
    deadline = time.monotonic() + DAEMON_STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not process_identity.is_running(record):
            process_identity.reap_if_child(record.pid)
            return True
        time.sleep(DAEMON_POLL_SECONDS)
    if process_identity.is_running(record) and process_identity.matches(record):
        os.kill(record.pid, signal.SIGKILL)
    process_identity.reap_if_child(record.pid)
    return not process_identity.is_running(record)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _string_field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _notification_turn_id(notification: dict[str, Any]) -> str | None:
    params = notification.get("params")
    if not isinstance(params, dict):
        return None
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return None
    turn_id = _string_field(turn, "id")
    return turn_id or None


def _handler_name(handler: Any) -> str:
    name = getattr(handler, "name", None)
    if isinstance(name, str) and name:
        return name
    return type(handler).__name__


def _handler_names(handlers: list[Any] | tuple[Any, ...] | None) -> list[str]:
    names: list[str] = []
    for handler in handlers or []:
        name = _handler_name(handler)
        if name not in names:
            names.append(name)
    return names


def _schedule_row(state: "daemon_state.DaemonState", schedule_id: str) -> dict[str, Any] | None:
    schedules = state.payload.get("scheduled_triggers")
    if not isinstance(schedules, dict):
        return None
    row = schedules.get(schedule_id)
    if isinstance(row, dict):
        return dict(row)
    return None


def _schedule_matches_dispatch_snapshot(current: dict[str, Any] | None, snapshot: dict[str, Any]) -> bool:
    if current is None:
        return False
    fields = (
        "schedule_id",
        "type",
        "payload",
        "source_context",
        "status",
        "updated_at",
        "due_at",
        "schedule_key",
    )
    return all(current.get(field) == snapshot.get(field) for field in fields)


def _notify_subscriptions_payload(notify_subscriptions: list[str] | tuple[str, ...] | None) -> list[str]:
    names: list[str] = []
    for value in notify_subscriptions or []:
        if not isinstance(value, str):
            raise ValueError("notify subscription event types must be strings")
        name = value.strip()
        if name and name not in names:
            names.append(name)
    return names


def load_daemon_context(
    instance_json: Path,
    *,
    host: contracts.DaemonHost,
) -> contracts.DaemonContext:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance JSON must contain an object: {instance_json}")
    actor_id = _string_field(payload, "actor_id")
    role = _string_field(payload, "role")
    main_thread_id = _string_field(payload, "thread_id")
    instance_root_text = _string_field(payload, "instance_root")
    workspace_dir_text = _string_field(payload, "workspace_dir")
    if not actor_id or not role or not main_thread_id or not instance_root_text or not workspace_dir_text:
        raise ValueError(f"instance JSON is missing daemon fields: {instance_json}")
    instance_root = Path(instance_root_text)
    workspace_dir = Path(workspace_dir_text)
    project_workspace_dir = instance_root.parent.parent / "project" / "workspace"
    socket_text = _string_field(payload, "app_server_socket")
    socket_path = (
        Path(socket_text)
        if socket_text
        else host.resolve_socket_path(actor_id=actor_id, instance_root=instance_root)
    )
    return contracts.DaemonContext(
        instance_json=instance_json,
        instance_payload=payload,
        actor_id=actor_id,
        instance_root=instance_root,
        main_thread_id=main_thread_id,
        role=role,
        workspace_dir=workspace_dir,
        project_workspace_dir=project_workspace_dir,
        socket_path=socket_path,
    )


def derive_daemon_runtime_env(context: contracts.DaemonContext) -> dict[str, str]:
    shared_root = context.instance_root.parent.parent
    return {
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
        "BUDDYSWITCH_INSTANCE_ROOT": str(context.instance_root),
        "BUDDYSWITCH_INSTANCE_JSON": str(context.instance_json),
        "BUDDYSWITCH_WORKSPACE_DIR": str(context.workspace_dir),
        "BUDDYSWITCH_ACTOR_ID": context.actor_id,
        "BUDDYSWITCH_ROLE_ID": context.role,
    }


def identity_route_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    extra_keys = set(value) - {"identity_id", "role_id"}
    if extra_keys:
        raise ValueError(f"{field} contains unsupported fields: {sorted(extra_keys)}")
    identity_id = value.get("identity_id")
    role_id = value.get("role_id")
    if not isinstance(identity_id, str) or ACTOR_ID_PATTERN.fullmatch(identity_id.strip()) is None:
        raise ValueError(f"{field}.identity_id must be a valid actor identity id")
    if not isinstance(role_id, str) or ROLE_ID_PATTERN.fullmatch(role_id.strip()) is None:
        raise ValueError(f"{field}.role_id must be a valid role id")
    return {"identity_id": identity_id.strip(), "role_id": role_id.strip()}


def identity_route_for_context(context: contracts.DaemonContext) -> dict[str, str]:
    return identity_route_payload(
        {"identity_id": context.actor_id, "role_id": context.role},
        "context.identity_route",
    )


def ensure_actor_identity_profile(context: contracts.DaemonContext, identity_route: dict[str, str]) -> dict[str, Any]:
    existing = identity_profiles.get_actor_identity_profile(identity_route["identity_id"])
    if isinstance(existing, dict):
        if existing.get("role_id") != identity_route["role_id"]:
            raise ValueError(
                "actor identity profile role mismatch: "
                f"{identity_route['identity_id']} has {existing.get('role_id')}, "
                f"instance has {identity_route['role_id']}"
            )
        return existing
    return identity_profiles.save_actor_identity_profile(
        {
            "identity": {"id": identity_route["identity_id"], "type": "actor"},
            "role_id": identity_route["role_id"],
        }
    )


def central_daemon_socket_path(context: contracts.DaemonContext) -> Path:
    raw_socket = os.environ.get("BUDDYSWITCH_CENTRAL_DAEMON_SOCKET")
    if isinstance(raw_socket, str) and raw_socket.strip():
        return Path(raw_socket.strip()).expanduser().resolve(strict=False)
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        shared_root = Path(raw_shared_root.strip()).expanduser().resolve(strict=False)
    else:
        shared_root = context.instance_root.parent.parent
    return daemon_client.central_daemon_socket_path_for_shared_root(shared_root)


def register_daemon_actor(
    context: contracts.DaemonContext,
    identity_route: dict[str, str],
    *,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    endpoint: dict[str, Any] = {
        "kind": "daemon_mailbox_socket",
        "socket_path": str(mailbox.mailbox_socket_path(context.instance_root)),
    }
    subscriptions = _notify_subscriptions_payload(notify_subscriptions)
    if subscriptions:
        endpoint["subscriptions"] = subscriptions
    return daemon_client.register_actor(
        identity_id=identity_route["identity_id"],
        role_id=identity_route["role_id"],
        endpoint=endpoint,
        heartbeat={"kind": "central_daemon_rpc"},
        socket_path=central_daemon_socket_path(context),
    )


def unregister_daemon_actor(
    context: contracts.DaemonContext,
    identity_route: dict[str, str],
) -> dict[str, Any]:
    return daemon_client.unregister_actor(
        identity_id=identity_route["identity_id"],
        role_id=identity_route["role_id"],
        socket_path=central_daemon_socket_path(context),
    )


def safe_unregister_daemon_actor(
    context: contracts.DaemonContext,
    identity_route: dict[str, str],
    *,
    state: daemon_state.DaemonState | None = None,
) -> dict[str, Any]:
    try:
        result = unregister_daemon_actor(context, identity_route)
    except Exception as exc:
        message = str(exc)
        if state is not None and state.payload.get("last_error") is None:
            state.record_error(origin_turn_id=None, message=message)
        return {
            "unregister_status": "failed",
            "unregister_error": message,
        }
    return {
        "unregister_status": "ok",
        "unregister_result": result,
    }


def heartbeat_daemon_actor(
    context: contracts.DaemonContext,
    identity_route: dict[str, str],
) -> dict[str, Any]:
    return daemon_client.heartbeat_actor(
        identity_id=identity_route["identity_id"],
        socket_path=central_daemon_socket_path(context),
    )


def build_application_commands(
    context: contracts.DaemonContext,
    factories: list[contracts.ApplicationCommandFactory]
    | tuple[contracts.ApplicationCommandFactory, ...]
    | None,
) -> Mapping[str, contracts.ApplicationCommand]:
    commands: dict[str, contracts.ApplicationCommand] = {}
    for factory in factories or ():
        if not callable(factory):
            raise ValueError("application command factories must be callable")
        registrations = factory(context)
        if not isinstance(registrations, Mapping):
            raise ValueError("application command factory must return a mapping")
        for key, command in registrations.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("application command keys must be non-empty strings")
            normalized_key = key.strip()
            if normalized_key in commands:
                raise ValueError(f"duplicate application command: {normalized_key}")
            if normalized_key in mailbox.CONTROL_METHODS:
                raise ValueError(f"application command conflicts with control method: {normalized_key}")
            if not callable(command):
                raise ValueError(f"application command must be callable: {normalized_key}")
            commands[normalized_key] = command
    return MappingProxyType(commands)


def start_daemon_mailbox(
    *,
    context: contracts.DaemonContext,
    state: daemon_state.DaemonState,
    identity_route: dict[str, str],
    handlers: list[Any] | tuple[Any, ...],
    host: contracts.DaemonHost,
    application_command_factories: list[contracts.ApplicationCommandFactory]
    | tuple[contracts.ApplicationCommandFactory, ...]
    | None = None,
) -> mailbox.DaemonMailboxServer:
    server = mailbox.DaemonMailboxServer(
        socket_path=mailbox.mailbox_socket_path(context.instance_root),
        local_identity_id=identity_route["identity_id"],
        local_role_id=identity_route["role_id"],
        handlers=handlers,
        context=context,
        state=state,
        trigger_dispatcher=lambda trigger: dispatch_trigger(
            context,
            state,
            daemon_runtime.DaemonRuntime(context=context, host=host),
            trigger,
            handlers,
        ),
        application_commands=build_application_commands(context, application_command_factories),
    )
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + DAEMON_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if mailbox.mailbox_socket_path(context.instance_root).exists():
            return server
        time.sleep(DAEMON_READY_POLL_SECONDS)
    server.close()
    raise RuntimeError(f"daemon mailbox did not become ready for {context.actor_id}")


def bind_main_thread(context: contracts.DaemonContext, client: Any) -> None:
    client.bind(context)


def dispatch_notification(
    context: contracts.DaemonContext,
    state: daemon_state.DaemonState,
    client: Any,
    notification: dict[str, Any],
    handlers: list[Any] | tuple[Any, ...],
    *,
    host: contracts.DaemonHost,
) -> bool:
    daemon_handler_runtime = daemon_runtime.DaemonRuntime(context=context, host=host)
    trigger = triggers.normalize_app_server_notification(
        notification,
        target_identity_id=context.actor_id,
        target_role_id=context.role,
    )
    _append_daemon_event(
        context,
        "notification_received",
        trigger_type=trigger.type,
        origin_id=_trigger_origin_id(trigger),
    )
    result = dispatch_trigger(
        context,
        state,
        daemon_handler_runtime,
        trigger,
        handlers,
    )
    handled_count = result.get("handled_count")
    return isinstance(handled_count, int) and handled_count > 0


def _trigger_origin_id(trigger: Any) -> str | None:
    origin_id = getattr(trigger, "origin_id", None)
    return origin_id if isinstance(origin_id, str) and origin_id else None


def dispatch_trigger(
    context: contracts.DaemonContext,
    state: daemon_state.DaemonState,
    runtime: Any,
    trigger: triggers.DaemonTrigger,
    handlers: list[Any] | tuple[Any, ...],
) -> dict[str, Any]:
    handled = 0
    matched = 0
    errors: list[str] = []
    origin_id = _trigger_origin_id(trigger)
    for handler in handlers:
        handler_name = _handler_name(handler)
        handles = getattr(handler, "handles", None)
        if not callable(handles):
            continue
        try:
            if handles(trigger) is not True:
                continue
        except Exception as exc:
            errors.append(str(exc))
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=str(exc))
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type=type(exc).__name__,
            )
            continue
        matched += 1
        handle = getattr(handler, "handle", None)
        if not callable(handle):
            message = f"handler {handler_name} has no unified handle method"
            errors.append(message)
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=message)
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type="missing_handle",
            )
            continue
        try:
            result = handle(context, state, runtime, trigger)
        except Exception as exc:
            errors.append(str(exc))
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=str(exc))
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type=type(exc).__name__,
            )
            continue
        status = getattr(result, "status", None)
        message = getattr(result, "message", None)
        if isinstance(result, dict):
            status = result.get("status")
            message = result.get("message")
        if status not in {"ignored", "handled", "failed"}:
            message = f"handler returned invalid result: {type(result).__name__}"
            errors.append(message)
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=message)
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type="invalid_result",
            )
            continue
        normalized = contracts.HandlerResult(status, str(message) if status == "failed" and message else None)
        state.record_handler_result(handler_name, normalized, origin_turn_id=origin_id)
        _append_daemon_event(
            context,
            "handler_result",
            handler=handler_name,
            trigger_type=trigger.type,
            origin_id=origin_id,
            result=normalized.status,
        )
        if status == "handled":
            handled += 1
        elif status == "failed":
            errors.append(str(message or "handler failed"))
    if errors:
        return {
            "accepted": True,
            "handled_count": handled,
            "matched_count": matched,
            "handling_status": "failed",
            "handling_error": "; ".join(errors),
            "trigger": trigger.to_payload(),
        }
    return {
        "accepted": True,
        "handled_count": handled,
        "matched_count": matched,
        "handling_status": "handled" if handled > 0 else "ignored",
        "trigger": trigger.to_payload(),
    }


def reconcile_handlers(
    context: contracts.DaemonContext,
    state: daemon_state.DaemonState,
    runtime: Any,
    handlers: list[Any] | tuple[Any, ...],
) -> dict[str, Any]:
    handled_count = 0
    ignored_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []
    for handler in handlers:
        reconcile = getattr(handler, "reconcile", None)
        if not callable(reconcile):
            continue
        handler_name = _handler_name(handler)
        try:
            result = reconcile(context, state, runtime)
        except Exception as exc:
            message = str(exc)
            failed_count += 1
            state.record_handler_error(
                handler_name,
                origin_turn_id=None,
                message=message,
            )
            _append_daemon_event(
                context,
                "handler_reconcile_failed",
                handler=handler_name,
                error_type=type(exc).__name__,
            )
            results.append({
                "handler": handler_name,
                "status": "failed",
                "message": message,
            })
            continue
        status = getattr(result, "status", None)
        message = getattr(result, "message", None)
        if isinstance(result, dict):
            status = result.get("status")
            message = result.get("message")
        if status not in {"ignored", "handled", "failed"}:
            message = (
                "handler reconcile returned invalid result: "
                f"{type(result).__name__}"
            )
            failed_count += 1
            state.record_handler_error(
                handler_name,
                origin_turn_id=None,
                message=message,
            )
            _append_daemon_event(
                context,
                "handler_reconcile_failed",
                handler=handler_name,
                error_type="invalid_result",
            )
            results.append({
                "handler": handler_name,
                "status": "failed",
                "message": message,
            })
            continue
        normalized = contracts.HandlerResult(
            status,
            str(message) if status == "failed" and message else None,
        )
        state.record_handler_result(
            handler_name,
            normalized,
            origin_turn_id=None,
        )
        if status == "handled":
            handled_count += 1
        elif status == "ignored":
            ignored_count += 1
        else:
            failed_count += 1
        _append_daemon_event(
            context,
            "handler_reconcile_result",
            handler=handler_name,
            result=status,
        )
        row: dict[str, Any] = {
            "handler": handler_name,
            "status": status,
        }
        if normalized.message:
            row["message"] = normalized.message
        results.append(row)
    return {
        "reconciled_count": handled_count,
        "ignored_count": ignored_count,
        "failed_count": failed_count,
        "handlers": results,
    }


def sweep_due_scheduled_triggers(
    context: contracts.DaemonContext,
    state: daemon_state.DaemonState,
    runtime: Any,
    handlers: list[Any] | tuple[Any, ...],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
    identity_route = identity_route_for_context(context)
    swept_count = 0
    delivered_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []
    for schedule in state.due_schedules(now=timestamp):
        schedule_id = schedule["schedule_id"]
        trigger = triggers.normalize_scheduled_trigger(
            schedule,
            target_identity_id=identity_route["identity_id"],
            target_role_id=identity_route["role_id"],
        )
        dispatch_result = dispatch_trigger(context, state, runtime, trigger, handlers)
        swept_count += 1
        handling_status = dispatch_result.get("handling_status")
        matched_count = dispatch_result.get("matched_count")
        if handling_status == "failed":
            error = dispatch_result.get("handling_error")
            if not isinstance(error, str) or not error:
                error = "scheduled trigger handler failed"
            current_schedule = _schedule_row(state, schedule_id)
            if _schedule_matches_dispatch_snapshot(current_schedule, schedule):
                updated = state.mark_schedule_failed(
                    schedule_id,
                    message=error,
                    dispatch_result=dispatch_result,
                    now=timestamp,
                )
                failed_count += 1
            else:
                updated = current_schedule if current_schedule is not None else schedule
        elif isinstance(matched_count, int) and matched_count > 0 and handling_status in {
            "handled",
            "ignored",
        }:
            current_schedule = _schedule_row(state, schedule_id)
            if _schedule_matches_dispatch_snapshot(current_schedule, schedule):
                updated = state.mark_schedule_delivered(schedule_id, dispatch_result=dispatch_result, now=timestamp)
                delivered_count += 1
            else:
                updated = current_schedule if current_schedule is not None else schedule
        else:
            current_schedule = _schedule_row(state, schedule_id)
            if _schedule_matches_dispatch_snapshot(current_schedule, schedule):
                updated = state.mark_schedule_failed(
                    schedule_id,
                    message="scheduled trigger had no matching handler",
                    dispatch_result=dispatch_result,
                    now=timestamp,
                )
                failed_count += 1
            else:
                updated = current_schedule if current_schedule is not None else schedule
        results.append(updated)
    return {
        "swept_count": swept_count,
        "delivered_count": delivered_count,
        "failed_count": failed_count,
        "schedules": results,
    }


def _handler_status_payload(
    state: daemon_state.DaemonState,
    handlers: list[Any] | tuple[Any, ...] | None,
    *,
    include_unregistered: bool = True,
    excluded_persisted_names: set[str] | None = None,
) -> dict[str, Any]:
    registered = _handler_names(handlers)
    excluded = excluded_persisted_names or set()
    persisted = state.payload.get("handlers")
    persisted_handlers = persisted if isinstance(persisted, dict) else {}
    names = list(registered)
    if include_unregistered:
        for name in sorted(persisted_handlers):
            if name not in names and name not in excluded:
                names.append(name)
    else:
        for name in sorted(persisted_handlers):
            if name in registered and name not in names:
                names.append(name)

    items: dict[str, Any] = {}
    for name in names:
        raw_state = persisted_handlers.get(name)
        handler_state = dict(raw_state) if isinstance(raw_state, dict) else {}
        is_registered = name in registered
        item = {
            "registered": is_registered,
            "enabled": is_registered,
            "active": is_registered,
            "result_scope": "trigger_dispatch",
            "last_result": None,
            "last_handled_at": None,
            "last_error": None,
        }
        for field in daemon_state.HANDLER_STATE_FIELDS:
            if field in handler_state and field not in {"registered", "enabled", "active"}:
                item[field] = handler_state[field]
        items[name] = item
    return {"registered": registered, "items": items}


def _schedule_status_payload(state: daemon_state.DaemonState) -> dict[str, Any]:
    schedule_ids = [
        item for item in state.payload.get("scheduled_trigger_ids", []) if isinstance(item, str) and item
    ]
    schedules = state.payload.get("scheduled_triggers")
    schedule_items = schedules if isinstance(schedules, dict) else {}
    items = {
        schedule_id: schedule_items[schedule_id]
        for schedule_id in schedule_ids
        if schedule_id in schedule_items and isinstance(schedule_items[schedule_id], dict)
    }
    counts = {"pending": 0, "delivered": 0, "failed": 0, "canceled": 0}
    for item in items.values():
        status = item.get("status")
        if status in counts:
            counts[status] += 1
    return {"ids": list(items), "items": items, "counts": counts}


def daemon_status(
    instance_json: Path,
    *,
    host: contracts.DaemonHost,
    handlers: list[Any] | tuple[Any, ...] | None = None,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    context = load_daemon_context(instance_json, host=host)
    runtime_dir = daemon_runtime_dir(context.instance_root)
    pid_path = daemon_pid_file(context.instance_root)
    log_path = daemon_log_file(context.instance_root)
    state_path = daemon_state.daemon_state_file(context.instance_root)
    pid = _read_pid(pid_path)
    recorded = process_identity.read_record(pid_path)
    identity_matches = recorded is not None and process_identity.matches(recorded)
    pid_live = recorded is not None and process_identity.is_running(recorded)
    if pid is not None and not pid_live:
        process_identity.remove_record(pid_path)
        pid = None
    state = daemon_state.DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    ready = bool(pid is not None and pid_live and state.ready_for(pid, context.main_thread_id))
    ready_payload = state.payload.get("ready")
    ready_main_thread_id = ready_payload.get("main_thread_id") if isinstance(ready_payload, dict) else None
    return {
        "live": bool(pid_live),
        "pid": pid,
        "pid_live": bool(pid_live),
        "identity_matches": bool(identity_matches),
        "ready": ready,
        "ready_main_thread_id": ready_main_thread_id,
        "runtime_dir": str(runtime_dir),
        "pid_file": str(pid_path),
        "log_path": str(log_path),
        "log": event_log.log_metadata(log_path),
        "state_path": str(state_path),
        "last_error": state.payload.get("last_error"),
        "schedules": _schedule_status_payload(state),
        "handlers": _handler_status_payload(state, handlers),
        "notify": {"subscriptions": _notify_subscriptions_payload(notify_subscriptions)},
    }


def start_daemon(
    instance_json: Path,
    *,
    host: contracts.DaemonHost,
    handlers: list[Any] | tuple[Any, ...] | None = None,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    context = load_daemon_context(instance_json, host=host)
    runtime_dir = daemon_runtime_dir(context.instance_root)
    pid_path = daemon_pid_file(context.instance_root)
    log_path = daemon_log_file(context.instance_root)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    state = daemon_state.DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    state.register_handlers(_handler_names(handlers))
    state.save()

    pid = _read_pid(pid_path)
    recorded = process_identity.read_record(pid_path)
    if recorded is not None and process_identity.is_running(recorded):
        if state.ready_for(pid, context.main_thread_id):
            status = daemon_status(
                instance_json,
                host=host,
                handlers=handlers,
                notify_subscriptions=notify_subscriptions,
            )
            status["started"] = False
            return status
        _terminate_record(recorded)
        process_identity.remove_record(pid_path)
    if pid is not None:
        process_identity.remove_record(pid_path)
    state.payload["ready"] = None
    state.save()

    command = host.instance_daemon_command(instance_json)
    child_env = os.environ.copy()
    child_env.update(derive_daemon_runtime_env(context))
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(context.instance_root),
            env=child_env,
        )
    process_identity.write_record(pid_path, process.pid)
    _append_daemon_event(context, "daemon_started", pid=process.pid, main_thread_id=context.main_thread_id)
    deadline = time.monotonic() + DAEMON_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        wait_state = daemon_state.DaemonState.load(
            instance_root=context.instance_root,
            actor_id=context.actor_id,
            main_thread_id=context.main_thread_id,
        )
        if wait_state.ready_for(process.pid, context.main_thread_id):
            status = daemon_status(
                instance_json,
                host=host,
                handlers=handlers,
                notify_subscriptions=notify_subscriptions,
            )
            status["started"] = True
            status["pid"] = process.pid
            status["pid_live"] = _pid_is_live(process.pid)
            status["live"] = bool(status["pid_live"])
            return status
        if process.poll() is not None:
            process_identity.remove_record(pid_path)
            raise RuntimeError(f"daemon exited before ready for {context.actor_id}; see {log_path}")
        time.sleep(DAEMON_READY_POLL_SECONDS)
    recorded = process_identity.read_record(pid_path)
    if recorded is not None:
        _terminate_record(recorded)
    process_identity.remove_record(pid_path)
    raise RuntimeError(f"daemon did not become ready for {context.actor_id}; see {log_path}")


def stop_daemon(
    instance_json: Path,
    *,
    host: contracts.DaemonHost,
) -> dict[str, Any]:
    context = load_daemon_context(instance_json, host=host)
    identity_route = identity_route_for_context(context)
    state = daemon_state.DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    pid_path = daemon_pid_file(context.instance_root)
    pid = _read_pid(pid_path)
    recorded = process_identity.read_record(pid_path)
    identity_matches = recorded is not None and process_identity.matches(recorded)
    terminated = False
    if recorded is not None and process_identity.is_running(recorded):
        terminated = _terminate_record(recorded)
    process_identity.remove_record(pid_path)
    unregister = safe_unregister_daemon_actor(context, identity_route, state=state)
    _append_daemon_event(context, "daemon_stopped", pid=pid, terminated=bool(terminated))
    payload = {
        "ok": True,
        "pid": pid,
        "terminated": bool(terminated),
        "identity_mismatch": bool(pid is not None and not identity_matches),
        "pid_file": str(pid_path),
    }
    payload.update(unregister)
    return payload


def run_daemon(
    instance_json: Path,
    *,
    host: contracts.DaemonHost,
    handlers: list[Any] | None = None,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
    application_command_factories: list[contracts.ApplicationCommandFactory]
    | tuple[contracts.ApplicationCommandFactory, ...]
    | None = None,
) -> int:
    context = load_daemon_context(instance_json, host=host)
    pid_path = daemon_pid_file(context.instance_root)
    process_identity.write_record(pid_path, os.getpid())
    os.environ.update(derive_daemon_runtime_env(context))
    state_runtime.refresh_runtime_roots_from_env()
    identity_route = identity_route_for_context(context)
    ensure_actor_identity_profile(context, identity_route)
    state = daemon_state.DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    state.save()
    daemon_handlers = list(handlers or [])
    state.register_handlers(_handler_names(daemon_handlers))
    registered = False
    mailbox_server: mailbox.DaemonMailboxServer | None = None
    try:
        with host.notification_client(context) as client:
            bind_main_thread(context, client)
            state.record_ready(pid=os.getpid(), main_thread_id=context.main_thread_id)
            _append_daemon_event(context, "daemon_ready", pid=os.getpid(), main_thread_id=context.main_thread_id)
            mailbox_server = start_daemon_mailbox(
                context=context,
                state=state,
                identity_route=identity_route,
                handlers=daemon_handlers,
                host=host,
                application_command_factories=application_command_factories,
            )
            if notify_subscriptions is None:
                register_daemon_actor(context, identity_route)
            else:
                register_daemon_actor(context, identity_route, notify_subscriptions=notify_subscriptions)
            registered = True
            daemon_handler_runtime = daemon_runtime.DaemonRuntime(context=context, host=host)
            reconcile_handlers(
                context,
                state,
                daemon_handler_runtime,
                daemon_handlers,
            )
            next_maintenance_at = time.monotonic() + host.maintenance_interval_seconds
            while True:
                try:
                    notification = client.read_notification()
                except contracts.DaemonHostTimeout:
                    reconcile_handlers(
                        context,
                        state,
                        daemon_handler_runtime,
                        daemon_handlers,
                    )
                    sweep_due_scheduled_triggers(
                        context,
                        state,
                        daemon_handler_runtime,
                        daemon_handlers,
                    )
                    heartbeat_daemon_actor(context, identity_route)
                    next_maintenance_at = (
                        time.monotonic() + host.maintenance_interval_seconds
                    )
                    continue
                except contracts.DaemonHostError as exc:
                    state.record_error(origin_turn_id=None, message=str(exc))
                    return 1
                dispatch_notification(
                    context,
                    state,
                    client,
                    notification,
                    daemon_handlers,
                    host=host,
                )
                sweep_due_scheduled_triggers(
                    context,
                    state,
                    daemon_handler_runtime,
                    daemon_handlers,
                )
                if time.monotonic() >= next_maintenance_at:
                    reconcile_handlers(
                        context,
                        state,
                        daemon_handler_runtime,
                        daemon_handlers,
                    )
                    heartbeat_daemon_actor(context, identity_route)
                    next_maintenance_at = (
                        time.monotonic() + host.maintenance_interval_seconds
                    )
    except contracts.DaemonHostError as exc:
        state.record_error(origin_turn_id=None, message=str(exc))
        return 1
    finally:
        if registered:
            safe_unregister_daemon_actor(context, identity_route, state=state)
        if mailbox_server is not None:
            mailbox_server.close()
        process_identity.remove_record(pid_path)
    return 0
