"""Fake CDP WebSocket protocol primitives shared by test servers."""

from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Protocol

from tests.support.python import executable_python_source
from tests.support.cli import write_executable


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class BinaryReader(Protocol):
    def read(self, length: int) -> bytes: ...


class BinaryWriter(Protocol):
    def write(self, content: bytes) -> object: ...

    def flush(self) -> object: ...


def websocket_accept_value(key: str) -> str:
    digest = hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def read_exact(stream: BinaryReader, length: int) -> bytes:
    chunks = b""
    while len(chunks) < length:
        chunk = stream.read(length - len(chunks))
        if not chunk:
            raise EOFError("websocket stream closed")
        chunks += chunk
    return chunks


def read_client_text_frame(stream: BinaryReader) -> str:
    first, second = read_exact(stream, 2)
    opcode = first & 0x0F
    if opcode != 0x1:
        raise ValueError(f"expected text frame, got opcode {opcode}")
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(read_exact(stream, 2), "big")
    elif length == 127:
        length = int.from_bytes(read_exact(stream, 8), "big")
    mask = read_exact(stream, 4) if masked else b""
    payload = read_exact(stream, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return payload.decode("utf-8")


def write_server_text_frame(stream: BinaryWriter, text: str) -> None:
    payload = text.encode("utf-8")
    first = 0x80 | 0x1
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < (1 << 16):
        header = bytes([first, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 127]) + length.to_bytes(8, "big")
    stream.write(header + payload)
    stream.flush()


class FakeCdpServer:
    """Parent-owned CDP endpoint bound directly to loopback port 0."""

    def __init__(self, *, activation_path: Path | None = None) -> None:
        self.activation_path = activation_path
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if owner.activation_path is not None and not owner.activation_path.exists():
                    self.send_response(503)
                    self.end_headers()
                    return
                if self.path == "/json/version":
                    payload: object = {
                        "Browser": "fake",
                        "webSocketDebuggerUrl": f"ws://127.0.0.1:{owner.port}/devtools/browser/fake",
                    }
                elif self.path == "/json/list":
                    payload = [{"id": "ready", "type": "page", "url": "about:blank"}]
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> "FakeCdpServer":
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)


def write_fake_chrome(path: Path, argv_path: Path) -> Path:
    source = executable_python_source(
        "\n".join(
            [
                "import json, signal, sys, time",
                "from pathlib import Path",
                f"argv_path = Path({str(argv_path)!r})",
                "argv_path.parent.mkdir(parents=True, exist_ok=True)",
                "with argv_path.open('a', encoding='utf-8') as handle:",
                "    handle.write(json.dumps(sys.argv[1:], ensure_ascii=True) + '\\n')",
                "signal.signal(signal.SIGTERM, lambda *_args: (_ for _ in ()).throw(SystemExit(0)))",
                "signal.signal(signal.SIGINT, lambda *_args: (_ for _ in ()).throw(SystemExit(0)))",
                "time.sleep(60)",
            ]
        )
        + "\n"
    )
    return write_executable(path, source)
