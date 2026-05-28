#!/usr/bin/env python3
"""Raw launcher input wrapper."""

from __future__ import annotations

from pathlib import Path


def compose(*, raw_text: str, instance_json: Path) -> str:
    del instance_json
    return raw_text
