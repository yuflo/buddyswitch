#!/usr/bin/env python3
"""Launcher-managed runtime broker server."""

from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import threading
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid
from typing import Any, Iterator

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from env_manifest import ManifestError, load_manifest
import env_profiles
from runtime_kernel.client import PROTOCOL
from runtime_kernel.persist import persist_buddy_run_request
from runtime_kernel.resolve import prepare_turn_context_request
import turn_runtime
from env.tools.task_manager import dispatch_task_manager_request


def _error(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if extra:
        error.update(extra)
    return {"ok": False, "error": error}


def _allowed(*actions: str) -> list[str]:
    return list(actions)


def _boundary_error(code: str, message: str, *, boundary: str, actions: list[str]) -> dict[str, Any]:
    return _error(
        code,
        message,
        {
            "permission_boundary": boundary,
            "allowed_next_actions": actions,
        },
    )


def _error_from_payload(error: dict[str, Any], *, default_code: str, default_message: str) -> dict[str, Any]:
    message = error.get("message") if isinstance(error.get("message"), str) else default_message
    code = error.get("code") if isinstance(error.get("code"), str) else default_code
    extra = {key: value for key, value in error.items() if key not in {"code", "message"}}
    return _error(code, message, extra)


def _load_instance_record(instance_json_path: Path) -> dict[str, Any]:
    payload = json.loads(instance_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance record must be an object: {instance_json_path}")
    instance_id = payload.get("instance_id")
    buddy = payload.get("buddy")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError(f"instance record missing instance_id: {instance_json_path}")
    if not isinstance(buddy, str) or not buddy.strip():
        raise ValueError(f"instance record missing buddy: {instance_json_path}")
    return payload


def _instance_shared_root(instance_json_path: Path) -> Path:
    instance_root = instance_json_path.parent
    if instance_root.parent.name == "instances":
        return instance_root.parent.parent
    return instance_root


@contextlib.contextmanager
def _runtime_server_env(*, instance_id: str, buddy_id: str, instance_json_path: Path) -> Iterator[None]:
    shared_root = _instance_shared_root(instance_json_path)
    updates = {
        "BUDDYSWITCH_RUNTIME_BROKER_MODE": "server",
        "BUDDYSWITCH_INSTANCE_ID": instance_id,
        "BUDDYSWITCH_ACTIVE_BUDDY": buddy_id,
        "BUDDYSWITCH_INSTANCE_JSON": str(instance_json_path),
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
    }
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _product_session(*, instance_json_path: Path, instance_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_json": instance_json_path,
        "payload": dict(instance_record),
        "instance_id": instance_record.get("instance_id"),
        "active_buddy": instance_record.get("buddy"),
    }


def _prepare_dispatch(
    *,
    payload: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("prepare payload.text must be a non-empty string")
    prepared = prepare_turn_context_request(text, manifest_path=manifest_path)
    if prepared.get("ok") is not True:
        error = prepared.get("error") if isinstance(prepared.get("error"), dict) else {}
        return _error_from_payload(error, default_code="E_RUNTIME_BROKER", default_message="prepare rejected")
    session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
    try:
        task_id, track_id = turn_runtime._resolve_binding_from_payload(prepared)
        turn_runtime._write_product_session_binding(session, task_id=task_id, track_id=track_id)
    except (OSError, ValueError) as exc:
        turn_runtime._clear_reservation_from_payload(prepared, fail_on_warning=True)
        raise ValueError(f"instance binding update failed after prepare: {exc}") from exc
    return {"ok": True, "payload": prepared}


def _persist_dispatch(
    *,
    payload: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    context = payload.get("context")
    result = payload.get("result")
    if not isinstance(context, dict):
        return _boundary_error(
            "E_RUNTIME_BROKER",
            "persist payload.context must be an object",
            boundary="request-payload",
            actions=_allowed("Send a persist request with object payload.context and payload.result."),
        )
    if not isinstance(result, dict):
        return _boundary_error(
            "E_RUNTIME_BROKER",
            "persist payload.result must be an object",
            boundary="request-payload",
            actions=_allowed("Send a persist request with object payload.context and payload.result."),
        )
    session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
    try:
        turn_runtime._validate_product_persist_context_binding(context, session)
    except turn_runtime.RuntimeFeedbackError as exc:
        return _error(exc.code, exc.message, exc.details)
    persisted = persist_buddy_run_request(context, result=result, manifest_path=manifest_path)
    if persisted.get("ok") is not True:
        error = persisted.get("error") if isinstance(persisted.get("error"), dict) else {}
        return _error_from_payload(error, default_code="E_RUNTIME_BROKER", default_message="persist rejected")
    binding = turn_runtime._persist_binding_from_payload(persisted)
    if binding is not None:
        task_id, track_id = binding
        try:
            turn_runtime._write_product_session_binding(session, task_id=task_id, track_id=track_id)
        except (OSError, ValueError) as exc:
            turn_runtime._mark_committed_binding_update_failed(persisted, session, exc)
    return {"ok": True, "payload": persisted}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _context_matches_active_instance(*, context: dict[str, Any], instance_record: dict[str, Any], buddy_id: str) -> None:
    if context.get("ok") is not True:
        turn_runtime._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context must be successful before issuing browser evidence",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=turn_runtime._rerun_prepare_actions(),
        )
    if context.get("instance_id") != instance_record.get("instance_id"):
        turn_runtime._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context instance_id mismatch for evidence issuance",
            permission_boundary="active-instance",
            allowed_next_actions=turn_runtime._rerun_prepare_actions(),
        )
    if context.get("active_buddy") != buddy_id:
        turn_runtime._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context active_buddy mismatch for evidence issuance",
            permission_boundary="active-buddy",
            allowed_next_actions=turn_runtime._rerun_prepare_actions(),
        )

    task_id = context.get("current_task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("context.current_task_id is required for evidence issuance")
    context_track_id = context.get("current_track_id")
    if context_track_id is not None and not isinstance(context_track_id, str):
        raise ValueError("context.current_track_id must be a string when provided")

    bound_task = instance_record.get("current_task_id")
    if isinstance(bound_task, str) and bound_task.strip() and bound_task != task_id:
        turn_runtime._raise_runtime_feedback(
            "E_RUNTIME_BROKER",
            "context task_id does not match active instance binding",
            permission_boundary="active-instance",
            allowed_next_actions=turn_runtime._rerun_prepare_actions(),
        )
    bound_track = instance_record.get("current_track_id")
    if isinstance(bound_track, str) and bound_track.strip():
        if not isinstance(context_track_id, str) or context_track_id != bound_track:
            turn_runtime._raise_runtime_feedback(
                "E_RUNTIME_BROKER",
                "context track_id does not match active instance binding",
                permission_boundary="active-instance",
                allowed_next_actions=turn_runtime._rerun_prepare_actions(),
            )

    context_revision = context.get("context_revision")
    if not isinstance(context_revision, str) or not context_revision.strip():
        raise ValueError("context.context_revision is required for evidence issuance")
    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("context.run_envelope is required for evidence issuance")
    run_id = run_envelope.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("context.run_envelope.run_id is required for evidence issuance")


def _instance_browser_url(instance_record: dict[str, Any]) -> str:
    port = instance_record.get("browser_port")
    if not isinstance(port, int):
        raise ValueError("instance browser_port is missing")
    if port < 1 or port > 65535:
        raise ValueError(f"invalid instance browser_port: {port}")
    return f"http://127.0.0.1:{port}"


def _require_browser_endpoint(url: str) -> None:
    probe_url = f"{url}/json/version"
    try:
        with urlopen(probe_url, timeout=3.0) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"browser endpoint probe failed: HTTP {response.status}")
    except (URLError, OSError, ValueError) as exc:
        raise ValueError(f"browser cockpit endpoint is unreachable: {probe_url}: {exc}") from exc


def _browser_target_is_usable_page(target: Any) -> bool:
    if not isinstance(target, dict):
        return False
    if target.get("type") != "page":
        return False
    url = target.get("url")
    if not isinstance(url, str):
        return False
    normalized = url.strip().lower()
    if not normalized:
        return False
    if normalized == "about:blank":
        return True
    if normalized.startswith("chrome://"):
        return False
    if normalized.startswith("chrome-untrusted://"):
        return False
    if normalized.startswith("devtools://"):
        return False
    return True


def _browser_has_usable_page(url: str) -> bool:
    targets_url = f"{url}/json/list"
    try:
        with urlopen(targets_url, timeout=3.0) as response:
            if response.status < 200 or response.status >= 300:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(payload, list):
        return False
    return any(_browser_target_is_usable_page(target) for target in payload)


def _browser_create_blank_page(url: str) -> bool:
    create_url = f"{url}/json/new?about:blank"
    request = Request(create_url, method="PUT")
    try:
        with urlopen(request, timeout=3.0) as response:
            return 200 <= response.status < 300
    except (URLError, OSError, ValueError):
        return False


def _require_browser_ready_page(url: str, *, instance_id: str) -> None:
    _require_browser_endpoint(url)
    if _browser_has_usable_page(url):
        return
    _browser_create_blank_page(url)
    if _browser_has_usable_page(url):
        return
    turn_runtime._raise_runtime_feedback(
        "E_RUNTIME_BROKER",
        "browser cockpit ready page is required before issuing browser evidence",
        permission_boundary="browser-cockpit-ready",
        stop_condition="browser cockpit is not ready for MCP page operations",
        allowed_next_actions=_allowed(
            "Restart or open the launcher-managed instance to rebuild browser cockpit readiness.",
            "Rerun browser ensure for the active launcher-managed instance.",
        ),
        command_hint=f"./buddyswitch-codex env browser ensure --instance {instance_id}",
    )


def _evidence_root(instance_json_path: Path) -> Path:
    return instance_json_path.parent / "runtime" / "evidence-tokens"


def _write_evidence_token(
    *,
    instance_json_path: Path,
    context: dict[str, Any],
    mode: str,
    reason: str | None,
    browser_url: str | None,
) -> dict[str, Any]:
    run_envelope = context["run_envelope"]
    run_id = str(run_envelope["run_id"]).strip()
    context_revision = str(context["context_revision"]).strip()
    buddy_id = str(context["active_buddy"]).strip()
    instance_id = str(context["instance_id"]).strip()
    task_id = str(context["current_task_id"]).strip()
    track_id = context.get("current_track_id")
    token_prefix = "evidence" if mode == "browser-cockpit-preflight" else "downgrade"
    token = f"{token_prefix}-{run_id}-{uuid.uuid4().hex[:8]}"

    root = _evidence_root(instance_json_path) / run_id
    root.mkdir(parents=True, exist_ok=True)
    token_path = root / f"{token}.json"
    payload: dict[str, Any] = {
        "token": token,
        "mode": mode,
        "instance_id": instance_id,
        "buddy_id": buddy_id,
        "task_id": task_id,
        "track_id": track_id if isinstance(track_id, str) and track_id else None,
        "context_revision": context_revision,
        "run_id": run_id,
        "issued_at": _now_iso(),
    }
    if browser_url is not None:
        payload["browser_url"] = browser_url
    if reason is not None:
        payload["reason"] = reason
    token_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    token_scope = {
        "instance_id": instance_id,
        "buddy_id": buddy_id,
        "task_id": task_id,
        "track_id": track_id if isinstance(track_id, str) and track_id else None,
        "context_revision": context_revision,
        "run_id": run_id,
    }
    if mode == "browser-cockpit-preflight":
        return {
            "ok": True,
            "tool_evidence": {"browser_cockpit_token": token},
            "feedback": {
                "mode": mode,
                "browser_url": browser_url,
                "persist_field": "tool_evidence.browser_cockpit_token",
                "token_scope": token_scope,
                "next_action": "Include tool_evidence.browser_cockpit_token in the next artifact-producing persist.",
            },
        }
    return {
        "ok": True,
        "tool_evidence": {"approved_downgrade_token": token},
        "feedback": {
            "mode": mode,
            "reason": reason,
            "persist_field": "tool_evidence.approved_downgrade_token",
            "token_scope": token_scope,
            "next_action": "Include tool_evidence.approved_downgrade_token in the next artifact-producing persist.",
        },
    }


def _issue_browser_evidence_dispatch(
    *,
    payload: dict[str, Any],
    profile: dict[str, Any],
    instance_record: dict[str, Any],
    instance_json_path: Path,
) -> dict[str, Any]:
    tool_capability = profile.get("tool_capability")
    if not isinstance(tool_capability, dict):
        raise ValueError("env profile tool_capability must be an object")
    if tool_capability.get("browser_cockpit") != "required":
        raise ValueError("active profile does not require browser cockpit evidence")
    if tool_capability.get("market_research_evidence") != "required":
        raise ValueError("active profile does not require market research evidence")

    context = payload.get("context")
    mode = payload.get("mode")
    reason = payload.get("reason")
    if not isinstance(context, dict):
        raise ValueError("issue_browser_evidence payload.context must be an object")
    if not isinstance(mode, str) or mode.strip() not in {"browser-cockpit-preflight", "approved-downgrade"}:
        raise ValueError("issue_browser_evidence payload.mode must be browser-cockpit-preflight|approved-downgrade")
    normalized_mode = mode.strip()
    normalized_reason = reason.strip() if isinstance(reason, str) else None
    if normalized_mode == "approved-downgrade":
        if not isinstance(normalized_reason, str) or not normalized_reason:
            raise ValueError("approved downgrade requires a non-empty reason")

    buddy_id = str(instance_record["buddy"]).strip()
    _context_matches_active_instance(context=context, instance_record=instance_record, buddy_id=buddy_id)

    browser_url: str | None = None
    if normalized_mode == "browser-cockpit-preflight":
        browser_url = _instance_browser_url(instance_record)
        _require_browser_ready_page(browser_url, instance_id=str(instance_record["instance_id"]).strip())

    payload_out = _write_evidence_token(
        instance_json_path=instance_json_path,
        context=context,
        mode=normalized_mode,
        reason=normalized_reason,
        browser_url=browser_url,
    )
    return {"ok": True, "payload": payload_out}


def _env_task_dispatch(
    *,
    payload: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    instance_id = str(instance_record["instance_id"]).strip()
    active_buddy = str(instance_record["buddy"]).strip()
    return dispatch_task_manager_request(
        payload=payload,
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json_path,
        instance_payload=dict(instance_record),
        manifest=manifest,
    )


def dispatch_runtime_request(
    *,
    request: dict[str, Any],
    instance_json_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    try:
        if request.get("protocol") != PROTOCOL:
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"unsupported protocol: {request.get('protocol')!r}",
                boundary="broker-protocol",
                actions=_allowed("Use the launcher-managed BuddySwitch runtime tools instead of direct broker calls."),
            )
        method = request.get("method")
        if not isinstance(method, str) or not method.strip():
            raise ValueError("request.method must be a non-empty string")
        method = method.strip()

        payload = request.get("payload")
        if not isinstance(payload, dict):
            return _boundary_error(
                "E_RUNTIME_BROKER",
                "request.payload must be an object",
                boundary="request-payload",
                actions=_allowed("Send a broker request with an object payload."),
            )

        instance_record = _load_instance_record(instance_json_path)
        request_instance_id = request.get("instance_id")
        request_buddy = request.get("active_buddy")

        instance_id = str(instance_record["instance_id"]).strip()
        active_buddy = str(instance_record["buddy"]).strip()
        if request_instance_id != instance_id:
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"instance_id mismatch: expected '{instance_id}', got '{request_instance_id}'",
                boundary="active-instance",
                actions=_allowed("Use the active launcher-managed instance id.", "Rerun prepare in the active instance."),
            )
        if request_buddy != active_buddy:
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"active_buddy mismatch: expected '{active_buddy}', got '{request_buddy}'",
                boundary="active-buddy",
                actions=_allowed("Use the active buddy locked by the launcher.", "Rerun prepare in the active instance."),
            )
        status = instance_record.get("status")
        if status != "active":
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"instance is not active: {status!r}",
                boundary="active-instance-status",
                actions=_allowed("Open an active launcher-managed instance before calling runtime tools."),
            )

        profile = env_profiles.require_env_profile(
            active_buddy,
            manifest_path=manifest_path,
            repo_root=Path(__file__).resolve().parents[2],
        )

        with _runtime_server_env(
            instance_id=instance_id,
            buddy_id=active_buddy,
            instance_json_path=instance_json_path,
        ):
            if method == "prepare":
                lock_session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
                with turn_runtime._hold_product_runtime_lock(lock_session):
                    locked_instance_record = _load_instance_record(instance_json_path)
                    return _prepare_dispatch(
                        payload=payload,
                        manifest_path=manifest_path,
                        instance_json_path=instance_json_path,
                        instance_record=locked_instance_record,
                    )
            if method == "persist":
                lock_session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
                with turn_runtime._hold_product_runtime_lock(lock_session):
                    locked_instance_record = _load_instance_record(instance_json_path)
                    return _persist_dispatch(
                        payload=payload,
                        manifest_path=manifest_path,
                        instance_json_path=instance_json_path,
                        instance_record=locked_instance_record,
                    )
            if method == "env.task":
                lock_session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
                with turn_runtime._hold_product_runtime_lock(lock_session):
                    locked_instance_record = _load_instance_record(instance_json_path)
                    return _env_task_dispatch(
                        payload=payload,
                        manifest_path=manifest_path,
                        instance_json_path=instance_json_path,
                        instance_record=locked_instance_record,
                    )
            if method == "issue_browser_evidence":
                return _issue_browser_evidence_dispatch(
                    payload=payload,
                    profile=profile,
                    instance_record=instance_record,
                    instance_json_path=instance_json_path,
                )
        return _boundary_error(
            "E_RUNTIME_BROKER",
            f"unsupported method: {method}",
            boundary="broker-protocol",
            actions=_allowed("Use supported runtime methods: prepare, persist, env.task, issue_browser_evidence."),
        )
    except turn_runtime.RuntimeFeedbackError as exc:
        return _error(exc.code, exc.message, exc.details)
    except (ValueError, OSError, json.JSONDecodeError, ManifestError, env_profiles.EnvProfileError) as exc:
        return _error("E_RUNTIME_BROKER", str(exc))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BuddySwitch runtime broker.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Serve runtime broker socket")
    serve.add_argument("--socket", required=True, type=Path)
    serve.add_argument("--pid-file", required=True, type=Path)
    serve.add_argument("--instance-json", required=True, type=Path)
    serve.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def _serve(*, socket_path: Path, pid_file: Path, instance_json: Path, manifest: Path) -> int:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    if socket_path.exists():
        socket_path.unlink()

    lock = threading.Lock()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        server.listen(16)
        os.chmod(socket_path, 0o600)
        while True:
            conn, _ = server.accept()
            with conn:
                chunks: list[bytes] = []
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                try:
                    request = json.loads(b"".join(chunks).decode("utf-8"))
                except json.JSONDecodeError as exc:
                    response = _error("E_RUNTIME_BROKER", f"invalid request JSON: {exc}")
                else:
                    if not isinstance(request, dict):
                        response = _error("E_RUNTIME_BROKER", "request must be a JSON object")
                    else:
                        with lock:
                            response = dispatch_runtime_request(
                                request=request,
                                instance_json_path=instance_json,
                                manifest_path=manifest,
                            )
                conn.sendall(json.dumps(response, ensure_ascii=True).encode("utf-8"))


def main() -> int:
    args = _parse_args()
    if args.command != "serve":
        return 2
    try:
        return _serve(
            socket_path=args.socket,
            pid_file=args.pid_file,
            instance_json=args.instance_json,
            manifest=args.manifest,
        )
    finally:
        if args.command == "serve":
            try:
                args.socket.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
