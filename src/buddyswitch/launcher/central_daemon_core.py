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


from buddyswitch.launcher import daemon_mailbox  # noqa: E402
from buddyswitch.env.domain.identity import ACTOR_ID_PATTERN, ROLE_ID_PATTERN  # noqa: E402
from buddyswitch.foundation.daemon import client as daemon_client  # noqa: E402
from buddyswitch.runtime_kernel import protocol  # noqa: E402
from buddyswitch.runtime_kernel import process_identity  # noqa: E402


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
        self.pid_identity_file = process_identity.identity_file(self.pid_file)
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


def _actor_identity_id(value: Any, field: str = "identity_id") -> str:
    if not isinstance(value, str) or ACTOR_ID_PATTERN.fullmatch(value.strip()) is None:
        raise CentralDaemonError("invalid_identity_id", f"{field} must be a valid actor identity id")
    return value.strip()


def _actor_identity_route(params: dict[str, Any]) -> dict[str, str]:
    return {
        "identity_id": _actor_identity_id(params.get("identity_id")),
        "role_id": _require_role_id(params.get("role_id")),
    }


def _require_role_id(value: Any) -> str:
    if not isinstance(value, str) or ROLE_ID_PATTERN.fullmatch(value.strip()) is None:
        raise CentralDaemonError("invalid_role_id", "role_id must match /^[a-z][a-z0-9-]*$/")
    return value.strip()


def _normalize_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    try:
        identity_id = _actor_identity_id(row.get("identity_id"))
        role_id = _require_role_id(row.get("role_id"))
    except Exception:
        return None
    endpoint = row.get("endpoint")
    heartbeat = row.get("heartbeat")
    status = row.get("status")
    last_seen_at = row.get("last_seen_at")
    return {
        "identity_id": identity_id,
        "identity": {"id": identity_id, "type": "actor"},
        "role_id": role_id,
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
        identity_id = row["identity_id"]
        actors = [
            existing
            for existing in registry["actors"]
            if existing.get("identity_id") != identity_id
        ]
        actors.append(row)
        self._save_registry({"actors": actors})
        return row

    def _record_for_identity_id(self, identity_id: str) -> dict[str, Any] | None:
        for row in self._load_registry()["actors"]:
            if row.get("identity_id") == identity_id:
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
            if method == "actor_directory.list_online":
                return self._list_online_actors(params)
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
        route = _actor_identity_route(params)
        endpoint = _require_object(params.get("endpoint"), "endpoint")
        heartbeat_raw = params.get("heartbeat")
        heartbeat = dict(heartbeat_raw) if isinstance(heartbeat_raw, dict) else {"kind": "central_daemon_rpc"}
        status_raw = params.get("status")
        status = status_raw if status_raw in {"online", "registered_offline"} else "online"
        row = {
            "identity_id": route["identity_id"],
            "identity": {"id": route["identity_id"], "type": "actor"},
            "role_id": route["role_id"],
            "endpoint": endpoint,
            "heartbeat": heartbeat,
            "status": status,
            "last_seen_at": self.now(),
        }
        return {"record": self._upsert_actor(row)}

    def _unregister(self, params: dict[str, Any]) -> dict[str, Any]:
        route = _actor_identity_route(params)
        row = self._record_for_identity_id(route["identity_id"])
        if row is None:
            row = {
                "identity_id": route["identity_id"],
                "identity": {"id": route["identity_id"], "type": "actor"},
                "role_id": route["role_id"],
                "endpoint": {},
                "heartbeat": {},
                "status": "registered_offline",
                "last_seen_at": self.now(),
            }
        else:
            row = dict(row, status="registered_offline", last_seen_at=self.now())
        return {"record": self._upsert_actor(row)}

    def _heartbeat(self, params: dict[str, Any]) -> dict[str, Any]:
        identity_id = _actor_identity_id(params.get("identity_id"))
        row = self._record_for_identity_id(identity_id)
        if row is None:
            raise CentralDaemonError("never_registered", "actor identity has never registered")
        row = dict(row, status="online", last_seen_at=self.now())
        return {"record": self._upsert_actor(row)}

    def _list_online_actors(self, params: dict[str, Any]) -> dict[str, Any]:
        role_filter = params.get("role_id")
        normalized_role = _require_role_id(role_filter) if isinstance(role_filter, str) and role_filter.strip() else None
        actors: list[dict[str, Any]] = []
        for row in self._load_registry()["actors"]:
            if row.get("status") != "online":
                continue
            if normalized_role is not None and row.get("role_id") != normalized_role:
                continue
            actors.append(dict(row))
        return {"actors": actors, "count": len(actors)}

    def _reachability(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            identity_id = _actor_identity_id(params.get("target_identity_id"), "target_identity_id")
        except Exception as exc:
            return {
                "reachability_status": "invalid_identity_id",
                "target_identity_id": None,
                "reason": str(exc),
            }
        row = self._record_for_identity_id(identity_id)
        if row is None:
            return {
                "reachability_status": "never_registered",
                "target_identity_id": identity_id,
                "record": None,
            }
        status = "online" if row.get("status") == "online" else "registered_offline"
        return {
            "reachability_status": status,
            "target_identity_id": identity_id,
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
        reachability = self._reachability({"target_identity_id": signal["target_identity_id"]})
        if reachability["reachability_status"] != "online":
            return {
                "delivery_status": "target_not_online",
                "handling_status": "ignored",
                "reachability_status": reachability["reachability_status"],
                "target_identity_id": signal["target_identity_id"],
            }
        record = reachability.get("record")
        endpoint = record.get("endpoint") if isinstance(record, dict) else None
        if not isinstance(endpoint, dict) or endpoint.get("kind") != "daemon_mailbox_socket":
            return {
                "delivery_status": "delivery_failed",
                "handling_status": "ignored",
                "signal_error": "target endpoint is not daemon_mailbox_socket",
                "target_identity_id": signal["target_identity_id"],
                "signal": signal,
            }
        socket_raw = endpoint.get("socket_path")
        if not isinstance(socket_raw, str) or not socket_raw.strip():
            return {
                "delivery_status": "delivery_failed",
                "handling_status": "ignored",
                "signal_error": "target mailbox socket_path is required",
                "target_identity_id": signal["target_identity_id"],
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
                "target_identity_id": signal["target_identity_id"],
                "signal": signal,
            }
        result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
        handling_status = result.get("handling_status") if isinstance(result.get("handling_status"), str) else "ignored"
        return {
            "delivery_status": "delivered",
            "handling_status": handling_status,
            "target_identity_id": signal["target_identity_id"],
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
            process_identity.write_record(paths.pid_file, os.getpid())
            try:
                while not self._stop_event.is_set():
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
                for path in (
                    paths.socket_path,
                    paths.pid_file,
                    paths.pid_identity_file,
                ):
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
