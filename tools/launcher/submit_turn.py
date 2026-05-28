#!/usr/bin/env python3
"""Launcher-owned shared submit-turn helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import app_server  # noqa: E402


class SubmitTurnError(RuntimeError):
    """Raised when launcher-owned turn submission fails."""


def submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
    try:
        return app_server.input_turn(socket_path, thread_id, text, permissions)
    except app_server.AppServerError as exc:
        raise SubmitTurnError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--permissions", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = submit_turn(
            socket_path=Path(args.socket),
            thread_id=args.thread_id,
            text=args.text,
            permissions=args.permissions,
        )
    except SubmitTurnError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
