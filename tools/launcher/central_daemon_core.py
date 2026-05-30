#!/usr/bin/env python3
"""Shared-root central daemon service."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys
import threading
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_mailbox  # noqa: E402
from env.tool_runtime.actor_profile import BUDDY_ID_PATTERN, RuntimeActorAddress  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402
from runtime_kernel import protocol  # noqa: E402


class CentralDaemonError(ValueError):
    def __init__(self, code: str, message: str, *, retriable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retriable = retriable


class CentralDaemonPaths:
    def __init__(self, shared_root: Path) -> None:
        self.shared_root = Path(shared_root).expanduser().resolve(strict=False)
        self.run_dir = self.shared_root / "run" / "central-daemon"
        self.socket_path = daemon_client.central_daemon_socket_path_for_shared_root(self.shared_root)
        self.pid_file = self.run_dir / "central-daemon.pid"
        self.log_file = self.run_dir / "central-daemon.log"
        self.registry_path = self.shared_root / "state" / "runtime" / "central-daemon" / "registry.json"


def central_daemon_paths(shared_root: Path) -> CentralDaemonPaths:
    return CentralDaemonPaths(shared_root)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CentralDaemonError("invalid_payload", f"{field} must be an object")
    return dict(value)


def _actor_address(value: Any) -> RuntimeActorAddress:
    try:
        return RuntimeActorAddress.from_payload(value)
    except Exception as exc:
        raise CentralDaemonError("invalid_actor_address", str(exc)) from exc


def _require_buddy_id(value: Any) -> str:
    if not isinstance(value, str) or BUDDY_ID_PATTERN.fullmatch(value.strip()) is None:
        raise CentralDaemonError("invalid_buddy_id", "buddy_id must match /^[a-z][a-z0-9-]*$/")
    return value.strip()


def _test_runtime_cleanup_in_progress(paths: CentralDaemonPaths) -> bool:
    registry_raw = os.environ.get("BUDDYSWITCH_TEST_PROCESS_REGISTRY")
    if not isinstance(registry_raw, str) or not registry_raw.strip():
        return False
    return paths.shared_root.exists() and not paths.pid_file.exists()


def _normalize_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    try:
        address = RuntimeActorAddress.from_payload(row.get("actor_address"))
    except Exception:
        return None
    endpoint = row.get("endpoint")
    heartbeat = row.get("heartbeat")
    status = row.get("status")
    last_seen_at = row.get("last_seen_at")
    return {
        "actor_address": address.to_payload(),
        "endpoint": dict(endpoint) if isinstance(endpoint, dict) else {},
        "heartbeat": dict(heartbeat) if isinstance(heartbeat, dict) else {},
        "status": status if status in {"online", "registered_offline"} else "registered_offline",
        "last_seen_at": last_seen_at if isinstance(last_seen_at, str) else "",
    }


class CentralDaemonService:
    def __init__(self, *, paths: CentralDaemonPaths, now: Any = utc_now) -> None:
        self.paths = paths
        self.now = now
        self._lock = threading.RLock()

    def _load_registry(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.paths.registry_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"actors": []}
        except json.JSONDecodeError as exc:
            raise CentralDaemonError("invalid_registry", f"invalid central daemon registry JSON: {exc}") from exc
        rows = payload.get("actors") if isinstance(payload, dict) else []
        actors: list[dict[str, Any]] = []
        if isinstance(rows, list):
            for row in rows:
                normalized = _normalize_row(row)
                if normalized is not None:
                    actors.append(normalized)
        return {"actors": actors}

    def _save_registry(self, payload: dict[str, Any]) -> dict[str, Any]:
        if _test_runtime_cleanup_in_progress(self.paths):
            raise CentralDaemonError(
                "test_runtime_cleanup_in_progress",
                "central daemon shared root is being removed by test cleanup",
                retriable=True,
            )
        rows = payload.get("actors") if isinstance(payload, dict) else []
        normalized_rows = []
        if isinstance(rows, list):
            for row in rows:
                normalized = _normalize_row(row)
                if normalized is not None:
                    normalized_rows.append(normalized)
        normalized = {"actors": normalized_rows}
        self.paths.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.paths.registry_path.with_name(f".{self.paths.registry_path.name}.{os.getpid()}.tmp")
        temp_path.write_text(json.dumps(normalized, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.paths.registry_path)
        return normalized

    def _upsert_actor(self, row: dict[str, Any]) -> dict[str, Any]:
        registry = self._load_registry()
        instance_id = row["actor_address"]["instance_id"]
        actors = [
            existing
            for existing in registry["actors"]
            if existing.get("actor_address", {}).get("instance_id") != instance_id
        ]
        actors.append(row)
        self._save_registry({"actors": actors})
        return row

    def _record_for_address(self, address: RuntimeActorAddress) -> dict[str, Any] | None:
        for row in self._load_registry()["actors"]:
            if row.get("actor_address") == address.to_payload():
                return row
        return None

    def handle(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(method, str) or not method.strip():
            raise CentralDaemonError("invalid_payload", "method must be a non-empty string")
        if not isinstance(params, dict):
            raise CentralDaemonError("invalid_payload", "params must be an object")
        with self._lock:
            if method == "daemon.ping":
                return {
                    "ok": True,
                    "pid": os.getpid(),
                    "socket_path": str(self.paths.socket_path),
                    "registry_path": str(self.paths.registry_path),
                }
            if method == "daemon.register":
                return self._register(params)
            if method == "daemon.unregister":
                return self._unregister(params)
            if method == "daemon.heartbeat":
                return self._heartbeat(params)
            if method == "daemon.registry":
                return self._load_registry()
            if method == "contacts.list":
                return self._contacts(params)
            if method == "actor.check_reachability":
                return self._reachability(params)
            if method == "signal.deliver":
                return self._deliver_signal(params)
            if method == "event.deliver":
                return self._deliver_signal(params)
        raise CentralDaemonError("unknown_method", f"unsupported central daemon method: {method}")

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
        try:
            if not isinstance(request, dict):
                raise CentralDaemonError("invalid_payload", "request must be an object")
            if "protocol" in request and request.get("protocol") != daemon_client.CENTRAL_DAEMON_PROTOCOL:
                raise CentralDaemonError("invalid_protocol", "unsupported central daemon protocol")
            method = request.get("method")
            params = request.get("params")
            if not isinstance(method, str) or not method.strip():
                raise CentralDaemonError("invalid_payload", "method must be a non-empty string")
            if not isinstance(params, dict):
                raise CentralDaemonError("invalid_payload", "params must be an object")
            result = self.handle(method, params)
            return {
                "protocol": daemon_client.CENTRAL_DAEMON_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "result": result,
            }
        except CentralDaemonError as exc:
            return {
                "protocol": daemon_client.CENTRAL_DAEMON_PROTOCOL,
                "request_id": request_id,
                "ok": False,
                "error": {"code": exc.code, "message": exc.message, "retriable": exc.retriable},
            }
        except Exception as exc:
            return {
                "protocol": daemon_client.CENTRAL_DAEMON_PROTOCOL,
                "request_id": request_id,
                "ok": False,
                "error": {"code": "central_daemon_internal_error", "message": str(exc), "retriable": False},
            }

    def _register(self, params: dict[str, Any]) -> dict[str, Any]:
        address = _actor_address(params.get("actor_address"))
        endpoint = _require_object(params.get("endpoint"), "endpoint")
        heartbeat_raw = params.get("heartbeat")
        heartbeat = dict(heartbeat_raw) if isinstance(heartbeat_raw, dict) else {"kind": "central_daemon_rpc"}
        status_raw = params.get("status")
        status = status_raw if status_raw in {"online", "registered_offline"} else "online"
        row = {
            "actor_address": address.to_payload(),
            "endpoint": endpoint,
            "heartbeat": heartbeat,
            "status": status,
            "last_seen_at": self.now(),
        }
        return {"record": self._upsert_actor(row)}

    def _unregister(self, params: dict[str, Any]) -> dict[str, Any]:
        address = _actor_address(params.get("actor_address"))
        row = self._record_for_address(address)
        if row is None:
            row = {
                "actor_address": address.to_payload(),
                "endpoint": {},
                "heartbeat": {},
                "status": "registered_offline",
                "last_seen_at": self.now(),
            }
        else:
            row = dict(row, status="registered_offline", last_seen_at=self.now())
        return {"record": self._upsert_actor(row)}

    def _heartbeat(self, params: dict[str, Any]) -> dict[str, Any]:
        address = _actor_address(params.get("actor_address"))
        row = self._record_for_address(address)
        if row is None:
            raise CentralDaemonError("never_registered", "actor address has never registered")
        row = dict(row, status="online", last_seen_at=self.now())
        return {"record": self._upsert_actor(row)}

    def _contacts(self, params: dict[str, Any]) -> dict[str, Any]:
        buddy_filter = params.get("buddy_id")
        normalized_buddy = _require_buddy_id(buddy_filter) if isinstance(buddy_filter, str) and buddy_filter.strip() else None
        contacts: list[dict[str, Any]] = []
        for row in self._load_registry()["actors"]:
            if row.get("status") != "online":
                continue
            address = RuntimeActorAddress.from_payload(row["actor_address"])
            if normalized_buddy is not None and address.buddy_id != normalized_buddy:
                continue
            contacts.append(dict(row))
        return {"contacts": contacts, "count": len(contacts)}

    def _reachability(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            address = RuntimeActorAddress.from_payload(params.get("target_actor_address"))
        except Exception as exc:
            return {
                "reachability_status": "invalid_actor_address",
                "target_actor_address": None,
                "reason": str(exc),
            }
        row = self._record_for_address(address)
        if row is None:
            return {
                "reachability_status": "never_registered",
                "target_actor_address": address.to_payload(),
                "record": None,
            }
        status = "online" if row.get("status") == "online" else "registered_offline"
        return {
            "reachability_status": status,
            "target_actor_address": address.to_payload(),
            "record": row,
        }

    def _deliver_signal(self, params: dict[str, Any]) -> dict[str, Any]:
        candidate = params.get("signal")
        if candidate is None:
            candidate = params.get("event")
        try:
            signal = daemon_mailbox.validate_daemon_signal(candidate)
        except Exception as exc:
            return {
                "delivery_status": "invalid_signal",
                "handling_status": "ignored",
                "signal_error": str(exc),
            }
        reachability = self._reachability({"target_actor_address": signal["target_actor_address"]})
        if reachability["reachability_status"] != "online":
            return {
                "delivery_status": "target_not_online",
                "handling_status": "ignored",
                "reachability_status": reachability["reachability_status"],
                "target_actor_address": signal["target_actor_address"],
            }
        record = reachability.get("record")
        endpoint = record.get("endpoint") if isinstance(record, dict) else None
        if not isinstance(endpoint, dict) or endpoint.get("kind") != "daemon_mailbox_socket":
            return {
                "delivery_status": "delivery_failed",
                "handling_status": "ignored",
                "signal_error": "target endpoint is not daemon_mailbox_socket",
                "target_actor_address": signal["target_actor_address"],
                "signal": signal,
            }
        socket_raw = endpoint.get("socket_path")
        if not isinstance(socket_raw, str) or not socket_raw.strip():
            return {
                "delivery_status": "delivery_failed",
                "handling_status": "ignored",
                "signal_error": "target mailbox socket_path is required",
                "target_actor_address": signal["target_actor_address"],
                "signal": signal,
            }
        envelope = daemon_client.request_mailbox(
            "mailbox.deliver",
            {"signal": signal},
            socket_path=Path(socket_raw),
        )
        if envelope.get("ok") is not True:
            error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
            return {
                "delivery_status": "delivery_failed",
                "handling_status": "ignored",
                "signal_error": error.get("message") if isinstance(error.get("message"), str) else "mailbox delivery failed",
                "target_actor_address": signal["target_actor_address"],
                "signal": signal,
            }
        result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
        handling_status = result.get("handling_status") if isinstance(result.get("handling_status"), str) else "ignored"
        return {
            "delivery_status": "delivered",
            "handling_status": handling_status,
            "target_actor_address": signal["target_actor_address"],
            "signal": signal,
            "handling_result": result,
        }


class CentralDaemonSocketServer:
    def __init__(self, *, service: CentralDaemonService) -> None:
        self.service = service
        self._stop_event = threading.Event()
        self._server: socket.socket | None = None

    def close(self) -> None:
        self._stop_event.set()
        server = self._server
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        paths = self.service.paths
        paths.run_dir.mkdir(parents=True, exist_ok=True)
        paths.log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            paths.socket_path.unlink()
        except FileNotFoundError:
            pass
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            self._server = server
            server.bind(str(paths.socket_path))
            server.listen(64)
            server.settimeout(0.05)
            os.chmod(paths.socket_path, 0o600)
            paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            try:
                while not self._stop_event.is_set():
                    if _test_runtime_cleanup_in_progress(paths):
                        break
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        if self._stop_event.is_set():
                            break
                        continue
                    self._handle_connection(conn)
            finally:
                self._server = None
                for path in (paths.socket_path, paths.pid_file):
                    try:
                        path.unlink()
                    except OSError:
                        pass

    def _handle_connection(self, conn: socket.socket) -> None:
        request_id: str | None = None
        with conn:
            try:
                request = protocol.read_message(conn)
                request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
                response = self.service.dispatch(request)
            except Exception as exc:
                response = {
                    "protocol": daemon_client.CENTRAL_DAEMON_PROTOCOL,
                    "request_id": request_id,
                    "ok": False,
                    "error": {"code": "central_daemon_protocol_error", "message": str(exc), "retriable": False},
                }
            try:
                protocol.write_message(conn, response)
            except OSError:
                return
