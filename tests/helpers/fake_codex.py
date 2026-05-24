#!/usr/bin/env python3
"""Fake codex executable for BuddySwitch launcher tests."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
RUNNING = True
MEMORY_STATE: dict[str, object] = {}


def _handle_exit(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(_sig, _handle_exit)


def append_calls(payload: dict[str, object]) -> None:
    calls_path = os.environ.get("BUDDYSWITCH_TEST_CALLS")
    if not calls_path:
        return
    path = Path(calls_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def remove_mcp_section(config_text: str, server_name: str) -> str:
    lines = config_text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    target = f"[mcp_servers.{server_name}]"
    while index < len(lines):
        if lines[index].strip() == target:
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith("["):
                index += 1
            continue
        output.append(lines[index])
        index += 1
    return "".join(output)


def upsert_mcp_section(codex_home: Path, server_name: str, argv: list[str]) -> None:
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    config_text = remove_mcp_section(config_text, server_name).rstrip() + "\n\n"
    separator_index = argv.index("--")
    command = argv[separator_index + 1]
    args = argv[separator_index + 2 :]
    section = (
        f"[mcp_servers.{server_name}]\n"
        f"command = {json.dumps(command)}\n"
        f"args = {json.dumps(args)}\n"
    )
    config_path.write_text(config_text + section, encoding="utf-8")


def maybe_capture_prepare_probe() -> dict[str, object] | None:
    if not os.environ.get("BUDDYSWITCH_TEST_PREPARE_TEXT"):
        return None
    prepare_result = subprocess.run(
        ["python3", "scripts/turn_runtime.py", "status"],
        cwd=os.getcwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    payload: dict[str, object] = {
        "returncode": prepare_result.returncode,
        "stdout": prepare_result.stdout,
        "stderr": prepare_result.stderr,
        "json": None,
    }
    if prepare_result.stdout.strip():
        try:
            payload["json"] = json.loads(prepare_result.stdout)
        except json.JSONDecodeError as exc:
            payload["json_error"] = str(exc)
    return payload


def maybe_capture_broker_probe(entry: dict[str, object]) -> dict[str, object] | None:
    if not os.environ.get("BUDDYSWITCH_TEST_BROKER_STATUS"):
        return None
    instance_json = entry.get("instance_json")
    if not isinstance(instance_json, str) or not instance_json:
        return None
    instance_json_path = Path(instance_json)
    runtime_dir = instance_json_path.parent / "runtime"
    status_result = subprocess.run(
        [
            "python3",
            "scripts/runtime_kernel/broker.py",
            "status",
            "--socket",
            entry.get("runtime_broker_socket") or str(runtime_dir / "runtime-broker.sock"),
            "--pid-file",
            str(runtime_dir / "runtime-broker.pid"),
            "--marker-file",
            str(runtime_dir / "runtime-broker.socket"),
            "--log-file",
            str(runtime_dir / "runtime-broker.log"),
            "--instance-json",
            str(instance_json_path),
            "--manifest",
            str(Path(os.getcwd()) / "buddyswitch" / "manifest.toml"),
        ],
        cwd=os.getcwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    payload: dict[str, object] = {
        "returncode": status_result.returncode,
        "stdout": status_result.stdout,
        "stderr": status_result.stderr,
        "json": None,
        "pid_file_text": (runtime_dir / "runtime-broker.pid").read_text(encoding="utf-8").strip()
        if (runtime_dir / "runtime-broker.pid").exists()
        else None,
        "marker_file_text": (runtime_dir / "runtime-broker.socket").read_text(encoding="utf-8").strip()
        if (runtime_dir / "runtime-broker.socket").exists()
        else None,
        "socket_exists": Path(str(entry.get("runtime_broker_socket"))).exists()
        if entry.get("runtime_broker_socket")
        else False,
    }
    if status_result.stdout.strip():
        try:
            payload["json"] = json.loads(status_result.stdout)
        except json.JSONDecodeError as exc:
            payload["json_error"] = str(exc)
    return payload


def maybe_capture_runtime_smoke() -> list[dict[str, object]] | None:
    if os.environ.get("BUDDYSWITCH_TEST_RUNTIME_COMMAND_SMOKE") != "1":
        return None
    rows: list[dict[str, object]] = []
    smoke_commands = (
        ("turn_runtime.status", ["python3", "scripts/turn_runtime.py", "status"]),
        ("context.summarize", ["python3", "scripts/env/client.py", "context", "summarize"]),
        ("buddybox.desc", ["python3", "scripts/env/client.py", "buddybox", "desc"]),
        ("search.status", ["python3", "scripts/env/client.py", "search", "status"]),
    )
    for name, command in smoke_commands:
        result = subprocess.run(
            command,
            cwd=os.getcwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        row: dict[str, object] = {
            "name": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "json": None,
        }
        if result.stdout.strip():
            try:
                row["json"] = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                row["json_error"] = str(exc)
        rows.append(row)
    return rows


def build_capture_payload(entry: dict[str, object], codex_home: Path, argv: list[str]) -> dict[str, object]:
    project_workspace_dir = entry["project_workspace_dir"]
    product_probe = None
    product_write = os.environ.get("BUDDYSWITCH_TEST_PRODUCT_WRITE")
    product_read = os.environ.get("BUDDYSWITCH_TEST_PRODUCT_READ")
    if project_workspace_dir and product_write:
        product_path = Path(project_workspace_dir) / "projects" / "app" / "shared-product-sentinel.txt"
        try:
            product_path.parent.mkdir(parents=True, exist_ok=True)
            product_path.write_text(product_write + "\n", encoding="utf-8")
            product_probe = {
                "ok": True,
                "path": str(product_path),
                "content": product_path.read_text(encoding="utf-8").strip(),
            }
        except Exception as exc:  # pragma: no cover - probe diagnostics only
            product_probe = {
                "ok": False,
                "path": str(product_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    elif project_workspace_dir and product_read:
        product_path = Path(project_workspace_dir) / "projects" / "app" / "shared-product-sentinel.txt"
        product_probe = {
            "path": str(product_path),
            "exists": product_path.exists(),
            "content": product_path.read_text(encoding="utf-8").strip() if product_path.exists() else None,
        }

    projects_app_path = Path("projects/app")
    projects_app_probe: dict[str, object] = {
        "path": str(projects_app_path),
        "exists": projects_app_path.exists(),
        "resolved": None,
    }
    try:
        projects_app_probe["resolved"] = str(projects_app_path.resolve(strict=True))
    except FileNotFoundError:
        pass
    except OSError as exc:
        projects_app_probe["resolve_error"] = str(exc)

    relative_probe = None
    relative_write_path = os.environ.get("BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH")
    relative_write_content = os.environ.get("BUDDYSWITCH_TEST_RELATIVE_WRITE_CONTENT")
    relative_read_path = os.environ.get("BUDDYSWITCH_TEST_RELATIVE_READ_PATH")
    if relative_write_path or relative_read_path:
        relative_probe = {}
    if relative_write_path:
        write_target = projects_app_path / relative_write_path
        write_value = relative_write_content if relative_write_content is not None else "relative-write"
        try:
            write_target.parent.mkdir(parents=True, exist_ok=True)
            write_target.write_text(write_value + "\n", encoding="utf-8")
            relative_probe["write"] = {
                "ok": True,
                "path": str(write_target),
                "resolved": str(write_target.resolve(strict=True)),
                "exists": write_target.exists(),
                "content": write_target.read_text(encoding="utf-8").strip(),
            }
        except Exception as exc:  # pragma: no cover - probe diagnostics only
            relative_probe["write"] = {
                "ok": False,
                "path": str(write_target),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "exists": write_target.exists(),
            }
    if relative_read_path:
        read_target = projects_app_path / relative_read_path
        relative_probe["read"] = {
            "path": str(read_target),
            "resolved": str(read_target.resolve(strict=False)),
            "exists": read_target.exists(),
            "content": read_target.read_text(encoding="utf-8").strip() if read_target.exists() else None,
        }

    instance_payload = None
    if entry["instance_json"]:
        instance_payload = json.loads(Path(str(entry["instance_json"])).read_text(encoding="utf-8"))

    counter_path = codex_home / "launch-count.txt"
    launch_count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0
    launch_count += 1
    counter_path.write_text(f"{launch_count}\n", encoding="utf-8")

    auth_payload = None
    auth_path = codex_home / "auth.json"
    if auth_path.exists():
        auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))

    return {
        **entry,
        "product_probe": product_probe,
        "projects_app_probe": projects_app_probe,
        "relative_probe": relative_probe,
        "prepare_probe": maybe_capture_prepare_probe(),
        "broker_status_probe": maybe_capture_broker_probe(entry),
        "runtime_command_smoke": maybe_capture_runtime_smoke(),
        "launch_count": launch_count,
        "config_toml": (codex_home / "config.toml").read_text(encoding="utf-8")
        if (codex_home / "config.toml").exists()
        else "",
        "auth_json": auth_payload,
        "instance_json_payload": instance_payload,
    }


def write_capture(payload: dict[str, object]) -> None:
    capture_path = os.environ.get("BUDDYSWITCH_TEST_CAPTURE")
    if not capture_path:
        return
    Path(capture_path).write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def server_state_path() -> Path | None:
    raw = os.environ.get("BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE")
    if not raw:
        return None
    return Path(raw)


def load_server_state(default_thread_id: str) -> dict[str, object]:
    global MEMORY_STATE
    path = server_state_path()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            state = {"thread_id": default_thread_id}
            path.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            return state
        payload = read_json(path)
        if "thread_id" not in payload:
            payload["thread_id"] = default_thread_id
        return payload
    if "thread_id" not in MEMORY_STATE:
        MEMORY_STATE = {"thread_id": default_thread_id}
    return dict(MEMORY_STATE)


def save_server_state(state: dict[str, object]) -> None:
    global MEMORY_STATE
    path = server_state_path()
    if path is not None:
        path.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return
    MEMORY_STATE = dict(state)


def default_thread(state: dict[str, object], *, status: object | None = None) -> dict[str, object]:
    thread_id = state.get("thread_id") or "thread-test"
    thread_status = status if status is not None else state.get("thread_status", {"type": "idle"})
    return {
        "id": thread_id,
        "sessionId": state.get("session_id", thread_id),
        "forkedFromId": None,
        "preview": "",
        "ephemeral": False,
        "modelProvider": "openai",
        "createdAt": 0,
        "updatedAt": 0,
        "status": thread_status,
        "path": None,
        "cwd": os.getcwd(),
        "cliVersion": "test",
        "source": "appServer",
        "threadSource": None,
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": None,
        "turns": [],
    }


def default_turn(turn_id: str, status: str = "inProgress") -> dict[str, object]:
    return {
        "id": turn_id,
        "items": [],
        "itemsView": "summary",
        "status": status,
        "error": None,
        "startedAt": 0,
        "completedAt": None,
        "durationMs": None,
    }


def build_default_result(method: str, params: dict[str, object] | None, state: dict[str, object]) -> dict[str, object]:
    if method == "thread/loaded/list":
        return {"data": [state.get("thread_id")], "nextCursor": None}
    if method == "thread/start":
        return {"thread": default_thread(state)}
    if method == "thread/read":
        return {"thread": default_thread(state)}
    if method == "thread/turns/list":
        return {
            "data": state.get("turns", []),
            "nextCursor": None,
            "backwardsCursor": None,
        }
    if method == "turn/start":
        next_turn_id = str(state.get("next_turn_id", "turn-test"))
        return {"turn": default_turn(next_turn_id)}
    if method == "turn/steer":
        expected_turn_id = None
        if isinstance(params, dict):
            expected_turn_id = params.get("expectedTurnId")
        return {"turnId": expected_turn_id or state.get("next_turn_id", "turn-test")}
    if method == "turn/interrupt":
        return {}
    return {}


def maybe_mutate_state(method: str, params: dict[str, object] | None, state: dict[str, object]) -> None:
    if method == "thread/start":
        state.setdefault("thread_status", {"type": "idle"})
        state.setdefault("turns", [])
        return
    if method == "turn/start":
        next_turn_id = str(state.get("next_turn_id", "turn-test"))
        state["thread_status"] = {"type": "active", "activeFlags": []}
        state["turns"] = [default_turn(next_turn_id)]
        return
    if method == "turn/steer":
        if not isinstance(state.get("turns"), list) or not state["turns"]:
            expected_turn_id = None
            if isinstance(params, dict):
                expected_turn_id = params.get("expectedTurnId")
            state["turns"] = [default_turn(str(expected_turn_id or state.get("next_turn_id", "turn-test")))]
        state["thread_status"] = {"type": "active", "activeFlags": []}
        return
    if method == "turn/interrupt":
        turns = state.get("turns")
        if isinstance(turns, list) and turns:
            turn = turns[0]
            if isinstance(turn, dict):
                turn["status"] = "interrupted"
        state["thread_status"] = {"type": "idle"}


def rpc_error_response(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"id": request_id, "error": {"code": code, "message": message}}


def rpc_result_response(request_id: object, result: dict[str, object]) -> dict[str, object]:
    return {"id": request_id, "result": result}


def handle_rpc_message(message: dict[str, object], entry: dict[str, object]) -> dict[str, object] | None:
    method = message.get("method")
    if not isinstance(method, str):
        return None
    if method == "initialized":
        return None

    request_id = message.get("id")
    params = message.get("params")
    params_dict = params if isinstance(params, dict) else None
    if method == "initialize":
        return rpc_result_response(request_id, {"userAgent": "codex/1.0.0"})

    append_calls(
        {
            "argv": ["json-rpc", method],
            "rpc_method": method,
            "params": params,
            "cwd": os.getcwd(),
            "instance_id": entry.get("instance_id"),
        }
    )

    default_thread_id = str(entry.get("instance_id") or "thread-test")
    state = load_server_state(f"thread-{default_thread_id}")
    errors = state.get("errors", {})
    if isinstance(errors, dict):
        error = errors.get(method)
        if isinstance(error, dict):
            code = error.get("code")
            message_text = error.get("message")
            return rpc_error_response(
                request_id,
                code if isinstance(code, int) else -32001,
                message_text if isinstance(message_text, str) else f"{method} failed",
            )

    responses = state.get("responses", {})
    if isinstance(responses, dict):
        response = responses.get(method)
        if isinstance(response, dict):
            maybe_mutate_state(method, params_dict, state)
            save_server_state(state)
            return rpc_result_response(request_id, response)

    result = build_default_result(method, params_dict, state)
    maybe_mutate_state(method, params_dict, state)
    save_server_state(state)
    return rpc_result_response(request_id, result)


def read_http_request(sock: socket.socket) -> str:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("client closed before websocket upgrade")
        data += chunk
    return data.decode("ascii")


def websocket_accept_value(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")


def extract_websocket_key(headers: str) -> str:
    for line in headers.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("missing Sec-WebSocket-Key")


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("socket closed")
        data += chunk
    return data


def read_frame(sock: socket.socket) -> tuple[int, bytes]:
    first, second = read_exact(sock, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(read_exact(sock, 2), "big")
    elif length == 127:
        length = int.from_bytes(read_exact(sock, 8), "big")
    mask = read_exact(sock, 4) if masked else b""
    payload = read_exact(sock, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def send_frame(sock: socket.socket, opcode: int, payload: bytes) -> None:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < (1 << 16):
        header = bytes([first, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 127]) + length.to_bytes(8, "big")
    sock.sendall(header + payload)


def send_json(sock: socket.socket, payload: dict[str, object]) -> None:
    send_frame(sock, 0x1, json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def handle_websocket_connection(sock: socket.socket, entry: dict[str, object]) -> None:
    sock.settimeout(0.5)
    headers = read_http_request(sock)
    websocket_key = extract_websocket_key(headers)
    sock.sendall(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {websocket_accept_value(websocket_key)}\r\n"
            "\r\n"
        ).encode("ascii")
    )
    while RUNNING:
        try:
            opcode, payload = read_frame(sock)
        except (EOFError, OSError, TimeoutError):
            return
        if opcode == 0x1:
            message = json.loads(payload.decode("utf-8"))
            if not isinstance(message, dict):
                continue
            response = handle_rpc_message(message, entry)
            if response is not None:
                send_json(sock, response)
        elif opcode == 0x8:
            try:
                send_frame(sock, 0x8, payload)
            except OSError:
                pass
            return
        elif opcode == 0x9:
            try:
                send_frame(sock, 0xA, payload)
            except OSError:
                return
        elif opcode == 0xA:
            continue


def run_fake_app_server(socket_url: str, entry: dict[str, object]) -> int:
    socket_path = socket_url.removeprefix("unix://")
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    if os.environ.get("BUDDYSWITCH_TEST_APP_SERVER_EXIT_AFTER_START") == "1":
        return 1

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(path))
        server.listen(5)
        server.settimeout(0.2)
        while RUNNING:
            try:
                client, _addr = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                handle_websocket_connection(client, entry)
            finally:
                client.close()
        return 0
    finally:
        server.close()
        path.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    codex_home = Path(os.environ["CODEX_HOME"])
    entry: dict[str, object] = {
        "argv": argv,
        "cwd": os.getcwd(),
        "home": os.environ.get("HOME"),
        "codex_home": os.environ.get("CODEX_HOME"),
        "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
        "tmpdir": os.environ.get("TMPDIR"),
        "tmp": os.environ.get("TMP"),
        "temp": os.environ.get("TEMP"),
        "active_buddy": os.environ.get("BUDDYSWITCH_ACTIVE_BUDDY"),
        "instance_id": os.environ.get("BUDDYSWITCH_INSTANCE_ID"),
        "instance_json": os.environ.get("BUDDYSWITCH_INSTANCE_JSON"),
        "project_workspace_dir": os.environ.get("BUDDYSWITCH_PROJECT_WORKSPACE_DIR"),
        "runtime_broker_socket": os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_SOCKET"),
    }
    append_calls(entry)

    if argv[:2] == ["mcp", "remove"] and len(argv) >= 3:
        config_path = codex_home / "config.toml"
        config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        config_path.write_text(remove_mcp_section(config_text, argv[2]), encoding="utf-8")
        return 0

    if argv[:2] == ["mcp", "add"] and len(argv) >= 3:
        if os.environ.get("BUDDYSWITCH_TEST_FAIL_MCP_ADD_NAME") == argv[2]:
            print(f"simulated mcp add failure: {argv[2]}", file=sys.stderr)
            return 42
        upsert_mcp_section(codex_home, argv[2], argv)
        return 0

    write_capture(build_capture_payload(entry, codex_home, argv))

    if argv[:2] == ["app-server", "--listen"] and len(argv) >= 3:
        return run_fake_app_server(argv[2], entry)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
