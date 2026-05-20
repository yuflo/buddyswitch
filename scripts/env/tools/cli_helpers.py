#!/usr/bin/env python3
"""Shared env.tool CLI argument helpers."""

from __future__ import annotations

import argparse
import json
from typing import Any


def load_json_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--payload must be a JSON object string: {exc.msg} at char {exc.pos}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--payload must be a JSON object string")
    return payload


def operation_to_action(operation: str) -> str:
    return operation.replace("-", "_")


def add_payload_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--payload",
        required=True,
        metavar="JSON_OBJECT",
        help="JSON object string to send as env.tool args; do not pass a file path.",
    )
