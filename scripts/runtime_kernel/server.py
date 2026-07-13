"""Runtime broker v2 Unix socket server with bounded request isolation."""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from pathlib import Path
import socket
import threading
from typing import Any, Callable

from runtime_kernel import coordinator, dispatcher, protocol


@dataclass(frozen=True)
class RuntimeBrokerConfig:
    socket_path: Path
    pid_file: Path
    instance_json_path: Path
    manifest_path: Path
    repo_root_path: Path | None = None
    max_workers: int = 4
    request_body_limit_bytes: int = 1048576
    response_margin_ms: int = 1000


class RuntimeBrokerServer:
    def __init__(self, *, config: RuntimeBrokerConfig, dispatch_fn: Callable[..., dict[str, Any]]) -> None:
        self.config = config
        self.dispatch_fn = dispatch_fn
        self._stop_event = threading.Event()
        self._server: socket.socket | None = None
        self._capacity = threading.BoundedSemaphore(max(1, int(config.max_workers)))
        self._session = dispatcher.RuntimeBrokerSession(
            instance_json_path=config.instance_json_path,
            manifest_path=config.manifest_path,
            repo_root_path=config.repo_root_path,
            socket_path=config.socket_path,
            pid_file=config.pid_file,
        )
        self._dispatch_wants_session = len(inspect.signature(dispatch_fn).parameters) >= 2

    def close(self) -> None:
        self._stop_event.set()
        server = self._server
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        self.config.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.socket_path.unlink(missing_ok=True)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            self._server = server
            server.bind(str(self.config.socket_path))
            server.listen(64)
            os.chmod(self.config.socket_path, 0o600)
            self.config.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            try:
                while not self._stop_event.is_set():
                    try:
                        conn, _ = server.accept()
                    except OSError:
                        if self._stop_event.is_set():
                            break
                        continue
                    thread = threading.Thread(target=self._handle_connection, args=(conn,), daemon=True)
                    thread.start()
            finally:
                self._server = None
                try:
                    self.config.socket_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._dispatch_wants_session:
            return self.dispatch_fn(request, self._session)
        return self.dispatch_fn(request)

    def _dispatch_with_coordination(self, request: dict[str, Any]) -> dict[str, Any]:
        business = coordinator.dispatch_with_coordination(
            request,
            {
                "instance_json": self.config.instance_json_path,
                "manifest_path": self.config.manifest_path,
                "actor_id": None,
                "active_role": None,
                "payload": {},
            },
            lambda req, _session: self._dispatch(req),
            response_margin_ms=self.config.response_margin_ms,
        )
        return business

    def _write_response(self, conn: socket.socket, payload: dict[str, Any]) -> None:
        protocol.write_message(conn, payload)

    def _handle_connection(self, conn: socket.socket) -> None:
        request_id: str | None = None
        with conn:
            try:
                request = protocol.read_message(
                    conn,
                    body_limit_bytes=self.config.request_body_limit_bytes,
                )
                validated = protocol.validate_request(request)
                request_id = validated.get("request_id") if isinstance(validated.get("request_id"), str) else None
            except protocol.BrokerProtocolError as exc:
                try:
                    self._write_response(
                        conn,
                        protocol.error_response(
                            exc.request_id,
                            code=exc.code,
                            message=exc.message,
                            retriable=False,
                        ),
                    )
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                return
            except (ValueError, OSError) as exc:
                try:
                    self._write_response(
                        conn,
                        protocol.error_response(
                            request_id,
                            code="E_RUNTIME_BROKER_PROTOCOL",
                            message=str(exc),
                            retriable=False,
                        ),
                    )
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                return

            if not self._capacity.acquire(blocking=False):
                try:
                    busy = protocol.error_response(
                        request_id,
                        code="E_RUNTIME_BROKER_BUSY",
                        message="runtime broker is at request capacity",
                        retriable=True,
                        retry_after_ms=250,
                    )
                    busy["broker_status"] = {
                        "pid": os.getpid(),
                        "socket_path": str(self.config.socket_path),
                    }
                    self._write_response(
                        conn,
                        busy,
                    )
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                return

            try:
                business = self._dispatch_with_coordination(validated)
                if not isinstance(business, dict):
                    business = {
                        "ok": False,
                        "error": {
                            "code": "E_RUNTIME_BROKER_PROTOCOL",
                            "message": "dispatcher returned non-object response",
                            "retriable": False,
                        },
                    }
                if business.get("ok") is True:
                    response = protocol.success_response(request_id, business)
                else:
                    error = business.get("error") if isinstance(business.get("error"), dict) else {}
                    code = error.get("code") if isinstance(error.get("code"), str) else "E_RUNTIME_BROKER_PERMISSION"
                    message = error.get("message") if isinstance(error.get("message"), str) else "runtime broker request failed"
                    retriable = bool(error.get("retriable", False))
                    extra = {
                        key: value
                        for key, value in business.items()
                        if key not in {"ok", "error"}
                    }
                    retry_after_ms = error.get("retry_after_ms") if isinstance(error.get("retry_after_ms"), int) else None
                    response = protocol.error_response(
                        request_id,
                        code=code,
                        message=message,
                        retriable=retriable,
                        retry_after_ms=retry_after_ms,
                    )
                    response.update(extra)
            except TimeoutError as exc:
                response = protocol.error_response(
                    request_id,
                    code="E_RUNTIME_BROKER_DEADLINE_EXCEEDED",
                    message=str(exc),
                    retriable=True,
                    retry_after_ms=250,
                )
            except Exception as exc:  # pragma: no cover - defensive isolation
                response = protocol.error_response(
                    request_id,
                    code="E_RUNTIME_BROKER_PROTOCOL",
                    message=f"runtime broker internal error: {exc}",
                    retriable=False,
                )
            finally:
                self._capacity.release()

            try:
                self._write_response(conn, response)
            except BrokenPipeError:
                # Client disconnected before response write; broker keeps serving.
                return
            except ConnectionResetError:
                return
            except OSError:
                return
