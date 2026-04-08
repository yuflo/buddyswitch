#!/usr/bin/env python3
"""Serve the BuddySwitch Context Panel with dynamic workspace data."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONSOLE_DIR = ROOT / "framework" / "console"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_console_snapshot import build_snapshot  # noqa: E402


class ContextPanelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CONSOLE_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/workspace-data.js":
            self.send_workspace_data()
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def send_workspace_data(self) -> None:
        data = build_snapshot()
        payload = "window.BUDDYSWITCH_WORKSPACE = "
        payload += json.dumps(data, ensure_ascii=True, indent=2)
        payload += ";\n"
        body = payload.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the BuddySwitch Context Panel.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    try:
        server = ThreadingHTTPServer((args.host, args.port), ContextPanelHandler)
    except OSError as exc:
        print(f"ERROR: cannot bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        print("Try another port, for example: python3 scripts/serve_context_panel.py --port 8766", file=sys.stderr)
        return 1
    url = f"http://{args.host}:{args.port}/"
    print(f"Serving BuddySwitch Context Panel at {url}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
